/**
 * frontend/src/components/Sidebar.tsx
 *
 * Project Agency (Tekika AI) のサイドバーコンポーネント。
 * 新規チャット作成、会話履歴一覧、Quality/Speed モード切替トグル、
 * 全データのエクスポート/インポート、設定ダイアログ呼び出しボタンを提供する。
 */

"use client";

import React, { useRef, useState } from "react";
import {
  Plus,
  MessageSquare,
  Zap,
  Sparkles,
  Download,
  Upload,
  Settings,
  Trash2,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import clsx from "clsx";
import type { AgentMode, SessionSummary } from "@/lib/api";

export interface SidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  mode: AgentMode;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onModeChange: (mode: AgentMode) => void;
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
  onOpenSettings: () => void;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  mode,
  isCollapsed,
  onToggleCollapse,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onModeChange,
  onExport,
  onImport,
  onOpenSettings,
}: SidebarProps): React.JSX.Element {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importError, setImportError] = useState<string | null>(null);

  const handleExportClick = async (): Promise<void> => {
    setIsExporting(true);
    try {
      await onExport();
    } finally {
      setIsExporting(false);
    }
  };

  const handleImportButtonClick = (): void => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement>
  ): Promise<void> => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setImportError(null);
    try {
      await onImport(file);
    } catch (error) {
      setImportError(
        error instanceof Error ? error.message : "インポートに失敗しました。"
      );
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  if (isCollapsed) {
    return (
      <div className="flex h-full w-14 flex-col items-center gap-3 border-r border-zinc-800 bg-zinc-950 py-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="サイドバーを開く"
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
        >
          <PanelLeftOpen size={20} />
        </button>
        <button
          type="button"
          onClick={onNewChat}
          aria-label="新規チャット"
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
        >
          <Plus size={20} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-72 flex-col border-r border-zinc-800 bg-zinc-950">
      {/* ヘッダー */}
      <div className="flex items-center justify-between px-3 py-4">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-indigo-400" />
          <span className="text-sm font-semibold text-zinc-100">
            Tekika AI
          </span>
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="サイドバーを閉じる"
          className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      {/* 新規チャット */}
      <div className="px-3">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm font-medium text-zinc-100 transition-colors hover:bg-zinc-800"
        >
          <Plus size={16} />
          新規チャット
        </button>
      </div>

      {/* モード切替 */}
      <div className="mt-4 px-3">
        <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          動作モード
        </p>
        <div className="flex rounded-lg bg-zinc-900 p-1">
          <button
            type="button"
            onClick={() => onModeChange("QUALITY")}
            className={clsx(
              "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
              mode === "QUALITY"
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:text-zinc-200"
            )}
          >
            <Sparkles size={14} />
            Quality
          </button>
          <button
            type="button"
            onClick={() => onModeChange("SPEED")}
            className={clsx(
              "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
              mode === "SPEED"
                ? "bg-amber-600 text-white"
                : "text-zinc-400 hover:text-zinc-200"
            )}
          >
            <Zap size={14} />
            Speed
          </button>
        </div>
      </div>

      {/* 会話履歴 */}
      <div className="mt-4 flex-1 overflow-y-auto px-3">
        <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          会話履歴
        </p>
        {sessions.length === 0 ? (
          <p className="px-1 text-xs text-zinc-600">
            まだ会話履歴がありません。
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <div
                  className={clsx(
                    "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors",
                    session.session_id === activeSessionId
                      ? "bg-zinc-800 text-zinc-100"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.session_id)}
                    className="flex flex-1 items-center gap-2 overflow-hidden text-left"
                  >
                    <MessageSquare size={14} className="shrink-0" />
                    <span className="truncate">
                      {session.title || session.session_id}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteSession(session.session_id)}
                    aria-label="セッションを削除"
                    className="shrink-0 rounded p-1 text-zinc-500 opacity-0 transition-opacity hover:bg-zinc-700 hover:text-red-400 group-hover:opacity-100"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* データ管理 */}
      <div className="border-t border-zinc-800 px-3 py-3">
        <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          データ管理
        </p>
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            onClick={handleExportClick}
            disabled={isExporting}
            className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 disabled:opacity-50"
          >
            {isExporting ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Download size={15} />
            )}
            全データをエクスポート
          </button>
          <button
            type="button"
            onClick={handleImportButtonClick}
            disabled={isImporting}
            className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 disabled:opacity-50"
          >
            {isImporting ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Upload size={15} />
            )}
            データをインポート
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={handleFileChange}
          />
          {importError && (
            <p className="px-1 text-xs text-red-400">{importError}</p>
          )}
        </div>
      </div>

      {/* 設定 */}
      <div className="border-t border-zinc-800 px-3 py-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          <Settings size={15} />
          設定
        </button>
      </div>
    </div>
  );
}
