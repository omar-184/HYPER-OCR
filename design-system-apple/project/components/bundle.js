/* @ds-bundle: {"format":4,"namespace":"AppleStyle","components":[]} */
/* Motion for HYPER-OCR, after Apple's "Designing Fluid Interfaces":
 * springs described by damping ratio and response (not duration), always
 * starting from the current on-screen value and velocity, so any motion can be
 * grabbed and redirected mid-flight; momentum projection; rubber-banding. */
(function (H) {
  'use strict';

  const reducedQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  const reduced = () => !!(reducedQuery && reducedQuery.matches);

  class Spring {
    /* damping 1 = no overshoot (the default for UI); ~0.8 only after a flick or throw.
     * response = seconds to reach the target, roughly; not a fixed duration. */
    constructor(value, opts = {}) {
      this.value = value;
      this.target = value;
      this.velocity = 0;
      this.damping = opts.damping ?? 1;
      this.response = opts.response ?? 0.4;
      this.precision = opts.precision ?? 0.05;
      this.listeners = [];
      this.raf = 0;
      this.waiters = [];
      this.tick = this.tick.bind(this);
    }

    onChange(fn) {
      this.listeners.push(fn);
      fn(this.value, this.velocity);
      return this;
    }

    emit() {
      for (const fn of this.listeners) fn(this.value, this.velocity);
    }

    /* Retarget from wherever the value is now, keeping its velocity (no "brick wall"). */
    to(target, opts = {}) {
      if (opts.damping != null) this.damping = opts.damping;
      if (opts.response != null) this.response = opts.response;
      if (opts.velocity != null) this.velocity = opts.velocity;
      this.target = target;
      if (reduced()) {
        this.jump(target);
        return Promise.resolve();
      }
      const done = new Promise((resolve) => this.waiters.push(resolve));
      if (!this.raf) {
        this.last = performance.now();
        this.raf = requestAnimationFrame(this.tick);
      }
      return done;
    }

    jump(value) {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.value = this.target = value;
      this.velocity = 0;
      this.emit();
      this.settle();
    }

    stop() {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.target = this.value;
      this.settle();
    }

    settle() {
      const waiters = this.waiters;
      this.waiters = [];
      for (const w of waiters) w();
    }

    tick(now) {
      const dt = Math.min(0.064, (now - this.last) / 1000);
      this.last = now;
      const w0 = (2 * Math.PI) / this.response;
      const k = w0 * w0;
      const c = 2 * this.damping * w0;
      const steps = Math.max(1, Math.ceil(dt * 240));
      const h = dt / steps;
      for (let i = 0; i < steps; i++) {
        const a = k * (this.target - this.value) - c * this.velocity;
        this.velocity += a * h;
        this.value += this.velocity * h;
      }
      if (Math.abs(this.target - this.value) < this.precision && Math.abs(this.velocity) < this.precision * 10) {
        this.value = this.target;
        this.velocity = 0;
        this.raf = 0;
        this.emit();
        this.settle();
        return;
      }
      this.emit();
      this.raf = requestAnimationFrame(this.tick);
    }
  }

  /* Where a flick would come to rest (Apple's sample code; d ~ 0.998 is scroll feel). */
  function project(velocity, rate = 0.998) {
    return ((velocity / 1000) * rate) / (1 - rate);
  }

  /* Past a boundary, follow less and less: real things slow before they stop. */
  function rubberband(overshoot, dimension, constant = 0.55) {
    return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
  }

  /* Pointer velocity from the last ~100 ms of moves, in px/s. */
  class VelocityTracker {
    constructor() { this.samples = []; }
    add(value, time = performance.now()) {
      this.samples.push([time, value]);
      while (this.samples.length > 2 && time - this.samples[0][0] > 100) this.samples.shift();
    }
    velocity() {
      const s = this.samples;
      if (s.length < 2) return 0;
      const [t0, v0] = s[0];
      const [t1, v1] = s[s.length - 1];
      return t1 > t0 ? ((v1 - v0) / (t1 - t0)) * 1000 : 0;
    }
  }

  H.motion = { Spring, project, rubberband, VelocityTracker, reduced };
})(window.HOCR = window.HOCR || {});
window.AppleStyle = window.HOCR.motion;
