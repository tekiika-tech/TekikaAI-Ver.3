/**
 * frontend/src/lib/api.ts
 *
 * Project Agency (Tekika AI) バックエンド (http://localhost:8000) との通信クライアント。
 * SSE (Server-Sent Events) を fetch の ReadableStream で読み取るストリーミングチャット、
 * データのエクスポート/インポート、プラグイン管理APIを提供する。
 * 外部クラウドサービスへは一切通信しない（バックエンドのローカルAPIのみを呼び出す）。
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export type AgentMode = "QUALITY" | "SPEED";

/**
 * list_directory等、ツール呼び出しの構造化された結果。
 * LLMの文章内容とは独立して、バックエンドがSSEの tool_event として送ってくる
 * 実際のデータ（引数・結果）を保持する。UIはこれを直接解釈して表示する
 * （LLMにJSON/ツリー文字列を生成させる方式は取らない）。
 */
export interface ToolEventResult {
  toolName: string;
  status: "running" | "done" | "error";
  detail?: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_name?: string | null;
  created_at?: string;
  execution_time?: number;
  /** このアシスタント回答の生成中に実行されたツールの構造化結果（あれば）。 */
  toolResults?: ToolEventResult[];
}

export interface ChatRequestPayload {
  message: string;
  session_id?: string | null;
  mode?: AgentMode | null;
  stream?: boolean;
  regenerate?: boolean;
  provider?: string | null;
}

export interface ProviderInfo {
  provider: string;
  default_model: string;
  is_default: boolean;
}

export async function listProviders(): Promise<ProviderInfo[]> {
  return requestJson<ProviderInfo[]>("/providers", { method: "GET" });
}

export interface ChatResponsePayload {
  session_id: string;
  response: string;
  mode: string;
  tool_trace: Array<Record<string, unknown>>;
  execution_time?: number;
}

export interface SessionSummary {
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface PluginInfo {
  name: string;
  file_path: string;
  exported_tools: string[];
}

export interface PluginListResponse {
  loaded: PluginInfo[];
  available_files: string[];
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorResponse(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (data && typeof data.detail === "string") {
      return data.detail;
    }
    return JSON.stringify(data);
  } catch {
    return response.statusText || `HTTPエラー: ${response.status}`;
  }
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const message = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

/**
 * 非ストリーミングでチャットメッセージを送信し、完全な応答を取得する。
 */
export async function sendChatMessageOnce(
  message: string,
  sessionId: string | null,
  mode: AgentMode
): Promise<ChatResponsePayload> {
  return requestJson<ChatResponsePayload>("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      session_id: sessionId,
      mode,
      stream: false,
    } as ChatRequestPayload),
  });
}

export interface SendChatMessageOptions {
  onChunk: (chunk: string) => void;
  onToolEvent?: (event: Record<string, unknown>) => void;
  onDone?: (sessionId: string | null) => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
  /**
   * Trueの場合、messageを新規のユーザー発言として保存せず、既存の会話履歴のみを
   * 使って直前の回答を再生成する（「再試行」機能用）。既定はfalse。
   */
  regenerate?: boolean;
  provider?: string | null;
}

/**
 * SSE (Server-Sent Events) を用いてチャットメッセージをストリーミング送信する。
 * バックエンドの `/api/chat` (stream=true) が返す `data: {...}\n\n` 形式の
 * イベントを fetch の ReadableStream から逐次パースし、コールバックへ渡す。
 *
 * @param message - ユーザーの入力メッセージ。
 * @param sessionId - 会話セッションID（新規会話時は null）。
 * @param mode - QUALITY または SPEED。
 * @param options - onChunk / onToolEvent / onDone / onError / signal / regenerate コールバック群。
 */
