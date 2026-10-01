"""Write hyperocr/static/tokens.css and components.css from this design system.

    python design-system/build_css.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
STATIC = HERE.parent / "hyperocr" / "static"


def block(tokens: dict, theme: str) -> list[str]:
    lines = []
    for t in tokens["color"]["tokens"]:
        v = t["value"]
        lines.append("  --%s: %s;" % (t["name"], v[theme] if isinstance(v, dict) else v))
    for t in tokens.get("shadow", {}).get("tokens", []):
        v = t["value"]
        lines.append("  --%s: %s;" % (t["name"], v[theme] if isinstance(v, dict) else v))
    return lines


def main() -> None:
    tokens = json.loads((HERE / "tokens.json").read_text(encoding="utf-8"))
    out = ["/* Generated from design-system/tokens.json by design-system/build_css.py. Do not edit. */", ""]
    out += [":root {"] + block(tokens, "light")
    for fam in ("spacing", "radius", "controlHeight", "width"):
        for t in tokens.get(fam, {}).get("tokens", []):
            out.append("  --%s: %s;" % (t["name"], t["value"]))
    for key, stack in tokens["type"]["families"].items():
        out.append("  --font-%s: %s;" % (key, stack))
    out += ["  color-scheme: light;", "}", ""]
    dark = block(tokens, "dark") + ["  color-scheme: dark;"]
    out += ["@media (prefers-color-scheme: dark) {", "  :root:not([data-theme=\"light\"]) {"]
    out += ["  " + line for line in dark] + ["  }", "}", ""]
    out += [":root[data-theme=\"dark\"] {"] + dark + ["}", ""]
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / "tokens.css").write_text("\n".join(out), encoding="utf-8")
    shutil.copyfile(HERE / "components.css", STATIC / "components.css")
    print("wrote", STATIC / "tokens.css", "and components.css")


if __name__ == "__main__":
    main()
