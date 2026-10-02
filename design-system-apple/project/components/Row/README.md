# Row

One line of a grouped list: an optional 28px icon tile, a label (with an optional subtitle) and a trailing value, control or glyph.

**Use** inside a `group`. The page provides the label, and per variant:
- **Picker** (`label.row` + `.row-value.select`): a native `<select>` styled as a trailing value with an up-down glyph.
- **Disclosure** (`button.row`): a value and a `chev` that opens a sheet.
- **Switch** (`label.row` + `input.switch`): see Switch.
- **Checkmark** (`button.row.lang-option`, `role="checkbox"`): a `check` in `link` that pops in with a bounce when `aria-checked="true"`; native names as a subtitle in `<bdi>`.
- **Download** (`a.row.file-row`): a red/grey/green tile, the file kind, the file name as a subtitle, a `down` glyph in `link`.
- **Action** (`button.row.row-action`): a plain `plus` and a `link` label.

Tiles: `size-tile`, `radius-tile`, white glyph at stroke 2 on `tile-blue`, `tile-gray`, `tile-green`, `tile-indigo`, `tile-orange` or `tile-red`, one colour per meaning. Hairlines between rows start at the label (`inset-separator`; 16px when there is no tile). Rows are at least 52px tall; pressed rows fill with `pressed`.

Do: wrap names that may be Latin inside Arabic (or the reverse) in `<bdi>`. Don't: put two controls in one row.
