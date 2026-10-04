# Switch

An on/off control at the end of a row, drawn as the iOS switch.

**Use** for options that take effect without a confirm button, and never for a safeguard: the original-table picture in each Word file is always on, so it has no switch. The page provides the row label; use a native `<input type="checkbox" class="switch" role="switch">` inside the `label.row` so the whole row toggles it.

- Track `green` when on, `switch-off` when off; knob white with `shadow-knob`; on/off is also told by the knob's side.
- Pressing stretches the knob 27→33px; it settles with a bouncy spring curve. Mirrors in right-to-left.
- Size: `size-switch-w` × 31px.

**A set of choices** (the Output section: Searchable PDF, Markdown File, Pictures and Figures, Tables as Word Files): one switch per row, each with its file kind's tile (the same tiles as the Download rows). At least one stays on: switching off the last one springs it back on and the footer says "Keep at least one switched on." The footer lists what is on ("You get one ZIP: a searchable PDF and a Markdown file."). A setting that only shapes one choice sits in its own group below the footer and is hidden while that choice is off.
