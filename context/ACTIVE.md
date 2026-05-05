# Active Context

Last curated: 2026-05-04 (revised — Wrapper Phase 5 shipped: `--open-pr`; wrapper roadmap complete)

## Current State

The converter pipeline (analyze → review → rewrite → assemble → validate) is
fully shipped. All 15 original BUILD-* items from the 2026-04-25 gap analysis
are done.

The **wrapper** (`python -m wrapper`) layer that orchestrates the CLI, clones
GitHub repos, and creates a conversion branch is operational through Phase 3:

- Phase 1 — local convert: ✅
- Phase 2 — clone + convert + local commit on a `Requires-more-review/` branch: ✅
- Phase 3 — opt-in push to origin via `--push` / `--no-push` (default prompts): ✅
- Phase 4 — conversational polish (pre-flight metadata banner, post-flight `gh pr create` + compare-URL fallback, educational "What's on this branch" block, `--brief` flag): ✅
- Phase 5 — `--open-pr` via `gh pr create` (off by default, refuses `--no-push --open-pr`): ✅

Real-world validation passed against `the-survival-bible` monorepo
(`apps/mobile`, 42 files, **50/50 structural-validation pass**) after fixing
the arrow-function leak in `component_converter.py`.

All docs, plans, and code were committed as `168f7a1` and pushed to
`origin/main` on 2026-05-04.

A **2026-05-04 documentation review** of `docs/` against the project's stated
ambition of "transposing popular coding languages to Swift" surfaced 9 new
gaps (GAP-D1…D9) — most importantly: source-language scope was JS/TS only, no
Objective-C interop, strict-concurrency/Sendable underweighted, ARC depth
underweighted, and a few internal inconsistencies (`try!`/`as!` in samples,
`@ObservedObject ↔ useContext` mismap). These were tracked as BUILD-16…22
plus a Tier 2/3/4 backlog (BUILD-23…30) in `plans/gap-analysis-and-build-guide.md`,
under **Phase E — Documentation Depth & Source-Language Coverage**.

**Phase E Tier 0 + Tier 1 shipped 2026-05-04** (BUILD-16…22, eight files):
correctness fixes plus seven new chapters covering concurrency/Sendable, ARC,
ObjC interop, generics, persistence, and Kotlin/Java/Python source-language
transpositions.

**Tier 2/3 partial — BUILD-26 + BUILD-29 shipped 2026-05-04** (four files):

- ✅ BUILD-26 — Deepened JS/TS as three companion chapters:
  - `docs/02-swift-fundamentals/combine-and-async-streams.md` (Combine for RxJS
    devs, AsyncSequence, `@Published`/`AnyCancellable`, `Observable` macro).
  - `docs/02-swift-fundamentals/codable-deep.md` (CodingKeys, dates,
    polymorphism, lossy arrays, property-wrapper-based decoders).
  - `docs/02-swift-fundamentals/swift-toolkit-for-web-devs.md` (KeyPaths,
    property-wrapper authoring, result builders / `@ViewBuilder`, IUOs).
  - The intro `swift-for-web-devs.md` got a "Going Deeper" pointer block.
- ✅ BUILD-29 — `docs/09-deployment/app-store-operations.md` (privacy manifest,
  ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements,
  pre-submission checklist). Cross-linked from `security-guide.md` and
  `deployment-guide.md`.

**Tier 2/3/4 niche tail — BUILD-27 + BUILD-28 + BUILD-30 shipped 2026-05-04** (three files):

- ✅ BUILD-27 — `docs/02-swift-fundamentals/cpp-interop.md` (Swift 5.9+
  first-class C++ interop, `.interoperabilityMode(.Cxx)`, module map setup,
  `std::string`/`std::vector` bridging, Objective-C++ `.mm` shims for
  exception translation, vendored static libs vs SPM binary frameworks,
  ABI-breakage and `std::string_view` lifetime hazards).
