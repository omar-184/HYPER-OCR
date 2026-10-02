#!/usr/bin/env bash
# Update HYPER-OCR to the newest version (needs the internet for a moment).
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "HYPER-OCR is not set up yet. Run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m hyperocr.update "$@"
