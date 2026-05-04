# Active Context

Last curated: 2026-05-04 (revised — BUILD-23/24/25 shipped: UIKit, C#, Dart/Flutter)

## Current State

The converter pipeline (analyze → review → rewrite → assemble → validate) is
fully shipped. All 15 original BUILD-* items from the 2026-04-25 gap analysis
are done.

The **wrapper** (`python -m wrapper`) layer that orchestrates the CLI, clones
GitHub repos, and creates a conversion branch is operational through Phase 3:

- Phase 1 — local convert: ✅
- Phase 2 — clone + convert + local commit on a `Requires-more-review/` branch: ✅
- Phase 3 — opt-in push to origin via `--push` / `--no-push` (default prompts): ✅
- Phase 4 — conversational polish: ⏳ next
- Phase 5 — `--open-pr` via `gh pr create`: ⏳ later

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

Source review: `plans/reviews/2026-05-04-language-transposition.md`.

## What's Next

Two tracks remain:

**Wrapper Phase 4/5.** Phase 4 is the conversational polish layer
(pre-flight repo metadata via the GitHub API, post-flight PR-ready
next steps, educational mode for first-time users). Phase 5 wires
`--open-pr` via `gh pr create`, off by default. Both build on the
Phase 3 push plumbing already in place.

**Phase E remaining Tier 2/3/4 backlog:** BUILD-27 (C++ interop),
BUILD-28 (Rust FFI), BUILD-30 (Go/Ruby/PHP). BUILD-23/24/25 shipped
2026-05-04 (UIKit, C#, Dart/Flutter). The final batch (BUILD-27 + 28 +
30) is the niche-tail commit per `plans/phase-e-tier-2-3-remaining.md`.

## Relevant Knowledge Refs

- `plans/gap-analysis-and-build-guide.md` — capability matrix and roadmap (all 15 BUILD items marked complete)
- `plans/github-round-trip.md` — wrapper design + delivered command surface
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper / Claude Code)
- `wrapper/git_ops.py` — clone, branch, commit, revision counter, update notes
- `wrapper/orchestrator.py` — runs CLI as subprocess, parses reports into `ConversionResult`
- `wrapper/triage.py` — renders user-facing triage summary (top-N review targets)
- `wrapper/__main__.py` — `python -m wrapper convert` and `convert-from-github` subcommands
- `converter/rewriter/component_converter.py` — JSX→SwiftUI translator (arrow-leak 3-point fix)
- `converter/validator/swift_checker.py` — pattern lint + optional swiftc -parse

## Git Identity (this repo)

Local config: `jjdcodingcollective <jjd.codingcollective@gmail.com>` (scoped, no global write).
Auto-conversion commits on `Requires-more-review/` branches use `ios-agent <ios-agent@localhost>`.
