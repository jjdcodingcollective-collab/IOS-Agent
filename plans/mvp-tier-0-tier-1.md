# Plan: MVP Tier 0 + Tier 1 — Lock Scope, Then Build the Spine

**Source:** `MVP-Gap-Analysis.md` (saved to `/storage/outputs/ios-agent/`)
**Status:** Tier 0 complete (all 5 steps shipped 2026-05-05). Tier 1 Step 6 ✅ complete (all 7 sub-steps shipped 2026-05-05). Tier 1 Steps 7 and 8 not started.
**Owner:** Product / Tech Lead
**Created:** 2026-05-05
**Strategy:** "Docs first, converter second." Tier 0 lands as decisions and documentation. Tier 1 is the engineering spine every later BLOCKING item plugs into.

---

## Summary

This plan executes the first eight items from the MVP gap analysis, in dependency order. Tier 0 (items 1–5) is decision and documentation work — no engineering. Tier 1 (items 6–8) is the foundational engineering spine that every remaining BLOCKING item depends on.

Items deferred explicitly: §2.4 (ARC), §2.5 (concurrency), §2.6 (idiom spec), §3.1 (UI mapping), and all of Phase 2+. These are not in MVP scope per §10.1 of the gap analysis.

---

## Tier 0 — Lock Scope (Decisions & Docs Only)

No engineering. Each item is a one-shot deliverable that closes a decision and unblocks the doc team.

### Step 1 — Lock MVP scope to Phase 1: Web → Wrap (gap §10.1) ✅ shipped 2026-05-05

**Deliverable:** A signed-off `docs/mvp-scope.md` document.

**Contents:**
- Phase 1 scope: Web codebases (HTML / JS / TS front-ends) → Wrap mode (Capacitor-based WKWebView wrapper) only.
- Explicit exclusions: Java, Kotlin, Python source; Bridge mode; Port mode; UI translation.
- Definition of Done for MVP: an actual App Store approval of a tool-converted reference web app (per §Definition of Done in the gap analysis).
- Phase 2+ list, deferred until Phase 1 ships.

**Acceptance:** Doc reviewed and approved by product owner. Marketing copy updated to match. No remaining references to Java / Python / Kotlin in MVP-tier materials.

---

### Step 2 — Publish the Source × Target compatibility matrix (gap §1.1) ✅ shipped 2026-05-05

**Deliverable:** `config/compatibility-matrix.yaml` (data) + `wrapper/compatibility.py` (loader + `assert_supported()` gate) + `wrapper/__main__.py` integration with `--allow-unsupported` dev override + `wrapper/tests/test_compatibility.py` (9 tests).

**Contents:**
- Data file (not code) listing every supported source archetype × target mode combination.
- For MVP, only one row is `supported: true`: `web` × `wrap`.
- Every other row is either `supported: false` (with reason) or `phase: 2|3|4|5` (with target phase).
- Schema includes: `source_archetype`, `target_mode`, `supported`, `phase`, `notes`, `reference_repo` (optional).

**Acceptance:** Matrix loads at tool start-up. UI selector reads the matrix and disables every combination not marked `supported: true`. Attempting to invoke an unsupported combination via CLI returns a clear error pointing to the matrix.

---

### Step 3 — Rename modes to Wrap / Bridge / Port (gap §1.2) ✅ shipped 2026-05-05

**Deliverable:** Codebase-wide rename + updated docs (`docs/glossary.md` defines the canonical names; transition-overview, webview-guide, testing-guide, and README updated).

**Contents:**
- Rename "WKWebView wrapper" → **Wrap**.
- Rename "semi-native hybrid" → **Bridge**.
- Rename "fully native" → **Port**.
- Update: README, marketing copy, conversion-mode selector strings, CLI flag names, generated PR descriptions, the gap analysis doc, and every existing plan file in `plans/`.
- Add a glossary entry to `docs/glossary.md` defining each mode.

**Acceptance:** `grep -ri "wrapper\|hybrid\|fully native"` across the repo returns only intentional historical references (changelog, release notes). All user-facing strings use the new names.

**Why now:** Doing this before Tier 1 docs prevents a rename pass through every doc that gets written this week.

---

### Step 4 — Mandate the tooling stack via ADR (gap §6.1) ✅ shipped 2026-05-05

**Deliverable:** `docs/adr/0001-tooling-stack.md` (Architecture Decision Record).

**Contents:**
- Decision: the tooling stack is fixed as below. No in-house reimplementation without a superseding ADR.
- Stack table (mirrored from §6.1 of the gap analysis):

  | Layer | Tool | Pinned version | Justification |
  |---|---|---|---|
  | Web wrapper | Capacitor (Ionic) | TBD on first install | MVP target; plugin-rich; Apple-tolerated |
  | Source AST | tree-sitter | TBD | Multi-language, fast |
  | Swift AST | swift-syntax + swift-format | TBD | Apple-official |
  | Project generation | XcodeGen (default) or Tuist | TBD | Declarative, version-stable |
  | Static checks | SwiftLint, SwiftFormat, periphery | TBD | Standard Swift tooling |
  | Java → iOS (deferred) | J2ObjC | — | Phase 2 |
  | Kotlin ↔ Swift (deferred) | Skip + KMM | — | Phase 2 |

