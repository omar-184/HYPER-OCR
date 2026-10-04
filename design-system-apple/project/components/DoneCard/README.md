# DoneCard

The card that opens the results: a drawn check, a one-line summary, up to four counts and the download button.

**Use** once, at the top of the results. The page provides the summary ("3 files · read by Tesseract in 15 s"; "1 file · taken from the PDF’s own text in 2 min 5 s" when no page needed OCR; past an hour, "2 h 14 min"), the totals (pages and words always; pictures and tables only when those files were chosen, `--n` sets the number of columns) and the ZIP link. Below it, the files that were not chosen have no rows or sections.

- The numbers notice (see Notice) always follows the card; the done announcement for screen readers includes it.
- The check disc (`green`) pops in with a bounce and its tick is drawn after it; the stat numbers count up on springs, 60ms apart; the card and what follows rise in one after another.
- Title `title-1`; summary `subheadline` in `label-2`; stat tiles `fill-4`, `radius-lifted`, numbers in `stat`, labels `footnote` in `label-2` (4.6:1). One column per count (`repeat(var(--n), 1fr)`); two on phones, where the download button moves to the MobileBar.
