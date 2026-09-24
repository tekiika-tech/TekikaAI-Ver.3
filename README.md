# Tekika AI (Project Agency)

**あなたのPC上で動く、マルチLLM対応のプライベートAIエージェント。**
Ollama（ローカルLLM）に加えて OpenAI / Anthropic Claude / Google Gemini を切り替えて使え、
Gitリポジトリ操作・ファイル検索・OSエクスプローラー連携・ローカル画像生成・プラグインによる
自己拡張など、実務で使えるローカルツール群を備えています。

このREADMEは、Tekika AIの導入と日常利用に必要なユーザー向け説明書です。開発者向けの引き継ぎ情報は、ローカル専用の `AI_HANDOFF.md` に分離しています。

---

# ユーザー向け説明書

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
