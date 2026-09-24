/**
 * frontend/src/components/MessageItem.tsx
 *
 * 個々のチャットメッセージを描画するコンポーネント。
 * react-markdown + remark-gfm でMarkdownを整形し、コードブロックには
 * シンタックスハイライトとワンクリックコピー機能を付与する。
 * ツール実行中はローディングバッジを表示し、list_directoryのように構造化データを
 * 返すツールについては、バックエンドが送ってくる実際の結果（tool_event）を
 * そのままFileTreeコンポーネントで描画する（LLMの文章生成には依存しない）。
 * さらに、メッセージ本文中にローカル絶対パス（Windows: `C:\...`、Unix: `/home/...`）
 * が含まれる場合、そのパスを「コピー」「エクスプローラーで開く」できる
 * アクションバーを表示する（バックエンドの /api/file-system/open を呼び出す）。
 */

"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Check,
  Copy,
  User,
  Bot,
  Wrench,
  Loader2,
  FolderOpen,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import clsx from "clsx";
import { API_BASE_URL, type ChatMessage, type ToolEventResult } from "@/lib/api";
import FileTree, { type DirectoryEntry } from "./FileTree";

export type ToolExecutionStatus = ToolEventResult;

export interface MessageItemProps {
  message: ChatMessage;
  isStreaming?: boolean;
  toolStatuses?: ToolExecutionStatus[];
  /** アシスタント回答を再試行する場合に呼ばれる。未指定なら再試行ボタンは表示しない。 */
  onRetry?: () => void;
  /** 送信中（ストリーミング中）は再試行を無効化する。 */
  disableRetry?: boolean;
}

interface CodeBlockProps {
  language: string;
  code: string;
}

function CodeBlock({ language, code }: CodeBlockProps): React.JSX.Element {
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="my-3 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-700 bg-zinc-800 px-3 py-1.5">
        <span className="text-xs font-medium text-zinc-400">
          {language || "text"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-100"
        >
          {copied ? (
            <>
              <Check size={13} />
              コピーしました
            </>
          ) : (
            <>
              <Copy size={13} />
              コピー
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: "0.75rem",
          fontSize: "0.8125rem",
          background: "transparent",
        }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

function ToolStatusBadge({
  status,
}: {
  status: ToolExecutionStatus;
}): React.JSX.Element {
  return (
    <div
      className={clsx(
        "mb-2 flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs",
        status.status === "running" &&
          "border-amber-700/50 bg-amber-950/40 text-amber-300",
        status.status === "done" &&
          "border-emerald-700/50 bg-emerald-950/40 text-emerald-300",
        status.status === "error" &&
          "border-red-700/50 bg-red-950/40 text-red-300"
      )}
    >
      {status.status === "running" ? (
        <Loader2 size={13} className="animate-spin" />
      ) : (
        <Wrench size={13} />
      )}
      <span>
        {status.status === "running" && `${status.toolName} を実行中...`}
        {status.status === "done" && `${status.toolName} の実行が完了しました`}
        {status.status === "error" && `${status.toolName} の実行に失敗しました`}
      </span>
      {status.detail && (
        <span className="truncate text-zinc-500">— {status.detail}</span>
      )}
    </div>
  );
}

/**
 * list_directoryの結果が期待通りの形（DirectoryEntryの配列）かどうかを判定する型ガード。
 */
function isDirectoryEntryArray(value: unknown): value is DirectoryEntry[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as Record<string, unknown>).path === "string" &&
        typeof (item as Record<string, unknown>).name === "string" &&
        typeof (item as Record<string, unknown>).is_dir === "boolean"
    )
  );
}

/**
 * 1件のツール実行結果を、ツール名に応じて適切なUIで描画する。
 * list_directoryは専用のFileTree表示、それ以外は従来通りのバッジのみ表示する。
 */
function ToolResultView({ status }: { status: ToolExecutionStatus }): React.JSX.Element {
  if (
    status.toolName === "list_directory" &&
    status.status === "done" &&
    isDirectoryEntryArray(status.result)
  ) {
    const directory =
      (status.arguments && typeof status.arguments.dir_path === "string"
        ? status.arguments.dir_path
        : undefined) ?? "";
    return <FileTree directory={directory} entries={status.result} />;
  }
  return <ToolStatusBadge status={status} />;
}

