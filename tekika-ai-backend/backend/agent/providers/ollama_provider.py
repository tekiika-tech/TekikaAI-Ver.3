"""
backend/agent/providers/ollama_provider.py

ローカルOllama (既定: http://localhost:11434) と通信する `BaseLLMClient` 実装。
外部クラウドAPIは使用しない。マスターが導入したタイムアウト無効化オプション
（`timeout=None` で接続ごとの読み込みタイムアウトを無制限にする挙動）を引き継いでいる。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx

from backend.agent.base_client import (
    BaseLLMClient,
    ChatResponse,
    LLMConnectionError,
    LLMResponseError,
)

logger = logging.getLogger("tekika_ai.providers.ollama")

# 後方互換のためのエイリアス（過去バージョンの backend/agent/ollama_client.py が
# 送出していた例外名をそのまま利用したいコードのために残している）
OllamaConnectionError = LLMConnectionError
OllamaResponseError = LLMResponseError


class OllamaProvider(BaseLLMClient):
    """
    ローカルOllama APIとの通信を担当する `BaseLLMClient` 実装。

    Attributes:
        base_url: OllamaサーバのベースURL（既定: http://localhost:11434）。
        default_model: 既定で使用するモデル名。
        timeout: リクエストタイムアウト設定（秒数、httpx.Timeoutオブジェクト、
            またはNoneで無制限）。
    """

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen2.5:1.5b",
        timeout: Union[float, httpx.Timeout, None] = None,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(default_model=default_model, temperature=temperature)
        self.base_url = base_url.rstrip("/")

        # タイムアウトの設定：数値の場合は接続10秒/読み込み指定秒数、Noneの場合は無制限（制限なし）。
        # ローカルの重いモデルでは応答生成に数分かかることがあるため、既定はNone（無制限）としている。
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
            raise LLMConnectionError(
                f"Ollamaサーバへの接続に失敗しました ({self.base_url}): {exc}"
            ) from exc

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> ChatResponse:
        """
        Ollama /api/chat エンドポイントを呼び出す（非ストリーミング）。

        Args:
            messages: 正準フォーマット（OpenAI互換）のメッセージリスト。
            model: 使用するモデル名。省略時は default_model。
            tools: Tool Calling用のツールスキーマリスト。
            temperature: サンプリング温度。省略時はインスタンス設定値。

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
            # timeout=None を直接指定して個別リクエストのタイムアウトを無効化する
            resp = await self._client.post("/api/chat", json=payload, timeout=None)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"ローカルOllamaサーバに接続できません。'ollama serve' が起動しているか確認してください: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise LLMResponseError(
                f"Ollamaの応答処理がタイムアウトしました。処理時間が長すぎるか、モデルが重い可能性があります: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMResponseError(
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
            messages: 正準フォーマットのメッセージリスト。
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
            raise LLMConnectionError(
                f"ローカルOllamaサーバに接続できません。'ollama serve' が起動しているか確認してください: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise LLMResponseError(f"Ollamaの応答処理がタイムアウトしました。: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMResponseError(
                f"Ollama APIがエラーを返しました: {exc.response.status_code} {exc.response.text}"
            ) from exc
