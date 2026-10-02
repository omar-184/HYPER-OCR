# ProgressBar

A 6px track with an `accent` fill that shows how far a conversion has got.

**Use** inside the ProgressCard. Set `--p` (0–1) on the fill; app.js drives it with a spring (`response` .6) so jumps glide. Add `.indeterminate` while the length is unknown (uploading, loading the model): a 32% segment wanders across. Give the track `role="progressbar"` and `aria-valuenow`.

- Track `fill-3`, `radius-bar`; the fill carries a soft moving sheen.
- Grows from the start edge (right in right-to-left).
