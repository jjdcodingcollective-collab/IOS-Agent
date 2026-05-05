# IOS-Agent

> A reference guide **and** an automated converter for teams transitioning from web development (containerized builds, Vercel deployments) to the iOS and Apple ecosystem.

**Who this is for:** Web developers who build with modern frameworks (React, Next.js, Vite), deploy on Vercel, and are now bringing their products to native iOS.

**What this covers:** The full journey from web to native — environment setup, Swift fundamentals mapped to web concepts, architecture translation, WebView-based shells (Wrap / Bridge), App Store deployment, and everything in between. Plus a working pipeline that takes your TypeScript codebase and produces a buildable Swift/SwiftUI project.

---

## The Converter (operational)

Two ways to use it:

**1. Local conversion** — point it at a TS project on disk:
```
python -m wrapper convert path/to/typescript-app --app-name MyApp
```

**2. GitHub round-trip** — clone a repo, convert, and create an `ios-conversion` branch:
```
python -m wrapper convert-from-github https://github.com/you/your-app --app-name MyApp
# Monorepo? scope to a subdirectory:
python -m wrapper convert-from-github https://github.com/you/your-app \
    --source-subdir apps/mobile --app-name MyApp
# Push the branch to origin (default is to prompt after the local commit):
python -m wrapper convert-from-github https://github.com/you/your-app --push
# Or commit locally only:
python -m wrapper convert-from-github https://github.com/you/your-app --no-push
```

