# HYPER-OCR

Offline web app (Flask on 127.0.0.1) that turns scanned PDFs and photos into searchable PDFs, Markdown, pictures and Word tables. Run the tests with `.venv/bin/python -m pytest -q`.

## Design changes: keep the "Apple style App" design system in step

The interface (`hyperocr/static/`: `style.css`, `index.html`, `app.js`, `motion.js`, `icon.svg`) is the source of truth for the **Apple style App** design system in Claude Design: https://claude.ai/artifact/5DMM2F5XN8yfvWP6BAiCDk. Its files live in `design-system-apple/project/`.

Whenever a change touches the look or behaviour of the interface (colours, type, spacing, components, icons, motion, copy patterns), finish it like this:

1. Run `python design-system-apple/build.py`. It syncs colour values, `shadow-lift` and font stacks into `tokens.json`, regenerates `components/bundle.css` and `components/bundle.js`, re-extracts the icons and refreshes the sprite and app icon in every preview. A new colour variable stops the build until it has a token with a usage note.
2. By hand, update what the script can't know: tokens that live in component rules (spacing, radius, size, other shadows), the affected `components/<Name>/README.md` and `preview.html` (a new component gets both), `README.md` or `motion.md` when a rule changes, and contrast notes for changed colours.
3. Publish the changed files to the design system with the Artifact tool: read `project/design-system.json` from the artifact first, upload any new or changed SVG under `assets/` as an asset and record it in the index, then ONE publish with `url` = the link above, `root` = `design-system-apple`, only the changed `project/...` files, and the index last with an updated `lastChange`.
4. `tests/test_design_system.py` fails while `build.py --check` reports anything out of date.

`design-system/` is the older green "Attendance Register" system (version 1.0's look); leave it alone unless asked.
