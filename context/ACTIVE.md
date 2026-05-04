# Active Context

Last curated: 2026-05-04 (revised — Phase E Tier 0 + Tier 1 shipped)

## Current State

The converter pipeline (analyze → review → rewrite → assemble → validate) is
fully shipped. All 15 original BUILD-* items from the 2026-04-25 gap analysis
are done.

The **wrapper** (`python -m wrapper`) layer that orchestrates the CLI, clones
GitHub repos, and creates a conversion branch is operational through Phase 2:

- Phase 1 — local convert: ✅
- Phase 2 — clone + convert + local commit on a `Requires-more-review/` branch: ✅
- Phase 3 — push to GitHub: ⏳ next

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

**Phase E Tier 0 + Tier 1 are now shipped (2026-05-04).** Eight files of
changes:

- ✅ BUILD-20 — Tier 0 correctness fixes in `docs/11-pitfalls/web-dev-gotchas.md`,
  `docs/05-networking/api-integration.md`, `docs/02-swift-fundamentals/swift-for-web-devs.md`.
- ✅ BUILD-17 — `docs/02-swift-fundamentals/concurrency-and-sendable.md` (new).
- ✅ BUILD-19 — `docs/02-swift-fundamentals/arc-and-lifetimes.md` (new).
- ✅ BUILD-16 — `docs/02-swift-fundamentals/swift-objc-interop.md` (new).
- ✅ BUILD-18 — `docs/02-swift-fundamentals/generics-and-protocols-deep.md` (new).
- ✅ BUILD-21 — `from-kotlin.md`, `from-java.md`, `from-python.md` (new, all under `docs/02-swift-fundamentals/`).
- ✅ BUILD-22 — `docs/03-architecture/persistence.md` (new).

Source review: `plans/reviews/2026-05-04-language-transposition.md`.

## What's Next

Two tracks remain:

**Wrapper Phase 3 — push branch from the wrapper.** The `convert-from-github`
command currently clones, converts, and commits locally but does not push.
Phase 3 wires `git push origin <branch>` and optionally `gh pr create` inside
`wrapper/git_ops.py`.

**Phase E Tier 2/3/4 backlog** — BUILD-23…30 are enumerated but not yet specced
in detail. Highest-value among them: BUILD-23 (UIKit chapter), BUILD-26 (deepen
JS/TS chapter — Combine, Codable customization, KeyPath, property wrappers),
BUILD-29 (privacy manifest / ATT / BGTaskScheduler operational chapter).

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
