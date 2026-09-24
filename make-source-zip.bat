@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Tekika AI - Source ZIP Creator
cd /d "%~dp0"

echo =========================================
echo      Tekika AI ソースZIP作成ツール
echo =========================================
echo.
echo ソースコードのみをZIP化します。
echo .env、生成物、DB、node_modules、.next等は除外します。
echo.

set "ZIP_PATH=%~dp0TekikaAI-source.zip"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%" >nul 2>&1

REM tarの--excludeはファイル名パターンを対象とするため、.env.exampleは残し、
REM 秘密の .env だけを除外します。
tar -a -c -f "%ZIP_PATH%" ^
  --exclude=".env" ^
  --exclude=".env.*" ^
  --exclude="*.db" ^
  --exclude="*.sqlite" ^
  --exclude="*.sqlite3" ^
  --exclude="chroma" ^
  --exclude="__pycache__" ^
  --exclude=".venv" ^
  --exclude="venv" ^
  --exclude=".git" ^
  --exclude=".next" ^
  --exclude="node_modules" ^
  --exclude="dist" ^
  --exclude="build" ^
  --exclude="*.log" ^
  --exclude="data/exports/*" ^
  --exclude="data/images/*" ^
  --exclude="TekikaAI-source.zip" ^
  --exclude="TekikaAI-Distribution.zip" ^
  *

if errorlevel 1 (
    echo.
    echo [NG] ZIPの作成に失敗しました。
    pause
    exit /b 1
)

echo.
echo [OK] ソースZIPの作成が完了しました。
echo 出力先: %ZIP_PATH%
echo.
pause
