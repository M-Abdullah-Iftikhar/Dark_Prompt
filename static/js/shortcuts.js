/* Global keyboard shortcuts + cheat-sheet (?) modal.
   Shortcuts (active everywhere unless typing in an input/textarea):
     ?              — open cheat-sheet
     g h            — go to landing
     g c            — go to console (chat)
     g s            — go to settings
     g a            — go to activity log
   On the chat page additionally:
     Ctrl/Cmd+K      — focus conversation search
     Ctrl/Cmd+/      — focus prompt textarea
     Ctrl/Cmd+Shift+N — new chat
     Esc            — close drawer / dismiss cheat-sheet                  */
(function () {
  const URLS = (window.dpUrls || {});
  const isTyping = (el) => {
    if (!el) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    return false;
  };

  function $(id) { return document.getElementById(id); }

  // ---------- cheat-sheet modal --------------------------------------
  let modal = null;
  function buildModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'dh-modal kb-cheat';
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="dh-modal-backdrop" data-modal-dismiss></div>
      <div class="dh-modal-card" role="dialog" aria-modal="true" aria-labelledby="kb-cheat-title">
        <span class="auth-corner auth-corner-tl" aria-hidden="true"></span>
        <span class="auth-corner auth-corner-tr" aria-hidden="true"></span>
        <span class="auth-corner auth-corner-bl" aria-hidden="true"></span>
        <span class="auth-corner auth-corner-br" aria-hidden="true"></span>

        <span class="dh-modal-tag mono">// KEYBINDINGS</span>
        <h2 class="dh-modal-title" id="kb-cheat-title">Shortcuts</h2>

        <div class="kb-grid">
          <h3 class="kb-section">Global</h3>
          <dl>
            <div><dt><kbd>?</kbd></dt><dd>Open this cheat-sheet</dd></div>
            <div><dt><kbd>g</kbd> <kbd>h</kbd></dt><dd>Home / landing</dd></div>
            <div><dt><kbd>g</kbd> <kbd>c</kbd></dt><dd>Console (chat)</dd></div>
            <div><dt><kbd>g</kbd> <kbd>s</kbd></dt><dd>Settings</dd></div>
            <div><dt><kbd>g</kbd> <kbd>a</kbd></dt><dd>Activity log</dd></div>
            <div><dt><kbd>Esc</kbd></dt><dd>Close dialog / drawer</dd></div>
          </dl>

          <h3 class="kb-section">Chat console</h3>
          <dl>
            <div><dt><kbd>Ctrl</kbd>+<kbd>K</kbd></dt><dd>Focus conversation search</dd></div>
            <div><dt><kbd>Ctrl</kbd>+<kbd>/</kbd></dt><dd>Focus prompt</dd></div>
            <div><dt><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd></dt><dd>New chat</dd></div>
            <div><dt><kbd>Enter</kbd></dt><dd>Send prompt</dd></div>
            <div><dt><kbd>Shift</kbd>+<kbd>Enter</kbd></dt><dd>Newline in prompt</dd></div>
          </dl>
        </div>

        <div class="dh-modal-actions">
          <button type="button" class="auth-btn auth-btn-ghost" data-modal-dismiss>
            <span class="auth-btn-text">Close</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('[data-modal-dismiss]').forEach((el) => {
      el.addEventListener('click', closeCheat);
    });
    return modal;
  }
  function openCheat() {
    buildModal();
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => modal.classList.add('is-open'));
  }
  function closeCheat() {
    if (!modal || modal.hidden) return;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    setTimeout(() => { if (modal) modal.hidden = true; }, 160);
  }
  function toggleCheat() {
    if (modal && !modal.hidden) closeCheat(); else openCheat();
  }

  // ---------- chord state ('g' followed by another key) --------------
  let chord = null;
  let chordTimer = null;
  function clearChord() {
    chord = null;
    if (chordTimer) { clearTimeout(chordTimer); chordTimer = null; }
  }

  // ---------- main keydown handler -----------------------------------
  document.addEventListener('keydown', (e) => {
    // Always allow Esc to close cheat
    if (e.key === 'Escape' && modal && !modal.hidden) {
      e.preventDefault(); closeCheat(); return;
    }

    // Skip when typing — except for the modifier-based chat shortcuts.
    const typing = isTyping(document.activeElement);
    const meta = e.metaKey || e.ctrlKey;

    // Chat-context modifier shortcuts (work even while typing)
    const onChat = !!document.querySelector('.chat-shell');
    if (onChat && meta) {
      if (e.key.toLowerCase() === 'k' && !e.shiftKey && !e.altKey) {
        const search = document.getElementById('convo-search');
        if (search) { e.preventDefault(); search.focus(); search.select(); return; }
      }
      if (e.key === '/' && !e.shiftKey && !e.altKey) {
        const input = document.getElementById('chat-input');
        if (input) { e.preventDefault(); input.focus(); return; }
      }
      if ((e.key === 'N' || e.key === 'n') && e.shiftKey && !e.altKey) {
        const newBtn = document.getElementById('new-chat-btn');
        if (newBtn) { e.preventDefault(); newBtn.click(); return; }
      }
    }

    if (typing) { clearChord(); return; }
    if (meta || e.altKey) { clearChord(); return; }

    // ? — open cheat-sheet (Shift+/ on US keyboard)
    if (e.key === '?') {
      e.preventDefault(); toggleCheat(); return;
    }

    // chord: 'g' then h/c/s/a
    if (chord === 'g') {
      const k = e.key.toLowerCase();
      const target = (
        k === 'h' ? URLS.landing :
        k === 'c' ? URLS.chat :
        k === 's' ? URLS.settings :
        k === 'a' ? URLS.activity : null
      );
      clearChord();
      if (target) { e.preventDefault(); window.location.href = target; }
      return;
    }
    if (e.key.toLowerCase() === 'g') {
      chord = 'g';
      chordTimer = setTimeout(clearChord, 1200);
      return;
    }
  });
})();
