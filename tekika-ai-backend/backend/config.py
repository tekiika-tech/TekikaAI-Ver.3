"""
backend/config.py

Project Agency (Tekika AI) - 動作設定モジュール
ローカルOllamaに加え、OpenAI / Anthropic Claude / Google Gemini など複数のLLMプロバイダを
`.env` の設定で切り替え可能なマルチプロバイダ構成。APIキー等の秘密情報は必ず `.env`
（バージョン管理対象外）で管理し、本ファイルにハードコードしない。
Pydantic Settings (pydantic-settings) を利用。
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env をロード（存在しない場合は無視される）
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)


class AgentMode(str, Enum):
    """エージェントの動作モード"""

    QUALITY = "QUALITY"  # 思考→ツール実行→結果統合のループを行う高精度モード
    SPEED = "SPEED"      # 単一ステップで即座に回答を生成する高速モード


class Settings(BaseSettings):
    """
    アプリケーション全体の設定値。
    すべての値は環境変数（.env含む）で上書き可能。
    外部クラウドAPIのキー等は一切保持しない。
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- アプリケーション基本情報 ----
    APP_NAME: str = Field(default="Project Agency (Tekika AI)")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)

    # ---- LLMプロバイダ共通設定 ----
    # "ollama" / "openai" / "claude" / "gemini" のいずれか。
    # 未設定・未対応値の場合はollama（ローカル）にフォールバックする。
    LLM_PROVIDER: str = Field(default="ollama")
    # OpenAI / Claude / Gemini など、クラウドプロバイダ共通の既定サンプリング温度
    # （Ollama専用の温度は下記 OLLAMA_TEMPERATURE を使用する）
    LLM_TEMPERATURE: float = Field(default=0.7)

    # ---- Ollama (ローカルLLM) 設定 ----
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_DEFAULT_MODEL: str = Field(default="qwen2.5:latest")
    OLLAMA_FALLBACK_MODEL: str = Field(default="llama3.3:latest")
    # None（既定）の場合、ローカルの重いモデルでも読み込みタイムアウトで
    # 応答が打ち切られないよう無制限として扱う。数値を指定すると秒単位で上限を設ける。
    OLLAMA_REQUEST_TIMEOUT: Optional[float] = Field(default=None)
    OLLAMA_TEMPERATURE: float = Field(default=0.7)
    OLLAMA_MAX_TOOL_ITERATIONS: int = Field(default=8)

    # ---- OpenAI 設定 ----
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_BASE_URL: Optional[str] = Field(default=None)  # Azure互換プロキシ等を使う場合に指定
    OPENAI_DEFAULT_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_REQUEST_TIMEOUT: Optional[float] = Field(default=None)

    # ---- Anthropic Claude 設定 ----
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    CLAUDE_DEFAULT_MODEL: str = Field(default="claude-sonnet-4-5")
    ANTHROPIC_REQUEST_TIMEOUT: Optional[float] = Field(default=None)

    # ---- Google Gemini 設定 ----
    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    GEMINI_DEFAULT_MODEL: str = Field(default="gemini-2.0-flash")
    GEMINI_REQUEST_TIMEOUT: Optional[float] = Field(default=None)

    # ---- エージェント動作モード ----
    AGENT_MODE: AgentMode = Field(default=AgentMode.QUALITY)

    # ---- ローカルデータ保存先 ----
    BASE_DIR: Path = Field(default=Path(__file__).resolve().parent.parent)
    DATA_DIR: Path = Field(default=Path(__file__).resolve().parent.parent / "data")
    SQLITE_DB_PATH: Path = Field(
        default=Path(__file__).resolve().parent.parent / "data" / "agency.db"
    )
    CHROMA_PERSIST_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "data" / "chroma"
    )
    EXPORT_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "data" / "exports"
    )
    PLUGIN_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "plugins"
    )

    # ---- ローカル画像生成 (Stable Diffusion WebUI) ----
    SD_WEBUI_BASE_URL: str = Field(default="http://localhost:7860")
    SD_WEBUI_TIMEOUT: float = Field(default=120.0)
    IMAGE_OUTPUT_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "data" / "images"
    )
    IMAGE_DEFAULT_WIDTH: int = Field(default=512)
    IMAGE_DEFAULT_HEIGHT: int = Field(default=512)
    IMAGE_DEFAULT_STEPS: int = Field(default=20)

    # ---- Git ツール ----
    GIT_DEFAULT_AUTHOR_NAME: str = Field(default="Tekika Agent")
    GIT_DEFAULT_AUTHOR_EMAIL: str = Field(default="tekika-agent@local")

    # ---- FastAPI / CORS ----
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    CORS_ALLOW_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator(
        "DATA_DIR",
        "SQLITE_DB_PATH",
        "CHROMA_PERSIST_DIR",
        "EXPORT_DIR",
        "PLUGIN_DIR",
        "IMAGE_OUTPUT_DIR",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value):
        if value is None:
            return value
        return Path(value)

    def ensure_directories(self) -> None:
        """必要なローカルディレクトリをすべて作成する（存在すれば何もしない）。"""
        for directory in (
            self.DATA_DIR,
            self.CHROMA_PERSIST_DIR,
            self.EXPORT_DIR,
            self.PLUGIN_DIR,
            self.IMAGE_OUTPUT_DIR,
            self.SQLITE_DB_PATH.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def active_model(self) -> str:
        """
        現在の動作モードに応じてOllama用の既定モデル名を返す（Ollama専用のレガシーヘルパー）。
        マルチプロバイダ構成では、各プロバイダは自身の `default_model` を使用するため、
        本メソッドは主にOllama単体運用時の後方互換用として残している。
        """
        if self.AGENT_MODE == AgentMode.SPEED:
            return self.OLLAMA_FALLBACK_MODEL
        return self.OLLAMA_DEFAULT_MODEL


# シングルトンとして設定インスタンスを生成
settings = Settings()
settings.ensure_directories()


def get_settings() -> Settings:
    """FastAPI の Depends() などから利用するための取得関数。"""
    return settings
