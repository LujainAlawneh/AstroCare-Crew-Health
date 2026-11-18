@echo off
cd /d "%~dp0"
echo AstroCare - open http://127.0.0.1:8765 in your browser.
echo Keep this window open while using the app.
py --version >nul 2>nul
if %errorlevel% equ 0 (
  py server.py
) else (
  python server.py
)
pause
