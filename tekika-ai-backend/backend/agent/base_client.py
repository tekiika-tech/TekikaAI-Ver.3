"""
backend/agent/base_client.py

全LLMプロバイダ（Ollama / OpenAI / Anthropic Claude / Google Gemini）に共通する
抽象インターフェース `BaseLLMClient` と、共通データ構造・ユーティリティを定義する。

設計方針:
- メッセージ形式は OpenAI Chat Completions 互換の「正準フォーマット」
  ({"role": "system"|"user"|"assistant"|"tool", "content": str, ...}) を採用する。
- 各プロバイダクライアント (`backend/agent/providers/*.py`) はこの正準フォーマットと
  プロバイダ固有のAPI形式との変換を内部で行い、`chat()` / `stream_chat()` は必ず
  正準フォーマットの `ChatResponse`（tool_callsはOpenAI形式）を返す。
- これにより `run_tool_calling_loop()`（思考 -> ツール実行 -> 結果統合 -> 回答生成）を
  本クラスに一度だけ実装すれば、全プロバイダで共通して動作する。
  `orchestrator.py` はプロバイダの違いを一切意識する必要がない。
"""

from __future__ import annotations

import abc
import inspect
import json
import logging
import typing
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, get_type_hints

logger = logging.getLogger("tekika_ai.base_client")


# ---------------------------------------------------------------------------
# 共通例外
# ---------------------------------------------------------------------------
class LLMProviderError(Exception):
    """全プロバイダ共通の基底例外。"""


class LLMConnectionError(LLMProviderError):
    """プロバイダAPI/ローカルサーバへの接続に失敗した場合の例外。"""


class LLMResponseError(LLMProviderError):
    """プロバイダAPIからのレスポンスが不正、またはAPI側がエラーを返した場合の例外。"""


class LLMAuthenticationError(LLMProviderError):
    """APIキーが未設定・無効な場合の例外。"""


# ---------------------------------------------------------------------------
# Python 型 -> JSON Schema 型のマッピング（Tool Calling用スキーマ生成）
# ---------------------------------------------------------------------------
_PY_TYPE_TO_JSON_TYPE: Dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_type(py_type: Any) -> str:
    """Python の型ヒントを JSON Schema の type 文字列に変換する。"""
    origin = typing.get_origin(py_type)
    if origin is list or origin is typing.List:
        return "array"
    if origin is dict or origin is typing.Dict:
        return "object"
    if origin is typing.Union:
        args = [a for a in typing.get_args(py_type) if a is not type(None)]
        if args:
            return _python_type_to_json_type(args[0])
        return "string"
    return _PY_TYPE_TO_JSON_TYPE.get(py_type, "string")


