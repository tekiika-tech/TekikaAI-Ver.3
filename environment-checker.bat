@echo off
chcp 932 >nul
setlocal EnableExtensions

title Tekika AI - Environment Checker

cd /d "%~dp0"

echo =========================================
echo       Tekika AI 環境チェック
echo =========================================
echo.
echo このプログラムは環境の確認のみを行います。
echo PythonやNode.jsなどの設定は変更しません。
echo.

set "ERROR_COUNT=0"

REM =========================================
REM 1. Python
REM =========================================
echo [1/5] Python
echo -----------------------------------------

py --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] Python Launcher (py) が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → Pythonをインストールしてください。' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    → インストール後、このチェッカーをもう一度実行してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] Python' -ForegroundColor Green"
    py --version
)

echo.


REM =========================================
REM 2. Python packages
REM =========================================
echo [2/5] Pythonパッケージ
echo -----------------------------------------

if not exist "%~dp0tekika-ai-backend\requirements.txt" (
    powershell -NoProfile -Command "Write-Host '[NG] requirements.txt が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → tekika-ai-backend フォルダーが正しく配置されているか確認してください。' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    → Tekika AIのソース一式を正しい場所に配置してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (

    py -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] FastAPI' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] FastAPI' -ForegroundColor Green"
    )

    py -c "import uvicorn" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Uvicorn' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Uvicorn' -ForegroundColor Green"
    )

    py -c "import pydantic" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pydantic' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pydantic' -ForegroundColor Green"
    )

    py -c "import pydantic_settings" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pydantic Settings' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pydantic Settings' -ForegroundColor Green"
    )

    py -c "import dotenv" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] python-dotenv' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] python-dotenv' -ForegroundColor Green"
    )

    py -c "import httpx" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] httpx' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] httpx' -ForegroundColor Green"
    )

    py -c "import git" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] GitPython' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] GitPython' -ForegroundColor Green"
    )

    py -c "import chromadb" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] ChromaDB' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] ChromaDB' -ForegroundColor Green"
    )

    py -c "from PIL import Image" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pillow' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pillow' -ForegroundColor Green"
    )

    py -c "import multipart" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] python-multipart' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Pythonパッケージが不足しています。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → requirements.txt の依存関係をインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] python-multipart' -ForegroundColor Green"
    )
)

echo.


REM =========================================
REM 3. Node.js / npm
REM =========================================
echo [3/5] Node.js / npm
echo -----------------------------------------

node --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] Node.js が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → Node.jsをインストールしてください。' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    → インストール後、このチェッカーをもう一度実行してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] Node.js' -ForegroundColor Green"
    node --version
)

call npm --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] npm が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → Node.jsをインストールするとnpmも利用できます。' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    → Node.jsのインストール後、このチェッカーをもう一度実行してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] npm' -ForegroundColor Green"
    call npm --version
)

echo.


REM =========================================
REM 4. Frontend
REM =========================================
echo [4/5] フロントエンド
echo -----------------------------------------

if not exist "%~dp0tekika-ai-frontend\package.json" (
    powershell -NoProfile -Command "Write-Host '[NG] package.json が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → tekika-ai-frontend フォルダーが正しく配置されているか確認してください。' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    → Tekika AIのフロントエンドファイルを正しい場所に配置してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] package.json' -ForegroundColor Green"

    if exist "%~dp0tekika-ai-frontend\node_modules" (
        powershell -NoProfile -Command "Write-Host '[OK] node_modules' -ForegroundColor Green"
    ) else (
        powershell -NoProfile -Command "Write-Host '[NG] node_modules がありません。' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → フロントエンドの依存パッケージがインストールされていません。' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    → tekika-ai-frontend フォルダーで npm install を実行してください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    )
)

echo.


REM =========================================
REM 5. Environment
REM =========================================
echo [5/7] 環境設定
echo -----------------------------------------

if not exist "%~dp0tekika-ai-backend\.env" (
    powershell -NoProfile -Command "Write-Host '[NG] .env が見つかりません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → tekika-ai-backend\.env.example を .env にコピーして設定してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] .env' -ForegroundColor Green"
)

if not exist "%~dp0tekika-ai-backend\.env.example" (
    powershell -NoProfile -Command "Write-Host '[NG] .env.example が見つかりません。' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] .env.example' -ForegroundColor Green"
)

set "LLM_PROVIDER="
if exist "%~dp0tekika-ai-backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"LLM_PROVIDER=" "%~dp0tekika-ai-backend\.env"`) do set "LLM_PROVIDER=%%B"
)

