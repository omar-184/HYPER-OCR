"""Build the files for a GitHub Release, the only thing the in-app updater installs.

    python tools/make_release.py

Writes dist/HYPER-OCR-<version>.zip (the committed files, from `git archive`) and
dist/HYPER-OCR-<version>.zip.sha256. Then, on GitHub: Releases -> Draft a new release,
tag `v<version>` on the same commit, attach both files, and publish. With the GitHub CLI:

    gh release create v<version> dist/HYPER-OCR-<version>.zip dist/HYPER-OCR-<version>.zip.sha256
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    version = re.search(r'__version__ = "([\d.]+)"', (ROOT / "hyperocr" / "__init__.py").read_text()).group(1)
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True,
                      check=True).stdout.strip():
        print("Commit or stash your changes first: a release is built from the last commit.")
        return 1
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    name = "HYPER-OCR-%s.zip" % version
    archive = dist / name
    subprocess.run(["git", "archive", "--format=zip", "--prefix=HYPER-OCR-%s/" % version, "-o", str(archive), "HEAD"],
                   cwd=ROOT, check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / (name + ".sha256")).write_text("%s  %s\n" % (digest, name), encoding="ascii")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    print("Built %s (%d KB) from commit %s" % (archive.relative_to(ROOT), archive.stat().st_size // 1024, commit))
    print("SHA-256 %s" % digest)
    print("Publish it as release v%s on that commit, with both files attached." % version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
