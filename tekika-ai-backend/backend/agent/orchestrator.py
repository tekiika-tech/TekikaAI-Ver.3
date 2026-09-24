"""
backend/agent/orchestrator.py

AgentOrchestrator: 複数のLLMプロバイダ（`BaseLLMClient` 実装）/ MemoryStore /
各種ローカルツールを統括し、ユーザーの自然な指示を解釈してタスクを実行するオーケストレータ。

`.env` の `LLM_PROVIDER` 設定、またはリクエストごとの `provider` 指定により、
Ollama / OpenAI / Anthropic Claude / Google Gemini を動的に切り替えて利用できる。
プロバイダ間の差異（Tool Callingの形式など）はすべて各 `BaseLLMClient` 実装内で
吸収されているため、本クラスはプロバイダの違いを一切意識しない。

- Quality Mode: 思考 -> ツール実行 -> 結果統合 -> 回答生成 のループ（Tool Calling）。
- Speed Mode: 単一ステップでLLMに直接回答させる（ツールは使用しない）。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from backend.agent.base_client import BaseLLMClient, LLMProviderError, function_to_tool_schema
from backend.agent.memory import MemoryStore
from backend.config import AgentMode, Settings

logger = logging.getLogger("tekika_ai.orchestrator")


_SYSTEM_PROMPT_TEMPLATE = """あなたは「Tekika Agent Intellect」（愛称: Tekika AI）です。
ユーザーのローカルPC上で動作するプライベートAIエージェントであり、
現在は「{provider_name}」（モデル: {model_name}）を頭脳として応答しています。

以下のローカルツールを必要に応じて呼び出すことができます:
{tool_list}

方針:
1. ユーザーの日本語による自然な指示を正確に解釈すること。
2. ファイル操作・Git操作・画像生成・プラグイン登録などは、必ず対応するツールを呼び出して実行すること。
3. ツールの実行結果を踏まえて、わかりやすい日本語で最終的な回答をまとめること。
4. 不確実な情報を断定的に述べないこと。

コード・ファイル内容・ディレクトリ構造を示す際のルール:
5. コードやディレクトリ構造を示す際は、必ずMarkdownのコードブロック（```言語名 ... ```）を使い、
   拡張子に応じて適切な言語名を指定すること
   （例: .py→python, .ts→typescript, .tsx→tsx, .js→javascript, .json→json, .css→css,
   .html→html, .ps1→powershell, .bat/.cmd→bat, .md→markdown, ディレクトリツリー→text）。
6. 可能な場合は、コードブロックの直前に「### `ファイル名` — 言語名」のような見出しを付けること。
7. ユーザーが「〇〇の内容を表示して」「〇〇を見せて」のようにファイル内容を求めた場合は、
   説明だけで済ませず、必ず read_file ツールを呼び出して実際の内容を取得し、
   省略せずコードブロックとして提示すること。
8. list_directory の結果を提示する際は、その一覧をあなたの文章内でJSONやツリー文字列として
   書き起こす必要はない。構造化された結果はフロントエンド側が自動的に見やすく表示するため、
   あなたは一覧の内容について簡潔に触れるだけでよい。