/** メッセージ本文からローカル絶対パスらしき文字列を抽出する。 */
function extractLocalPaths(text: string): string[] {
  const found = new Set<string>();
  const trimTrailingPunctuation = (value: string): string =>
    value.replace(/[.,;:!?)\]]+$/, "");

  // 先にURL全体の範囲（開始・終了インデックス）を特定しておく
  const urlSpans: Array<[number, number]> = [];
  const urlRegex = /\w+:\/\/[^\s<>"')\]]+/g;
  let urlMatch: RegExpExecArray | null;
  while ((urlMatch = urlRegex.exec(text)) !== null) {
    urlSpans.push([urlMatch.index, urlMatch.index + urlMatch[0].length]);
  }
  const isInsideUrl = (index: number): boolean =>
    urlSpans.some(([start, end]) => index >= start && index < end);

  const windowsRegex = /[A-Za-z]:\\(?:[^\s"'<>|?*\r\n]+\\)*[^\s"'<>|?*\r\n]+/g;
  let match: RegExpExecArray | null;
  while ((match = windowsRegex.exec(text)) !== null) {
    const candidate = trimTrailingPunctuation(match[0]);
    if (candidate.length > 3) {
      found.add(candidate);
    }
  }

  const unixRegex = /\/(?:[\w.\-]+\/)+[\w.\-]+/g;
  while ((match = unixRegex.exec(text)) !== null) {
    if (isInsideUrl(match.index)) {
      continue;
    }
    const candidate = trimTrailingPunctuation(match[0]);
    if (candidate.length > 3) {
      found.add(candidate);
    }
  }

  return Array.from(found);
}

interface PathActionsProps {
  paths: string[];
}

function PathActions({ paths }: PathActionsProps): React.JSX.Element | null {
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [openingPath, setOpeningPath] = useState<string | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);

  if (paths.length === 0) {
    return null;
  }

  const handleCopyPath = async (path: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      window.setTimeout(() => setCopiedPath(null), 1500);
    } catch {
      // クリップボードAPIが利用できない環境では静かに失敗させる
    }
  };

  const handleOpenInExplorer = async (path: string): Promise<void> => {
    setOpeningPath(path);
    setOpenError(null);
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
    } catch (error) {
      setOpenError(
        error instanceof Error
          ? error.message
          : "エクスプローラーで開けませんでした。"
      );
    } finally {
      setOpeningPath(null);
    }
  };

  return (
    <div className="mt-2 flex w-full flex-col gap-1.5">
      {paths.map((path) => (
        <div
          key={path}
          className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5"
        >
          <FolderOpen size={13} className="shrink-0 text-zinc-500" />
          <span
            className="flex-1 truncate font-mono text-[0.7rem] text-zinc-400"
            title={path}
          >
            {path}
          </span>
          <button
            type="button"
            onClick={() => void handleCopyPath(path)}
            className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-[0.7rem] text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
          >
            {copiedPath === path ? (
              <>
                <Check size={12} />
                コピー済み
              </>
            ) : (
              <>
                <Copy size={12} />
                パスをコピー
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => void handleOpenInExplorer(path)}
            disabled={openingPath === path}
            className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-[0.7rem] text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
          >
            {openingPath === path ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <FolderOpen size={12} />
            )}
            エクスプローラーで開く
          </button>
        </div>
      ))}
      {openError && (
        <p className="flex items-center gap-1.5 px-1 text-[0.7rem] text-red-400">
          <AlertCircle size={12} />
          {openError}
        </p>
      )}
    </div>
  );
}

function RenderedMarkdown({ text }: { text: string }): React.JSX.Element {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code(props) {
          const { className, children, ...rest } = props;
          const match = /language-(\w+)/.exec(className || "");
          const isInline = !match && !String(children).includes("\n");

          if (isInline) {
            return (
              <code
                className="rounded bg-zinc-900 px-1.5 py-0.5 text-[0.8125rem] text-amber-300"
                {...rest}
              >
                {children}
              </code>
            );
          }

          return (
            <CodeBlock
              language={match ? match[1] : ""}
              code={String(children).replace(/\n$/, "")}
            />
          );
        },
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

/** アシスタント回答全体をコピーするための小さな操作ボタン。 */
function CopyResponseButton({ content }: { content: string }): React.JSX.Element {
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // クリップボードAPIが利用できない環境では静かに失敗させる
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      title="回答をコピー"
      aria-label="回答をコピー"
      className="flex items-center gap-1 rounded px-1.5 py-1 text-[0.7rem] text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
    >
      {copied ? (
        <>
          <Check size={12} />
          コピーしました
        </>
      ) : (
        <>
          <Copy size={12} />
          コピー
        </>
      )}
    </button>
  );
}

export default function MessageItem({
  message,
  isStreaming = false,
  toolStatuses = [],
  onRetry,
  disableRetry = false,
}: MessageItemProps): React.JSX.Element {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isTool) {
    // toolロールの生メッセージはチャット欄には直接描画しない
    // （ツール実行結果はtoolStatuses/message.toolResults経由でassistantメッセージ内に表示する）
    return <></>;
  }

  const detectedPaths =
    !isUser && !isStreaming ? extractLocalPaths(message.content) : [];

  // ストリーミング中は toolStatuses（ライブ更新）、確定後は message.toolResults
  // （finalizeされた値）を使う。どちらもツール名ごとの最新状態を保持する配列。
  const effectiveToolResults: ToolExecutionStatus[] = isStreaming
    ? toolStatuses
    : message.toolResults ?? [];

  return (
    <div
      className={clsx(
        "flex gap-3 px-4 py-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={clsx(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-indigo-600" : "bg-zinc-700"
        )}
      >
        {isUser ? (
          <User size={16} className="text-white" />
        ) : (
          <Bot size={16} className="text-zinc-100" />
        )}
      </div>

      <div
        className={clsx(
          "flex max-w-[75%] flex-col gap-1",
          isUser ? "items-end" : "items-start"
        )}
      >
        {effectiveToolResults.length > 0 && (
          <div className="w-full">
            {effectiveToolResults.map((status, idx) => (
              <ToolResultView key={`${status.toolName}-${idx}`} status={status} />
            ))}
          </div>
        )}

        <div
          className={clsx(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-indigo-600 text-white"
              : "bg-zinc-800 text-zinc-100"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-pre:my-0 prose-pre:bg-transparent prose-pre:p-0">
              <RenderedMarkdown text={message.content || (isStreaming ? "" : "")} />
              {isStreaming && (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-400 align-middle" />
              )}
            </div>
          )}
        </div>

        {!isUser && !isStreaming && message.content && (
          <div className="flex items-center gap-1">
            <CopyResponseButton content={message.content} />
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                disabled={disableRetry}
                title="再試行"
                aria-label="再試行"
                className="flex items-center gap-1 rounded px-1.5 py-1 text-[0.7rem] text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
              >
                <RotateCcw size={12} />
                再試行
              </button>
            )}
          </div>
        )}

        {detectedPaths.length > 0 && <PathActions paths={detectedPaths} />}
      </div>
    </div>
  );
}
