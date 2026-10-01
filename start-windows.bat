@echo off
chcp 65001 >nul
cd /d "%~dp0"
title HYPER-OCR
if not exist ".venv\Scripts\python.exe" (
  echo HYPER-OCR is not set up yet. Double-click setup-windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m hyperocr %*
pause
