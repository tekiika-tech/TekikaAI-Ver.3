@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Tekika AI - Environment Checker

cd /d "%~dp0"

echo =========================================
echo       Tekika AI Environment Check
echo =========================================
echo.
echo This program only checks your environment.
echo It does not modify Python, Node.js, or other settings.
echo.

set "ERROR_COUNT=0"

REM =========================================
REM 1. Python
REM =========================================
echo [1/7] Python
echo -----------------------------------------

py --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] Python Launcher (py) was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Please install Python.' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    -> Run this checker again after installation.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] Python' -ForegroundColor Green"
    py --version
)

echo.


REM =========================================
REM 2. Python packages
REM =========================================
echo [2/7] Python Packages
echo -----------------------------------------

if not exist "%~dp0tekika-ai-backend\requirements.txt" (
    powershell -NoProfile -Command "Write-Host '[NG] requirements.txt was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Make sure the tekika-ai-backend folder is correctly placed.' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    -> Make sure the complete Tekika AI source is in the correct location.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (

    py -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] FastAPI' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] FastAPI' -ForegroundColor Green"
    )

    py -c "import uvicorn" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Uvicorn' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Uvicorn' -ForegroundColor Green"
    )

    py -c "import pydantic" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pydantic' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pydantic' -ForegroundColor Green"
    )

    py -c "import pydantic_settings" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pydantic Settings' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pydantic Settings' -ForegroundColor Green"
    )

    py -c "import dotenv" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] python-dotenv' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] python-dotenv' -ForegroundColor Green"
    )

    py -c "import httpx" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] httpx' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] httpx' -ForegroundColor Green"
    )

    py -c "import git" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] GitPython' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] GitPython' -ForegroundColor Green"
    )

    py -c "import chromadb" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] ChromaDB' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] ChromaDB' -ForegroundColor Green"
    )

    py -c "from PIL import Image" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Pillow' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Pillow' -ForegroundColor Green"
    )

    py -c "import multipart" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] python-multipart' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> A required Python package is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] python-multipart' -ForegroundColor Green"
    )

    py -c "import ollama" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Ollama Python Library' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> The Ollama Python library is missing.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Install the dependencies from requirements.txt.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Ollama Python Library' -ForegroundColor Green"
    )
)

echo.


REM =========================================
REM 3. Node.js / npm
REM =========================================
echo [3/7] Node.js / npm
echo -----------------------------------------

node --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] Node.js was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Please install Node.js.' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    -> Run this checker again after installation.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] Node.js' -ForegroundColor Green"
    node --version
)

call npm --version >nul 2>&1

if errorlevel 1 (
    powershell -NoProfile -Command "Write-Host '[NG] npm was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> npm is included with Node.js.' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    -> Run this checker again after installing Node.js.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] npm' -ForegroundColor Green"
    call npm --version
)

echo.


REM =========================================
REM 4. Frontend
REM =========================================
echo [4/7] Frontend
echo -----------------------------------------

if not exist "%~dp0tekika-ai-frontend\package.json" (
    powershell -NoProfile -Command "Write-Host '[NG] package.json was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Make sure the tekika-ai-frontend folder is correctly placed.' -ForegroundColor Yellow"
    powershell -NoProfile -Command "Write-Host '    -> Make sure the Tekika AI frontend files are in the correct location.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] package.json' -ForegroundColor Green"

    if exist "%~dp0tekika-ai-frontend\node_modules" (
        powershell -NoProfile -Command "Write-Host '[OK] node_modules' -ForegroundColor Green"
    ) else (
        powershell -NoProfile -Command "Write-Host '[NG] node_modules was not found.' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> Frontend dependencies have not been installed.' -ForegroundColor Yellow"
        powershell -NoProfile -Command "Write-Host '    -> Run npm install inside the tekika-ai-frontend folder.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    )
)

echo.


REM =========================================
REM 5. Environment
REM =========================================
echo [5/7] Environment Configuration
echo -----------------------------------------

if not exist "%~dp0tekika-ai-backend\.env" (
    powershell -NoProfile -Command "Write-Host '[NG] .env was not found.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Copy tekika-ai-backend\.env.example to .env and configure it.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] .env' -ForegroundColor Green"
)

if not exist "%~dp0tekika-ai-backend\.env.example" (
    powershell -NoProfile -Command "Write-Host '[NG] .env.example was not found.' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] .env.example' -ForegroundColor Green"
)

set "LLM_PROVIDER="

if exist "%~dp0tekika-ai-backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"LLM_PROVIDER=" "%~dp0tekika-ai-backend\.env"`) do (
        set "LLM_PROVIDER=%%B"
    )
)

