"""
backend/agent/providers/openai_provider.py

OpenAI Chat Completions API (`AsyncOpenAI`) を利用する `BaseLLMClient` 実装。
Tool Callingの形式はOpenAI/Ollamaでほぼ共通のため、正準フォーマットへの変換は最小限で済む。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import openai
from openai import AsyncOpenAI

from backend.agent.base_client import (
    BaseLLMClient,
    ChatResponse,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMResponseError,
)

logger = logging.getLogger("tekika_ai.providers.openai")


class OpenAIProvider(BaseLLMClient):
    """
    OpenAI API (Chat Completions) と通信する `BaseLLMClient` 実装。

    Attributes:
        default_model: 既定で使用するモデル名（例: "gpt-4o-mini"）。
        api_key: OpenAI APIキー。
        base_url: カスタムエンドポイント（Azure OpenAI互換プロキシ等）を使う場合に指定。
    """

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(default_model=default_model, temperature=temperature)
        if not api_key:
            raise LLMAuthenticationError("OpenAI APIキーが指定されていません。")

        # timeout=None を渡すと openai SDK 側でタイムアウト無制限として扱われる
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.close()

    async def health_check(self) -> bool:
        """OpenAI APIへの疎通確認（モデル一覧取得）を行う。"""
        try:
            await self._client.models.list()
            return True
        except openai.OpenAIError:
            return False

    def _normalize_tool_calls(self, message: Any) -> List[Dict[str, Any]]:
        tool_calls: List[Dict[str, Any]] = []
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        for tc in raw_tool_calls:
            tool_calls.append(
                {
                    "id": tc.id,
                    "type": getattr(tc, "type", None) or "function",  # type: "function" を明示的に付与
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
            )
        return tool_calls

    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """メッセージ履歴内の tool_calls に 'type': 'function' が欠けている場合に自動補填する"""
        sanitized = []
        for msg in messages:
            msg_copy = dict(msg)
            if "tool_calls" in msg_copy and isinstance(msg_copy["tool_calls"], list):
                new_tool_calls = []
                for tc in msg_copy["tool_calls"]:
                    if isinstance(tc, dict):
                        tc_copy = dict(tc)
                        if "type" not in tc_copy:
                            tc_copy["type"] = "function"
                        new_tool_calls.append(tc_copy)
                    else:
                        new_tool_calls.append(tc)
                msg_copy["tool_calls"] = new_tool_calls
            sanitized.append(msg_copy)
        return sanitized

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> ChatResponse:
        """OpenAI Chat Completions APIを呼び出す（非ストリーミング）。"""
        sanitized_messages = self._sanitize_messages(messages)
        request_kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": sanitized_messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**request_kwargs)
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError(f"OpenAI APIキーが無効です: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(f"OpenAI APIへの接続に失敗しました: {exc}") from exc
        except openai.APITimeoutError as exc:
            raise LLMResponseError(f"OpenAI APIの応答がタイムアウトしました: {exc}") from exc
        except openai.APIStatusError as exc:
            raise LLMResponseError(
                f"OpenAI APIがエラーを返しました: {exc.status_code} {exc.message}"
            ) from exc

        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        tool_calls = self._normalize_tool_calls(message)

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
            done=True,
        )

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        OpenAI Chat Completions APIをストリーミングモードで呼び出す。
        """
        sanitized_messages = self._sanitize_messages(messages)
        request_kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": sanitized_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }

        try:
            stream = await self._client.chat.completions.create(**request_kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError(f"OpenAI APIキーが無効です: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(f"OpenAI APIへの接続に失敗しました: {exc}") from exc
        except openai.APITimeoutError as exc:
            raise LLMResponseError(f"OpenAI APIの応答がタイムアウトしました: {exc}") from exc
        except openai.APIStatusError as exc:
            raise LLMResponseError(
                f"OpenAI APIがエラーを返しました: {exc.status_code} {exc.message}"
            ) from exc