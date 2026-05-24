@echo off
chcp 65001 >nul
echo 正在啟動 Antigravity 結構設計引擎...
echo.
cd /d "%~dp0"
start http://localhost:5000
python server.py
pause
