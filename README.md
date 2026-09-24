# Tekika AI (Project Agency)

**あなたのPC上で動く、マルチLLM対応のプライベートAIエージェント。**
Ollama（ローカルLLM）に加えて OpenAI / Anthropic Claude / Google Gemini を切り替えて使え、
Gitリポジトリ操作・ファイル検索・OSエクスプローラー連携・ローカル画像生成・プラグインによる
自己拡張など、実務で使えるローカルツール群を備えています。

このREADMEは2部構成です。

- **Part 1: ユーザー＆管理者向け 実用・操作マニュアル** — 導入し、実際に使うための手順。
- **Part 2: AI＆開発者向け 開発引き継ぎ・仕様書** — コードベースを理解し、拡張するための設計解説。

---

# Part 1: ユーザー＆管理者向け 実用・操作マニュアル

## 1. Tekika AIとは

Tekika AI（Project Agency）は、外部クラウドサービスへの常時接続を前提としない、**自分のPCで完結するAIアシスタント**です。次のような使い方を想定しています。

- **ローカルLLM（Ollama）だけで完全オフライン運用** — 機密性の高い作業やコストをかけたくない用途に。
- **必要に応じてOpenAI / Claude / Geminiに切り替え** — より高精度な応答や長い文脈が必要な場面に。
- **手元のGitリポジトリの状態確認・ファイル編集・コミット** を自然な日本語の指示で実行。
- **「〇〇のファイルを探して」「エクスプローラーで開いて」** といった指示でローカルファイル操作。
- **画像生成**（Stable Diffusion WebUIと連携、未起動時はプレースホルダー画像で代替）。
- **プラグインによる自己拡張** — AI自身に新しいツール（Pythonコード）を生成・登録させることも可能。
- 会話履歴・長期記憶は**すべて手元のSQLite/ChromaDBに保存**され、ZIPで丸ごとエクスポート/インポートできます。

どのLLMプロバイダを使う場合も、Gitツールやファイル検索などのローカルツールは共通して使えます。

## 2. 動作要件 & 事前準備

| 項目 | 要件 |
|---|---|
| OS | Windows 10/11、または Linux / macOS |
| Python | 3.10 以上（3.11〜3.12推奨） |
| Node.js | 18.17 以上（フロントエンド用） |
| Git | ローカルGitツールを使う場合に必要 |

**プロバイダ別の追加要件:**