- Upgrade testing policy: pin every version; CI validates against the latest two Xcode releases.
- Forbid in-house reimplementation of any listed tool.

**Acceptance:** ADR merged. Pinned versions added to `package.json` / `Package.swift` / equivalent. CI green on the pinned stack.

---

### Step 5 — Remove Python from MVP supported languages (gap §2.2) ✅ shipped 2026-05-05

**Deliverable:** A scope-reduction commit. Audit confirmed no Python source-detection code paths exist in the converter, so no `EXPERIMENTAL_PYTHON` flag was needed — the matrix gate (Step 2) is sufficient. `python × *` rows in the matrix are all `supported: false, phase: 5`.

**Contents:**
- Remove Python from every MVP-facing list of supported source languages: README, marketing copy, onboarding flow, compatibility matrix (Step 2), gap analysis cross-references.
- Add Python to the Phase 5 deferred list with the explicit caveat: "Assisted (LLM-driven, manual review required)."
- If any code paths exist for Python detection or parsing in the current converter, gate them behind a `EXPERIMENTAL_PYTHON=1` env flag and surface a `not-supported` error in normal flows.

**Acceptance:** No user-facing flow allows selecting Python as a source. The compatibility matrix from Step 2 marks `python × *` as `phase: 5, supported: false`.

---

## Tier 1 — Foundation Engineering Spine

Once Tier 0 is locked, these are the dependency roots. Every remaining BLOCKING compliance item plugs into one of them, so build them in order.

### Step 6 — API-usage scanner + privacy manifest generator (gap §4.1) ✅ shipped 2026-05-05

**Status:** Complete. Sub-plan tracked at `plans/tier-1-step-6-privacy-scanner.md`. All seven sub-steps shipped 2026-05-05: 6.1 (`config/apple-required-reason-apis.yaml`), 6.2 (`converter/compliance/api_scanner.py`), 6.3 (`converter/compliance/privacy_manifest.py`), 6.4 (`templates/privacy-overrides.yaml.template`), 6.5 (54 tests across `test_api_scanner.py` + `test_privacy_manifest.py` + `test_compliance_step.py`), 6.6 (`wrapper/compliance_step.py` wired into `convert` and `convert-from-github`), 6.7 (`config/apple-privacy-manifest.schema.json`).

**Why first in Tier 1:** This single component is the foundation for §4.3 (ATT detection), §4.5 (usage strings), §4.9 (ATS), and §7.3 (pre-flight scanner). Build it once, reuse it five times.

**Deliverable:** A scanner module + a `PrivacyInfo.xcprivacy` generator.

**Sub-tasks:**

1. **Scanner core.** Walks generated Swift output (or, in Wrap mode, declared Capacitor plugins) and detects calls to Apple's required-reason APIs.
2. **Required-reason API list as data.** `config/apple-required-reason-apis.yaml`. Versioned. Cite Apple source. Initial coverage: `UserDefaults`, `NSFileManager` timestamps, `systemBootTime`, `mach_absolute_time`, `kIOPMAssertionTypeNoIdleSleep`, disk space APIs, active keyboard APIs.
3. **Manifest generator.** Emits `PrivacyInfo.xcprivacy` from scanner output. Validates against Apple's schema before writing.
4. **Manual override.** `privacy-overrides.yaml` that the developer can extend.
5. **Findings emitter.** Every detected API → a structured finding with file path, line, API name, declared reason. Wires into the report schema (Step 7).
6. **Re-run on every conversion.** Manifest is regenerated, never hand-edited downstream.

**Acceptance:**
- Scanner detects every required-reason API in a fixture suite of 20+ usage patterns.
- Generated manifest validates against Apple's schema.
- A reference Capacitor project produced by the tool ships with a complete `PrivacyInfo.xcprivacy`.
- Adding a new required-reason API to the YAML data file picks it up on next run with no code change.

**Out of scope for this step:** the ATT, SIWA, ATS, usage-string components (later steps reuse this scanner — they are not in this step).

---

### Step 7 — Three-layer report structure (gap §7.1)

**Why before the pre-flight scanner:** Every compliance and translation component will emit findings. Define the schema first, or every component retrofits later.

**Deliverable:** A report schema + emitter library + Markdown and JSON renderers.

**Sub-tasks:**

1. **Schema definition.** `schemas/report.schema.json`. Three-layer structure:
   - **Layer A — Blockers.** Fields: `id`, `category`, `severity`, `file`, `line`, `original_snippet`, `attempted_translation`, `reason`, `recommended_fix`, `doc_link`.
   - **Layer B — Manual review.** Same fields + `confidence_score` (per symbol, not per file).
   - **Layer C — Learnings.** Cross-cutting: `pattern`, `occurrences`, `applied_translation`, `untranslatable_count`, `refactor_recommendation`. Plus trend fields (`prior_rev_confidence`, `delta`) when rev > 1.
