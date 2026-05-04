# Decisions

Last curated: 2026-05-04

## Active Decisions

### Wrapper / GitHub round-trip

- **Same-repo branch, not fork.** The wrapper creates an `ios-conversion`
  branch in the user's repo. Forks add UX overhead and break the "drop into
  your repo" demo.
- **Wrapper-only feature, not part of the CLI.** The CLI must stay a pure
  function (TS source → Swift project) so it stays testable and CI-friendly.
  Anything stateful (git, network, GitHub API) lives in `wrapper/`.
- **Branch named `ios-conversion` by default; user can rename.** Validated
  with `git check-ref-format`; protected branches (`main`/`master`/`develop`/
  `trunk`/`release`) refused outright.
- **Re-runs are fresh commits with `rev N`, never amend or force-push.**
  The revision counter scans `git log` for `^ios:\s*auto-conversion rev (\d+)`.
- **Validation-failing runs push anyway, but to a `Requires-more-review/`
  prefixed branch.** Trigger: any validation error, or average confidence
  below 60%. Prefix is hyphenated (slashes-with-spaces aren't valid git refs).
- **Bot identity for auto-conversion commits**: `ios-agent <ios-agent@localhost>`,
  scoped to the clone via `git config` (no global writes). Auto-commits must
  never pose as the human user.
- **Phase 2 ships without `git push`.** Push is a Phase 3 problem; verifying
  branch contents locally first is cheap insurance.

### Converter pipeline

- **Regex-based parsing is acceptable** for the converter's structural
  layer. BUILD-1 added lightweight AST support where regex was failing,
  but the architecture stays "regex-first, AST when forced."
- **Generated reports are first-class output.** The wrapper reads them
  off disk to drive its triage and commit-message logic — never re-runs
  the CLI to introspect state.
- **Confidence < 60% triggers `Requires-more-review/` even with zero
  validation errors.** Compiling-but-mostly-stub Swift is worse than
  obviously-broken Swift; the prefix forces human review.

### Layout in the conversion branch

- Swift project files (`Package.swift`, `project.yml`, `Sources/`, `Tests/`)
  go at the repo root.
- All converter reports go to `.ios-conversion/` so reviewers see the TS
  vs Swift diff side-by-side at the top level.
- Original TypeScript source is untouched — only the listed paths are ever
  modified by the wrapper.

### Documentation scope and sequencing (added 2026-05-04)

- **Docs first, converter scope second.** Expanding the `docs/` guide to
  cover new source languages (Kotlin, Java, Python, etc.) does not require
  expanding the converter. The docs are the cheaper experiment and signal
  audience demand before any converter investment.
- **Tier 0 docs fixes ship before Tier 1 new content.** BUILD-20 (mechanical
  inconsistency fixes), BUILD-17 (strict concurrency / Sendable), and
  BUILD-19 (ARC depth) are sequenced before BUILD-16 (ObjC interop),
  BUILD-18 (generics/opaque/existentials), BUILD-21 (Kotlin → Java →
  Python source-language chapters), and BUILD-22 (persistence). Reason:
  fixing a chapter that contradicts its own samples is corrective; adding
  a new chapter on top of contradictory samples just spreads the problem.
- **Per-language template is locked in before the second source-language
  chapter is written.** Without it, new chapters drift in depth like the
  existing ones do. Template fields: variables/types, null model, error
  model, value-vs-reference, concurrency model, generics & polymorphism,
  memory model, module/visibility, testing idioms, "5 most surprising
  things."
- **Tier 1 source-language order: Kotlin → Java → Python.** Kotlin is the
  near-twin language (highest leverage per page); Java is the largest
  enterprise audience; Python is the largest data/ML audience. C# / Dart /
  C++ / Rust deferred to Tier 2/3 backlog.
