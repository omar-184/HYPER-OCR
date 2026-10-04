# Section

An inset grouped list with an uppercase header above and an explanatory footer below: the page's basic building block.

**Use** for every group of settings or results. The page provides the header text (a short noun: "Files", "Text recognition"), the rows, and an optional footer sentence that explains a consequence.

- Header: `section-header` style in `label-2`, 16px in from the group's edge; 7px above the group. Arabic: no uppercase, 14px.
- Group: `surface` with `radius-group` and `shadow-edge`; no borders.
- Footer: `footnote` in `label-2`, 8px below. A **status footer** (`.section-footer.status`) leads with a glyph: `check` in `green-text` (ok) or, with the whole line in `red-text`, `warn` (error). A `warn` variant (`orange` glyph) exists for the experimental GPU engine's messages.
- Sections are 32px apart; groups inside one section 24px apart, also when the first group has a footer (`.section-footer + .group`).

Don't: put headers inside the group, or use bold for them.
