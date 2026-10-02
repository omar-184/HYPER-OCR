"""Where HYPER-OCR's own files are: a source checkout, or the installed desktop app.

In the desktop app (a PyInstaller build) the program and its Python live in one
folder, with Tesseract in `tesseract/` and the languages in `tessdata/` next to
HYPER-OCR.exe. Windows installs it for the current user (no administrator rights),
so that folder can be written to: languages can be added and updates installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

# The folder holding the app: the checkout's root, or the folder of HYPER-OCR.exe.
APP_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]


def user_data() -> Path:
    """Per-user settings of the desktop window (its browser storage, the log)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "HYPER-OCR"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "HYPER-OCR"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "hyperocr"


def no_window() -> dict:
    """subprocess arguments that keep a console window from flashing up on Windows."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
