# Dark Prompt — Roadmap

Backlog of improvements split by category. Pick from any bucket. Items marked
**★** are the highest-leverage picks per category.

---

## Where we are now

GUI is in a strong place. The site has:

- Iridescent Threat theme with holo gradients, animated body wash, hero sigil,
  anomaly sweep, live telemetry strip.
- Live chat-demo on landing.
- Rich footer with brand + social + 4-column nav.
- Auth pages with show/hide password + strength meter.
- Chat console with: date-grouped sidebar + search, mobile hamburger drawer,
  composer with live MITRE classifier + verb-shifting send, AbortController
  stop, regenerate hover action, code blocks (line numbers + Hex toggle +
  Show-all + decrypt animation + first-token bloom + MITRE pills + SHA fp).
- Cmd+K command palette, focus rings, tooltips, toast utility.
- LLM-down banner with retry, session-once boot banner.
- Stat counters, magnetic primary buttons + ripple, page transitions.
- Responsive at 4 breakpoints (1100/900/680/460).
- Favicon + OG card.

What's left isn't pure GUI anymore. It's functional, structural, or research.

---

## A. Pure GUI (small, mostly cosmetic)

Diminishing returns. Skip most of these.

- [ ] **Inline date dividers** in long threads (`── TODAY ──`).
- [ ] ★ **Conversation rename** — click chat-head title to edit, save via
      `PATCH /api/conversations/<id>/`.
- [ ] **Diff view between regenerated responses** — show what changed after ↻.
- [ ] **Onboarding tour** — first-visit overlay highlighting hex toggle, MITRE
      pills, Cmd+K, regen.
- [ ] **Print stylesheet** — clean conversation printout.
- [ ] **Toast positioning options** — bottom-right variant.
- [ ] **Custom accent picker** — user-configurable gradient stops. *Skip.*

---

## B. Functional with GUI consequences (medium)

These actually expand what the tool can do.

- [ ] ★ **Real token streaming (SSE)** — replace fake client-side stream with
      `EventSource` / fetch-stream. Tokens appear as the LLM emits them.
      Requires Flask backend support.
- [ ] ★ **Conversation export** — download thread as `.md` with code fences.
      One button on chat header.
- [ ] **Settings page** — UI to change `LLM_API_URL`, default temperature,
      default max-tokens, model selection. Stored per-user or globally.
- [ ] **Search inside messages** — extend sidebar search to message content
      via SQLite FTS5 index.
- [ ] ★ **VirusTotal hash lookup** — paste a SHA, see detection rates.
      Free-tier API key. Real research workflow integration.
- [ ] ★ **MITRE drilldown panel** — click a `T1056.001` pill → slideover with
      description + known examples. Static JSON of MITRE ATT&CK data.
- [ ] **Sandbox stub for real** — wire the disabled `▶ Run` button to execute
      artefacts in a Docker container with time/memory limits + no networking.
- [ ] **Pin / star artefacts** — saved-artefacts library indexed by SHA,
      searchable, taggable.

---

## C. Structural / production (highest-leverage, invisible)

These determine whether this project is real or a demo.

- [ ] ★ **Tests** — zero exist today. Add Django tests for auth, chat views,
      regenerate, abort paths. JS unit tests for `parseParts`,
      `mitreTagsFor`, `toHexDump`, `detectVerb`.
- [ ] ★ **WhiteNoise + `ManifestStaticFilesStorage`** — cache-busting works in
      prod, no more "blank page on stale CSS" trap.
- [ ] ★ **Dockerfile + docker-compose** — Django + Flask LLM service together,
      gunicorn, nginx reverse proxy.
- [ ] ★ **Production security settings** — `SECURE_SSL_REDIRECT`,
      `CSRF_TRUSTED_ORIGINS`, env-driven `SECRET_KEY`, `DEBUG=False` default,
      `ALLOWED_HOSTS` from env. Currently `DEBUG=1` is the default.
- [ ] **Content Security Policy** — allow Prism CDN + Google Fonts + Flask
      LLM, nothing else. On-brand for a tool that generates adversarial code.
- [ ] **Postgres migration path** — settings split, docker volume, migration
      compatibility check.
- [ ] **GitHub Actions CI** — run tests + ruff + Playwright smoke on PR.
- [ ] **API rate-limiting** — `django-ratelimit` on `/api/chat/` and
      regenerate.

---

## D. Research-grade additions (large scope)

Real product-direction work.

- [ ] **Ollama integration** — list pulled models, switch mid-conversation,
      pull new ones from UI.
- [ ] **YARA rule generator** — given an artefact, prompt the LLM to produce a
      YARA detection rule, save to a rules library, export.
- [ ] **Baseline diff** — keep one "canonical" generation per technique, diff
      every new artefact against it. Useful for studying mutation surface.
- [ ] **Token budget UI** — track tokens per day, show a budget bar in the
      navbar, throttle when approaching.
- [ ] **Public read-only share link** — generate a signed slug for a single
      conversation (for research write-ups).
- [ ] **Multi-user with team roles** — admin / researcher / viewer roles, plus
      shared conversation collections.

---

## My recommended sequencing

If you want **the most useful tool**, in this order:

1. **C16 + C17 + C18 + C19** (tests + whitenoise + docker + prod settings)
   → makes the project real. ~1 day.
2. **B8 + B10** (real streaming + export) → makes the chat *useful*. ~½ day.
3. **B12 + B13** (VirusTotal + MITRE drilldown) → makes it *research-grade*.
   ~1 day.

After that, anything from D depending on what direction you want.

---

## Hard passes (do not revisit)

- Wallpaper-style glitch effects, matrix rain, scan lines, ASCII skulls,
  generic "Anonymous mask" iconography. Kitsch, off-brand.
- Adding a third visual theme. The Iridescent Threat direction is committed.
- Avatar uploads, conversation pinning per-user, social features. Out of
  scope for a single-operator research tool.
- Service worker / offline mode. The LLM is local; little gain.
- Virtual scrolling. Threads aren't long enough yet.
