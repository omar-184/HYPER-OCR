@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HYPER-OCR update
if not exist ".venv\Scripts\python.exe" (
  echo HYPER-OCR is not set up yet. Double-click setup-windows.bat first.
  pause
  exit /b 1
)
echo Checking for a newer HYPER-OCR (needs the internet for a moment) ...
".venv\Scripts\python.exe" -m hyperocr.update %*
pause
