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

