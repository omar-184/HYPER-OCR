@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title HYPER-OCR setup
echo.
echo  HYPER-OCR setup
echo  ---------------
echo  This needs the internet once. After it, HYPER-OCR works fully offline.
echo.

rem ---- 1. Python 3.10 or newer
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Installing Python 3.12 ...
  winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
  if errorlevel 1 goto :nopython
  echo.
  echo Python is installed. Close this window and double-click setup-windows.bat again to continue.
  pause
  exit /b 0
)

rem ---- 2. A private Python environment with the app's packages
if not exist ".venv\Scripts\python.exe" (
  echo Creating the app's Python environment ...
  %PY% -m venv .venv
  if errorlevel 1 goto :nopython
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip >nul
echo Installing packages ...
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
"%VPY%" -m pip install --no-deps "markitdown>=0.1.2,<0.2"
if errorlevel 1 goto :fail

rem ---- 3. Tesseract OCR (the engine that works on any computer)
"%VPY%" -c "import sys; from hyperocr.engines.tesseract_engine import find_tesseract; sys.exit(0 if find_tesseract() else 1)"
if errorlevel 1 (
  echo Installing Tesseract OCR ...
  winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo.
    echo Tesseract could not be installed automatically. Download it from
    echo https://github.com/UB-Mannheim/tesseract/wiki and run this setup again.
    goto :fail
  )
)

rem ---- 4. English and Arabic for Tesseract
echo Adding the English and Arabic languages ...
"%VPY%" -m hyperocr.languages add eng ara osd

rem ---- 5. Optional: Unlimited-OCR on an NVIDIA graphics card
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo No NVIDIA graphics card found: HYPER-OCR will use Tesseract.
) else (
  echo.
  echo An NVIDIA graphics card was found. Unlimited-OCR reads pages more accurately,
  echo but needs about 3 GB of downloads now plus the model, several GB more.
  choice /C YN /M "Install Unlimited-OCR GPU support now"
  if not errorlevel 2 call :gpu
)

echo.
echo Setup finished. Double-click start-windows.bat to open HYPER-OCR.
pause
exit /b 0

:gpu
echo Installing PyTorch with CUDA ...
"%VPY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 exit /b 1
"%VPY%" -m pip install -r requirements-gpu.txt
if errorlevel 1 exit /b 1
"%VPY%" -m hyperocr.download_model
exit /b 0

:nopython
echo.
echo Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then run this setup again.
:fail
echo.
echo Setup did not finish. Read the messages above, fix the problem and run it again.
pause
exit /b 1
