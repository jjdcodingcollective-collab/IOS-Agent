# Active Context

Last curated: 2026-05-04 (revised — added Phase E docs work)

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
gaps (GAP-D1…D9) — most importantly: source-language scope is JS/TS only, no
Objective-C interop, strict-concurrency/Sendable underweighted, ARC depth
underweighted, and a few internal inconsistencies (`try!`/`as!` in samples,
`@ObservedObject ↔ useContext` mismap). These are now tracked as BUILD-16…22
plus a Tier 2/3/4 backlog (BUILD-23…30) in `plans/gap-analysis-and-build-guide.md`,
under a new **Phase E — Documentation Depth & Source-Language Coverage**.
Source review: `plans/reviews/2026-05-04-language-transposition.md`.

## What's Next

Two parallel tracks:

**Wrapper Phase 3 — push branch from the wrapper.** The `convert-from-github`
command currently clones, converts, and commits locally but does not push.
Phase 3 wires `git push origin <branch>` and optionally `gh pr create` inside
`wrapper/git_ops.py`.

**Phase E — Tier 0 docs correctness fixes** (sequenced before any new language
chapters):
- BUILD-20 (mechanical): fix `try!`/`as!` in pitfalls #3 + api-integration
  samples; correct `@ObservedObject ↔ useContext` mapping; add IUO callout.
- BUILD-17: strict-concurrency / Sendable / actor-isolation chapter.
- BUILD-19: ARC, capture, lifetime chapter (expanded from pitfalls #6).

Tier 1 follows: BUILD-16 (Objective-C interop), BUILD-18 (generics/opaque/
existentials), BUILD-21 (Kotlin → Java → Python source-language chapters),
BUILD-22 (persistence mapped from ORMs).

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
