# Active Context

Last curated: 2026-05-20 (Track 1 smoke test complete; template legend bug fixed; rolling into Track 2)

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

**Test totals.** 260 tests green: 137 converter (`python3 -m unittest
discover -t . -s converter`) + 123 wrapper (`python3 -m unittest discover -s
wrapper`; +27 from §6.2 preflight). The converter command needs the `-t .`
top-level-dir flag to keep relative imports inside `converter/__init__.py`
modules resolvable.

**Real-world validation — 2026-05-20 smoke test (Track 1) ✅**

End-to-end run against `the-survival-bible/apps/web` (React + Vite;
jjdcodingcollective-collab/the-survival-bible, private):

- `preflight`: exit 1, 84 Layer-A `UserDefaults` blockers. ✅
- `convert --allow-unsupported`: 70 files converted, 63% avg confidence,
  0 swiftc errors, `PrivacyInfo.xcprivacy` + `project.yml` emitted. ✅
- `report.json` Layer A: 87 items (84 UserDefaults + 3 xcode.placeholder). ✅
- Template legend bug found and fixed (`commit 6e2cff3`): legend lines used
  `{{TOKEN}}` syntax which `_substitute()` replaced with live values. Switched
  to `<TOKEN>` in all three templates. Broken test updated. 260 green. ✅

Note: this repo has React Native in `apps/mobile` — our Capacitor wrap output
targets the `apps/web` layer only, which is correct for MVP scope.

## What's Next

**Track 2 — MVP §4.x compliance items** is now active.
Plan at `plans/mvp-section-4-compliance.md`.

Remaining open tracks after Track 2:
- **Ship / publish** — `v0.1.0` tag, PyPI, GitHub Release.
- **Phase 2 kickoff** — Kotlin → Swift converter expansion (deferred per MVP scope).

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
- `wrapper/preflight.py` — MVP §6.2 pre-flight scanner; `run_preflight()` + `PreflightResult` + `format_preflight_report()`.
- `wrapper/__main__.py` — `convert`, `convert-from-github`, `preflight` subcommands.
- `.github/workflows/test.yml` — Linux + macOS CI; macOS gated to `main` push and `macos-ci` label.

### Phase E — docs expansion (2026-05-04, BUILD-16…30, complete)

- `plans/reviews/2026-05-04-language-transposition.md` — in-repo canonical copy of the gap analysis that drove Phase E.
- `docs/02-swift-fundamentals/swift-objc-interop.md` — BUILD-16 (ObjC interop, bridging headers, KVO).
- `docs/02-swift-fundamentals/concurrency-and-sendable.md` — BUILD-17 (actors, `@MainActor`, `Sendable`).
- `docs/02-swift-fundamentals/generics-and-protocols-deep.md` — BUILD-18 (`some` vs `any`, PATs, type erasure).
- `docs/02-swift-fundamentals/arc-and-lifetimes.md` — BUILD-19 (ARC, retain cycles, capture lists, `Task` retention).
- `docs/02-swift-fundamentals/from-kotlin.md`, `from-java.md`, `from-python.md` — BUILD-21 (Tier 1 source-language chapters).
- `docs/03-architecture/persistence.md` — BUILD-22 (UserDefaults / Keychain / SwiftData / Core Data / CloudKit).
- `docs/04-ui-development/uikit-guide.md` — BUILD-23 (view controllers, Auto Layout, diffable data sources, SwiftUI bridge).
- `docs/02-swift-fundamentals/from-csharp.md`, `from-dart-flutter.md` — BUILD-24/25 (Xamarin/MAUI sunset, Flutter replatforming).
- `docs/02-swift-fundamentals/combine-and-async-streams.md`, `codable-deep.md`, `swift-toolkit-for-web-devs.md` — BUILD-26 (deeper JS/TS companion chapters).
- `docs/09-deployment/app-store-operations.md` — BUILD-29 (privacy manifest, ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements, pre-submission checklist).
- `docs/02-swift-fundamentals/cpp-interop.md`, `rust-ffi.md`, `from-server-langs.md` — BUILD-27/28/30 (C++ interop, Rust FFI, Go/Ruby/PHP).
- Build guide (`plans/gap-analysis-and-build-guide.md`) updated: all 30 BUILD items (BUILD-1…30) marked ✅ complete; Phase E ✅ COMPLETE.

### Wrapper roadmap (2026-05-04, Phases 1–5 complete)

- `plans/gap-analysis-and-build-guide.md` — capability matrix and roadmap (all 30 BUILD items marked complete).
- `plans/github-round-trip.md` — wrapper design + delivered command surface (Phases 1–5 all complete).
- `plans/wrapper-phase-4-conversational-polish.md` + `plans/wrapper-phase-5-open-pr.md`.
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper / Claude Code).
- `wrapper/git_ops.py`, `wrapper/orchestrator.py`, `wrapper/triage.py`, `wrapper/repo_metadata.py`, `wrapper/post_flight.py`, `wrapper/explainer.py`, `wrapper/pr_ops.py`.

### Tests

- Converter: `python3 -m unittest discover -t . -s converter` (137 tests).
- Wrapper: `python3 -m unittest discover -s wrapper` (123 tests; +27 preflight).
- Combined: 260 green.

## Git Identity (this repo)

Local config: `jjdcodingcollective <jjd.codingcollective@gmail.com>` (scoped, no global write).
Auto-conversion commits on `Requires-more-review/` branches use `ios-agent <ios-agent@localhost>`.
