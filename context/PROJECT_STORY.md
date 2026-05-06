# Project Story

Last curated: 2026-05-05 (Tier 0 complete; Tier 1 Step 6 ✅ complete; Tier 1 Step 7 ✅ complete; Tier 1 Step 8 ✅ complete — entitlement scanner + 12-capability catalogue + XcodeGen spec emitter + 6 templates + wrapper integration + Linux+macOS CI + 36 tests; 233 total green; Tier 1 closed)

## Narrative

`ios-agent` started as a guidebook for web developers (containerized builds,
Vercel deployments) bringing their products to native iOS — then grew an
automated converter that takes their TypeScript/React code and produces a
buildable Swift/SwiftUI project.

The converter pipeline (analyze → review → rewrite → assemble → validate) was
built across four phases tracked as BUILD-1 through BUILD-15. By 2026-04-25
all 15 items had shipped and the converter could handle a small fixture
end-to-end. The remaining open question was: how does a real user actually
use this thing?

The answer, per the agent-interaction-design plan, is three surfaces:

1. The **CLI** — a one-shot pure function (TS dir → Swift project + reports).
2. A **conversational wrapper** — orchestrates the CLI, clones GitHub repos,
   manages branches, and surfaces a triage summary.
3. **Claude Code** — how the project is built and maintained day-to-day.

Phase 1 of the wrapper (local convert) and Phase 2 (clone + commit, no push)
shipped over 2026-04-30 → 2026-05-04. The first real-world test against
`jjdcodingcollective-collab/the-survival-bible` (a Next.js + React Native
monorepo) surfaced two issues that have since been fixed:

- The wrapper had no way to scope to a monorepo subdirectory; added
  `--source-subdir`.
- The rewriter leaked `=>` arrow-function syntax into Swift output for JSX
  prop callbacks (`style={({pressed}) => [...]}`, render-props,
  `.map((x) => (...))`). Three-point fix in `component_converter.py`
  (Text-content guard, JSX-expression dispatcher, post-processor) brought
  the survival-bible run from 5 validation errors to 0.

Phase 3 (push) is next. The eventual product vision is a paid hosted
service: "point us at your repo, get an iOS PR" — but only after the local
round-trip is rock-solid.

A second track opened on 2026-05-04: a focused review of the human-facing
`docs/` guide against the project's broader brief of "transposing popular
coding languages to Swift" found the docs were monolingual (JS/TS only),
missing an Objective-C interop chapter, and underweighting Swift's strict
concurrency model and ARC discipline. The review also caught a handful of
internal inconsistencies (sample code using `try!` / `as!` in chapters that
forbid them, and an `@ObservedObject ↔ useContext` mismap that misleads
React readers). These are now tracked as GAP-D1…D9 / BUILD-16…30 under a
new Phase E in the build guide, sequenced so correctness fixes ship before
any new source-language chapters. The converter scope is intentionally
unchanged — docs first, converter later, because docs are cheaper to
experiment with.

**Phase E shipped end-to-end on 2026-05-04** in seven commits. Tier 0
correctness fixes (BUILD-20) plus Tier 1 chapters on ObjC interop, strict
concurrency, ARC, generics, persistence, and Kotlin/Java/Python landed
first. BUILD-26 (deeper JS/TS) and BUILD-29 (App Store operations) followed.
The Tier 2/3/4 niche tail closed in three reviewable commits: BUILD-23
(UIKit), BUILD-24/25 (C#, Dart/Flutter), and BUILD-27/28/30 (C++ interop,
Rust FFI, Go/Ruby/PHP). The `docs/` guide now spans **JavaScript/TypeScript,
Kotlin, Java, Python, C#, Dart/Flutter, and Go/Ruby/PHP** as source
languages **for documentation** — i.e. each chapter teaches Swift to a
developer arriving from that language. This is distinct from converter
input scope, which is locked to web codebases (HTML/CSS/JS/TS) for the
MVP per `docs/mvp-scope.md`. Operational depth on ObjC, C++, and Rust
interop, UIKit for non-greenfield codebases, and an App Store
operations checklist round out the docs.

