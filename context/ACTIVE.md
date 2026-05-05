# Active Context

Last curated: 2026-05-05 (MVP Tier 1 closed — Steps 6/7/8 shipped; 233 tests green; XcodeGen project generation online)

## Current State

Two roadmaps are now closed. The **wrapper roadmap** (Phases 1–5) shipped
2026-05-04 and the **MVP Tier 0 + Tier 1 plan** (`plans/mvp-tier-0-tier-1.md`)
shipped 2026-05-05 across five commits:

- `41c3afc` — MVP gap analysis: Tier 0 complete + Tier 1 Step 6 partial.
- `24c9b61` — Step 6: privacy scanner (`UserDefaults` / `FileManager` /
  `SystemBoot` / disk-space / active-keyboard) + `PrivacyInfo.xcprivacy`
  generator + `--app-name` plumbing.
- `d1da0df` — Step 7.1: three-layer report schema
  (`schemas/report.schema.json`) + nullable-type validator.
- `54b921f` — Step 7: emitter (`converter/reports/three_layer_emitter.py`),
  Markdown + JSON renderers, scanner retrofit, wrapper integration writing
  `report.md` and `report.json` to the output dir.
- `7795104` — Step 8: XcodeGen project generation. Closes Tier 1.

**Tier 1 Step 8 highlights** (the new code):

- `converter/compliance/entitlement_scanner.py` + 12-capability catalogue
  in `config/apple-entitlements.yaml` (~30 patterns: JS APIs + Capacitor
  plugin manifests). Routes Apple-Developer-Account-required capabilities
  to Layer A blockers and permission-prompted capabilities to Layer B
  manual review.
- `converter/xcode_project/emitter.py` + 6 templates
  (`xcodegen.yml.tmpl`, `Info.plist.tmpl`, `AppDelegate.swift.tmpl`,
  `LaunchScreen.storyboard`, `Assets.xcassets/*` including a 1024×1024
  PNG built from stdlib-only `struct` + `zlib`). Atomic per-file writes +
  re-parse validation. Placeholder bundle-id / team-id / app-icon /
  launch-screen / privacy-manifest are emitted as Layer A findings so a
  developer can never accidentally ship a placeholder.
- `wrapper/xcode_step.py` + `_run_post_conversion_steps` (renamed from
  `_run_compliance_with_report`) wires the emitter into the post-convert
  pipeline. New `--bundle-id` and `--team-id` flags on `convert`.
- `wrapper/explainer.py` got an `xcodegen generate && open *.xcodeproj`
  quickstart block.
- First CI workflow (`.github/workflows/test.yml`): Linux job builds
  XcodeGen 2.39 from source and validates the generated `project.yml`;
  macOS job (gated to `main` push and the `macos-ci` label) runs
  `xcodebuild` with `CODE_SIGNING_ALLOWED=NO` against the generated
  project.

**Test totals.** 233 tests green: 137 converter (`python3 -m unittest
discover -t . -s converter`) + 96 wrapper (`python3 -m unittest discover -s
wrapper`). The converter command needs the `-t .` top-level-dir flag to
keep relative imports inside `converter/__init__.py` modules resolvable. Step 8 alone added 36 new tests (entitlement scanner, emitter
spec validation, template substitution, plist round-trips, placeholder
findings, wrapper integration end-to-end).

**Real-world validation** is still the 2026-05-04 `the-survival-bible`
run (50/50 structural pass). Step 8 has not yet been run end-to-end
against a real repo — that is the natural next smoke test.

## What's Next

Tier 1 is closed. The natural next plan is **MVP gap §6.2 — pre-flight
compliance scanner** (the developer-facing CLI that runs the privacy
scanner + entitlement scanner + emitter dry-run + report builder
*before* a conversion run, so a failing repo never enters the converter
in the first place). It reuses every component shipped in Steps 6/7/8 —
no new engine work, just a CLI surface and a fail-fast harness.

Two smaller follow-ons are also queued:

1. End-to-end smoke run of Step 8 against the `the-survival-bible`
   repo (or another small Capacitor-shaped fixture), to confirm the
   emitter's Layer A placeholder findings render correctly in the
   wrapper's triage summary and that `xcodegen generate` succeeds on
   real macOS hardware.
2. The still-open documentation question on converter source-language
   expansion (see `context/OPEN_QUESTIONS.md`) — out-of-scope for MVP
   per `docs/mvp-scope.md` but a recurring user ask.

There is no auto-queued next phase; the user picks the next track.

## Relevant Knowledge Refs

### MVP Tier 0 + Tier 1 (2026-05-05)

- `docs/mvp-scope.md` — authoritative MVP scope (Web → Wrap; binding).
- `plans/mvp-tier-0-tier-1.md` — Tier 0 + Tier 1 plan, all 8 steps marked complete.
- `config/apple-entitlements.yaml` — 12-capability catalogue (entitlement key, capability, label, patterns, requires-developer-account flag, usage strings).
- `config/compatibility-matrix.yaml` — Source × target matrix (only `web × wrap` is `supported: true` for MVP).
- `converter/compliance/privacy_scanner.py` + `converter/compliance/privacy_manifest.py` — Step 6 (privacy scanner + `PrivacyInfo.xcprivacy` generator).
- `converter/compliance/entitlement_scanner.py` — Step 8.2 (entitlement scanner + Layer A/B routing).
- `converter/reports/three_layer_emitter.py` + `converter/reports/renderers.py` — Step 7 (report builder + Markdown + JSON renderers).
- `schemas/report.schema.json` — Step 7.1 (three-layer report schema; nullable-type validator).
- `converter/xcode_project/emitter.py` + `converter/xcode_project/templates/` — Step 8.3 (XcodeGen spec emitter + 6 templates incl. 1024×1024 PNG).
- `wrapper/compatibility.py` + `wrapper/compliance_step.py` + `wrapper/xcode_step.py` — wrapper-side glue.
- `wrapper/__main__.py` — `convert` and `convert-from-github` subcommands; new `--bundle-id`, `--team-id`, `--app-name` flags.
- `.github/workflows/test.yml` — Linux + macOS CI; macOS gated to `main` push and `macos-ci` label.

### Wrapper roadmap (2026-05-04, complete)

- `plans/gap-analysis-and-build-guide.md` — capability matrix and roadmap (all 15 BUILD items marked complete).
- `plans/github-round-trip.md` — wrapper design + delivered command surface (Phases 1–5 all complete).
- `plans/wrapper-phase-4-conversational-polish.md` + `plans/wrapper-phase-5-open-pr.md`.
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper / Claude Code).
- `wrapper/git_ops.py`, `wrapper/orchestrator.py`, `wrapper/triage.py`, `wrapper/repo_metadata.py`, `wrapper/post_flight.py`, `wrapper/explainer.py`, `wrapper/pr_ops.py`.

### Tests

- Converter: `python3 -m unittest discover -t . -s converter` (137 tests).
- Wrapper: `python3 -m unittest discover -s wrapper` (96 tests).
- Combined: 233 green.

## Git Identity (this repo)

Local config: `jjdcodingcollective <jjd.codingcollective@gmail.com>` (scoped, no global write).
Auto-conversion commits on `Requires-more-review/` branches use `ios-agent <ios-agent@localhost>`.
