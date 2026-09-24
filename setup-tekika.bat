@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Tekika AI - Setup
cd /d "%~dp0"

set "BACKEND_DIR=%~dp0tekika-ai-backend"
set "FRONTEND_DIR=%~dp0tekika-ai-frontend"

echo =========================================
echo        Tekika AI セットアップ
echo =========================================
echo.
echo この処理は依存関係をインストールし、必要な初期ファイルを作成します。
echo 既存の .env は上書きしません。
echo.

py --version >nul 2>&1
if errorlevel 1 (
    echo [NG] Python Launcher (py) が見つかりません。
    echo     Python 3.10以上をインストールしてから再実行してください。
    pause
    exit /b 1
)
py -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [NG] Python 3.10以上が必要です。
    pause
    exit /b 1
)
echo [OK] Python

echo.
echo [1/3] Python依存関係をインストールしています...
cd /d "%BACKEND_DIR%"
py -m pip install --upgrade pip
if errorlevel 1 (
    echo [NG] pipの更新に失敗しました。
    pause
    exit /b 1
)
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo [NG] Python依存関係のインストールに失敗しました。
    pause
    exit /b 1
)
echo [OK] Python dependencies

if not exist ".env" (
    if not exist ".env.example" (
        echo [NG] .env.example が見つかりません。
        pause
        exit /b 1
    )
    copy /Y ".env.example" ".env" >nul
    echo [OK] .env を .env.example から作成しました。
    echo     クラウドLLMを使用する場合は .env にAPIキーを設定してください。
) else (
    echo [OK] 既存の .env を保持しました。
)

echo.
echo [2/3] Node.js / npm を確認しています...
cd /d "%FRONTEND_DIR%"
node --version >nul 2>&1
if errorlevel 1 (
    echo [NG] Node.js が見つかりません。Node.js 18.17以上をインストールしてください。
    pause
    exit /b 1
)
node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0]>18 || (v[0]===18 && v[1]>=17) ? 0 : 1)"
if errorlevel 1 (
    echo [NG] Node.js 18.17以上が必要です。
    pause
    exit /b 1
)
npm --version >nul 2>&1
if errorlevel 1 (
    echo [NG] npm が見つかりません。
    pause
    exit /b 1
)
echo [OK] Node.js / npm
npm install
if errorlevel 1 (
    echo [NG] npm install に失敗しました。
    pause
    exit /b 1
)
echo [OK] Frontend dependencies

echo.
echo [3/3] データディレクトリを初期化しています...
cd /d "%BACKEND_DIR%"
if not exist "data" mkdir "data"
if not exist "data\exports" mkdir "data\exports"
if not exist "data\images" mkdir "data\images"
if not exist "data\chroma" mkdir "data\chroma"
if not exist "plugins" mkdir "plugins"
echo [OK] Backend data directories

echo.
echo =========================================
echo          セットアップ完了
echo =========================================
echo.
echo 次に environment-checker.bat を実行してください。
echo Ollamaを使用する場合は、Ollamaを起動して必要なモデルを取得してください。
echo.
pause