The converter writes a Swift project (`Package.swift`, `project.yml` for [xcodegen](https://github.com/yonaskolb/XcodeGen), `Sources/`, `Tests/`) plus five reports under `.ios-conversion/` on the conversion branch. Runs that fail validation or score below 60% confidence land on a `Requires-more-review/` prefixed branch so reviewers can spot them at a glance.

Pipeline:

```
TS source → analyzer → reviewer → rewriter → assembler → validator → reports + Swift project
```

Status: all 15 BUILD-* items shipped (see `plans/gap-analysis-and-build-guide.md`); the wrapper roadmap is **complete through Phase 5**. Phase 1–3 covered clone + convert + local commit + opt-in push (with hard refusal on protected branches, no force-push, and a read-only fallback if credentials are missing). Phase 4 added a pre-flight GitHub repo-metadata banner, a copy-pasteable `gh pr create` command after a successful push (with a compare-URL fallback for users without `gh`), and an educational "what's on this branch" block — all suppressible with `--brief`. Phase 5 wires `--open-pr` (off by default) to invoke `gh pr create` directly with the same `(base, head, title, body-file)` tuple Phase 4 prints, and rejects the incoherent `--no-push --open-pr` combination.

---

## Table of Contents

### Getting Started
- [MVP Scope](docs/mvp-scope.md) — Authoritative reference for what's in and out of MVP
- [Glossary](docs/glossary.md) — Canonical terms (Wrap / Bridge / Port mode names, archetypes, compliance)
- [ADR 0001 — Tooling Stack](docs/adr/0001-tooling-stack.md) — Mandated tooling, version policy, forbidden reinvention
- [Web-to-iOS Transition Overview](docs/01-getting-started/transition-overview.md) — Strategy, timeline, and decision framework
- [Environment Setup](docs/01-getting-started/environment-setup.md) — Xcode, tooling, certificates, and simulators

### Language & Fundamentals
- [Swift for Web Developers](docs/02-swift-fundamentals/swift-for-web-devs.md) — Swift concepts mapped to JavaScript/TypeScript
- [Swift for Kotlin Developers](docs/02-swift-fundamentals/from-kotlin.md) — Near-twin language transposition (coroutines, sealed classes, data classes)
- [Swift for Java Developers](docs/02-swift-fundamentals/from-java.md) — POJOs → structs, checked exceptions → typed throws, GC → ARC
- [Swift for Python Developers](docs/02-swift-fundamentals/from-python.md) — Static typing, no truthiness, no GIL, optionals as types
- [Swift for C# Developers](docs/02-swift-fundamentals/from-csharp.md) — LINQ → sequence ops, GC → ARC, Xamarin/MAUI sunset migration
- [Swift for Dart / Flutter Developers](docs/02-swift-fundamentals/from-dart-flutter.md) — Widgets → Views, StatefulWidget → @State, isolates → actors
- [Swift for Go / Ruby / PHP Developers](docs/02-swift-fundamentals/from-server-langs.md) — Goroutines → Tasks, channels → AsyncStream, no `method_missing`, no superglobals
- [Strict Concurrency & Sendable](docs/02-swift-fundamentals/concurrency-and-sendable.md) — Actors, `@MainActor`, `Sendable`, Swift 6 strict mode
- [ARC, Captures & Lifetimes](docs/02-swift-fundamentals/arc-and-lifetimes.md) — Reference counting, retain cycles, `[weak self]`, `Task` retention
- [Generics, Opaque Types & Existentials](docs/02-swift-fundamentals/generics-and-protocols-deep.md) — `some` vs `any`, PATs, type erasure
- [Objective-C Interop](docs/02-swift-fundamentals/swift-objc-interop.md) — `@objc`, bridging headers, `#selector`, KVO, framework header reading
- [C++ / Objective-C++ Interop](docs/02-swift-fundamentals/cpp-interop.md) — Swift 5.9+ first-class C++ interop, `.mm` shims, `std::string`/`std::vector` bridging
- [Rust → Swift FFI](docs/02-swift-fundamentals/rust-ffi.md) — `extern "C"`, `cbindgen`, ownership across the boundary, `xcframework` packaging, `uniffi`/`cargo-swift`
- [Combine & AsyncStream](docs/02-swift-fundamentals/combine-and-async-streams.md) — Combine for RxJS readers, AsyncSequence, when to pick which
- [Codable Customization](docs/02-swift-fundamentals/codable-deep.md) — CodingKeys, dates, polymorphism, lossy arrays, property-wrapper decoders
- [The Swift Toolkit](docs/02-swift-fundamentals/swift-toolkit-for-web-devs.md) — KeyPaths, property-wrapper authoring, result builders, IUOs

### Architecture
- [Architecture Patterns](docs/03-architecture/patterns.md) — Translating web architecture to iOS (MVC, MVVM, state management)
- [Persistence](docs/03-architecture/persistence.md) — UserDefaults, Keychain, FileManager, SwiftData, Core Data, CloudKit (mapped from ORMs)

### UI Development
- [UI Development with SwiftUI](docs/04-ui-development/swiftui-guide.md) — Building interfaces, mapped from web components and CSS
- [UIKit for Web & Imperative-UI Developers](docs/04-ui-development/uikit-guide.md) — View controllers, Auto Layout, diffable data sources, bridging to SwiftUI

### Networking & APIs
- [Networking & API Integration](docs/05-networking/api-integration.md) — URLSession, async/await, REST/GraphQL from Swift

### Hybrid & WebView
- [WebView & Hybrid Integration](docs/06-webview-hybrid/webview-guide.md) — Embedding web content, JS-Swift bridging, progressive migration

### Testing & Debugging
- [Testing & Debugging](docs/07-testing/testing-guide.md) — XCTest, UI testing, Instruments, debugging workflows

### Security & Privacy
- [Security & Privacy](docs/08-security/security-guide.md) — App Transport Security, Keychain, privacy manifests, App Store requirements

### Deployment & Distribution
- [Deployment & Distribution](docs/09-deployment/deployment-guide.md) — TestFlight, App Store Connect, CI/CD (mapped from Vercel workflows)
- [App Store Operations](docs/09-deployment/app-store-operations.md) — Privacy manifest, ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements, pre-submission checklist

### Maintenance
- [Maintenance & Dependencies](docs/10-maintenance/maintenance-guide.md) — Swift Package Manager, versioning, OS compatibility

### Common Pitfalls
- [Common Pitfalls for Web Developers](docs/11-pitfalls/web-dev-gotchas.md) — Mistakes web developers make on iOS and how to avoid them

---

## How to Use This Guide

**New to iOS?** Start with the [Transition Overview](docs/01-getting-started/transition-overview.md), then work through the [Environment Setup](docs/01-getting-started/environment-setup.md) and [Swift for Web Developers](docs/02-swift-fundamentals/swift-for-web-devs.md).

**Building a Wrap or Bridge app?** Jump to [WebView & Hybrid Integration](docs/06-webview-hybrid/webview-guide.md) for strategies on embedding your existing web app in a native shell.

**Ready to ship?** The [Deployment Guide](docs/09-deployment/deployment-guide.md) maps your Vercel workflow to TestFlight and App Store Connect.

**Hit a wall?** Check [Common Pitfalls](docs/11-pitfalls/web-dev-gotchas.md) first — it covers the most frequent issues web developers encounter.

---

## Contributing

This is a living reference. To contribute:

1. Create a branch from `main`
2. Add or edit markdown files in the relevant `docs/` subfolder
3. Update the Table of Contents in this README if adding new sections
4. Open a PR with a clear description of what changed and why

**Style guidelines:**
- Write for developers who know web but not iOS — explain the *why*, not just the *how*
- Include code examples for every concept
- Link to official Apple documentation where applicable
- Mark deprecated patterns clearly with `> **Deprecated:**` callouts

---

## Scope (Current)

The `docs/` guide now covers **JavaScript / TypeScript, Kotlin, Java, Python, C#, Dart/Flutter, and Go / Ruby / PHP → Swift** developers, plus operational depth on Objective-C interop, **C++ and Rust interop**, strict concurrency, ARC, generics, persistence, and UIKit (for non-greenfield iOS codebases).

**Phase E Tier 0 + Tier 1 shipped 2026-05-04** (BUILD-16 through BUILD-22): seven new chapters, three correctness fixes, and a per-language template established for future source-language additions.

**BUILD-26 + BUILD-29 also shipped 2026-05-04** out of the Tier 2/3 backlog (highest reader-leverage among the non-language items): three new companion chapters under `02-swift-fundamentals/` deepening the JS/TS material (Combine, Codable customization, and the KeyPaths/property-wrappers/result-builders/IUO toolkit), and a dedicated `09-deployment/app-store-operations.md` chapter consolidating privacy manifest, ATT, BGTaskScheduler, push, App Groups, and entitlements as a pre-submission checklist.

**Phase E is now complete.** All Tier 2/3/4 chapters (BUILD-23/24/25/27/28/30) shipped 2026-05-04. The remaining roadmap work is wrapper Phase 4 (conversational polish) and Phase 5 (`--open-pr` via `gh pr create`). See `plans/gap-analysis-and-build-guide.md` for the full record and `plans/phase-e-tier-2-3-remaining.md` for the sequencing log.

The converter (`converter/`, `wrapper/`) remains TypeScript-source only. Expanding source-language coverage in the docs ahead of the converter is intentional — the docs are the cheaper experiment.

---

## Last Updated

**2026-05-05** *(MVP gap analysis kicked off; Tier 0 complete; Tier 1 Step 6 ✅ complete; Tier 1 Step 7 sub-step 7.1 shipped)* — Senior-iOS-architect review of the whole concept produced a 34-item MVP gap analysis (`/storage/outputs/ios-agent/MVP-Gap-Analysis.md`): 27 BLOCKING + 7 AT-RISK items, binding Definition of Done = actual App Store approval of a tool-converted reference web app. Three new plans landed: `plans/mvp-tier-0-tier-1.md` (parent), `plans/tier-1-step-6-privacy-scanner.md` (Step 6 sub-plan), and `plans/tier-1-step-7-three-layer-report.md` (Step 7 sub-plan).

Tier 0 (5 steps, decisions + docs only) shipped end-to-end:
- Step 1: `docs/mvp-scope.md` — MVP locked to web → Wrap only; explicit exclusions for Java, Kotlin, Python, Bridge, Port, UI translation; 7-criteria Definition of Done; marketing-compliance section bans deprecated mode names and "convert any codebase" copy.
- Step 2: `config/compatibility-matrix.yaml` (18 combinations across 6 source archetypes × 3 target modes; all `supported: false` until App Store approval) + `wrapper/compatibility.py` (minimal-subset YAML loader, no PyYAML dep, exports `Combination`, `CompatibilityMatrix`, `assert_supported()`, `UnsupportedCombination`) + `wrapper/__main__.py` integration: both `convert` and `convert-from-github` gate on `("web", "wrap")` before any work, with a `--allow-unsupported` dev override that prints a warning and proceeds; 9 new tests in `wrapper/tests/test_compatibility.py` covering the parser, the gate, and marketing-protection invariants (`python → wrap` always blocked).
- Step 3: Mode rename — "WKWebView wrapper" → **Wrap**, "semi-native hybrid" → **Bridge**, "fully native" → **Port**. Canonical definitions live in new `docs/glossary.md`; rename propagated through `README.md`, `docs/01-getting-started/transition-overview.md`, `docs/06-webview-hybrid/webview-guide.md`, and `docs/07-testing/testing-guide.md`.
- Step 4: `docs/adr/0001-tooling-stack.md` — the project's first ADR. Mandates Capacitor, tree-sitter, swift-syntax + swift-format, XcodeGen (default) / Tuist (opt-in), SwiftLint + SwiftFormat + periphery, J2ObjC (Phase 2), Skip + KMM (Phase 2). Quarterly review; latest-2-Xcode CI gate. "Forbidden without superseding ADR" list explicitly forbids in-house parser reinvention. Alternatives considered (in-house parser, React Native / Flutter as host, Cordova, pure-LLM) all rejected with reasoning.
- Step 5: Python removed from MVP supported source languages; audit confirmed no Python detection code paths exist in the converter, so the matrix gate is sufficient — no `EXPERIMENTAL_PYTHON` flag needed.

Tier 1 Step 6 (privacy scanner + manifest generator) is now complete — all seven sub-steps shipped 2026-05-05:
- Step 6.1: `config/apple-required-reason-apis.yaml` — versioned, data-driven catalogue of Apple's five required-reason API categories (UserDefaults, FileTimestamp, SystemBootTime, DiskSpace, ActiveKeyboards) with every approved reason code and a clear update policy. Maps web-archetype detection patterns (`localStorage`, `sessionStorage`, `navigator.storage.estimate`, `@capacitor/preferences`, `@capacitor/filesystem`, `Filesystem.stat`) to their target categories; native-API patterns are listed for future Bridge/Port phases. Deliberate exclusion: `performance.now()` is not flagged because WKWebView does not route it through `mach_absolute_time`.
- Step 6.2: `converter/compliance/api_scanner.py` — walks JS/TS source with identifier-boundary regex (skipping `node_modules`, `dist`, `build`, `.next`, `workspace`, comment lines) and reads `package.json` + `capacitor.config.{ts,js,json}` to enumerate declared plugins. Both passes produce the same `APIFinding` dataclass so future passes (emitted Swift in Bridge/Port) plug in without interface change.
- Step 6.3: `converter/compliance/privacy_manifest.py` — emits XML plist via stdlib `plistlib` and validates against the captured schema *before* writing (partial files never land on disk). Includes a bounded in-house JSON Schema validator (no `jsonschema` dep) covering exactly the keywords the schema uses, matching the no-PyYAML stdlib-only posture.
- Step 6.4: `templates/privacy-overrides.yaml.template` — canonical override file documenting *why* the scanner can't infer each section (`additional_categories`, `tracking`, `third_party_sdks`, `excluded_findings`, `collected_data_types`). Developer drops a populated copy next to their source tree.
- Step 6.5: 54 tests across `converter/compliance/tests/test_api_scanner.py` (25), `converter/compliance/tests/test_privacy_manifest.py` (21), and `wrapper/tests/test_compliance_step.py` (8). Inline `TemporaryDirectory(dir="workspace")` fixtures (no checked-in fixture trees). Tests verify shipped template loads cleanly and that no partial file is left on disk on validation failure.
- Step 6.6: `wrapper/compliance_step.py` — thin orchestrator wired into both `convert` and `convert-from-github`. Discovers `privacy-overrides.yaml` next to the source tree, writes `PrivacyInfo.xcprivacy` to the conversion output dir, prints a one-line summary (`privacy manifest: N finding(s) across M categories → PrivacyInfo.xcprivacy`), and surfaces failures as warnings rather than hard fails — Step 7's pre-flight scanner is the ship-gate. The hook fires before commit in `convert-from-github` so the manifest lands in the conversion branch.
- Step 6.7: `config/apple-privacy-manifest.schema.json` — a derived JSON Schema (Apple does not publish a formal one) for validating `PrivacyInfo.xcprivacy` after `plistlib` decoding. Enums the 5 categories, all 17 reason codes, and the 6 collection purposes; conditional `allOf` rules reject invalid (category, reason_code) pairs (e.g. using `CA92.1` under `FileTimestamp`).

One incidental fix landed in `wrapper/compatibility.py`: a `_split_flow_sequence` helper so inline flow sequences like `reason_codes: ['1C8F.1']` parse correctly — the prior loader silently dropped them as raw strings, which masked an override-merge bug. All 135 tests across the wrapper, compatibility, repo-metadata, post-flight, explainer, compliance, and compliance-step suites pass.

Tier 1 Step 7 (three-layer report schema + emitter — gap §7.1) is in progress. Sub-step 7.1 shipped:
- Step 7.1: `schemas/report.schema.json` — formalises the three-layer report (A blockers / B manual review / C learnings) with `Source`, `Finding`, `LearningPattern`, and `Provenance` `$defs`. Version-pinned at `1.0.0`; every object is `additionalProperties: false`. `Finding.severity` enum is `blocker | warning | info`; `Source.archetype` matches the compatibility-matrix vocabulary; `Source.target_mode` is `wrap | bridge | port`. Provenance fields (`model`, `prompt_template`, `seed`) are reserved but nullable — no MVP producer populates them; Bridge/Port phases will. Trend fields (`prior_rev_confidence`, `delta`) are likewise reserved for revision-aware runs. The bounded JSON Schema validator in `converter/compliance/privacy_manifest.py` was extended to support array-form `type` (e.g. `["string", "null"]`) so nullable fields validate without bumping to a third-party `jsonschema` dep — matching the no-PyYAML stdlib-only posture. The 54 compliance tests still pass after the validator extension.

Sub-steps 7.2 (emitter library), 7.3 (renderers — Markdown / JSON / summary), 7.4 (Step 6 scanner retrofit via `to_findings()` adapter), 7.5 (wrapper integration writing `report.md` + `report.json`), and 7.6 (tests) are next, in that order. After Step 7 closes: Step 8 (Xcode project generation via XcodeGen / Tuist — gap §3.4 + §6.2).

**2026-05-04** *(Wrapper Phase 5 shipped — `--open-pr` via `gh pr create`; wrapper roadmap complete)* — New module `wrapper/pr_ops.py` adds `gh_available()` (checks `shutil.which("gh")` + `gh auth status`, returns a clear install/login hint on failure) and `open_pr(repo_path, *, base, head, title, body_path)` which invokes `gh pr create` from inside the repo with a 60s timeout, captures stdout/stderr, and extracts the PR URL via regex (last `https://github.com/.../pull/<n>` match wins). New `--open-pr` flag on `convert-from-github` (off by default — opening a PR is irreversible: notifications, CI, teammates) reuses the Phase 4 `(base, head, title, body-file)` tuple, gates on a successful push, and refuses the incoherent `--no-push --open-pr` combination at the argparse layer. Existing-PR collisions surface gh's own stderr ("a pull request for branch X already exists"). Read-only fallback preserved exactly as Phase 3 left it: a failed push still prints the manual `git push -u` retry instruction and never attempts a PR. 15 new unit tests using `unittest.mock.patch` for `subprocess.run` and `shutil.which` — no real `gh` calls in tests; 72 wrapper tests total. Plan: `plans/wrapper-phase-5-open-pr.md`. **The wrapper roadmap is now complete.**

**2026-05-04** *(Wrapper Phase 4 shipped — conversational polish)* — Three new wrapper modules: `wrapper/repo_metadata.py` (parses HTTPS/SSH/scheme-less GitHub URLs, fetches `/repos/{owner}/{repo}` via the REST API with auth resolved through `gh auth token` → `GITHUB_TOKEN` → anonymous, renders a single-line "About:" banner with visibility/language/default-branch/last-push/stars/issues — soft-fails on every error path), `wrapper/post_flight.py` (after a successful push, prints a copy-pasteable `gh pr create` command with `--body-file .ios-conversion/generation-summary.md` plus a fallback `compare/<base>...<head>?expand=1` URL for users without `gh`), and `wrapper/explainer.py` (a short "What's on this branch" block between the commit and the push prompt, with separate text for clean runs vs `Requires-more-review/` prefixed runs). New `--brief` flag on both subcommands suppresses the metadata banner and the explainer block; the PR command stays. 57 unit tests (33 metadata + 24 post-flight/explainer), no network in tests. Plan: `plans/wrapper-phase-4-conversational-polish.md`. The remaining wrapper roadmap is Phase 5 (`--open-pr` via `gh pr create`).

**2026-05-04** *(BUILD-27 + BUILD-28 + BUILD-30 shipped — C++, Rust, server-langs; Phase E complete)* — Three new chapters under `02-swift-fundamentals/`: `cpp-interop.md` (Swift 5.9+ first-class C++ interop, `.interoperabilityMode(.Cxx)`, module map setup, `std::string`/`std::vector` bridging, Objective-C++ `.mm` shims for exception translation, vendored static libs vs SPM binary frameworks, ABI-breakage and `std::string_view` lifetime hazards), `rust-ffi.md` (`extern "C"` + `#[no_mangle]` + `catch_unwind`, `cbindgen` header generation, `Box::into_raw`/`Box::from_raw` ownership patterns, string-bridging via `withCString` and `String(cString:)`, async strategies, `uniffi-rs` and `cargo-swift` higher-level options, building an `xcframework` with `cargo` + `xcodebuild -create-xcframework`), and `from-server-langs.md` (combined Go/Ruby/PHP chapter — goroutines/channels → `Task`/`AsyncStream`, Go interfaces vs Swift protocols with PAT caveats, no `method_missing` and no monkey-patching for Ruby refugees, no type-juggling and no superglobals for PHP refugees). README TOC, ACTIVE, REFERENCES, and gap-analysis build guide updated; **Phase E backlog is now empty**.

**2026-05-04** *(BUILD-24 + BUILD-25 shipped — C# and Dart/Flutter chapters)* — Two new source-language chapters: `docs/02-swift-fundamentals/from-csharp.md` (LINQ → sequence ops, GC → ARC, MVVM with `@Observable`, Xamarin/MAUI sunset migration plan) and `docs/02-swift-fundamentals/from-dart-flutter.md` (widgets → views, `StatefulWidget` → `@State`, `ChangeNotifier` → `@Observable`, isolates → actors, layout & rebuild cost-model contrast). Both follow the established per-language template and cross-link to the deep chapters. README TOC, ACTIVE, REFERENCES, and gap-analysis build guide updated; remaining backlog narrowed to BUILD-27/28/30.

**2026-05-04** *(BUILD-23 shipped — UIKit chapter)* — New chapter `docs/04-ui-development/uikit-guide.md` covering view controllers + lifecycle, Auto Layout (the constraint mental model + `translatesAutoresizingMaskIntoConstraints` trap), Storyboards/XIBs/programmatic tradeoffs, modern `UICollectionView` with diffable data sources, navigation patterns, gestures + responder chain, and bidirectional bridging to SwiftUI via `UIHostingController` / `UIViewRepresentable`. README TOC updated; BUILD-23 marked ✅ in the gap-analysis build guide. No converter or wrapper code changes.

**2026-05-04** *(Wrapper Phase 3 shipped — opt-in push)* — `convert-from-github` gains `--push` / `--no-push` flags (default: prompt after the local commit lands). `wrapper/git_ops.py` adds `push_branch()` + `PushInfo`: plain `git push --set-upstream`, never `--force`, hard refusal on the protected-branch list, and a read-only fallback when credentials are missing or the push otherwise fails. `--yes` implies `--push` unless overridden. Phase 3 marked ✅ in `plans/github-round-trip.md`; the previously-open re-run-on-stale-base question is resolved as "leave alone."

**2026-05-04** *(BUILD-26 + BUILD-29 shipped from Tier 2/3 backlog)* — Four new chapters: `combine-and-async-streams.md`, `codable-deep.md`, `swift-toolkit-for-web-devs.md` (under `02-swift-fundamentals/`), and `app-store-operations.md` (under `09-deployment/`). The intro `swift-for-web-devs.md` got a "Going Deeper" pointer block linking the eight companion chapters. Cross-links added from `security-guide.md` and `deployment-guide.md` into the new operations chapter. BUILD-26 and BUILD-29 marked ✅ in the gap-analysis build guide. No converter code changes.

**2026-05-04** *(Phase E Tier 0 + Tier 1 shipped, evening)* — Authored seven new chapters: `swift-objc-interop.md`, `concurrency-and-sendable.md`, `arc-and-lifetimes.md`, `generics-and-protocols-deep.md`, `from-kotlin.md`, `from-java.md`, `from-python.md`, plus `03-architecture/persistence.md`. Fixed internal inconsistencies in `web-dev-gotchas.md`, `api-integration.md`, and `swift-for-web-devs.md` (eliminated `try!`/`as!` from happy-path samples; corrected `@EnvironmentObject ↔ useContext` mapping; added IUO callout). BUILD-16…22 marked ✅ in the gap-analysis build guide. No converter code changes.

**2026-05-04** *(revised same-day)* — Documentation review against "popular coding languages → Swift" brief. Added dimension 6 (Documentation & Source-Language Coverage) to gap analysis: 9 new gaps, 7 specified BUILD items, 8-item backlog, new Phase E roadmap. Source review at `outputs/Language-Transposition-Gap-Analysis.md`. No code changes.

**2026-05-04** — Added GitHub round-trip wrapper (Phase 1 + 2). Validated end-to-end against `the-survival-bible` monorepo (42 files converted, 50/50 structural validation pass). All 15 original BUILD-* items from the gap analysis are shipped.

**2026-04-25** — Initial release covering the full web-to-iOS transition path and the four-phase converter pipeline.

Maintained by the IOS-Agent team. Review quarterly or after major WWDC announcements.
