"""What the repository says about itself stays true."""

import re

from conftest import ROOT


def test_there_is_a_licence():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE") and "Version 3, 19 November 2007" in text
    assert 'license = "AGPL-3.0-or-later"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_readme_makes_no_claim_the_code_cant_back():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "phone browser" not in readme.lower()            # the server listens on this computer only
    for image in re.findall(r"!\[[^\]]*\]\((docs/[^)]+)\)", readme):
        assert (ROOT / image).is_file(), image

