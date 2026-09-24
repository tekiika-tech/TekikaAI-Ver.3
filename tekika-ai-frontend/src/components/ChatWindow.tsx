/**
 * frontend/src/components/ChatWindow.tsx
 *
 * メインチャット表示エリア。メッセージ一覧の自動下スクロール、
 * Enter送信/Shift+Enter改行に対応したマルチライン入力フォーム、
 * 送信中の停止ボタン(AbortController連携)を提供する。
 */

"use client";

import React, {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Send, Square, Sparkles, Zap, AlertCircle } from "lucide-react";
import clsx from "clsx";
import type { AgentMode, ChatMessage } from "@/lib/api";
import MessageItem, { type ToolExecutionStatus } from "./MessageItem";
import type { ProviderInfo } from "@/lib/api";

export interface ChatWindowProps {
  messages: ChatMessage[];
  mode: AgentMode;
  providers: ProviderInfo[];
  selectedProvider: string | null;
  onProviderChange: (provider: string | null) => void;
  isSending: boolean;
  streamingContent: string;
  toolStatuses: ToolExecutionStatus[];
  errorMessage: string | null;
  onSendMessage: (message: string) => void;
  onStopGeneration: () => void;
  /** 指定インデックスのアシスタント回答を再試行する。未指定なら再試行ボタンは表示されない。 */
  onRetryMessage?: (assistantIndex: number) => void;
}

export default function ChatWindow({
  messages,
  mode,
  providers,
  selectedProvider,
  onProviderChange,
  isSending,
  streamingContent,
  toolStatuses,
  errorMessage,
  onSendMessage,
  onStopGeneration,
  onRetryMessage,
}: ChatWindowProps): React.JSX.Element {
  const [inputValue, setInputValue] = useState<string>("");
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, toolStatuses]);

  const handleSubmit = (): void => {
    const trimmed = inputValue.trim();
    if (!trimmed || isSending) return;
    onSendMessage(trimmed);
    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaChange = (
    event: React.ChangeEvent<HTMLTextAreaElement>
  ): void => {
    setInputValue(event.target.value);
    const el = event.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const showStreamingBubble =
    isSending && (streamingContent.length > 0 || toolStatuses.length > 0);

  return (
    <div className="flex h-full flex-1 flex-col bg-zinc-900">
      {/* ヘッダー */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
        <h1 className="text-sm font-semibold text-zinc-100">
          Project Agency — Tekika AI
        </h1>
        <div className="flex items-center gap-3">
        {providers.length > 0 && <label className="flex items-center gap-2 text-xs text-zinc-400">
          Provider
          <select value={selectedProvider ?? providers.find((item) => item.is_default)?.provider ?? ""} onChange={(event) => onProviderChange(event.target.value || null)} disabled={isSending}
            className="max-w-36 rounded-md border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-100">
            {providers.map((item) => <option key={item.provider} value={item.provider}>{item.provider}</option>)}
          </select>
          <span className="hidden text-zinc-500 lg:inline">{providers.find((item) => item.provider === selectedProvider)?.default_model ?? providers.find((item) => item.is_default)?.default_model}</span>
        </label>}
        <span
          className={clsx(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            mode === "QUALITY"
              ? "bg-indigo-950 text-indigo-300"
              : "bg-amber-950 text-amber-300"
          )}
        >
          {mode === "QUALITY" ? <Sparkles size={12} /> : <Zap size={12} />}
          {mode === "QUALITY" ? "Quality Priority" : "Speed Priority"}
        </span>
        </div>
      </div>

      {/* メッセージ一覧 */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 && !showStreamingBubble ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-zinc-500">
            <Sparkles size={28} className="text-zinc-700" />
            <p className="text-sm">
              Tekika AIに指示を送って、ローカルタスクを開始しましょう。
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col">
            {messages.map((message, index) => (
              <MessageItem
                key={`${message.role}-${index}`}
                message={message}
                onRetry={
                  message.role === "assistant" && onRetryMessage
                    ? () => onRetryMessage(index)
                    : undefined
                }
                disableRetry={isSending}
              />
            ))}

            {showStreamingBubble && (
              <MessageItem
                message={{ role: "assistant", content: streamingContent }}
                isStreaming
                toolStatuses={toolStatuses}
              />
            )}
          </div>
        )}
        <div ref={scrollAnchorRef} />
      </div>

      {/* エラー表示 */}
      {errorMessage && (
        <div className="mx-auto flex w-full max-w-3xl items-center gap-2 px-4 pb-1 text-xs text-red-400">
          <AlertCircle size={14} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 入力フォーム */}
      <div className="border-t border-zinc-800 px-4 py-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-700 bg-zinc-800 px-3 py-2">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Tekika AIへの指示を入力... (Shift+Enterで改行)"
            rows={1}
            disabled={isSending}
            className="max-h-[200px] flex-1 resize-none bg-transparent text-sm text-zinc-100 placeholder-zinc-500 outline-none disabled:opacity-60"
          />
          {isSending ? (
            <button
              type="button"
              onClick={onStopGeneration}
              aria-label="生成を停止"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-600 text-white transition-colors hover:bg-red-500"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
            disabled={!inputValue.trim() || isSending}
              aria-label="送信"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