def function_to_tool_schema(func: Callable, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Python関数のシグネチャから、OpenAI/Ollama互換のTool Calling用JSON Schemaを生成する。
    Claude / Gemini 向けの形式には、各プロバイダクライアント内部で変換される。

    Args:
        func: スキーマ化対象の関数（型ヒント必須、docstring推奨）。
        description: ツールの説明文。省略時は関数のdocstringを使用する。

    Returns:
        {"type": "function", "function": {"name", "description", "parameters"}} 形式のdict。
    """
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:  # pragma: no cover - 型ヒント解決に失敗した場合のフォールバック
        hints = {}

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        py_type = hints.get(name, str)
        json_type = _python_type_to_json_type(py_type)
        prop: Dict[str, Any] = {"type": json_type}

        # Enum のような選択肢型に対応
        if inspect.isclass(py_type) and issubclass(py_type, str) and hasattr(py_type, "__members__"):
            prop["enum"] = list(py_type.__members__.keys())

        properties[name] = prop
        if param.default is inspect._empty:
            required.append(name)

    tool_description = description or (inspect.getdoc(func) or f"{func.__name__} を実行する。")

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# ---------------------------------------------------------------------------
# 共通データ構造
# ---------------------------------------------------------------------------
@dataclass
class ToolCallResult:
    """ツール実行結果を表すデータクラス。"""

    tool_call_id: str
    name: str
    result: Any
    error: Optional[str] = None

    def to_message(self) -> Dict[str, Any]:
        """
        LLMへフィードバックするためのメッセージ形式に変換する。
        `tool_call_id` と `name` の両方を含めることで、
        OpenAI形式（tool_call_id必須）とOllama形式（name参照）の両方に対応する。
        Claude/Gemini向けの変換は各プロバイダクライアント内部で行う。
        """
        content = (
            json.dumps({"error": self.error}, ensure_ascii=False)
            if self.error
            else json.dumps(self.result, ensure_ascii=False, default=str)
        )
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": content,
        }


@dataclass
class ChatResponse:
    """LLM /chat 呼び出しの単発レスポンスをラップする正準データクラス。"""

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    done: bool = True

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ---------------------------------------------------------------------------
# 抽象基底クラス
# ---------------------------------------------------------------------------
class BaseLLMClient(abc.ABC):
    """
    全LLMプロバイダに共通する抽象基底クラス。

    サブクラスは `chat()` / `stream_chat()` / `health_check()` を実装するだけでよい。
    `run_tool_calling_loop()` は本クラスに共通実装されており、
    `chat()` が正準フォーマットの `tool_calls` を返す限り、全プロバイダで統一的に動作する。

    Attributes:
        provider_name: プロバイダ識別子（ログ出力・エラーメッセージ用）。
        default_model: このクライアントが既定で使用するモデル名。
        temperature: 既定のサンプリング温度。
    """

    provider_name: str = "base"

    def __init__(self, default_model: str, temperature: float = 0.7) -> None:
        self.default_model = default_model
        self.temperature = temperature

    async def aclose(self) -> None:
        """内部リソース（HTTPクライアント等）のクローズ処理。既定では何もしない。"""
        return None

    async def __aenter__(self) -> "BaseLLMClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """プロバイダ（ローカルサーバまたはクラウドAPI）へ接続可能かどうかを確認する。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> ChatResponse:
        """
        非ストリーミングでチャット応答を1回取得する。

        Args:
            messages: 正準フォーマットのメッセージリスト。
            model: 使用するモデル名。省略時は `default_model`。
            tools: `function_to_tool_schema()` で生成したツールスキーマのリスト。
            temperature: サンプリング温度。省略時はインスタンス設定値。

        Returns:
            ChatResponse: 正準フォーマットのレスポンス（tool_callsはOpenAI形式）。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        ストリーミングでテキストチャンクを逐次yieldする非同期ジェネレータ。

        Args:
            messages: 正準フォーマットのメッセージリスト。
            model: 使用するモデル名。
            tools: ツールスキーマ（プロバイダによってはストリーミング中のTool Calling非対応）。
            temperature: サンプリング温度。

        Yields:
            str: モデルが生成したテキストの断片。
        """
        raise NotImplementedError

    async def run_tool_calling_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_registry: Dict[str, Callable],
        tool_schemas: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_iterations: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        「思考 -> ツール実行 -> 結果統合 -> 回答生成」のループを全プロバイダ共通で実装する。

        `chat()` が正準フォーマットの `tool_calls`
        (`[{"id":..., "function": {"name":..., "arguments": {...}}}]`) を返す限り、
        このメソッドはプロバイダの違いを一切意識せず動作する。

        Args:
            messages: 初期メッセージ履歴（system/userを含む正準フォーマット）。
            tool_registry: ツール名 -> 実行可能関数 の辞書。
            tool_schemas: `function_to_tool_schema()` で生成したスキーマのリスト。
            model: 使用モデル名。
            max_iterations: 無限ループ防止のための最大反復回数。

        Returns:
            List[Dict[str, Any]]: ループ終了時点での完全なメッセージ履歴
                （最終アシスタント応答を含む）。
        """
        working_messages = list(messages)

        for iteration in range(max_iterations):
            response = await self.chat(
                messages=working_messages,
                model=model,
                tools=tool_schemas,
            )

            assistant_message: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
            }
            if response.tool_calls:
                assistant_message["tool_calls"] = response.tool_calls
            working_messages.append(assistant_message)

            if not response.has_tool_calls:
                logger.info(
                    "[%s] Tool Callingループ完了（%d回の反復）", self.provider_name, iteration + 1
                )
                return working_messages

            for call in response.tool_calls:
                function_info = call.get("function", {}) or {}
                tool_name = function_info.get("name", "")
                raw_args = function_info.get("arguments", {})

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw_args or {}

                tool_func = tool_registry.get(tool_name)
                call_id = call.get("id") or tool_name

                if tool_func is None:
                    result = ToolCallResult(
                        tool_call_id=call_id,
                        name=tool_name,
                        result=None,
                        error=f"未登録のツールが呼び出されました: {tool_name}",
                    )
                else:
                    try:
                        if inspect.iscoroutinefunction(tool_func):
                            output = await tool_func(**args)
                        else:
                            output = tool_func(**args)
                        result = ToolCallResult(tool_call_id=call_id, name=tool_name, result=output)
                    except Exception as exc:  # noqa: BLE001 - ツール実行エラーをそのままフィードバック
                        logger.exception(
                            "[%s] ツール実行中にエラーが発生しました: %s", self.provider_name, tool_name
                        )
                        result = ToolCallResult(
                            tool_call_id=call_id,
                            name=tool_name,
                            result=None,
                            error=str(exc),
                        )

                working_messages.append(result.to_message())

        logger.warning(
            "[%s] Tool Callingループが最大反復回数(%d)に達しました", self.provider_name, max_iterations
        )
        return working_messages
