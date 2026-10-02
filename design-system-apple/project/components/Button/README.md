# Button

The app's buttons: one **filled** primary action per screen, **tinted** secondary actions, and **plain** text buttons.

**Use**:
- `btn btn-filled btn-large`: the one action the screen is for ("Convert 4 Files", "Download All (ZIP)"). Full width, `size-row` tall, `radius-group`, `accent` with white text (4.7:1).
- `btn btn-tinted btn-small`: secondary actions next to content ("Cancel", "Check"). `accent-tint` with `link` text, a 34px pill.
- `btn btn-plain`: low-emphasis actions ("Convert Other Files", a sheet's "Done"). `link` text, a `fill-4` wash on hover.

Labels are verbs in Title Case; a count when it helps ("Convert 4 Files"). An optional 20px glyph leads. Pressed buttons scale to .97 at once and spring back; disabled filled buttons turn `fill-3` with `label-2` text (exempt from contrast rules) and ignore the pointer.
