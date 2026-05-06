# References

Last curated: 2026-05-06 (MVP §6.2 pre-flight scanner shipped; 260 tests green)

## Sources

### Test Repositories

- **jjdcodingcollective-collab/the-survival-bible** — Real-world monorepo used
  for end-to-end smoke testing. Contains `apps/web` (Next.js), `apps/mobile`
  (React Native), and 4 shared packages. The `apps/mobile` subdir (42 files)
  is the canonical test target for the iOS converter. First run surfaced the
  arrow-function leak; second run (with `--source-subdir apps/mobile`) achieved
  50/50 validation pass.

### Key Plans

- `plans/mvp-tier-0-tier-1.md` — MVP Tier 0 + Tier 1 plan; **all 8 steps shipped 2026-05-05**. Step 6 (privacy scanner), Step 7 (three-layer report), Step 8 (XcodeGen project generation). Tier 1 closed.
- `docs/mvp-scope.md` — authoritative MVP scope reference. Web → Wrap mode only; everything else explicitly deferred. Binding; marketing copy and product UI must conform.
- `plans/gap-analysis-and-build-guide.md` — capability matrix and full
  remediation plan. **All 15 original BUILD items complete.** Revised
  2026-05-04 to add dimension 6 (Documentation & Source-Language Coverage),
  GAP-D1…D9, BUILD-16…22, Tier 2/3/4 backlog (BUILD-23…30), and Phase E
  roadmap. **Phase E Tier 0 + Tier 1 (BUILD-16…22) shipped 2026-05-04.**
  **BUILD-26 + BUILD-29 also shipped 2026-05-04** out of the Tier 2/3 backlog.
- `plans/github-round-trip.md` — design spec for the wrapper's GitHub round-trip
  (Phases 1–5). **All five phases delivered.** Phase 3 added `--push`/`--no-push`,
  `push_branch()` + `PushInfo`, protected-branch refusal, and a read-only
  fallback. Phase 4 added pre-flight repo-metadata banner, post-flight
  `gh pr create` command + compare-URL fallback, educational mode, and
  `--brief`. Phase 5 added `--open-pr` (invokes `gh pr create`; off by
  default; refuses `--no-push --open-pr`).
- `plans/wrapper-phase-4-conversational-polish.md` — Phase 4 sub-plan,
  shipped 2026-05-04 in three commits matching the locked sequencing.
- `plans/wrapper-phase-5-open-pr.md` — Phase 5 sub-plan, shipped 2026-05-04
  in a single commit per the locked sequencing.
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper /
  Claude Code) and long-term product vision.
- `plans/ios-code-converter.md` — original converter design (historical).

### Reviews & external deliverables

