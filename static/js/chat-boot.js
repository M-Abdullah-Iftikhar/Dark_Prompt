/* Chat-page boot sequence — types a brief handshake into the empty state
   on first /chat/ visit per browser session. Inert when the thread already
   has messages or when the user prefers reduced motion. */
(function () {
  if (!document.querySelector('.chat-shell')) return;

  const KEY = 'darkprompt-chat-booted';
  let alreadyBooted = false;
  try { alreadyBooted = sessionStorage.getItem(KEY) === '1'; } catch (_e) {}
  const reduced = window.matchMedia &&
                  window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (alreadyBooted || reduced) return;

  // Only boot when there's no existing conversation — otherwise the user
  // came back to a real session and shouldn't see a fresh handshake.
  const empty = document.querySelector('.empty-state');
  if (!empty) return;

  // Hide the existing empty-state body until the boot finishes.
  empty.classList.add('is-booting');

  const host = document.createElement('div');
  host.className = 'chat-boot';
  host.setAttribute('aria-hidden', 'true');
  host.innerHTML = `<pre class="chat-boot-pre" data-no-copy></pre>`;
  empty.parentNode.insertBefore(host, empty);

  const pre = host.querySelector('.chat-boot-pre');

  const LINES = [
    ['HANDSHAKE',  'OK',                   'ok'],
    ['MODEL',      'llama3.2:8b',          'ok'],
    ['QUANT',      'Q4_K_M',               'ok'],
    ['CTX',        '8192',                 'ok'],
    ['TLS',        'local // ENC ✓',       'ok'],
    ['SIGVERIFY',  'expired 7d ago',       'warn'],
    ['SESSION',    '0x' + (Math.random().toString(16).slice(2, 6).toUpperCase() + '····').slice(0, 8), 'ok'],
    ['READY',      '_',                    'ready'],
  ];

  function pad(s, n) { return (s + '          ').slice(0, n); }

  let i = 0;
  function nextLine() {
    if (i >= LINES.length) {
      setTimeout(() => {
        host.classList.add('is-fading');
        empty.classList.remove('is-booting');
        empty.classList.add('is-revealed');
        setTimeout(() => host.remove(), 520);
      }, 380);
      return;
    }
    const [k, v, level] = LINES[i++];
    const line = document.createElement('span');
    line.className = 'chat-boot-line lvl-' + level;
    const tag = level === 'warn'  ? '[WARN]' :
                level === 'ready' ? '[ OK ]' : '[ OK ]';
    line.innerHTML =
      `<span class="cb-tag cb-${level}">${tag}</span>` +
      `<span class="cb-key">${pad(k, 11)}</span>` +
      `<span class="cb-val">${v}</span>`;
    pre.appendChild(line);
    pre.appendChild(document.createTextNode('\n'));
    setTimeout(nextLine, 95 + Math.random() * 70);
  }
  nextLine();

  try { sessionStorage.setItem(KEY, '1'); } catch (_e) {}
})();
