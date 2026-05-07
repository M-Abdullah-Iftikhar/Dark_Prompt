# Dark Prompt — Improvements Backlog

Living checklist of UX, feature, and hardening work for the site.
Items are grouped by impact. Tick the box once shipped.

---

## In progress / shipping now (priority batch)

- [x] **#6 — Real password reset flow** (token + email; replaces stub)
- [x] **#9 — Rename conversation** (inline sidebar edit + API)
- [x] **#7 — Export conversation** (`.md` / `.txt` download)
- [x] **#11 — Code copy buttons** on every `<pre>` in messages
- [x] **#15 — Activity log** (`ActivityEvent` model + Settings → Activity)
- [x] **#24 — Keyboard shortcuts** + `?` cheat-sheet modal

---

## High impact — UX gaps people will hit immediately

- [ ] **#1** — Toast notifications system (verify `dpToast()` is global; build a bottom-right stack)
- [x] **#2** — Per-message "Retry last prompt" button when LLM fails
- [x] **#3** — Loading skeletons for the conversation list
- [x] **#4** — Account email verification (token before unlocking chat)
- [x] **#5** — Rate limiting + abuse protection on signup/login (cache-backed)
- [x] **#6** — Real password reset (token + email, console backend in dev)

## Medium impact — features that round out the product

- [x] **#7** — Export conversation as `.md` / `.txt`
- [x] **#8** — Pin / favorite conversations (sticky group at top)
- [x] **#9** — Rename conversation (sidebar inline edit)
- [x] **#10** — Search inside message bodies, not only titles
- [x] **#11** — Code block enhancements: copy button, language badge, line numbers
- [x] **#12** — Token / cost telemetry per session
- [x] **#13** — Settings → API keys (mint personal tokens for `/api/chat/`)
- [x] **#14** — Settings → Sessions / devices with revoke buttons
- [x] **#15** — Activity log (last 50 events: login IP, password change, etc.)
- [x] **#16** — 2FA (TOTP) — pure-stdlib RFC 6238 + backup codes

## Polish & content

- [x] **#17** — About / Manifesto page (defensive-research thesis)
- [x] **#18** — Changelog page (data-driven from views.CHANGELOG_RELEASES)
- [x] **#19** — Status page (`/status/` showing local LLM reachability + latency)
- [x] **#20** — `templates/500.html` + `handler500`
- [x] **#21** — `robots.txt` + `sitemap.xml`
- [x] **#22** — Open Graph / Twitter card meta tags (per-page blocks + noindex on private)
- [x] **#23** — Favicon + apple-touch-icon + PWA `manifest.webmanifest` view
- [x] **#24** — Keyboard shortcuts (Ctrl+K search, Ctrl+Shift+N new chat, etc.) + `?` cheat-sheet
- [x] **#25** — First-visit onboarding tour (5-step spotlight overlay, replayable)

## Theme-on-theme details

- [x] **#26** — Audio cues on dispatch / response (toggleable, Web Audio synth)
- [x] **#27** — Boot sequence on chat first load (per-session handshake terminal)
- [x] **#28** — Glitch hover on destructive elements (chromatic shake, reduced-motion safe)

## Backend hardening

- [x] **#29** — CORS for `/api/chat/` (in-tree decorator, configurable via `LLM_CORS_ALLOW_ORIGINS`)
- [x] **#30** — Hardened settings + boot-time guards + `.env.example` contract
- [x] **#31** — Done de-facto: `Conversation.is_pinned`, `UserProfile.email_verified_at` (tier still on session — non-blocking)
- [x] **#32** — Tests: signup/AUP, email-or-username backend, owner-scoped delete/rename/export, verify gate

---

## Done

- [x] Confirm modal for chat deletion (replaces browser `confirm()`)
- [x] Wire `handler404` + `/404-preview/` route
