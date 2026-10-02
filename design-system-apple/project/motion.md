# Motion

Motion follows Apple's "Designing Fluid Interfaces": springs described by **damping** (1 = no overshoot) and **response** (roughly the seconds to arrive), always starting from the current value and velocity. `components/bundle.js` provides them as `window.AppleStyle`.

## The tools

- `new AppleStyle.Spring(value, {damping = 1, response = .4, precision})`: `.to(target, {velocity})` returns a promise and retargets from wherever it is now, keeping its velocity; `.jump(v)` sets a value without motion; `.stop()` holds it; `.onChange(fn)` is called every frame with the value and velocity. Under Reduce Motion, `.to()` jumps.
- `AppleStyle.project(velocity, rate = .998)`: where a flick would come to rest (px). Use it to decide whether a release dismisses or springs back.
- `AppleStyle.rubberband(overshoot, dimension, constant = .55)`: the distance to show past a boundary, so drags slow before they stop.
- `new AppleStyle.VelocityTracker()`: `.add(y)` on every pointer move, `.velocity()` (px/s over the last 100 ms) on release.
- `AppleStyle.reduced()`: true when the user asks for reduced motion.

## The springs in use

| What | damping | response | Notes |
| --- | --- | --- | --- |
| Segmented thumb (position, width) | 1 | .32 | Two springs; a finger can slide across the track |
| Sheet open and close | 1 | .40 | Wide: scale .94→1 and fade; phone: slides up. Close keeps the finger's velocity |
| Sheet springing back after a short pull | .85 | .35 | Starts with the finger's velocity |
| Dragged row settling | 1, or .82 after a fast flick | .35 | The pointer's velocity is handed to the spring: no seam |
| Neighbouring rows making room | 1 | .35 | Retarget as the dragged row passes their centres |
| Lift of a dragged row | 1 | .25 | Scale 1 → 1.02 with `shadow-lift` |
| Removed row collapsing | 1 | .30 | Height and opacity together |
| Disclosure opening | 1 | .40 | Height and opacity; reversible mid-way |
| Progress fill | 1 | .60 | Glides between reported percentages |
| Stat count-up | 1 | .90 | 150 ms delay, then 60 ms between tiles |

## CSS curves

Where CSS animates on its own, it uses two springs sampled into `linear()` curves (in `bundle.css`): `--ease-spring` (damping 1) for entrances, the chevron turn and button release, and `--ease-bounce` (a small overshoot) for the switch knob, the done check and the drop icon. Entrances rise 14px and fade over .7–.8 s, 60 ms apart.

## Rules

- Drags follow the pointer 1:1 from where it was grabbed; never snap the grabbed point to the centre.
- Past a boundary, rubber-band; never stop dead.
- On release, decide with `project()`, then hand the velocity to the spring.
- No motion on a timer that the user did not cause, except the scan line and the indeterminate bar, which show that work is happening.
- Theme changes cross-fade colours over .35 s.