With Phase E complete, the active roadmap narrows back to a single track:
**wrapper Phase 4 (conversational polish) and Phase 5 (`--open-pr` via
`gh pr create`)** — both build on the Phase 3 push plumbing already in
place. Brand alignment is now resolved in favour of the broad scope; the
README "Scope" section reflects the wider language coverage and the
remaining-backlog line was replaced with a "Phase E complete" callout.

A third track opened on 2026-05-05: a senior-iOS-architect review of the
whole concept produced a 34-item MVP gap analysis (saved to
`/storage/outputs/ios-agent/MVP-Gap-Analysis.md`) — 27 BLOCKING + 7 AT-RISK
items spanning scope ambiguity, App Store compliance gaps (privacy
manifest, ATT, SIWA, ATS, usage strings, encryption, 4.2 minimum
functionality, 4.7/2.5.2 runtime-code), tooling-stack drift risk, and
report design. The binding Definition of Done is hard: actual App Store
approval of a tool-converted reference web app. The plan
(`plans/mvp-tier-0-tier-1.md`) executes the first eight items in
dependency order: Tier 0 (locks scope, no engineering) and Tier 1 (the
foundational engineering spine — scanner → report → Xcode gen — which
every later compliance module reuses).

**Tier 0 shipped 2026-05-05** in five commits. Step 1 produced
`docs/mvp-scope.md`: MVP is web → Wrap only, with an explicit exclusions
list (Java, Kotlin, Python, Bridge, Port, UI translation) and a
seven-criteria Definition of Done. Step 2 added the data-driven
`config/compatibility-matrix.yaml` (18 combinations across 6 source
archetypes × 3 target modes; only `web × wrap` will ever be `supported:
true` and even that flips on only after App Store approval) plus a
minimal-subset YAML loader (`wrapper/compatibility.py`) that the wrapper
now consults at start-up via `assert_supported()`; both `convert` and
`convert-from-github` gained a `--allow-unsupported` dev-override flag.
Step 3 renamed the conversion modes everywhere: "WKWebView wrapper" →
**Wrap**, "semi-native hybrid" → **Bridge**, "fully native" → **Port** —
the new canonical names live in `docs/glossary.md` and propagate through
README, transition-overview, webview-guide, and testing-guide. Step 4
mandated the tooling stack via `docs/adr/0001-tooling-stack.md` (the
project's first ADR): Capacitor, tree-sitter, swift-syntax, XcodeGen
default with Tuist opt-in, J2ObjC + Skip + KMM deferred to Phase 2,
quarterly review, and a "forbidden without superseding ADR" list that
forbids in-house parser reinvention. Step 5 removed Python from the MVP
supported-source list; an audit confirmed no Python detection code paths
exist in the converter, so no `EXPERIMENTAL_PYTHON` flag was needed —
the matrix gate is sufficient.

**Tier 1 Step 6 began the same day.** The sub-plan
(`plans/tier-1-step-6-privacy-scanner.md`) is the foundation that ATT,
SIWA, ATS, usage strings, and the pre-flight scanner all reuse. Two
sub-steps shipped: 6.1 produced `config/apple-required-reason-apis.yaml`
— a versioned, data-driven catalogue of Apple's five required-reason API
categories (UserDefaults, FileTimestamp, SystemBootTime, DiskSpace,
ActiveKeyboards) with every approved reason code, captured 2026-05-05
from the canonical Apple URL via Firecrawl. The file maps web-archetype
detection patterns (`localStorage`, `sessionStorage`,
`navigator.storage.estimate`, `@capacitor/preferences`,
`@capacitor/filesystem`, `Filesystem.stat`) to their target Apple
categories so the future scanner can do source-side detection without
parsing emitted Swift; native-API patterns are also listed for the
Bridge/Port phases. Notable deliberate exclusion: `performance.now()` is
not flagged because WKWebView does not route it through
`mach_absolute_time`. Step 6.7 produced
`config/apple-privacy-manifest.schema.json` — a derived JSON Schema
(Apple does not publish a formal one) for validating
`PrivacyInfo.xcprivacy` after `plistlib` decoding; it enums the five
categories, all 17 reason codes, and the six collection purposes, and
uses conditional `allOf` rules so invalid (category, reason_code) pairs
fail validation.

**Step 6 closed out the same day** — the remaining five sub-steps
(6.2 → 6.6) all shipped 2026-05-05. The scanner core
(`converter/compliance/api_scanner.py`) walks JS/TS source with
identifier-boundary regex (skipping `node_modules`, `dist`, `build`,
`.next`, `workspace`, comment lines) and reads `package.json` +
`capacitor.config.{ts,js,json}` to enumerate declared plugins; both
passes produce the same `APIFinding` dataclass so future passes (emitted
Swift in Bridge/Port) plug in without interface change. The manifest
generator (`converter/compliance/privacy_manifest.py`) emits XML plist
via stdlib `plistlib` and validates against the captured schema *before*
writing — partial files never land on disk. The override loader takes a
`privacy-overrides.yaml` next to the source tree and merges five
sections the scanner can't infer (`additional_categories`, `tracking`,
`third_party_sdks`, `excluded_findings`, `collected_data_types`). A
canonical `templates/privacy-overrides.yaml.template` documents *why*
each section needs human input. To stay stdlib-only (matching the
no-PyYAML decision) a bounded JSON Schema validator was written in-house
covering exactly the keywords the schema uses. One incidental fix landed
in `wrapper/compatibility.py`: a `_split_flow_sequence` helper so inline
flow sequences like `reason_codes: ['1C8F.1']` parse correctly — the
prior loader silently dropped them as raw strings, which masked an
override-merge bug. CLI wiring lives in `wrapper/compliance_step.py`,
hooked into both `convert` and `convert-from-github` (the latter writes
the manifest before commit so it lands in the conversion branch).
Compliance failures surface as warnings, not hard fails; Step 7's
pre-flight scanner is the ship-gate. 54 tests cover the work (25 scanner
+ 21 manifest + 8 wrapper-step), all green.