if not defined LLM_PROVIDER (
    powershell -NoProfile -Command "Write-Host '[NG] LLM_PROVIDER is not configured.' -ForegroundColor Red"
    powershell -NoProfile -Command "Write-Host '    -> Set ollama, openai, claude, or gemini in .env.' -ForegroundColor Yellow"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] LLM_PROVIDER = !LLM_PROVIDER!' -ForegroundColor Green"
)

if /I "!LLM_PROVIDER!"=="openai" call :check_key "OPENAI_API_KEY" "OpenAI"
if /I "!LLM_PROVIDER!"=="claude" call :check_key "ANTHROPIC_API_KEY" "Anthropic Claude"
if /I "!LLM_PROVIDER!"=="gemini" call :check_key "GOOGLE_API_KEY" "Google Gemini"

echo.


REM =========================================
REM 6. Ollama
REM =========================================
echo [6/7] Ollama
echo -----------------------------------------

if /I not "!LLM_PROVIDER!"=="ollama" (
    powershell -NoProfile -Command "Write-Host '[SKIP] Ollama check skipped because LLM_PROVIDER is not ollama.' -ForegroundColor Yellow"
) else (
    ollama --version >nul 2>&1

    if errorlevel 1 (
        powershell -NoProfile -Command "Write-Host '[NG] Ollama was not found.' -ForegroundColor Red"
        powershell -NoProfile -Command "Write-Host '    -> Please install Ollama.' -ForegroundColor Yellow"
        set /a ERROR_COUNT+=1
    ) else (
        powershell -NoProfile -Command "Write-Host '[OK] Ollama' -ForegroundColor Green"
        ollama --version

        echo.
        echo Checking connection to the Ollama server...

        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"

        if errorlevel 1 (
            powershell -NoProfile -Command "Write-Host '[NG] Could not connect to the Ollama server.' -ForegroundColor Red"
            powershell -NoProfile -Command "Write-Host '    -> Make sure Ollama is running.' -ForegroundColor Yellow"
            set /a ERROR_COUNT+=1
        ) else (
            powershell -NoProfile -Command "Write-Host '[OK] Connected to the Ollama server.' -ForegroundColor Green"
        )

        echo.
        echo Installed models:
        ollama list
    )
)

echo.


REM =========================================
REM 7. Backend
REM =========================================
echo [7/7] Backend Structure
echo -----------------------------------------

if exist "%~dp0tekika-ai-backend\backend\main.py" (
    powershell -NoProfile -Command "Write-Host '[OK] backend\main.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] backend\main.py was not found.' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

if exist "%~dp0tekika-ai-backend\backend\agent\factory.py" (
    powershell -NoProfile -Command "Write-Host '[OK] agent\factory.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] agent\factory.py was not found.' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

if exist "%~dp0tekika-ai-backend\backend\agent\orchestrator.py" (
    powershell -NoProfile -Command "Write-Host '[OK] agent\orchestrator.py' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '[NG] agent\orchestrator.py was not found.' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
)

echo.


REM =========================================
REM Result
REM =========================================
echo =========================================
echo             Check Result
echo =========================================
echo.

if "%ERROR_COUNT%"=="0" (
    powershell -NoProfile -Command "Write-Host '[OK] All checks passed successfully.' -ForegroundColor Green"
    echo.
    echo Tekika AI is ready to start.
    echo Run start-tekika.bat to launch Tekika AI.
) else (
    powershell -NoProfile -Command "Write-Host '[NG] %ERROR_COUNT% problem(s) were found.' -ForegroundColor Red"
    echo.
    powershell -NoProfile -Command "Write-Host 'Please check the [NG] items and the yellow instructions above.' -ForegroundColor Yellow"
)

echo.
echo =========================================
echo            Check Complete
echo =========================================
echo.
echo Press any key to exit.
echo.

pause
exit /b


REM =========================================
REM API Key Check
REM =========================================
:check_key

set "CHECK_KEY="

if exist "%~dp0tekika-ai-backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"%~1=" "%~dp0tekika-ai-backend\.env"`) do (
        set "CHECK_KEY=%%B"
    )
)

if not defined CHECK_KEY (
    powershell -NoProfile -Command "Write-Host '[NG] %~2 API key (%~1) is not configured or is empty.' -ForegroundColor Red"
    set /a ERROR_COUNT+=1
) else (
    powershell -NoProfile -Command "Write-Host '[OK] %~2 API key is configured.' -ForegroundColor Green"
)

exit /b