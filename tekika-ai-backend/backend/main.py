"""
backend/main.py

Project Agency (Tekika AI) - FastAPI エントリポイント。
LLM_PROVIDER 設定（.env）に応じて、Ollama / OpenAI / Anthropic Claude / Google Gemini を
切り替え可能なマルチプロバイダ構成。ローカルツール（Git操作・ファイル検索・画像生成・
プラグイン自己アップデート）は全プロバイダ共通で利用できる。
"""

from __future__ import annotations

import json
import logging
import time  # 応答処理時間の計測用
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.base_client import LLMConnectionError, LLMProviderError, LLMResponseError
from backend.agent.factory import LLMFactory
from backend.agent.memory import MemoryStore
from backend.agent.orchestrator import AgentOrchestrator
from backend.config import AgentMode, Settings, get_settings
from backend.tools.file_system_tool import (
    FileSystemTool,
    FileSystemToolError,
    PathSecurityError,
)
from backend.tools.git_tool import GitToolError, LocalGitTool
from backend.tools.image_gen_tool import ImageGenerationError, LocalImageGenerator
from backend.tools.plugin_loader import PluginError, PluginLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tekika_ai.main")

settings: Settings = get_settings()

# ---------------------------------------------------------------------------
# アプリケーション状態（グローバルシングルトン群）
# ---------------------------------------------------------------------------
memory_store: Optional[MemoryStore] = None
llm_clients: Dict[str, Any] = {}
orchestrator: Optional[AgentOrchestrator] = None
git_tool: Optional[LocalGitTool] = None
image_generator: Optional[LocalImageGenerator] = None
plugin_loader: Optional[PluginLoader] = None
file_system_tool: Optional[FileSystemTool] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """アプリケーション起動時・終了時のリソース初期化/解放処理。"""
    global memory_store, llm_clients, orchestrator, git_tool, image_generator, plugin_loader, file_system_tool

    logger.info("Project Agency (Tekika AI) バックエンドを起動しています...")

    memory_store = MemoryStore(
        db_path=settings.SQLITE_DB_PATH,
        chroma_persist_dir=settings.CHROMA_PERSIST_DIR,
        export_dir=settings.EXPORT_DIR,
    )

    # 設定済みの全LLMプロバイダ（Ollama/OpenAI/Claude/Gemini）を初期化する。
    # APIキー未設定のプロバイダは自動的にスキップされる（Ollamaは鍵不要のため通常は常に含まれる）。
    llm_factory = LLMFactory(settings)
    llm_clients = llm_factory.create_available_clients()

    if not llm_clients:
        logger.error(
            "利用可能なLLMプロバイダが1つもありません。.env の LLM_PROVIDER / "
            "各種APIキー設定を確認してください。"
        )

    git_tool = LocalGitTool(
        default_author_name=settings.GIT_DEFAULT_AUTHOR_NAME,
        default_author_email=settings.GIT_DEFAULT_AUTHOR_EMAIL,
    )
    image_generator = LocalImageGenerator(
        webui_base_url=settings.SD_WEBUI_BASE_URL,
        output_dir=settings.IMAGE_OUTPUT_DIR,
        default_width=settings.IMAGE_DEFAULT_WIDTH,
        default_height=settings.IMAGE_DEFAULT_HEIGHT,
        default_steps=settings.IMAGE_DEFAULT_STEPS,
        timeout=settings.SD_WEBUI_TIMEOUT,
    )
    plugin_loader = PluginLoader(plugin_dir=settings.PLUGIN_DIR)
    file_system_tool = FileSystemTool()

    orchestrator = AgentOrchestrator(
        settings=settings,
        clients=llm_clients,
        memory=memory_store,
        default_provider=settings.LLM_PROVIDER,
    )

    # ローカルツールをオーケストレータに登録
    orchestrator.register_tool(git_tool.get_repo_status, "ローカルGitリポジトリのステータスを取得する。")
    orchestrator.register_tool(git_tool.read_file, "ローカルGitリポジトリ内のファイルを読み込む。")
    orchestrator.register_tool(git_tool.write_file, "ローカルGitリポジトリ内のファイルへ書き込む。")
    orchestrator.register_tool(git_tool.commit_and_branch, "ブランチを切り替え、変更をコミットする。")
    orchestrator.register_tool(git_tool.get_log, "ローカルGitリポジトリのコミットログを取得する。")

    orchestrator.register_tool(
        file_system_tool.search_files,
        "指定フォルダ配下からキーワードや拡張子に一致するファイルを再帰的に検索する。"
        "ユーザーが「〇〇のファイルを探して」のように指示した場合に使用する。",
    )
    orchestrator.register_tool(
        file_system_tool.list_directory,
        "指定フォルダ直下のファイル・フォルダ一覧（サイズ・更新日時付き）を取得する。",
    )
    orchestrator.register_tool(
        file_system_tool.open_in_explorer,
        "指定したファイルまたはフォルダをOS標準のエクスプローラー（Windows: explorer.exe, "
        "macOS: Finder, Linux: xdg-open）で開く。"
        "ユーザーが「エクスプローラーで開いて」のように指示した場合に使用する。",
    )

    # 既存プラグインをロードし、公開関数をツールとして登録
    for loaded in plugin_loader.load_all_plugins():
        for tool_name in loaded.exported_tools:
            func = getattr(loaded.module, tool_name, None)
            if callable(func):
                orchestrator.register_tool(func)

    for provider_name, client in llm_clients.items():
        if await client.health_check():
            logger.info(
                "プロバイダ '%s' への接続に成功しました（既定モデル: %s）",
                provider_name,
                client.default_model,
            )
        else:
            logger.warning(
                "プロバイダ '%s' への接続確認に失敗しました。APIキーやネットワーク設定、"
                "（Ollamaの場合は 'ollama serve' の起動状況）を確認してください。",
                provider_name,
            )

    yield

    logger.info("Project Agency (Tekika AI) バックエンドを終了しています...")
    for client in llm_clients.values():
        await client.aclose()
    if memory_store:
        memory_store.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# リクエスト/レスポンス スキーマ
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="ユーザーからのメッセージ本文")
    session_id: Optional[str] = Field(default=None, description="会話セッションID")
    mode: Optional[AgentMode] = Field(default=None, description="QUALITY または SPEED")
    provider: Optional[str] = Field(
        default=None,
        description="使用するLLMプロバイダ ('ollama'/'openai'/'claude'/'gemini')。省略時は既定プロバイダ",
    )
    stream: bool = Field(default=False, description="Server-Sent Eventsでストリーミング応答するか")
    regenerate: bool = Field(
        default=False,
        description="Trueの場合、messageを新規のユーザー発言として保存せず、"
        "既存の会話履歴のみを使って直前の回答を再生成する（「再試行」機能用）。",
    )


