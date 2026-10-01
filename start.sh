#!/usr/bin/env bash
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "HYPER-OCR is not set up yet. Run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m hyperocr "$@"
