# ProgressCard

The card shown while files convert: a live preview of the page being read with a scan line, the stage, the file, the bar and the time left.

**Use** in place of the setup sections during a conversion. The page provides the preview image (the page being read, or the first photo), the stage title ("Reading page 3 of 12"), the file line ("scan.pdf · file 2 of 3"), the percent and the estimate, from the time each page took: "About 40 s left", "About 25 min left", and from 90 minutes in hours, to the quarter hour ("About 2 h 30 min left") or, from 5 hours, to the hour ("About 10 h left"), never "597 min".

- Two columns: a 128px A4 paper (`paper`, `radius-segment`, `shadow-paper`; 92px on phones) and the info. A blue scan line sweeps down the page every 2.6s; `.idle` stops it outside the reading stage.
- Title `title-3`; file line `subheadline` in `label-2`; meta `footnote`, tabular figures.
- **Cancel** is a tinted small button.
