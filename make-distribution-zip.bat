@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Tekika AI - Distribution ZIP Creator
cd /d "%~dp0"

echo =========================================
echo     Tekika AI 配布用ZIP作成ツール
echo =========================================
echo.
echo 配布用ZIPを作成します。
echo.
echo 除外対象:
echo   - .env / APIキーを含む設定ファイル
echo   - node_modules / .next
echo   - Python仮想環境 / __pycache__
echo   - DB / SQLite / ChromaDB / ログ / キャッシュ
echo   - Git管理情報
echo.

set "PROJECT_DIR=%~dp0"
set "TEMP_DIR=%TEMP%\TekikaAI_Distribution_%RANDOM%_%RANDOM%"
set "ZIP_NAME=TekikaAI-Distribution.zip"
set "ZIP_PATH=%PROJECT_DIR%%ZIP_NAME%"

mkdir "%TEMP_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [NG] 一時フォルダを作成できませんでした。
    pause
    exit /b 1
)

robocopy "%PROJECT_DIR%" "%TEMP_DIR%" /E ^
    /XD ^
        "%PROJECT_DIR%.git" ^
        "%PROJECT_DIR%.venv" ^
        "%PROJECT_DIR%venv" ^
        "%PROJECT_DIR%node_modules" ^
        "%PROJECT_DIR%.next" ^
        "%PROJECT_DIR%dist" ^
        "%PROJECT_DIR%build" ^
        "%PROJECT_DIR%__pycache__" ^
        "%PROJECT_DIR%tekika-ai-backend\.venv" ^
        "%PROJECT_DIR%tekika-ai-backend\venv" ^
        "%PROJECT_DIR%tekika-ai-backend\__pycache__" ^
        "%PROJECT_DIR%tekika-ai-backend\data" ^
        "%PROJECT_DIR%tekika-ai-backend\tekika-ai-backend" ^
        "%PROJECT_DIR%tekika-ai-frontend\node_modules" ^
        "%PROJECT_DIR%tekika-ai-frontend\.next" ^
        "%PROJECT_DIR%tekika-ai-frontend\dist" ^
        "%PROJECT_DIR%tekika-ai-frontend\build" ^
    /XF ^
        "%ZIP_NAME%" ^
        "TekikaAI-source.zip" ^
        ".env" ^
        ".env.*" ^
        "*.db" ^
        "*.sqlite" ^
        "*.sqlite3" ^
        "*.log" ^
        "*.pyc" ^
    /R:1 /W:1 /NFL /NDL /NJH /NJS

if errorlevel 8 (
    echo [NG] ファイルのコピー中にエラーが発生しました。
    rmdir /s /q "%TEMP_DIR%" >nul 2>&1
    pause
    exit /b 1
)

REM .env.example は配布対象。robocopyの拡張子除外には含めない。
if not exist "%TEMP_DIR%\tekika-ai-backend" mkdir "%TEMP_DIR%\tekika-ai-backend"
copy /Y "%PROJECT_DIR%tekika-ai-backend\.env.example" "%TEMP_DIR%\tekika-ai-backend\.env.example" >nul
if errorlevel 1 (
    echo [NG] .env.example のコピーに失敗しました。
    rmdir /s /q "%TEMP_DIR%" >nul 2>&1
    pause
    exit /b 1
)

if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%" >nul 2>&1
powershell -NoProfile -Command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo [NG] ZIPファイルの作成に失敗しました。
    rmdir /s /q "%TEMP_DIR%" >nul 2>&1
    pause
    exit /b 1
)

rmdir /s /q "%TEMP_DIR%" >nul 2>&1

echo.
echo =========================================
echo              作成完了
echo =========================================
echo.
echo 配布用ZIP:
echo %ZIP_PATH%
echo.
powershell -NoProfile -Command "if (Test-Path '%ZIP_PATH%') { $size=(Get-Item '%ZIP_PATH%').Length / 1MB; Write-Host ('ZIP Size: {0:N2} MB' -f $size) -ForegroundColor Green }"
echo.
echo 配布ZIPには .env、node_modules、.next、DB、仮想環境は含まれません。
echo.
pause
