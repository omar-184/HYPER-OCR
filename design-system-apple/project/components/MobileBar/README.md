# MobileBar

A frosted bar fixed to the bottom of a phone screen that keeps the one main action (Download All) under the thumb.

**Use** only at phone widths (≤640px) and only on the results screen; on wider screens the same action sits in the done card. The page provides one filled button.

- Fill `bar` with `saturate(180%) blur(20px)`, a 0.5px `separator` line on top, padding includes the bottom safe area.
- The button is full width, 50px tall, `radius-group`.
- `main` gets 120px bottom padding on phones so content clears the bar.