export async function sendChatMessage(
  message: string,
  sessionId: string | null,
  mode: AgentMode,
  options: SendChatMessageOptions
): Promise<void> {
  const { onChunk, onToolEvent, onDone, onError, signal, regenerate, provider } = options;

  // onDone / onError のどちらか一方を必ず1回だけ発火させるためのガード。
  // これが無いと、「SSEの done イベント受信時」と「ReadableStream終了時」で
  // onDoneが二重に呼ばれたり、backend側エラー受信後にさらにonDoneが呼ばれたりして、
  // 処理完了前に中断ボタンが送信ボタンへ戻ってしまう不具合につながる。
  let settled = false;
  const finishWithDone = (): void => {
    if (settled) return;
    settled = true;
    onDone?.(sessionId);
  };
  const finishWithError = (error: Error): void => {
    if (settled) return;
    settled = true;
    onError?.(error);
  };

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        mode,
        stream: true,
        regenerate: regenerate ?? false,
        provider: provider ?? null,
      } as ChatRequestPayload),
      signal,
    });

    if (!response.ok || !response.body) {
      const detail = await parseErrorResponse(response);
      throw new ApiError(detail, response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith("data:")) continue;

        const jsonStr = line.slice("data:".length).trim();
        if (!jsonStr) continue;

        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(jsonStr);
        } catch {
          continue;
        }

        if (typeof parsed.delta === "string") {
          onChunk(parsed.delta);
        } else if (parsed.tool_event) {
          onToolEvent?.(parsed);
        } else if (parsed.error) {
          finishWithError(new ApiError(String(parsed.error), 500));
        } else if (parsed.done) {
          // バックエンドが送出する "done" イベントは完了の目印に過ぎない。
          // 実際の処理完了は、下のwhileループを抜けてSSEのReadableStreamが
          // 完全に終了した時点（＝ /api/chat のレスポンスが本当に終わった時点）
          // でのみ判定するため、ここでは意図的に何もしない。
        }
      }
    }

    // ReadableStreamが完全に終了した時点（Tool Calling・最終回答のストリーミングを
    // 含め、/api/chat のSSEが本当に終了した時点）でのみ処理完了を通知する。
    finishWithDone();
  } catch (error) {
    if ((error as { name?: string }).name === "AbortError") {
      // ユーザーが中断ボタンを押した場合はここに来るが、UI状態の更新
      // （isSending=falseやメッセージの確定処理）は呼び出し元（page.tsx）が
      // AbortController.abort() 実行時に既に行っているため、ここでは
      // onDone/onErrorのどちらも呼ばず、通常の通信エラーとしても扱わない。
      return;
    }
    finishWithError(error instanceof Error ? error : new Error(String(error)));
  }
}

/**
 * 全セッション一覧を取得する。
 */
export async function listSessions(): Promise<SessionSummary[]> {
  return requestJson<SessionSummary[]>("/sessions", { method: "GET" });
}

/**
 * 指定セッションの会話履歴を取得する。
 */
export async function getSessionHistory(
  sessionId: string
): Promise<ChatMessage[]> {
  return requestJson<ChatMessage[]>(
    `/sessions/${encodeURIComponent(sessionId)}`,
    { method: "GET" }
  );
}

/**
 * 指定セッションを削除する。
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await requestJson(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

/**
 * 全ローカルデータをZIPファイルとしてエクスポートし、ブラウザでダウンロードさせる。
 */
export async function exportData(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/export`, { method: "GET" });
  if (!response.ok) {
    const detail = await parseErrorResponse(response);
    throw new ApiError(detail, response.status);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition");
  let filename = "tekika_export.zip";
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * アップロードされたZIPファイルからローカルデータをインポートする。
 */
export async function importData(file: File): Promise<{ status: string; source_file: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/import`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = await parseErrorResponse(response);
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as { status: string; source_file: string };
}

/**
 * 登録済みプラグイン一覧を取得する。
 */
export async function getPlugins(): Promise<PluginListResponse> {
  return requestJson<PluginListResponse>("/plugins", { method: "GET" });
}

/**
 * 新規プラグインコードを登録し、即座にホットロードさせる。
 */
export async function registerPlugin(
  pluginName: string,
  pythonCode: string
): Promise<PluginInfo> {
  return requestJson<PluginInfo>("/plugins", {
    method: "POST",
    body: JSON.stringify({
      plugin_name: pluginName,
      python_code: pythonCode,
    }),
  });
}

/**
 * 既存プラグインをホットリロードする。
 */
export async function reloadPlugin(pluginName: string): Promise<PluginInfo> {
  return requestJson<PluginInfo>(
    `/plugins/${encodeURIComponent(pluginName)}/reload`,
    { method: "POST" }
  );
}

/**
 * プラグインを削除する。
 */
export async function deletePlugin(pluginName: string): Promise<void> {
  await requestJson(`/plugins/${encodeURIComponent(pluginName)}`, {
    method: "DELETE",
  });
}

/**
 * バックエンドのヘルスチェック（Ollama接続状況を含む）を取得する。
 */
export async function getHealth(): Promise<{
  status: string;
  app_name: string;
  version: string;
  ollama_connected: boolean;
  agent_mode: string;
}> {
  return requestJson("/health", { method: "GET" });
}
