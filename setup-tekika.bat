@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Tekika AI - Setup
cd /d "%~dp0"

set "BACKEND_DIR=%~dp0tekika-ai-backend"
set "FRONTEND_DIR=%~dp0tekika-ai-frontend"
set "OLLAMA_URL=https://ollama.com/download/windows"
set "OLLAMA_PS=irm https://ollama.com/install.ps1 | iex"

rem Enable ANSI colors in modern Windows consoles.
for /F "delims=" %%A in ('echo prompt $E^| cmd') do set "ESC=%%A"

set "C_RESET=!ESC![0m"
set "C_DIM=!ESC![90m"
set "C_BLUE=!ESC![94m"
set "C_CYAN=!ESC![96m"
set "C_GREEN=!ESC![92m"
set "C_YELLOW=!ESC![93m"
set "C_RED=!ESC![91m"
set "C_WHITE=!ESC![97m"

cls
echo.
echo !C_CYAN!============================================================!C_RESET!
echo !C_WHITE!                       TEKIKA AI SETUP!C_RESET!
echo !C_CYAN!============================================================!C_RESET!
echo.
echo !C_DIM!This setup installs project dependencies and creates the
echo required local data directories.!C_RESET!
echo.

if not exist "%BACKEND_DIR%\." (
    echo !C_RED![ERROR] Backend directory not found:!C_RESET!
    echo         %BACKEND_DIR%
    echo.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\." (
    echo !C_RED![ERROR] Frontend directory not found:!C_RESET!
    echo         %FRONTEND_DIR%
    echo.
    pause
    exit /b 1
)

rem ================================================================
rem [1/4] Python
rem ================================================================
echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![1/4] Python environment!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

py --version >nul 2>&1
if errorlevel 1 (
    echo !C_RED![ERROR] Python Launcher "py" was not found.!C_RESET!
    echo.
    echo !C_YELLOW!Please install Python 3.10 or newer, then run this setup again.!C_RESET!
    echo.
    pause
    exit /b 1
)

py -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo !C_RED![ERROR] Python 3.10 or newer is required.!C_RESET!
    py --version
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('py --version 2^>^&1') do set "PY_VERSION=%%V"
echo !C_GREEN![OK] !C_RESET!!PY_VERSION!

cd /d "%BACKEND_DIR%"

echo.
echo !C_CYAN!Updating pip...!C_RESET!
py -m pip install --upgrade pip --progress-bar on
if errorlevel 1 (
    echo.
    echo !C_RED![ERROR] Failed to update pip.!C_RESET!
    pause
    exit /b 1
)

echo.
echo !C_CYAN!Installing Python dependencies...!C_RESET!
py -m pip install -r requirements.txt --progress-bar on
if errorlevel 1 (
    echo.
    echo !C_RED![ERROR] Failed to install Python dependencies.!C_RESET!
    pause
    exit /b 1
)

echo.
echo !C_GREEN![OK] Python dependencies installed.!C_RESET!

rem ================================================================
rem .env
rem ================================================================
echo.
if not exist ".env" (
    if not exist ".env.example" (
        echo !C_RED![ERROR] .env.example was not found.!C_RESET!
        pause
        exit /b 1
    )
    copy /Y ".env.example" ".env" >nul
    echo !C_GREEN![OK] Created .env from .env.example.!C_RESET!
    echo !C_YELLOW!     Edit .env if you need to configure a cloud LLM API key.!C_RESET!
) else (
    echo !C_GREEN![OK] Existing .env preserved.!C_RESET!
)

rem ================================================================
rem [2/4] Node.js / npm
rem ================================================================
echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![2/4] Node.js / npm environment!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

node --version >nul 2>&1
if errorlevel 1 (
    echo !C_RED![ERROR] Node.js was not found.!C_RESET!
    echo !C_YELLOW!Please install Node.js 18.17 or newer, then run this setup again.!C_RESET!
    echo.
    pause
    exit /b 1
)

node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0]>18 || (v[0]===18 && v[1]>=17) ? 0 : 1)"
if errorlevel 1 (
    echo !C_RED![ERROR] Node.js 18.17 or newer is required.!C_RESET!
    node --version
    echo.
    pause
    exit /b 1
)

npm --version >nul 2>&1
if errorlevel 1 (
    echo !C_RED![ERROR] npm was not found.!C_RESET!
    pause
    exit /b 1
)

for /f "delims=" %%V in ('node --version') do set "NODE_VERSION=%%V"
for /f "delims=" %%V in ('npm --version') do set "NPM_VERSION=%%V"

echo !C_GREEN![OK] !C_RESET!Node.js !NODE_VERSION! / npm !NPM_VERSION!

cd /d "%FRONTEND_DIR%"

echo.
echo !C_CYAN!Installing frontend dependencies...!C_RESET!
npm install --progress=true
if errorlevel 1 (
    echo.
    echo !C_RED![ERROR] npm install failed.!C_RESET!
    pause
    exit /b 1
)

echo.
echo !C_GREEN![OK] Frontend dependencies installed.!C_RESET!

rem ================================================================
rem [3/4] Backend directories
rem ================================================================
echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![3/4] Backend data directories!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

cd /d "%BACKEND_DIR%"

if not exist "data" mkdir "data"
if not exist "data\exports" mkdir "data\exports"
if not exist "data\images" mkdir "data\images"
if not exist "data\chroma" mkdir "data\chroma"
if not exist "plugins" mkdir "plugins"

echo !C_GREEN![OK] Backend data directories are ready.!C_RESET!

rem ================================================================
rem [4/4] Ollama - user controlled
rem ================================================================
echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![4/4] Ollama (optional / user controlled)!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.
echo !C_DIM!Ollama is NOT installed automatically.!C_RESET!
echo !C_DIM!Choose how you want to install it, or skip it for now.!C_RESET!
echo.
echo !C_WHITE![1]!C_RESET! Open the official Ollama download page
echo !C_WHITE![2]!C_RESET! Show the official PowerShell install command
echo !C_WHITE![3]!C_RESET! Skip Ollama setup
echo.

set "OLLAMA_CHOICE="
set /p "OLLAMA_CHOICE=Select [1-3]: "

if "!OLLAMA_CHOICE!"=="1" (
    echo.
    echo !C_CYAN!Opening the official Ollama download page...!C_RESET!
    start "" "%OLLAMA_URL%"
    echo !C_GREEN![OK] Browser opened.!C_RESET!
    echo !C_DIM!Install Ollama manually from the official page.!C_RESET!
) else if "!OLLAMA_CHOICE!"=="2" (
    echo.
    echo !C_WHITE!PowerShell command:!C_RESET!
    echo.
    echo !C_YELLOW!!OLLAMA_PS!!C_RESET!
    echo.
    echo !C_DIM!The command above is only displayed. This setup does not execute it.!C_RESET!
) else if "!OLLAMA_CHOICE!"=="3" (
    echo.
    echo !C_YELLOW![SKIP] Ollama setup skipped.!C_RESET!
) else (
    echo.
    echo !C_YELLOW![SKIP] Invalid selection. Ollama setup skipped.!C_RESET!
)

rem ================================================================
rem Finish
rem ================================================================
echo.
echo !C_CYAN!============================================================!C_RESET!
echo !C_GREEN!                    SETUP COMPLETED!C_RESET!
echo !C_CYAN!============================================================!C_RESET!
echo.
echo !C_WHITE!Next steps:!C_RESET!
echo   1. Run environment-checker.bat
echo   2. If you use Ollama, install Ollama and then pull the required model
echo.
echo !C_DIM!Project directory: %~dp0!C_RESET!
echo.
pause
exit /b 0
