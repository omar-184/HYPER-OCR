# PyInstaller recipe for the HYPER-OCR desktop app. Built by tools/build_desktop.py, which also
# adds Tesseract and the languages next to HYPER-OCR.exe; see README "Building the desktop app".
# -*- mode: python -*-

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821  (SPECPATH is set by PyInstaller)
WINDOWS = sys.platform == "win32"
VERSION = re.search(r'__version__ = "([\d.]+)"', (ROOT / "hyperocr" / "__init__.py").read_text()).group(1)

datas = [
    (str(ROOT / "hyperocr" / "static"), "hyperocr/static"),
    (str(ROOT / "hyperocr" / "outputs" / "glyphless.ttf"), "hyperocr/outputs"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
]
datas += collect_data_files("markitdown")

# The experimental GPU engine stays off in the desktop app: its libraries are left out.
excludes = ["torch", "torchvision", "transformers", "accelerate", "safetensors", "huggingface_hub",
            "onnxruntime", "magika", "tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6", "PySide2",
            "PySide6"]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "hyperocr_app.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=collect_submodules("hyperocr") + ["waitress"],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

version_info = None
if WINDOWS:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo)

    numbers = tuple(int(p) for p in (VERSION.split(".") + ["0", "0", "0"])[:4])
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "HYPER-OCR"),
            StringStruct("FileDescription", "HYPER-OCR"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "HYPER-OCR"),
            StringStruct("LegalCopyright", "AGPL-3.0-or-later"),
            StringStruct("OriginalFilename", "HYPER-OCR.exe"),
            StringStruct("ProductName", "HYPER-OCR"),
            StringStruct("ProductVersion", VERSION)])]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])])],
    )

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HYPER-OCR",
    console=False,                       # a window app: no black console window
    icon=str(ROOT / "packaging" / "windows" / "HYPER-OCR.ico") if WINDOWS else None,
    version=version_info,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="HYPER-OCR", upx=False)  # noqa: F821