- `plans/reviews/2026-05-04-language-transposition.md` — 2026-05-04 review
  of `docs/` against the "transposing popular coding languages to Swift"
  brief. Source for GAP-D1…D9 and BUILD-16…30. (A copy also lives at
  `/storage/outputs/ios-agent/Language-Transposition-Gap-Analysis.md` for
  the user's Files panel; the in-repo copy is canonical.)

### Documentation Chapters (Phase E)

Phase E Tier 0 + Tier 1 (2026-05-04, BUILD-16…22):
- `docs/02-swift-fundamentals/concurrency-and-sendable.md` — strict concurrency, actors, `@MainActor`, `Sendable`.
- `docs/02-swift-fundamentals/arc-and-lifetimes.md` — ARC, retain cycles, `weak`/`unowned`, capture lists, `Task` retention.
- `docs/02-swift-fundamentals/swift-objc-interop.md` — `@objc`, bridging, `#selector`, KVO, NSError, framework header reading.
- `docs/02-swift-fundamentals/generics-and-protocols-deep.md` — generics, `some` (opaque) vs `any` (existential), PATs, type erasure.
- `docs/02-swift-fundamentals/from-kotlin.md` — Kotlin → Swift transposition.
- `docs/02-swift-fundamentals/from-java.md` — Java → Swift transposition.
- `docs/02-swift-fundamentals/from-python.md` — Python → Swift transposition.
- `docs/03-architecture/persistence.md` — UserDefaults / Keychain / FileManager / SwiftData / Core Data / CloudKit; ORM mappings (Prisma / Drizzle / ActiveRecord / SQLAlchemy / Hibernate / Room).

Phase E Tier 2/3 partial (2026-05-04, BUILD-26 + BUILD-29):
- `docs/02-swift-fundamentals/combine-and-async-streams.md` — Combine for RxJS readers, AsyncSequence, `@Published`/`AnyCancellable`/`AnyPublisher`, `Observable` macro decision table.
- `docs/02-swift-fundamentals/codable-deep.md` — CodingKeys, dates, polymorphism, lossy arrays, property-wrapper-based decoders, JSON-library mappings.
- `docs/02-swift-fundamentals/swift-toolkit-for-web-devs.md` — KeyPaths, property-wrapper authoring, result builders / `@ViewBuilder`, IUOs.
- `docs/09-deployment/app-store-operations.md` — privacy manifest, ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements, pre-submission checklist.

Phase E Tier 2 — BUILD-23/24/25 (2026-05-04):
- `docs/04-ui-development/uikit-guide.md` — view controllers + lifecycle, Auto Layout mental model, Storyboards/XIBs/programmatic tradeoffs, modern `UICollectionView` diffable data sources, navigation patterns, responder chain + gestures, bidirectional SwiftUI bridging (`UIHostingController` / `UIViewRepresentable`).
- `docs/02-swift-fundamentals/from-csharp.md` — type system, LINQ → sequence ops, async/await with cancellation contrast, properties/pattern-matching/generics, GC → ARC, "where it gets weird" (no `internal` across modules, no `protected`, trailing closures), MVVM port with `@Observable`/`@MainActor`, Xamarin/MAUI sunset migration plan.
- `docs/02-swift-fundamentals/from-dart-flutter.md` — type system (with sealed-class → enum collapse), widget → view tree, `StatefulWidget` → `@State`, layout idiom mapping, state-management mapping (Provider/Riverpod/BLoC → `@State`/`@Observable`/AsyncStream), `Future`/`Stream` → `async`/`AsyncSequence`, isolates → actors, `ChangeNotifier` real-world port, rebuild cost-model contrast.

Phase E Tier 3/4 — BUILD-27/28/30 (2026-05-04, Phase E complete):
- `docs/02-swift-fundamentals/cpp-interop.md` — Swift 5.9+ first-class C++ interop, `.interoperabilityMode(.Cxx)`, module map setup, `std::string`/`std::vector<T>` bridging, what works vs what's still rough (templates, exceptions are UB), Objective-C++ `.mm` shims with try/catch translation to NSError, vendored static libs vs SPM binary frameworks, ABI-breakage and `std::string_view` lifetime hazards, real-world C++ codec wrap.
- `docs/02-swift-fundamentals/rust-ffi.md` — full FFI surface (`extern "C"` + `#[no_mangle]` + `catch_unwind`), `cbindgen` header generation, Swift class wrapping with `deinit`, memory ownership rules, string bridging (`withCString` / `String(cString:)`), Result types (out-parameter + tagged struct), async patterns (Task.detached, `withCheckedContinuation` + `Unmanaged.passRetained` callbacks, polling), `uniffi-rs` and `cargo-swift` higher-level options, building `xcframework` with `cargo` + `xcodebuild -create-xcframework`, real-world parser package.
- `docs/02-swift-fundamentals/from-server-langs.md` — combined Go/Ruby/PHP chapter. Go: goroutines → `Task`, channels → `AsyncStream`, structural interfaces vs nominal protocols with PAT caveats, error returns → `throws`. Ruby: no `method_missing`, no monkey-patching across modules, mixins → protocol extensions, `&:method` → key-paths. PHP: no type-juggling, no superglobals, `array` splits into `Array<T>` + `Dictionary<K,V>`.

### Wrapper Command Surface

```
python -m wrapper convert <path>             # local only (Phase 1)
python -m wrapper convert-from-github <url>  # clone + convert + commit + push (Phases 2/3) + polish (Phase 4)
  --branch <name>       override ios-conversion default
  --app-name <name>     override derived app name (Tier 1 Step 6)
  --bundle-id <id>      reverse-DNS bundle id; defaults to placeholder (Tier 1 Step 8)
  --team-id <id>        10-char Apple developer team id; defaults to placeholder (Tier 1 Step 8)
  --source-subdir <dir> scope to monorepo subdirectory
  --no-validate         skip structural validation
  --yes                 skip confirmation prompt; implies --push
  --reuse-clone         skip re-cloning if workspace exists
  --push                push the conversion branch to origin (Phase 3)
  --no-push             commit locally only; do not push (Phase 3)
  --brief               suppress metadata banner + educational block (Phase 4)
  --open-pr             after push, invoke `gh pr create` to open the PR (Phase 5)
  --allow-unsupported   bypass compatibility-matrix gate (Tier 0 Step 2 dev override)
```

### MVP Tier 1 — Compliance & Project Generation (2026-05-05)

- `config/apple-entitlements.yaml` — 12-capability entitlement catalogue (key + label + patterns + `requires_developer_account` + usage strings). Drives Layer A vs Layer B routing.
- `config/compatibility-matrix.yaml` — Source × target matrix; only `web × wrap` is `supported: true` for MVP.
- `schemas/report.schema.json` — three-layer report JSON schema (Step 7.1). Validated by `converter/compliance/privacy_manifest._validate_against_schema` (nullable-type aware).
- `converter/compliance/privacy_scanner.py` — five required-reason API families (`UserDefaults` / `FileManager` / `SystemBoot` / disk-space / active-keyboard).
- `converter/compliance/privacy_manifest.py` — `PrivacyInfo.xcprivacy` generator + plist round-trip.
- `converter/compliance/entitlement_scanner.py` — JS-API + Capacitor-plugin pattern matcher; emits `EntitlementFinding` with capability, label, usage strings, `requires_developer_account` flag.
- `converter/reports/three_layer_emitter.py` — builds `ThreeLayerReport` from compliance + emitter findings; routes by severity.
- `converter/reports/renderers.py` — Markdown + JSON renderers; both files written to the output dir.
- `converter/xcode_project/emitter.py` — `XcodeSpec` + `emit_xcode_project()`; atomic per-file writes + re-parse validation; placeholder findings (bundle-id / team-id / app-icon / launch-screen / privacy-manifest).
- `converter/xcode_project/templates/` — `xcodegen.yml.tmpl`, `Info.plist.tmpl`, `AppDelegate.swift.tmpl`, `LaunchScreen.storyboard`, `Assets.xcassets/AppIcon.appiconset/{Contents.json,icon-1024.png}` (1024×1024 PNG built from stdlib `struct` + `zlib`, no third-party deps).
- `wrapper/compatibility.py` — loads matrix, `assert_supported()` gate (Tier 0 Step 2).
- `wrapper/compliance_step.py` — runs scanners + writes `PrivacyInfo.xcprivacy` (Tier 1 Step 6).
- `wrapper/xcode_step.py` — drives the emitter from the wrapper post-convert pipeline (Tier 1 Step 8.4).
- `wrapper/preflight.py` — MVP §6.2: `run_preflight()` + `PreflightResult` + `format_preflight_report()`; no file writes; exit code 0/1/2.
- `wrapper/__main__.py` — `convert`, `convert-from-github`, `preflight` subcommands; `_run_post_conversion_steps` writes `report.md` + `report.json`.

### CI

- `.github/workflows/test.yml` — first CI workflow.
  - **Linux job**: builds XcodeGen 2.39 from source (`swift build`), runs the converter + wrapper test suites, and validates a generated `project.yml` end-to-end.
  - **macOS job**: gated to `main` push events and the `macos-ci` PR label. Generates the project, then runs `xcodebuild -scheme App build CODE_SIGNING_ALLOWED=NO`.

### Tests

- Converter: `python3 -m unittest discover -t . -s converter` — 137 tests. (`-t .` keeps relative imports in `converter/__init__.py` modules resolvable.)
- Wrapper: `python3 -m unittest discover -s wrapper` — 123 tests (+27 preflight).
- Combined: 260 green.
- Notable Step 8 suites: `converter/xcode_project/tests/test_emitter.py` (spec validation, file emission, plist contents, placeholder findings), `converter/xcode_project/tests/test_templates.py` (template substitution + XML/JSON parse), `converter/compliance/tests/test_entitlement_scanner.py`, `wrapper/tests/test_xcode_integration.py`, `wrapper/tests/test_report_integration.py` (covers Step 8 via the renamed `_run_post_conversion_steps`).
- `wrapper/tests/test_preflight.py` — 27 tests; `mock.patch` stubs `scan_all`/`scan_all_entitlements` so no real filesystem scan.

### Wrapper modules

- `wrapper/__main__.py` — argparse + subcommand dispatch
- `wrapper/orchestrator.py` — runs the converter CLI as a subprocess; parses reports into `ConversionResult`
- `wrapper/triage.py` — top-N review-target summary
- `wrapper/git_ops.py` — clone / branch / commit / push (Phases 2/3); `CommitInfo` + `PushInfo`
- `wrapper/repo_metadata.py` — Phase 4: GitHub URL parser, REST `/repos/{owner}/{repo}` fetch, banner formatter; soft-fails on every error path
- `wrapper/post_flight.py` — Phase 4: `gh pr create` formatter + `compare/<base>...<head>?expand=1` URL fallback
- `wrapper/explainer.py` — Phase 4: educational "What's on this branch" block (two flavours, depending on `Requires-more-review/` prefix)
- `wrapper/preflight.py` — MVP §6.2: `run_preflight()` scans without converting; `PreflightResult` carries blockers/warnings/errors/exit_code; `format_preflight_report()` renders human output; `--brief` flag suppresses per-finding detail
- `wrapper/pr_ops.py` — Phase 5: `gh_available()` (detects `gh` + auth) and `open_pr()` (invokes `gh pr create`, 60s timeout, PR-URL regex extraction); hard-fail on missing/unauthenticated `gh`
- `wrapper/tests/test_preflight.py` — 27 tests; scanners mocked, no real I/O
- `wrapper/tests/test_repo_metadata.py` — 33 tests
- `wrapper/tests/test_post_flight.py` — 24 tests; covers `post_flight` and `explainer`
- `wrapper/tests/test_pr_ops.py` — 15 tests; `mock.patch` stubs `subprocess.run` and `shutil.which` so no real `gh` calls
- Run all wrapper tests (123 total): `python3 -m unittest discover -s wrapper`