**Tier 1 Step 7 began the same day.** The sub-plan at
`plans/tier-1-step-7-three-layer-report.md` defines a six-step path:
schema → emitter → renderers → scanner retrofit → wrapper integration →
tests. Sub-step 7.1 shipped: `schemas/report.schema.json` formalises
the three-layer report (A blockers / B manual review / C learnings)
with `Source`, `Finding`, `LearningPattern`, and `Provenance` `$defs`,
version-pinned at `1.0.0`, every object `additionalProperties: false`.
Provenance fields (`model`, `prompt_template`, `seed`) are reserved but
nullable — no MVP producer populates them; Bridge/Port phases will. The
bounded validator in `converter/compliance/privacy_manifest.py` gained
support for JSON Schema's array-form `type` (e.g. `["string", "null"]`)
so nullable fields validate cleanly without bumping to a third-party
`jsonschema` dep. The 54 compliance tests still pass after the
extension; five manual validation cases (empty report, populated
report, missing required, bad enum, unknown layer key) all behave
correctly.

**Step 7 closed out the same day** — the remaining five sub-steps
landed end-to-end. Sub-step 7.2 (`converter/report/emitter.py`)
introduced frozen dataclasses `Finding`, `LearningPattern`, `Source`,
`Provenance`, and `Report`, plus a `ReportBuilder` that de-duplicates
findings by id (across both Layer A and B — first call wins) and
learnings by pattern, validates dataclass invariants in
`__post_init__` (severity enum, confidence ∈ [0, 1], `untranslatable_count
≤ occurrences`), and runs the schema validator on `to_dict()` before
returning, raising `ReportError` with the validator's path-pointed
message on failure. Clock injection (`clock=lambda: "..."`) keeps
test output byte-stable. Sub-step 7.3 (`converter/report/render.py`)
shipped three renderers: `render_json` (sorted-key, indented),
`render_markdown` (sorted by `(severity_rank, category, file, line, id)`
with per-finding detail blocks and category-grouped tables), and
`render_summary` with a 65,000-character default budget for GitHub
PR-comment headroom — Layer A capped at 20, Layer B grouped by
category counts, Layer C top 5 by occurrences, with a `_trim_to_budget`
fallback that halves the Layer A cap iteratively and never produces
invalid Markdown even at extreme tight budgets. Sub-step 7.4 retrofitted
the Step 6 scanner: `converter/compliance/api_scanner.to_findings`
maps `APIFinding` records to `Finding(category="compliance.privacy-manifest")`
records with stable ids (`compliance.privacy-manifest.<short>#<idx>`),
the pinned Apple required-reason-API doc URL, and repo-relative file
paths (resolved via `Path.resolve()` on both sides before
`relative_to`, working around the `TemporaryDirectory(dir="workspace")`
relative-vs-absolute mismatch). The wrapper-side `compliance_step.py`
gained an optional `report_builder` kwarg that, when supplied, pushes
findings into Layer A and preserves the existing one-line summary
print. Sub-step 7.5 wired the wrapper: a new
`_run_compliance_with_report` helper in `wrapper/__main__.py`
constructs a `ReportBuilder` keyed on `Source(archetype="web",
target_mode="wrap", root=str(source_dir), rev=1)`, runs the compliance
step into it, and writes both `report.md` and `report.json` into the
output dir on every conversion (failures surface as warnings, never
ship-blockers — that role belongs to Step 7+1's pre-flight scanner).
Sub-step 7.6 added 62 new tests (14 schema rejection + 28 emitter
validation + 15 renderer byte-stability/budget + 5 end-to-end wrapper
integration); 197 tests total, all green.

**Tier 1 Step 8 closed Tier 1 the same day.** The sub-plan at
`plans/tier-1-step-8-xcode-project-generation.md` pinned XcodeGen as
the project generator (Tuist out of scope per ADR-0001), split
entitlement detection from required-reason API detection
(`config/apple-entitlements.yaml` separate from
`config/apple-required-reason-apis.yaml`), and decided the wrapper
writes `project.yml` while the developer runs `xcodegen generate`.
Sub-step 8.2 shipped a 12-capability catalogue (push, App Groups,
iCloud, HealthKit, Sign in with Apple, camera, microphone, location,
photo library, contacts, calendar, bluetooth) and an entitlement
scanner that mirrors `api_scanner.py`'s walk + dedup contract.
Sub-step 8.3 shipped the XcodeGen emitter (`converter/xcode_project/emitter.py`)
plus six templates including a programmatically-generated 1024×1024
PNG (stdlib `struct` + `zlib`, no Pillow dependency). The emitter
emits Layer-A blockers for placeholder bundle id, placeholder team
id, placeholder app icon, placeholder launch screen, and missing
privacy manifest. Sub-step 8.4 added `--bundle-id` and `--team-id`
flags to both `convert` subcommands and renamed
`_run_compliance_with_report` to `_run_post_conversion_steps` so it
drives both Step 6 and Step 8 against the same `ReportBuilder` —
final `report.md` lists Layer A (privacy manifest + entitlements +
placeholders) and Layer B (permission-prompted capabilities) in one
pass. Sub-step 8.5 shipped the project's first CI workflow
(`.github/workflows/test.yml`): a Linux job that builds XcodeGen 2.39
from source and validates the emitted spec, plus a macOS job (gated
to `main` push and PRs labelled `macos-ci`) that runs `xcodegen
generate` + `xcodebuild` with `CODE_SIGNING_ALLOWED=NO`. Sub-step 8.6
added 36 new tests (13 scanner + 14 emitter + 7 template + 2 wrapper
integration); 233 tests total, all green. **Tier 1 is now complete.**

MVP gap §6.2 (pre-flight compliance scanner) shipped 2026-05-06:
`python -m wrapper preflight <path>` scans for App Store compliance
issues without converting. `wrapper/preflight.py` runs both scanners,
routes findings to Layer-A blockers or Layer-B warnings, and returns a
`PreflightResult` with an exit code (0 = clear, 1 = blocked, 2 = scan
error). 27 new unit tests; 260 tests total, all green.
