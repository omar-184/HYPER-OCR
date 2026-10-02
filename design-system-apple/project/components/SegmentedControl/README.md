# SegmentedControl

Two or three mutually exclusive choices in one track, with a white thumb that slides to the selection.

**Use** for a mode that changes how the rest of the screen behaves (Combine into One / Each Separately; Automatic / Light / Dark). The page provides the segments (`button role="radio"` with `data-value`) and a `.segmented-thumb` span first in the track; follow it with a one-line footer explaining the selected mode.

**Behaviour**: the thumb's `--seg-x` and `--seg-w` are driven by two `AppleStyle.Spring`s (`response` .32, no overshoot) that start from where the thumb is, so quick changes redirect it. A finger can slide across the track to change the selection. Arrow keys move it (reversed in right-to-left); only the selected segment is in the tab order.

Track `fill-3`, `radius-segmented`; thumb `seg-thumb`, `radius-segment`, `shadow-thumb`; labels `segment`, 600 when selected.
