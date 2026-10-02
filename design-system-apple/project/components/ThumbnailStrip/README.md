# ThumbnailStrip

A horizontally scrolling row of picture thumbnails, each a link that opens the full image.

**Use** for the pictures and figures cut out of a document. The page provides each image URL and file name. With none, show an `empty-note` ("No pictures or figures were found.") in the group instead.

- 148px columns, 112px tall, `object-fit: contain` on `paper` (white in both themes), `radius-segmented`, 0.5px `separator` ring; scroll-snaps to each thumbnail; 16px padding.
- Captions: `caption` in `label-2`, one line, ellipsis, the file name in `<bdi>`.
- Pressed thumbnails scale to .96.
