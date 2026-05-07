/* Optional audio cues for dispatch + response. Synth-only via Web Audio,
   no asset files. Off by default; toggle persisted in localStorage. */
(function () {
  const KEY = 'dp.audio.enabled';
  let ctx = null;

  function isEnabled() {
    try { return localStorage.getItem(KEY) === '1'; } catch (_e) { return false; }
  }
  function setEnabled(on) {
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (_e) {}
  }
  function getCtx() {
    if (!isEnabled()) return null;
    if (ctx) return ctx;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try {
      ctx = new Ctx();
    } catch (_e) {
      ctx = null;
    }
    return ctx;
  }

  /** A short percussive blip with an exponential pitch sweep. */
  function blip({ from = 720, to = 540, duration = 0.06, gain = 0.06, type = 'square', detune = 0 } = {}) {
    const c = getCtx();
    if (!c) return;
    if (c.state === 'suspended') c.resume().catch(() => {});
    const t0 = c.currentTime;
    const osc = c.createOscillator();
    const g   = c.createGain();
    osc.type = type;
    osc.detune.setValueAtTime(detune, t0);
    osc.frequency.setValueAtTime(from, t0);
    osc.frequency.exponentialRampToValueAtTime(Math.max(to, 1), t0 + duration);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain, t0 + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
    osc.connect(g).connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + duration + 0.02);
  }

  // Outbound — terse, mid-pitch click.
  function dispatch() {
    if (!isEnabled()) return;
    blip({ from: 880, to: 440, duration: 0.05, gain: 0.05, type: 'square' });
  }

  // Inbound — two-tone arrival, slightly warmer.
  function response() {
    if (!isEnabled()) return;
    blip({ from: 540, to: 660, duration: 0.07, gain: 0.06, type: 'triangle' });
    setTimeout(() => blip({ from: 880, to: 1100, duration: 0.06, gain: 0.05, type: 'triangle' }), 70);
  }

  // Failure — single low growl.
  function fault() {
    if (!isEnabled()) return;
    blip({ from: 300, to: 110, duration: 0.18, gain: 0.07, type: 'sawtooth' });
  }

  // Public API used by chat.js + the settings toggle.
  window.dpAudio = { dispatch, response, fault, isEnabled, setEnabled };
})();
