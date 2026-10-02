# Sheet

A modal panel for settings and details: centred on wide screens, a bottom sheet with a grabber on phones.

**Use** for secondary content the user opens and dismisses (About, the language list). The page provides the title, the body (grouped lists, `section-header`s, a `segmented` control) and the element that opened it, to return focus to.

**Behaviour** (app.js + motion.js):
- Opens with a spring (`response` .4, no overshoot): from `scale(.94)` and transparent on wide screens, sliding up from below on phones. The scrim (`rgba(0,0,0,.35)`) fades with it.
- Phones: drag the grabber or title bar down; the sheet follows the finger 1:1, resists upwards (rubber band), and closes if the momentum-projected position passes 45% of its height, otherwise springs back with the finger's velocity.
- Escape and **Done** close it; Tab is kept inside; focus returns to the opener. The page behind is `inert`.
- Groups inside use `sheet-group` (one step lighter than `sheet-bg` in dark).

Do: one sheet at a time. Don't: put a primary task (converting files) in a sheet.
