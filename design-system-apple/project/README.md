The interface of HYPER-OCR, an offline app that turns scanned PDFs and photos of pages into searchable PDFs, Markdown, pictures and Word tables. It follows Apple's own app conventions: inset grouped lists on a grey ground, a large title that folds into a frosted bar, system colours with a light and a dark value, the system font, and spring motion that can be interrupted. It runs in English and Arabic, left to right and right to left, in a desktop or phone browser.

Use `tokens.css` for every colour, font stack, spacing, radius and shadow, `components/bundle.css` for the components (class names below), and `components/bundle.js` (`window.AppleStyle`) for springs and gestures.

## Content

- **Plain and short.** Say what happens: "Convert 4 Files", "Download All (ZIP)", "Check". Buttons are verbs in Title Case; counts appear when they help.
- **Section headers** are short nouns ("Files", "Text recognition", "Output"), shown uppercase in English. **Footers** explain a consequence in one sentence: "You get one ZIP: a searchable PDF, a Markdown file, an Images folder and a Tables folder with one Word file per table."
- **Never overstate accuracy.** Every extracted number is a draft: the results screen and every Word table say "Every number HYPER-OCR reads is unverified" and point to the original. Don't add wording, colours or badges that suggest some values are safe.
- **Errors** say what went wrong and what to do, naming the file: "“notes.txt” isn’t a PDF or a picture. Choose PDF, JPG, PNG, HEIC, TIFF, WebP or BMP files." No apologies, no codes.
- **Status** uses the present tense and names what will happen: "Tesseract will read the pages on this computer’s processor."; an error names the fix: "Tesseract isn’t installed. Run the setup again."
- **Typography of text:** curly quotes and apostrophes (“ ” ’), "·" between facts ("Photo · 363 KB"), "…" for work in progress ("Installing…"), a non-breaking space between a number and its unit ("15 s").
- **No emoji.** Glyphs come from the icon set.
- **Counts** use plural rules, never "1 pages": `Intl.PluralRules` picks the form; Arabic has six ("صفحة واحدة", "صفحتان", "3 صفحات", "11 صفحة").
- **Numbers** use Western digits in both languages.

## Colour

