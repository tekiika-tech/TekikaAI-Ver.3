"""
backend/agent/ollama_client.py

ローカルOllama (http://localhost:11434) と通信するクライアント。
Tool Calling (Function Calling) に対応し、Python関数からJSON Schemaを
自動生成してOllama APIに渡し、tool_callsの判定・実行・結果フィードバックの
ループを処理する。外部クラウドAPIは一切使用しない。
"""

from __future__ import annotations

import inspect
import json
import logging
import typing
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union, get_type_hints

import httpx

logger = logging.getLogger("tekika_ai.ollama_client")


class OllamaConnectionError(Exception):
    """ローカルOllamaサーバへの接続に失敗した場合の例外。"""


class OllamaResponseError(Exception):
    """Ollamaからのレスポンスが不正な場合の例外。"""


# ---------------------------------------------------------------------------
# Python 型 -> JSON Schema 型のマッピング
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
    Python関数のシグネチャからOllama Tool Calling用のJSON Schemaを生成する。

    Args:
        func: スキーマ化対象の関数（型ヒント必須、docstring推奨）。
        description: ツールの説明文。省略時は関数のdocstringを使用する。

    Returns:
        Ollama /api/chat の `tools` パラメータに渡せる dict。
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


@dataclass
class ToolCallResult:
    """ツール実行結果を表すデータクラス。"""

    tool_call_id: str
    name: str
    result: Any
    error: Optional[str] = None

    def to_message(self) -> Dict[str, Any]:
        """Ollamaへフィードバックするためのメッセージ形式に変換する。"""
        content = (
            json.dumps({"error": self.error}, ensure_ascii=False)
            if self.error
            else json.dumps(self.result, ensure_ascii=False, default=str)
        )
        return {
            "role": "tool",
            "content": content,
            "name": self.name,
        }


@dataclass
class ChatResponse:
    """Ollama /api/chat の単発レスポンスをラップするデータクラス。"""

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    done: bool = True

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class OllamaClient:
    """
    ローカルOllama APIとの通信を担当するクライアント。

    Attributes:
        base_url: OllamaサーバのベースURL（既定: http://localhost:11434）。
        default_model: 既定で使用するモデル名。
        timeout: リクエストタイムアウト設定（秒数、または httpx.Timeout オブジェクト）。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen2.5:1.5b",
        timeout: Union[float, httpx.Timeout, None] = None,
        temperature: float = 0.7,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.temperature = temperature

        # タイムアウトの設定：数値の場合は接続10秒/読み込み指定秒数、Noneの場合は無制限（制限なし）
        if isinstance(timeout, (int, float)):
            self.timeout = httpx.Timeout(timeout, connect=10.0)
        elif timeout is None:
            self.timeout = httpx.Timeout(None, connect=10.0)
        else:
            self.timeout = timeout

        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
    async def aclose(self) -> None:
        """内部HTTPクライアントを閉じる。アプリケーション終了時に呼び出すこと。"""
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    async def health_check(self) -> bool:
        """ローカルOllamaサーバが起動しているかを確認する。"""
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> List[str]:
        """ローカルにダウンロード済みのモデル一覧を取得する。"""
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(
                f"Ollamaサーバへの接続に失敗しました ({self.base_url}): {exc}"
            ) from exc

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """
        Ollama /api/chat エンドポイントを呼び出す（非ストリーミング）。

        Args:
            messages: OpenAI形式のメッセージリスト。
            model: 使用するモデル名。省略時は default_model。
            tools: Tool Calling用のツールスキーマリスト。
            temperature: サンプリング温度。省略時はインスタンス設定値。
            stream: 常にFalseで内部処理する（ストリームは stream_chat を使用）。

        Returns:
            ChatResponse: モデルの応答内容とtool_calls。
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature if temperature is not None else self.temperature},
        }
        if tools:
            payload["tools"] = tools

        try:
            # timeout=None を直接指定して個別リクエストのタイムアウトを無効化
            resp = await self._client.post("/api/chat", json=payload, timeout=None)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"ローカルOllamaサーバに接続できません。'ollama serve' が起動しているか確認してください: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise OllamaResponseError(
                f"Ollamaの応答処理がタイムアウトしました。処理時間が長すぎるか、モデルが重い可能性があります: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaResponseError(
                f"Ollama APIがエラーを返しました: {exc.response.status_code} {exc.response.text}"
            ) from exc

        data = resp.json()
        message = data.get("message", {}) or {}
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls", []) or []

        return ChatResponse(content=content, tool_calls=tool_calls, raw=data, done=data.get("done", True))

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Ollama /api/chat をストリーミングモードで呼び出し、テキストチャンクを逐次yieldする。

        Args:
            messages: OpenAI形式のメッセージリスト。
            model: 使用するモデル名。
            tools: Tool Callingスキーマ（ストリーミング中は基本的に最終応答のみに使用）。
            temperature: サンプリング温度。

        Yields:
            str: モデルが生成したテキストの断片。
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature if temperature is not None else self.temperature},
        }
        if tools:
            payload["tools"] = tools

        try:
            # ストリーミング時もタイムアウトを無効化する
            async with self._client.stream("POST", "/api/chat", json=payload, timeout=None) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Ollamaストリームの行をJSONとして解析できませんでした: %s", line)
                        continue
                    message = chunk.get("message", {}) or {}
                    piece = message.get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"ローカルOllamaサーバに接続できません。'ollama serve' が起動しているか確認してください: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise OllamaResponseError(
                f"Ollamaの応答処理がタイムアウトしました。: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaResponseError(
                f"Ollama APIがエラーを返しました: {exc.response.status_code} {exc.response.text}"
            ) from exc

    async def run_tool_calling_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_registry: Dict[str, Callable],
        tool_schemas: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_iterations: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        「思考 -> ツール実行 -> 結果統合 -> 回答生成」のループを完全実装する。

        Args:
            messages: 初期メッセージ履歴（system/userを含む）。
            tool_registry: ツール名 -> 実行可能関数 の辞書。
            tool_schemas: function_to_tool_schema() で生成したスキーマのリスト。
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
                # ツール呼び出しがなければ最終回答とみなしループ終了
                logger.info("Tool Callingループ完了（%d回の反復）", iteration + 1)
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
                call_id = call.get("id", tool_name)

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
                        logger.exception("ツール実行中にエラーが発生しました: %s", tool_name)
                        result = ToolCallResult(
                            tool_call_id=call_id,
                            name=tool_name,
                            result=None,
                            error=str(exc),
                        )

                working_messages.append(result.to_message())

        logger.warning("Tool Callingループが最大反復回数(%d)に達しました", max_iterations)
        return working_messages