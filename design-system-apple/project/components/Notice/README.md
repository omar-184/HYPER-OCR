# Notice

A rounded banner with a leading glyph that reports an error, a warning or a note about the result.

**Use** under the section it concerns. The page provides one or two sentences: what happened and what to do, with file names isolated (`<bdi>`, or U+2068/U+2069 inside translated text).

- `notice error`: whole text in `red-text`, `warn` glyph; `role="alert"`.
- `notice warn`: text in `label`, `warn` glyph in `orange` (2.0:1 in light: the text carries the meaning).
- `notice info`: `info` glyph in `link`.
- `surface`, `radius-group`, 12×16px padding, `subheadline` style, 12px above.
