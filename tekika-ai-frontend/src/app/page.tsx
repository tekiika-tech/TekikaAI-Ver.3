/**
 * frontend/src/app/page.tsx
 *
 * Project Agency (Tekika AI) のメイン統合ページ。
 * Sidebar / ChatWindow / SettingsModal を統合し、アプリ全体の状態
 * （会話メッセージ配列、動作モード、アクティブチャットID、セッション一覧）を管理する。
 */

"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import SettingsModal from "@/components/SettingsModal";
import type { ToolExecutionStatus } from "@/components/MessageItem";
import {
  listSessions,
  getSessionHistory,
  deleteSession as apiDeleteSession,
  exportData as apiExportData,
  importData as apiImportData,
  sendChatMessage,
  listProviders,
  type AgentMode,
  type ChatMessage,
  type SessionSummary,
  type ProviderInfo,
} from "@/lib/api";

const DEFAULT_MODEL = "qwen2.5:latest";

export default function HomePage(): React.JSX.Element {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<AgentMode>("QUALITY");
  const [ollamaModel, setOllamaModel] = useState<string>(DEFAULT_MODEL);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const [isSending, setIsSending] = useState<boolean>(false);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [toolStatuses, setToolStatuses] = useState<ToolExecutionStatus[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const refreshSessions = useCallback(async (): Promise<void> => {
    try {
      const result = await listSessions();
      setSessions(result);
    } catch (error) {
      // セッション一覧の取得失敗はチャット自体をブロックしないよう黙って無視する
      console.error("セッション一覧の取得に失敗しました:", error);
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    void listProviders().then((available) => {
      setProviders(available);
      setSelectedProvider((current) => current ?? available.find((item) => item.is_default)?.provider ?? available[0]?.provider ?? null);
    }).catch((error) => console.error("Provider一覧の取得に失敗しました:", error));
  }, []);

  const handleNewChat = useCallback((): void => {
    setActiveSessionId(null);
    setMessages([]);
    setStreamingContent("");
    setToolStatuses([]);
    setErrorMessage(null);
  }, []);

  const handleSelectSession = useCallback(
    async (sessionId: string): Promise<void> => {
      setActiveSessionId(sessionId);
      setStreamingContent("");
      setToolStatuses([]);
      setErrorMessage(null);
      try {
        const history = await getSessionHistory(sessionId);
        setMessages(history);
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "会話履歴の取得に失敗しました。"
        );
      }
    },
    []
  );

  const handleDeleteSession = useCallback(
    async (sessionId: string): Promise<void> => {
      try {
        await apiDeleteSession(sessionId);
        await refreshSessions();
        if (sessionId === activeSessionId) {
          handleNewChat();
        }
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "セッションの削除に失敗しました。"
        );
      }
    },
    [activeSessionId, handleNewChat, refreshSessions]
  );

  const handleExport = useCallback(async (): Promise<void> => {
    try {
      await apiExportData();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "エクスポートに失敗しました。"
      );
      throw error;
    }
  }, []);

  const handleImport = useCallback(
    async (file: File): Promise<void> => {
      await apiImportData(file);
      await refreshSessions();
      handleNewChat();
    },
    [handleNewChat, refreshSessions]
  );

  const handleSendMessage = useCallback(
    (userMessage: string): void => {
      const userChatMessage: ChatMessage = {
        role: "user",
        content: userMessage,
      };
      setMessages((prev) => [...prev, userChatMessage]);
      startChatRequest(userMessage, { regenerate: false });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeSessionId, mode, refreshSessions, selectedProvider]
  );

  const handleRetryMessage = useCallback(
    (assistantIndex: number): void => {
      // 直前のユーザー発言を探す（再試行はそのユーザー発言を使って回答を再生成する）
      let userIndex = assistantIndex - 1;
      while (userIndex >= 0 && messages[userIndex].role !== "user") {
        userIndex -= 1;
      }
      if (userIndex < 0) return;
      const userMessageContent = messages[userIndex].content;

      // 古いアシスタント回答（とそれ以降）を取り除き、ユーザー発言まで残す。
      // ユーザーメッセージ自体は再送しない（重複防止）。
      setMessages((prev) => prev.slice(0, assistantIndex));
      startChatRequest(userMessageContent, { regenerate: true });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, activeSessionId, mode, refreshSessions, selectedProvider]
  );

  /**
   * チャットリクエストの送信〜完了までの共通処理。
   * 通常送信（handleSendMessage）と再試行（handleRetryMessage）の両方から使う。
   *
   * @param userMessage - LLMに送るユーザー発言（再試行時は直前と同じ内容）。
   * @param options.regenerate - trueの場合、バックエンドはこの発言を履歴に
   *   新規保存せず、既存の履歴のみを使って回答を再生成する（重複防止）。
   */
  function startChatRequest(
    userMessage: string,
    options: { regenerate: boolean }
  ): void {
    setStreamingContent("");
    setToolStatuses([]);
    setErrorMessage(null);
    setIsSending(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulated = "";
    const startTime = Date.now();
    // React stateのsetToolStatusesは非同期のため、onDone時点で「今回のターンで
    // 実際に実行されたツール結果一式」を確実に取得できるよう、ローカル変数にも
    // 同時に蓄積しておく（finalizeされたメッセージへ添付するため）。
    let localToolResults: ToolExecutionStatus[] = [];

    void sendChatMessage(userMessage, activeSessionId, mode, {
      signal: controller.signal,
      regenerate: options.regenerate,
      provider: selectedProvider,
      onChunk: (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      },
      onToolEvent: (event) => {
        const toolName =
          typeof event.tool_name === "string" ? event.tool_name : "ツール";
        const status =
          (event.status as ToolExecutionStatus["status"]) || "running";
        const eventArguments =
          event.arguments && typeof event.arguments === "object"
            ? (event.arguments as Record<string, unknown>)
            : undefined;
        const updated: ToolExecutionStatus = {
          toolName,
          status,
          arguments: eventArguments,
          result: event.result,
        };
        localToolResults = [
          ...localToolResults.filter((item) => item.toolName !== toolName),
          updated,
        ];
        setToolStatuses(localToolResults);
      },
      onDone: (sessionId) => {
        setIsSending(false);
        const elapsedTime = Number(((Date.now() - startTime) / 1000).toFixed(1));
        if (accumulated) {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: accumulated,
              execution_time: elapsedTime,
              toolResults: localToolResults.length > 0 ? localToolResults : undefined,
            },
          ]);
        }
        setStreamingContent("");
        setToolStatuses([]);
        if (sessionId && sessionId !== activeSessionId) {
          setActiveSessionId(sessionId);
        }
        void refreshSessions();
        abortControllerRef.current = null;
      },
      onError: (error) => {
        setIsSending(false);
        setStreamingContent("");
        setToolStatuses([]);
        setErrorMessage(error.message || "エージェントとの通信に失敗しました。");
        abortControllerRef.current = null;
      },
    });
  }

  const handleStopGeneration = useCallback((): void => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsSending(false);
    if (streamingContent) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `${streamingContent}\n\n*(生成が中断されました)*` },
      ]);
    }
    setStreamingContent("");
    setToolStatuses([]);
  }, [streamingContent]);

  return (
    <main className="flex h-screen w-full overflow-hidden bg-zinc-900">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        mode={mode}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        onNewChat={handleNewChat}
        onSelectSession={(sessionId) => void handleSelectSession(sessionId)}
        onDeleteSession={(sessionId) => void handleDeleteSession(sessionId)}
        onModeChange={setMode}
        onExport={handleExport}
        onImport={handleImport}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <ChatWindow
        messages={messages}
        mode={mode}
        providers={providers}
        selectedProvider={selectedProvider}
        onProviderChange={setSelectedProvider}
        isSending={isSending}
        streamingContent={streamingContent}
        toolStatuses={toolStatuses}
        errorMessage={errorMessage}
        onSendMessage={handleSendMessage}
        onStopGeneration={handleStopGeneration}
        onRetryMessage={handleRetryMessage}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        ollamaModel={ollamaModel}
        onOllamaModelChange={setOllamaModel}
      />
    </main>
  );
}
