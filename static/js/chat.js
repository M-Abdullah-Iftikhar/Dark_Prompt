/* Dark Prompt — chat console logic. */
(function () {
  const shell        = document.querySelector('.chat-shell');
  if (!shell) return;
  const apiChat      = shell.dataset.apiChat;
  const apiNew       = shell.dataset.apiNew;
  let activeId       = shell.dataset.activeConversation || '';

  const csrfToken    = document.getElementById('csrf-token-input').value;
  const thread       = document.getElementById('message-thread');
  const form         = document.getElementById('chat-form');
  const input        = document.getElementById('chat-input');
  const sendBtn      = document.getElementById('chat-send');
  const sendLabel    = sendBtn.querySelector('.send-label');
  const sendSpin     = sendBtn.querySelector('.send-spin');
  const tempEl       = document.getElementById('param-temp');
  const tempOut      = document.getElementById('param-temp-out');
  const maxEl        = document.getElementById('param-max');
  const newBtn       = document.getElementById('new-chat-btn');
  const titleEl      = document.getElementById('chat-title');
  const status       = document.getElementById('composer-status');
  const classifierEl = document.getElementById('composer-classifier');

  const toast = (window.dpToast || function(){});

  // ---------- language (asm | c) -----------------------------------------
  const LANG_KEY = 'dp.lang.preference';
  // C is always selectable now — when the live C backend is empty the
  // server falls back to FallbackCodes/Codes_C/ samples.

  // Resolve the active language — for the chat the user is currently viewing.
  let activeLang = (shell.dataset.activeLanguage || 'asm').toLowerCase();
  // Locked = the currently-viewed conversation has at least one message,
  // so its language can't be changed (it's tied to a model already).
  let activeLocked = shell.dataset.activeLocked === '1';

  function readPreferredLang() {
    try {
      const v = (localStorage.getItem(LANG_KEY) || '').toLowerCase();
      if (v === 'c')   return 'c';
      if (v === 'asm') return 'asm';
    } catch (_e) {}
    return activeLang || 'asm';
  }
  function writePreferredLang(lang) {
    try { localStorage.setItem(LANG_KEY, lang); } catch (_e) {}
  }

  // Pending language for the *next* message when no conversation exists yet.
  // For an existing conversation, we always use its own language regardless.
  let pendingLang = readPreferredLang();

  function effectiveLang() {
    // If we have an active convo, that convo's language is law.
    if (activeId) return activeLang || 'asm';
    return pendingLang || 'asm';
  }

  // Toggle UI ---------------------------------------------------------------
  const langToggle = document.getElementById('lang-toggle');
  function paintLangToggle() {
    if (!langToggle) return;
    const showLang = effectiveLang();
    langToggle.querySelectorAll('.lang-toggle-btn').forEach(btn => {
      const isActive = btn.dataset.lang === showLang;
      btn.classList.toggle('is-active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    langToggle.classList.toggle('is-locked', !!activeId && activeLocked);
    langToggle.dataset.activeLang = showLang;
  }
  paintLangToggle();

  async function switchLanguage(toLang) {
    if (toLang !== 'asm' && toLang !== 'c') return;
    // Case A — no active conversation: just update preference + repaint.
    if (!activeId) {
      pendingLang = toLang;
      writePreferredLang(toLang);
      paintLangToggle();
      return;
    }

    // Case B — active convo, no messages yet: flip its language inline.
    if (!activeLocked) {
      const res = await fetch(`/api/conversations/${activeId}/language/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ language: toLang }),
      });
      if (!res.ok) {
        // 409 means it just gained messages between paint and click — fall through to Case C.
        if (res.status !== 409) {
          toast('<span class="toast-tag toast-tag-warn">SWITCH FAILED</span>');
          return;
        }
      } else {
        activeLang  = toLang;
        pendingLang = toLang;
        writePreferredLang(toLang);
        paintLangToggle();
        return;
      }
    }

    // Case C — active convo with messages: confirm + create a new chat.
    const labels = { asm: 'Assembly', c: 'C' };
    const ok = await openConfirm({
      title: `Switch to ${labels[toLang]}?`,
      body: 'This conversation is locked to its current language. Switching will create a brand-new chat in ' + labels[toLang] + ' mode. Your current chat stays untouched and selectable from the sidebar.',
      target: '',
      okLabel: 'Create new chat',
    });
    if (!ok) return;

    pendingLang = toLang;
    writePreferredLang(toLang);
    const res = await fetch(apiNew, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify({ language: toLang }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      toast(`<span class="toast-tag toast-tag-warn">NEW CHAT FAILED</span><span class="toast-meta">${(data.detail || data.error || 'error')}</span>`);
      return;
    }
    const c = await res.json();
    // Navigate to the new chat — full reload keeps the empty-state, boot, etc. consistent.
    window.location.href = `?c=${c.id}`;
  }

  langToggle?.addEventListener('click', (e) => {
    const btn = e.target.closest('.lang-toggle-btn');
    if (!btn) return;
    const target = btn.dataset.lang;
    if (target === effectiveLang()) return;
    switchLanguage(target);
  });

  // ---------- token meter ------------------------------------------------
  const tokenMeter = document.getElementById('token-meter');
  // Soft cap used purely to fill the visual bar — beyond this the bar pegs at 100%.
  const TOKEN_BAR_CEIL = 50000;
  function fmtTokens(n) {
    n = +n || 0;
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 10_000)    return (n / 1000).toFixed(1) + 'k';
    if (n >= 1_000)     return (n / 1000).toFixed(2) + 'k';
    return String(n);
  }
  function fmtCost(usd) {
    const v = +usd || 0;
    if (v < 0.01) return '$' + v.toFixed(4);
    if (v < 1)    return '$' + v.toFixed(3);
    return '$' + v.toFixed(2);
  }
  function updateTokenMeter(totals) {
    if (!tokenMeter || !totals) return;
    const tot = totals.total_tokens ?? 0;
    const cost = totals.cost_usd   ?? 0;
    tokenMeter.dataset.prompt     = totals.prompt_tokens ?? 0;
    tokenMeter.dataset.completion = totals.completion_tokens ?? 0;
    tokenMeter.dataset.total      = tot;
    tokenMeter.dataset.cost       = cost;
    const totEl  = tokenMeter.querySelector('[data-tm-total]');
    const costEl = tokenMeter.querySelector('[data-tm-cost]');
    const barEl  = tokenMeter.querySelector('[data-tm-bar]');
    if (totEl)  totEl.textContent  = fmtTokens(tot);
    if (costEl) costEl.textContent = fmtCost(cost);
    if (barEl) {
      const pct = Math.min(100, (tot / TOKEN_BAR_CEIL) * 100);
      barEl.style.width = pct.toFixed(1) + '%';
      tokenMeter.classList.toggle('is-hot',  tot >= 20000);
      tokenMeter.classList.toggle('is-warn', tot >= 40000);
    }
    tokenMeter.title = `prompt: ${totals.prompt_tokens ?? 0} · completion: ${totals.completion_tokens ?? 0} · total ${tot} · est. ${fmtCost(cost)}`;
  }
  // Initialize from server-rendered values so the bar is correct on first paint.
  if (tokenMeter) {
    updateTokenMeter({
      prompt_tokens:     +tokenMeter.dataset.prompt || 0,
      completion_tokens: +tokenMeter.dataset.completion || 0,
      total_tokens:      +tokenMeter.dataset.total || 0,
      cost_usd:          +tokenMeter.dataset.cost || 0,
    });
  }

  // ---------- styled confirm modal ---------------------------------------
  const cm        = document.getElementById('confirm-modal');
  const cmTitle   = document.getElementById('confirm-modal-title');
  const cmBody    = document.getElementById('confirm-modal-body');
  const cmTarget  = document.getElementById('confirm-modal-target');
  const cmOk      = document.getElementById('confirm-modal-ok');
  const cmCancel  = document.getElementById('confirm-modal-cancel');
  let cmResolver  = null;
  let cmLastFocus = null;

  function openConfirm({ title, body, target, okLabel } = {}) {
    if (!cm) return Promise.resolve(true); // fallback if markup missing
    if (title) cmTitle.textContent = title;
    if (body)  cmBody.textContent  = body;
    if (target) {
      cmTarget.textContent = target;
      cmTarget.hidden = false;
    } else {
      cmTarget.textContent = '';
      cmTarget.hidden = true;
    }
    if (okLabel) {
      const span = cmOk.querySelector('.auth-btn-text');
      if (span) span.textContent = okLabel;
    }
    cmLastFocus = document.activeElement;
    cm.hidden = false;
    cm.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => {
      cm.classList.add('is-open');
      cmOk.focus();
    });
    return new Promise((resolve) => { cmResolver = resolve; });
  }
  function closeConfirm(result) {
    if (!cm || cm.hidden) return;
    cm.classList.remove('is-open');
    cm.setAttribute('aria-hidden', 'true');
    setTimeout(() => { cm.hidden = true; }, 160);
    const r = cmResolver; cmResolver = null;
    if (cmLastFocus && cmLastFocus.focus) cmLastFocus.focus();
    if (r) r(!!result);
  }
  cmOk?.addEventListener('click',     () => closeConfirm(true));
  cmCancel?.addEventListener('click', () => closeConfirm(false));
  cm?.querySelector('[data-modal-dismiss]')?.addEventListener('click', () => closeConfirm(false));
  document.addEventListener('keydown', (e) => {
    if (cm && !cm.hidden) {
      if (e.key === 'Escape') { e.preventDefault(); closeConfirm(false); }
      if (e.key === 'Enter')  { e.preventDefault(); closeConfirm(true); }
    }
  });

  // ---------- LLM-down banner --------------------------------------------
  function llmEndpointLabel(detail) {
    const m = (detail || '').match(/https?:\/\/[^\s]+/);
    return m ? m[0] : '127.0.0.1:5000/generate';
  }
  // ---------- Thinking indicator (rotating cybersec phrases) ----------
  const THINKING_PHRASES = [
    'Walking the PEB',
    'Resolving imports',
    'Probing entropy',
    'Mapping syscalls',
    'Patching IAT',
    'Tracing handles',
    'Pivoting through pipes',
    'Hashing artefacts',
    'Decrypting strings',
    'Carving payload',
    'Unpacking stub',
    'Hooking ntdll',
    'Sniffing packets',
    'Spawning shellcode',
    'Allocating RWX',
    'Bypassing AMSI',
    'Scanning kernel32',
    'Forking persistence',
    'Hijacking COM',
    'Hollowing process',
    'Unhooking EDR',
    'Brute-forcing nonce',
    'Querying registry',
    'Resolving SID',
    'Sweeping FIND_FIRST',
    'Calling int 21h',
    'Aligning sections',
    'Patching signatures',
    'Encoding shellcode',
    'Building IOC list',
  ];

  let thinkingNode  = null;
  let thinkingTimer = null;
  let thinkingStart = 0;

  function pickPhrase(used) {
    // Pick a phrase that wasn't shown in the last 3 ticks, to avoid repeats.
    let p; let guard = 0;
    do {
      p = THINKING_PHRASES[Math.floor(Math.random() * THINKING_PHRASES.length)];
      guard++;
    } while (used.includes(p) && guard < 8);
    return p;
  }

  function showThinking() {
    hideThinking(); // never double-stack
    const node = document.createElement('div');
    node.className = 'msg msg-assistant msg-thinking';
    node.setAttribute('aria-live', 'polite');
    node.setAttribute('aria-busy', 'true');
    node.innerHTML = `
      <div class="msg-meta">
        <span class="msg-who">Dark Prompt</span>
        <span class="msg-time" data-think-elapsed>0.0s</span>
      </div>
      <div class="msg-body">
        <span class="thinking-row">
          <span class="thinking-spinner" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
                 stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9" stroke-opacity="0.20"/>
              <path d="M12 3a9 9 0 0 1 9 9"/>
            </svg>
          </span>
          <span class="thinking-text" data-think-text>Initialising</span>
          <span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>
        </span>
      </div>
    `;
    thread.appendChild(node);
    thread.scrollTop = thread.scrollHeight;
    thinkingNode  = node;
    thinkingStart = performance.now();

    const textEl    = node.querySelector('[data-think-text]');
    const elapsedEl = node.querySelector('[data-think-elapsed]');
    const recent = [];
    function tick() {
      if (!thinkingNode) return;
      const phrase = pickPhrase(recent);
      recent.push(phrase);
      if (recent.length > 3) recent.shift();
      // Soft fade between phrases.
      textEl.style.opacity = '0';
      setTimeout(() => {
        if (!thinkingNode) return;
        textEl.textContent = phrase;
        textEl.style.opacity = '';
      }, 140);
      const secs = ((performance.now() - thinkingStart) / 1000).toFixed(1);
      elapsedEl.textContent = `${secs}s`;
    }
    tick();
    // Update elapsed every 100ms; rotate phrase every ~1.4s.
    thinkingTimer = setInterval(() => {
      const secs = ((performance.now() - thinkingStart) / 1000).toFixed(1);
      if (elapsedEl) elapsedEl.textContent = `${secs}s`;
    }, 100);
    // Rotate phrase on its own slower beat.
    thinkingNode._phraseTimer = setInterval(tick, 1400);
  }

  function hideThinking() {
    if (thinkingTimer) { clearInterval(thinkingTimer); thinkingTimer = null; }
    if (thinkingNode) {
      if (thinkingNode._phraseTimer) clearInterval(thinkingNode._phraseTimer);
      thinkingNode.remove();
      thinkingNode = null;
    }
  }

  function markLastUserFailed(prompt, errorTitle) {
    const lastUser = thread.querySelector('.msg-user:last-of-type');
    if (!lastUser) return;
    lastUser.classList.add('is-failed');
    if (lastUser.querySelector('.msg-failed-bar')) return;
    const bar = document.createElement('div');
    bar.className = 'msg-failed-bar';
    bar.innerHTML = `
      <span class="msg-failed-tag mono">// FAULT</span>
      <span class="msg-failed-text">${(errorTitle || 'Generation failed').replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}</span>
      <button type="button" class="msg-retry-btn" title="Retry this prompt" aria-label="Retry">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 12a9 9 0 1 0 3-6.7"/><polyline points="3 4 3 9 8 9"/>
        </svg>
        <span>Retry</span>
      </button>
    `;
    lastUser.appendChild(bar);
    bar.querySelector('.msg-retry-btn').addEventListener('click', () => {
      bar.remove();
      lastUser.classList.remove('is-failed');
      const banner = thread.querySelector('.llm-banner');
      if (banner) banner.remove();
      input.value = prompt;
      autoGrow();
      updateClassifier();
      form.requestSubmit();
    });
  }

  function showLlmDownBanner(error, lastPrompt) {
    let banner = thread.querySelector('.llm-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.className = 'llm-banner';
      banner.innerHTML = `
        <div class="llm-banner-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 9v4"/><path d="M12 17h.01"/>
            <path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          </svg>
        </div>
        <div class="llm-banner-body">
          <div class="llm-banner-title"></div>
          <div class="llm-banner-detail mono"></div>
        </div>
        <button type="button" class="llm-banner-retry btn btn-ghost btn-sm">Retry</button>
        <button type="button" class="llm-banner-close" aria-label="Dismiss" data-tip="Dismiss">×</button>
      `;
      thread.prepend(banner);
      banner.querySelector('.llm-banner-close').addEventListener('click', () => banner.remove());
      banner.querySelector('.llm-banner-retry').addEventListener('click', async () => {
        const p = banner.dataset.lastPrompt;
        if (!p) { banner.remove(); return; }
        banner.remove();
        input.value = p;
        autoGrow();
        updateClassifier();
        form.requestSubmit();
      });
    }
    const code = (error && error.code) || 'llm_unreachable';
    const titleMap = {
      llm_unreachable: 'LLM endpoint unreachable',
      llm_timeout:     'LLM request timed out',
      llm_error:       'LLM backend returned an error',
      llm_bad_response: 'LLM returned an unexpected response',
      network:         'Network error',
    };
    banner.querySelector('.llm-banner-title').textContent = titleMap[code] || 'LLM error';
    banner.querySelector('.llm-banner-detail').textContent =
      (error && error.detail) || llmEndpointLabel(error && error.detail);
    if (lastPrompt) banner.dataset.lastPrompt = lastPrompt;
    return banner;
  }

  // ---------- helpers ----------------------------------------------------

  const LANG_MAP = {
    c: 'c', h: 'c',
    cpp: 'cpp', 'c++': 'cpp', cxx: 'cpp', hpp: 'cpp',
    cs: 'csharp', csharp: 'csharp',
    py: 'python', python: 'python',
    js: 'javascript', javascript: 'javascript',
    ts: 'typescript', typescript: 'typescript',
    rs: 'rust', rust: 'rust',
    go: 'go', golang: 'go',
    java: 'java',
    rb: 'ruby', ruby: 'ruby',
    php: 'php',
    html: 'html', xml: 'xml',
    css: 'css',
    json: 'json',
    yml: 'yaml', yaml: 'yaml',
    sh: 'bash', bash: 'bash', shell: 'bash', zsh: 'bash',
    ps1: 'powershell', powershell: 'powershell', pwsh: 'powershell',
    bat: 'batch', cmd: 'batch', batch: 'batch',
    asm: 'nasm', nasm: 'nasm', s: 'nasm',
    sql: 'sql',
  };
  const EXT_MAP = {
    c: 'c', cpp: 'cpp', csharp: 'cs', python: 'py', javascript: 'js',
    typescript: 'ts', rust: 'rs', go: 'go', java: 'java', ruby: 'rb',
    php: 'php', html: 'html', xml: 'xml', css: 'css', json: 'json',
    yaml: 'yml', bash: 'sh', powershell: 'ps1', batch: 'bat',
    nasm: 'asm', sql: 'sql',
  };

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // The chat shell carries the active conversation's language so that
  // un-fenced LLM output gets highlighted in the right family.
  function chatLanguage() {
    return (shell.dataset.activeLanguage || 'asm').toLowerCase();
  }

  function detectLang(code) {
    const head = code.slice(0, 1500); // wide enough to clear large header comments
    // C-mode preference: if the conversation is C and the source has any
    // C-shaped tokens, return 'c' before falling into assembly heuristics.
    if (chatLanguage() === 'c') {
      if (/#\s*include\s*[<"]/.test(head)
          || /\b(int|void|char|long|short|float|double|unsigned|signed|static|extern|typedef|struct|enum|union)\b/.test(head)
          || /\b\w+\s*\([^)]*\)\s*\{/.test(head)
          || /\b(printf|fprintf|fopen|fread|fwrite|memcpy|memset|malloc|free|GetProcAddress|VirtualAlloc|CreateThread)\b/.test(head)) {
        return 'c';
      }
    }
    if (/#include\s*</.test(head)) {
      return /\b(std::|namespace\s+std|template\s*<|class\s+\w+\s*[:{])/.test(code) ? 'cpp' : 'c';
    }
    if (/^\s*using\s+System\b/m.test(head) || /\bnamespace\s+\w+\s*{/.test(head)) return 'csharp';
    if (/^\s*(import|from)\s+\w+/m.test(head) || /^\s*def\s+\w+\s*\(/m.test(head)) return 'python';
    if (/\bfn\s+main\s*\(\)/.test(head) || /\blet\s+mut\b/.test(head)) return 'rust';
    if (/^\s*package\s+main\b/m.test(head) || /\bfunc\s+main\s*\(\)/.test(head)) return 'go';
    if (/^\s*(function\s+[A-Z]\w*-\w+|\$[A-Za-z_]+\s*=|Get-\w+|Set-\w+|Invoke-\w+)/m.test(head)) return 'powershell';
    if (/^\s*@echo\s+off\b/im.test(head) || /\bsetlocal\b/im.test(head)) return 'batch';
    if (/^\s*(#!\/bin\/(ba)?sh|#!\/usr\/bin\/env\s+bash)/m.test(head)) return 'bash';
    // x86 / x64 assembly — covers NASM, MASM, TASM, AT&T, and DOS .COM files.
    if (
      /\b(BITS\s+\d+|section\s+\.(text|data|bss)|global\s+_?main|extern\s+\w+)\b/i.test(head) ||
      /^\s*\.(model|code|data|stack|386|486|586|686|startup|exit|radix)\b/im.test(head) ||
      /^\s*(org\s+[0-9a-f]+h?|assume\s+\w+:)/im.test(head) ||
      /^\s*\w+\s+(proc|endp|segment|ends|equ|db|dw|dd|dq|times)\b/im.test(head) ||
      /\b(mov|jmp|jne|jne|jz|jnz|call|ret|push|pop|int|lea|xor|and|or|not|cmp|test|inc|dec|add|sub|mul|div)\s+(byte|word|dword|qword|ptr|short|near|far|cs:|ds:|es:|ss:|fs:|gs:|\[|[a-z]{2,3}\b)/i.test(head)
    ) return 'nasm';
    if (/\b(public|private)\s+(class|static)\b/.test(head) && /\bSystem\.out\.println\b/.test(head)) return 'java';
    if (/^\s*(const|let|var|function|=>|console\.log)\b/m.test(head)) return 'javascript';
    return '';
  }

  // ---------- MITRE ATT&CK auto-tag --------------------------------------
  const MITRE_RULES = [
    { re: /keylog|keystroke|setwindowshookex|wm_keydown|kbd_event|low[- ]?level.*keyboard/i,
      id: 'T1056.001', name: 'KEYBOARD CAPTURE' },
    { re: /screenshot|screen.?capture|gdi.*bitblt|getdesktopwindow|printscreen/i,
      id: 'T1113',     name: 'SCREEN CAPTURE' },
    { re: /process.?inject|reflective.?dll|process.?hollow|writeprocessmemory|createremotethread/i,
      id: 'T1055',     name: 'PROCESS INJECTION' },
    { re: /persist|registry.*\\?run\\?|hkcu.*\\?run|startup.?folder|scheduled.?task|schtasks/i,
      id: 'T1547.001', name: 'BOOT/LOGON AUTOSTART' },
    { re: /enumerate.?process|list.?process|tasklist|win32_process|process.?discovery/i,
      id: 'T1057',     name: 'PROCESS DISCOVERY' },
    { re: /\bc2\b|command.?and.?control|reverse.?shell|beacon|implant/i,
      id: 'T1071.001', name: 'C2 OVER WEB PROTOCOL' },
    { re: /credential|lsass|mimikatz|dump.?pass|sam\.hive|secretsdump/i,
      id: 'T1003.001', name: 'CREDENTIAL DUMPING' },
    { re: /encrypt.*file|ransomware|aes.*encrypt.*file/i,
      id: 'T1486',     name: 'DATA ENCRYPTED' },
    { re: /\bencode\b|base64|obfuscat|xor.?(shellcode|payload|encrypt)/i,
      id: 'T1027',     name: 'OBFUSCATED FILES' },
    { re: /powershell|wscript|cmd\.exe|cmd \/c|mshta|rundll32|regsvr32/i,
      id: 'T1059.001', name: 'CMD / SCRIPTING' },
    { re: /exfil|upload.?(data|file)|http.?post.*body|send.?to.?server/i,
      id: 'T1041',     name: 'EXFIL OVER C2' },
    { re: /evade|bypass.?(av|edr|defender)|disable.?defender|amsi.?bypass|unhook/i,
      id: 'T1562',     name: 'IMPAIR DEFENSES' },
    { re: /uac|elevat|getsystem|token.?steal|seimpersonate/i,
      id: 'T1548.002', name: 'BYPASS UAC' },
  ];
  function mitreTagsFor(text) {
    if (!text) return [];
    const out = []; const seen = new Set();
    for (const r of MITRE_RULES) {
      if (r.re.test(text) && !seen.has(r.id)) {
        out.push(r); seen.add(r.id);
      }
    }
    return out;
  }
  function renderMitrePills(tags) {
    if (!tags.length) return null;
    const div = document.createElement('div');
    div.className = 'mitre-tags';
    div.innerHTML = tags.map(t => `
      <span class="mitre-tag">
        <span class="mitre-id">${t.id}</span>
        <span class="mitre-name">${t.name}</span>
      </span>`).join('');
    return div;
  }

  // ---------- SHA-256 fingerprint ---------------------------------------
  async function sha256Short(text) {
    if (!crypto || !crypto.subtle) return 'unavailable';
    try {
      const buf = new TextEncoder().encode(text || '');
      const hash = await crypto.subtle.digest('SHA-256', buf);
      return Array.from(new Uint8Array(hash)).slice(0, 6)
        .map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (_e) { return 'unavailable'; }
  }
  function startFpChurn(node) {
    const el = node && node.querySelector('[data-fp]');
    if (!el) return null;
    return setInterval(() => {
      let h = '';
      for (let i = 0; i < 12; i++) h += '0123456789abcdef'[Math.floor(Math.random()*16)];
      el.textContent = h;
    }, 80);
  }
  async function settleFingerprint(node, text) {
    const el = node && node.querySelector('[data-fp]');
    if (!el) return;
    const hex = await sha256Short(text);
    el.textContent = hex + '…';
  }

  // ---------- Hex dump --------------------------------------------------
  function toHexDump(text) {
    const bytes = new TextEncoder().encode(text || '');
    const lines = [];
    for (let i = 0; i < bytes.length; i += 16) {
      const chunk = Array.from(bytes.slice(i, i + 16));
      const offset = i.toString(16).padStart(8, '0');
      const hex = chunk.map(b => b.toString(16).padStart(2, '0')).join(' ').padEnd(48, ' ');
      const ascii = chunk.map(b => (b >= 0x20 && b < 0x7f) ? String.fromCharCode(b) : '.').join('');
      lines.push(`${offset}  ${hex}  ${ascii}`);
    }
    if (!lines.length) lines.push('00000000  --                                                .');
    return lines.join('\n');
  }

  // ---------- Verb / classifier ----------------------------------------
  function detectVerb(text) {
    const t = (text || '').toLowerCase();
    if (!t.trim()) return 'dispatch';
    if (/\bcompil(e|ing)|\bbuild\b|\bgcc\b|\bmsvc\b/.test(t))         return 'compile';
    if (/\bevad(e|ing)|\bbypass|\bobfuscat|\bhide\b|\bunhook/.test(t)) return 'evade';
    if (/\binject\b|\bhollow\b|\breflective/.test(t))                  return 'inject';
    if (/\bpersist|\bautostart|\binstall(\s+as)?\s+service|\bschtasks/.test(t)) return 'persist';
    if (/\bencrypt|\bransom/.test(t))                                  return 'encrypt';
    if (/\bexfil|\bupload\b|\bsend.+server/.test(t))                   return 'exfil';
    if (/\bexploit|\bcve-/.test(t))                                    return 'exploit';
    if (/\benumerat|\bdiscover|\brecon\b|\blist\s|\bscan/.test(t))     return 'recon';
    if (/\bdump\b|\bcredential|\blsass/.test(t))                       return 'extract';
    return 'dispatch';
  }

  function detectTarget(text) {
    const t = (text || '').toLowerCase();
    if (/\bwindows|\bwin32|\bwin64|\bpowershell|\bcmd\.exe|\bmsvc|\bmingw/.test(t)) return 'windows';
    if (/\blinux|\bubuntu|\belf\b|\bsystemd|\b\/etc\/|\bbash\b/.test(t))             return 'linux';
    if (/\bmacos|\bosx\b|\bdarwin|\bmach-?o\b/.test(t))                              return 'macos';
    if (/\bandroid|\b\.dex\b|\bapk\b/.test(t))                                       return 'android';
    if (/\bios\b|\biphone/.test(t))                                                  return 'ios';
    return '—';
  }
  const LANG_DETECT = [
    [/\bin\s+c\b|\bc\s+programming|\.c\b|\bgcc\b|\bmsvc\b|\bsetwindowshook|\bwin32\s+api/i, 'c'],
    [/\bc\+\+|\bcpp\b|\bvirtual\s+method/i, 'cpp'],
    [/\bcsharp\b|\bc#\b|\.cs\b|\bdotnet|\bnet\s+framework/i, 'csharp'],
    [/\bpython\b|\.py\b/i, 'python'],
    [/\bpowershell\b|\.ps1\b|\bpwsh\b|\bget-\w+|\binvoke-\w+/i, 'powershell'],
    [/\brust\b|\.rs\b|\bcargo\b/i, 'rust'],
    [/\bgolang\b|\bgo\s+language|\.go\b/i, 'go'],
    [/\bjavascript\b|\bnode\.js|\.js\b/i, 'javascript'],
    [/\bbash\b|\bshell\s+script|\.sh\b/i, 'bash'],
    [/\bnasm\b|\bassembly\b|\bassembler\b|\bx86_?64\b|\.asm\b/i, 'nasm'],
    [/\bbatch\b|\.bat\b|\.cmd\b/i, 'batch'],
  ];
  function detectClassLang(text) {
    for (const [re, name] of LANG_DETECT) if (re.test(text)) return name;
    return '—';
  }

  function updateClassifier() {
    if (!classifierEl) return;
    const t = input.value;
    const target = detectTarget(t);
    const lang   = detectClassLang(t);
    const tags   = mitreTagsFor(t);
    const tech   = tags.length ? tags[0].id : '—';
    const tokens = Math.ceil((t || '').length / 3.7) +
                   parseInt(maxEl.value || 0, 10);
    classifierEl.querySelector('[data-cls="target"]').textContent    = target;
    classifierEl.querySelector('[data-cls="lang"]').textContent      = lang;
    classifierEl.querySelector('[data-cls="technique"]').textContent = tech;
    classifierEl.querySelector('[data-cls="tokens"]').textContent    = tokens.toLocaleString();
    classifierEl.classList.toggle('has-content', t.trim().length > 0);
    sendLabel.textContent = detectVerb(t);
  }

  function looksLikeCode(text) {
    const t = text.trim();
    if (!t) return false;
    const lines = t.split('\n');
    const ASM_MNEMONICS = /\b(mov|jmp|jne|jz|jnz|jc|jnc|jbe|jae|jb|ja|jl|jg|jle|jge|call|ret|retf|retn|push|pop|pushf|popf|int|lea|xor|and|or|not|cmp|test|inc|dec|add|adc|sub|sbb|mul|imul|div|idiv|shl|shr|sal|sar|rol|ror|rcl|rcr|nop|hlt|cli|sti|stosb|stosw|movsb|movsw|cwd|cbw|loop|loopz|loopnz)\b/i;
    const isCMode = chatLanguage() === 'c';
    const C_SHAPED = /^(#\s*include|#\s*define|#\s*ifdef|#\s*ifndef|#\s*pragma|typedef\s+|extern\s+|static\s+|struct\s+\w+|enum\s+\w+|union\s+\w+|return\b|if\s*\(|else\b|for\s*\(|while\s*\(|switch\s*\(|case\s+|break\s*;|continue\s*;|goto\s+|\}\s*;?\s*$|^\s*\}\s*$|\b(int|void|char|long|short|float|double|unsigned|signed)\s+\w)/i;
    const codey = lines.filter(l => {
      const s = l.trim();
      if (!s) return false;
      return (
        /^(\/\/|#|\*|\/\*|;|--|<!--)/.test(s)         ||  // line comment at start
        /\s;\s|\s;[^']/.test(s)                        ||  // inline ; comment (assembly)
        /[{};]\s*$/.test(s)                            ||  // ends with brace / semicolon
        /^(import|include|using|def|fn|func|class|public|private|let|const|var|function|package|namespace|section|global|extern)\b/.test(s) ||
        /^[A-Za-z_]\w*\s*\(/.test(s)                   ||  // function call / definition
        /^\.[a-zA-Z]\w*/.test(s)                       ||  // .directive (TASM/MASM/AT&T)
        /^[A-Za-z_]\w*:\s*($|[A-Za-z;])/.test(s)       ||  // label:  or label: instruction
        /^(org|assume|proc|endp|segment|ends|equ|db|dw|dd|dq|times|bits|format)\b/i.test(s) ||
        /^\w+\s+(proc|endp|segment|ends|equ|db|dw|dd|dq)\b/i.test(s) ||
        (!isCMode && ASM_MNEMONICS.test(s.split(/\s+/, 1)[0])) ||  // first token is an asm mnemonic
        /^[A-Za-z_]\w*\s+(mov|jmp|push|pop|int|call|ret|cmp|lea|add|sub|xor)\b/i.test(s) || // label + mnemonic
        (isCMode && C_SHAPED.test(s))                   // C-shaped lines in C-mode
      );
    }).length;
    return lines.length > 2 && codey / lines.length > 0.30;
  }

  function buildLineGutter(code) {
    const count = code.split('\n').length;
    let html = '';
    for (let i = 1; i <= count; i++) html += `<span class="ln">${i}</span>`;
    return html;
  }

  const _DP_META_RE = /^<!--\s*DP_META:\s*\{[\s\S]*?\}\s*-->\r?\n?/;

  function makeCodeBlock(lang, code) {
    code = code.replace(_DP_META_RE, '');
    const normLang = LANG_MAP[lang] || (lang && Prism.languages[lang] ? lang : '') || '';
    const ext = EXT_MAP[normLang] || normLang || 'txt';
    const display = (normLang || 'plain').toUpperCase();
    let highlighted;
    if (normLang && Prism.languages[normLang]) {
      try {
        highlighted = Prism.highlight(code, Prism.languages[normLang], normLang);
      } catch (e) {
        highlighted = escapeHtml(code);
      }
    } else {
      highlighted = escapeHtml(code);
    }
    const wrap = document.createElement('div');
    wrap.className = 'code-block';
    wrap.dataset.lang = normLang;
    wrap.dataset.ext = ext;
    wrap.innerHTML = `
      <div class="code-head">
        <span class="code-lang">${escapeHtml(display)} <span class="code-ext">.${escapeHtml(ext)}</span></span>
        <span class="code-actions">
          <button type="button" class="code-btn code-btn-run" data-action="analyse"
                  data-tip="Static analysis (no execution)" aria-label="Analyse">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="6"/>
              <path d="m20 20-3.5-3.5"/>
            </svg>
            Analyse
          </button>
          <button type="button" class="code-btn" data-action="hex"
                  data-tip="Toggle hex dump view" aria-label="Hex dump">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M4 7h4M4 12h4M4 17h4"/>
              <path d="M11 7h9M11 12h9M11 17h9"/>
            </svg>
            <span class="code-btn-label">Hex</span>
          </button>
          <button type="button" class="code-btn" data-action="copy"
                  data-tip="Copy to clipboard" aria-label="Copy">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="9" y="9" width="11" height="11" rx="2"/>
              <path d="M5 15V5a2 2 0 0 1 2-2h10"/>
            </svg>
            Copy
          </button>
          <button type="button" class="code-btn" data-action="download"
                  data-tip="Download as .${escapeHtml(ext)}" aria-label="Download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 3v12"/>
              <path d="m7 10 5 5 5-5"/>
              <path d="M5 21h14"/>
            </svg>
            .${escapeHtml(ext)}
          </button>
        </span>
      </div>
      <pre class="language-${escapeHtml(normLang || 'none')}"><span class="ln-gutter" aria-hidden="true">${buildLineGutter(code)}</span><code class="language-${escapeHtml(normLang || 'none')}">${highlighted}</code></pre>
    `;
    wrap.dataset.raw = code;
    return wrap;
  }

  // ---------- code-block "Show all" affordance for long blocks -----------
  function maybeAddExpand(block) {
    requestAnimationFrame(() => {
      const pre = block.querySelector('pre');
      if (!pre) return;
      // re-measure on next frame so Prism + line-numbers are laid out
      requestAnimationFrame(() => {
        if (pre.scrollHeight <= 540) return;
        if (block.querySelector('.code-expand')) return;
        block.classList.add('needs-expand');
        const lines = (block.dataset.raw || '').split('\n').length;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'code-expand';
        btn.dataset.collapsedLabel = `Show all (${lines} lines)`;
        btn.dataset.expandedLabel  = 'Collapse';
        btn.textContent = btn.dataset.collapsedLabel;
        btn.addEventListener('click', () => {
          const expanded = block.classList.toggle('is-expanded');
          btn.textContent = expanded ? btn.dataset.expandedLabel : btn.dataset.collapsedLabel;
        });
        block.appendChild(btn);
      });
    });
  }

  function renderTextChunk(text) {
    const span = document.createElement('div');
    span.className = 'msg-text';
    // simple paragraph-ize: split on blank lines
    const blocks = text.split(/\n{2,}/).map(b => b.trim()).filter(Boolean);
    if (!blocks.length) { span.innerHTML = ''; return span; }
    span.innerHTML = blocks.map(b => {
      // inline-code with single backticks
      const html = escapeHtml(b)
        .replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`)
        .replace(/\n/g, '<br>');
      return `<p>${html}</p>`;
    }).join('');
    return span;
  }

  function renderContent(raw, opts) {
    const showMitre = opts && opts.mitre;
    const frag = document.createDocumentFragment();
    const re = /```([a-zA-Z0-9_+\-]*)\n?([\s\S]*?)```/g;
    let last = 0;
    let m;
    let foundAny = false;
    let mitreInserted = false;
    while ((m = re.exec(raw)) !== null) {
      foundAny = true;
      if (m.index > last) {
        const txt = raw.slice(last, m.index);
        if (txt.trim()) frag.appendChild(renderTextChunk(txt));
      }
      if (showMitre && !mitreInserted) {
        const pills = renderMitrePills(mitreTagsFor(raw));
        if (pills) frag.appendChild(pills);
        mitreInserted = true;
      }
      const cb = makeCodeBlock(m[1] || '', m[2].replace(/\n$/, ''));
      frag.appendChild(cb);
      maybeAddExpand(cb);
      last = m.index + m[0].length;
    }
    if (foundAny) {
      if (last < raw.length) {
        const tail = raw.slice(last);
        if (tail.trim()) frag.appendChild(renderTextChunk(tail));
      }
      return frag;
    }
    if (looksLikeCode(raw)) {
      if (showMitre) {
        const pills = renderMitrePills(mitreTagsFor(raw));
        if (pills) frag.appendChild(pills);
      }
      const cb = makeCodeBlock(detectLang(raw), raw);
      frag.appendChild(cb);
      maybeAddExpand(cb);
      return frag;
    }
    frag.appendChild(renderTextChunk(raw));
    return frag;
  }

  function makeMessageNode(role, time, msgId) {
    const tpl = document.getElementById('msg-template');
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.classList.add(`msg-${role}`);
    node.dataset.role = role;
    if (msgId != null) node.dataset.id = msgId;
    node.querySelector('.msg-who').textContent = role === 'user' ? 'You' : 'Dark Prompt';
    node.querySelector('.msg-time').textContent = time || formatTime(new Date());
    const body = node.querySelector('.msg-body');
    body.innerHTML = '';
    if (role === 'assistant') addMsgActions(node);
    return { node, body };
  }

  function addMsgActions(node) {
    if (node.querySelector('.msg-actions')) return;
    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = `
      <button type="button" class="msg-action" data-action="regen"
              data-tip="Regenerate" aria-label="Regenerate">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>
        </svg>
      </button>
      <button type="button" class="msg-action" data-action="copy-msg"
              data-tip="Copy message" aria-label="Copy message">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="9" y="9" width="11" height="11" rx="2"/>
          <path d="M5 15V5a2 2 0 0 1 2-2h10"/>
        </svg>
      </button>
    `;
    node.appendChild(actions);
  }

  function appendMessage(role, content, time) {
    const { node, body } = makeMessageNode(role, time);
    body.appendChild(renderContent(content));
    thread.appendChild(node);
    thread.scrollTop = thread.scrollHeight;
    const empty = thread.querySelector('.empty-state');
    if (empty) empty.remove();
    return node;
  }

  // ---------- streaming render for newly-arrived assistant messages -----
  function parseParts(raw) {
    const parts = [];
    const re = /```([a-zA-Z0-9_+\-]*)\n?([\s\S]*?)```/g;
    let last = 0; let m; let any = false;
    while ((m = re.exec(raw)) !== null) {
      any = true;
      if (m.index > last) {
        const txt = raw.slice(last, m.index);
        if (txt.trim()) parts.push({ type: 'text', body: txt });
      }
      const fenceLang = m[1] || '';
      const body      = m[2].replace(/\n$/, '');
      // If the fence had no language tag, fall back to detection — important
      // for C-mode chats that emit unfenced or untagged blocks.
      parts.push({ type: 'code', lang: fenceLang || detectLang(body), body });
      last = m.index + m[0].length;
    }
    if (any) {
      if (last < raw.length) {
        const tail = raw.slice(last);
        if (tail.trim()) parts.push({ type: 'text', body: tail });
      }
      return parts;
    }
    if (looksLikeCode(raw)) return [{ type: 'code', lang: detectLang(raw), body: raw }];
    return [{ type: 'text', body: raw }];
  }

  function renderTextHtml(text) {
    const blocks = text.split(/\n{2,}/);
    return blocks.map(b => {
      if (!b) return '';
      const html = escapeHtml(b)
        .replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`)
        .replace(/\n/g, '<br>');
      return `<p>${html}</p>`;
    }).filter(Boolean).join('');
  }

  function streamText(target, text, opts) {
    return new Promise(resolve => {
      const wrap = document.createElement('div');
      wrap.className = 'msg-text streaming';
      target.appendChild(wrap);
      const speed = (opts && opts.speed) || 1100;
      const signal = opts && opts.signal;
      const start = performance.now();
      let bloomed = false;
      function finish(visible) {
        wrap.innerHTML = renderTextHtml(visible);
        wrap.classList.remove('streaming');
        resolve();
      }
      function tick(now) {
        if (signal && signal.aborted) { finish(text); return; }
        const elapsed = now - start;
        const want = Math.min(text.length, Math.floor(elapsed * speed / 1000));
        const visible = text.slice(0, want);
        if (!bloomed && want >= 1) {
          bloomed = true;
          wrap.classList.add('first-bloom');
          setTimeout(() => wrap.classList.remove('first-bloom'), 320);
        }
        wrap.innerHTML = renderTextHtml(visible) +
                         (want < text.length ? '<span class="type-caret"></span>' : '');
        thread.scrollTop = thread.scrollHeight;
        if (want < text.length) requestAnimationFrame(tick);
        else finish(text);
      }
      requestAnimationFrame(tick);
    });
  }

  const SCRAMBLE_CHARS = '0123456789ABCDEFabcdef!@#$%&*?<>/\\|~^=+-';
  function scrambleChar() {
    return SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
  }

  function decryptCode(target, lang, code, opts) {
    return new Promise(resolve => {
      const signal = opts && opts.signal;
      const block = makeCodeBlock(lang, code);
      block.classList.add('is-decrypting');
      target.appendChild(block);
      thread.scrollTop = thread.scrollHeight;

      const codeEl = block.querySelector('code');
      const gutterEl = block.querySelector('.ln-gutter');
      const original = code;
      // Reset the gutter so line numbers grow alongside the typed code
      // instead of pre-allocating all of them up front.
      if (gutterEl) gutterEl.innerHTML = '<span class="ln">1</span>';
      let visibleLines = 1;
      function appendGutterLines(n) {
        if (!gutterEl || n <= 0) return;
        const frag = document.createDocumentFragment();
        for (let i = 0; i < n; i++) {
          visibleLines++;
          const sp = document.createElement('span');
          sp.className = 'ln';
          sp.textContent = String(visibleLines);
          frag.appendChild(sp);
        }
        gutterEl.appendChild(frag);
      }
      // Typewriter feel: chars appended progressively at a steady rate.
      // ~260 chars/sec is roughly "fast typist" — readable but not draggy.
      // Bound by [1.2s, 9s] so tiny snippets aren't instant and huge files
      // don't take forever.
      const charsPerSec = 260;
      const minMs = 1200;
      const maxMs = 9000;
      const naive = (original.length / charsPerSec) * 1000;
      const duration = Math.max(minMs, Math.min(maxMs, naive));
      const start = performance.now();

      // Detect if the user has scrolled up — if so, don't auto-pin to bottom
      // (otherwise typing keeps yanking them back down).
      const isPinned = () => {
        const pad = 80;
        return (thread.scrollHeight - thread.clientHeight - thread.scrollTop) < pad;
      };
      let stickToBottom = isPinned();

      // Render an empty <code> with a blinking caret while typing.
      codeEl.textContent = '';
      const caret = document.createElement('span');
      caret.className = 'type-caret';
      codeEl.appendChild(caret);

      function settle() {
        block.classList.remove('is-decrypting');
        if (caret.parentNode) caret.parentNode.removeChild(caret);
        const normLang = block.dataset.lang;
        if (normLang && Prism.languages[normLang]) {
          codeEl.innerHTML = Prism.highlight(original, Prism.languages[normLang], normLang);
        } else {
          codeEl.textContent = original;
        }
        // Final gutter rebuild — guarantees gutter count == code line count
        // even if the typing was cancelled mid-flight or the chunk math
        // missed a newline at the very tail.
        if (gutterEl) {
          const total = original.split('\n').length;
          let html = '';
          for (let i = 1; i <= total; i++) html += `<span class="ln">${i}</span>`;
          gutterEl.innerHTML = html;
        }
        maybeAddExpand(block);
        resolve();
      }

      let lastWant = 0;
      function tick(now) {
        if (signal && signal.aborted) { settle(); return; }
        const t = Math.min(1, (now - start) / duration);
        const want = Math.floor(t * original.length);
        if (want > lastWant) {
          // Append the new slice as a text node BEFORE the caret so the
          // caret stays at the trailing edge.
          const slice = original.slice(lastWant, want);
          codeEl.insertBefore(document.createTextNode(slice), caret);
          // Grow the gutter by however many newlines just typed, so the
          // line numbers stay in lock-step with the visible code.
          const newlines = (slice.match(/\n/g) || []).length;
          if (newlines) appendGutterLines(newlines);
          lastWant = want;
          if (stickToBottom) {
            thread.scrollTop = thread.scrollHeight;
          } else {
            // User scrolled away — re-check each tick in case they came back.
            stickToBottom = isPinned();
          }
        }
        if (t < 1) requestAnimationFrame(tick);
        else settle();
      }
      requestAnimationFrame(tick);
    });
  }

  // ---------- DP_META marker (Groq-produced wrapper) -------------------
  // The server prepends `<!-- DP_META: {...} -->\n` to assistant messages
  // when classify_prompt / explain_code returned a structured wrapper. The
  // marker survives a page reload so we can rebuild the same UI.
  const DP_META_RE = /^<!--\s*DP_META:\s*(\{[\s\S]*?\})\s*-->\r?\n?/;
  function parseDPMeta(raw) {
    const text = raw || '';
    const m = DP_META_RE.exec(text);
    if (!m) return { meta: null, body: text };
    try {
      return { meta: JSON.parse(m[1]), body: text.slice(m[0].length) };
    } catch (_e) {
      return { meta: null, body: text };
    }
  }

  function makeIntroNode(text) {
    if (!text) return null;
    const el = document.createElement('div');
    el.className = 'msg-intro';
    el.textContent = text;
    return el;
  }

  function makeCardNode(kind, label, text) {
    if (!text) return null;
    const el = document.createElement('div');
    el.className = `msg-card msg-${kind}`;
    el.innerHTML =
      `<span class="msg-card-tag mono">// ${label}</span>` +
      `<div class="msg-card-body"></div>`;
    el.querySelector('.msg-card-body').textContent = text;
    return el;
  }

  function makeSuggestionChips(items) {
    if (!items || !items.length) return null;
    const wrap = document.createElement('div');
    wrap.className = 'msg-suggestions';
    wrap.innerHTML = `<span class="msg-suggestions-label mono">// TRY ONE OF THESE</span>`;
    const list = document.createElement('div');
    list.className = 'msg-suggestions-list';
    items.forEach(s => {
      if (typeof s !== 'string' || !s.trim()) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'suggestion-chip';
      btn.dataset.suggestion = s.trim();
      btn.textContent = s.trim();
      list.appendChild(btn);
    });
    wrap.appendChild(list);
    return wrap;
  }

  function renderAssistantBody(body, meta, cleaned) {
    if (meta && meta.kind === 'chat') {
      const txt = document.createElement('div');
      txt.className = 'msg-text msg-chat-reply';
      txt.textContent = cleaned;
      body.appendChild(txt);
      const chips = makeSuggestionChips(meta.suggestions);
      if (chips) body.appendChild(chips);
      return;
    }
    if (meta && meta.kind === 'code') {
      const intro = makeIntroNode(meta.intro);
      if (intro) body.appendChild(intro);
      body.appendChild(renderContent(cleaned, { mitre: true }));
      const sum = makeCardNode('summary', 'WHAT IT DOES', meta.summary);
      if (sum) body.appendChild(sum);
      const use = makeCardNode('usage', 'HOW TO USE', meta.usage);
      if (use) body.appendChild(use);
      return;
    }
    body.appendChild(renderContent(cleaned, { mitre: true }));
  }

  async function streamAssistantMessage(content, time, signal, msgId, opts) {
    const { node, body } = makeMessageNode('assistant', time, msgId);
    thread.appendChild(node);
    const empty = thread.querySelector('.empty-state');
    if (empty) empty.remove();
    thread.scrollTop = thread.scrollHeight;

    // Churn the SHA fingerprint while streaming
    const churn = startFpChurn(node);

    opts = opts || {};
    const kind = opts.kind || 'code';

    if (kind === 'chat') {
      await streamText(body, content, { signal });
      const chips = makeSuggestionChips(opts.suggestions);
      if (chips) {
        body.appendChild(chips);
        thread.scrollTop = thread.scrollHeight;
      }
      if (churn) clearInterval(churn);
      settleFingerprint(node, content);
      if (signal && signal.aborted) node.classList.add('is-cancelled');
      return node;
    }

    if (opts.intro) {
      const intro = makeIntroNode(opts.intro);
      if (intro) body.appendChild(intro);
    }

    const parts = parseParts(content);
    const tags  = mitreTagsFor(content);
    let mitreInserted = false;

    for (const part of parts) {
      if (signal && signal.aborted) break;
      if (part.type === 'text') {
        await streamText(body, part.body, { signal });
      } else {
        if (!mitreInserted) {
          const pills = renderMitrePills(tags);
          if (pills) body.appendChild(pills);
          mitreInserted = true;
        }
        await decryptCode(body, part.lang, part.body, { signal });
      }
    }

    if (!(signal && signal.aborted)) {
      const sum = makeCardNode('summary', 'WHAT IT DOES', opts.summary);
      if (sum) body.appendChild(sum);
      const use = makeCardNode('usage', 'HOW TO USE', opts.usage);
      if (use) body.appendChild(use);
      if (sum || use) thread.scrollTop = thread.scrollHeight;
    }

    if (churn) clearInterval(churn);
    settleFingerprint(node, content);
    if (signal && signal.aborted) node.classList.add('is-cancelled');
    return node;
  }

  function formatTime(d) {
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  }

  // ---------- existing messages: re-render with code blocks --------------
  document.querySelectorAll('.msg').forEach(msgEl => {
    const body = msgEl.querySelector('.msg-body');
    if (!body) return;
    const raw = body.textContent;
    const isAssistant = msgEl.dataset.role === 'assistant';
    body.innerHTML = '';
    if (isAssistant) {
      const { meta, body: cleaned } = parseDPMeta(raw);
      renderAssistantBody(body, meta, cleaned);
      settleFingerprint(msgEl, cleaned);
      addMsgActions(msgEl);
    } else {
      body.appendChild(renderContent(raw, { mitre: false }));
    }
  });

  // ---------- message action delegation (regenerate / copy-msg) ---------
  thread.addEventListener('click', async (e) => {
    const action = e.target.closest('.msg-action');
    if (!action) return;
    e.preventDefault();
    e.stopPropagation();
    const msg = action.closest('.msg');
    if (!msg) return;
    const id = msg.dataset.id;
    if (action.dataset.action === 'copy-msg') {
      const raw = collectMsgText(msg);
      try {
        await navigator.clipboard.writeText(raw);
        const bytes = new TextEncoder().encode(raw).length;
        const fp = await sha256Short(raw);
        toast(
          `<span class="toast-tag">COPIED</span>` +
          `<span class="toast-meta">${bytes.toLocaleString()} BYTES</span>` +
          `<span class="toast-meta">SHA ${fp}…</span>`
        );
      } catch (_e) {
        toast('<span class="toast-tag toast-tag-warn">COPY FAILED</span>');
      }
      return;
    }
    if (action.dataset.action === 'regen') {
      if (!id) return;
      msg.classList.add('is-regenerating');

      async function doRegenerate(forceNew) {
        const res = await fetch(`/api/messages/${id}/regenerate/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            temperature: parseFloat(tempEl.value),
            max_tokens: parseInt(maxEl.value, 10),
            force_new: !!forceNew,
          }),
        });
        const payload = await res.json().catch(() => ({}));
        return { ok: res.ok, status: res.status, data: payload };
      }

      try {
        let { ok, status, data } = await doRegenerate(false);
        if (!ok) {
          showLlmDownBanner(
            { code: data.error || 'llm_error', detail: data.detail || `HTTP ${status}` }
          );
          return;
        }

        // The current code already compiles cleanly — confirm before
        // generating a fresh variant from the LLM (or fallback corpus).
        if (data.regenerate_kind === 'already_clean') {
          msg.classList.remove('is-regenerating');
          const proceed = await openConfirm({
            title:   'Code is already clean',
            body:    data.detail ||
                     'The current code already compiles cleanly. Generating a new variant will replace it with a fresh sample.',
            target:  '',
            okLabel: 'Generate new variant',
          });
          if (!proceed) return;
          msg.classList.add('is-regenerating');
          ({ ok, status, data } = await doRegenerate(true));
          if (!ok) {
            showLlmDownBanner(
              { code: data.error || 'llm_error', detail: data.detail || `HTTP ${status}` }
            );
            return;
          }
        }

        // Replace this message's body content with the new stream
        const body = msg.querySelector('.msg-body');
        body.innerHTML = '';
        msg.querySelector('.msg-time').textContent =
          formatTime(new Date(data.assistant_message.created_at));
        // Re-trigger fingerprint churn while we render
        const churn = startFpChurn(msg);
        const parts = parseParts(data.assistant_message.content);
        const tags  = mitreTagsFor(data.assistant_message.content);
        let mitreInserted = false;
        for (const part of parts) {
          if (part.type === 'text') {
            await streamText(body, part.body, { speed: 1400 });
          } else {
            if (!mitreInserted) {
              const pills = renderMitrePills(tags);
              if (pills) body.appendChild(pills);
              mitreInserted = true;
            }
            await decryptCode(body, part.lang, part.body);
          }
        }
        if (churn) clearInterval(churn);
        settleFingerprint(msg, data.assistant_message.content);
        addMsgActions(msg);

        if (data.regenerate_kind === 'fixed') {
          toast(
            '<span class="toast-tag">FIXED</span>' +
            '<span class="toast-meta">Compile errors repaired</span>'
          );
        }
      } catch (err) {
        showLlmDownBanner({ code: 'network', detail: err.message || String(err) });
      } finally {
        msg.classList.remove('is-regenerating');
      }
      return;
    }
  });

  function collectMsgText(msg) {
    // Prefer raw code blocks if present, otherwise visible text
    const codeBlocks = msg.querySelectorAll('.code-block');
    if (codeBlocks.length === 1) {
      return codeBlocks[0].dataset.raw || codeBlocks[0].querySelector('code').textContent;
    }
    return msg.querySelector('.msg-body').innerText.trim();
  }

  // ---------- code-block action delegation -------------------------------
  thread.addEventListener('click', (e) => {
    const btn = e.target.closest('.code-btn');
    if (!btn) {
      const ex = e.target.closest('.examples li');
      if (ex && ex.dataset.ex) {
        input.value = ex.dataset.ex;
        input.focus();
        autoGrow();
        return;
      }
      const chip = e.target.closest('.suggestion-chip');
      if (chip && chip.dataset.suggestion) {
        input.value = chip.dataset.suggestion;
        input.focus();
        autoGrow();
        return;
      }
      return;
    }
    const block = btn.closest('.code-block');
    if (!block) return;
    const code = block.dataset.raw || block.querySelector('code').textContent;
    if (btn.dataset.action === 'copy') {
      navigator.clipboard.writeText(code).then(async () => {
        const bytes = new TextEncoder().encode(code).length;
        const fp = await sha256Short(code);
        toast(
          `<span class="toast-tag">COPIED</span>` +
          `<span class="toast-meta">${bytes.toLocaleString()} BYTES</span>` +
          `<span class="toast-meta">SHA ${fp}…</span>`
        );
      }).catch(() => {
        toast('<span class="toast-tag toast-tag-warn">COPY FAILED</span>');
      });
    } else if (btn.dataset.action === 'hex') {
      const codeEl = block.querySelector('code');
      const labelEl = btn.querySelector('.code-btn-label') || btn;
      const isHex = block.classList.toggle('is-hex');
      if (isHex) {
        block.dataset.syntaxHtml = codeEl.innerHTML;
        codeEl.textContent = toHexDump(code);
        labelEl.textContent = 'Source';
      } else {
        codeEl.innerHTML = block.dataset.syntaxHtml || code;
        labelEl.textContent = 'Hex';
      }
    } else if (btn.dataset.action === 'download') {
      const ext = block.dataset.ext || 'txt';
      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dark-prompt.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } else if (btn.dataset.action === 'analyse') {
      runAnalysis(block, btn);
    } else if (btn.dataset.action === 'compile') {
      runCompile(block, btn);
    }
  });

  // ---------- code-block sandbox: analyse + compile ----------------------
  function ensureSandboxPanel(block) {
    let panel = block.querySelector('.code-sandbox');
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'code-sandbox';
      block.appendChild(panel);
    }
    return panel;
  }

  async function runAnalysis(block, btn) {
    const code = block.dataset.raw || block.querySelector('code').textContent;
    const lang = block.dataset.lang || '';
    btn.disabled = true;
    btn.classList.add('is-busy');
    const panel = ensureSandboxPanel(block);
    panel.innerHTML = `<div class="cs-row cs-row-head"><span class="cs-tag mono">// ANALYSING</span><span class="cs-spin mono">···</span></div>`;
    try {
      const res = await fetch('/api/code/analyse/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ code, lang }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        panel.innerHTML = `<div class="cs-row cs-row-fail"><span class="cs-tag mono">// ERROR</span><span>${escapeHtml(data.detail || data.error || ('HTTP ' + res.status))}</span></div>`;
        return;
      }
      renderAnalysis(panel, data, block);
    } catch (e) {
      panel.innerHTML = `<div class="cs-row cs-row-fail"><span class="cs-tag mono">// NETWORK</span><span>${escapeHtml(e.message || String(e))}</span></div>`;
    } finally {
      btn.disabled = false;
      btn.classList.remove('is-busy');
    }
  }

  function renderAnalysis(panel, data, block) {
    const ok = !!data.syntax_ok;
    const hits = (data.api_hits || []).map(h => `
      <li>
        <span class="cs-api-label">${escapeHtml(h.label)}</span>
        <span class="cs-api-tag mono">${escapeHtml(h.tag || '')}</span>
        <span class="cs-api-match mono">${escapeHtml(h.match)}</span>
      </li>`).join('');
    const warnings = (data.warnings || []).map(w => `<li>${escapeHtml(w)}</li>`).join('');
    const compileBtn = data.can_compile
      ? `<button type="button" class="cs-action" data-action="compile">Compile</button>`
      : (data.missing_tool
          ? `<span class="cs-missing mono">missing toolchain: ${escapeHtml(data.missing_tool)}</span>`
          : '');
    panel.innerHTML = `
      <div class="cs-row cs-row-head">
        <span class="cs-tag mono">// ANALYSIS</span>
        <span class="cs-verdict ${ok ? 'cs-ok' : 'cs-fail'} mono">${ok ? 'SYNTAX_OK' : 'SYNTAX_FAIL'}</span>
        <span class="cs-elapsed mono">${data.elapsed_ms}ms</span>
        <span class="cs-spacer"></span>
        ${compileBtn}
      </div>
      ${data.syntax_detail ? `<pre class="cs-detail mono" data-no-copy>${escapeHtml(data.syntax_detail)}</pre>` : ''}
      ${warnings ? `<div class="cs-section"><div class="cs-section-head mono">// WARNINGS</div><ul class="cs-warn">${warnings}</ul></div>` : ''}
      ${hits ? `<div class="cs-section"><div class="cs-section-head mono">// SUSPICIOUS API HITS (${data.api_hits.length})</div><ul class="cs-apis">${hits}</ul></div>` : ''}
    `;
    // Wire the inline Compile button — it's inside the panel, not the head.
    const innerCompile = panel.querySelector('[data-action="compile"]');
    if (innerCompile) {
      innerCompile.addEventListener('click', (e) => {
        e.stopPropagation();
        runCompile(block, innerCompile);
      });
    }

    // If the analyser found real syntax errors (not a soft-degrade like
    // "MinGW headers unavailable"), offer to auto-fix via the regenerate
    // flow — Groq will repair compile + logic bugs while preserving intent.
    const detail = (data.syntax_detail || '').trim();
    const hasRealError = !ok && detail && !/^Skipped\b/i.test(detail);
    if (hasRealError) {
      const msg = block.closest('.msg');
      const regenBtn = msg && msg.querySelector('.msg-action[data-action="regen"]');
      if (regenBtn && !block.dataset.autoFixOffered) {
        block.dataset.autoFixOffered = '1';
        // Defer one tick so the analysis panel paints before the modal.
        setTimeout(() => offerAutoFix(regenBtn), 250);
      }
    }
  }

  async function offerAutoFix(regenBtn) {
    const proceed = await openConfirm({
      title:   'Compile errors detected',
      body:    'The analyser found errors in this code. Regenerate will use Groq to repair compile and logic bugs while preserving the original behaviour. Apply auto-fix now?',
      target:  '',
      okLabel: 'Auto-fix via regenerate',
    });
    if (!proceed) return;
    regenBtn.click();
  }

  async function runCompile(block, btn) {
    const code = block.dataset.raw || block.querySelector('code').textContent;
    const lang = block.dataset.lang || '';
    const panel = ensureSandboxPanel(block);
    btn.disabled = true;
    btn.classList.add('is-busy');
    const buildRow = document.createElement('div');
    buildRow.className = 'cs-build cs-row';
    buildRow.innerHTML = `<span class="cs-tag mono">// COMPILING</span><span class="cs-spin mono">···</span>`;
    panel.appendChild(buildRow);
    try {
      const res = await fetch('/api/code/compile/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ code, lang }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        buildRow.innerHTML = `<span class="cs-tag mono">// COMPILE_ERROR</span><span>${escapeHtml(data.detail || data.error || ('HTTP ' + res.status))}</span>`;
        return;
      }
      renderCompile(buildRow, data);
    } catch (e) {
      buildRow.innerHTML = `<span class="cs-tag mono">// NETWORK</span><span>${escapeHtml(e.message || String(e))}</span>`;
    } finally {
      btn.disabled = false;
      btn.classList.remove('is-busy');
    }
  }

  function renderCompile(row, data) {
    if (data.ok) {
      row.classList.add('cs-row-ok');
      row.innerHTML = `
        <span class="cs-tag mono">// BUILT</span>
        <span class="cs-verdict cs-ok mono">${escapeHtml(data.binary_name || 'binary')}</span>
        <span class="cs-elapsed mono">${data.binary_size ?? 0}B · ${data.elapsed_ms}ms</span>
        <span class="cs-spacer"></span>
        <a class="cs-action cs-action-dl" href="${escapeHtml(data.download_url)}" download>Download</a>
      `;
    } else {
      row.classList.add('cs-row-fail');
      row.innerHTML = `
        <div class="cs-row-head">
          <span class="cs-tag mono">// COMPILE_FAILED</span>
          <span class="cs-elapsed mono">${data.elapsed_ms}ms</span>
        </div>
        ${data.stderr ? `<pre class="cs-detail mono" data-no-copy>${escapeHtml(data.stderr)}</pre>` : ''}
        ${data.stdout ? `<pre class="cs-detail cs-detail-stdout mono" data-no-copy>${escapeHtml(data.stdout)}</pre>` : ''}
      `;
    }
  }

  // ---------- composer ---------------------------------------------------
  function autoGrow() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 220) + 'px';
  }
  input.addEventListener('input', () => { autoGrow(); updateClassifier(); });
  maxEl.addEventListener('input', updateClassifier);
  updateClassifier();
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  tempEl.addEventListener('input', () => {
    tempOut.textContent = parseFloat(tempEl.value).toFixed(2);
  });
  tempOut.textContent = parseFloat(tempEl.value).toFixed(2);

  let activeController = null;     // for fetch abort
  let activeStream = null;         // { aborted: false } for stream abort
  function setSending(on) {
    if (on) {
      sendBtn.dataset.mode = 'stop';
      sendBtn.classList.add('is-stopping');
      sendLabel.textContent = 'stop';
      sendSpin.hidden = false;
      status.textContent = 'Generating…';
    } else {
      sendBtn.dataset.mode = 'send';
      sendBtn.classList.remove('is-stopping');
      sendLabel.textContent = detectVerb(input.value);
      sendSpin.hidden = true;
      status.textContent = '';
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    // If we're already in flight, the click means "stop"
    if (sendBtn.dataset.mode === 'stop') {
      if (activeController) activeController.abort();
      if (activeStream)     activeStream.aborted = true;
      return;
    }
    const prompt = input.value.trim();
    if (!prompt) return;

    appendMessage('user', prompt);
    input.value = '';
    autoGrow();
    updateClassifier();
    setSending(true);
    window.dpAudio?.dispatch();
    showThinking();
    // Lazy permission request — only the first time the user actually
    // dispatches something. The browser shows its native prompt once;
    // after that we never ask again.
    if (window.dpNotify && window.dpNotify.isEnabled() && window.dpNotify.permission() === 'default') {
      window.dpNotify.ensurePermission();
    }
    activeController = new AbortController();

    try {
      const res = await fetch(apiChat, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          instruction: prompt,
          temperature: parseFloat(tempEl.value),
          max_tokens: parseInt(maxEl.value, 10),
          conversation_id: activeId || null,
          language: effectiveLang(),
        }),
        signal: activeController.signal,
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        hideThinking();
        const code = data.error || 'llm_error';
        showLlmDownBanner(
          { code, detail: data.detail || `HTTP ${res.status}` },
          prompt
        );
        const faultLabel = ({
          llm_unreachable:  'LLM endpoint unreachable',
          llm_timeout:      'Request timed out',
          llm_error:        'Backend error',
          llm_bad_response: 'Unexpected response',
        }[code]) || 'Generation failed';
        markLastUserFailed(prompt, faultLabel);
        window.dpAudio?.fault();
        window.dpNotify?.notify({
          title: 'Dark Prompt — generation failed',
          body:  faultLabel,
          tag:   'dp-fault',
        });
        status.textContent = 'Error';
        return;
      }

      hideThinking();
      activeId = String(data.conversation.id);
      shell.dataset.activeConversation = activeId;
      // Conversation now has at least one message — lock its language.
      activeLang   = (data.conversation.language || activeLang || 'asm').toLowerCase();
      activeLocked = true;
      shell.dataset.activeLanguage = activeLang;
      shell.dataset.activeLocked   = '1';
      paintLangToggle();
      titleEl.textContent = data.conversation.title;
      addOrUpdateConvo(data.conversation);
      if (data.session_totals) updateTokenMeter(data.session_totals);
      window.dpAudio?.response();
      // Desktop notification — only fires when the tab is actually hidden.
      const convoTitle = (data.conversation.title || 'New chat').slice(0, 80);
      const previewBody = (data.assistant_message.content || '')
        .replace(/```[\s\S]*?```/g, '[code]')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 140);
      window.dpNotify?.notify({
        title: `Dark Prompt — response ready`,
        body:  previewBody ? `${convoTitle} · ${previewBody}` : convoTitle,
        tag:   `dp-response-${activeId}`,
        onClick: () => {
          // Bring the user back to this exact conversation.
          if (activeId) window.location.href = `?c=${activeId}`;
        },
      });
      // request done — keep "stop" mode active during streaming
      activeController = null;
      activeStream = { aborted: false };
      try {
        const am = data.assistant_message || {};
        await streamAssistantMessage(
          am.content,
          formatTime(new Date(am.created_at)),
          activeStream,
          am.id,
          {
            kind:        am.kind || 'code',
            intro:       am.intro || '',
            summary:     am.summary || '',
            usage:       am.usage || '',
            suggestions: am.suggestions || [],
          },
        );
      } finally {
        activeStream = null;
        setSending(false);
        input.focus();
      }
      return;
    } catch (err) {
      hideThinking();
      if (err && err.name === 'AbortError') {
        // user cancelled
        const lastUser = thread.querySelector('.msg-user:last-of-type');
        if (lastUser) lastUser.classList.add('is-cancelled');
        toast('<span class="toast-tag toast-tag-warn">CANCELLED</span><span class="toast-meta">request aborted</span>');
      } else {
        showLlmDownBanner({ code: 'network', detail: err.message || String(err) }, prompt);
        markLastUserFailed(prompt, 'Network error');
        window.dpAudio?.fault();
        window.dpNotify?.notify({
          title: 'Dark Prompt — network error',
          body:  err.message || 'Could not reach the server.',
          tag:   'dp-fault',
        });
        status.textContent = 'Network error';
      }
    }
    activeController = null;
    setSending(false);
    input.focus();
  });

  // ---------- conversation list ------------------------------------------
  function ensureTodayGroup() {
    const list = document.getElementById('convo-list');
    let group = list.querySelector('.convo-group[data-group-today]');
    if (group) return group;
    // Find any existing Today group by label text — server renders them with mono label.
    for (const g of list.querySelectorAll('.convo-group')) {
      const lbl = g.querySelector('.convo-group-label');
      if (lbl && lbl.textContent.trim() === 'Today') {
        g.dataset.groupToday = '1';
        return g;
      }
    }
    group = document.createElement('div');
    group.className = 'convo-group';
    group.dataset.group = '';
    group.dataset.groupToday = '1';
    group.innerHTML = '<div class="convo-group-label mono">Today</div>';
    list.prepend(group);
    return group;
  }

  function addOrUpdateConvo(c) {
    const list = document.getElementById('convo-list');
    // Drop the "no conversations yet" placeholder if shown
    const empty = list.querySelector('.convo-empty:not(#convo-search-empty)');
    if (empty) empty.remove();

    let item = list.querySelector(`.convo-item[data-id="${c.id}"]`);
    if (!item) {
      item = document.createElement('a');
      item.href = `?c=${c.id}`;
      item.className = 'convo-item';
      item.dataset.id = c.id;
      item.dataset.title = (c.title || '').toLowerCase();
      const lang = (c.language || 'asm').toLowerCase();
      item.dataset.language = lang;
      item.innerHTML = `
        <span class="convo-lang-badge convo-lang-${lang}" aria-label="${lang === 'c' ? 'C' : 'Assembly'}">${lang.toUpperCase()}</span>
        <span class="convo-title"></span>
        <span class="convo-actions">
          <button type="button" class="convo-act convo-pin" data-pin="${c.id}" title="Pin" aria-label="Toggle pin" aria-pressed="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 17v5"/><path d="M9 4h6l-1 7 4 3v2H6v-2l4-3-1-7z"/>
            </svg>
          </button>
          <button type="button" class="convo-act convo-rename" data-rename="${c.id}" title="Rename" aria-label="Rename conversation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M14 4l6 6"/><path d="M3 21l4-1 12-12-3-3L4 17l-1 4z"/>
            </svg>
          </button>
          <button type="button" class="convo-act convo-del" data-del="${c.id}" title="Delete" aria-label="Delete conversation">×</button>
        </span>
      `;
    }
    item.dataset.title = (c.title || '').toLowerCase();
    item.querySelector('.convo-title').textContent = c.title;

    const today = ensureTodayGroup();
    // Place item directly under the group label
    const label = today.querySelector('.convo-group-label');
    label.insertAdjacentElement('afterend', item);

    list.querySelectorAll('.convo-item').forEach(x => x.classList.remove('is-active'));
    item.classList.add('is-active');
    pruneEmptyGroups();
  }

  function pruneEmptyGroups() {
    const list = document.getElementById('convo-list');
    list.querySelectorAll('.convo-group').forEach(g => {
      const remaining = g.querySelectorAll('.convo-item');
      if (!remaining.length) g.remove();
    });
  }

  // ---------- search filter ----------------------------------------------
  // Empty / 1-char query: local title filter (fast).
  // 2+ chars:               server search across titles + message bodies.
  const searchInput = document.getElementById('convo-search');
  const searchEmpty = document.getElementById('convo-search-empty');

  function showAllGroups() {
    document.querySelectorAll('.convo-group').forEach(g => {
      g.style.display = '';
      g.querySelectorAll('.convo-item').forEach(item => { item.style.display = ''; });
    });
    removeSearchResultsGroup();
    if (searchEmpty) searchEmpty.hidden = true;
  }

  function localTitleFilter(q) {
    let totalVisible = 0;
    document.querySelectorAll('.convo-group').forEach(g => {
      if (g.dataset.searchResults) return;
      let visible = 0;
      g.querySelectorAll('.convo-item').forEach(item => {
        const match = !q || (item.dataset.title || '').includes(q);
        item.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      g.style.display = visible ? '' : 'none';
      totalVisible += visible;
    });
    if (searchEmpty) searchEmpty.hidden = (totalVisible !== 0 || !q);
  }

  function removeSearchResultsGroup() {
    document.querySelectorAll('.convo-group[data-search-results]').forEach(g => g.remove());
  }

  function showSearchSkeletons(query) {
    // Hide normal groups and drop a placeholder group with N shimmer rows.
    document.querySelectorAll('.convo-group').forEach(g => {
      if (!g.dataset.searchResults) g.style.display = 'none';
    });
    removeSearchResultsGroup();
    if (searchEmpty) searchEmpty.hidden = true;

    const list = document.getElementById('convo-list');
    const group = document.createElement('div');
    group.className = 'convo-group';
    group.dataset.searchResults = '1';
    group.dataset.skeleton = '1';
    let html = `<div class="convo-group-label mono">Search · ${escapeHtmlInline(query)} <span class="convo-skeleton-spin">···</span></div>`;
    for (let i = 0; i < 4; i++) {
      html += `
        <div class="convo-item convo-skeleton" aria-hidden="true">
          <span class="skeleton-bar skeleton-bar-title"></span>
          <span class="skeleton-bar skeleton-bar-snippet"></span>
        </div>`;
    }
    group.innerHTML = html;
    list.prepend(group);
  }

  function escapeHtmlInline(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function highlightTerm(text, term) {
    if (!term) return escapeHtmlInline(text);
    const safe = escapeHtmlInline(text);
    const re = new RegExp('(' + term.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&') + ')', 'ig');
    return safe.replace(re, '<mark>$1</mark>');
  }

  function renderSearchResults(query, results) {
    // Hide all the regular groups.
    document.querySelectorAll('.convo-group').forEach(g => {
      if (!g.dataset.searchResults) g.style.display = 'none';
    });
    removeSearchResultsGroup();
    if (searchEmpty) searchEmpty.hidden = results.length > 0;

    if (!results.length) return;

    const list = document.getElementById('convo-list');
    const group = document.createElement('div');
    group.className = 'convo-group';
    group.dataset.searchResults = '1';
    group.innerHTML = `<div class="convo-group-label mono">Search · ${escapeHtmlInline(query)}</div>`;
    for (const r of results) {
      const a = document.createElement('a');
      a.href = `?c=${r.id}`;
      a.className = 'convo-item convo-search-hit';
      a.dataset.id = r.id;
      const title = highlightTerm(r.title || 'Untitled', query);
      const snippet = r.kind === 'message' && r.snippet
        ? `<span class="convo-snippet">${highlightTerm(r.snippet, query)}</span>`
        : '';
      a.innerHTML = `<span class="convo-title">${title}</span>${snippet}`;
      group.appendChild(a);
    }
    list.prepend(group);
  }

  let searchTimer = null;
  let searchSeq = 0;
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const raw = searchInput.value.trim();
      if (searchTimer) clearTimeout(searchTimer);
      if (raw.length === 0) { showAllGroups(); return; }
      if (raw.length === 1) { localTitleFilter(raw.toLowerCase()); return; }
      // 2+ chars → server search, debounced. Show skeletons immediately
      // so the user gets visual feedback while we wait for the response.
      showSearchSkeletons(raw);
      const mySeq = ++searchSeq;
      searchTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/conversations/search/?q=${encodeURIComponent(raw)}`);
          if (!res.ok) { localTitleFilter(raw.toLowerCase()); return; }
          const data = await res.json();
          // Discard stale responses
          if (mySeq !== searchSeq) return;
          renderSearchResults(raw, data.results || []);
        } catch (_e) {
          localTitleFilter(raw.toLowerCase());
        }
      }, 220);
    });
    // Esc clears the search
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        searchInput.value = '';
        showAllGroups();
        searchInput.blur();
      }
    });
  }

  // delete conversation
  document.getElementById('convo-list').addEventListener('click', async (e) => {
    const del = e.target.closest('[data-del]');
    if (!del) return;
    e.preventDefault();
    e.stopPropagation();
    const id = del.dataset.del;
    const item = del.closest('.convo-item');
    const targetTitle = item?.querySelector('.convo-title')?.textContent?.trim() || '';
    const ok = await openConfirm({
      title: 'Delete this conversation?',
      body: 'This will permanently remove the session and all of its messages. This action cannot be undone.',
      target: targetTitle ? `> ${targetTitle}` : '',
      okLabel: 'Delete',
    });
    if (!ok) return;
    const res = await fetch(`/api/conversations/${id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
    });
    if (res.ok) {
      item?.remove();
      pruneEmptyGroups();
      if (String(activeId) === String(id)) {
        window.location.href = '/chat/';
      }
    } else {
      toast('Failed to delete conversation.', 'error');
    }
  });

  // ---------- rename conversation ----------------------------------------
  async function renameConversation(id, newTitle) {
    const res = await fetch(`/api/conversations/${id}/rename/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle }),
    });
    if (!res.ok) return null;
    return await res.json();
  }

  function applyConversationTitle(id, newTitle) {
    const item = document.querySelector(`.convo-item[data-id="${id}"]`);
    if (item) {
      item.dataset.title = (newTitle || '').toLowerCase();
      const t = item.querySelector('.convo-title');
      if (t) t.textContent = newTitle;
    }
    if (String(activeId) === String(id) && titleEl) {
      titleEl.textContent = newTitle;
    }
  }

  function startSidebarRename(item) {
    if (!item || item.querySelector('.convo-rename-input')) return;
    const id = item.dataset.id;
    const titleSpan = item.querySelector('.convo-title');
    const original = titleSpan.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'convo-rename-input';
    input.value = original;
    input.maxLength = 255;
    titleSpan.replaceWith(input);
    item.classList.add('is-renaming');
    input.focus();
    input.select();

    let settled = false;
    const finish = async (commit) => {
      if (settled) return; settled = true;
      const next = input.value.trim();
      const newSpan = document.createElement('span');
      newSpan.className = 'convo-title';
      input.replaceWith(newSpan);
      item.classList.remove('is-renaming');
      if (commit && next && next !== original) {
        const data = await renameConversation(id, next);
        if (data && data.title) {
          applyConversationTitle(id, data.title);
        } else {
          newSpan.textContent = original;
          toast('Rename failed.', 'error');
        }
      } else {
        newSpan.textContent = original;
      }
    };
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter')  { e.preventDefault(); finish(true); }
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
    });
    input.addEventListener('blur', () => finish(true));
    // prevent the surrounding <a> from navigating while editing
    input.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); });
  }

  document.getElementById('convo-list').addEventListener('click', (e) => {
    const ren = e.target.closest('[data-rename]');
    if (!ren) return;
    e.preventDefault();
    e.stopPropagation();
    const item = ren.closest('.convo-item');
    startSidebarRename(item);
  });

  // ---------- pin / unpin conversation -----------------------------------
  function ensurePinnedGroup() {
    const list = document.getElementById('convo-list');
    let group = list.querySelector('.convo-group[data-group-pinned]');
    if (group) return group;
    for (const g of list.querySelectorAll('.convo-group')) {
      const lbl = g.querySelector('.convo-group-label');
      if (lbl && lbl.textContent.trim() === 'Pinned') {
        g.dataset.groupPinned = '1';
        return g;
      }
    }
    group = document.createElement('div');
    group.className = 'convo-group';
    group.dataset.group = '';
    group.dataset.groupPinned = '1';
    group.innerHTML = '<div class="convo-group-label mono">Pinned</div>';
    list.prepend(group);
    return group;
  }

  function applyPinState(item, pinned) {
    if (!item) return;
    item.dataset.pinned = pinned ? '1' : '0';
    item.classList.toggle('is-pinned', !!pinned);
    const btn = item.querySelector('.convo-pin');
    if (btn) {
      btn.setAttribute('aria-pressed', pinned ? 'true' : 'false');
      btn.setAttribute('title', pinned ? 'Unpin' : 'Pin');
      const svg = btn.querySelector('svg');
      if (svg) svg.setAttribute('fill', pinned ? 'currentColor' : 'none');
    }
    if (pinned) {
      const group = ensurePinnedGroup();
      const label = group.querySelector('.convo-group-label');
      label.insertAdjacentElement('afterend', item);
    } else {
      const today = ensureTodayGroup();
      const label = today.querySelector('.convo-group-label');
      label.insertAdjacentElement('afterend', item);
    }
    pruneEmptyGroups();
  }

  document.getElementById('convo-list').addEventListener('click', async (e) => {
    const pinBtn = e.target.closest('[data-pin]');
    if (!pinBtn) return;
    e.preventDefault();
    e.stopPropagation();
    const item = pinBtn.closest('.convo-item');
    if (!item) return;
    const id = pinBtn.dataset.pin;
    const want = item.dataset.pinned !== '1';
    const res = await fetch(`/api/conversations/${id}/pin/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: want }),
    });
    if (!res.ok) {
      toast('Pin failed.', 'error');
      return;
    }
    const data = await res.json();
    applyPinState(item, !!data.is_pinned);
  });

  // Header rename button — prompt-style inline overlay on the title
  const headerRenameBtn = document.getElementById('chat-rename-btn');
  function startHeaderRename() {
    if (!titleEl || !titleEl.dataset.id) return;
    if (titleEl.querySelector('input')) return;
    const id = titleEl.dataset.id;
    const original = titleEl.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'chat-title-input';
    input.value = original;
    input.maxLength = 255;
    titleEl.textContent = '';
    titleEl.appendChild(input);
    input.focus();
    input.select();

    let settled = false;
    const finish = async (commit) => {
      if (settled) return; settled = true;
      const next = input.value.trim();
      titleEl.textContent = original;
      if (commit && next && next !== original) {
        const data = await renameConversation(id, next);
        if (data && data.title) {
          applyConversationTitle(id, data.title);
        } else {
          toast('Rename failed.', 'error');
        }
      }
    };
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter')  { e.preventDefault(); finish(true); }
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
    });
    input.addEventListener('blur', () => finish(true));
  }
  headerRenameBtn?.addEventListener('click', startHeaderRename);
  titleEl?.addEventListener('dblclick', startHeaderRename);

  // ---------- export menu ------------------------------------------------
  const exportBtn  = document.getElementById('chat-export-btn');
  const exportMenu = document.getElementById('chat-export-menu');
  const exportWrap = document.getElementById('chat-export-wrap');
  function closeExport() {
    if (!exportMenu) return;
    exportMenu.hidden = true;
    exportBtn?.setAttribute('aria-expanded', 'false');
  }
  function openExport() {
    if (!exportMenu) return;
    exportMenu.hidden = false;
    exportBtn?.setAttribute('aria-expanded', 'true');
  }
  exportBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (exportMenu.hidden) openExport(); else closeExport();
  });
  document.addEventListener('click', (e) => {
    if (!exportWrap) return;
    if (!exportWrap.contains(e.target)) closeExport();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeExport();
  });
  exportMenu?.addEventListener('click', () => closeExport());

  // new chat
  function showNewChatSkeleton() {
    const list = document.getElementById('convo-list');
    if (!list || list.querySelector('.convo-item.convo-skeleton[data-pending-new]')) return;
    const today = ensureTodayGroup();
    const skel = document.createElement('div');
    skel.className = 'convo-item convo-skeleton';
    skel.dataset.pendingNew = '1';
    skel.setAttribute('aria-hidden', 'true');
    skel.innerHTML = `<span class="skeleton-bar skeleton-bar-title"></span>`;
    today.querySelector('.convo-group-label')?.insertAdjacentElement('afterend', skel);
  }
  function clearNewChatSkeleton() {
    document.querySelectorAll('.convo-item.convo-skeleton[data-pending-new]').forEach(el => el.remove());
  }

  newBtn.addEventListener('click', async () => {
    showNewChatSkeleton();
    const lang = readPreferredLang();
    const res = await fetch(apiNew, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: lang }),
    });
    if (!res.ok) { clearNewChatSkeleton(); return; }
    const c = await res.json();
    clearNewChatSkeleton();
    activeId = String(c.id);
    shell.dataset.activeConversation = activeId;
    titleEl.textContent = c.title;
    activeLang = (c.language || lang).toLowerCase();
    activeLocked = false;
    shell.dataset.activeLanguage = activeLang;
    shell.dataset.activeLocked   = '0';
    pendingLang = activeLang;
    paintLangToggle();
    addOrUpdateConvo(c);
    // clear thread
    thread.innerHTML = '';
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `
      <img class="empty-logo" src="/static/img/logo.png" alt="" aria-hidden="true">
      <h2>New session</h2>
      <p class="muted">Describe what you want generated.</p>
    `;
    thread.appendChild(empty);
    updateTokenMeter({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, cost_usd: 0 });
    input.focus();
  });

  // ---------- desktop sidebar collapse (persisted in localStorage) ------
  const SIDEBAR_KEY = 'dp.sidebar.collapsed';
  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  const expandBtn   = document.getElementById('sidebar-expand-btn');
  function applySidebarState(collapsed) {
    shell.classList.toggle('is-sidebar-collapsed', !!collapsed);
    if (collapseBtn) {
      collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseBtn.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    }
    try { localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0'); } catch (_e) {}
  }
  let initiallyCollapsed = false;
  try { initiallyCollapsed = localStorage.getItem(SIDEBAR_KEY) === '1'; } catch (_e) {}
  applySidebarState(initiallyCollapsed);
  collapseBtn?.addEventListener('click', () => {
    applySidebarState(!shell.classList.contains('is-sidebar-collapsed'));
  });
  expandBtn?.addEventListener('click', () => applySidebarState(false));

  // ---------- mobile drawer ----------------------------------------------
  const menuBtn       = document.getElementById('chat-menu-btn');
  const drawerBackdrop = document.getElementById('chat-drawer-backdrop');
  function openDrawer() { shell.classList.add('is-drawer-open'); }
  function closeDrawer() { shell.classList.remove('is-drawer-open'); }
  menuBtn?.addEventListener('click', () => {
    if (shell.classList.contains('is-drawer-open')) closeDrawer();
    else openDrawer();
  });
  drawerBackdrop?.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });
  // close drawer on convo click (small screens)
  document.getElementById('convo-list').addEventListener('click', (e) => {
    if (e.target.closest('.convo-item') && !e.target.closest('.convo-del')) {
      if (window.matchMedia('(max-width: 900px)').matches) {
        // small delay so the link nav isn't visually clipped
        setTimeout(closeDrawer, 50);
      }
    }
  });

  // ---------- empty-state rotating tips ----------------------------------
  const TIPS = [
    'Iterate temperature 0.4–0.9 to vary the signature surface across runs.',
    'Append "show only the code" to skip prose for cleaner artefacts.',
    'Specify the API surface (e.g. SetWindowsHookEx, NtCreateThreadEx) for tighter output.',
    'Click the Hex toggle on a code block to inspect byte-level patterns.',
    'MITRE pills above each artefact map back to ATT&CK techniques.',
    'Use Shift+Enter in the composer for multi-line prompts.',
    'The SHA fingerprint next to each reply identifies the artefact uniquely.',
  ];
  function rotateTip() {
    const el = document.getElementById('empty-tip-text');
    if (!el) return;
    let idx = 0;
    setInterval(() => {
      idx = (idx + 1) % TIPS.length;
      el.classList.add('is-fading');
      setTimeout(() => {
        el.textContent = TIPS[idx];
        el.classList.remove('is-fading');
      }, 240);
    }, 7000);
  }
  rotateTip();

  // initial scroll to bottom
  thread.scrollTop = thread.scrollHeight;
  input.focus();
})();
