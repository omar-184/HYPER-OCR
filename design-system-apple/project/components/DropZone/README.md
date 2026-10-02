# DropZone

A dashed target inside the Files group that opens the file picker on click and accepts files dropped anywhere on the window.

**Use** while no file is chosen; once there are files it is replaced by the FileList and an "Add More Files" action row. The page provides the title ("Choose PDFs or Photos"), a hint ("or drop them here") and a visually hidden `<input type="file" multiple>` inside the `label.drop`.

- Dashed 1.5px `separator` border, `radius-lifted`, inset 10px from the group.
- Icon well: 56px, `accent-tint`, `link` glyph (`scan`).
- While files are dragged over the window: `.drop.over` turns the border solid `accent`, fills `accent-tint-2` and lifts the icon 4px at 1.12 scale with a bounce. Pressing scales the zone to .985.
- Keyboard focus shows the 3px `accent` ring around the whole zone.