class ChatResponsePayload(BaseModel):
    session_id: str
    response: str
    mode: str
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time: Optional[float] = Field(default=None, description="応答処理時間(秒)")
    provider: Optional[str] = Field(default=None, description="実際に応答を生成したLLMプロバイダ")
    model: Optional[str] = Field(default=None, description="実際に応答を生成したモデル名")


class GitRepoRequest(BaseModel):
    repo_path: str


class GitReadFileRequest(BaseModel):
    repo_path: str
    file_path: str


class GitWriteFileRequest(BaseModel):
    repo_path: str
    file_path: str
    content: str


class GitCommitRequest(BaseModel):
    repo_path: str
    branch_name: Optional[str] = None
    commit_message: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    add_all: bool = True


class ImageGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    seed: int = -1


class PluginRegisterRequest(BaseModel):
    plugin_name: str
    python_code: str


class FileSearchRequest(BaseModel):
    base_path: str
    keyword: str = ""
    extension: Optional[str] = None


class DirectoryListRequest(BaseModel):
    dir_path: str


class FileSystemOpenRequest(BaseModel):
    target_path: str = Field(..., description="開きたいファイルまたはフォルダの絶対パス")


# ---------------------------------------------------------------------------
# ヘルスチェック / プロバイダ一覧
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """アプリケーション全体、および各LLMプロバイダの接続状況を確認する。"""
    provider_status: Dict[str, bool] = {}
    for name, client in llm_clients.items():
        provider_status[name] = await client.health_check()

    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "agent_mode": settings.AGENT_MODE.value,
        "default_provider": settings.LLM_PROVIDER,
        "providers": provider_status,
    }


