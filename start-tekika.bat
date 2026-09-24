@echo off
title Tekika AI Launcher
echo =========================================
echo         Tekika AI を起動しています...
echo =========================================

:: 1. バックエンドの起動 (Port 8000)
echo [1/3] バックエンドサーバーを起動中...
start "Tekika AI - Backend" cmd /k "cd /d %~dp0tekika-ai-backend && py -m uvicorn backend.main:app --port 8000"

:: 2. フロントエンドの起動 (Port 3000)
echo [2/3] フロントエンド(Web UI)を起動中...
start "Tekika AI - Frontend" cmd /k "cd /d %~dp0tekika-ai-frontend && npm run dev"

:: 3. サーバーの準備完了検知とブラウザ起動
echo [3/3] Web画面の準備完了を待っています...
powershell -Command "while (!(Test-NetConnection -ComputerName localhost -Port 3000 -InformationLevel Quiet)) { Start-Sleep -Seconds 2 }"

echo -----------------------------------------
echo サーバー起動を確認しました！ブラウザを開きます。
start http://localhost:3000

echo =========================================
echo 起動が完了しました！
echo =========================================