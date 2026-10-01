#!/usr/bin/env bash
# HYPER-OCR setup for macOS and Linux. Needs the internet once.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  echo "Python 3.10 or newer is needed (macOS: brew install python; Ubuntu: sudo apt install python3 python3-venv)."
  exit 1
fi

if ! command -v tesseract >/dev/null 2>&1; then
  if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    echo "Installing Tesseract OCR with Homebrew ..."
    brew install tesseract
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Installing Tesseract OCR (asks for your password) ..."
    sudo apt-get install -y tesseract-ocr
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y tesseract
  else
    echo "Install Tesseract OCR with your package manager, then run this again."
    exit 1
  fi
fi

[[ -x .venv/bin/python ]] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
echo "Installing packages ..."
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps "markitdown>=0.1.2,<0.2"

echo "Adding the English and Arabic languages ..."
.venv/bin/python -m hyperocr.languages add eng ara osd || echo "Languages could not be downloaded; the system's Tesseract languages will be used."

if command -v nvidia-smi >/dev/null 2>&1; then
  echo
  echo "An NVIDIA graphics card was found. Unlimited-OCR reads pages more accurately,"
  echo "but needs about 3 GB of downloads now plus the model, several GB more."
  read -r -p "Install Unlimited-OCR GPU support now? [y/N] " answer
  if [[ "${answer:-n}" =~ ^[Yy] ]]; then
    .venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    .venv/bin/python -m pip install -r requirements-gpu.txt
    .venv/bin/python -m hyperocr.download_model
  fi
else
  echo "No NVIDIA graphics card found: HYPER-OCR will use Tesseract."
fi

echo
echo "Setup finished. Start HYPER-OCR with ./start.sh (on a Mac you can double-click start-mac.command)."
