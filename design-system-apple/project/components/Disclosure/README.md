# Disclosure

A grouped header row that expands to show one document's results when several files were converted separately.

**Use** only when there is more than one document; a single document shows its results directly. The page provides the document name (in `<bdi>`), a counted summary ("2 pages · 1 picture · 1 table", plural forms from `Intl.PluralRules`) and the body.

- Header: `tile-blue` with the `stack` glyph, label in 600 weight, `chev` that rotates 90° (flipped in right-to-left).
- Body height and opacity follow one spring (`response` .4); it can be reversed mid-way.
- The first document starts open; `aria-expanded` mirrors the state.