if not defined LLM_PROVIDER (
    powershell -NoProfile -Command "Write-Host '[NG] LLM_PROVIDER が設定されていません。' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    → .env に ollama / openai / claude / gemini のいずれかを設定してください。' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] LLM_PROVIDER = %LLM_PROVIDER%' -ForegroundColor Green"
)

if /I "%LLM_PROVIDER%"=="openai" call :check_key "OPENAI_API_KEY" "OpenAI"
if /I "%LLM_PROVIDER%"=="claude" call :check_key "ANTHROPIC_API_KEY" "Anthropic Claude"
if /I "%LLM_PROVIDER%"=="gemini" call :check_key "GOOGLE_API_KEY" "Google Gemini"

echo.

REM =========================================
REM 6. Ollama
REM =========================================
echo [6/7] Ollama
echo -----------------------------------------

if /I not "%LLM_PROVIDER%"=="ollama" (
    powershell -NoProfile -Command "Write-Host '[SKIP] LLM_PROVIDER がollamaではないため、Ollamaのチェックを省略します。' -ForegroundColor Yellow"
) else (
    py -c "import ollama" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Ollama Python Library' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Ollama Pythonライブラリが不足しています。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Ollama Python Library' -ForegroundColor Green"
    )

    ollama --version >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Ollama が見つかりません。' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    → Ollamaをインストールしてください。' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Ollama' -ForegroundColor Green"
        ollama --version

        echo.
        echo Ollamaサーバーへの接続を確認しています...

        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
        if errorlevel 1 (
            powershell -NoProfile -Command "Write-Host '[NG] Ollamaサーバーに接続できません。' -ForegroundColor Red"
            powershell -NoProfile -Command "Write-Host '    → Ollamaが起動しているか確認してください。' -ForegroundColor Yellow"
            set /a ERROR_COUNT+=1
        ) else (
            powershell -NoProfile -Command "Write-Host '[OK] Ollamaサーバーに接続できます。' -ForegroundColor Green"
        )

        echo.
        echo インストール済みモデル:
        ollama list
    )
)

echo.

REM =========================================
REM 7. Backend
REM =========================================
echo [7/7] バックエンド構成
echo -----------------------------------------

if exist "%~dp0tekika-ai-backend\backend\main.py" (
    powershell -NoProfile -Command "Write-Host '[OK] backend\main.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] backend\main.py が見つかりません。' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

if exist "%~dp0tekika-ai-backend\backend\agent\factory.py" (
    powershell -NoProfile -Command "Write-Host '[OK] agent\factory.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] agent\factory.py が見つかりません。' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

if exist "%~dp0tekika-ai-backend\backend\agent\orchestrator.py" (
    powershell -NoProfile -Command "Write-Host '[OK] agent\orchestrator.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] agent\orchestrator.py が見つかりません。' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

echo.



REM =========================================
REM Result
REM =========================================
echo =========================================
echo             チェック結果
echo =========================================
echo.

if "%ERROR_COUNT%"=="0" (
    powershell -NoProfile -Command "Write-Host '[OK] すべてのチェックに合格しました。' -ForegroundColor Green"
    echo.
    echo Tekika AIを起動可能です。
    echo start-tekika.bat を実行してください。
) else (
    powershell -NoProfile -Command "Write-Host '[NG] %ERROR_COUNT% 個の問題が見つかりました。' -ForegroundColor Red"
    echo.
    powershell -NoProfile -Command "Write-Host '上記の [NG] 項目と黄色の対処方法を確認してください。' -ForegroundColor Yellow"
)

echo.
echo =========================================
echo チェック終了
echo =========================================
echo.
echo Enterキーを押すと終了します。
echo.

pause
:check_key
set "CHECK_KEY="
if exist "%~dp0tekika-ai-backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"%~1=" "%~dp0tekika-ai-backend\.env"`) do set "CHECK_KEY=%%B"
)
if not defined CHECK_KEY (
    powershell -NoProfile -Command "Write-Host '[NG] %~2 のAPIキー (%~1) が未設定または空欄です。' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] %~2 APIキーが設定されています。' -ForegroundColor Green"
)
exit /b
