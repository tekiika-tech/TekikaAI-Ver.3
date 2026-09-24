"""
backend/agent/providers/gemini_provider.py

Google Gemini API (`google-genai` SDK) を利用する `BaseLLMClient` 実装。
Geminiは以下の点でOpenAI/Ollamaと異なる形式を要求するため、正準フォーマットとの
相互変換を本クラス内部で行う:
- ロール名が "user" / "model"（"assistant"ではない）。
- `system` メッセージは `GenerateContentConfig.system_instruction` として渡す。
- ツール呼び出しは `Part.function_call`、実行結果は `Part.function_response` として表現される。
- Geminiはツール呼び出しに明示的なcall IDを持たないため、関数名をIDの代用として使用する。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import google.genai as genai
import google.genai.errors as genai_errors
from google.genai import types as genai_types

from backend.agent.base_client import (
    BaseLLMClient,
    ChatResponse,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMResponseError,
)

logger = logging.getLogger("tekika_ai.providers.gemini")


class GeminiProvider(BaseLLMClient):
    """
    Google Gemini API と通信する `BaseLLMClient` 実装。

    Attributes:
        default_model: 既定で使用するモデル名（`.env` の `GEMINI_DEFAULT_MODEL` で指定）。
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-2.0-flash",
        timeout: Optional[float] = None,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(default_model=default_model, temperature=temperature)
        if not api_key:
            raise LLMAuthenticationError("Google (Gemini) APIキーが指定されていません。")

        http_options = None
        if timeout is not None:
            # google-genai は httpリクエストのタイムアウトをミリ秒単位で指定する
            http_options = genai_types.HttpOptions(timeout=int(timeout * 1000))

        self._client = genai.Client(api_key=api_key, http_options=http_options)

    async def aclose(self) -> None:
        # google-genai の Client は明示的なクローズ処理を必要としない
        return None

    async def health_check(self) -> bool:
        """Gemini APIへの疎通確認（モデル一覧取得）を行う。"""
        try:
            await self._client.aio.models.list()
            return True
        except genai_errors.APIError:
            return False
        except Exception:  # noqa: BLE001 - SDKの想定外エラーもヘルスチェック失敗として扱う
            return False

    # ------------------------------------------------------------------
    # 正準フォーマット <-> Gemini形式 の変換
    # ------------------------------------------------------------------
    def _convert_messages(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], List[genai_types.Content]]:
        """正準フォーマットのメッセージ配列を、Geminiの `Content` 配列に変換する。"""
        system_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
        system_instruction = "\n\n".join(system_parts) if system_parts else None

        contents: List[genai_types.Content] = []
        for m in messages:
            role = m.get("role")

            if role == "system":
                continue

            if role == "user":
                contents.append(
                    genai_types.Content(role="user", parts=[genai_types.Part(text=m.get("content", ""))])
                )

            elif role == "assistant":
                parts: List[genai_types.Part] = []
                if m.get("content"):
                    parts.append(genai_types.Part(text=m["content"]))
                for tc in m.get("tool_calls", []) or []:
                    function_info = tc.get("function", {}) or {}
                    raw_args = function_info.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = raw_args or {}
                    parts.append(
                        genai_types.Part(
                            function_call=genai_types.FunctionCall(
                                name=function_info.get("name", ""), args=args
                            )
                        )
                    )
                if parts:
                    contents.append(genai_types.Content(role="model", parts=parts))

            elif role == "tool":
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part(
                                function_response=genai_types.FunctionResponse(
                                    name=m.get("name", ""),
                                    response={"result": m.get("content", "")},
                                )
                            )
                        ],
                    )
                )

        return system_instruction, contents

    def _convert_tools(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[genai_types.Tool]]:
        """OpenAI形式のツールスキーマをGeminiの `FunctionDeclaration` 形式に変換する。"""
        if not tools:
            return None

        declarations: List[genai_types.FunctionDeclaration] = []
        for tool in tools:
            function_info = tool.get("function", {}) or {}
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=function_info.get("name", ""),
                    description=function_info.get("description", ""),
                    parameters=function_info.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                )
            )
        return [genai_types.Tool(function_declarations=declarations)]

    def _normalize_response(self, response: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """Geminiのレスポンスを、正準フォーマットのtext/tool_callsに変換する。"""
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "", []

        candidate_content = getattr(candidates[0], "content", None)
        parts = getattr(candidate_content, "parts", None) or []

        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                text_parts.append(part_text)

            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                args = dict(function_call.args) if function_call.args else {}
                tool_calls.append(
                    {
                        # Geminiは明示的なtool_call idを持たないため関数名をIDの代用とする
                        "id": function_call.name,
                        "function": {
                            "name": function_call.name,
                            "arguments": args,
                        },
                    }
                )

        return "".join(text_parts), tool_calls

    # ------------------------------------------------------------------
    # chat / stream_chat
    # ------------------------------------------------------------------
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> ChatResponse:
        """Gemini generateContent APIを呼び出す（非ストリーミング）。"""
        system_instruction, contents = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools)

        config = genai_types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self.temperature,
            system_instruction=system_instruction,
            tools=gemini_tools,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=config,
            )
        except genai_errors.ClientError as exc:
            raise LLMAuthenticationError(f"Gemini APIキーが無効、またはリクエストが不正です: {exc}") from exc
        except genai_errors.ServerError as exc:
            raise LLMConnectionError(f"Gemini APIサーバでエラーが発生しました: {exc}") from exc
        except genai_errors.APIError as exc:
            raise LLMResponseError(f"Gemini APIがエラーを返しました: {exc}") from exc

        content_text, tool_calls = self._normalize_response(response)

        return ChatResponse(content=content_text, tool_calls=tool_calls, raw={}, done=True)

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Gemini generateContentStream APIをストリーミングモードで呼び出す。
        Tool Callingはストリーミング時は解決しないため、テキスト生成のみをサポートする。
        """
        system_instruction, contents = self._convert_messages(messages)

        config = genai_types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self.temperature,
            system_instruction=system_instruction,
        )

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model or self.default_model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                chunk_text = getattr(chunk, "text", None)
                if chunk_text:
                    yield chunk_text
        except genai_errors.ClientError as exc:
            raise LLMAuthenticationError(f"Gemini APIキーが無効、またはリクエストが不正です: {exc}") from exc
        except genai_errors.ServerError as exc:
            raise LLMConnectionError(f"Gemini APIサーバでエラーが発生しました: {exc}") from exc
        except genai_errors.APIError as exc:
            raise LLMResponseError(f"Gemini APIがエラーを返しました: {exc}") from exc
