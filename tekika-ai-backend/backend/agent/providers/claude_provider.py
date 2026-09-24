"""
backend/agent/providers/claude_provider.py

Anthropic Claude API (`AsyncAnthropic`) を利用する `BaseLLMClient` 実装。
Claudeは以下の点でOpenAI/Ollamaと異なる形式を要求するため、正準フォーマットとの
相互変換を本クラス内部で行う:
- `system` メッセージはリストに含めず、トップレベルの `system` パラメータとして渡す。
- ツール定義は `{"name", "description", "input_schema"}` 形式（OpenAIの
  `{"type": "function", "function": {...}}` とは異なる）。
- アシスタントのツール呼び出しは `content` 内の `tool_use` ブロック、
  ツール実行結果は `role: "user"` メッセージ内の `tool_result` ブロックとして表現される。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import anthropic
from anthropic import AsyncAnthropic

from backend.agent.base_client import (
    BaseLLMClient,
    ChatResponse,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMResponseError,
)

logger = logging.getLogger("tekika_ai.providers.claude")

_DEFAULT_MAX_TOKENS = 4096


class ClaudeProvider(BaseLLMClient):
    """
    Anthropic Claude API と通信する `BaseLLMClient` 実装。

    Attributes:
        default_model: 既定で使用するモデル名（`.env` の `CLAUDE_DEFAULT_MODEL` で指定）。
        max_tokens: 1回の応答で生成する最大トークン数。
    """

    provider_name = "claude"

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-5",
        timeout: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(default_model=default_model, temperature=temperature)
        if not api_key:
            raise LLMAuthenticationError("Anthropic APIキーが指定されていません。")

        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.max_tokens = max_tokens

    async def aclose(self) -> None:
        await self._client.close()

    async def health_check(self) -> bool:
        """Anthropic APIへの疎通確認（モデル一覧取得）を行う。"""
        try:
            await self._client.models.list()
            return True
        except anthropic.AnthropicError:
            return False

    # ------------------------------------------------------------------
    # 正準フォーマット <-> Claude形式 の変換
    # ------------------------------------------------------------------
    def _split_system_and_messages(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        正準フォーマットのメッセージ配列から、Claude用の `system` 文字列と
        `messages` 配列（tool_use / tool_result ブロックを含む）を組み立てる。
        """
        system_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
        system_prompt = "\n\n".join(system_parts) if system_parts else None

        converted: List[Dict[str, Any]] = []
        for m in messages:
            role = m.get("role")

            if role == "system":
                continue

            if role == "tool":
                tool_use_id = m.get("tool_call_id") or m.get("name", "")
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": m.get("content", ""),
                            }
                        ],
                    }
                )
                continue

            if role == "assistant" and m.get("tool_calls"):
                content_blocks: List[Dict[str, Any]] = []
                if m.get("content"):
                    content_blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    function_info = tc.get("function", {}) or {}
                    raw_args = function_info.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = raw_args or {}
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or function_info.get("name", ""),
                            "name": function_info.get("name", ""),
                            "input": args,
                        }
                    )
                converted.append({"role": "assistant", "content": content_blocks})
                continue

            # user / assistant（ツール呼び出しなし）はそのままテキストとして渡す
            converted.append({"role": role, "content": m.get("content", "")})

        return system_prompt, converted

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """OpenAI形式のツールスキーマをClaudeの `input_schema` 形式に変換する。"""
        if not tools:
            return None

        claude_tools: List[Dict[str, Any]] = []
        for tool in tools:
            function_info = tool.get("function", {}) or {}
            claude_tools.append(
                {
                    "name": function_info.get("name", ""),
                    "description": function_info.get("description", ""),
                    "input_schema": function_info.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return claude_tools

    def _normalize_response_content(self, content_blocks: List[Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """Claudeのレスポンス `content` ブロック配列を、正準フォーマットのtext/tool_callsに変換する。"""
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for block in content_blocks:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": block.input if isinstance(block.input, dict) else {},
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
        """Anthropic Messages APIを呼び出す（非ストリーミング）。"""
        system_prompt, claude_messages = self._split_system_and_messages(messages)
        claude_tools = self._convert_tools(tools)

        request_kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": self.max_tokens,
            "messages": claude_messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if system_prompt:
            request_kwargs["system"] = system_prompt
        if claude_tools:
            request_kwargs["tools"] = claude_tools

        try:
            response = await self._client.messages.create(**request_kwargs)
        except anthropic.AuthenticationError as exc:
            raise LLMAuthenticationError(f"Anthropic APIキーが無効です: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMConnectionError(f"Anthropic APIへの接続に失敗しました: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMResponseError(
                f"Anthropic APIがエラーを返しました: {exc.status_code} {exc.message}"
            ) from exc

        content_text, tool_calls = self._normalize_response_content(response.content)

        return ChatResponse(
            content=content_text,
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
        Anthropic Messages APIをストリーミングモードで呼び出す。
        Tool Callingとストリーミングの併用は複雑になるため、ストリーミング時は
        テキスト生成のみをサポートする（Tool Callingは非ストリーミングの `chat()` /
        `run_tool_calling_loop()` 側で先に解決する設計を推奨）。
        """
        system_prompt, claude_messages = self._split_system_and_messages(messages)

        request_kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": self.max_tokens,
            "messages": claude_messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if system_prompt:
            request_kwargs["system"] = system_prompt

        try:
            async with self._client.messages.stream(**request_kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.AuthenticationError as exc:
            raise LLMAuthenticationError(f"Anthropic APIキーが無効です: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMConnectionError(f"Anthropic APIへの接続に失敗しました: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMResponseError(
                f"Anthropic APIがエラーを返しました: {exc.status_code} {exc.message}"
            ) from exc
