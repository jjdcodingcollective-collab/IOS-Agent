# References

Last curated: 2026-05-04 (Wrapper Phase 5 shipped — `--open-pr`; wrapper roadmap complete)

## Sources

### Test Repositories

- **jjdcodingcollective-collab/the-survival-bible** — Real-world monorepo used
  for end-to-end smoke testing. Contains `apps/web` (Next.js), `apps/mobile`
  (React Native), and 4 shared packages. The `apps/mobile` subdir (42 files)
  is the canonical test target for the iOS converter. First run surfaced the
  arrow-function leak; second run (with `--source-subdir apps/mobile`) achieved
  50/50 validation pass.

### Key Plans

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
  --app-name <name>     override derived app name
  --source-subdir <dir> scope to monorepo subdirectory
  --no-validate         skip structural validation
  --yes                 skip confirmation prompt; implies --push
  --reuse-clone         skip re-cloning if workspace exists
  --push                push the conversion branch to origin (Phase 3)
  --no-push             commit locally only; do not push (Phase 3)
  --brief               suppress metadata banner + educational block (Phase 4)
  --open-pr             after push, invoke `gh pr create` to open the PR (Phase 5)
```

### Wrapper modules

- `wrapper/__main__.py` — argparse + subcommand dispatch
- `wrapper/orchestrator.py` — runs the converter CLI as a subprocess; parses reports into `ConversionResult`
- `wrapper/triage.py` — top-N review-target summary
- `wrapper/git_ops.py` — clone / branch / commit / push (Phases 2/3); `CommitInfo` + `PushInfo`
- `wrapper/repo_metadata.py` — Phase 4: GitHub URL parser, REST `/repos/{owner}/{repo}` fetch, banner formatter; soft-fails on every error path
- `wrapper/post_flight.py` — Phase 4: `gh pr create` formatter + `compare/<base>...<head>?expand=1` URL fallback
- `wrapper/explainer.py` — Phase 4: educational "What's on this branch" block (two flavours, depending on `Requires-more-review/` prefix)
- `wrapper/pr_ops.py` — Phase 5: `gh_available()` (detects `gh` + auth) and `open_pr()` (invokes `gh pr create`, 60s timeout, PR-URL regex extraction); hard-fail on missing/unauthenticated `gh`
- `wrapper/tests/test_repo_metadata.py` — 33 tests
- `wrapper/tests/test_post_flight.py` — 24 tests; covers `post_flight` and `explainer`
- `wrapper/tests/test_pr_ops.py` — 15 tests; `mock.patch` stubs `subprocess.run` and `shutil.which` so no real `gh` calls
- Run all wrapper tests (72 total): `python3 -m unittest discover -s wrapper`
