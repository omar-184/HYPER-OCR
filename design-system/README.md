A calm, practical system for offline tools that turn a messy file into a clean one. One page holds a column of numbered step cards; the register green marks the one thing to do next. Built for English and Arabic alike: every layout mirrors for right-to-left.

## Content fundamentals

- Speak to the person doing the work, in plain words: "Choose or drop Excel files", "Match the columns", "Review students". Steps are short imperative phrases in sentence case, never Title Case.
- Say what will happen and where the data stays. The footer line is a promise, keep it: "Offline tool: no internet, no AI, no accounts. Data stays on this computer."
- Hints explain the next action and the reason in one or two sentences: "Matches are guessed from the column titles and remembered for next time."
- Errors say what went wrong and how to fix it, with no apology: "Old .xls files can't be read. Open the file in Excel and use "Save As" → "Excel Workbook (.xlsx)", then choose it again."
- Counts are concrete: "{n} students will be written into the register (room for {slots})." Use `«»` around quoted values in both languages.
- Every string exists in English and Arabic. Arabic is written natively, not transliterated; field labels may carry the Arabic term in brackets in English mode ("Section (الشعبة)").
- No emoji, no exclamation marks, no marketing words.

## Visual foundations

**Colour.** Neutrals carry the page: `bg` behind, `card` for each step, `field` inside inputs. `text` for reading, `muted` for hints, labels and the footer. `accent` (register green) is the only brand hue: primary buttons, the selected pill, link buttons, step-number digits, a matched field and the focus ring. Text on an accent fill is `accent-ink`, never literal white (the dark theme's accent is light and takes near-black ink). `accent-soft` tints step discs, badges and the drop zone under a dragged file.

**State colours** are a fixed trio, each with a word beside it: `ok-bg`/`ok-ink` (done, combined), `warn-bg`/`warn-ink`/`warn-line` (looks wrong: please check), `error-bg`/`error-ink` (could not read). Values the tool changed by itself are blue: `fixed-bg` with a `fixed-line` underline. Messages with a start border use `border-inline-start: 4px`, so the stripe moves to the right in Arabic.

**Dark theme.** Pure black `bg` (OLED friendly) with graphite `card`, softened `text` and a lighter `accent`. The theme button cycles Auto → Dark → Light; Auto follows the system and sets no `data-theme` attribute. Printed-page previews stay white paper (`sheet`, `sheet-ink`) in both themes.

**Type.** One system stack (`sans`): Segoe UI, system-ui, Tahoma, Arial. These faces render Arabic well on Windows, macOS and Android without shipping font files, which keeps the tool fully offline. Scale: `title` 24, `step-title` 18, `body` 15, `hint` 14, `small` 13, `micro` 12. Under 700px use `title-phone`, `step-title-phone` and `body-phone` (16px, so iPhone Safari does not zoom into fields). Buttons are `button` (600). Digits that line up use tabular numbers.

**Layout.** A single column, max `page-max` (1100px), `space-24` side gutter (12px on phones), `space-16` between cards. Each step is a `card` with `radius`, a 1px `line` border and `space-18`/`space-20` padding. Cards that are not reachable yet stay `hidden` until the step before them is done, so the page grows as the work progresses. Field groups use auto-fit grids (`minmax(190px, 1fr)` for short fields, `minmax(320px, 1fr)` for groups) and collapse to one column under `breakpoint-phone`.

**Borders, not shadows.** Cards and lists are outlined with `line`. Interactive outlines use `line-strong` (3:1 on every surface). The one shadow (`shadow`) sits under printed-page previews only.

**Radii.** `radius` (12px) cards and drop zone, `radius-control` (10px) buttons and lists, `radius-field` (8px) fields and messages, `radius-cell` (6px) table inputs, `radius-pill` for toggles, tabs and badges, a full circle for step numbers.

**Focus and touch.** Focus is `outline: 3px solid var(--accent)` with a 2px offset on every control, the drop zone included. Tap targets are at least `control` (40px); buttons and phone fields `control-touch` (44px).

**Phones.** Under 700px the top bar stacks, buttons in a row go full width, tables turn into one card per row with the column name above each value, and the export actions move to a fixed bottom bar (`mobile-bar`) padded by the safe-area inset.

**Right-to-left.** Use logical properties only (`margin-inline-start`, `inset-inline-end`, `padding-inline-start`, `text-align: start`). User text inputs take `dir="auto"`; numeric and year fields take `dir="ltr"`. Wrap mixed-direction values in `<bdi>`.

**Motion.** Almost none: hover brightens a primary button (`filter: brightness(1.08)`) and moves a secondary border to `accent`. Respect `prefers-reduced-motion`.

## Iconography

The source draws its few icons as inline SVG in `currentColor` at 18px (the half-filled circle on the theme button). Text glyphs stand in elsewhere: `×` for remove, `+` for add, `→` in instructions. There is no icon font and no logo; the product name is set in plain `title` type.

## Intentional additions

Four components were added for HYPER-OCR (a scanned-PDF converter built on this system), using only the tokens above:

- **ProgressBar**: OCR runs for minutes, so a long job shows an `accent` bar on `accent-soft` with "Page 3 of 12" in tabular numbers.
- **StatChip**: read-only counts (pages, pictures, tables) in the shape of a `tab`, outlined with `line` instead of `line-strong` because it is not a control.
- **ThumbGrid**: extracted pictures on `sheet` paper with their file names.
- **TextPreview**: a scrolling monospace block for Markdown output and logs, `unicode-bidi: plaintext` so Arabic lines read right-to-left.
