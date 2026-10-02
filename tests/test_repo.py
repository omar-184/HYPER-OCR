"""What the repository says about itself stays true."""

import re

from conftest import ROOT
from hyperocr.engines.tesseract_engine import TESTED_VERSION, WINGET_VERSION


def test_there_is_a_licence():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE") and "Version 3, 19 November 2007" in text
    assert 'license = "AGPL-3.0-or-later"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_readme_makes_no_claim_the_code_cant_back():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "phone browser" not in readme.lower()            # the server listens on this computer only
    for image in re.findall(r"!\[[^\]]*\]\((docs/[^)]+)\)", readme):
        assert (ROOT / image).is_file(), image


def test_windows_setup_installs_the_tested_tesseract():
    setup = (ROOT / "setup-windows.bat").read_text(encoding="utf-8")
    assert "--version %s" % WINGET_VERSION in setup and WINGET_VERSION.startswith(TESTED_VERSION)


def test_one_version_number():
    from hyperocr import __version__

    assert 'version = "%s"' % __version__ in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_desktop_app_bundles_the_tested_tesseract_and_a_full_icon():
    import importlib.util

    from PIL import Image

    spec = importlib.util.spec_from_file_location("build_desktop", ROOT / "tools" / "build_desktop.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    assert WINGET_VERSION in build.TESSERACT["url"] and len(build.TESSERACT["sha256"]) == 64
    assert sorted(build.TESSDATA) == ["ara", "eng", "osd"] and all(len(h) == 64 for h in build.TESSDATA.values())
    assert "/tesseract-ocr/tessdata/" in build.TESSDATA_URL       # the standard models, as setup downloads
    icon = Image.open(ROOT / "packaging" / "windows" / "HYPER-OCR.ico")
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(icon.info["sizes"])
    iss = (ROOT / "packaging" / "windows" / "HYPER-OCR.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss and "OutputBaseFilename=HYPER-OCR-Setup-{#AppVersion}" in iss
