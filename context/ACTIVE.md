# Active Context

Last curated: 2026-05-04

## Current State

The converter pipeline (analyze → review → rewrite → assemble → validate) is
fully shipped. All 15 BUILD-* items from the original gap analysis are done.

The **wrapper** (`python -m wrapper`) layer that orchestrates the CLI, clones
GitHub repos, and creates a conversion branch is operational through Phase 2:

- Phase 1 — local convert: ✅
- Phase 2 — clone + convert + local commit on a `Requires-more-review/` branch: ✅
- Phase 3 — push to GitHub: ⏳ next

Real-world validation passed against `the-survival-bible` monorepo
(`apps/mobile`, 42 files, 50/50 structural-validation pass after fixing the
arrow-function leak in `component_converter.py`).

## What I'm working on right now

Updating documentation across `plans/`, `context/`, and `README.md` to reflect
shipped state, then pushing the accumulated work to GitHub. After that:
**Phase 3 — push from the wrapper**.

## Relevant Knowledge Refs

- `plans/gap-analysis-and-build-guide.md` — capability matrix and roadmap
- `plans/github-round-trip.md` — wrapper design + delivered command surface
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper / Claude Code)
- `wrapper/git_ops.py` — clone, branch, commit, revision counter, update notes
- `converter/rewriter/component_converter.py` — JSX→SwiftUI translator (arrow-leak fix lives here)
- `converter/validator/swift_checker.py` — pattern lint + optional swiftc -parse
