"""
backend/tools/file_system_tool.py

ローカルファイルシステムの閲覧・検索、およびOS標準エクスプローラー連携ツール。
外部通信は一切行わず、ローカルPC上のファイルシステム操作のみで完結する。

セキュリティ方針:
- 全てのパスは `Path.resolve()` で正規化してから使用し、NULLバイトや
  制御文字を含む不正な入力を拒否する。
- OSコマンド実行は `subprocess.run` に引数リストを渡す形のみで行い、
  `shell=True` は一切使用しない（OSコマンドインジェクション対策）。
- `search_files` / `list_directory` は、実在し、かつ実際にディレクトリで
  あることを検証したうえでのみ走査する（存在しないパスやファイルパスを
  ディレクトリとして扱おうとする誤用を防止する）。
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tekika_ai.file_system_tool")


class FileSystemToolError(Exception):
    """ファイルシステムツール操作全般のエラー。"""


class PathSecurityError(FileSystemToolError):
    """パス検証（トラバーサル・不正文字など）に失敗した場合のエラー。"""


def _has_control_characters(raw_path: str) -> bool:
    """NULLバイトや制御文字が含まれていないかを確認する。"""
    return any(ord(ch) < 0x20 for ch in raw_path if ch not in ("\t",))


class FileSystemTool:
    """
    ローカルファイルシステムの閲覧・検索・OSエクスプローラー連携を提供するクラス。

    Attributes:
        max_search_results: `search_files` が返す最大件数（暴走防止）。
        max_list_entries: `list_directory` が返す最大件数（暴走防止）。
    """

    def __init__(
        self,
        max_search_results: int = 500,
        max_list_entries: int = 2000,
    ) -> None:
        self.max_search_results = max_search_results
        self.max_list_entries = max_list_entries
        self._os_name = platform.system()  # 'Windows' / 'Linux' / 'Darwin'

    # ------------------------------------------------------------------
    # パス検証
    # ------------------------------------------------------------------
    def _resolve_and_validate(self, raw_path: str, must_exist: bool = True) -> Path:
        """
        入力パス文字列を正規化・検証し、安全な `Path` オブジェクトを返す。

        Args:
            raw_path: ユーザー/AIから渡された生のパス文字列。
            must_exist: True の場合、実際にファイルシステム上に存在することを要求する。

        Raises:
            PathSecurityError: NULLバイト・制御文字を含む、または検証に失敗した場合。
            FileSystemToolError: must_exist=True で対象が存在しない場合。
        """
        if not raw_path or not isinstance(raw_path, str):
            raise PathSecurityError("パスが指定されていません。")

        if _has_control_characters(raw_path):
            raise PathSecurityError("パスに不正な制御文字が含まれています。")

        try:
            resolved = Path(raw_path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise PathSecurityError(f"パスの解決に失敗しました: {raw_path}") from exc

        if must_exist and not resolved.exists():
            raise FileSystemToolError(f"指定されたパスが存在しません: {resolved}")

        return resolved

    # ------------------------------------------------------------------
    # ファイル検索
    # ------------------------------------------------------------------
    def search_files(
        self,
        base_path: str,
        keyword: str = "",
        extension: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        指定フォルダ配下を再帰的に検索し、キーワードおよび拡張子に一致する
        ファイルの一覧（絶対パス・メタ情報付き）を返す。

        Args:
            base_path: 検索の起点となるフォルダの絶対パス。
            keyword: ファイル名に部分一致させる検索キーワード（大文字小文字無視）。
                     空文字の場合はキーワードによる絞り込みを行わない。
            extension: 拡張子でのフィルタ（例: ".py" または "py"）。省略時は全拡張子対象。

        Returns:
            List[Dict[str, Any]]: 各要素は
                {"path", "name", "size_bytes", "modified_at", "is_dir"}
        """
        root = self._resolve_and_validate(base_path, must_exist=True)
        if not root.is_dir():
            raise FileSystemToolError(f"検索対象はディレクトリではありません: {root}")

        normalized_keyword = keyword.strip().lower()
        normalized_extension: Optional[str] = None
        if extension:
            normalized_extension = extension.lower()
            if not normalized_extension.startswith("."):
                normalized_extension = f".{normalized_extension}"

        results: List[Dict[str, Any]] = []

        for current_dir, dir_names, file_names in os.walk(root):
            # 隠しディレクトリ・巨大な仮想環境フォルダなどを軽くスキップ（暴走・ノイズ防止）
            dir_names[:] = [
                d for d in dir_names if d not in (".git", "node_modules", "__pycache__", ".venv")
            ]

            for file_name in file_names:
                if normalized_keyword and normalized_keyword not in file_name.lower():
                    continue
                if normalized_extension and not file_name.lower().endswith(normalized_extension):
                    continue

                file_path = Path(current_dir) / file_name
                try:
                    stat_result = file_path.stat()
                except OSError:
                    # アクセス権限エラーなどはスキップして検索を継続する
                    continue

                results.append(
                    {
                        "path": str(file_path),
                        "name": file_name,
                        "size_bytes": stat_result.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat_result.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "is_dir": False,
                    }
                )

                if len(results) >= self.max_search_results:
                    logger.warning(
                        "search_files: 最大件数(%d)に達したため検索を打ち切りました。",
                        self.max_search_results,
                    )
                    return results

        return results

    # ------------------------------------------------------------------
    # ディレクトリ一覧
    # ------------------------------------------------------------------
    def list_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """
        指定フォルダ直下のファイル・フォルダ一覧を、サイズ・更新日時付きで取得する。

        Args:
            dir_path: 一覧を取得したいディレクトリの絶対パス。

        Returns:
            List[Dict[str, Any]]: 各要素は
                {"path", "name", "size_bytes", "modified_at", "is_dir"}
        """
        target = self._resolve_and_validate(dir_path, must_exist=True)
        if not target.is_dir():
            raise FileSystemToolError(f"指定されたパスはディレクトリではありません: {target}")

        entries: List[Dict[str, Any]] = []

        try:
            iterator = os.scandir(target)
        except PermissionError as exc:
            raise FileSystemToolError(f"ディレクトリへのアクセス権限がありません: {target}") from exc

        with iterator as scan:
            for entry in scan:
                try:
                    stat_result = entry.stat(follow_symlinks=False)
                except OSError:
                    continue

                entries.append(
                    {
                        "path": entry.path,
                        "name": entry.name,
                        "size_bytes": stat_result.st_size if entry.is_file() else 0,
                        "modified_at": datetime.fromtimestamp(
                            stat_result.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "is_dir": entry.is_dir(follow_symlinks=False),
                    }
                )

                if len(entries) >= self.max_list_entries:
                    logger.warning(
                        "list_directory: 最大件数(%d)に達したため一覧取得を打ち切りました。",
                        self.max_list_entries,
                    )
                    break

        # フォルダを先に、その後ファイルを名前順で並べる
        entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))
        return entries

    # ------------------------------------------------------------------
    # OSエクスプローラー連携
    # ------------------------------------------------------------------
    def open_in_explorer(self, target_path: str) -> Dict[str, Any]:
        """
        指定されたファイルまたはフォルダをOS標準のファイルマネージャーで開く。
        - Windows: `explorer.exe`（ファイル指定時は `/select,` でそのファイルを選択状態で開く）
        - Linux: `xdg-open`（ファイル指定時は既定アプリで開かれるため、代わりに親フォルダを開く）
        - macOS: `open`（ファイル指定時は `-R` でFinder上に表示する）

        Args:
            target_path: 開きたいファイルまたはフォルダの絶対パス。

        Returns:
            Dict[str, Any]: {"opened_path", "mode", "platform"}

        Raises:
            PathSecurityError: パス検証に失敗した場合。
            FileSystemToolError: 対象が存在しない、または起動コマンドが見つからない場合。
        """
        target = self._resolve_and_validate(target_path, must_exist=True)

        if self._os_name == "Windows":
            return self._open_in_explorer_windows(target)
        if self._os_name == "Darwin":
            return self._open_in_explorer_macos(target)
        return self._open_in_explorer_linux(target)

    def _open_in_explorer_windows(self, target: Path) -> Dict[str, Any]:
        explorer_bin = shutil.which("explorer.exe") or shutil.which("explorer") or "explorer.exe"

        if target.is_file():
            # "/select,<path>" は1つの引数として渡す（カンマの前後にスペースを入れない）
            arg = f"/select,{target}"
            command = [explorer_bin, arg]
            mode = "select_file"
        else:
            command = [explorer_bin, str(target)]
            mode = "open_folder"

        self._run_command(command)
        return {"opened_path": str(target), "mode": mode, "platform": "Windows"}

    def _open_in_explorer_macos(self, target: Path) -> Dict[str, Any]:
        open_bin = shutil.which("open")
        if not open_bin:
            raise FileSystemToolError("'open' コマンドが見つかりません。")

        if target.is_file():
            command = [open_bin, "-R", str(target)]
            mode = "reveal_file"
        else:
            command = [open_bin, str(target)]
            mode = "open_folder"

        self._run_command(command)
        return {"opened_path": str(target), "mode": mode, "platform": "Darwin"}

    def _open_in_explorer_linux(self, target: Path) -> Dict[str, Any]:
        open_bin = shutil.which("xdg-open")
        if not open_bin:
            raise FileSystemToolError(
                "'xdg-open' コマンドが見つかりません。デスクトップ環境がインストールされているか確認してください。"
            )

        if target.is_file():
            # Linuxには「ファイルを選択状態で開く」共通APIが無いため、親フォルダを開く
            directory_to_open = target.parent
            mode = "open_parent_folder"
        else:
            directory_to_open = target
            mode = "open_folder"

        command = [open_bin, str(directory_to_open)]
        self._run_command(command)
        return {"opened_path": str(directory_to_open), "mode": mode, "platform": "Linux"}

    def _run_command(self, command: List[str]) -> None:
        """
        引数リストのみで外部コマンドを起動する（shell=True不使用、
        OSコマンドインジェクション対策済み）。ファイルマネージャーのGUI起動は
        ブロッキングを避けるため、完了を待たずに起動する。
        """
        try:
            subprocess.Popen(  # noqa: S603 - 引数リスト形式で実行しているため安全
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise FileSystemToolError(f"コマンドの実行に失敗しました: {command[0]}") from exc
        except OSError as exc:
            raise FileSystemToolError(f"エクスプローラーの起動に失敗しました: {exc}") from exc
