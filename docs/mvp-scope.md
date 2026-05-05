# MVP Scope — Authoritative Reference

**Status:** Active, binding
**Owner:** Product / Tech Lead
**Created:** 2026-05-05
**Source decisions:** `MVP-Gap-Analysis.md` §10.1; `plans/mvp-tier-0-tier-1.md` Step 1

This document defines what is, and is not, in scope for the ios-agent MVP. It is the authoritative reference. Marketing copy, onboarding flows, the compatibility matrix, the product UI, and all engineering plans must conform to this document. When this document and any other artefact disagree, this document wins until it is formally updated via PR.

---

## 1. MVP Scope (Phase 1)

The MVP is **one** source archetype converted into **one** target output mode.

### Source archetype: Web codebases

In scope:
- HTML / CSS front-end assets
- JavaScript front-end code (browser-runnable)
- TypeScript front-end code (browser-runnable)
- Front-end build outputs from common bundlers (Vite, Webpack, Next.js static export, Create React App, Astro, etc.) where the output is a deployable static or SPA web bundle
- Common front-end frameworks (React, Vue, Svelte, Angular, vanilla) — as content inside the WebView, not as transpilation targets

Out of scope (Phase 1):
- Server-side code of any kind (Node.js servers, Next.js server components / API routes, BFFs, edge functions)
- Native mobile codebases (Java Android, Kotlin Android, Objective-C, existing Swift)
- Backend languages (Python, Go, Rust, Ruby, PHP, C#, Java server, etc.)
- Desktop apps (Electron, Tauri)
- Game engines (Unity, Unreal)

### Target output mode: Wrap

Wrap mode produces a Capacitor-based iOS host project that loads the developer's web app inside a WKWebView, with App Store compliance scaffolding generated alongside.

In scope:
- Capacitor-based Xcode project generation
- Privacy manifest (`PrivacyInfo.xcprivacy`) auto-generation
- Sign in with Apple stub when third-party logins are detected in source
- Permission usage strings (`Info.plist` `NS*UsageDescription`) scaffolding
- App Transport Security (ATS) configuration
- Encryption export compliance declaration
- Minimum-functionality enforcement (Guideline 4.2 — native feature density check)
- Pre-flight compliance scanner
- Three-layer conversion report (Blockers / Manual review / Learnings)
- Branch + PR delivery workflow on the `ios-conversion` branch
- Round-trip / 3-way merge support for re-conversion

Out of scope (Phase 1):
- Bridge mode (hybrid native shell + selective WebView screens)
- Port mode (full native Swift/SwiftUI translation)
- Automatic UI translation of any kind
- Logic-only Swift Package generation from native source languages

---

## 2. Explicit Exclusions

These are deliberately deferred to later phases. They MUST NOT appear in MVP-tier marketing, onboarding, the compatibility matrix as `supported: true`, the product UI as selectable, or any user-facing documentation outside this doc and the phasing roadmap.

| Item | Deferred to | Reason |
|---|---|---|
| Java source | Phase 2 | Requires J2ObjC integration; not yet built |
| Kotlin source | Phase 2 | Requires Skip / KMM integration; not yet built |
| Python source | Phase 5 | Not statically feasible without LLM-heavy assistance; will be marketed as "Assisted, manual review required" |
| Objective-C source | Future | Trivial via existing Swift interop; not a transpilation product |
| C# / .NET source | Future | No mature tooling; out of strategic priority |
| C++ / Rust / Go source | Future | Out of strategic priority |
| Bridge mode | Phase 3 | Requires per-route conversion decision engine |
| Port mode | Phase 4 | Narrow domains only; UI mapping problem unsolved |
| Automatic UI translation (HTML/React → SwiftUI/UIKit) | No phase committed | No mechanical mapping exists; not a transpilation problem |
| Strict Swift 6 concurrency / Sendable conformance pass | Phase 2 | Not required while logic translation is out of scope |
| ARC retain-cycle static analyzer | Phase 2 | Required only when transpilation begins |
| Idiom translation specification | Phase 2 | Required only when transpilation begins |

---

## 3. Definition of Done — MVP

The MVP is **shippable** when, and only when, all of the following are true. No subset is acceptable.

1. Every BLOCKING item in `MVP-Gap-Analysis.md` §11 is resolved.
2. A reference web app (publicly available, open-source preferred) has been:
   - Converted by the tool in Wrap mode
   - Passed the pre-flight compliance scanner with **zero Layer-A findings**
   - Submitted to App Store Connect
   - **Approved** by Apple App Review
3. The pre-flight compliance scanner runs in under 60 seconds on a representative codebase.
4. The three-layer report renders in both Markdown (`report.md`) and JSON (`report.json`) for the reference run.
5. The `ios-conversion` branch / revision workflow successfully handles three sequential re-conversions on a developer-edited branch with no data loss, validated by a documented test scenario.
6. The disclaimer and developer sign-off flow (`MVP-Gap-Analysis.md` §9.1) is reviewed and approved by legal counsel.
7. The compliance rule data files (required-reason API list, rejection-pattern rules) are published, versioned, and documented under `config/`.

A "soft launch" or "beta with caveats" does **not** satisfy this Definition of Done. The binding criterion is an actual, documented App Store approval.

---

## 4. Phase Roadmap (Non-Binding Reference)

The phases below are the agreed sequencing for post-MVP work. They are non-binding scope commitments — Phase 2 work does not begin until Phase 1 ships and the Definition of Done above is met.

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Web → Wrap (this MVP) | Active |
| Phase 2 | Logic transpilation: Kotlin, Java → Swift Package (developer authors UI by hand) | Deferred |
| Phase 3 | Bridge mode (native shell + selective WebView screens, per-route decision) | Deferred |
| Phase 4 | Port mode (full-app native, narrow CRUD/forms domain) | Deferred |
| Phase 5 | TypeScript and Python full support (LLM-heavy, marketed as assisted) | Deferred |

Each phase has its own Definition of Done, including a reference app that passes App Store review for that phase's output. No phase is shipped without that gate.

---

## 5. Marketing & Communications Compliance

Marketing copy, sales materials, the public website, demo scripts, and onboarding flows MUST conform to the MVP scope above. Specifically:

- Do not claim, imply, or list as a feature any item in §2 (Explicit Exclusions) for the MVP launch.
- The phrase "convert any codebase" or equivalent is not permitted. Use "convert your web app to a native iOS shell" or similar precise language.
- Do not list Java, Kotlin, Python, or other Phase 2+ source languages as "supported" or "available" until their respective phases ship and pass App Store approval.
- The Wrap / Bridge / Port mode names (per Step 3 of the Tier 0 plan) are the only mode names permitted in user-facing materials. The terms "wrapper," "hybrid," and "fully native" are deprecated.
- Any forward-looking statement about Phase 2+ must be prefaced with a clear "planned" or "roadmap" qualifier and must not appear in feature lists or comparison tables.

The product owner is responsible for marketing-copy compliance; engineering will reject any feature request that conflicts with this document until this document is updated.

---

## 6. How to Update This Document

This is the authoritative scope document. Changing it changes the scope of the MVP.

To propose a scope change:
1. Open a PR that edits this document.
2. The PR description must state the rationale, the affected sections, and any cascading changes (compatibility matrix, marketing copy, plans, ADRs).
3. The PR requires sign-off from the product owner and the tech lead.
4. On merge, the PR author updates: `config/compatibility-matrix.yaml`, marketing copy, the relevant plans in `plans/`, and any affected ADRs.

Drift between this document and the rest of the project is treated as a defect. Quarterly, the tech lead audits compliance with this document and files corrective tickets for any drift found.

---

*End of document.*
