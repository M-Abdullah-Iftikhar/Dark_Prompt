/* Dark Prompt — page-level effects.
   - Operator node id (persisted)
   - Section reveal-on-scroll
   - Live telemetry ticker
*/
(function () {

  // --- Operator status: stable per-device node id ----------------------
  function ensureNodeId() {
    let id = '';
    try { id = localStorage.getItem('darkprompt-node') || ''; } catch (e) {}
    if (!/^[0-9A-F]{4}$/.test(id)) {
      id = '';
      for (let i = 0; i < 4; i++) {
        id += '0123456789ABCDEF'[Math.floor(Math.random() * 16)];
      }
      try { localStorage.setItem('darkprompt-node', id); } catch (e) {}
    }
    document.querySelectorAll('[data-op-node]').forEach(el => {
      el.textContent = `NODE 0x${id}`;
    });
  }

  // --- Section reveal -------------------------------------------------
  function wireReveals() {
    const items = document.querySelectorAll('[data-reveal]');
    if (!items.length || !('IntersectionObserver' in window)) {
      items.forEach(el => el.classList.add('is-visible'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          const delay = e.target.dataset.revealDelay || 0;
          setTimeout(() => e.target.classList.add('is-visible'), parseInt(delay, 10) || 0);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    items.forEach(el => io.observe(el));
  }

  // --- Telemetry ticker -----------------------------------------------
  const HEX = '0123456789abcdef';
  function randHex(n) { let s = ''; for (let i = 0; i < n; i++) s += HEX[Math.floor(Math.random() * 16)]; return s; }
  function randIp() {
    const r = () => Math.floor(Math.random() * 256);
    return `${r()}.${r()}.${r()}.${r()}`;
  }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  const TTPS = ['T1059.001', 'T1055', 'T1027', 'T1071.001', 'T1547.001', 'T1003.001',
                'T1218.011', 'T1112', 'T1486', 'T1090.003', 'T1140', 'T1036.005'];
  const PROCS = ['explorer.exe', 'svchost.exe', 'powershell.exe', 'rundll32.exe',
                 'regsvr32.exe', 'cmd.exe', 'wmic.exe', 'mshta.exe', 'wscript.exe',
                 'lsass.exe', 'winlogon.exe', 'taskhost.exe'];
  const CVES = ['CVE-2024-21626', 'CVE-2024-23222', 'CVE-2024-3094', 'CVE-2024-1709',
                'CVE-2024-21412', 'CVE-2023-46805', 'CVE-2024-30051', 'CVE-2024-38063'];
  const FAMILIES = ['LummaStealer', 'Qakbot', 'IcedID', 'Emotet', 'Rhadamanthys',
                    'AsyncRAT', 'XWorm', 'BumbleBee', 'PikaBot'];
  const SEVERITIES = [
    { l: 'low',    cls: 'sev-low' },
    { l: 'med',    cls: 'sev-med' },
    { l: 'high',   cls: 'sev-high' },
    { l: 'crit',   cls: 'sev-crit' },
  ];

  function makeItem() {
    const kind = Math.floor(Math.random() * 7);
    switch (kind) {
      case 0: return { label: 'SHA256', value: randHex(12) + '…', tag: 'hash' };
      case 1: return { label: 'CVE',    value: pick(CVES) };
      case 2: return { label: 'IP',     value: randIp() };
      case 3: return { label: 'TTP',    value: pick(TTPS) };
      case 4: return { label: 'PROC',   value: pick(PROCS) };
      case 5: return { label: 'FAM',    value: pick(FAMILIES) };
      case 6: {
        const s = pick(SEVERITIES);
        return { label: 'ALERT', value: s.l, severity: s.cls };
      }
    }
  }

  function renderItem(it) {
    const span = document.createElement('span');
    span.className = 'tlm-item' + (it.severity ? ' ' + it.severity : '');
    span.innerHTML = `
      <span class="tlm-label">${it.label}</span>
      <span class="tlm-val">${it.value}</span>
    `;
    return span;
  }

  function buildTelemetry() {
    const track = document.getElementById('telemetry-track');
    if (!track) return;
    const items = [];
    for (let i = 0; i < 28; i++) items.push(makeItem());
    // Render twice so the ticker can loop seamlessly.
    items.concat(items).forEach(it => track.appendChild(renderItem(it)));
  }

  // --- Click ripple on primary buttons --------------------------------
  function wireMagnetic() {
    document.querySelectorAll('.btn-primary').forEach(btn => {
      btn.addEventListener('pointerdown', (e) => {
        const r = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'btn-ripple';
        ripple.style.left = `${e.clientX - r.left}px`;
        ripple.style.top  = `${e.clientY - r.top}px`;
        btn.appendChild(ripple);
        setTimeout(() => ripple.remove(), 700);
      });
    });
  }

  // --- Cross-page fade transition --------------------------------------
  function wirePageTransitions() {
    const reduced = window.matchMedia &&
                    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) return;

    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[href]');
      if (!a) return;
      if (e.defaultPrevented) return;
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (a.target && a.target !== '_self') return;
      if (a.hasAttribute('download')) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#')) return;
      let url;
      try { url = new URL(a.href, location.href); } catch (_) { return; }
      if (url.origin !== location.origin) return;
      // same path + hash only — let browser handle scroll
      if (url.pathname === location.pathname && url.hash) return;
      e.preventDefault();
      document.body.classList.add('is-leaving');
      setTimeout(() => { window.location.href = a.href; }, 170);
    });

    document.addEventListener('submit', (e) => {
      if (e.defaultPrevented) return;
      const f = e.target;
      if (!(f instanceof HTMLFormElement)) return;
      // Don't fade for fetch-handled forms (they call preventDefault first)
      // Don't fade for forms in the chat shell (chat composer fetches itself)
      if (f.closest('.chat-shell')) return;
      document.body.classList.add('is-leaving');
    });

    window.addEventListener('pageshow', () => {
      document.body.classList.remove('is-leaving');
    });
  }

  // --- Stat counters ---------------------------------------------------
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animateCounter(el) {
    const to = parseFloat(el.dataset.countTo);
    if (!Number.isFinite(to)) return;
    const decimals = parseInt(el.dataset.countDecimals || '0', 10);
    const suffix = el.dataset.countSuffix || '';
    const prefix = el.dataset.countPrefix || '';
    const duration = parseInt(el.dataset.countDuration || '1800', 10);
    const start = performance.now();
    function fmt(n) {
      const v = decimals
        ? n.toFixed(decimals)
        : Math.floor(n).toString();
      // group with commas (en-US)
      const parts = v.split('.');
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return prefix + parts.join('.') + suffix;
    }
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      el.textContent = fmt(to * easeOutCubic(t));
      if (t < 1) requestAnimationFrame(tick);
      else el.textContent = fmt(to);
    }
    requestAnimationFrame(tick);
  }

  function wireCounters() {
    const items = document.querySelectorAll('[data-count-to]');
    if (!items.length) return;
    if (!('IntersectionObserver' in window)) {
      items.forEach(animateCounter);
      return;
    }
    const reduced = window.matchMedia &&
                    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      items.forEach(el => {
        const to = parseFloat(el.dataset.countTo);
        const decimals = parseInt(el.dataset.countDecimals || '0', 10);
        const suffix = el.dataset.countSuffix || '';
        const prefix = el.dataset.countPrefix || '';
        const v = decimals ? to.toFixed(decimals) : Math.floor(to).toString();
        const parts = v.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        el.textContent = prefix + parts.join('.') + suffix;
      });
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          animateCounter(e.target);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.4 });
    items.forEach(el => io.observe(el));
  }

  // --- Password show/hide + strength meter -----------------------------
  function wirePasswordToggle() {
    document.querySelectorAll('[data-pw-toggle]').forEach(btn => {
      btn.addEventListener('click', () => {
        const wrap = btn.closest('[data-pw-wrap]');
        if (!wrap) return;
        const input = wrap.querySelector('input');
        if (!input) return;
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        btn.setAttribute('aria-pressed', String(!showing));
        btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
        wrap.classList.toggle('is-revealed', !showing);
      });
    });
  }

  const STRENGTH_LABELS = ['—', 'WEAK', 'FAIR', 'GOOD', 'STRONG', 'EXCELLENT'];
  function scorePassword(pw) {
    if (!pw) return 0;
    let score = 0;
    if (pw.length >= 8)  score++;
    if (pw.length >= 12) score++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw)) score++;
    return Math.min(5, score);
  }

  function wirePasswordStrength() {
    document.querySelectorAll('[data-pw-strength]').forEach(meter => {
      const wrap = meter.previousElementSibling;
      if (!wrap || !wrap.matches('[data-pw-wrap]')) return;
      const input = wrap.querySelector('input');
      const label = meter.querySelector('[data-pw-strength-label]');
      if (!input || !label) return;
      function update() {
        const s = scorePassword(input.value);
        meter.dataset.score = String(s);
        label.textContent = STRENGTH_LABELS[s];
      }
      input.addEventListener('input', update);
      update();
    });
  }

  // --- Tooltip system --------------------------------------------------
  function wireTooltips() {
    let current = null;
    let openFor = null;
    let timer = null;

    function position(tip, target) {
      const r = target.getBoundingClientRect();
      const tr = tip.getBoundingClientRect();
      const placement = target.dataset.tipPlace || 'top';
      let top, left;
      if (placement === 'bottom') {
        top  = r.bottom + 8;
        left = r.left + r.width / 2 - tr.width / 2;
      } else {
        top  = r.top - tr.height - 8;
        left = r.left + r.width / 2 - tr.width / 2;
        if (top < 8) top = r.bottom + 8;
      }
      if (left < 8) left = 8;
      if (left + tr.width > window.innerWidth - 8) left = window.innerWidth - 8 - tr.width;
      tip.style.top  = top  + 'px';
      tip.style.left = left + 'px';
    }

    function show(target) {
      if (openFor === target) return;
      hide();
      const text = target.dataset.tip;
      if (!text) return;
      const tip = document.createElement('div');
      tip.className = 'tip';
      tip.textContent = text;
      document.body.appendChild(tip);
      position(tip, target);
      requestAnimationFrame(() => tip.classList.add('is-visible'));
      current = tip;
      openFor = target;
    }

    function hide() {
      if (current) {
        current.classList.remove('is-visible');
        const tip = current;
        setTimeout(() => tip.remove(), 140);
        current = null;
        openFor = null;
      }
    }

    document.addEventListener('pointerover', (e) => {
      const el = e.target.closest && e.target.closest('[data-tip]');
      if (!el) { clearTimeout(timer); hide(); return; }
      if (el === openFor) return;
      clearTimeout(timer);
      timer = setTimeout(() => show(el), 320);
    });
    document.addEventListener('pointerleave', () => { clearTimeout(timer); hide(); }, true);
    document.addEventListener('click', () => { clearTimeout(timer); hide(); }, true);
    window.addEventListener('scroll', hide, true);
    window.addEventListener('blur', hide);
  }

  // --- Toast (global utility) ------------------------------------------
  function showToast(content, opts) {
    const stack = document.getElementById('toast-stack');
    if (!stack) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    if (opts && opts.tone) toast.classList.add('toast-' + opts.tone);
    toast.innerHTML = '<span class="toast-body">' + content + '</span>';
    stack.appendChild(toast);
    const dur = (opts && opts.duration) || 2400;
    setTimeout(() => {
      toast.classList.add('is-leaving');
      setTimeout(() => toast.remove(), 220);
    }, dur);
    return toast;
  }
  window.dpToast = showToast;

  // --- POST-style boot banner (session-once) ---------------------------
  function wireBoot() {
    const overlay = document.getElementById('boot-overlay');
    if (!overlay) return;
    let already;
    try { already = sessionStorage.getItem('darkprompt-booted'); } catch (e) {}
    const reduced = window.matchMedia &&
                    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (already || reduced) {
      overlay.remove();
      return;
    }

    const linesEl = document.getElementById('boot-lines');
    if (!linesEl) { overlay.remove(); return; }

    const LINES = [
      { tag: '[OK]',   text: 'dispatcher',                 level: 'ok'    },
      { tag: '[OK]',   text: 'sandbox-7c3f',               level: 'ok'    },
      { tag: '[WARN]', text: 'sigverify · expired 7d ago', level: 'warn'  },
      { tag: '[OK]',   text: 'llm 2.4B-Q4 · 14.3 MB',      level: 'ok'    },
      { tag: '[OK]',   text: 'session 0xA17C',             level: 'ok'    },
      { tag: '',       text: 'READY',                      level: 'ready' },
    ];

    overlay.classList.add('is-active');

    let i = 0;
    function nextLine() {
      if (i >= LINES.length) {
        setTimeout(() => {
          overlay.classList.add('is-fading');
          setTimeout(() => overlay.remove(), 420);
        }, 480);
        return;
      }
      const line = LINES[i++];
      const el = document.createElement('div');
      el.className = 'boot-line lvl-' + line.level;
      const tagCls = line.level === 'warn' ? 'tag-warn' :
                     line.level === 'ready' ? 'tag-ready' : 'tag-ok';
      el.innerHTML = line.tag
        ? `<span class="tag ${tagCls}">${line.tag}</span><span class="boot-text">${line.text}</span>`
        : `<span class="boot-text boot-ready">${line.text}</span>`;
      linesEl.appendChild(el);
      setTimeout(nextLine, 95 + Math.random() * 70);
    }
    nextLine();

    try { sessionStorage.setItem('darkprompt-booted', '1'); } catch (e) {}
  }

  // --- Command palette (Cmd+K / Ctrl+K) --------------------------------
  function wirePalette() {
    const palette = document.getElementById('cmd-palette');
    const input   = document.getElementById('palette-input');
    const list    = document.getElementById('palette-list');
    if (!palette || !input || !list) return;

    let items = [];   // [{label, hint, action, kind}]
    let filtered = [];
    let cursor = 0;

    function buildItems() {
      items = [];
      // Conversations from sidebar (chat page)
      document.querySelectorAll('.convo-item').forEach(c => {
        const title = (c.dataset.title || c.querySelector('.convo-title')?.textContent || '').trim();
        if (!title) return;
        items.push({
          label: c.querySelector('.convo-title')?.textContent || title,
          hint: 'Open conversation',
          kind: 'convo',
          action: () => { window.location.href = c.href; },
        });
      });
      // Nav targets — read off existing links so we don't hardcode URLs
      const link = (sel) => document.querySelector(sel)?.href || null;
      const home   = link('a.brand');
      const chat   = link('a[href$="/chat/"]') || '/chat/';
      const login  = link('a[href$="/login/"]');
      const signup = link('a[href$="/signup/"]');
      if (home)   items.push({ label: 'Go to landing',    hint: 'Page',  kind: 'nav', action: () => location.href = home });
      if (chat)   items.push({ label: 'Open chat console', hint: 'Page', kind: 'nav', action: () => location.href = chat });
      if (login)  items.push({ label: 'Sign in',          hint: 'Auth',  kind: 'nav', action: () => location.href = login });
      if (signup) items.push({ label: 'Create account',   hint: 'Auth',  kind: 'nav', action: () => location.href = signup });

      // Actions
      const newBtn = document.getElementById('new-chat-btn');
      if (newBtn) {
        items.push({ label: 'New chat', hint: 'Action', kind: 'action', action: () => { closePalette(); newBtn.click(); } });
      }
    }

    function render() {
      list.innerHTML = '';
      filtered.forEach((it, idx) => {
        const li = document.createElement('li');
        li.className = 'palette-item' + (idx === cursor ? ' is-selected' : '');
        li.dataset.idx = idx;
        li.innerHTML = `
          <span class="palette-kind palette-kind-${it.kind}">${it.kind}</span>
          <span class="palette-label">${escape(it.label)}</span>
          <span class="palette-hint">${escape(it.hint)}</span>
        `;
        li.addEventListener('click', () => { it.action(); });
        list.appendChild(li);
      });
    }
    function escape(s) {
      return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    }

    function filter(query) {
      const q = query.trim().toLowerCase();
      filtered = !q
        ? items.slice(0, 12)
        : items.filter(it => it.label.toLowerCase().includes(q) ||
                             it.hint.toLowerCase().includes(q)).slice(0, 12);
      cursor = Math.min(cursor, Math.max(0, filtered.length - 1));
      render();
    }

    function openPalette() {
      buildItems();
      input.value = '';
      cursor = 0;
      filter('');
      palette.hidden = false;
      requestAnimationFrame(() => palette.classList.add('is-open'));
      input.focus();
    }
    function closePalette() {
      palette.classList.remove('is-open');
      setTimeout(() => { palette.hidden = true; }, 160);
    }

    input.addEventListener('input', () => filter(input.value));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); cursor = Math.min(cursor + 1, filtered.length - 1); render(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); cursor = Math.max(0, cursor - 1); render(); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const it = filtered[cursor];
        if (it) it.action();
      }
      else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
    });
    palette.querySelectorAll('[data-palette-close]').forEach(el =>
      el.addEventListener('click', closePalette));

    document.addEventListener('keydown', (e) => {
      const isTrigger = (e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey);
      if (isTrigger) {
        e.preventDefault();
        if (palette.hidden) openPalette();
        else closePalette();
      }
    });
  }

  // --- Dark — UTC clock + scramble + one-shot terminal typer ----------
  function wireDarkBoot() {
    const reduced = window.matchMedia &&
                    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // UTC clock (some elements append " UTC", preserve initial format)
    const clocks = document.querySelectorAll('[data-dh-clock]');
    if (clocks.length) {
      const pad = (n) => String(n).padStart(2, '0');
      const wantsUtc = Array.from(clocks).map(el => /UTC\s*$/i.test(el.textContent.trim()));
      function tick() {
        const d = new Date();
        const t = pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds());
        clocks.forEach((el, i) => { el.textContent = wantsUtc[i] ? (t + ' UTC') : t; });
      }
      tick();
      setInterval(tick, 1000);
    }

    // Light scramble on a few HUD labels (only when Dark is active)
    if (!reduced) {
      const els = document.querySelectorAll('[data-dh-scramble]');
      if (els.length) {
        const CHARS = '!<>-_/[]=+*^?#0123456789ABCDEF';
        function scramble(el, finalText, duration) {
          const len = finalText.length;
          const start = performance.now();
          function tick(now) {
            const tt = Math.min(1, (now - start) / duration);
            const reveal = Math.floor(tt * len);
            let out = '';
            for (let i = 0; i < len; i++) {
              const c = finalText[i];
              if (i < reveal || c === ' ' || c === '_' || c === ':' || c === '/') out += c;
              else out += CHARS[Math.floor(Math.random() * CHARS.length)];
            }
            el.textContent = out;
            if (tt < 1) requestAnimationFrame(tick);
            else el.textContent = finalText;
          }
          requestAnimationFrame(tick);
        }
        els.forEach((el, i) => {
          const original = el.textContent.trim();
          function loop() {
            const t = document.documentElement.getAttribute('data-theme');
            if (t === 'dark') scramble(el, original, 360 + Math.random() * 320);
            setTimeout(loop, 4200 + Math.random() * 3500);
          }
          setTimeout(loop, 800 + i * 380);
        });
      }
    }

    // Boot sequence + ambient looping commands typer
    const target = document.querySelector('[data-dh-term]');
    if (!target) return;
    const BOOT = [
      { kind: 'cmd', text: '> booting secure environment...' },
      { kind: 'cmd', text: '> loading model: llama3.2:8b' },
      { kind: 'cmd', text: '> allocating local resources' },
      { kind: 'cmd', text: '> establishing sandbox' },
      { kind: 'ok',  text: '> system ready.' },
    ];
    // Lines that keep typing in after boot — picked at random
    const AMBIENT = [
      { kind: 'cmd', text: '> heartbeat 0xA17C · ok' },
      { kind: 'cmd', text: '> sandbox: nominal · 0 escapes' },
      { kind: 'cmd', text: '> rotating session keys' },
      { kind: 'ok',  text: '> egress check: 0 bytes' },
      { kind: 'cmd', text: '> kernel checksum verified' },
      { kind: 'cmd', text: '> probe deflected · src=10.0.0.42' },
      { kind: 'cmd', text: '> idle entropy pool: 78%' },
      { kind: 'cmd', text: '> watcher: alive · 412ms' },
      { kind: 'cmd', text: '> handshake re-verified · sha256 ok' },
      { kind: 'ok',  text: '> exfil_guarantee: 0_bytes' },
      { kind: 'cmd', text: '> telemetry dropped to local drive' },
      { kind: 'cmd', text: '> daemon: anathema_0xA17C live' },
    ];
    const MAX_LINES = 7;  // visible terminal lines (excluding the trailing prompt)

    let runId = 0;
    function appendPrompt() {
      const p = document.createElement('span');
      p.className = 'dh-term-line is-prompt';
      p.innerHTML = '$ <span class="dh-term-cursor"></span>';
      target.appendChild(p);
    }
    function removePrompt() {
      const p = target.querySelector('.dh-term-line.is-prompt');
      if (p) p.remove();
    }
    function trimToMax() {
      // Keep last MAX_LINES non-prompt lines; oldest scroll off the top
      const lines = target.querySelectorAll('.dh-term-line:not(.is-prompt)');
      let excess = lines.length - MAX_LINES;
      while (excess > 0) {
        target.firstElementChild?.remove();
        excess--;
      }
    }
    async function typeLine(line, currentRunId) {
      const lineEl = document.createElement('span');
      lineEl.className = 'dh-term-line is-' + line.kind;
      target.appendChild(lineEl);
      for (let c = 0; c < line.text.length; c++) {
        if (runId !== currentRunId) return false;
        lineEl.textContent = line.text.slice(0, c + 1);
        await wait(14 + Math.random() * 16);
      }
      return true;
    }
    function staticRender() {
      target.innerHTML = BOOT.map(l =>
        `<span class="dh-term-line is-${l.kind}">${l.text}</span>`
      ).join('');
      appendPrompt();
    }
    function clearTerm() { target.innerHTML = ''; }
    function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function run() {
      const myId = ++runId;
      if (reduced) { staticRender(); return; }
      clearTerm();

      // Boot sequence — type one line at a time
      for (const line of BOOT) {
        if (runId !== myId) return;
        if (!(await typeLine(line, myId))) return;
        await wait(220 + Math.random() * 180);
      }
      if (runId !== myId) return;
      appendPrompt();

      // Ambient loop — pause, drop prompt, type a new line, scroll, re-prompt
      while (runId === myId) {
        await wait(2400 + Math.random() * 2200);
        if (runId !== myId) return;
        removePrompt();
        const next = AMBIENT[Math.floor(Math.random() * AMBIENT.length)];
        if (!(await typeLine(next, myId))) return;
        if (runId !== myId) return;
        trimToMax();
        appendPrompt();
      }
    }

    function maybeRun() {
      const t = document.documentElement.getAttribute('data-theme');
      if (t === 'dark') run();
      else clearTerm();
    }

    new MutationObserver(maybeRun).observe(document.documentElement, {
      attributes: true, attributeFilter: ['data-theme'],
    });
    maybeRun();
  }

  // --- boot ------------------------------------------------------------
  // --- Avatar dropdown in dh-nav (top-right) --------------------------
  function wireUserMenu() {
    const wrap = document.querySelector('[data-dh-user]');
    if (!wrap) return;
    const trigger = wrap.querySelector('.dh-user-trigger');
    const menu = wrap.querySelector('.dh-user-menu');
    if (!trigger || !menu) return;

    function open() {
      menu.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      wrap.classList.add('is-open');
    }
    function close() {
      menu.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      wrap.classList.remove('is-open');
    }
    function toggle() {
      if (menu.hidden) open();
      else close();
    }

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      toggle();
    });
    document.addEventListener('click', (e) => {
      if (!wrap.contains(e.target)) close();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !menu.hidden) {
        close();
        trigger.focus();
      }
    });
  }

  function boot() {
    wireBoot();
    ensureNodeId();
    wireReveals();
    buildTelemetry();
    wireMagnetic();
    wirePageTransitions();
    wireCounters();
    wirePasswordToggle();
    wirePasswordStrength();
    wireTooltips();
    wirePalette();
    wireDarkBoot();
    wireUserMenu();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
