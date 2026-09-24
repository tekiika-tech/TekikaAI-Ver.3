/**
 * frontend/src/components/SettingsModal.tsx
 *
 * 設定ダイアログ。Ollamaモデル選択と、インストール済みプラグインの閲覧、
 * 新規Pythonプラグインコードの貼り付け登録（AI自己アップデート用の投入口）を提供する。
 */

"use client";

import React, { useEffect, useState } from "react";
import { X, Plus, RefreshCw, Trash2, Loader2, Puzzle } from "lucide-react";
import clsx from "clsx";
import {
  getPlugins,
  registerPlugin,
  reloadPlugin,
  deletePlugin,
  type PluginInfo,
} from "@/lib/api";

export interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  ollamaModel: string;
  onOllamaModelChange: (model: string) => void;
}

const PRESET_MODELS = [
  "qwen2.5:latest",
  "qwen2.5:14b",
  "llama3.3:latest",
  "llama3.1:8b",
  "mistral-nemo:latest",
];

type Tab = "model" | "plugins";

export default function SettingsModal({
  isOpen,
  onClose,
  ollamaModel,
  onOllamaModelChange,
}: SettingsModalProps): React.JSX.Element | null {
  const [activeTab, setActiveTab] = useState<Tab>("model");
  const [customModel, setCustomModel] = useState<string>(ollamaModel);

  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [isLoadingPlugins, setIsLoadingPlugins] = useState<boolean>(false);
  const [pluginError, setPluginError] = useState<string | null>(null);

  const [newPluginName, setNewPluginName] = useState<string>("");
  const [newPluginCode, setNewPluginCode] = useState<string>("");
  const [isRegistering, setIsRegistering] = useState<boolean>(false);
  const [reloadingName, setReloadingName] = useState<string | null>(null);
  const [deletingName, setDeletingName] = useState<string | null>(null);

  const refreshPlugins = async (): Promise<void> => {
    setIsLoadingPlugins(true);
    setPluginError(null);
    try {
      const result = await getPlugins();
      setPlugins(result.loaded);
    } catch (error) {
      setPluginError(
        error instanceof Error ? error.message : "プラグイン一覧の取得に失敗しました。"
      );
    } finally {
      setIsLoadingPlugins(false);
    }
  };

  useEffect(() => {
    if (isOpen && activeTab === "plugins") {
      void refreshPlugins();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, activeTab]);

  if (!isOpen) return null;

  const handleSaveModel = (): void => {
    const trimmed = customModel.trim();
    if (trimmed) {
      onOllamaModelChange(trimmed);
    }
  };

  const handleRegisterPlugin = async (): Promise<void> => {
    const name = newPluginName.trim();
    const code = newPluginCode.trim();
    if (!name || !code) {
      setPluginError("プラグイン名とコードの両方を入力してください。");
      return;
    }

    setIsRegistering(true);
    setPluginError(null);
    try {
      await registerPlugin(name, code);
      setNewPluginName("");
      setNewPluginCode("");
      await refreshPlugins();
    } catch (error) {
      setPluginError(
        error instanceof Error ? error.message : "プラグインの登録に失敗しました。"
      );
    } finally {
      setIsRegistering(false);
    }
  };

  const handleReloadPlugin = async (name: string): Promise<void> => {
    setReloadingName(name);
    setPluginError(null);
    try {
      await reloadPlugin(name);
      await refreshPlugins();
    } catch (error) {
      setPluginError(
        error instanceof Error ? error.message : "プラグインの再読み込みに失敗しました。"
      );
    } finally {
      setReloadingName(null);
    }
  };

  const handleDeletePlugin = async (name: string): Promise<void> => {
    setDeletingName(name);
    setPluginError(null);
    try {
      await deletePlugin(name);
      await refreshPlugins();
    } catch (error) {
      setPluginError(
        error instanceof Error ? error.message : "プラグインの削除に失敗しました。"
      );
    } finally {
      setDeletingName(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex h-[600px] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        {/* ヘッダー */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-100">設定</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="閉じる"
            className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
          >
            <X size={18} />
          </button>
        </div>

        {/* タブ */}
        <div className="flex gap-1 border-b border-zinc-800 px-5 pt-3">
          <button
            type="button"
            onClick={() => setActiveTab("model")}
            className={clsx(
              "rounded-t-lg px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "model"
                ? "border-b-2 border-indigo-500 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            Ollamaモデル
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("plugins")}
            className={clsx(
              "rounded-t-lg px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "plugins"
                ? "border-b-2 border-indigo-500 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            プラグイン
          </button>
        </div>

        {/* 本文 */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {activeTab === "model" && (
            <div className="flex flex-col gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                  プリセットから選択
                </label>
                <div className="flex flex-wrap gap-2">
                  {PRESET_MODELS.map((model) => (
                    <button
                      key={model}
                      type="button"
                      onClick={() => setCustomModel(model)}
                      className={clsx(
                        "rounded-full border px-3 py-1.5 text-xs transition-colors",
                        customModel === model
                          ? "border-indigo-500 bg-indigo-950 text-indigo-300"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
                      )}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="custom-model-input"
                  className="mb-1.5 block text-xs font-medium text-zinc-400"
                >
                  モデル名を直接入力
                </label>
                <input
                  id="custom-model-input"
                  type="text"
                  value={customModel}
                  onChange={(event) => setCustomModel(event.target.value)}
                  placeholder="例: qwen2.5:latest"
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
                />
              </div>

              <button
                type="button"
                onClick={handleSaveModel}
                className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
              >
                このモデルを使用する
              </button>

              <p className="text-xs text-zinc-500">
                現在選択中のモデル: <span className="text-zinc-300">{ollamaModel}</span>
              </p>
            </div>
          )}

          {activeTab === "plugins" && (
            <div className="flex flex-col gap-5">
              {/* インストール済みプラグイン一覧 */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-zinc-400">
                    インストール済みプラグイン
                  </span>
                  <button
                    type="button"
                    onClick={() => void refreshPlugins()}
                    className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800"
                  >
                    <RefreshCw
                      size={12}
                      className={isLoadingPlugins ? "animate-spin" : ""}
                    />
                    更新
                  </button>
                </div>

                {isLoadingPlugins ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-zinc-500">
                    <Loader2 size={14} className="animate-spin" />
                    読み込み中...
                  </div>
                ) : plugins.length === 0 ? (
                  <p className="py-2 text-xs text-zinc-600">
                    登録済みのプラグインはありません。
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {plugins.map((plugin) => (
                      <li
                        key={plugin.name}
                        className="flex items-start justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2"
                      >
                        <div className="flex items-start gap-2">
                          <Puzzle size={14} className="mt-0.5 text-indigo-400" />
                          <div>
                            <p className="text-xs font-medium text-zinc-200">
                              {plugin.name}
                            </p>
                            <p className="text-[0.7rem] text-zinc-500">
                              {plugin.exported_tools.length > 0
                                ? plugin.exported_tools.join(", ")
                                : "公開関数なし"}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          <button
                            type="button"
                            onClick={() => void handleReloadPlugin(plugin.name)}
                            disabled={reloadingName === plugin.name}
                            aria-label="再読み込み"
                            className="rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
                          >
                            {reloadingName === plugin.name ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <RefreshCw size={13} />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDeletePlugin(plugin.name)}
                            disabled={deletingName === plugin.name}
                            aria-label="削除"
                            className="rounded p-1.5 text-zinc-400 hover:bg-red-950 hover:text-red-400 disabled:opacity-50"
                          >
                            {deletingName === plugin.name ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <Trash2 size={13} />
                            )}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* 新規プラグイン登録フォーム */}
              <div className="border-t border-zinc-800 pt-4">
                <p className="mb-2 text-xs font-medium text-zinc-400">
                  新規プラグインを登録（AI自己アップデート）
                </p>
                <input
                  type="text"
                  value={newPluginName}
                  onChange={(event) => setNewPluginName(event.target.value)}
                  placeholder="プラグイン名 (例: weather_lookup)"
                  className="mb-2 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
                />
                <textarea
                  value={newPluginCode}
                  onChange={(event) => setNewPluginCode(event.target.value)}
                  placeholder="def my_tool(arg: str) -> str:\n    return f'受け取った値: {arg}'"
                  rows={8}
                  className="mb-2 w-full resize-y rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-100 outline-none focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={() => void handleRegisterPlugin()}
                  disabled={isRegistering}
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-60"
                >
                  {isRegistering ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Plus size={14} />
                  )}
                  プラグインを登録
                </button>
              </div>

              {pluginError && (
                <p className="text-xs text-red-400">{pluginError}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