@app.get("/api/providers")
async def list_providers() -> List[Dict[str, Any]]:
    """現在利用可能な全LLMプロバイダ（APIキー設定済みのもの）とその既定モデルを一覧する。"""
    assert orchestrator is not None
    return orchestrator.list_available_providers()


# ---------------------------------------------------------------------------
# チャット
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """ローカルエージェントとチャットする。stream=Trueの場合はSSEでストリーミング応答する。"""
    assert orchestrator is not None

    start_time = time.perf_counter()

    if request.stream:

        async def event_generator() -> AsyncIterator[str]:
            try:
                async for chunk in orchestrator.stream_user_message(
                    user_input=request.message,
                    session_id=request.session_id,
                    mode=request.mode,
                    provider=request.provider,
                    regenerate=request.regenerate,
                ):
                    if chunk.get("type") == "tool_result":
                        # list_directory等のツール実行結果を構造化イベントとして送出する。
                        # 既存の "delta"/"done"/"error" フレームの形式・意味は変更しない。
                        payload = json.dumps(
                            {
                                "tool_event": True,
                                "tool_name": chunk.get("name"),
                                "status": chunk.get("status", "done"),
                                "arguments": chunk.get("arguments"),
                                "result": chunk.get("result"),
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                    else:
                        payload = json.dumps({"delta": chunk.get("text", "")}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            except (LLMConnectionError, LLMProviderError, LLMResponseError) as exc:
                error_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
                yield f"data: {error_payload}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    try:
        result = await orchestrator.handle_user_message(
            user_input=request.message,
            session_id=request.session_id,
            mode=request.mode,
            provider=request.provider,
            regenerate=request.regenerate,
        )
        result["execution_time"] = round(time.perf_counter() - start_time, 1)
    except LLMProviderError as exc:
        # APIキー未設定・未対応プロバイダ指定など、利用者側の設定不備
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponsePayload(**result)


# ---------------------------------------------------------------------------
# セッション管理
# ---------------------------------------------------------------------------
@app.get("/api/sessions")
async def list_sessions() -> List[Dict[str, Any]]:
    assert memory_store is not None
    return memory_store.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    assert memory_store is not None
    return memory_store.get_history(session_id)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    assert memory_store is not None
    memory_store.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ---------------------------------------------------------------------------
# エクスポート / インポート
# ---------------------------------------------------------------------------
@app.get("/api/export")
async def export_data():
    """全ローカルデータ（会話履歴・長期記憶）を単一ZIPでダウンロードする。"""
    assert memory_store is not None
    export_path = memory_store.export_data()
    return FileResponse(
        path=str(export_path),
        filename=export_path.name,
        media_type="application/zip",
    )


@app.post("/api/import")
async def import_data(file: UploadFile = File(...)) -> Dict[str, str]:
    """アップロードされたZIPファイルからローカルデータを復元する。"""
    assert memory_store is not None

    temp_path = settings.EXPORT_DIR / f"_upload_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        memory_store.import_data(temp_path, overwrite=True)
    except (FileNotFoundError, ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return {"status": "imported", "source_file": file.filename or "unknown"}


# ---------------------------------------------------------------------------
# ローカルGit操作
# ---------------------------------------------------------------------------
@app.post("/api/git/status")
async def git_status(request: GitRepoRequest) -> Dict[str, Any]:
    assert git_tool is not None
    try:
        return git_tool.get_repo_status(request.repo_path)
    except GitToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/git/read")
async def git_read_file(request: GitReadFileRequest) -> Dict[str, str]:
    assert git_tool is not None
    try:
        content = git_tool.read_file(request.repo_path, request.file_path)
        return {"file_path": request.file_path, "content": content}
    except GitToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/git/write")
async def git_write_file(request: GitWriteFileRequest) -> Dict[str, Any]:
    assert git_tool is not None
    try:
        return git_tool.write_file(request.repo_path, request.file_path, request.content)
    except GitToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/git/commit")
async def git_commit(request: GitCommitRequest) -> Dict[str, Any]:
    assert git_tool is not None
    try:
        return git_tool.commit_and_branch(
            repo_path=request.repo_path,
            branch_name=request.branch_name,
            commit_message=request.commit_message,
            author_name=request.author_name,
            author_email=request.author_email,
            add_all=request.add_all,
        )
    except GitToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# ローカル画像生成
# ---------------------------------------------------------------------------
@app.post("/api/image/generate")
async def generate_image(request: ImageGenerateRequest) -> Dict[str, Any]:
    assert image_generator is not None
    try:
        return await image_generator.generate_image(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            steps=request.steps,
            seed=request.seed,
        )
    except ImageGenerationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# ローカルファイルシステム閲覧・検索・エクスプローラー連携
# ---------------------------------------------------------------------------
@app.post("/api/file-system/search")
async def file_system_search(request: FileSearchRequest) -> List[Dict[str, Any]]:
    assert file_system_tool is not None
    try:
        return file_system_tool.search_files(
            base_path=request.base_path,
            keyword=request.keyword,
            extension=request.extension,
        )
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileSystemToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/file-system/list")
async def file_system_list(request: DirectoryListRequest) -> List[Dict[str, Any]]:
    assert file_system_tool is not None
    try:
        return file_system_tool.list_directory(request.dir_path)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileSystemToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/file-system/open")
async def file_system_open(request: FileSystemOpenRequest) -> Dict[str, Any]:
    """指定されたファイル/フォルダをOS標準のエクスプローラー（ファイルマネージャー）で開く。"""
    assert file_system_tool is not None
    try:
        return file_system_tool.open_in_explorer(request.target_path)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileSystemToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# プラグイン管理（自己アップデート基盤）
# ---------------------------------------------------------------------------
@app.get("/api/plugins")
async def list_plugins() -> Dict[str, Any]:
    assert plugin_loader is not None
    return {
        "loaded": plugin_loader.list_loaded_plugins(),
        "available_files": plugin_loader.list_available_plugin_files(),
    }


@app.post("/api/plugins")
async def register_plugin(request: PluginRegisterRequest) -> Dict[str, Any]:
    """AI自身が生成した新規プラグインコードを保存し、即座にホットロードする。"""
    assert plugin_loader is not None
    assert orchestrator is not None
    try:
        loaded = plugin_loader.register_new_plugin(request.plugin_name, request.python_code)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for tool_name in loaded.exported_tools:
        func = getattr(loaded.module, tool_name, None)
        if callable(func):
            orchestrator.register_tool(func)

    return {
        "name": loaded.name,
        "file_path": str(loaded.file_path),
        "exported_tools": loaded.exported_tools,
    }


@app.post("/api/plugins/{plugin_name}/reload")
async def reload_plugin(plugin_name: str) -> Dict[str, Any]:
    assert plugin_loader is not None
    assert orchestrator is not None
    try:
        loaded = plugin_loader.reload_plugin(plugin_name)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for tool_name in loaded.exported_tools:
        func = getattr(loaded.module, tool_name, None)
        if callable(func):
            orchestrator.register_tool(func)

    return {
        "name": loaded.name,
        "file_path": str(loaded.file_path),
        "exported_tools": loaded.exported_tools,
    }


@app.delete("/api/plugins/{plugin_name}")
async def delete_plugin(plugin_name: str) -> Dict[str, str]:
    assert plugin_loader is not None
    assert orchestrator is not None

    for tool_name in list(orchestrator.tool_registry.keys()):
        if tool_name in plugin_loader.get_all_tool_functions():
            pass

    loaded = plugin_loader._loaded.get(plugin_name)
    if loaded:
        for tool_name in loaded.exported_tools:
            orchestrator.unregister_tool(tool_name)

    plugin_loader.delete_plugin(plugin_name)
    return {"status": "deleted", "plugin_name": plugin_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )