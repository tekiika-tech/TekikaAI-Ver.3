"""
backend/agent/memory.py

完全ローカルの記憶管理モジュール。
- sqlite3: 会話履歴・ユーザープロファイル・設定データの永続化。
- ChromaDB (PersistentClient): 長期記憶のベクトル検索。
- export_data() / import_data(): 全データを単一ZIPにパッケージ化・復元。
外部クラウドサービスへの通信は一切行わない。
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger("tekika_ai.memory")


# ---------------------------------------------------------------------------
# SQLite スキーマ定義
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    tool_name TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_session
    ON conversations (session_id, created_at);

CREATE TABLE IF NOT EXISTS user_profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """
    会話履歴・ユーザープロファイル・長期記憶（ベクトル検索）を統括するクラス。

    Attributes:
        db_path: SQLiteデータベースファイルのパス。
        chroma_persist_dir: ChromaDBの永続化ディレクトリ。
        export_dir: エクスポートZIPの出力先ディレクトリ。
    """

    def __init__(
        self,
        db_path: Path,
        chroma_persist_dir: Path,
        export_dir: Path,
        chroma_collection_name: str = "tekika_long_term_memory",
    ) -> None:
        self.db_path = Path(db_path)
        self.chroma_persist_dir = Path(chroma_persist_dir)
        self.export_dir = Path(export_dir)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self._init_sqlite()

        # ChromaDB をローカル永続化モードで初期化（外部通信なし）
        self._chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name=chroma_collection_name,
            metadata={"description": "Tekika AI 長期記憶ベクトルストア"},
        )

    # ------------------------------------------------------------------
    # SQLite 基盤
    # ------------------------------------------------------------------
    def _init_sqlite(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # セッション・会話履歴
    # ------------------------------------------------------------------
    def ensure_session(self, session_id: str, title: Optional[str] = None) -> None:
        """セッションが存在しなければ新規作成する。"""
        now = _now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO sessions (session_id, title, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, title or session_id, now, now),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
            conn.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
    ) -> int:
        """会話メッセージを1件保存し、挿入されたレコードIDを返す。"""
        self.ensure_session(session_id)
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (session_id, role, content, tool_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, tool_name, _now_iso()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_history(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """指定セッションの会話履歴を時系列で取得する。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, tool_name, created_at FROM conversations "
                "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sessions(self) -> List[Dict[str, Any]]:
        """保存済みの全セッション一覧を取得する。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, title, created_at, updated_at FROM sessions "
                "ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_session(self, session_id: str) -> None:
        """指定セッションと関連する会話履歴をすべて削除する。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    # ------------------------------------------------------------------
    # ユーザープロファイル / アプリ設定
    # ------------------------------------------------------------------
    def set_profile_value(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_profile (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, serialized, _now_iso()),
            )
            conn.commit()

    def get_profile_value(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM user_profile WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def get_full_profile(self) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
        result: Dict[str, Any] = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                result[row["key"]] = row["value"]
        return result

    def set_app_setting(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, serialized, _now_iso()),
            )
            conn.commit()

    def get_app_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    # ------------------------------------------------------------------
    # 長期記憶（ChromaDB ベクトル検索）
    # ------------------------------------------------------------------
    def add_long_term_memory(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> str:
        """長期記憶にテキストを1件追加する（埋め込みはChromaDBの既定関数で自動生成）。"""
        doc_id = memory_id or f"mem_{datetime.now(timezone.utc).timestamp()}"
        meta = dict(metadata or {})
        meta.setdefault("created_at", _now_iso())
        self._collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
        )
        return doc_id

    def search_long_term_memory(
        self, query: str, top_k: int = 5, where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """クエリに関連する長期記憶を類似度検索で取得する。"""
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        output: List[Dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]
        for doc, meta, dist, doc_id in zip(documents, metadatas, distances, ids):
            output.append(
                {"id": doc_id, "text": doc, "metadata": meta, "distance": dist}
            )
        return output

    def delete_long_term_memory(self, memory_id: str) -> None:
        self._collection.delete(ids=[memory_id])

    # ------------------------------------------------------------------
    # エクスポート / インポート（単一ZIPパッケージ）
    # ------------------------------------------------------------------
    def export_data(self, export_name: Optional[str] = None) -> Path:
        """
        SQLiteデータベース全体とChromaDB永続化ディレクトリを
        単一のZIPファイルにパッケージ化する。

        Returns:
            Path: 生成されたZIPファイルの絶対パス。
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = export_name or f"tekika_export_{timestamp}"
        if not name.endswith(".zip"):
            name = f"{name}.zip"
        export_path = self.export_dir / name

        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # SQLite DB
            if self.db_path.exists():
                zf.write(self.db_path, arcname=f"sqlite/{self.db_path.name}")

            # ChromaDB 永続化ディレクトリを丸ごと格納
            for file_path in self.chroma_persist_dir.rglob("*"):
                if file_path.is_file():
                    relative = file_path.relative_to(self.chroma_persist_dir)
                    zf.write(file_path, arcname=f"chroma/{relative}")

            # メタ情報
            manifest = {
                "exported_at": _now_iso(),
                "app": "Project Agency (Tekika AI)",
                "sqlite_file": self.db_path.name,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        logger.info("データをエクスポートしました: %s", export_path)
        return export_path

    def import_data(self, zip_path: Path, overwrite: bool = True) -> None:
        """
        export_data() で生成されたZIPファイルからデータを復元する。

        Args:
            zip_path: インポート対象のZIPファイルパス。
            overwrite: 既存データを上書きするかどうか。
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"インポート対象のファイルが見つかりません: {zip_path}")

        extract_tmp = self.export_dir / f"_import_tmp_{datetime.now(timezone.utc).timestamp()}"
        extract_tmp.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_tmp)

            manifest_path = extract_tmp / "manifest.json"
            if not manifest_path.exists():
                raise ValueError("不正なエクスポートファイルです（manifest.jsonが見つかりません）。")

            # SQLite DB の復元
            sqlite_dir = extract_tmp / "sqlite"
            if sqlite_dir.exists():
                for db_file in sqlite_dir.glob("*.db"):
                    target = self.db_path
                    if target.exists() and not overwrite:
                        raise FileExistsError(f"既存のDBファイルが存在します: {target}")
                    shutil.copy2(db_file, target)

            # ChromaDB 永続化データの復元
            chroma_dir = extract_tmp / "chroma"
            if chroma_dir.exists():
                if self.chroma_persist_dir.exists() and overwrite:
                    shutil.rmtree(self.chroma_persist_dir)
                shutil.copytree(chroma_dir, self.chroma_persist_dir, dirs_exist_ok=True)

            logger.info("データをインポートしました: %s", zip_path)
        finally:
            shutil.rmtree(extract_tmp, ignore_errors=True)

    def close(self) -> None:
        """明示的なクローズ処理（ChromaDBのPersistentClientはコネクション管理不要だが将来拡張用）。"""
        logger.info("MemoryStore をクローズしました。")
