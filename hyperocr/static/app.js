/* HYPER-OCR interface. Talks only to this computer (127.0.0.1). */
(function (H) {
  'use strict';

  const { t } = H.i18n;
  const { Spring, project, rubberband, VelocityTracker, reduced } = H.motion;
  const $ = (id) => document.getElementById(id);
  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem('hocr.' + key)); } catch { return null; } },
    set(key, value) { try { localStorage.setItem('hocr.' + key, JSON.stringify(value)); } catch { /* storage may be blocked */ } },
  };
  const ENGINE_NAMES = { unlimited: 'Unlimited-OCR', 'unlimited-server': 'Unlimited-OCR', tesseract: 'Tesseract' };
  const OUTPUTS = ['pdf', 'markdown', 'images', 'tables'];
  const INFO_NOTES = ['ownText'];
  const IMAGE_EXT = /\.(jpe?g|png|tiff?|bmp|webp|gif|heic|heif)$/i;
  const STAGE_PERCENT = { uploading: 0, queued: 1, opening: 2, 'loading-model': 4, 'writing-pdf': 93, 'writing-markdown': 96, packing: 98, done: 100 };
  const phone = () => window.matchMedia('(max-width: 640px)').matches;
  const isRtl = () => document.documentElement.dir === 'rtl';

  const state = {
    system: null, files: [], mode: store.get('mode') === 'separate' ? 'separate' : 'combine',
    job: null, pollTimer: 0, xhr: null, busy: false, timing: null, nextId: 1,
  };

  // ================================================================ helpers

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function icon(name, cls) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    if (cls) svg.setAttribute('class', cls);
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS(ns, 'use');
    use.setAttribute('href', '#i-' + name);
    svg.append(use);
    return svg;
  }

  // A name inside a translated sentence: isolated so a Latin name can't reorder Arabic text.
  const isolate = (text) => '\u2068' + text + '\u2069';
  // A name on its own line: <bdi> keeps its own direction but follows the page's alignment.
  function named(tag, cls, text) {
    const e = el(tag, cls);
    e.append(el('bdi', '', text));
    return e;
  }
  const listJoin = (items) => items.join(H.i18n.lang === 'ar' ? '، ' : ', ');
  // "1, 2 and 5" / "1 و2 و5"
  function listOf(items) {
    try { return new Intl.ListFormat(H.i18n.lang, { style: 'long', type: 'conjunction' }).format(items); } catch { return listJoin(items); }
  }
  // Runs of three or more pages as a range: "1–3, 5 and 7–2,831", not every page of a book.
  function pageList(pages) {
    const items = [];
    for (let i = 0; i < pages.length; i++) {
      let j = i;
      while (j + 1 < pages.length && pages[j + 1] === pages[j] + 1) j++;
      if (j - i >= 2) { items.push('\u2068' + H.i18n.num(pages[i]) + '\u2013' + H.i18n.num(pages[j]) + '\u2069'); i = j; }
      else items.push(H.i18n.num(pages[i]));
    }
    return listOf(items);
  }

  function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let n = bytes, u = 0;
    while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
    return (u ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + units[u];
  }

  function formatDuration(sec) {
    sec = Math.max(1, Math.round(sec));
    if (sec < 60) return t('seconds', { n: sec });
    if (sec < 3600) return t('minutes', { m: Math.floor(sec / 60), s: sec % 60 });
    return t('hours', { h: Math.floor(sec / 3600), m: Math.floor((sec % 3600) / 60) });
  }

  const live = el('div', 'sr-only');
  live.setAttribute('aria-live', 'polite');
  live.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)';
  document.body.append(live);
  const announce = (text) => { live.textContent = ''; setTimeout(() => { live.textContent = text; }, 30); };

  // ================================================================ appearance

  const THEMES = ['auto', 'light', 'dark'];
  let appearanceSeg = null;                  // the About sheet's control, made below
  const darkQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const themeMode = () => (THEMES.includes(store.get('theme')) ? store.get('theme') : 'auto');

  function applyTheme(animate) {
    const mode = themeMode();
    const root = document.documentElement;
    if (animate && !reduced()) {
      document.body.classList.add('theme-change');
      setTimeout(() => document.body.classList.remove('theme-change'), 400);
    }
    if (mode === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);
    const dark = mode === 'dark' || (mode === 'auto' && !!darkQuery && darkQuery.matches);
    $('theme-color').setAttribute('content', dark ? '#000000' : '#f2f2f7');
    $('theme-icon').setAttribute('href', mode === 'auto' ? '#i-appearance' : mode === 'dark' ? '#i-moon' : '#i-sun');
    const label = t('themeBtn', { mode: t('theme_' + mode) });
    $('theme-btn').setAttribute('aria-label', label);
    $('theme-btn').title = label;
    if (appearanceSeg) appearanceSeg.set(mode, false);
  }

  function setTheme(mode) {
    store.set('theme', mode);
    applyTheme(true);
  }

  $('theme-btn').addEventListener('click', () => setTheme(THEMES[(THEMES.indexOf(themeMode()) + 1) % THEMES.length]));
  if (darkQuery && darkQuery.addEventListener) darkQuery.addEventListener('change', () => applyTheme(true));

  // ================================================================ segmented controls

  class Segmented {
    constructor(root, value, onChange) {
      this.root = root;
      this.onChange = onChange;
      this.thumb = root.querySelector('.segmented-thumb');
      this.buttons = [...root.querySelectorAll('button')];
      this.x = new Spring(0, { response: 0.32, precision: 0.2 });
      this.w = new Spring(0, { response: 0.32, precision: 0.2 });
      this.x.onChange((v) => this.thumb.style.setProperty('--seg-x', v + 'px'));
      this.w.onChange((v) => this.thumb.style.setProperty('--seg-w', v + 'px'));
      for (const b of this.buttons) {
        b.addEventListener('click', () => this.set(b.dataset.value, true));
        b.addEventListener('keydown', (e) => this.key(e));
      }
      // Slide the selection by dragging across the control, as on iOS.
      root.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return;
        this.dragging = true;
      });
      root.addEventListener('pointermove', (e) => {
        if (!this.dragging || !(e.buttons & 1)) return;
        const b = this.buttons.find((x) => { const r = x.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right; });
        if (b && b.dataset.value !== this.value) this.set(b.dataset.value, true);
      });
      window.addEventListener('pointerup', () => { this.dragging = false; });
      new ResizeObserver(() => this.place(false)).observe(root);
      this.set(value, false);
    }

    set(value, user) {
      const changed = value !== this.value;
      this.value = value;
      for (const b of this.buttons) {
        const on = b.dataset.value === value;
        b.setAttribute('aria-checked', String(on));
        b.tabIndex = on ? 0 : -1;
      }
      this.place(user);
      if (user && changed && this.onChange) this.onChange(value);
    }

    place(animate) {
      const b = this.buttons.find((x) => x.dataset.value === this.value);
      if (!b || !b.offsetWidth) return;
      const x = b.offsetLeft, w = b.offsetWidth;
      if (animate && this.w.value) { this.x.to(x); this.w.to(w); } else { this.x.jump(x); this.w.jump(w); }
    }

    key(e) {
      const i = this.buttons.findIndex((b) => b.dataset.value === this.value);
      let step = 0;
      if (e.key === 'ArrowRight') step = isRtl() ? -1 : 1;
      if (e.key === 'ArrowLeft') step = isRtl() ? 1 : -1;
      if (!step) return;
      e.preventDefault();
      const next = this.buttons[(i + step + this.buttons.length) % this.buttons.length];
      this.set(next.dataset.value, true);
      next.focus();
    }
  }

  const modeSeg = new Segmented($('mode'), state.mode, (v) => { state.mode = v; store.set('mode', v); renderMode(); });
  appearanceSeg = new Segmented($('appearance'), themeMode(), (v) => setTheme(v));

  // ================================================================ language

  $('lang-btn').addEventListener('click', () => {
    store.set('lang', H.i18n.lang === 'ar' ? 'en' : 'ar');
    renderAll();
  });

  function renderAll() {
    const saved = store.get('lang');
    H.i18n.setLang(saved || ((navigator.language || '').startsWith('ar') ? 'ar' : 'en'));
    $('lang-label').textContent = t('langName');
    $('lang-btn').setAttribute('aria-label', t('langBtn'));
    $('about-btn').setAttribute('aria-label', t('aboutBtn'));
    $('about-btn').title = t('aboutBtn');
    $('mode').setAttribute('aria-label', t('modeLabel'));
    applyTheme(false);
    renderFiles(false);
    renderSystem();
    renderUpdate();
    if (state.job && state.job.state === 'done' && state.job.result) showResults(state.job, false);
    else if (state.job) renderJob(state.job);
    requestAnimationFrame(() => { modeSeg.place(false); appearanceSeg.place(false); });
  }

  // ================================================================ navigation bar: large title collapses on scroll

  let scrollQueued = false;
  function onScroll() {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      scrollQueued = false;
      const y = window.scrollY;
      const title = $('large-title');
      const nav = $('navbar');
      const navH = nav.offsetHeight;
      const titleBottom = title.getBoundingClientRect().bottom + y - navH;
      const barO = Math.min(1, Math.max(0, (y - 2) / 14));
      const titleO = Math.min(1, Math.max(0, (y - titleBottom + 18) / 18));
      nav.style.setProperty('--bar-o', barO.toFixed(3));
      nav.style.setProperty('--title-o', titleO.toFixed(3));
      nav.style.setProperty('--title-y', ((1 - titleO) * 8).toFixed(2) + 'px');
      title.style.setProperty('--large-o', (1 - titleO * 0.9).toFixed(3));
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  // ================================================================ system and settings

  async function loadSystem() {
    setStatus('', t('st_checking'));
    try {
      const resp = await fetch('/api/system', { cache: 'no-store' });
      state.system = await resp.json();
    } catch {
      setStatus('error', t('err_network'));
      return;
    }
    renderSystem();
  }

  const engineInfo = (id) => (state.system ? state.system.engines.find((e) => e.id === id) : null);

  function renderSystem() {
    const sys = state.system;
    if (!sys) return;
    const footer = $('upd-footer');                    // the desktop app updates through its installer
    footer.dataset.i18n = sys.desktop ? 'updFooterDesktop' : 'updFooter';
    footer.textContent = t(footer.dataset.i18n);
    const select = $('engine');
    for (const opt of select.options) {
      opt.textContent = t(opt.dataset.i18n);
      if (opt.value === 'auto') continue;
      const info = engineInfo(opt.value);
      opt.hidden = !info;
      opt.disabled = !info || !info.ok;
      if (info && !info.ok) opt.textContent = t('engUnavailable', { name: t(opt.dataset.i18n) });
    }
    const saved = store.get('engine');
    if (saved && !select.dataset.touched) {
      const opt = [...select.options].find((o) => o.value === saved && !o.disabled && !o.hidden);
      if (opt) select.value = saved;
    }
    if (select.selectedOptions[0] && select.selectedOptions[0].disabled) select.value = 'auto';
    for (const opt of $('dpi').options) opt.textContent = t(opt.dataset.i18n) + ' · ' + opt.value + ' dpi';
    const savedDpi = String(store.get('dpi') || '');
    if (['200', '300', '400'].includes(savedDpi) && !$('dpi').dataset.touched) $('dpi').value = savedDpi;
    if (store.get('furniture') === false) $('opt-furniture').checked = false;
    if (store.get('ownText') === false) $('opt-own-text').checked = false;
    renderOutputs();
    $('about-version').textContent = t('version', { v: sys.version });
    renderEngineStatus();
    renderLanguages();
    renderAboutEngines();
    updateStart();
  }

  function setStatus(kind, text) {
    const box = $('engine-status');
    box.className = 'section-footer status' + (kind ? ' ' + kind : '');
    box.replaceChildren();
    if (kind === 'ok') box.append(icon('check'));
    if (kind === 'warn' || kind === 'error') box.append(icon('warn'));
    box.append(el('span', '', text));
  }

  function renderEngineStatus() {
    const sys = state.system;
    const choice = $('engine').value;
    const tess = engineInfo('tesseract');
    const gpu = engineInfo('unlimited');
    const effective = choice === 'auto' ? sys.auto : choice;
    if (effective === 'unlimited') setStatus('ok', t('st_gpuReady', { detail: (gpu && gpu.detail) || 'GPU' }));
    else if (effective === 'unlimited-server') setStatus('ok', t('st_serverReady', { detail: (engineInfo('unlimited-server') || {}).detail || '' }));
    else if (!tess || !tess.ok) setStatus('error', t('err_tesseractMissing'));
    else if (choice === 'auto' && gpu && !gpu.ok && H.i18n.has('st_' + gpu.reason)) setStatus('warn', t('st_' + gpu.reason, { detail: gpu.detail || '' }));
    else setStatus('ok', t('st_cpu'));
  }

  function currentLanguages() {
    const sys = state.system;
    const saved = store.get('languages');
    const valid = Array.isArray(saved) ? saved.filter((l) => sys.languages.includes(l)) : [];
    if (valid.length) return valid;
    const byUi = sys.defaults.languagesByUi;          // until chosen: the interface language's own
    return (byUi && byUi[H.i18n.lang]) || sys.defaults.languages;
  }

  function renderLanguages() {
    const sys = state.system;
    const chosen = currentLanguages();
    const names = chosen.map((c) => H.i18n.langName(c));
    $('langs-value').textContent = !sys.languages.length ? t('noLangs')
      : names.length > 2 ? t('langsMore', { first: listJoin(names.slice(0, 2)), n: names.length - 2 }) : listJoin(names);
    const list = $('langs-list');
    list.replaceChildren();
    const order = ['eng', 'ara'];
    const langs = [...sys.languages].sort((a, b) => {
      const ia = order.indexOf(a), ib = order.indexOf(b);
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      return H.i18n.langName(a).localeCompare(H.i18n.langName(b));
    });
    for (const code of langs) {
      const row = el('button', 'row lang-option');
      row.type = 'button';
      row.setAttribute('role', 'checkbox');
      row.setAttribute('aria-checked', String(chosen.includes(code)));
      const label = el('span', 'row-label');
      label.append(el('span', '', H.i18n.langName(code)));
      const native = H.i18n.nativeName(code);
      if (native && native !== H.i18n.langName(code)) label.append(named('small', 'native', native));
      row.append(label, icon('check', 'check'));
      row.addEventListener('click', () => {
        const now = currentLanguages();
        const on = now.includes(code);
        if (on && now.length === 1) return;          // at least one language
        store.set('languages', on ? now.filter((c) => c !== code) : [...now, code]);
        renderLanguages();
        list.querySelectorAll('.lang-option')[langs.indexOf(code)].focus();
      });
      list.append(row);
    }
  }

  $('langs-row').addEventListener('click', () => sheets.open('langs-sheet', $('langs-row')));
  $('engine').addEventListener('change', () => {
    $('engine').dataset.touched = '1';
    store.set('engine', $('engine').value);
    renderEngineStatus();
    updateStart();
  });
  $('dpi').addEventListener('change', () => { $('dpi').dataset.touched = '1'; store.set('dpi', Number($('dpi').value)); });
  $('opt-furniture').addEventListener('change', () => store.set('furniture', $('opt-furniture').checked));
  $('opt-own-text').addEventListener('change', () => store.set('ownText', $('opt-own-text').checked));

  // ================================================================ outputs

  const outputSwitches = () => [...document.querySelectorAll('#outputs [data-output]')];

  function currentOutputs() {
    const saved = store.get('outputs');
    const valid = Array.isArray(saved) ? OUTPUTS.filter((o) => saved.includes(o)) : [];
    return valid.length ? valid : OUTPUTS.slice();
  }

  function renderOutputs() {
    const chosen = currentOutputs();
    for (const sw of outputSwitches()) sw.checked = chosen.includes(sw.dataset.output);
    $('output-footer').textContent = t('outputFooter', { list: listOf(chosen.map((o) => t('out_' + o))) });
    $('furniture-group').hidden = !chosen.includes('markdown');     // it only shapes the Markdown
  }

  for (const sw of outputSwitches()) {
    sw.addEventListener('change', () => {
      const chosen = outputSwitches().filter((x) => x.checked).map((x) => x.dataset.output);
      if (!chosen.length) {                        // the last one stays on
        sw.checked = true;
        $('output-footer').textContent = t('outputOne');
        announce(t('outputOne'));
        return;
      }
      store.set('outputs', chosen);
      renderOutputs();
    });
  }

  function engineUsable() {
    const sys = state.system;
    if (!sys) return false;
    const choice = $('engine').value;
    if (choice === 'auto') {
      if (sys.auto !== 'tesseract') return true;
      const tess = engineInfo('tesseract');
      return !!(tess && tess.ok);
    }
    const info = engineInfo(choice);
    return !!(info && info.ok);
  }

  function updateStart() {
    const n = state.files.length;
    $('start').disabled = !n || !engineUsable() || state.busy;
    $('start').querySelector('span').textContent = n > 1 ? H.i18n.plural('startFiles', n) : t('start');
    $('start-hint').hidden = n > 0;
  }

  // ================================================================ files

  function kindOf(file) {
    if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) return 'pdf';
    if ((file.type || '').startsWith('image/') || IMAGE_EXT.test(file.name)) return 'image';
    return null;
  }

  function addFiles(list) {
    $('file-error').hidden = true;
    const bad = [];
    const added = [];
    for (const file of list) {
      const kind = kindOf(file);
      if (!kind) { bad.push(file.name); continue; }
      const item = { id: state.nextId++, file, kind, name: file.name, size: file.size, url: '' };
      if (kind === 'image') item.url = URL.createObjectURL(file);
      state.files.push(item);
      added.push(item.id);
    }
    if (bad.length) {
      const box = $('file-error');
      box.replaceChildren(icon('warn'), el('span', '', t('fileNotSupported', { name: bad.map(isolate).join('”, “') })));
      box.hidden = false;
    }
    renderFiles(true, added);
  }

  function renderFiles(animate, added = []) {
    const list = $('file-list');
    const has = state.files.length > 0;
    list.hidden = !has;
    $('drop').hidden = has;
    $('add-more').hidden = !has;
    list.replaceChildren();
    state.files.forEach((item, i) => list.append(fileRow(item, i, animate && added.includes(item.id))));
    renderMode();
    updateStart();
  }

  function fileRow(item, index, entering) {
    const li = el('li', 'file-item' + (entering ? ' entering' : ''));
    li.dataset.id = item.id;
    const thumb = el('span', 'file-thumb');
    if (item.url) {
      const img = new Image();
      img.alt = '';
      img.src = item.url;
      img.onerror = () => thumb.replaceChildren(icon('photo'));   // HEIC: most browsers cannot show it
      thumb.append(img);
    } else {
      thumb.append(icon(item.kind === 'pdf' ? 'doc' : 'photo'));
    }
    if (state.files.length > 1 && state.mode === 'combine') li.append(el('span', 'file-order', String(index + 1)));
    const text = el('span', 'file-text');
    const name = named('span', 'file-name', item.name);
    const meta = el('span', 'file-meta', t(item.kind === 'pdf' ? 'kindPdf' : 'kindImage') + ' · ' + formatSize(item.size));
    text.append(name, meta);
    const remove = el('button', 'icon-btn remove');
    remove.type = 'button';
    remove.setAttribute('aria-label', t('remove', { name: item.name }));
    remove.append(icon('x'));
    remove.addEventListener('click', () => removeFile(item.id));
    li.append(thumb, text, remove);
    if (state.files.length > 1) {
      const handle = el('button', 'icon-btn handle');
      handle.type = 'button';
      handle.setAttribute('aria-label', t('reorder', { name: item.name }));
      handle.append(icon('handle'));
      handle.addEventListener('pointerdown', (e) => startDrag(e, li));
      handle.addEventListener('keydown', (e) => keyMove(e, item.id));
      li.append(handle);
    }
    return li;
  }

  function removeFile(id) {
    if (state.busy) return;
    const li = $('file-list').querySelector('[data-id="' + id + '"]');
    const finish = () => {
      const item = state.files.find((f) => f.id === id);
      if (item && item.url) URL.revokeObjectURL(item.url);
      state.files = state.files.filter((f) => f.id !== id);
      renderFiles(false);
    };
    if (!li || reduced()) return finish();
    const h = li.offsetHeight;
    li.style.overflow = 'hidden';
    const s = new Spring(1, { response: 0.3, precision: 0.005 });
    s.onChange((p) => {
      li.style.height = Math.max(0, h * p) + 'px';
      li.style.minHeight = '0';
      li.style.opacity = String(Math.max(0, p * 1.4 - 0.4));
      li.style.transform = 'scale(' + (0.96 + 0.04 * p) + ')';
    });
    s.to(0).then(finish);
  }

  // ---- reordering: 1:1 tracking from where it was grabbed, springs, rubber-band at the ends

  let drag = null;

  function startDrag(e, li) {
    if (e.button !== 0 || state.busy) return;
    e.preventDefault();
    if (drag) finishDrag(true);
    const items = [...$('file-list').children];
    const from = items.indexOf(li);
    const rects = items.map((x) => x.getBoundingClientRect());
    drag = {
      li, items, from, to: from, rects, startY: e.clientY, pointerId: e.pointerId,
      tracker: new VelocityTracker(), springs: new Map(), lift: new Spring(0, { response: 0.25, precision: 0.002 }),
      dy: 0,
    };
    for (const x of items) {
      if (x === li) continue;
      const s = new Spring(0, { response: 0.35, precision: 0.2 });
      s.onChange((v) => { x.style.transform = v ? 'translateY(' + v + 'px)' : ''; });
      drag.springs.set(x, s);
    }
    li.classList.add('lifted');
    drag.lift.onChange(() => paintDragged());
    drag.lift.to(1);
    e.currentTarget.setPointerCapture(e.pointerId);
    e.currentTarget.addEventListener('pointermove', moveDrag);
    e.currentTarget.addEventListener('pointerup', endDrag);
    e.currentTarget.addEventListener('pointercancel', endDrag);
  }

  function paintDragged() {
    if (!drag) return;
    const p = drag.lift.value;
    drag.li.style.transform = 'translateY(' + drag.dy + 'px) scale(' + (1 + 0.02 * p) + ')';
  }

  function moveDrag(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    const { rects, from, items } = drag;
    let dy = e.clientY - drag.startY;
    const top = rects[0].top - rects[from].top;
    const bottom = rects[rects.length - 1].bottom - rects[from].bottom;
    const h = rects[from].height;
    if (dy < top) dy = top - rubberband(top - dy, h);
    if (dy > bottom) dy = bottom + rubberband(dy - bottom, h);
    drag.dy = dy;
    drag.tracker.add(e.clientY);
    paintDragged();
    const center = rects[from].top + h / 2 + dy;
    // New place = how many of the other rows now sit above the dragged row's centre.
    const to = rects.reduce((acc, r, i) => (i !== from && center > r.top + r.height / 2 ? acc + 1 : acc), 0);
    drag.to = to;
    items.forEach((x, i) => {
      if (x === drag.li) return;
      let target = 0;
      if (from < to && i > from && i <= to) target = -h;
      if (from > to && i >= to && i < from) target = h;
      drag.springs.get(x).to(target);
    });
  }

  function endDrag(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    e.currentTarget.removeEventListener('pointermove', moveDrag);
    e.currentTarget.removeEventListener('pointerup', endDrag);
    e.currentTarget.removeEventListener('pointercancel', endDrag);
    const { rects, from, to } = drag;
    const target = to > from ? rects[to].bottom - rects[from].bottom : rects[to].top - rects[from].top;
    const v = drag.tracker.velocity();
    const settle = new Spring(drag.dy, { response: 0.35, damping: Math.abs(v) > 400 ? 0.82 : 1, precision: 0.3 });
    settle.velocity = v;                     // hand the finger's speed to the spring: no seam
    settle.onChange((y) => { if (drag) { drag.dy = y; paintDragged(); } });
    drag.lift.to(0);
    drag.settle = settle;
    settle.to(target).then(() => finishDrag(false));
  }

  function finishDrag() {
    if (!drag) return;
    const { from, to, li, items, springs } = drag;
    if (drag.settle) drag.settle.stop();
    for (const s of springs.values()) s.stop();
    drag = null;
    for (const x of items) x.style.transform = '';
    li.classList.remove('lifted');
    if (from !== to) {
      const [moved] = state.files.splice(from, 1);
      state.files.splice(to, 0, moved);
      announce(t('moved', { name: moved.name, n: to + 1 }));
    }
    renderFiles(false);
    const handle = $('file-list').children[to] && $('file-list').children[to].querySelector('.handle');
    if (handle && from !== to) handle.focus({ preventScroll: true });
  }

  function keyMove(e, id) {
    const delta = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0;
    if (!delta || state.busy) return;
    e.preventDefault();
    const i = state.files.findIndex((f) => f.id === id);
    const j = i + delta;
    if (j < 0 || j >= state.files.length) return;
    const before = new Map([...$('file-list').children].map((x) => [x.dataset.id, x.getBoundingClientRect().top]));
    [state.files[i], state.files[j]] = [state.files[j], state.files[i]];
    renderFiles(false);
    for (const x of $('file-list').children) {          // FLIP: start where it was, spring to where it is
      const dy = (before.get(x.dataset.id) || 0) - x.getBoundingClientRect().top;
      if (!dy || reduced()) continue;
      const s = new Spring(dy, { response: 0.35, precision: 0.3 });
      s.onChange((v) => { x.style.transform = v ? 'translateY(' + v + 'px)' : ''; });
      s.to(0);
    }
    $('file-list').children[j].querySelector('.handle').focus();
    announce(t('moved', { name: state.files[j].name, n: j + 1 }));
  }

  function renderMode() {
    const many = state.files.length > 1;
    $('mode-wrap').hidden = !many;
    $('mode-footer').textContent = t(state.mode === 'combine' ? 'modeCombineHint' : 'modeSeparateHint');
    if (many) requestAnimationFrame(() => modeSeg.place(false));
    for (const li of $('file-list').children) {
      const i = [...$('file-list').children].indexOf(li);
      const badge = li.querySelector('.file-order');
      if (many && state.mode === 'combine') {
        if (!badge) li.prepend(el('span', 'file-order', String(i + 1)));
        else badge.textContent = String(i + 1);
      } else if (badge) badge.remove();
    }
  }

  $('file-input').addEventListener('change', (e) => { addFiles([...e.target.files]); e.target.value = ''; });
  $('add-more').addEventListener('click', () => $('file-input').click());

  // Files can be dropped anywhere on the page.
  let dragDepth = 0;
  const dropTarget = () => ($('drop').hidden ? $('sec-files').querySelector('.group') : $('drop'));
  window.addEventListener('dragenter', (e) => {
    if (state.busy || !e.dataTransfer || ![...e.dataTransfer.types].includes('Files')) return;
    dragDepth++;
    dropTarget().classList.add('over');
  });
  window.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) { $('drop').classList.remove('over'); $('sec-files').querySelector('.group').classList.remove('over'); }
  });
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDepth = 0;
    $('drop').classList.remove('over');
    $('sec-files').querySelector('.group').classList.remove('over');
    if (!state.busy && e.dataTransfer && e.dataTransfer.files.length) addFiles([...e.dataTransfer.files]);
  });

  // ================================================================ converting

  const SETUP = ['sec-files', 'sec-recog', 'sec-output', 'start-wrap'];
  const bar = new Spring(0, { response: 0.6, precision: 0.001 });
  bar.onChange((p) => $('bar-fill').style.setProperty('--p', Math.max(0, Math.min(1, p)).toFixed(4)));

  function showSetup(show) {
    for (const id of SETUP) $(id).hidden = !show;
    if (show) for (const id of SETUP) { $(id).classList.remove('reveal'); void $(id).offsetWidth; $(id).classList.add('reveal'); }
  }

  $('start').addEventListener('click', start);

  function start() {
    if (!state.files.length || state.busy) return;
    const options = {
      engine: $('engine').value, languages: currentLanguages(), dpi: Number($('dpi').value),
      skip_furniture: $('opt-furniture').checked, own_text: $('opt-own-text').checked, outputs: currentOutputs(),
      ui_lang: H.i18n.lang, mode: state.mode,
    };
    const form = new FormData();
    for (const item of state.files) form.append('file', item.file, item.name);
    form.append('options', JSON.stringify(options));
    state.busy = true;
    state.timing = null;
    state.pollFailures = 0;
    state.saidStage = '';
    updateStart();
    showSetup(false);
    $('sec-results').hidden = true;
    $('mobile-bar').hidden = true;
    $('job-error').hidden = true;
    $('cancel').hidden = false;
    $('sec-progress').querySelector('.progress-card').hidden = false;
    $('sec-progress').hidden = false;
    $('sec-progress').classList.remove('reveal');
    void $('sec-progress').offsetWidth;
    $('sec-progress').classList.add('reveal');
    const first = state.files.find((f) => f.url);
    setPreview(first ? first.url : '');
    bar.jump(0);
    state.job = { state: 'running', stage: 'uploading', page: 0, pages: 0 };
    renderJob(state.job);
    window.scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' });

    const xhr = new XMLHttpRequest();
    state.xhr = xhr;
    xhr.open('POST', '/api/jobs');
    xhr.setRequestHeader('X-HyperOCR', '1');
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && state.job && state.job.stage === 'uploading') {
        state.job.upload = Math.round((e.loaded / e.total) * 100);
        renderJob(state.job);
      }
    });
    xhr.addEventListener('load', () => {
      state.xhr = null;
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status === 201) {
        state.job = body;
        store.set('job', body.id);        // a reload finds it again
        renderJob(body);
        poll();
      } else {
        fail(body.error || (xhr.status === 413 ? 'tooBig' : 'unexpected'), body.detail || 'HTTP ' + xhr.status);
      }
    });
    xhr.addEventListener('error', () => { state.xhr = null; fail('network'); });
    xhr.addEventListener('abort', () => { state.xhr = null; backToSetup(); });
    xhr.send(form);
  }

  // A status check that fails is retried, for about half a minute; the job keeps running on the
  // computer meanwhile and is never deleted because of it. Only a job the server no longer has
  // (it was restarted, or the results expired) ends the wait.
  const POLL_RETRIES = 25;

  function poll(delay = 600) {
    clearTimeout(state.pollTimer);
    if (!state.job || !state.job.id) return;
    state.pollTimer = setTimeout(async () => {
      let job;
      try {
        const resp = await fetch('/api/jobs/' + state.job.id, { cache: 'no-store' });
        if (resp.status === 404) { store.set('job', null); fail('jobLost', '', { keep: true }); return; }
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        job = await resp.json();
      } catch {
        state.pollFailures = (state.pollFailures || 0) + 1;
        if (state.pollFailures > POLL_RETRIES) { fail('network', '', { keep: true }); return; }
        poll(Math.min(3000, 600 * state.pollFailures));
        return;
      }
      state.pollFailures = 0;
      state.job = job;
      if (job.state === 'done') showResults(job, true);
      else if (job.state === 'failed') { renderJob(job); fail(job.error, job.detail); }
      else if (job.state === 'cancelled') backToSetup();
      else { renderJob(job); poll(); }
    }, delay);
  }

  function setPreview(url) {
    const img = $('scan-img');
    if (!url) { img.classList.remove('loaded'); img.removeAttribute('src'); return; }
    if (img.dataset.src === url) return;
    img.dataset.src = url;
    const next = new Image();
    next.onload = () => { img.src = url; img.classList.add('loaded'); };
    next.src = url;
  }

  function renderJob(job) {
    const stage = job.stage || 'queued';
    let percent = STAGE_PERCENT[stage] || 0;
    let title = t('stage_' + stage);
    let sub = '';
    let eta = '';
    if (stage === 'uploading') {
      sub = job.upload != null ? t('percent', { n: job.upload }) : '';
    } else if (stage === 'reading' && job.pages) {
      percent = 5 + Math.round(((job.page - 1) / job.pages) * 87);
      title = t('stage_reading', { page: H.i18n.num(job.page), pages: H.i18n.num(job.pages) });
      if (job.docs > 1) sub = t('docOf', { name: isolate(job.doc_name), doc: job.doc, docs: job.docs });
      else if (job.doc_name) sub = job.doc_name;
      eta = estimate(job);
      if (job.preview) setPreview(job.preview);
    } else if (stage === 'loading-model') {
      sub = t('firstRun');
    }
    $('progress-title').textContent = title;
    $('progress-sub').textContent = sub;
    $('progress-sub').hidden = !sub;
    $('progress-percent').textContent = stage === 'uploading' || stage === 'queued' ? '' : t('percent', { n: percent });
    $('progress-eta').textContent = eta;
    const indeterminate = ['uploading', 'queued', 'loading-model', 'opening'].includes(stage);
    $('bar').classList.toggle('indeterminate', indeterminate);
    $('bar').setAttribute('aria-valuenow', String(percent));
    $('sec-progress').querySelector('.progress-card').classList.toggle('idle', stage !== 'reading');
    if (!indeterminate) bar.to(percent / 100);
    // Screen readers hear each stage once (and each new document), not every status check.
    const said = stage + ':' + (job.doc || 0);
    if (said !== state.saidStage && stage !== 'uploading') { state.saidStage = said; announce(title); }
  }

  function estimate(job) {
    const now = performance.now();
    if (!state.timing || job.page < state.timing.page) state.timing = { page: job.page, at: now };
    const pagesDone = job.page - state.timing.page;
    if (pagesDone < 1) return '';
    const perPage = (now - state.timing.at) / 1000 / pagesDone;
    const left = perPage * (job.pages - job.page + 1);
    return etaText(left);
  }

  function etaText(seconds) {
    // Seconds, then minutes, then hours: a long book reads "About 10 h left", not "597 min".
    if (seconds < 90) return t('etaSeconds', { n: Math.max(5, Math.round(seconds / 5) * 5) });
    const minutes = Math.round(seconds / 60);
    if (minutes < 90) return t('etaMinutes', { n: minutes });
    if (minutes >= 300) return t('etaHours', { n: Math.round(minutes / 60) });
    const quarters = Math.round(minutes / 15);        // under 5 hours: to the quarter hour
    const h = Math.floor(quarters / 4), m = (quarters % 4) * 15;
    return m ? t('etaHoursMinutes', { h, m }) : t('etaHours', { n: h });
  }

  $('cancel').addEventListener('click', async () => {
    if (state.xhr) { state.xhr.abort(); return; }
    if (state.job && state.job.id) {
      $('cancel').disabled = true;
      try { await fetch('/api/jobs/' + state.job.id + '/cancel', { method: 'POST', headers: { 'X-HyperOCR': '1' } }); } catch { /* the poll reports it */ }
    }
  });

  function fail(key, detail, { keep = false } = {}) {
    clearTimeout(state.pollTimer);
    state.busy = false;
    $('cancel').hidden = true;
    $('cancel').disabled = false;
    const msgKey = H.i18n.has('err_' + key) ? 'err_' + key : 'err_unexpected';
    const box = $('job-error');
    box.replaceChildren(icon('warn'), el('span', '', t(msgKey, { detail: isolate(detail || key || '') })));
    box.hidden = false;
    $('sec-progress').querySelector('.progress-card').hidden = true;
    if (keep) state.job = null;     // not deleted: it may still be finishing; a reload re-attaches
    else forgetJob();
    showSetup(true);
    updateStart();
  }

  function backToSetup() {
    clearTimeout(state.pollTimer);
    state.busy = false;
    $('cancel').disabled = false;
    $('sec-progress').hidden = true;
    forgetJob();
    showSetup(true);
    updateStart();
  }

  // ================================================================ results

  function fileUrl(job, rel, download) {
    return '/api/jobs/' + job.id + '/files/' + rel.split('/').map(encodeURIComponent).join('/') + (download ? '?download=1' : '');
  }

  function showResults(job, animate) {
    clearTimeout(state.pollTimer);
    state.busy = false;
    const r = job.result;
    $('sec-progress').hidden = true;
    const card = $('sec-results').querySelector('.done-card');
    card.classList.toggle('animate', animate && !reduced());
    const files = H.i18n.plural('files', job.files);
    const time = formatDuration(r.seconds);
    $('done-sub').textContent = r.engine === 'pdf-text' ? t('doneSubOwnText', { files, time })
      : t('doneSub', { files, engine: isolate(ENGINE_NAMES[r.engine] || r.engine), time });

    const made = r.outputs || OUTPUTS;
    const stats = $('stats');
    stats.replaceChildren();
    const tiles = [['pages', 'statPages'], ['words', 'statWords'], ['images', 'statImages'], ['tables', 'statTables']]
      .filter(([k]) => !OUTPUTS.includes(k) || made.includes(k));          // pictures and tables only when made
    stats.style.setProperty('--n', String(tiles.length));
    tiles.forEach(([k, label], i) => {
      const box = el('div', 'stat' + (animate ? ' reveal-item' : ''));
      box.style.setProperty('--i', String(i + 1));
      const n = el('div', 'stat-num', '0');
      box.append(n, el('div', 'stat-label', t(label)));
      stats.append(box);
      const target = r.totals[k];
      if (!animate || reduced()) { n.textContent = H.i18n.num(target); return; }
      const s = new Spring(0, { response: 0.9, precision: 0.4 });
      s.onChange((v) => { n.textContent = H.i18n.num(Math.round(v)); });
      setTimeout(() => s.to(target), 150 + i * 60);
    });

    const zip = '/api/jobs/' + job.id + '/download';
    $('dl-zip').href = zip;
    $('m-zip').href = zip;

    const warnings = $('warnings');
    warnings.replaceChildren();
    const notes = [...r.warnings.map((w) => [w, ''])];
    // Name the document only when there is more than one to tell apart.
    for (const d of r.documents) for (const w of d.warnings) notes.push([w, r.documents.length > 1 ? d.name : '']);
    for (const [w, name] of notes) {
      if (!H.i18n.has('w_' + w.key)) continue;
      const note = INFO_NOTES.includes(w.key);         // good news, not a warning
      const p = el('p', 'notice ' + (note ? 'info' : 'warn'));
      const pages = w.pages || [];
      const key = 'w_' + w.key + (pages.length === 1 && H.i18n.has('w_' + w.key + '_one') ? '_one' : '');
      const text = (name ? isolate(name) + ': ' : '') + t(key, { pages: pageList(pages) });
      p.append(icon(note ? 'info' : 'warn'), el('span', '', text));
      warnings.append(p);
    }

    const docs = $('documents');
    docs.replaceChildren();
    r.documents.forEach((d, i) => docs.append(docBlock(job, d, i, r.documents.length > 1)));

    $('sec-results').hidden = false;
    $('mobile-bar').hidden = false;
    // The numbers warning is part of the page, never dismissed: it follows the done card every time.
    const caution = $('numbers-warning');
    if (animate) {
      for (const node of [card, caution, ...warnings.children, ...docs.children]) {
        node.classList.add('reveal-item');
      }
      card.style.setProperty('--i', '0');
      caution.style.setProperty('--i', '1');
      [...warnings.children, ...docs.children].forEach((n, i) => n.style.setProperty('--i', String(i + 2)));
      window.scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' });
      announce(t('doneTitle') + '. ' + t('numbersWarningTitle'));
    }
  }

  function downloadRow(job, rel, label, tileClass, iconName) {
    const a = el('a', 'row file-row');
    a.href = fileUrl(job, rel, true);
    a.setAttribute('download', '');
    a.setAttribute('aria-label', t('download', { name: rel.split('/').pop() }));
    const tile = el('span', 'tile ' + tileClass);
    tile.append(icon(iconName));
    const text = el('span', 'row-label');
    text.append(el('span', '', label));
    text.append(named('small', '', rel.split('/').pop()));
    const go = el('span', 'row-value');
    go.append(icon('down', 'dl'));
    a.append(tile, text, go);
    return a;
  }

  function docBlock(job, d, index, many) {
    const wrap = el('section', 'doc');
    const body = el('div', 'doc-body');
    const inner = el('div', 'doc-body-inner');
    body.append(inner);

    const made = d.outputs || OUTPUTS;
    const files = el('div', 'group');
    if (d.pdf) files.append(downloadRow(job, d.pdf, t('pdfRow'), 'tile-red', 'doc'));
    if (d.markdown_file) files.append(downloadRow(job, d.markdown_file, t('mdRow'), 'tile-gray', 'text'));
    if (files.children.length) inner.append(files);

    if (made.includes('images')) appendImages(job, d, inner);
    if (made.includes('tables')) appendTables(job, d, inner);
    if (d.markdown_file) {
      inner.append(el('h3', 'sub-header', t('resMarkdown')));
      const md = el('div', 'group');
      md.append(el('pre', 'md-preview', d.markdown));
      inner.append(md);
      if (d.markdown_truncated) inner.append(el('p', 'section-footer', t('mdTruncated')));
    }
    return collapsible(d, index, many, wrap, body, inner, made);
  }

  function appendImages(job, d, inner) {
    inner.append(el('h3', 'sub-header', t('resImages')));
    const pics = el('div', 'group');
    if (d.images.length) {
      const strip = el('div', 'thumbs');
      for (const rel of d.images) {
        const fig = el('figure', 'thumb');
        const a = el('a');
        a.href = fileUrl(job, rel, false);
        a.target = '_blank';
        a.rel = 'noopener';
        const img = new Image();
        img.loading = 'lazy';
        img.src = a.href;
        img.alt = rel.split('/').pop();
        a.append(img);
        fig.append(a, named('figcaption', '', rel.split('/').pop()));
        strip.append(fig);
      }
      pics.append(strip);
    } else {
      pics.append(el('p', 'empty-note', t('noImages')));
    }
    inner.append(pics);
  }

  function appendTables(job, d, inner) {
    inner.append(el('h3', 'sub-header', t('resTables')));
    const tables = el('div', 'group');
    if (d.tables.length) {
      d.tables.forEach((tb, n) => {
        const row = downloadRow(job, tb.file, t('tableName', { n: n + 1 }), 'tile-green', 'table');
        row.querySelector('small').textContent = t('tableMeta', { page: tb.page, rows: tb.rows, cols: tb.cols });
        tables.append(row);
      });
    } else {
      tables.append(el('p', 'empty-note', t('noTables')));
    }
    inner.append(tables);
  }

  function collapsible(d, index, many, wrap, body, inner, made) {
    if (!many) {
      wrap.append(body);
      return wrap;
    }
    const head = el('button', 'row doc-head');
    head.type = 'button';
    const tile = el('span', 'tile tile-blue');
    tile.append(icon('stack'));
    const label = el('span', 'row-label');
    const counts = [H.i18n.plural('pages', d.pages)];
    if (made.includes('images')) counts.push(H.i18n.plural('pictures', d.images.length));
    if (made.includes('tables')) counts.push(H.i18n.plural('tables', d.tables.length));
    label.append(named('span', '', d.name), el('small', '', counts.join(' · ')));
    head.append(tile, label, icon('chev', 'chev'));
    const headGroup = el('div', 'group doc-head-group');
    headGroup.append(head);
    wrap.append(headGroup, body);
    const open = index === 0;
    wrap.classList.toggle('open', open);
    head.setAttribute('aria-expanded', String(open));
    body.hidden = !open;
    const height = new Spring(open ? 1 : 0, { response: 0.4, precision: 0.002 });
    height.onChange((p) => {
      if (p >= 0.999) { body.style.height = ''; body.style.opacity = ''; return; }
      body.style.height = (inner.offsetHeight * Math.max(0, p)) + 'px';
      body.style.opacity = String(Math.max(0, Math.min(1, p * 1.3)));
    });
    head.addEventListener('click', () => {
      const opening = !wrap.classList.contains('open');
      wrap.classList.toggle('open', opening);
      head.setAttribute('aria-expanded', String(opening));
      if (opening) body.hidden = false;
      height.to(opening ? 1 : 0).then(() => { if (!wrap.classList.contains('open')) body.hidden = true; });
    });
    return wrap;
  }

  async function forgetJob() {
    const job = state.job;
    state.job = null;
    store.set('job', null);
    if (job && job.id) {
      try { await fetch('/api/jobs/' + job.id, { method: 'DELETE', headers: { 'X-HyperOCR': '1' } }); } catch { /* closed */ }
    }
  }

  $('again').addEventListener('click', () => {
    $('sec-results').hidden = true;
    $('mobile-bar').hidden = true;
    forgetJob();
    for (const f of state.files) if (f.url) URL.revokeObjectURL(f.url);
    state.files = [];
    renderFiles(false);
    showSetup(true);
    window.scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' });
  });

  // ================================================================ sheets

  const sheets = (() => {
    const layer = $('sheet-layer');
    const scrim = $('scrim');
    let current = null, trigger = null, anim = null, dragState = null;

    function paint(p, y) {
      scrim.style.opacity = String(Math.max(0, Math.min(1, p)));
      if (!current) return;
      if (phone()) {
        current.style.transform = 'translateY(' + y + 'px)';
        current.style.opacity = '';
      } else {
        current.style.transform = 'scale(' + (0.94 + 0.06 * p) + ')';
        current.style.opacity = String(Math.max(0, Math.min(1, p)));
      }
    }

    function open(id, from) {
      if (current) return;
      current = $(id);
      trigger = from || document.activeElement;
      layer.hidden = false;
      current.hidden = false;
      $('main').inert = true;
      $('navbar').inert = true;
      const h = current.offsetHeight;
      anim = new Spring(0, { response: 0.4, precision: 0.002 });
      anim.onChange((p) => paint(p, (1 - p) * h));
      anim.to(1);
      const done = current.querySelector('[data-close]');
      (done || current).focus({ preventScroll: true });
    }

    function close(velocity = 0) {
      if (!current) return;
      const sheet = current;
      const h = sheet.offsetHeight;
      const s = anim || new Spring(1);
      if (phone() && dragState) s.jump(1 - dragState.y / h);
      s.to(0, { velocity: h ? -velocity / h : 0 }).then(() => {
        if (current !== sheet) return;
        sheet.hidden = true;
        sheet.style.transform = sheet.style.opacity = '';
        layer.hidden = true;
        current = null;
        $('main').inert = false;
        $('navbar').inert = false;
        if (trigger && trigger.focus) trigger.focus({ preventScroll: true });
      });
    }

    layer.addEventListener('click', (e) => { if (e.target === scrim || e.target.closest('[data-close]')) close(); });
    document.addEventListener('keydown', (e) => {
      if (!current) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      if (e.key === 'Tab') {                               // keep focus inside the sheet
        const f = [...current.querySelectorAll('button, a[href], select, input')].filter((x) => !x.disabled && x.tabIndex >= 0 && x.offsetParent);
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });

    // Phones: pull the sheet down to dismiss; it follows the finger, resists upwards, and
    // either springs back or keeps going with the finger's speed.
    for (const sheet of document.querySelectorAll('.sheet')) {
      const handleZone = (e) => e.target.closest('.grabber, .sheet-bar') && !e.target.closest('button');
      sheet.addEventListener('pointerdown', (e) => {
        if (!phone() || !handleZone(e) || current !== sheet) return;
        if (anim) anim.stop();
        dragState = { start: e.clientY, y: 0, tracker: new VelocityTracker(), id: e.pointerId };
        sheet.setPointerCapture(e.pointerId);
      });
      sheet.addEventListener('pointermove', (e) => {
        if (!dragState || e.pointerId !== dragState.id) return;
        let y = e.clientY - dragState.start;
        if (y < 0) y = -rubberband(-y, sheet.offsetHeight);
        dragState.y = y;
        dragState.tracker.add(e.clientY);
        paint(1 - Math.max(0, y) / sheet.offsetHeight, y);
      });
      const release = (e) => {
        if (!dragState || e.pointerId !== dragState.id) return;
        const v = dragState.tracker.velocity();
        const h = sheet.offsetHeight;
        const projected = dragState.y + project(v, 0.99);
        if (projected > h * 0.45) {
          close(v);
        } else {
          anim = new Spring(1 - Math.max(0, dragState.y) / h, { response: 0.35, damping: 0.85, precision: 0.002 });
          anim.velocity = h ? -v / h : 0;
          anim.onChange((p) => paint(p, (1 - p) * h));
          anim.to(1);
        }
        dragState = null;
      };
      sheet.addEventListener('pointerup', release);
      sheet.addEventListener('pointercancel', release);
    }
    return { open, close, get current() { return current; } };
  })();

  $('about-btn').addEventListener('click', () => {
    sheets.open('about-sheet', $('about-btn'));
    requestAnimationFrame(() => appearanceSeg.place(false));
  });

  function renderAboutEngines() {
    const box = $('about-engines');
    box.replaceChildren();
    for (const e of state.system.engines) {
      const row = el('div', 'row');
      const tile = el('span', 'tile ' + (e.id === 'tesseract' ? 'tile-gray' : 'tile-blue'));
      tile.append(icon('cpu'));
      const label = el('span', 'row-label');
      label.append(el('span', '', t('eng_' + e.id)));
      // Why an engine is off is a sentence, so it goes under the name; the trailing value stays short.
      if (e.ok && e.detail) label.append(named('small', '', e.detail));
      else if (!e.ok) label.append(el('small', '', H.i18n.has('r_' + e.reason) ? t('r_' + e.reason) : e.reason));
      const value = el('span', 'row-value' + (e.ok ? ' ok' : ''));
      value.append(el('span', '', e.ok ? t('engReady') : t('engOff')));
      row.append(tile, label, value);
      box.append(row);
    }
  }

  // ================================================================ updates

  const upd = { phase: 'idle', latest: '', error: '', steps: [] };

  function renderUpdate() {
    const status = $('update-status');
    const btn = $('update-btn');
    const label = $('update-btn-label');
    btn.disabled = upd.phase === 'checking' || upd.phase === 'updating';
    btn.className = 'btn btn-small ' + (upd.phase === 'available' ? 'btn-filled' : 'btn-tinted');
    status.className = '';
    if (upd.phase === 'checking') status.textContent = t('updChecking');
    else if (upd.phase === 'current') status.textContent = t('updUpToDate', { v: state.system ? state.system.version : '' });
    else if (upd.phase === 'available' || upd.phase === 'updating') status.textContent = t('updAvailable', { latest: upd.latest });
    else if (upd.phase === 'busy') status.textContent = t('updBusy');
    else if (upd.phase === 'failed') { status.textContent = upd.error; status.style.color = 'var(--red-text)'; }
    else status.textContent = t('updIdle');
    if (upd.phase !== 'failed') status.style.color = '';
    label.textContent = upd.phase === 'available' ? t('updNow') : upd.phase === 'failed' ? t('updRetry') : t('updCheck');
    btn.hidden = upd.phase === 'updating';
    const steps = $('update-steps');
    steps.hidden = !upd.steps.length;
    steps.replaceChildren();
    upd.steps.forEach((s, i) => {
      const row = el('div', 'step ' + (s.done ? 'done' : i === upd.steps.length - 1 ? 'active' : ''));
      row.append(s.done ? icon('check') : el('span', 'spinner'), el('span', '', s.text));
      steps.append(row);
    });
  }

  $('update-btn').addEventListener('click', async () => {
    if (upd.phase === 'available') return applyUpdate();
    upd.phase = 'checking';
    upd.steps = [];
    renderUpdate();
    try {
      const resp = await fetch('/api/update/check', { method: 'POST', headers: { 'X-HyperOCR': '1' } });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || data.detail);
      upd.latest = data.latest;
      upd.phase = data.available ? 'available' : 'current';
    } catch (err) {
      upd.phase = 'failed';
      upd.error = t(err && err.message === 'updateRateLimited' ? 'updRateLimited' : 'updFailed');
    }
    renderUpdate();
  });

  async function applyUpdate() {
    const resp = await fetch('/api/update/apply', { method: 'POST', headers: { 'X-HyperOCR': '1' } }).catch(() => null);
    if (!resp || resp.status === 409) {
      upd.phase = resp ? 'busy' : 'failed';
      upd.error = t('updFailed');
      return renderUpdate();
    }
    upd.phase = 'updating';
    upd.steps = [];
    renderUpdate();
    const oldVersion = state.system ? state.system.version : '';
    const STEP = { downloading: 'step_downloading', installing: 'step_installing', packages: 'step_packages' };
    const tick = async () => {
      let st;
      try { st = await (await fetch('/api/update/status', { cache: 'no-store' })).json(); } catch { st = null; }
      if (st) {
        upd.steps = st.events.filter((ev) => STEP[ev.step]).map((ev) => ({ text: t(STEP[ev.step], { v: upd.latest }), done: false }));
        upd.steps.forEach((s, i) => { s.done = i < upd.steps.length - 1 || st.state !== 'running'; });
        const last = st.events[st.events.length - 1] || {};
        if (st.state === 'failed') {
          upd.phase = 'failed';
          upd.error = t('updFailedInstall', { detail: last.error || '' });
          upd.steps = [];
          return renderUpdate();
        }
        if (st.state === 'done') {
          upd.steps.push({ text: t('updRestartManual'), done: true });
          return renderUpdate();
        }
        if (st.state === 'restarting') {
          upd.steps.push({ text: t('step_restarting'), done: false });
          renderUpdate();
          return waitForRestart(oldVersion);
        }
      }
      renderUpdate();
      setTimeout(tick, 600);
    };
    tick();
  }

  function waitForRestart(oldVersion) {
    const started = Date.now();
    let sawDown = false;
    const check = async () => {
      try {
        const sys = await (await fetch('/api/system', { cache: 'no-store' })).json();
        if (sawDown || sys.version !== oldVersion) { location.reload(); return; }
      } catch { sawDown = true; }
      if (Date.now() - started > 60000) {
        upd.steps = [{ text: t('updRestartManual'), done: true }];
        return renderUpdate();
      }
      setTimeout(check, 800);
    };
    setTimeout(check, 1200);
  }

  // ================================================================ start

  // After a reload: pick up the conversion this browser started, running or finished.
  async function reattach() {
    const id = store.get('job');
    if (typeof id !== 'string' || !/^[0-9a-f]{8,32}$/.test(id)) return;
    let job;
    try {
      const resp = await fetch('/api/jobs/' + id, { cache: 'no-store' });
      if (!resp.ok) { store.set('job', null); return; }
      job = await resp.json();
    } catch { return; }
    state.job = job;
    state.pollFailures = 0;
    if (job.state === 'done' && job.result) {
      showSetup(false);
      showResults(job, false);
    } else if (job.state === 'queued' || job.state === 'running') {
      state.busy = true;
      showSetup(false);
      $('sec-results').hidden = true;
      $('job-error').hidden = true;
      $('cancel').hidden = false;
      $('sec-progress').querySelector('.progress-card').hidden = false;
      $('sec-progress').hidden = false;
      renderJob(job);
      poll();
    } else {
      state.job = null;
      store.set('job', null);
    }
  }

  renderAll();
  loadSystem();
  reattach();
  onScroll();
})(window.HOCR);