2. **Emitter library.** Every component (Step 6, future ATT/SIWA/ATS/usage modules) emits findings via this library, never via free-form logs.
3. **Renderers.**
   - `report.md` — human-readable, sorted by severity, PR-comment-friendly.
   - `report.json` — machine-readable, CI-consumable.
4. **Confidence scoring.** Per symbol (function / class / property), aggregated up to per-file and per-project.
5. **Provenance.** Every LLM-generated translation captures model, prompt template, seed (deferred wiring for §6.2 — schema field reserved now).

**Acceptance:**
- Step 6's scanner emits findings exclusively through the emitter library.
- A sample run on a fixture web app produces both `report.md` and `report.json` that validate against the schema.
- The report is renderable as a GitHub PR comment ≤65,536 characters via a "summary mode."

---

### Step 8 — Xcode project generation via XcodeGen / Tuist (gap §5.1)

**Why third:** Wrap-mode output has nowhere to land without a generated `.xcodeproj`. Builds on the tooling-stack ADR (Step 4).

**Deliverable:** Project-generation module that emits a buildable Capacitor + Xcode project.

**Sub-tasks:**

1. **Generator selection.** Default XcodeGen. Tuist as opt-in.
2. **Spec template.** `templates/xcodegen.yml.tmpl` produces a minimal Capacitor host project. Capabilities, signing placeholders, Info.plist scaffolding included.
3. **Capability detection.** Scanner (Step 6 reuse) detects required entitlements from source: push notifications, App Groups, iCloud, HealthKit, etc. Pre-populates the spec.
4. **Signing scaffolding.** Placeholder team ID + bundle ID, clearly marked `// TODO`. Signing guide added to generated README.
5. **Asset pipeline placeholders.** Default app icon set covering all required iOS sizes (placeholder), default `LaunchScreen.storyboard`. Real-asset replacement deferred to gap §5.3 (later step).
6. **CI validation.** Generated project must build clean against the latest two Xcode releases.

**Acceptance:**
- Running the tool against a sample web repo produces an `.xcodeproj` that opens, builds, and runs in the iOS Simulator with no manual intervention.
- Adding a required entitlement (e.g., push notifications) to the source-side detection flips the right capability in the generated spec.
- The generated project's `Info.plist` includes the Step 6 privacy manifest.

---

## Notes

### Strict ordering

- Tier 0 steps are independent — they can run in parallel, but **all five must close** before Tier 1 begins.
- Tier 1 steps are strictly sequential: 6 → 7 → 8.
  - Step 7 depends on Step 6 to validate the emitter on real findings.
  - Step 8 depends on Steps 6 & 7 to embed the privacy manifest and emit findings into the report.

### Explicit non-goals for this plan

- ARC translation, Sendable conformance, idiom translation specs, UI mapping — all Phase 2+, all explicitly deferred per §10.1.
- ATT, SIWA, usage strings, ATS, encryption declaration, 4.2 enforcement, 4.7/2.5.2 scanner, accessibility floor — these are the **next** plan after Tier 1 closes. They all reuse the Step 6 scanner and the Step 7 report.
- Round-trip / 3-way merge (gap §1.3, §8.2) — also follow-on plan; needs the report (Step 7) as a finding sink for conflicts.

### Risk callouts

- **Apple guideline drift.** The required-reason API list (Step 6 sub-task 2) and the report category list (Step 7) must both be data files, not hardcoded enums. Apple updates these multiple times a year.
- **XcodeGen vs Tuist drift.** Pin both versions in the ADR (Step 4). Test against new Xcode releases on a quarterly cadence.
- **LLM provenance schema.** Step 7 reserves the field but does not wire it. Make sure §6.2 (next plan) doesn't have to reshape the schema when it lands.

### Working memory

- The `ios-conversion` branch strategy and revisioning behaviour (rev 2, rev 3, confidence scores) is already decided and partly implemented per project memory. Steps 6–8 do **not** touch the branch flow. The follow-on plan covers conflict resolution and round-trip.
- The wrapper roadmap Phases 1–5 (currently complete per recent commits) is a separate workstream from this MVP gap-closure plan. This plan does not roll back any of that work — it builds the spine those phases will eventually consume.

---

## Definition of Done — This Plan

- All five Tier 0 deliverables merged and signed off.
- The compatibility matrix gates the tool's UI/CLI in code.
- The Step 6 scanner produces a valid `PrivacyInfo.xcprivacy` for at least one reference web app.
- The Step 7 report renders Markdown + JSON for the same reference run.
- The Step 8 generator produces a buildable Xcode project for the same reference run, with the privacy manifest embedded.
- All three Tier 1 steps emit findings via the report schema — no free-form logging.

When this plan closes, the next plan covers the remaining BLOCKING compliance items (§4.2–§4.9), all of which reuse Steps 6–7 as their substrate.