- Lay the page on `bg`; put content in groups on `surface`. Inside a sheet use `sheet-bg` and `sheet-group`.
- Text: `label` for primary, `label-2` for everything secondary (headers, footers, values, subtitles). `label-3` is for glyph hints only (chevrons, × and handles at rest), never for text.
- Blue has two jobs: `accent` fills (the one filled button, the progress fill, order badges, focus ring); `link` colours blue text and glyphs on any ground. Tinted buttons use `accent-tint` behind `link`.
- Meaning: `green-text` for success, `orange` for warning glyphs, `red-text` for errors; `green` only as a fill (the on-switch, the done check).
- Row icon tiles use the six `tile-*` colours, one per meaning, always with a white glyph. They are decoration: the row label carries the meaning.
- Hairlines are 0.5px `separator`; cards get `shadow-edge` instead of a border.
- `paper` stays white in dark: scanned pages and pictures are paper.
- Contrast: every text pair holds 4.5:1 in both themes (see each token's note). Pairs kept from the app that miss: `orange` glyphs in light (2.0:1), `label-3` glyphs (2.2:1), white on `tile-green` and `tile-orange` (2.2:1), and `link` on `accent-tint` inside a dark sheet (3.7:1). Each has text or a label beside it that carries the meaning.

## Type

- One family, the system's: `--font-text` for text up to 19px, `--font-display` from 20px and for titles (SF Pro Text/Display on Apple devices, Segoe UI Variable on Windows, Noto Sans and Noto Sans Arabic elsewhere). `--font-rounded` only for numbers in stat tiles and badges; `--font-mono` only for the Markdown preview.
- Use the scale's styles, each with its own tracking: `large-title` 34/700 (30 on phones), `title-1` 28/700, `title-2` 22/700, `title-3` 20/600, `nav-title` 17/600, `body` 17/400, `headline` 17/600, `callout` 16, `subheadline` 15, `segment` 14/500, `footnote` 13, `section-header` 13 uppercase, `caption` 12. Body text is 17px, as on iOS.
- Tracking tightens as size grows (−0.026em at 34px, −0.022em at 17px, −0.006em at 13px); uppercase headers open up to +0.02em.
- Arabic: never letter-spaced, never uppercased, line height 1.55, section headers 14px.
- Figures that line up (sizes, percents, stats, badges) use tabular numerals.

## Layout

- One column, at most `width-content` (760px) wide, `space-gutter` (16px) from the screen edges, with the safe areas added.
- Order: navigation bar, hero (app icon, large title, one-sentence subtitle), then sections `space-section` (32px) apart: Files, Text recognition, Output, then the main button `space-start` (30px) below.
- Rows are at least `size-row` (52px) tall with `space-row-y` and `space-gutter` padding. Separators start at the label: `inset-separator` (56px) after a tile, `inset-separator-file` (72px) after a thumbnail.
- Section header to group `space-header` (7px), group to footer `space-footer` (8px), group to group `space-group` (24px).
- During a conversion the setup sections give way to the ProgressCard; after it, the DoneCard, notices and the documents follow in that order.
- Phones (≤640px): the large title is 30px, stats go two across, the language button shows only its globe, sheets become bottom sheets, and the download button moves into the MobileBar.

## Shape, depth and materials

- Corners: `radius-group` (14px) for groups, notices and large buttons; `radius-tile` (7px) on 28px tiles; pills are half their height (`radius-pill`); `radius-sheet` (18px) for sheets; the app icon is a 22.5% squircle.
- Depth comes from shadows only where something floats: `shadow-lift` on a dragged row, `shadow-sheet` on a sheet, `shadow-knob` on the switch knob, `shadow-thumb` on the segmented thumb, `shadow-paper` under the page being scanned, `shadow-icon` under the app icon. Groups sit flat.
- The navigation bar and the phone bottom bar are frosted: `bar` under `saturate(180%) blur(20px)`. The scrim behind sheets is black at 35%.

## States

- Hover (pointer devices): a `fill-4` wash on rows and plain buttons.
- Press: rows fill with `pressed` instantly; buttons scale to .97 (nav buttons .92, icon buttons .88) and spring back.
- Disabled: filled buttons turn `fill-3` with `label-2` text and ignore the pointer.
- Focus: a solid 3px `accent` outline, 2px outside (inside rows, 3px inset). It holds 3:1 or more on every ground.
- Selected: segmented thumb on `seg-thumb`; checked rows show a `link` checkmark.

## Motion

Springs, not durations: see the Motion section. Every animation starts from what is on screen now, so it can be grabbed or reversed. Use `damping` 1 (no bounce) for UI; overshoot only after a flick or as a small reward (the done check, a checkmark, the switch knob).

## Iconography

- 23 line icons on a 24px grid, stroke 1.8, round caps and joins, no fills (one half-disc in `appearance`), kept as an SVG sprite and drawn in `currentColor`.
- Sizes: 21px in the nav bar, 18px in tiles (white, stroke 2) and icon buttons, 20px in buttons and notices, 14–15px in footers.
- The app icon is a blue squircle with a white page and scan corners; never redraw or recolour it.
- No emoji, no filled or duotone icons.

## Accessibility

- With Reduce Motion, springs jump to their end, entrance animations and the scan line are off, and only short fades remain.
- With Reduce Transparency, the bars are solid `bg`.
- With Increase Contrast, separators, `label-2` and card edges get stronger values.
- Every icon-only button has a label; switches use `role="switch"`, segmented controls `role="radiogroup"`, checklists `role="checkbox"`; moves and results are announced in a live region.

## Right to left and Arabic

- Set `dir="rtl"` and `lang="ar"`; layout uses logical properties, so rows, separators, switches, the progress fill and chevrons mirror by themselves (`:dir(rtl)` flips the chevrons and switch knob).
- Wrap a name that may be in the other script in `<bdi>` when it stands alone, or between U+2068 and U+2069 inside a translated sentence, so it can't reorder the sentence around it.
- Product names never break at their hyphen (U+2011): Unlimited‑OCR, HYPER‑OCR.
