"""
backend/agent/factory.py

設定（`.env` の `LLM_PROVIDER` や各プロバイダのAPIキー）、または個別のプロバイダ名指定に
応じて、適切な `BaseLLMClient` 実装を動的に生成する `LLMFactory` を提供する。
"""

from __future__ import annotations

import logging
from typing import Dict

from backend.agent.base_client import BaseLLMClient, LLMProviderError
from backend.agent.providers.claude_provider import ClaudeProvider
from backend.agent.providers.gemini_provider import GeminiProvider
from backend.agent.providers.ollama_provider import OllamaProvider
from backend.agent.providers.openai_provider import OpenAIProvider
from backend.config import Settings

logger = logging.getLogger("tekika_ai.factory")

# サポートするプロバイダ識別子の一覧（新しいプロバイダを追加する際はここにも追記する）
SUPPORTED_PROVIDERS: tuple[str, ...] = ("ollama", "openai", "claude", "gemini")


class LLMFactory:
    """`Settings` に基づき、`BaseLLMClient` 実装を生成するファクトリ。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_client(self, provider: str) -> BaseLLMClient:
        """
        指定されたプロバイダ名に対応する `BaseLLMClient` を1つ生成する。

        Args:
            provider: "ollama" / "openai" / "claude" / "gemini" のいずれか（大文字小文字を無視）。

        Returns:
            BaseLLMClient: 生成されたクライアントインスタンス。

        Raises:
            LLMProviderError: 未対応のプロバイダ名、またはAPIキー未設定の場合。
        """
        provider_key = provider.lower().strip()
        settings = self.settings

        if provider_key == "ollama":
            return OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                default_model=settings.OLLAMA_DEFAULT_MODEL,
                timeout=settings.OLLAMA_REQUEST_TIMEOUT,
                temperature=settings.OLLAMA_TEMPERATURE,
            )

        if provider_key == "openai":
            if not settings.OPENAI_API_KEY:
                raise LLMProviderError(
                    "OPENAI_API_KEY が設定されていません（.env を確認してください）。"
                )
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                default_model=settings.OPENAI_DEFAULT_MODEL,
                base_url=settings.OPENAI_BASE_URL,
                timeout=settings.OPENAI_REQUEST_TIMEOUT,
                temperature=settings.LLM_TEMPERATURE,
            )

        if provider_key == "claude":
            if not settings.ANTHROPIC_API_KEY:
                raise LLMProviderError(
                    "ANTHROPIC_API_KEY が設定されていません（.env を確認してください）。"
                )
            return ClaudeProvider(
                api_key=settings.ANTHROPIC_API_KEY,
                default_model=settings.CLAUDE_DEFAULT_MODEL,
                timeout=settings.ANTHROPIC_REQUEST_TIMEOUT,
                temperature=settings.LLM_TEMPERATURE,
            )

        if provider_key == "gemini":
            if not settings.GOOGLE_API_KEY:
                raise LLMProviderError(
                    "GOOGLE_API_KEY が設定されていません（.env を確認してください）。"
                )
            return GeminiProvider(
                api_key=settings.GOOGLE_API_KEY,
                default_model=settings.GEMINI_DEFAULT_MODEL,
                timeout=settings.GEMINI_REQUEST_TIMEOUT,
                temperature=settings.LLM_TEMPERATURE,
            )

        raise LLMProviderError(
            f"未対応のプロバイダが指定されました: '{provider}' "
            f"（対応プロバイダ: {', '.join(SUPPORTED_PROVIDERS)}）"
        )

    def create_available_clients(self) -> Dict[str, BaseLLMClient]:
        """
        設定上で利用可能な（＝APIキーが設定されている、または鍵不要のOllamaのような）
        プロバイダをすべてインスタンス化し、`{プロバイダ名: クライアント}` の辞書として返す。
        APIキー未設定などで生成に失敗したプロバイダはスキップし、ログに記録する。

        Returns:
            Dict[str, BaseLLMClient]: 利用可能な全プロバイダのクライアント辞書。
                Ollamaは鍵不要のため、通常は常に含まれる。
        """
        clients: Dict[str, BaseLLMClient] = {}
        for provider_key in SUPPORTED_PROVIDERS:
            try:
                clients[provider_key] = self.create_client(provider_key)
                logger.info("プロバイダ '%s' のクライアントを初期化しました。", provider_key)
            except LLMProviderError as exc:
                logger.info("プロバイダ '%s' はスキップされました: %s", provider_key, exc)
        return clients