- **Ollama**（既定・APIキー不要）: [ollama.com](https://ollama.com) からインストールし、`ollama pull qwen2.5` 等でモデルを取得しておく。
- **OpenAI**: [platform.openai.com](https://platform.openai.com/api-keys) でAPIキーを取得。
- **Anthropic Claude**: [console.anthropic.com](https://console.anthropic.com/settings/keys) でAPIキーを取得。
- **Google Gemini**: [aistudio.google.com](https://aistudio.google.com/app/apikey) でAPIキーを取得。

APIキーが必要なのは、そのプロバイダを**実際に使う場合のみ**です。Ollamaのみで使う場合、クラウドAPIキーは一切不要です。

## 3. インストール & セットアップ手順

### 3.1 バックエンド

Windowsでは、プロジェクトルートの `setup-tekika.bat` を実行すると、Python依存関係・フロントエンド依存関係・`.env` 初期化・データディレクトリ作成をまとめて行えます。既存の `.env` は上書きしません。

手動でセットアップする場合は次のとおりです。Windowsでは `python` ではなく `py` を使用できます。

```bash
cd tekika-ai-backend
py -m venv .venv

# 仮想環境の有効化
.venv\Scripts\activate        # Windows
source .venv/bin/activate        # macOS / Linux

py -m pip install -r requirements.txt
```

`.env.example` をコピーして `.env` を作成し、使いたいプロバイダの設定を記入します。

```bash
cp .env.example .env        # macOS/Linux
copy .env.example .env      # Windows
```

`.env` の主要項目:

```dotenv
# 使用するプロバイダ: ollama / openai / claude / gemini
LLM_PROVIDER=ollama

# Ollamaのみ使う場合、以下はそのままでOK
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:latest

# OpenAIを使う場合のみ記入
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-4o-mini

# Claudeを使う場合のみ記入
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_DEFAULT_MODEL=claude-sonnet-4-5

# Geminiを使う場合のみ記入
GOOGLE_API_KEY=AIza...
GEMINI_DEFAULT_MODEL=gemini-2.0-flash
```

> **複数プロバイダを同時に設定可能です。** `.env` に複数のAPIキーを記入しておけば、起動時にすべて初期化され、リクエストごとに `provider` パラメータで切り替えられます（後述）。`LLM_PROVIDER` は「指定なし時に使う既定プロバイダ」です。

### 3.2 フロントエンド

```bash
cd tekika-ai-frontend
npm install
```

### 3.3 ワンクリック起動（Windows）

プロジェクトルートの `start-tekika.bat` を実行すると、バックエンド（ポート8000）とフロントエンド（ポート3000）が別ウィンドウで立ち上がり、準備完了後に自動でブラウザが開きます。

`environment-checker.bat` / `environment-checker-en.bat` で、Python・必要なPython SDK・Node.js・npm・設定ファイル・現在のLLMプロバイダを確認できます。Ollamaは `LLM_PROVIDER=ollama` の場合のみ必須としてチェックされ、OpenAI / Claude / Geminiでは対応するAPIキーの設定を確認します。Stable Diffusion WebUIは任意機能として警告扱いです。

> **配布について:** `.env` にはAPIキーが含まれる可能性があるため、配布ZIPには絶対に含めません。配布用ZIPは `make-distribution-zip.bat` で作成してください。`node_modules`、`.next`、DB、ChromaDB、Pythonキャッシュ等も自動除外されます。配布先では `setup-tekika.bat` を実行して依存関係を再構築します。

## 4. 起動方法と実際の使い方

### 4.1 手動起動

```bash
# ターミナル1: バックエンド
cd tekika-ai-backend
python -m uvicorn backend.main:app --port 8000

# ターミナル2: フロントエンド
cd tekika-ai-frontend
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。

### 4.2 Web画面からの操作

- **サイドバー**でモデルの動作モード（Quality Priority / Speed Priority）を切り替えられます。
  - **Quality**: 思考→ツール実行→結果統合のループを行い、必要に応じてローカルツールを自動実行します。
  - **Speed**: ツールを使わず単発で高速に応答します。
- **設定ダイアログ**でOllamaのモデル名を変更したり、プラグインを登録・管理できます。
- チャット欄で「`C:\Projects\myapp` の状態を教えて」のように話しかけると、Gitツールが自動実行されます。
- 応答中にローカルパスが含まれると、「パスをコピー」「エクスプローラーで開く」ボタンが表示されます。
- サイドバーの「全データをエクスポート」「データをインポート」で、会話履歴・長期記憶をZIPごと保存・復元できます。

### 4.3 モデル（プロバイダ）の切り替え

`GET /api/providers` で現在利用可能なプロバイダの一覧（APIキーが設定されているもの）を取得できます。

```bash
curl http://localhost:8000/api/providers
```

```json
[
  {"provider": "ollama", "default_model": "qwen2.5:latest", "is_default": true},
  {"provider": "openai", "default_model": "gpt-4o-mini", "is_default": false}
]
```

チャットAPIを直接呼ぶ場合、`provider` を指定すればリクエストごとに切り替えられます（フロントエンドのモデル選択UIに組み込む際の拡張ポイントです。現バージョンのUIは既定プロバイダのみを使用します）。

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "こんにちは", "provider": "openai", "mode": "QUALITY"}'
```

### 4.4 ツールの自動実行の例

| 話しかけ方の例 | 実行されるツール |
|---|---|
| 「`D:\repo` の状態を見せて」 | `get_repo_status`（Git） |
| 「`D:\repo` の変更をコミットして」 | `commit_and_branch`（Git） |
| 「デスクトップから `report` という名前のファイルを探して」 | `search_files` |
| 「そのフォルダをエクスプローラーで開いて」 | `open_in_explorer` |
| 「猫のイラストを生成して」 | `generate_image`（画像生成） |

## 5. よくあるトラブルシューティング

**Q. 「ローカルOllamaサーバに接続できません」と出る**
A. `ollama serve` が起動しているか確認してください。`.env` の `OLLAMA_BASE_URL` がOllamaの実際の待受アドレスと一致しているかも確認してください。

**Q. 応答がタイムアウトする / 途中で止まる**
A. `.env` の `OLLAMA_REQUEST_TIMEOUT`（Ollama用）や `OPENAI_REQUEST_TIMEOUT` 等は、コメントアウトして未設定にすると無制限になります。`KEY=` のような空文字を明示すると、設定項目によっては型変換エラーになるため、無制限にしたい場合は行全体を `#` でコメントアウトしてください。大きなローカルモデルは応答に数分かかることがあるため、既定では無制限設定です。逆に長時間ハングしている場合は、秒数を指定して上限を設けてください。

**Q. 「OPENAI_API_KEY が設定されていません」等のエラーが出る**
A. そのプロバイダを使うには `.env` に対応するAPIキーが必要です。未設定のプロバイダは自動的にスキップされ、起動ログに一覧が出力されます。`LLM_PROVIDER` の値と実際に設定したキーが一致しているか確認してください。

**Q. プロバイダを切り替えたのに反映されない**
A. `.env` を編集した後は、バックエンドプロセスの再起動が必要です（環境変数はプロセス起動時に読み込まれます）。

**Q. 画像生成が「プレースホルダー画像」になる**
A. Stable Diffusion WebUI（AUTOMATIC1111等）が `SD_WEBUI_BASE_URL`（既定: `http://localhost:7860`）で起動していない場合、自動的にPillow製のプレースホルダー画像にフォールバックします。実際の画像生成にはWebUIの起動が必要です。

**Q. `npm run dev` がエラーで起動しない**
A. Node.js が18.17以上か確認してください（`node -v`）。`tekika-ai-frontend` ディレクトリで `npm install` をやり直すと解決することが多いです。

---

# Part 2: AI＆開発者向け 作業引き継ぎ・開発仕様書

このセクションは、次にこのリポジトリを引き継ぐ人間の開発者、またはCursor / Claude Code等のAIコーディングエージェントが、コードベースを素早く理解し安全に拡張できるようにするための設計ドキュメントです。

## 1. 全体アーキテクチャ

```
[ Web UI (Next.js) ]
        │  fetch / SSE
        ▼
[ FastAPI (backend/main.py) ]
        │
        ▼
[ AgentOrchestrator (backend/agent/orchestrator.py) ]
        │           │
        │           └─ MemoryStore (backend/agent/memory.py)
        │                  ├─ SQLite: 会話履歴・プロファイル・設定
        │                  └─ ChromaDB: 長期記憶（ベクトル検索）
        │
        ▼
[ BaseLLMClient 実装 (backend/agent/providers/*.py) ]
        ├─ OllamaProvider  (ローカル, httpx直接)
        ├─ OpenAIProvider  (AsyncOpenAI)
        ├─ ClaudeProvider  (AsyncAnthropic)
        └─ GeminiProvider  (google-genai)
        │
        ▼
[ ローカルツール群 (backend/tools/*.py) ]
        ├─ LocalGitTool          : Git操作
        ├─ FileSystemTool        : ファイル検索・一覧・エクスプローラー連携
        ├─ LocalImageGenerator   : 画像生成 (SD WebUI / Pillowフォールバック)
        └─ PluginLoader          : プラグイン動的ロード・自己アップデート
```

**データフロー（Quality Modeの場合）:**

1. `POST /api/chat` がリクエストを受け取る（`backend/main.py`）。
2. `AgentOrchestrator.handle_user_message()` / `stream_user_message()` が呼ばれる。
3. `orchestrator.get_client(provider)` で、リクエスト指定 or `.env` の `LLM_PROVIDER` に従い `BaseLLMClient` 実装を選択する。
4. `client.run_tool_calling_loop()`（`base_client.py` に共通実装）が、思考→ツール実行→結果統合のループを回す。
5. ループ中に呼ばれたツールは `orchestrator.tool_registry` から実行され、結果がメッセージ履歴に追記される。
6. 最終応答が `MemoryStore` に保存され、レスポンスとして返る。

## 2. 各主要ファイル・ディレクトリの役割

| パス | 役割 |
|---|---|
| `backend/main.py` | FastAPIエントリポイント。ライフサイクル管理、全APIエンドポイント定義。 |
| `backend/config.py` | `.env` から読み込む全設定値（`Settings`）。プロバイダ別APIキー・モデル名等。 |
| `backend/agent/base_client.py` | 全プロバイダ共通の抽象基底クラス `BaseLLMClient`、共通データ構造、Tool Callingループの共通実装。 |
| `backend/agent/factory.py` | `.env` の設定に基づき `BaseLLMClient` 実装を動的生成する `LLMFactory`。 |
| `backend/agent/providers/ollama_provider.py` | Ollama用実装（httpxで直接 `/api/chat` を叩く）。 |
| `backend/agent/providers/openai_provider.py` | OpenAI Chat Completions API用実装。 |
| `backend/agent/providers/claude_provider.py` | Anthropic Messages API用実装（tool_use/tool_result変換を内包）。 |
| `backend/agent/providers/gemini_provider.py` | Google Gemini API用実装（function_call/function_response変換を内包）。 |
| `backend/agent/orchestrator.py` | `AgentOrchestrator`。複数クライアント・メモリ・ツールを統括。 |
| `backend/agent/memory.py` | `MemoryStore`。SQLite会話履歴 + ChromaDB長期記憶 + ZIPエクスポート/インポート。 |
| `backend/tools/git_tool.py` | `LocalGitTool`。ローカルGitリポジトリ操作。 |
| `backend/tools/file_system_tool.py` | `FileSystemTool`。ファイル検索・一覧取得・OSエクスプローラー連携。 |
| `backend/tools/image_gen_tool.py` | `LocalImageGenerator`。SD WebUI連携 + Pillowフォールバック。 |
| `backend/tools/plugin_loader.py` | `PluginLoader`。`/plugins` 配下の動的ロード・AI自己アップデート基盤。 |
| `tekika-ai-frontend/src/lib/api.ts` | バックエンドAPIクライアント（SSEストリーミング含む）。 |
| `tekika-ai-frontend/src/components/*.tsx` | Sidebar / ChatWindow / MessageItem / SettingsModal 各UIコンポーネント。 |

## 3. LLMプロバイダ抽象化と Tool Calling ループの仕組み

### 3.1 正準メッセージフォーマット

`orchestrator.py` を含むアプリ全体は、**OpenAI Chat Completions互換の正準フォーマット**でメッセージをやり取りします。

```python
{"role": "system" | "user" | "assistant" | "tool", "content": str, ...}
```

`assistant` がツールを呼ぶ場合は `tool_calls` キーを持ち、その形式もOpenAI互換です:

```python
{"role": "assistant", "content": "", "tool_calls": [
    {"id": "call_1", "function": {"name": "search_files", "arguments": {"base_path": "...", "keyword": "..."}}}
]}
```

ツール実行結果は `role: "tool"` として返します（`base_client.ToolCallResult.to_message()` が生成）:

```python
{"role": "tool", "tool_call_id": "call_1", "name": "search_files", "content": "[...]"}
```

### 3.2 各プロバイダでの変換

| プロバイダ | 正準フォーマットとの主な違い | 変換箇所 |
|---|---|---|
| Ollama | ほぼ同一（OpenAI互換のtools形式をそのまま受理） | 変換不要 |
| OpenAI | ほぼ同一 | 変換不要（`tool_calls` の型変換のみ） |
| Claude | `system` はトップレベル引数。ツール定義は `input_schema` 形式。ツール呼び出しは `content` 内の `tool_use` ブロック、結果は `tool_result` ブロック。 | `ClaudeProvider._split_system_and_messages()` / `_convert_tools()` / `_normalize_response_content()` |
| Gemini | ロール名が `user`/`model`。`system` は `system_instruction`。ツール呼び出しは `function_call` Part、結果は `function_response` Part。明示的なtool_call IDが無いため関数名で代用。 | `GeminiProvider._convert_messages()` / `_convert_tools()` / `_normalize_response()` |

**新しいプロバイダを追加する際は、この変換ロジックだけを書けば済みます。** `chat()` が正準フォーマットの `ChatResponse`（`content` + `tool_calls`）を返す限り、`run_tool_calling_loop()` は一切変更不要です。

### 3.3 Tool Callingループの流れ（`base_client.py: BaseLLMClient.run_tool_calling_loop`）

```
while 反復回数 < max_iterations:
    1. client.chat(messages, tools=tool_schemas) を呼ぶ
    2. 応答を assistant メッセージとして履歴に追加
    3. tool_calls が無ければ終了（最終回答とみなす）
    4. tool_calls があれば、各ツールを実行し、
       結果を role="tool" メッセージとして履歴に追加
    5. 1に戻る
```

最大反復回数（既定8回、`.env` の `OLLAMA_MAX_TOOL_ITERATIONS`）に達した場合は、その時点までの履歴を返して打ち切ります（無限ループ防止）。

## 4. 拡張ガイド（Step-by-Step）

### 4.1 新しいAIプロバイダを追加する手順

1. `backend/agent/providers/<name>_provider.py` を作成し、`BaseLLMClient` を継承したクラスを実装する。
   - `provider_name` クラス変数を設定する。
   - `health_check()` / `chat()` / `stream_chat()` を実装する（`chat()` は必ず正準フォーマットの `ChatResponse` を返すこと）。
   - 正準フォーマット ⇔ プロバイダ固有形式の変換関数を内部に持つ（`_convert_messages` / `_convert_tools` / `_normalize_response` 等、既存プロバイダの命名規則に合わせる）。
2. `backend/config.py` に、そのプロバイダ用の設定項目（`<NAME>_API_KEY`, `<NAME>_DEFAULT_MODEL` 等）を追加する。
3. `backend/agent/factory.py` の `SUPPORTED_PROVIDERS` に識別子を追加し、`LLMFactory.create_client()` に分岐を追加する。
4. `.env.example` に設定例とAPIキー取得先URLを追記する。
5. 必要なSDKを `requirements.txt` に追加する。

これだけで `orchestrator.py` や `main.py` の変更は一切不要です（`LLMFactory.create_available_clients()` が自動的に検出します）。

### 4.2 新しいツール（Tool）を追加・登録する手順

1. `backend/tools/<name>_tool.py` に、ツールクラスとメソッドを実装する。
   - 各メソッドには**型ヒントとdocstring**を必ず付ける（`function_to_tool_schema()` がこれらからJSON Schemaを自動生成するため）。
   - 例外は専用の例外クラス（`<Name>ToolError` 等）で送出する。
2. `backend/main.py` の `lifespan()` 内で、ツールインスタンスを生成し、
   `orchestrator.register_tool(instance.method, "説明文")` で登録する。
3. （任意）そのツールをREST APIからも直接呼べるようにしたい場合、`main.py` にエンドポイントを追加する。
4. AIがツールを自然言語から呼び出せるよう、登録時の説明文に「ユーザーが『〇〇して』と言った場合に使う」のような具体例を含めると、Tool Callingの精度が上がる。

**AIが自分自身で新ツールを追加する場合**は、上記の代わりに `PluginLoader.register_new_plugin(plugin_name, python_code)`（`POST /api/plugins`）を使い、`/plugins` フォルダにPythonファイルとして保存・即時ホットロードさせる方式を使う（これは意図的にサンドボックス外の自己拡張機構として分離されている）。

## 5. AI向け開発・改修ルール (AI Agent Rules)

このリポジトリを改修するAIコーディングエージェント（Cursor / Claude Code 等）は、以下を遵守してください。

1. **非同期処理は必ず `async/await` を徹底する。** `BaseLLMClient` のメソッドはすべて非同期であり、同期的なブロッキング呼び出し（同期HTTPクライアント等）を混在させない。
2. **通信タイムアウトの扱いに注意する。** ローカルの重いモデル（Ollama）は応答に数分かかることがあるため、`.env` の `*_REQUEST_TIMEOUT` が空欄（`None`）の場合はタイムアウト無制限として扱う設計になっている。この挙動を安易に固定秒数へ変更しないこと。変更する場合は既定値をNone（無制限）のまま維持し、必要なら値の**上限**だけを追加する。
3. **正準メッセージフォーマットを崩さない。** 新しいプロバイダやツールを追加する際も、`orchestrator.py` に渡す/受け取るメッセージは必ずOpenAI互換の正準フォーマットに従うこと。プロバイダ固有の形式変換は、そのプロバイダの実装ファイル内に閉じ込める。
4. **ツール関数は副作用の説明をdocstringに明記する。** Tool Callingの精度はdocstringの質に直結するため、「何をするか」「いつ使うべきか」を具体的に書く。
5. **パス操作を伴うツールは必ずセキュリティ検証を通す。** `FileSystemTool` のように、パストラバーサル・OSコマンドインジェクション対策（`subprocess` は常に引数リスト・`shell=False`）を徹底する。
6. **APIキー等の秘密情報を絶対にコードやログに直書きしない。** 常に `.env` 経由で読み込み、`.env` はGit管理対象外（`.gitignore`）とする。
7. **既存のマスターによるカスタマイズを尊重する。** `OllamaProvider` のタイムアウト無効化ロジックや `main.py` の `execution_time` 計測など、マスターが独自に加えた改善は、リファクタリング時も機能として保持すること。
8. **新規プロバイダ・新規ツールを追加したら、必ずこのREADMEのPart 2（該当セクション）を更新する。** ドキュメントとコードの乖離は、次に引き継ぐAI/開発者の生産性を大きく損なう。

---

## 変更履歴（マルチプロバイダ化）

- `backend/agent/ollama_client.py` を新しい実行経路から分離し、`backend/agent/base_client.py`（抽象インターフェース）と
  `backend/agent/providers/ollama_provider.py`（Ollama実装）を中心とした構成へ移行。
- `backend/agent/providers/{openai,claude,gemini}_provider.py` を新規追加。
- `backend/agent/factory.py`（`LLMFactory`）を新規追加。`.env` のAPIキー設定に応じて利用可能なプロバイダを自動検出する。
- `backend/agent/orchestrator.py` を `BaseLLMClient` インターフェース経由で動作するよう変更。
  単一の `ollama_client` ではなく `clients: Dict[str, BaseLLMClient]` を保持し、リクエストごとに `provider` で切り替え可能に。
- `backend/main.py` に `GET /api/providers`（利用可能プロバイダ一覧）を追加。`POST /api/chat` に `provider` パラメータを追加。
- `backend/config.py` に `LLM_PROVIDER` / `LLM_TEMPERATURE` / 各プロバイダのAPIキー・モデル設定を追加。
