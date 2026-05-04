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
