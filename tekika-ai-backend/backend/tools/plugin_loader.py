"""
backend/tools/plugin_loader.py

/plugins フォルダ配下のPythonファイルをimportlibで動的にロードする基盤。
AI自身が新しいプラグインコードを生成・保存し、ホットリロードできる
「自己アップデート基盤」を提供する。外部レジストリへの通信は行わない。
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import logging
import re
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("tekika_ai.plugin_loader")

_VALID_PLUGIN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PluginError(Exception):
    """プラグイン読み込み・登録に関するエラー。"""


class PluginValidationError(PluginError):
    """プラグインコードの静的検証に失敗した場合のエラー。"""


@dataclass
class LoadedPlugin:
    """ロード済みプラグインのメタ情報。"""

    name: str
    file_path: Path
    module: types.ModuleType
    exported_tools: List[str] = field(default_factory=list)


class PluginLoader:
    """
    プラグインの動的ロード・登録・ホットリロードを管理するクラス。

    プラグインファイルは `/plugins/<plugin_name>.py` に配置され、
    トップレベルの関数のうち `_` で始まらないものが自動的にツールとして
    エクスポート対象とみなされる。

    Attributes:
        plugin_dir: プラグインファイルを格納するディレクトリ。
    """

    def __init__(self, plugin_dir: Path) -> None:
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: Dict[str, LoadedPlugin] = {}

    # ------------------------------------------------------------------
    # 静的検証（自己生成コードの安全性チェック）
    # ------------------------------------------------------------------
    _FORBIDDEN_MODULES = {
        "os.system",
        "subprocess",
        "shutil.rmtree",
    }

    def _validate_plugin_source(self, source_code: str, plugin_name: str) -> None:
        """
        AIが生成したプラグインコードに対する最低限の静的検証。
        構文エラーの検出と、危険度の高い呼び出しパターンの簡易検出を行う。
        完全なサンドボックスではないため、あくまで一次的な安全弁として機能する。
        """
        try:
            tree = ast.parse(source_code, filename=f"{plugin_name}.py")
        except SyntaxError as exc:
            raise PluginValidationError(f"プラグインコードの構文エラー: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("subprocess",):
                        logger.warning(
                            "プラグイン '%s' が subprocess をインポートしています。注意して利用してください。",
                            plugin_name,
                        )
            if isinstance(node, ast.Call):
                func = node.func
                call_name = None
                if isinstance(func, ast.Attribute):
                    call_name = func.attr
                elif isinstance(func, ast.Name):
                    call_name = func.id
                if call_name == "eval" or call_name == "exec":
                    raise PluginValidationError(
                        f"プラグイン '{plugin_name}' 内で禁止された呼び出し ({call_name}) が検出されました。"
                    )

    # ------------------------------------------------------------------
    # プラグイン登録（自己アップデート）
    # ------------------------------------------------------------------
    def register_new_plugin(self, plugin_name: str, python_code: str) -> LoadedPlugin:
        """
        AI自身が生成した新しいプラグインコードを検証のうえ `/plugins` に保存し、
        直ちにホットロードする。

        Args:
            plugin_name: プラグイン名（Pythonの識別子として有効な文字列）。
            python_code: プラグイン本体のPythonソースコード。

        Returns:
            LoadedPlugin: ロード済みプラグインのメタ情報。
        """
        if not _VALID_PLUGIN_NAME_RE.match(plugin_name):
            raise PluginError(
                f"不正なプラグイン名です: {plugin_name}"
                "（英字またはアンダースコアで始まり、英数字とアンダースコアのみ使用可能）"
            )

        self._validate_plugin_source(python_code, plugin_name)

        file_path = self.plugin_dir / f"{plugin_name}.py"
        file_path.write_text(python_code, encoding="utf-8")
        logger.info("新しいプラグインを保存しました: %s", file_path)

        return self.load_plugin(plugin_name)

    # ------------------------------------------------------------------
    # ロード / リロード / アンロード
    # ------------------------------------------------------------------
    def load_plugin(self, plugin_name: str) -> LoadedPlugin:
        """指定プラグインファイルをロード（または既存モジュールをリロード）する。"""
        file_path = self.plugin_dir / f"{plugin_name}.py"
        if not file_path.exists():
            raise PluginError(f"プラグインファイルが見つかりません: {file_path}")

        module_qualname = f"tekika_plugins.{plugin_name}"

        spec = importlib.util.spec_from_file_location(module_qualname, str(file_path))
        if spec is None or spec.loader is None:
            raise PluginError(f"プラグインのモジュール仕様を生成できませんでした: {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_qualname] = module

        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - プラグインコードの実行時エラーを捕捉
            sys.modules.pop(module_qualname, None)
            raise PluginError(f"プラグイン '{plugin_name}' の実行に失敗しました: {exc}") from exc

        exported_tools = [
            name
            for name, value in vars(module).items()
            if callable(value) and not name.startswith("_") and isinstance(value, types.FunctionType)
        ]

        loaded = LoadedPlugin(
            name=plugin_name,
            file_path=file_path,
            module=module,
            exported_tools=exported_tools,
        )
        self._loaded[plugin_name] = loaded
        logger.info(
            "プラグイン '%s' をロードしました（公開関数: %s）", plugin_name, exported_tools
        )
        return loaded

    def reload_plugin(self, plugin_name: str) -> LoadedPlugin:
        """既にロード済みのプラグインを最新のファイル内容で再ロードする。"""
        self.unload_plugin(plugin_name)
        return self.load_plugin(plugin_name)

    def unload_plugin(self, plugin_name: str) -> None:
        """プラグインをアンロードする（sys.modulesからも削除）。"""
        module_qualname = f"tekika_plugins.{plugin_name}"
        sys.modules.pop(module_qualname, None)
        self._loaded.pop(plugin_name, None)
        logger.info("プラグイン '%s' をアンロードしました。", plugin_name)

    def load_all_plugins(self) -> List[LoadedPlugin]:
        """`/plugins` ディレクトリ内の全 `.py` ファイルをロードする。"""
        loaded_plugins: List[LoadedPlugin] = []
        for file_path in sorted(self.plugin_dir.glob("*.py")):
            if file_path.stem.startswith("_"):
                continue
            try:
                loaded_plugins.append(self.load_plugin(file_path.stem))
            except PluginError:
                logger.exception("プラグイン '%s' のロードに失敗しました。スキップします。", file_path.stem)
        return loaded_plugins

    # ------------------------------------------------------------------
    # 参照系
    # ------------------------------------------------------------------
    def list_loaded_plugins(self) -> List[Dict[str, Any]]:
        """現在ロード中の全プラグインのメタ情報一覧を取得する。"""
        return [
            {
                "name": p.name,
                "file_path": str(p.file_path),
                "exported_tools": p.exported_tools,
            }
            for p in self._loaded.values()
        ]

    def list_available_plugin_files(self) -> List[str]:
        """`/plugins` ディレクトリに存在する全プラグインファイル名（ロード状況に関わらず）を取得する。"""
        return sorted(p.stem for p in self.plugin_dir.glob("*.py") if not p.stem.startswith("_"))

    def get_tool_function(self, plugin_name: str, tool_name: str) -> Optional[Callable]:
        """指定プラグイン内の特定関数を取得する。"""
        plugin = self._loaded.get(plugin_name)
        if plugin is None:
            return None
        return getattr(plugin.module, tool_name, None)

    def get_all_tool_functions(self) -> Dict[str, Callable]:
        """全ロード済みプラグインが公開する関数を `{関数名: 関数}` の形でまとめて取得する。"""
        tools: Dict[str, Callable] = {}
        for plugin in self._loaded.values():
            for tool_name in plugin.exported_tools:
                func = getattr(plugin.module, tool_name, None)
                if callable(func):
                    tools[tool_name] = func
        return tools

    def delete_plugin(self, plugin_name: str) -> None:
        """プラグインをアンロードし、ファイルも削除する。"""
        self.unload_plugin(plugin_name)
        file_path = self.plugin_dir / f"{plugin_name}.py"
        if file_path.exists():
            file_path.unlink()
            logger.info("プラグインファイルを削除しました: %s", file_path)