"""


class AgentOrchestrator:
    """
    エージェントの中枢制御を担うクラス。

    Attributes:
        settings: アプリケーション設定。
        clients: `{プロバイダ名: BaseLLMClientインスタンス}` の辞書
            （`LLMFactory.create_available_clients()` で構築される）。
        memory: 会話履歴・長期記憶ストア。
        default_provider: `provider` 未指定時に使用する既定プロバイダ名。
        tool_registry: ツール名 -> 実行関数の辞書。
        tool_schemas: Tool Calling用のスキーマリスト（OpenAI/Ollama互換形式）。
    """

    def __init__(
        self,
        settings: Settings,
        clients: Dict[str, BaseLLMClient],
        memory: MemoryStore,
        default_provider: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self.clients = clients
        self.memory = memory
        self.default_provider = (default_provider or settings.LLM_PROVIDER or "ollama").lower().strip()
        self.tool_registry: Dict[str, Callable] = {}
        self.tool_schemas: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # プロバイダ選択
    # ------------------------------------------------------------------
    def get_client(self, provider: Optional[str] = None) -> BaseLLMClient:
        """
        指定されたプロバイダ名（省略時は既定プロバイダ）に対応するクライアントを取得する。

        Raises:
            LLMProviderError: 指定プロバイダが未設定・未対応の場合
                （APIキー未設定でクライアントが生成されていない場合を含む）。
        """
        provider_key = (provider or self.default_provider or "ollama").lower().strip()
        client = self.clients.get(provider_key)
        if client is None:
            available = ", ".join(sorted(self.clients.keys())) or "(なし)"
            raise LLMProviderError(
                f"プロバイダ '{provider_key}' は現在利用できません（利用可能: {available}）。"
                "APIキーが .env に正しく設定されているか確認してください。"
            )
        return client

    def list_available_providers(self) -> List[Dict[str, Any]]:
        """現在利用可能な全プロバイダの一覧（名前・既定モデル・既定プロバイダかどうか）を返す。"""
        return [
            {
                "provider": name,
                "default_model": client.default_model,
                "is_default": name == self.default_provider,
            }
            for name, client in sorted(self.clients.items())
        ]

    # ------------------------------------------------------------------
    # ツール登録
    # ------------------------------------------------------------------
    def register_tool(self, func: Callable, description: Optional[str] = None) -> None:
        """
        新しいツール（Python関数）をオーケストレータに登録する。
        関数のシグネチャから自動的にJSON Schemaを生成する。
        """
        schema = function_to_tool_schema(func, description=description)
        self.tool_registry[func.__name__] = func
        self.tool_schemas.append(schema)
        logger.info("ツールを登録しました: %s", func.__name__)

    def unregister_tool(self, tool_name: str) -> None:
        """登録済みツールを削除する（プラグインのホットリロード時などに使用）。"""
        self.tool_registry.pop(tool_name, None)
        self.tool_schemas = [
            s for s in self.tool_schemas if s.get("function", {}).get("name") != tool_name
        ]
        logger.info("ツールを解除しました: %s", tool_name)

    def _build_system_prompt(self, client: BaseLLMClient) -> str:
        if self.tool_registry:
            tool_list = "\n".join(f"- {name}" for name in sorted(self.tool_registry.keys()))
        else:
            tool_list = "（現在登録されているツールはありません）"
        return _SYSTEM_PROMPT_TEMPLATE.format(
            provider_name=client.provider_name,
            model_name=client.default_model,
            tool_list=tool_list,
        )

    def _build_messages(
        self,
        session_id: str,
        user_input: str,
        client: BaseLLMClient,
        regenerate: bool = False,
    ) -> List[Dict[str, Any]]:
        history = self.memory.get_history(session_id, limit=100)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt(client)}
        ]
        for item in history:
            role = item["role"]
            if role == "tool":
                # 過去のtoolメッセージはLLMコンテキストに含めない（トークン節約）
                continue
            messages.append({"role": role, "content": item["content"]})
        if not regenerate:
            # 通常送信時のみ、新規のユーザー発言を末尾に追加する。
            # regenerate=True の場合、user_input は既に history の末尾に
            # 保存済みの発言と同一なので、二重に追加しない（再試行時の重複防止）。
            messages.append({"role": "user", "content": user_input})
        return messages

    @staticmethod
    def _find_tool_call_arguments(
        history: List[Dict[str, Any]], tool_call_id: str
    ) -> Dict[str, Any]:
        """指定されたtool_call_idに対応する、直前のassistantメッセージ内のツール呼び出し引数を取得する。"""
        for msg in history:
            if msg.get("role") != "assistant":
                continue
            for call in msg.get("tool_calls", []) or []:
                if call.get("id") == tool_call_id:
                    raw_args = call.get("function", {}).get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            return json.loads(raw_args)
                        except json.JSONDecodeError:
                            return {}
                    return raw_args or {}
        return {}

    @staticmethod
    def _build_tool_result_events(full_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Tool Callingループの実行後、履歴内の全ての role="tool" メッセージを
        構造化イベント（{"type": "tool_result", "name", "status", "arguments", "result"}）に変換する。
        LLMの文章生成に依存せず、実際のツール実行結果をそのままフロントエンドへ渡すために使用する。
        """
        events: List[Dict[str, Any]] = []
        for msg in full_history:
            if msg.get("role") != "tool":
                continue

            raw_content = msg.get("content", "")
            try:
                parsed_result: Any = json.loads(raw_content)
            except (TypeError, ValueError):
                parsed_result = raw_content

            is_error = isinstance(parsed_result, dict) and set(parsed_result.keys()) == {"error"}
            arguments = AgentOrchestrator._find_tool_call_arguments(
                full_history, msg.get("tool_call_id", "")
            )

            events.append(
                {
                    "type": "tool_result",
                    "name": msg.get("name", ""),
                    "status": "error" if is_error else "done",
                    "arguments": arguments,
                    "result": parsed_result,
                }
            )
        return events

    # ------------------------------------------------------------------
    # メイン実行エントリポイント
    # ------------------------------------------------------------------
    async def handle_user_message(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        mode: Optional[AgentMode] = None,
        provider: Optional[str] = None,
        regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        ユーザーメッセージを処理し、最終的な応答を返す（非ストリーミング）。

        Args:
            user_input: ユーザーからの自然言語指示。
            session_id: 会話セッションID。省略時は新規生成。
            mode: QUALITY / SPEED。省略時は設定値のデフォルトモード。
            provider: 使用するLLMプロバイダ名。省略時は既定プロバイダ（`.env` の `LLM_PROVIDER`）。
            regenerate: True の場合、ユーザー発言を新規保存せず、既存の履歴のみを使って
                直前の回答を再生成する（「再試行」機能用）。

        Returns:
            Dict[str, Any]: {"session_id", "response", "mode", "tool_trace", "provider", "model"}
        """
        session_id = session_id or str(uuid.uuid4())
        active_mode = mode or self.settings.AGENT_MODE
        client = self.get_client(provider)

        if not regenerate:
            self.memory.add_message(session_id, "user", user_input)
        messages = self._build_messages(session_id, user_input, client, regenerate=regenerate)

        if active_mode == AgentMode.SPEED:
            response = await client.chat(messages=messages)
            final_text = response.content
            self.memory.add_message(session_id, "assistant", final_text)
            return {
                "session_id": session_id,
                "response": final_text,
                "mode": AgentMode.SPEED.value,
                "tool_trace": [],
                "provider": client.provider_name,
                "model": client.default_model,
            }

        # ---- Quality Mode: Tool Calling ループ ----
        full_history = await client.run_tool_calling_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            tool_schemas=self.tool_schemas,
            max_iterations=self.settings.OLLAMA_MAX_TOOL_ITERATIONS,
        )

        tool_trace: List[Dict[str, Any]] = []
        final_text = ""
        for msg in full_history:
            if msg["role"] == "assistant":
                final_text = msg.get("content", "") or final_text
            elif msg["role"] == "tool":
                tool_trace.append(msg)

        self.memory.add_message(session_id, "assistant", final_text)
        return {
            "session_id": session_id,
            "response": final_text,
            "mode": AgentMode.QUALITY.value,
            "tool_trace": tool_trace,
            "provider": client.provider_name,
            "model": client.default_model,
        }

    async def stream_user_message(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        mode: Optional[AgentMode] = None,
        provider: Optional[str] = None,
        regenerate: bool = False,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        ユーザーメッセージを処理し、応答をストリーミングでyieldする。
        Quality Mode でツール呼び出しが発生した場合は、まずツールループを
        非ストリーミングで解決してから、最終回答のみをストリーミング再生成する。

        yieldされる要素は以下のいずれかの形:
            {"type": "delta", "text": str}         — 生成テキストの断片
            {"type": "tool_result", "name": str, "status": str,
             "arguments": dict, "result": Any}      — 実行済みツールの構造化された結果

        Args:
            regenerate: True の場合、ユーザー発言を新規保存せず、既存の履歴のみを使って
                直前の回答を再生成する（「再試行」機能用）。
        """
        session_id = session_id or str(uuid.uuid4())
        active_mode = mode or self.settings.AGENT_MODE
        client = self.get_client(provider)

        if not regenerate:
            self.memory.add_message(session_id, "user", user_input)
        messages = self._build_messages(session_id, user_input, client, regenerate=regenerate)

        if active_mode == AgentMode.SPEED:
            collected = []
            async for chunk in client.stream_chat(messages=messages):
                collected.append(chunk)
                yield {"type": "delta", "text": chunk}
            self.memory.add_message(session_id, "assistant", "".join(collected))
            return

        # Quality Mode: 先にツールループを解決
        full_history = await client.run_tool_calling_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            tool_schemas=self.tool_schemas,
            max_iterations=self.settings.OLLAMA_MAX_TOOL_ITERATIONS,
        )

        # 実行された各ツールの構造化結果を、最終回答のストリーミング開始前に送出する。
        # LLMの文章生成に依存せず、実際のtool result（例: list_directoryの一覧）を
        # フロントエンドがそのままUIコンポーネントとして描画できるようにするため。
        for event in self._build_tool_result_events(full_history):
            yield event

        # ツール実行結果を踏まえた最終回答をストリーミングで再生成
        collected = []
        async for chunk in client.stream_chat(messages=full_history):
            collected.append(chunk)
            yield {"type": "delta", "text": chunk}

        final_text = "".join(collected)
        if not final_text:
            # フォールバック: ツールループ内の最終assistantメッセージを使用
            for msg in reversed(full_history):
                if msg["role"] == "assistant" and msg.get("content"):
                    final_text = msg["content"]
                    break
        self.memory.add_message(session_id, "assistant", final_text)
