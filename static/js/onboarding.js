/* First-visit onboarding tour for the chat console.
   Shows once per browser, persisted via localStorage.
   Triggered: 600ms after chat-shell is in the DOM, only on first visit.
   Re-trigger from anywhere: window.dpReplayTour() */
(function () {
  if (!document.querySelector('.chat-shell')) return;

  const KEY = 'dp.onboarding.v1.done';
  const STEPS = [
    {
      sel:  '#new-chat-btn',
      side: 'right',
      title: 'Start a session',
      body:  'Click here to spin up a fresh conversation. Each session is local, scoped, and exportable.',
    },
    {
      sel:  '#convo-search',
      side: 'right',
      title: 'Search everything',
      body:  'Type to filter titles instantly. Two or more characters runs a full-text search across every message body.',
    },
    {
      sel:  '#chat-input',
      side: 'top',
      title: 'Compose a prompt',
      body:  'Describe the artefact: target OS, language, technique, constraints. Shift+Enter for newline. Ctrl+/ to focus this box.',
    },
    {
      sel:  '#token-meter',
      side: 'bottom',
      title: 'Token + cost meter',
      body:  'Live count of prompt + completion tokens for this session, with an estimated cost. The bar pegs around 50k.',
    },
    {
      sel:  '.dh-user-trigger',
      side: 'bottom-left',
      title: 'Account menu',
      body:  'Settings, sessions, API keys, sign out — all behind your avatar. Press ? any time for the keyboard shortcuts cheat-sheet.',
    },
  ];

  let idx = 0;
  let overlay = null;
  let highlight = null;
  let tooltip = null;
  let onResize = null;

  function build() {
    overlay = document.createElement('div');
    overlay.className = 'dp-tour-overlay';
    overlay.innerHTML = `
      <div class="dp-tour-veil" data-tour-veil></div>
      <div class="dp-tour-spot" data-tour-spot></div>
      <div class="dp-tour-tip" data-tour-tip role="dialog" aria-modal="true" aria-labelledby="dp-tour-title">
        <span class="dp-tour-step mono" data-tour-step></span>
        <h3 class="dp-tour-title" id="dp-tour-title" data-tour-title></h3>
        <p  class="dp-tour-body"  data-tour-body></p>
        <div class="dp-tour-actions">
          <button type="button" class="dp-tour-btn dp-tour-btn-ghost" data-tour-skip>Skip</button>
          <span class="dp-tour-spacer"></span>
          <button type="button" class="dp-tour-btn dp-tour-btn-ghost" data-tour-prev>Back</button>
          <button type="button" class="dp-tour-btn dp-tour-btn-primary" data-tour-next>Next</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    highlight = overlay.querySelector('[data-tour-spot]');
    tooltip   = overlay.querySelector('[data-tour-tip]');
    overlay.querySelector('[data-tour-veil]').addEventListener('click', finish);
    overlay.querySelector('[data-tour-skip]').addEventListener('click', finish);
    overlay.querySelector('[data-tour-prev]').addEventListener('click', prev);
    overlay.querySelector('[data-tour-next]').addEventListener('click', next);
    document.addEventListener('keydown', onKey);
    onResize = () => render();
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onResize, { passive: true });
  }

  function onKey(e) {
    if (!overlay) return;
    if (e.key === 'Escape')                        { e.preventDefault(); finish(); }
    else if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next();   }
    else if (e.key === 'ArrowLeft')                { e.preventDefault(); prev();   }
  }

  function destroy() {
    if (!overlay) return;
    document.removeEventListener('keydown', onKey);
    if (onResize) {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onResize);
    }
    overlay.remove();
    overlay = highlight = tooltip = null;
  }

  function finish() {
    try { localStorage.setItem(KEY, '1'); } catch (_e) {}
    destroy();
  }

  function next() {
    if (idx >= STEPS.length - 1) { finish(); return; }
    idx++; render();
  }
  function prev() {
    if (idx <= 0) return;
    idx--; render();
  }

  function placeTip(rect, side) {
    const PAD = 16;
    const tipRect = tooltip.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let top, left;
    switch (side) {
      case 'right':
        top  = rect.top + rect.height / 2 - tipRect.height / 2;
        left = rect.right + PAD;
        break;
      case 'left':
        top  = rect.top + rect.height / 2 - tipRect.height / 2;
        left = rect.left - tipRect.width - PAD;
        break;
      case 'top':
        top  = rect.top - tipRect.height - PAD;
        left = rect.left + rect.width / 2 - tipRect.width / 2;
        break;
      case 'bottom-left':
        top  = rect.bottom + PAD;
        left = rect.right - tipRect.width;
        break;
      case 'bottom':
      default:
        top  = rect.bottom + PAD;
        left = rect.left + rect.width / 2 - tipRect.width / 2;
    }
    // Clamp inside viewport
    left = Math.max(PAD, Math.min(left, vw - tipRect.width  - PAD));
    top  = Math.max(PAD, Math.min(top,  vh - tipRect.height - PAD));
    tooltip.style.top  = top  + 'px';
    tooltip.style.left = left + 'px';
  }

  function render() {
    if (!overlay) return;
    const step = STEPS[idx];
    let target = step.sel ? document.querySelector(step.sel) : null;
    // If the target is missing (e.g. element hidden on small screens), skip ahead.
    if (!target) {
      if (idx < STEPS.length - 1) { idx++; return render(); }
      finish(); return;
    }
    target.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    const rect = target.getBoundingClientRect();
    const PAD  = 8;
    Object.assign(highlight.style, {
      top:    (rect.top  - PAD) + 'px',
      left:   (rect.left - PAD) + 'px',
      width:  (rect.width  + PAD * 2) + 'px',
      height: (rect.height + PAD * 2) + 'px',
    });

    tooltip.querySelector('[data-tour-step]').textContent = `STEP ${idx + 1} / ${STEPS.length}`;
    tooltip.querySelector('[data-tour-title]').textContent = step.title;
    tooltip.querySelector('[data-tour-body]').textContent  = step.body;
    tooltip.querySelector('[data-tour-prev]').disabled = (idx === 0);
    tooltip.querySelector('[data-tour-next]').textContent =
      (idx === STEPS.length - 1) ? 'Done' : 'Next';

    // Two-pass placement: render to measure, then place.
    tooltip.style.visibility = 'hidden';
    requestAnimationFrame(() => {
      placeTip(rect, step.side);
      tooltip.style.visibility = 'visible';
    });
  }

  function start() {
    idx = 0;
    if (!overlay) build();
    render();
  }

  // Auto-start once per browser, unless the user dismissed before.
  function maybeAutoStart() {
    let done = false;
    try { done = localStorage.getItem(KEY) === '1'; } catch (_e) {}
    if (done) return;
    setTimeout(start, 600);
  }

  // Public API for re-running from a Settings link or shortcut.
  window.dpReplayTour = function () {
    try { localStorage.removeItem(KEY); } catch (_e) {}
    start();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeAutoStart);
  } else {
    maybeAutoStart();
  }
})();
