# NavigationBar

A sticky bar of trailing buttons that turns frosted, and shows the page title, once the large title scrolls under it.

**Use** once per page, above `main`. The page provides the title text, up to three trailing buttons (`nav-btn`, or `nav-btn icon` for a glyph only) and the hero with the large title.

**Behaviour** (app.js): on scroll, set `--bar-o` (0→1 over the first 14px), and `--title-o` / `--title-y` (fade and rise 8px as the large title passes under the bar) on `.navbar`; set `--large-o` on `.large-title`. Never animate with a timer: the values follow the scroll position.

- Bar fill is `bar` under `saturate(180%) blur(20px)` with a 0.5px `separator` line; solid `bg` when the user reduces transparency.
- Buttons are `link` blue, 36px (`size-nav-button`), pressed to scale .92 on `fill-3`.
- On phones the language button drops its label and becomes an icon.
- Do: give icon-only buttons an `aria-label` and `title`. Don't: put more than three buttons in the bar, or a filled button.
