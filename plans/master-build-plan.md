# Plan: Master Build Plan

**Created:** 2026-05-21
**Last updated:** 2026-05-21
**Status:** Active — v0.1.0 shipped; Phase 1 DoD Tracks B + A remaining

---

## Where We Are

v0.1.0 is tagged, released on GitHub, and pushed. The tool works end-to-end
and has been smoke-tested against a real codebase. All seven compliance
scanners are live. 396 tests green. No third-party runtime dependencies.

**The tool is NOT yet "MVP complete" per `docs/mvp-scope.md`.** The binding
Definition of Done requires an actual App Store approval of a converted
reference app. That gate has not been crossed.

---

## Phase 1 — Web → Wrap (Active)

### Definition of Done (from `docs/mvp-scope.md §3`)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Every BLOCKING item in MVP-Gap-Analysis resolved | ✅ Done — all §4.x items shipped |
| 2 | Reference app converted → preflight passes (0 Layer-A) → submitted → **App Store approved** | ⬜ Not started |
| 3 | Pre-flight scanner runs in <60s on representative codebase | ✅ Done (seconds on the-survival-bible) |
| 4 | report.md + report.json render for the reference run | ✅ Done |
| 5 | 3 sequential re-conversions on developer-edited branch — no data loss | ⬜ Track B — not yet validated |
| 6 | Disclaimer + developer sign-off flow reviewed by legal counsel | ⚙️ Scaffold done (`828b080`) — awaiting legal review of `docs/disclaimer.md` |
| 7 | Compliance rule data files published, versioned, documented under config/ | ✅ Done |

---

### Track A — Reference App Submission (blocks DoD #2)

The highest-leverage thing we can do right now. Pick a small, real, open-source
web app (ideally one we own or control), run it through the pipeline end-to-end,
fix whatever the compliance scanners surface, and submit to App Store Connect.

**Steps:**

1. **Pick the reference app** — must be a real TypeScript/React/Vite web app,
   publicly available, small enough that compliance findings are fixable.
   Candidate: build a purpose-built minimal reference app (`reference-app/`)
   rather than relying on a third-party repo we can't control.

2. **Run preflight + convert** — fix all Layer-A findings (the tool will tell us
   exactly what's wrong). Document the run in `context/sessions/`.

3. **Manual completion** — after conversion, a developer (human) must:
   - Replace all `NS*UsageDescription` placeholders with real strings
   - Set real bundle ID and Team ID
   - Run `xcodegen generate` and open in Xcode
   - Install on device via TestFlight
   - Submit to App Store Review

4. **Track approval** — once approved, flip `config/compatibility-matrix.yaml`
   `web × wrap` to `supported: true` and close Phase 1.

**Effort:** 1–2 sessions engineering + human Xcode/App Store work outside the tool.

---

### Track B — Re-conversion / 3-way merge validation (DoD #5)

**Status: Next up.**

The `ios-conversion` branch workflow must survive three sequential re-conversions
on a developer-edited branch without data loss.

**What needs building/testing:**
- Documented test scenario: convert → developer edits `App/Info.plist` →
  re-convert → verify developer edits survive.
- The git merge logic in `wrapper/git_ops.py` does a 3-way merge via
  `git merge-base`. This needs a scripted validation, not just unit tests.
- Write `plans/reconv-validation-scenario.md` with the exact steps and
  expected outcomes.
- Run it. Document results in `context/sessions/`.

**Effort:** 1 session.

---

### Track C — Developer sign-off flow (DoD #6) ✅ `828b080`

Engineering scaffold complete. Disclaimer shown before every conversion.
Interactive `agree` prompt or `--yes` for CI. Acceptance persisted to
`~/.ios-agent/disclaimer-accepted.json` (version-keyed).

**Remaining:** Legal review of `docs/disclaimer.md`. No engineering work needed
until legal requests text changes.

---

## Phase 2 — Logic Transpilation: Kotlin + Java → Swift Package (Deferred)

**Gate:** Phase 1 DoD must be fully met first.

### Scope
- Source: Kotlin or Java logic-only libraries (no UI, no Android-specific APIs)
- Target: Swift Package the developer integrates into their own Xcode project
- The developer authors the SwiftUI/UIKit UI by hand — no UI translation

### Technical dependencies not yet built
- **Java → Swift:** J2ObjC integration (Google's Java-to-Objective-C transpiler;
  the output then bridges to Swift via standard ObjC interop)
- **Kotlin → Swift:** Skip (transpiles Kotlin to Swift 1:1) or KMM
  (Kotlin Multiplatform Mobile — shared logic, platform UI)
- **New compatibility-matrix entry:** `java × port` and `kotlin × port`
  flip to `supported: true` only after a reference app passes App Store review

### What to build (high level, not yet planned in detail)
1. `converter/kotlin/` — Kotlin source scanner + Skip/KMM invocation layer
2. `converter/java/` — Java source scanner + J2ObjC invocation layer
3. `wrapper/` — new `convert-kotlin` and `convert-java` subcommands
4. Reference app: a small Kotlin or Java logic library integrated into a
   Capacitor wrapper and submitted to App Store

**Effort:** Multi-session, multi-week. Do not start until Phase 1 is approved.

---

## Phase 3 — Bridge Mode (Deferred)

**Gate:** Phase 2 DoD met.

Selective WebView screens: some routes rendered natively, some in WKWebView.
Requires a per-route conversion decision engine. No design yet.

---

## Phase 4 — Port Mode (Deferred)

**Gate:** Phase 3 DoD met.

Full native Swift/SwiftUI app from transpiled source. Narrow domain only
(CRUD, simple forms). Automatic UI translation is unsolved — not committed
to any phase.

---

## Phase 5 — TypeScript + Python (LLM-Heavy, Deferred)

**Gate:** Phase 4 DoD met (or independent parallel track, TBD).

LLM-assisted, marketed as "assisted / manual-review-required." Not a mechanical
transpilation product.

---

## Immediate Next Actions (ordered)

1. ~~**Track C** (disclaimer scaffold)~~ ✅ Done
2. **Track B** (re-conversion validation) — 1 session, scripted scenario
3. **Track A** (reference app) — build the minimal reference app, run through pipeline, submit
4. **Legal** (disclaimer text review) — human task, can run in parallel with B

---

## Key Files

| File | Role |
|------|------|
| `docs/mvp-scope.md` | Authoritative Phase 1 scope + DoD |
| `docs/disclaimer.md` | Disclaimer text pending legal review |
| `config/compatibility-matrix.yaml` | Gate: `web × wrap supported: false` until App Store approval |
| `wrapper/disclaimer.py` | Disclaimer scaffold + sign-off logic |
| `wrapper/git_ops.py` | Re-conversion / 3-way merge logic (Track B) |
| `wrapper/__main__.py` | CLI entry point |
| `context/ACTIVE.md` | Rolling engineering context |
| `plans/mvp-section-4-compliance.md` | §4.x compliance track (complete) |
| `CHANGELOG.md` | Release history |
