"""
backend/tools/git_tool.py

ローカルPC上のGitリポジトリを直接操作するツール。
GitHub等のクラウドAPIは一切使用せず、GitPython (subprocess経由でローカルgitバイナリを呼び出す)
のみでリポジトリの状態取得・ファイル読み書き・コミット・ブランチ作成を行う。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
from git import GitCommandError, InvalidGitRepositoryError, Repo

logger = logging.getLogger("tekika_ai.git_tool")


class GitToolError(Exception):
    """Gitツール操作全般のエラー。"""


class LocalGitTool:
    """
    ローカルGitリポジトリ操作を提供するクラス。

    Attributes:
        default_author_name: コミット時のデフォルト著者名。
        default_author_email: コミット時のデフォルト著者メールアドレス。
    """

    def __init__(
        self,
        default_author_name: str = "Tekika Agent",
        default_author_email: str = "tekika-agent@local",
    ) -> None:
        self.default_author_name = default_author_name
        self.default_author_email = default_author_email

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------
    def _open_repo(self, repo_path: str) -> Repo:
        path = Path(repo_path).expanduser().resolve()
        if not path.exists():
            raise GitToolError(f"指定されたパスが存在しません: {path}")
        try:
            return Repo(str(path))
        except InvalidGitRepositoryError as exc:
            raise GitToolError(f"有効なGitリポジトリではありません: {path}") from exc

    def _resolve_file_path(self, repo_path: str, file_path: str) -> Path:
        repo_root = Path(repo_path).expanduser().resolve()
        target = (repo_root / file_path).resolve()
        # リポジトリ外へのパストラバーサルを防止
        if repo_root not in target.parents and target != repo_root:
            raise GitToolError(
                f"リポジトリ外のパスへのアクセスは許可されていません: {file_path}"
            )
        return target

    # ------------------------------------------------------------------
    # リポジトリ初期化・クローン
    # ------------------------------------------------------------------
    def init_repo(self, repo_path: str) -> Dict[str, Any]:
        """指定パスに新しいローカルGitリポジトリを初期化する。既に存在すればそれを開く。"""
        path = Path(repo_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        try:
            repo = Repo(str(path))
            created = False
        except InvalidGitRepositoryError:
            repo = Repo.init(str(path))
            created = True
        return {
            "repo_path": str(path),
            "created": created,
            "current_branch": self._safe_active_branch(repo),
        }

    def clone_repo(self, source_path_or_url: str, destination_path: str) -> Dict[str, Any]:
        """ローカルまたはファイルシステム上のリポジトリを別のローカルパスへクローンする。"""
        dest = Path(destination_path).expanduser().resolve()
        try:
            Repo.clone_from(source_path_or_url, str(dest))
        except GitCommandError as exc:
            raise GitToolError(f"クローンに失敗しました: {exc}") from exc
        return {"cloned_to": str(dest)}

    def _safe_active_branch(self, repo: Repo) -> Optional[str]:
        try:
            return repo.active_branch.name
        except TypeError:
            return None

    # ------------------------------------------------------------------
    # 状態取得
    # ------------------------------------------------------------------
    def get_repo_status(self, repo_path: str) -> Dict[str, Any]:
        """
        指定リポジトリの `git status` 相当の情報を取得する。

        Returns:
            現在のブランチ、未追跡ファイル、変更済みファイル、ステージ済みファイルの一覧。
        """
        repo = self._open_repo(repo_path)

        untracked = repo.untracked_files
        changed = [item.a_path for item in repo.index.diff(None)]
        staged = [item.a_path for item in repo.index.diff("HEAD")] if repo.head.is_valid() else []

        return {
            "repo_path": str(Path(repo_path).expanduser().resolve()),
            "current_branch": self._safe_active_branch(repo),
            "is_dirty": repo.is_dirty(untracked_files=True),
            "untracked_files": list(untracked),
            "changed_files": changed,
            "staged_files": staged,
            "last_commit": self._describe_last_commit(repo),
        }

    def _describe_last_commit(self, repo: Repo) -> Optional[Dict[str, Any]]:
        if not repo.head.is_valid():
            return None
        commit = repo.head.commit
        return {
            "hexsha": commit.hexsha,
            "author": str(commit.author),
            "message": commit.message.strip(),
            "committed_datetime": commit.committed_datetime.isoformat(),
        }

    def list_branches(self, repo_path: str) -> List[str]:
        """リポジトリ内の全ローカルブランチ名を取得する。"""
        repo = self._open_repo(repo_path)
        return [head.name for head in repo.heads]

    def get_diff(self, repo_path: str, file_path: Optional[str] = None) -> str:
        """作業ツリーの差分（未コミット分）を文字列で取得する。"""
        repo = self._open_repo(repo_path)
        if file_path:
            return repo.git.diff(file_path)
        return repo.git.diff()

    # ------------------------------------------------------------------
    # ファイル読み書き
    # ------------------------------------------------------------------
    def read_file(self, repo_path: str, file_path: str) -> str:
        """リポジトリ内の指定ファイルをUTF-8テキストとして読み込む。"""
        target = self._resolve_file_path(repo_path, file_path)
        if not target.exists():
            raise GitToolError(f"ファイルが見つかりません: {target}")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise GitToolError(f"テキストとして読み込めないファイルです: {target}") from exc

    def write_file(self, repo_path: str, file_path: str, content: str) -> Dict[str, Any]:
        """リポジトリ内の指定ファイルにUTF-8テキストを書き込む（新規作成・上書き両対応）。"""
        target = self._resolve_file_path(repo_path, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "file_path": str(target),
            "bytes_written": len(content.encode("utf-8")),
        }

    def delete_file(self, repo_path: str, file_path: str) -> Dict[str, Any]:
        """リポジトリ内の指定ファイルを削除する。"""
        target = self._resolve_file_path(repo_path, file_path)
        if not target.exists():
            raise GitToolError(f"削除対象のファイルが見つかりません: {target}")
        target.unlink()
        return {"deleted": str(target)}

    # ------------------------------------------------------------------
    # ブランチ・コミット操作
    # ------------------------------------------------------------------
    def commit_and_branch(
        self,
        repo_path: str,
        branch_name: Optional[str],
        commit_message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        add_all: bool = True,
    ) -> Dict[str, Any]:
        """
        指定ブランチへ切り替え（存在しなければ作成）、変更をステージし、コミットを実行する。

        Args:
            repo_path: 対象リポジトリのパス。
            branch_name: 切り替え先/作成するブランチ名。Noneの場合は現在のブランチのまま。
            commit_message: コミットメッセージ。
            author_name: コミット著者名。省略時はデフォルト値を使用。
            author_email: コミット著者メール。省略時はデフォルト値を使用。
            add_all: True の場合、全ての変更（新規・変更・削除）をステージする。

        Returns:
            実行結果（ブランチ名、コミットハッシュ、コミットメッセージ）。
        """
        repo = self._open_repo(repo_path)

        if branch_name:
            existing_branch_names = [h.name for h in repo.heads]
            if branch_name in existing_branch_names:
                repo.git.checkout(branch_name)
            else:
                repo.git.checkout("-b", branch_name)

        if add_all:
            repo.git.add(A=True)
        else:
            repo.git.add(u=True)

        if not repo.is_dirty(index=True, working_tree=False) and not repo.untracked_files:
            return {
                "committed": False,
                "reason": "コミットする変更がありません。",
                "current_branch": self._safe_active_branch(repo),
            }

        actor = git.Actor(
            author_name or self.default_author_name,
            author_email or self.default_author_email,
        )

        try:
            commit = repo.index.commit(commit_message, author=actor, committer=actor)
        except GitCommandError as exc:
            raise GitToolError(f"コミットに失敗しました: {exc}") from exc

        return {
            "committed": True,
            "current_branch": self._safe_active_branch(repo),
            "commit_hexsha": commit.hexsha,
            "commit_message": commit_message,
        }

    def checkout_branch(self, repo_path: str, branch_name: str, create: bool = False) -> Dict[str, Any]:
        """指定ブランチへチェックアウトする。create=Trueの場合は新規作成も行う。"""
        repo = self._open_repo(repo_path)
        try:
            if create:
                repo.git.checkout("-b", branch_name)
            else:
                repo.git.checkout(branch_name)
        except GitCommandError as exc:
            raise GitToolError(f"チェックアウトに失敗しました: {exc}") from exc
        return {"current_branch": self._safe_active_branch(repo)}

    def get_log(self, repo_path: str, max_count: int = 20) -> List[Dict[str, Any]]:
        """コミットログを新しい順に取得する。"""
        repo = self._open_repo(repo_path)
        if not repo.head.is_valid():
            return []
        commits = list(repo.iter_commits(max_count=max_count))
        return [
            {
                "hexsha": c.hexsha,
                "author": str(c.author),
                "message": c.message.strip(),
                "committed_datetime": c.committed_datetime.isoformat(),
            }
            for c in commits
        ]
