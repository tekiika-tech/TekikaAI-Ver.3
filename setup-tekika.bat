@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Tekika AI - Setup

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Failed to enter the Tekika AI project directory: %~dp0
    pause
    exit /b 1
)

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

rem ================================================================
rem Initial checks
rem ================================================================

cls
echo.
echo !C_CYAN!============================================================!C_RESET!
echo !C_WHITE!                       TEKIKA AI SETUP!C_RESET!
echo !C_CYAN!============================================================!C_RESET!
echo.
echo !C_DIM!This setup checks the current environment first.!C_RESET!
echo !C_DIM!Only missing components will be offered for installation.!C_RESET!
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
rem Status variables
rem ================================================================

set "PYTHON_OK=0"
set "PYTHON_VERSION="
set "PYTHON_PACKAGES_OK=0"

set "NODE_OK=0"
set "NODE_VERSION="
set "NPM_OK=0"
set "NPM_VERSION="
set "FRONTEND_DEPS_OK=0"

set "ENV_OK=0"
set "ENV_EXAMPLE_OK=0"

set "BACKEND_DIRS_OK=0"

set "OLLAMA_OK=0"
set "OLLAMA_SERVER_OK=0"
set "OLLAMA_MODEL_OK=0"
set "OLLAMA_MODEL=qwen2.5:latest"

