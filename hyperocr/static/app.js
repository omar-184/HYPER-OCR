/* HYPER-OCR interface. Talks only to this computer (127.0.0.1). */
(function (H) {
  'use strict';

  const { t } = H.i18n;
  const $ = (id) => document.getElementById(id);
  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem('hocr.' + key)); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem('hocr.' + key, JSON.stringify(value)); } catch (e) { /* storage may be blocked */ } },
  };
  const ENGINE_NAMES = { unlimited: 'Unlimited-OCR', 'unlimited-server': 'Unlimited-OCR', tesseract: 'Tesseract' };
  const STAGE_PERCENT = { uploading: 0, queued: 1, opening: 2, 'loading-model': 4, 'writing-pdf': 92, 'writing-markdown': 95, packing: 98, done: 100 };

  const state = { system: null, file: null, job: null, pollTimer: 0, xhr: null, busy: false };

  // ---------------------------------------------------------------- colour theme

  const THEMES = ['auto', 'dark', 'light'];
  const darkQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function applyTheme() {
    const mode = THEMES.includes(store.get('theme')) ? store.get('theme') : 'auto';
    const root = document.documentElement;
    if (mode === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);
    const dark = mode === 'dark' || (mode === 'auto' && !!darkQuery && darkQuery.matches);
    $('theme-color').setAttribute('content', dark ? '#000000' : '#f3f4f6');
    const name = t('theme_' + mode);
    $('theme-label').textContent = name;
    $('theme-btn').setAttribute('aria-label', t('themeBtn', { mode: name }));
    $('theme-btn').title = t('themeBtn', { mode: name });
  }

  $('theme-btn').addEventListener('click', () => {
    const cur = THEMES.includes(store.get('theme')) ? store.get('theme') : 'auto';
    store.set('theme', THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
    applyTheme();
  });
  if (darkQuery && darkQuery.addEventListener) darkQuery.addEventListener('change', applyTheme);

  // ---------------------------------------------------------------- language

  for (const btn of document.querySelectorAll('[data-lang]')) {
    btn.addEventListener('click', () => { store.set('lang', btn.dataset.lang); renderAll(); });
  }

  function renderAll() {
    const saved = store.get('lang');
    H.i18n.setLang(saved || ((navigator.language || '').startsWith('ar') ? 'ar' : 'en'));
    applyTheme();
    $('file-remove').setAttribute('aria-label', t('fileRemove'));
    $('file-remove').title = t('fileRemove');
    renderFile();
    renderSystem();
    if (state.job) renderJob(state.job);
    if (state.job && state.job.state === 'done' && state.job.result) showResults(state.job, false);
  }

  // ---------------------------------------------------------------- system and settings

  async function loadSystem() {
    showMsg($('engine-status'), 'ok', t('st_checking'));
    try {
      const resp = await fetch('/api/system', { cache: 'no-store' });
      state.system = await resp.json();
    } catch (e) {
      showMsg($('engine-status'), 'error', t('err_network'));
      return;
    }
    renderSystem();
  }

  function engineInfo(id) {
    return state.system ? state.system.engines.find((e) => e.id === id) : null;
  }

  function renderSystem() {
    const sys = state.system;
    if (!sys) return;
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
    const savedDpi = String(store.get('dpi') || '');
    if (['200', '300', '400'].includes(savedDpi) && !$('dpi').dataset.touched) $('dpi').value = savedDpi;
    if (store.get('snapshot') === false) $('opt-snapshot').checked = false;
    if (store.get('furniture') === false) $('opt-furniture').checked = false;
    renderEngineStatus();
    renderLanguages();
    updateStart();
  }

  function renderEngineStatus() {
    const sys = state.system;
    const box = $('engine-status');
    const choice = $('engine').value;
    const tess = engineInfo('tesseract');
    const gpu = engineInfo('unlimited');
    const effective = choice === 'auto' ? sys.auto : choice;
    if (effective === 'unlimited') {
      showMsg(box, 'ok', t('st_gpuReady', { detail: (gpu && gpu.detail) || 'GPU' }));
    } else if (effective === 'unlimited-server') {
      showMsg(box, 'ok', t('st_serverReady', { detail: (engineInfo('unlimited-server') || {}).detail || '' }));
    } else if (!tess || !tess.ok) {
      showMsg(box, 'error', t('err_tesseractMissing'));
    } else if (choice === 'auto' && gpu && !gpu.ok && H.i18n.has('st_' + gpu.reason)) {
      showMsg(box, 'warn', t('st_' + gpu.reason, { detail: gpu.detail || '' }));
    } else {
      showMsg(box, 'ok', t('st_cpu'));
    }
  }

  function renderLanguages() {
    const sys = state.system;
    const list = $('lang-list');
    const chosen = new Set(currentLanguages());
    list.replaceChildren();
    if (!sys.languages.length) {
      const p = document.createElement('p');
      p.className = 'hint';
      p.textContent = t('noLangs');
      list.append(p);
      return;
    }
    const order = ['eng', 'ara'];
    const langs = [...sys.languages].sort((a, b) => {
      const ia = order.indexOf(a), ib = order.indexOf(b);
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      return H.i18n.langName(a).localeCompare(H.i18n.langName(b));
    });
    for (const code of langs) {
      const label = document.createElement('label');
      label.className = 'check';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = code;
      input.checked = chosen.has(code);
      input.addEventListener('change', () => { store.set('languages', checkedLanguages()); updateStart(); });
      const span = document.createElement('span');
      span.textContent = H.i18n.langName(code);
      label.append(input, span);
      list.append(label);
    }
  }

  function currentLanguages() {
    const sys = state.system;
    const saved = store.get('languages');
    const valid = Array.isArray(saved) ? saved.filter((l) => sys.languages.includes(l)) : [];
    return valid.length ? valid : sys.defaults.languages;
  }

  function checkedLanguages() {
    return [...$('lang-list').querySelectorAll('input:checked')].map((i) => i.value);
  }

  $('engine').addEventListener('change', () => {
    $('engine').dataset.touched = '1';
    store.set('engine', $('engine').value);
    renderEngineStatus();
    updateStart();
  });
  $('dpi').addEventListener('change', () => { $('dpi').dataset.touched = '1'; store.set('dpi', Number($('dpi').value)); });
  $('opt-snapshot').addEventListener('change', () => store.set('snapshot', $('opt-snapshot').checked));
  $('opt-furniture').addEventListener('change', () => store.set('furniture', $('opt-furniture').checked));

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
    const ready = !!state.file && engineUsable() && !state.busy;
    $('start').disabled = !ready;
    $('start-hint').hidden = !!state.file;
  }

  // ---------------------------------------------------------------- choosing the file

  function setFile(file) {
    $('file-error').hidden = true;
    if (!file) return;
    const isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    if (!isPdf) {
      showMsg($('file-error'), 'error', t('fileNotPdf'));
      return;
    }
    state.file = file;
    renderFile();
    updateStart();
  }

  function renderFile() {
    const file = state.file;
    $('file-list').hidden = !file;
    $('drop-title').textContent = t(file ? 'fileChange' : 'filePick');
    if (!file) return;
    $('file-name').textContent = file.name;
    $('file-meta').textContent = t('fileMetaNoPages', { size: formatSize(file.size) });
  }

  $('file-input').addEventListener('change', (e) => { setFile(e.target.files[0]); e.target.value = ''; });
  $('file-remove').addEventListener('click', () => { if (state.busy) return; state.file = null; renderFile(); updateStart(); });

  const drop = $('drop');
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('over');
    if (!state.busy && e.dataTransfer && e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
  });
  // A PDF dropped beside the target must not replace the app with the browser's viewer.
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  // ---------------------------------------------------------------- running a job

  $('start').addEventListener('click', start);

  function start() {
    if (!state.file || state.busy) return;
    const options = {
      engine: $('engine').value,
      languages: checkedLanguages(),
      dpi: Number($('dpi').value),
      table_snapshot: $('opt-snapshot').checked,
      skip_furniture: $('opt-furniture').checked,
      ui_lang: H.i18n.lang,
    };
    const form = new FormData();
    form.append('file', state.file, state.file.name);
    form.append('options', JSON.stringify(options));
    setBusy(true);
    clearResults();
    $('step-progress').hidden = false;
    $('job-error').hidden = true;
    $('cancel').hidden = false;
    state.job = { state: 'running', stage: 'uploading', page: 0, pages: 0 };
    renderJob(state.job);
    $('step-progress').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

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
      try { body = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
      if (xhr.status === 201) {
        state.job = body;
        renderJob(body);
        poll();
      } else {
        fail(body.error || (xhr.status === 413 ? 'tooBig' : 'unexpected'), body.detail || 'HTTP ' + xhr.status);
      }
    });
    xhr.addEventListener('error', () => { state.xhr = null; fail('network'); });
    xhr.addEventListener('abort', () => { state.xhr = null; finishCancelled(); });
    xhr.send(form);
  }

  function poll() {
    clearTimeout(state.pollTimer);
    if (!state.job || !state.job.id) return;
    state.pollTimer = setTimeout(async () => {
      let job;
      try {
        const resp = await fetch('/api/jobs/' + state.job.id, { cache: 'no-store' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        job = await resp.json();
      } catch (e) {
        fail('network');
        return;
      }
      state.job = job;
      renderJob(job);
      if (job.state === 'done') showResults(job);
      else if (job.state === 'failed') fail(job.error, job.detail);
      else if (job.state === 'cancelled') finishCancelled();
      else poll();
    }, 700);
  }

  function renderJob(job) {
    if (job.state === 'done' && job.result) {
      setProgress(100, false);
      $('progress-stage').textContent = t('stage_done');
      $('progress-count').textContent = '';
      $('progress-engine').textContent = t('withEngine', { engine: ENGINE_NAMES[job.result.engine] || job.result.engine });
      return;
    }
    const stage = job.stage || 'queued';
    $('progress-stage').textContent = t('stage_' + stage);
    let percent = STAGE_PERCENT[stage] || 0;
    let count = '';
    if (stage === 'uploading') {
      percent = 0;
      count = job.upload != null ? t('percent', { n: job.upload }) : '';
    } else if (stage === 'reading' && job.pages) {
      percent = 5 + Math.round(((job.page - 1) / job.pages) * 86);
      count = t('pageOf', { page: H.i18n.num(job.page), pages: H.i18n.num(job.pages) });
    } else if (stage === 'loading-model') {
      count = t('firstRun');
    }
    $('progress-count').textContent = count;
    $('progress-engine').textContent = '';
    setProgress(percent, stage === 'loading-model' || stage === 'queued' || stage === 'uploading');
  }

  function setProgress(percent, indeterminate) {
    $('progress').classList.toggle('indeterminate', indeterminate);
    $('progress-bar').style.width = indeterminate ? '' : percent + '%';
    $('progress').setAttribute('aria-valuenow', String(percent));
  }

  $('cancel').addEventListener('click', async () => {
    if (state.xhr) { state.xhr.abort(); return; }
    if (state.job && state.job.id) {
      $('cancel').disabled = true;
      try {
        await fetch('/api/jobs/' + state.job.id + '/cancel', { method: 'POST', headers: { 'X-HyperOCR': '1' } });
      } catch (e) { /* the poll reports what happened */ }
    }
  });

  function fail(key, detail) {
    clearTimeout(state.pollTimer);
    setBusy(false);
    $('cancel').hidden = true;
    const msgKey = H.i18n.has('err_' + key) ? 'err_' + key : 'err_unexpected';
    showMsg($('job-error'), 'error', t(msgKey, { detail: detail || key || '' }));
    setProgress(0, false);
    $('progress-stage').textContent = '';
    $('progress-count').textContent = '';
  }

  function finishCancelled() {
    clearTimeout(state.pollTimer);
    setBusy(false);
    $('step-progress').hidden = true;
    forgetJob();
  }

  function setBusy(busy) {
    state.busy = busy;
    $('cancel').disabled = !busy;
    for (const el of document.querySelectorAll('#step-settings select, #step-settings input, #file-input')) el.disabled = busy;
    $('file-remove').disabled = busy;
    drop.classList.toggle('disabled', busy);
    if (!busy) renderSystem();
    updateStart();
  }

  // ---------------------------------------------------------------- results

  function fileUrl(job, rel, download) {
    const path = rel.split('/').map(encodeURIComponent).join('/');
    return '/api/jobs/' + job.id + '/files/' + path + (download ? '?download=1' : '');
  }

  function showResults(job, scroll = true) {
    clearTimeout(state.pollTimer);
    setBusy(false);
    $('cancel').hidden = true;
    const r = job.result;
    const stats = $('stats');
    stats.replaceChildren();
    const chips = [[r.pages, 'statPages'], [r.words, 'statWords'], [r.images.length, 'statImages'], [r.tables.length, 'statTables'], [r.seconds, 'statSeconds']];
    for (const [n, key] of chips) {
      const li = document.createElement('li');
      li.className = 'stat';
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = H.i18n.num(n);
      li.append(badge, document.createTextNode(t(key)));
      stats.append(li);
    }

    const warnings = $('warnings');
    warnings.replaceChildren();
    for (const w of r.warnings) {
      if (!H.i18n.has('w_' + w.key)) continue;
      const p = document.createElement('p');
      p.className = 'msg warn';
      p.textContent = t('w_' + w.key, { pages: (w.pages || []).join(', ') });
      warnings.append(p);
    }

    const zip = '/api/jobs/' + job.id + '/download';
    $('dl-zip').href = zip;
    $('m-zip').href = zip;
    $('dl-pdf').href = fileUrl(job, r.pdf, true);
    $('dl-md').href = fileUrl(job, r.markdown_file, true);

    const thumbs = $('thumbs');
    thumbs.replaceChildren();
    for (const rel of r.images) {
      const fig = document.createElement('figure');
      fig.className = 'thumb';
      const a = document.createElement('a');
      a.href = fileUrl(job, rel, false);
      a.target = '_blank';
      a.rel = 'noopener';
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.src = a.href;
      img.alt = rel.split('/').pop();
      a.append(img);
      const cap = document.createElement('figcaption');
      cap.dir = 'ltr';
      cap.textContent = rel.split('/').pop();
      fig.append(a, cap);
      thumbs.append(fig);
    }
    $('no-images').hidden = r.images.length > 0;

    const tables = $('table-list');
    tables.replaceChildren();
    r.tables.forEach((tb, i) => {
      const item = document.createElement('div');
      item.className = 'src-item';
      const head = document.createElement('div');
      head.className = 'src-head';
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = H.i18n.num(i + 1);
      const name = document.createElement('span');
      name.className = 'file-name';
      name.dir = 'ltr';
      name.textContent = tb.file.split('/').pop();
      const dl = document.createElement('a');
      dl.className = 'btn secondary';
      dl.href = fileUrl(job, tb.file, true);
      dl.setAttribute('download', '');
      dl.textContent = t('dlFile');
      head.append(badge, name, dl);
      const meta = document.createElement('span');
      meta.className = 'muted';
      meta.textContent = t('tableMeta', { page: tb.page, rows: tb.rows, cols: tb.cols });
      item.append(head, meta);
      tables.append(item);
    });
    $('no-tables').hidden = r.tables.length > 0;

    $('md-name').textContent = r.markdown_file;
    $('md-preview').textContent = r.markdown;
    $('md-truncated').hidden = !r.markdown_truncated;

    $('step-results').hidden = false;
    $('mobile-bar').hidden = false;
    if (scroll) $('step-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function clearResults() {
    $('step-results').hidden = true;
    $('mobile-bar').hidden = true;
  }

  async function forgetJob() {
    const job = state.job;
    state.job = null;
    if (job && job.id) {
      try { await fetch('/api/jobs/' + job.id, { method: 'DELETE', headers: { 'X-HyperOCR': '1' } }); } catch (e) { /* app closed */ }
    }
  }

  function again() {
    clearResults();
    $('step-progress').hidden = true;
    forgetJob();
    state.file = null;
    renderFile();
    updateStart();
    $('step-file').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  $('again').addEventListener('click', again);
  $('m-again').addEventListener('click', again);

  // ---------------------------------------------------------------- helpers

  function showMsg(el, kind, text) {
    el.className = 'msg ' + kind;
    el.textContent = text;
    el.hidden = false;
  }

  function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let n = bytes, u = 0;
    while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
    return (u ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + units[u];
  }

  renderAll();
  loadSystem();
})(window.HOCR);
