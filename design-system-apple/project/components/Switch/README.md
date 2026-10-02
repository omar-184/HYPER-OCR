# Switch

An on/off control at the end of a row, drawn as the iOS switch.

**Use** for options that take effect without a confirm button, and never for a safeguard: the original-table picture in each Word file is always on, so it has no switch. The page provides the row label; use a native `<input type="checkbox" class="switch" role="switch">` inside the `label.row` so the whole row toggles it.

- Track `green` when on, `switch-off` when off; knob white with `shadow-knob`; on/off is also told by the knob's side.
- Pressing stretches the knob 27→33px; it settles with a bouncy spring curve. Mirrors in right-to-left.
- Size: `size-switch-w` × 31px.
