/**
 * frontend/src/components/FileTree.tsx
 *
 * list_directoryツールの実際の戻り値（1階層分のエントリ配列:
 * [{"path", "name", "size_bytes", "modified_at", "is_dir"}, ...]）を、
 * 生のJSONやLLMの文章としてではなく、フォルダ/ファイルアイコン付きの
 * ツリー表示として描画する。LLMの文章生成には一切依存せず、バックエンドが
 * SSEの tool_event として送ってくる構造化データをそのまま解釈して表示する。
 *
 * 各行から、既存の「パスをコピー」「エクスプローラーで開く」
 * （POST /api/file-system/open）を利用できる。
 */

"use client";

import React, { useState } from "react";
import {
  Check,
  Copy,
  Folder,
  FileText,
  FolderOpen,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

export interface DirectoryEntry {
  path: string;
  name: string;
  size_bytes: number;
  modified_at: string;
  is_dir: boolean;
}

export interface FileTreeProps {
  /** 一覧取得対象のディレクトリの絶対パス（list_directory呼び出し時の dir_path 引数）。 */
  directory: string;
  /** list_directoryの戻り値そのもの（直下1階層分のエントリ配列）。 */
  entries: DirectoryEntry[];
}

interface RowState {
  copiedPath: string | null;
  openingPath: string | null;
  openError: string | null;
}

function directoryLabel(directory: string): string {
  const segments = directory.split(/[\\/]/).filter(Boolean);
  return segments.length > 0 ? segments[segments.length - 1] : directory;
}

export default function FileTree({ directory, entries }: FileTreeProps): React.JSX.Element {
  const [state, setState] = useState<RowState>({
    copiedPath: null,
    openingPath: null,
    openError: null,
  });

  const handleCopy = async (path: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(path);
      setState((s) => ({ ...s, copiedPath: path }));
      window.setTimeout(() => setState((s) => ({ ...s, copiedPath: null })), 1500);
    } catch {
      // クリップボードAPIが利用できない環境では静かに失敗させる
    }
  };

  const handleOpen = async (path: string): Promise<void> => {
    setState((s) => ({ ...s, openingPath: path, openError: null }));
    try {
      const response = await fetch(`${API_BASE_URL}/file-system/open`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_path: path }),
      });

      if (!response.ok) {
        let detail = `エクスプローラーで開けませんでした (${response.status})`;
        try {
          const data = await response.json();
          if (data && typeof data.detail === "string") {
            detail = data.detail;
          }
        } catch {
          // レスポンスがJSONでない場合はデフォルトメッセージのまま
        }
        throw new Error(detail);
      }
      setState((s) => ({ ...s, openingPath: null }));
    } catch (error) {
      setState((s) => ({
        ...s,
        openingPath: null,
        openError: error instanceof Error ? error.message : "エクスプローラーで開けませんでした。",
      }));
    }
  };

  return (
    <div className="my-2 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900">
      <div
        className="truncate border-b border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-400"
        title={directory}
      >
        {directory}
      </div>
      <div className="max-h-72 overflow-y-auto px-3 py-2 font-mono text-xs">
        <Row
          icon={<Folder size={13} className="shrink-0 text-amber-400" />}
          label={directoryLabel(directory)}
          prefix=""
          absolutePath={directory}
          state={state}
          onCopy={handleCopy}
          onOpen={handleOpen}
        />
        {entries.length === 0 ? (
          <div className="py-1 pl-5 text-zinc-600">（空のディレクトリ）</div>
        ) : (
          entries.map((entry, index) => {
            const isLast = index === entries.length - 1;
            return (
              <Row
                key={entry.path}
                icon={
                  entry.is_dir ? (
                    <Folder size={13} className="shrink-0 text-amber-400" />
                  ) : (
                    <FileText size={13} className="shrink-0 text-zinc-400" />
                  )
                }
                label={entry.name}
                prefix={isLast ? "└── " : "├── "}
                absolutePath={entry.path}
                state={state}
                onCopy={handleCopy}
                onOpen={handleOpen}
              />
            );
          })
        )}
      </div>
      {state.openError && (
        <div className="flex items-center gap-1.5 border-t border-zinc-800 px-3 py-1.5 text-[0.7rem] text-red-400">
          <AlertCircle size={12} />
          {state.openError}
        </div>
      )}
    </div>
  );
}

interface RowProps {
  icon: React.ReactNode;
  label: string;
  prefix: string;
  absolutePath: string;
  state: RowState;
  onCopy: (path: string) => void;
  onOpen: (path: string) => void;
}

function Row({ icon, label, prefix, absolutePath, state, onCopy, onOpen }: RowProps): React.JSX.Element {
  const isCopied = state.copiedPath === absolutePath;
  const isOpening = state.openingPath === absolutePath;

  return (
    <div className="group flex items-center gap-1.5 whitespace-pre text-zinc-200">
      <span className="text-zinc-600">{prefix}</span>
      {icon}
      <span className="truncate" title={absolutePath}>
        {label}
      </span>
      <span className="ml-auto flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={() => onCopy(absolutePath)}
          title="パスをコピー"
          aria-label="パスをコピー"
          className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
        >
          {isCopied ? <Check size={11} /> : <Copy size={11} />}
        </button>
        <button
          type="button"
          onClick={() => onOpen(absolutePath)}
          disabled={isOpening}
          title="エクスプローラーで開く"
          aria-label="エクスプローラーで開く"
          className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
        >
          {isOpening ? <Loader2 size={11} className="animate-spin" /> : <FolderOpen size={11} />}
        </button>
      </span>
    </div>
  );
}
