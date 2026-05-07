/* Decorate any plain <pre> with a hover-revealed copy button.
   Skips:
     - <pre> already inside .code-block (chat already wires its own actions)
     - <pre data-no-copy> (opt-out)
     - <pre class="dh-term-body"> (typed terminal animation)               */
(function () {
  function attach(pre) {
    if (pre.dataset.copyBound) return;
    if (pre.closest('.code-block')) return;
    if (pre.dataset.noCopy !== undefined) return;
    if (pre.classList.contains('dh-term-body')) return;
    pre.dataset.copyBound = '1';

    const wrap = document.createElement('div');
    wrap.className = 'pre-copy-wrap';
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pre-copy-btn';
    btn.setAttribute('aria-label', 'Copy code');
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="9" width="11" height="11" rx="2"/>
        <path d="M5 15V5a2 2 0 0 1 2-2h10"/>
      </svg>
      <span class="pre-copy-label">Copy</span>`;
    wrap.appendChild(btn);

    btn.addEventListener('click', async () => {
      const code = pre.innerText;
      try {
        await navigator.clipboard.writeText(code);
        btn.classList.add('is-ok');
        btn.querySelector('.pre-copy-label').textContent = 'Copied';
        setTimeout(() => {
          btn.classList.remove('is-ok');
          btn.querySelector('.pre-copy-label').textContent = 'Copy';
        }, 1400);
      } catch (_e) {
        btn.classList.add('is-err');
        btn.querySelector('.pre-copy-label').textContent = 'Failed';
        setTimeout(() => {
          btn.classList.remove('is-err');
          btn.querySelector('.pre-copy-label').textContent = 'Copy';
        }, 1400);
      }
    });
  }

  function scan(root) {
    (root || document).querySelectorAll('pre').forEach(attach);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => scan());
  } else {
    scan();
  }

  // Re-scan when new content gets inserted (e.g. SPA-ish swaps, async renders).
  const obs = new MutationObserver((muts) => {
    for (const m of muts) {
      m.addedNodes.forEach((n) => {
        if (n.nodeType !== 1) return;
        if (n.tagName === 'PRE') attach(n);
        else if (n.querySelectorAll) n.querySelectorAll('pre').forEach(attach);
      });
    }
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });
})();
