/* Desktop notifications for Dark Prompt.
   ON by default. Toggle in Settings (browser-local preference).
   Fires only when:
     - feature is enabled in localStorage (default true)
     - browser permission is "granted"
     - the page is currently hidden (document.hidden)
   Permission is requested the first time the user dispatches a chat —
   the browser surfaces its native prompt, we don't add a custom UI for it. */
(function () {
  const KEY = 'dp.notifications.enabled';
  const supported = typeof window.Notification !== 'undefined';

  function isEnabled() {
    if (!supported) return false;
    try {
      // Default true: anything other than the literal "0" counts as enabled.
      const v = localStorage.getItem(KEY);
      return v !== '0';
    } catch (_e) { return true; }
  }
  function setEnabled(on) {
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (_e) {}
  }

  function permission() {
    return supported ? Notification.permission : 'unsupported';
  }

  /** Request browser permission if it hasn't been answered yet.
   *  Returns the resulting state: "granted" / "denied" / "default" / "unsupported".
   *  Called lazily by chat.js on first dispatch so we never nag a user
   *  who hasn't engaged with the chat yet. */
  async function ensurePermission() {
    if (!supported) return 'unsupported';
    if (Notification.permission === 'granted') return 'granted';
    if (Notification.permission === 'denied')  return 'denied';
    try {
      const result = await Notification.requestPermission();
      return result;
    } catch (_e) {
      return 'default';
    }
  }

  /** Fire a desktop notification, but only if the app is hidden.
   *  Silently no-ops in every other state (focused window, perm denied,
   *  feature disabled, browser without API support). */
  function notify({ title, body, tag, icon, onClick } = {}) {
    if (!supported)              return null;
    if (!isEnabled())            return null;
    if (Notification.permission !== 'granted') return null;
    // Only notify when the user is NOT currently looking at the page.
    if (!document.hidden)        return null;

    const opts = {
      body:    body || '',
      tag:     tag  || 'dark-prompt',  // duplicates collapse onto the same toast
      icon:    icon || '/static/img/icon-192.png',
      badge:   '/static/img/icon-192.png',
      renotify: true,
      silent:  false,
    };
    let n;
    try {
      n = new Notification(title || 'Dark Prompt', opts);
    } catch (_e) {
      return null;
    }
    n.addEventListener('click', () => {
      try { window.focus(); } catch (_e) {}
      if (onClick) {
        try { onClick(); } catch (_e) {}
      }
      n.close();
    });
    // Auto-close after 8s in case the OS doesn't.
    setTimeout(() => { try { n.close(); } catch (_e) {} }, 8000);
    return n;
  }

  // Public API used by chat.js + the settings toggle.
  window.dpNotify = {
    supported,
    isEnabled,
    setEnabled,
    permission,
    ensurePermission,
    notify,
  };
})();