- ✅ BUILD-28 — `docs/02-swift-fundamentals/rust-ffi.md` (`extern "C"` +
  `#[no_mangle]` + `catch_unwind`, `cbindgen` header generation,
  `Box::into_raw`/`Box::from_raw` ownership patterns, string-bridging via
  `withCString` and `String(cString:)`, async strategies, `uniffi-rs` and
  `cargo-swift` higher-level options, `xcframework` packaging).
- ✅ BUILD-30 — `docs/02-swift-fundamentals/from-server-langs.md` (combined
  Go/Ruby/PHP chapter — goroutines/channels → `Task`/`AsyncStream`, Go
  interfaces vs Swift protocols with PAT caveats, no `method_missing` and
  no monkey-patching for Ruby refugees, no type-juggling and no superglobals
  for PHP refugees).

**Phase E is now complete.** All Tier 2/3/4 chapters
(BUILD-23/24/25/27/28/30) shipped 2026-05-04.

Source review: `plans/reviews/2026-05-04-language-transposition.md`.

## What's Next

**The wrapper roadmap is complete.** Phase 5 shipped 2026-05-04: new
`wrapper/pr_ops.py` (gh detection + `open_pr()` invoking `gh pr create`
with a 60s timeout and PR-URL regex extraction); `--open-pr` flag on
`convert-from-github` (off by default, gated on a successful push,
refuses `--no-push --open-pr` at the argparse layer); existing-PR
collisions surface gh's own stderr; read-only fallback preserved
exactly. 15 new tests using `mock.patch` for `subprocess.run` and
`shutil.which` (no real gh calls); 72 wrapper tests total.

Forward options the user may pick up next: (1) end-to-end smoke run
through Phase 4 + Phase 5 against a real test repo to validate the
banner/explainer/PR command in production output; (2) the
still-open documentation question on converter source-language
expansion (see `context/OPEN_QUESTIONS.md`); (3) any new track the
user proposes — there is no auto-queued next phase.

## Relevant Knowledge Refs

- `plans/gap-analysis-and-build-guide.md` — capability matrix and roadmap (all 15 BUILD items marked complete)
- `plans/github-round-trip.md` — wrapper design + delivered command surface
- `plans/wrapper-phase-4-conversational-polish.md` — Phase 4 sub-plan (shipped 2026-05-04)
- `plans/wrapper-phase-5-open-pr.md` — Phase 5 sub-plan (shipped 2026-05-04)
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper / Claude Code)
- `wrapper/git_ops.py` — clone, branch, commit, revision counter, update notes, push
- `wrapper/orchestrator.py` — runs CLI as subprocess, parses reports into `ConversionResult`
- `wrapper/triage.py` — renders user-facing triage summary (top-N review targets)
- `wrapper/repo_metadata.py` — Phase 4: GitHub URL parser + repo-metadata fetch + banner formatter
- `wrapper/post_flight.py` — Phase 4: `gh pr create` formatter + compare-URL fallback
- `wrapper/explainer.py` — Phase 4: educational "What's on this branch" block
- `wrapper/pr_ops.py` — Phase 5: `gh_available()` + `open_pr()` (invokes `gh pr create`, extracts PR URL)
- `wrapper/__main__.py` — `python -m wrapper convert` and `convert-from-github` subcommands (with `--brief`, `--open-pr`)
- `wrapper/tests/` — `test_repo_metadata.py` (33) + `test_post_flight.py` (24) + `test_pr_ops.py` (15); 72 total. Run with `python3 -m unittest discover -s wrapper`
- `converter/rewriter/component_converter.py` — JSX→SwiftUI translator (arrow-leak 3-point fix)
- `converter/validator/swift_checker.py` — pattern lint + optional swiftc -parse

## Git Identity (this repo)

Local config: `jjdcodingcollective <jjd.codingcollective@gmail.com>` (scoped, no global write).
Auto-conversion commits on `Requires-more-review/` branches use `ios-agent <ios-agent@localhost>`.