set "MISSING_COUNT=0"
set "LLM_PROVIDER=ollama"
if exist "%BACKEND_DIR%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"LLM_PROVIDER=" "%BACKEND_DIR%\.env"`) do set "LLM_PROVIDER=%%B"
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"OLLAMA_DEFAULT_MODEL=" "%BACKEND_DIR%\.env"`) do set "OLLAMA_MODEL=%%B"
)

rem ================================================================
rem [1] Check Python
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![1] Checking Python environment!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

py --version >nul 2>&1

if errorlevel 1 (
    echo !C_RED![NG] Python Launcher "py" was not found.!C_RESET!
    set "PYTHON_OK=0"
    set /a MISSING_COUNT+=1
) else (
    py -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1

    if errorlevel 1 (
        echo !C_RED![NG] Python 3.10 or newer is required.!C_RESET!
        py --version
        set "PYTHON_OK=0"
        set /a MISSING_COUNT+=1
    ) else (
        for /f "delims=" %%V in ('py --version 2^>^&1') do set "PYTHON_VERSION=%%V"
        echo !C_GREEN![OK] !C_RESET!!PYTHON_VERSION!
        set "PYTHON_OK=1"
    )
)

rem ================================================================
rem [2] Check Python packages
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![2] Checking Python packages!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

if "!PYTHON_OK!"=="1" (
    cd /d "%BACKEND_DIR%"

    set "PY_PACKAGES_MISSING=0"

    py -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] FastAPI!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] FastAPI!C_RESET!
    )

    py -c "import uvicorn" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] Uvicorn!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] Uvicorn!C_RESET!
    )

    py -c "import pydantic" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] Pydantic!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] Pydantic!C_RESET!
    )

    py -c "import pydantic_settings" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] Pydantic Settings!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] Pydantic Settings!C_RESET!
    )

    py -c "import dotenv" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] python-dotenv!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] python-dotenv!C_RESET!
    )

    py -c "import httpx" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] httpx!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] httpx!C_RESET!
    )

    py -c "import git" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] GitPython!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] GitPython!C_RESET!
    )

    py -c "import chromadb" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] ChromaDB!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] ChromaDB!C_RESET!
    )

    py -c "from PIL import Image" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] Pillow!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] Pillow!C_RESET!
    )

    py -c "import multipart" >nul 2>&1
    if errorlevel 1 (
        echo !C_RED![NG] python-multipart!C_RESET!
        set "PY_PACKAGES_MISSING=1"
    ) else (
        echo !C_GREEN![OK] python-multipart!C_RESET!
    )

    if "!PY_PACKAGES_MISSING!"=="0" (
        set "PYTHON_PACKAGES_OK=1"
    ) else (
        set /a MISSING_COUNT+=1
    )
) else (
    echo !C_YELLOW![SKIP] Python packages cannot be checked because Python is unavailable.!C_RESET!
)

rem ================================================================
rem [3] Check Node.js / npm
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![3] Checking Node.js / npm environment!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

node --version >nul 2>&1

if errorlevel 1 (
    echo !C_RED![NG] Node.js was not found.!C_RESET!
    set "NODE_OK=0"
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%V in ('node --version') do set "NODE_VERSION=%%V"

    powershell -NoProfile -Command "$v=[version]'!NODE_VERSION:~1!'; if($v -ge [version]'18.17.0'){exit 0}else{exit 1}" >nul 2>&1

    if errorlevel 1 (
        echo !C_RED![NG] Node.js 18.17 or newer is required.!C_RESET!
        echo !C_RED!Installed version: !NODE_VERSION!!C_RESET!
        set "NODE_OK=0"
        set /a MISSING_COUNT+=1
    ) else (
        echo !C_GREEN![OK] !C_RESET!!NODE_VERSION!
        set "NODE_OK=1"
    )
)

call npm --version >nul 2>&1

if errorlevel 1 (
    echo !C_RED![NG] npm was not found.!C_RESET!
    set "NPM_OK=0"
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%V in ('call npm --version') do set "NPM_VERSION=%%V"
    echo !C_GREEN![OK] !C_RESET!npm !NPM_VERSION!
    set "NPM_OK=1"
)
rem ================================================================
rem [4] Check frontend dependencies
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![4] Checking frontend dependencies!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

if not exist "%FRONTEND_DIR%\package.json" (
    echo !C_RED![NG] package.json was not found.!C_RESET!
    set /a MISSING_COUNT+=1
) else (
    echo !C_GREEN![OK] package.json!C_RESET!

    if exist "%FRONTEND_DIR%\node_modules\." (
        echo !C_GREEN![OK] node_modules!C_RESET!
        set "FRONTEND_DEPS_OK=1"
    ) else (
        echo !C_RED![NG] node_modules was not found.!C_RESET!
        set /a MISSING_COUNT+=1
    )
)

rem ================================================================
rem [5] Check .env
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![5] Checking environment configuration!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

if exist "%BACKEND_DIR%\.env" (
    echo !C_GREEN![OK] .env!C_RESET!
    set "ENV_OK=1"
) else (
    echo !C_RED![NG] .env was not found.!C_RESET!
    set /a MISSING_COUNT+=1
)

if exist "%BACKEND_DIR%\.env.example" (
    echo !C_GREEN![OK] .env.example!C_RESET!
    set "ENV_EXAMPLE_OK=1"
) else (
    echo !C_RED![NG] .env.example was not found.!C_RESET!
)

rem ================================================================
rem [6] Check backend directories
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![6] Checking backend data directories!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

set "BACKEND_DIRS_MISSING=0"

for %%D in (
    "data"
    "data\exports"
    "data\images"
    "data\chroma"
    "plugins"
) do (
    if exist "%BACKEND_DIR%\%%~D\." (
        echo !C_GREEN![OK] %%~D!C_RESET!
    ) else (
        echo !C_RED![NG] %%~D!C_RESET!
        set "BACKEND_DIRS_MISSING=1"
    )
)

if "!BACKEND_DIRS_MISSING!"=="0" (
    set "BACKEND_DIRS_OK=1"
) else (
    set /a MISSING_COUNT+=1
)

rem ================================================================
rem [7] Check Ollama
rem ================================================================

echo.
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo !C_WHITE![7] Checking Ollama!C_RESET!
echo !C_BLUE!------------------------------------------------------------!C_RESET!
echo.

if /I not "!LLM_PROVIDER!"=="ollama" (
    echo !C_YELLOW![SKIP] LLM_PROVIDER is !LLM_PROVIDER!; Ollama is optional.!C_RESET!
    set "OLLAMA_OK=1"
    set "OLLAMA_SERVER_OK=1"
) else (
ollama --version >nul 2>&1

if errorlevel 1 (
    echo !C_RED![NG] Ollama was not found.!C_RESET!
    set "OLLAMA_OK=0"
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%V in ('ollama --version 2^>^&1') do set "OLLAMA_VERSION=%%V"
    echo !C_GREEN![OK] !C_RESET!!OLLAMA_VERSION!
    set "OLLAMA_OK=1"

    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1

    if errorlevel 1 (
        echo !C_YELLOW![WARN] Ollama is installed but the server is not running.!C_RESET!
    ) else (
        echo !C_GREEN![OK] Ollama server is running.!C_RESET!
        set "OLLAMA_SERVER_OK=1"
        powershell -NoProfile -Command "$m=(Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 5).models.name; if($m -contains '!OLLAMA_MODEL!'){exit 0}else{exit 1}" >nul 2>&1
        if errorlevel 1 (
            echo !C_YELLOW![WARN] Required Ollama model !OLLAMA_MODEL! is missing.!C_RESET!
            set /a MISSING_COUNT+=1
        ) else (
            echo !C_GREEN![OK] Required Ollama model !OLLAMA_MODEL!!C_RESET!
            set "OLLAMA_MODEL_OK=1"
        )
    )
)
)

rem ================================================================
rem Detection summary
rem ================================================================

echo.
echo !C_CYAN!============================================================!C_RESET!
echo !C_WHITE!                    DETECTION COMPLETE!C_RESET!
echo !C_CYAN!============================================================!C_RESET!
echo.

if "!MISSING_COUNT!"=="0" (
    echo !C_GREEN![OK] All required components are already available.!C_RESET!
    echo.
    goto :CREATE_ENV_AND_FINISH
)

echo !C_YELLOW!Missing or incomplete components were detected.!C_RESET!
echo !C_YELLOW!You can approve each installation individually below.!C_RESET!
echo.

rem ================================================================
rem Installation approval: Python
rem ================================================================

if "!PYTHON_OK!"=="0" (
    echo !C_WHITE!Python 3.10 or newer is required.!C_RESET!
    echo.
    choice /C YN /N /M "Install Python automatically? [Y/N]: "

    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Python installation skipped.!C_RESET!
    ) else (
        echo.
        echo !C_CYAN!Opening the official Python download page...!C_RESET!
        start "" "https://www.python.org/downloads/windows/"
        echo !C_DIM!Please install Python manually, then run this setup again.!C_RESET!
    )

    echo.
)

rem ================================================================
rem Installation approval: Python packages
rem ================================================================

if "!PYTHON_OK!"=="1" if "!PYTHON_PACKAGES_OK!"=="0" (
    echo !C_WHITE!Some Python packages are missing.!C_RESET!
    echo.
    choice /C YN /N /M "Install Python dependencies from requirements.txt? [Y/N]: "

    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Python dependency installation skipped.!C_RESET!
    ) else (
        cd /d "%BACKEND_DIR%"

        echo.
        if not exist requirements.txt (
            echo !C_RED![ERROR] requirements.txt was not found.!C_RESET!
        ) else (
            echo.
            echo !C_CYAN!Installing missing Python dependencies from requirements.txt...!C_RESET!
            py -m pip install -r requirements.txt --progress-bar on

            if errorlevel 1 (
                echo !C_RED![ERROR] Python dependency installation failed.!C_RESET!
            ) else (
                echo !C_GREEN![OK] Python dependencies installed.!C_RESET!
                set "PYTHON_PACKAGES_OK=1"
            )
        )
    )

    echo.
)

rem ================================================================
rem Installation approval: Node.js
rem ================================================================

if "!NODE_OK!"=="0" (
    echo !C_WHITE!Node.js 18.17 or newer is required.!C_RESET!
    echo.
    choice /C YN /N /M "Open the official Node.js download page? [Y/N]: "

    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Node.js installation skipped.!C_RESET!
    ) else (
        start "" "https://nodejs.org/en/download"
        echo !C_GREEN![OK] Browser opened.!C_RESET!
        echo !C_DIM!Install Node.js manually, then run this setup again.!C_RESET!
    )

    echo.
)

rem ================================================================
rem Installation approval: npm dependencies
rem ================================================================

if "!NODE_OK!"=="1" if "!NPM_OK!"=="1" if "!FRONTEND_DEPS_OK!"=="0" (
    echo !C_WHITE!Frontend dependencies are missing.!C_RESET!
    echo.
    choice /C YN /N /M "Run npm install? [Y/N]: "

    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Frontend dependency installation skipped.!C_RESET!
    ) else (
        cd /d "%FRONTEND_DIR%"

        echo.
        echo !C_CYAN!Installing frontend dependencies...!C_RESET!
        if exist package-lock.json (
            call npm ci --progress=true
        ) else (
            call npm install --progress=true
        )

        if errorlevel 1 (
            echo !C_RED![ERROR] npm install failed.!C_RESET!
        ) else (
            echo !C_GREEN![OK] Frontend dependencies installed.!C_RESET!
            set "FRONTEND_DEPS_OK=1"
        )
    )

    echo.
)

rem ================================================================
rem Installation approval: .env
rem ================================================================

if "!ENV_OK!"=="0" (
    if "!ENV_EXAMPLE_OK!"=="1" (
        echo !C_WHITE!.env does not exist, but .env.example is available.!C_RESET!
        echo.
        choice /C YN /N /M "Create .env from .env.example? [Y/N]: "

        if errorlevel 2 (
            echo !C_YELLOW![SKIP] .env creation skipped.!C_RESET!
        ) else (
            copy /Y "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul

            if errorlevel 1 (
                echo !C_RED![ERROR] Failed to create .env.!C_RESET!
            ) else (
                echo !C_GREEN![OK] Created .env from .env.example.!C_RESET!
                set "ENV_OK=1"
            )
        )

        echo.
    ) else (
        echo !C_RED![ERROR] .env.example is also missing.!C_RESET!
        echo !C_YELLOW!Cannot create .env automatically.!C_RESET!
        echo.
    )
)

rem ================================================================
rem Installation approval: backend directories
rem ================================================================

if "!BACKEND_DIRS_OK!"=="0" (
    echo !C_WHITE!Some backend data directories are missing.!C_RESET!
    echo.
    choice /C YN /N /M "Create missing backend directories? [Y/N]: "

    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Backend directory creation skipped.!C_RESET!
    ) else (
        if not exist "%BACKEND_DIR%\data\." mkdir "%BACKEND_DIR%\data"
        if not exist "%BACKEND_DIR%\data\exports\." mkdir "%BACKEND_DIR%\data\exports"
        if not exist "%BACKEND_DIR%\data\images\." mkdir "%BACKEND_DIR%\data\images"
        if not exist "%BACKEND_DIR%\data\chroma\." mkdir "%BACKEND_DIR%\data\chroma"
        if not exist "%BACKEND_DIR%\plugins\." mkdir "%BACKEND_DIR%\plugins"

        echo !C_GREEN![OK] Backend directories are ready.!C_RESET!
        set "BACKEND_DIRS_OK=1"
    )

    echo.
)

rem ================================================================
rem Installation approval: Ollama
rem ================================================================

if /I "!LLM_PROVIDER!"=="ollama" if "!OLLAMA_OK!"=="1" if "!OLLAMA_SERVER_OK!"=="1" if "!OLLAMA_MODEL_OK!"=="0" (
    choice /C YN /N /M "Required model !OLLAMA_MODEL! is not installed. Pull it now? [Y/N]: "
    if errorlevel 2 (
        echo !C_YELLOW![SKIP] Ollama model pull skipped.!C_RESET!
    ) else (
        ollama pull "!OLLAMA_MODEL!"
        if errorlevel 1 (echo !C_RED![ERROR] Ollama model pull failed.!C_RESET!) else (set "OLLAMA_MODEL_OK=1")
    )
)

if /I "!LLM_PROVIDER!"=="ollama" if "!OLLAMA_OK!"=="0" (
    echo !C_WHITE!Ollama is not installed.!C_RESET!
    echo.
    echo !C_WHITE![1]!C_RESET! Open the official Ollama download page
    echo !C_WHITE![2]!C_RESET! Show the official PowerShell install command
    echo !C_WHITE![3]!C_RESET! Skip Ollama
    echo.

    choice /C 123 /N /M "Select [1-3]: "

    if errorlevel 3 (
        echo !C_YELLOW![SKIP] Ollama installation skipped.!C_RESET!
    ) else if errorlevel 2 (
        echo.
        echo !C_WHITE!PowerShell command:!C_RESET!
        echo.
        echo !C_YELLOW!!OLLAMA_PS!!C_RESET!
        echo.
        echo !C_DIM!The command is only displayed. It is not executed by this setup.!C_RESET!
    ) else (
        echo.
        echo !C_CYAN!Opening the official Ollama download page...!C_RESET!
        start "" "%OLLAMA_URL%"
        echo !C_GREEN![OK] Browser opened.!C_RESET!
        echo !C_DIM!Install Ollama manually, then run this setup again.!C_RESET!
    )

    echo.
)

rem ================================================================
rem Final environment creation
rem ================================================================

:CREATE_ENV_AND_FINISH

cd /d "%BACKEND_DIR%"
if errorlevel 1 (
    echo !C_RED![ERROR] Failed to enter backend directory.!C_RESET!
    goto :FINISH
)

rem ================================================================
rem Finish
rem ================================================================

:FINISH

echo.
echo !C_CYAN!============================================================!C_RESET!
echo !C_GREEN!                    SETUP COMPLETED!C_RESET!
echo !C_CYAN!============================================================!C_RESET!
echo.

if "!PYTHON_OK!"=="1" (echo [OK] Python !PYTHON_VERSION!) else (echo [WARN] Python installation is still required.)
if "!PYTHON_PACKAGES_OK!"=="1" (echo [OK] Python packages) else (echo [WARN] Python packages are missing or were skipped.)
if "!NODE_OK!"=="1" (echo [OK] Node.js !NODE_VERSION!) else (echo [WARN] Node.js installation is still required.)
if "!NPM_OK!"=="1" (echo [OK] npm !NPM_VERSION!) else (echo [WARN] npm was not found.)
if "!FRONTEND_DEPS_OK!"=="1" (echo [OK] Frontend dependencies) else (echo [WARN] Frontend dependencies are missing or were skipped.)
if "!ENV_OK!"=="1" (echo [OK] Environment) else (echo [WARN] .env is missing or was skipped.)
if "!BACKEND_DIRS_OK!"=="1" (echo [OK] Backend directories) else (echo [WARN] Some backend directories are missing or were skipped.)
if /I not "!LLM_PROVIDER!"=="ollama" (
    echo [SKIP] Ollama checks; configured provider is !LLM_PROVIDER!.
) else (
    if "!OLLAMA_OK!"=="1" (echo [OK] Ollama installed) else (echo [WARN] Ollama is not installed.)
    if "!OLLAMA_SERVER_OK!"=="1" (echo [OK] Ollama server) else (echo [WARN] Ollama is installed but server is not running, or Ollama is missing.)
    if "!OLLAMA_MODEL_OK!"=="1" (echo [OK] Required Ollama model !OLLAMA_MODEL!) else (echo [WARN] Required Ollama model is missing or could not be checked.)
)
echo.

echo !C_WHITE!The setup process is complete.!C_RESET!
echo.
echo !C_WHITE!Next steps:!C_RESET!
echo   1. Run environment-checker.bat
echo   2. Review your .env configuration
echo   3. If you use Ollama, make sure the required model is available
echo   4. Run start-tekika.bat
echo.
echo !C_DIM!Project directory: %~dp0!C_RESET!
echo.

pause
exit /b 0
