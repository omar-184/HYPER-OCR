# FileList

The chosen files as rows, each with a thumbnail, name, kind and size, a remove button and, when there are several, a drag handle.

**Use** in the Files group once files are chosen. The page provides, per file: a thumbnail (an object URL for pictures; the `doc` or `photo` glyph when the browser can't draw it, as with HEIC), the name in `<bdi>`, and "Photo · 363 KB"-style meta. In Combine mode each row shows its position in a `badge` (`accent`, white figures).

**Behaviour** (app.js + motion.js):
- Drag the handle: the row lifts (`.lifted`: scale 1.02, `shadow-lift`, `radius-lifted`), follows the pointer 1:1 from where it was grabbed, and rubber-bands past the first and last rows. The other rows slide out of the way on springs. On release the row settles with the pointer's velocity handed to the spring.
- Focused handle + ↑/↓ moves a row; moves are animated (FLIP) and announced.
- Remove collapses the row's height on a spring while it fades.
- New rows slide in (`.entering`).

Icon buttons: 40px targets (`size-icon-button`), glyph `label-3` at rest (2.2:1, below 3:1: kept from the source), `label-2` on hover, × turns `red-text`.
