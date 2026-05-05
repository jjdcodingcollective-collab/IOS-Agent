# Decisions

Last curated: 2026-05-05 (added MVP Tier 1 decisions: XcodeGen-not-Tuist; placeholder-as-blocker; stdlib-only template assets)

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

### MVP Tier 1 — Compliance & Project Generation (added 2026-05-05)

- **XcodeGen, not Tuist, for project generation.** Captured in
  `plans/mvp-tier-0-tier-1.md` (Step 8) and reaffirmed during Step 8.3
  implementation. XcodeGen's YAML spec is a flatter contract than Tuist's
  Swift DSL, easier to validate in a Linux CI without a Swift toolchain on
  the critical path, and the wrapper only needs *generation*, not Tuist's
  workspace/dependency-graph features. Tuist deferred until a real product
  need surfaces.
- **Placeholders are Layer A blockers, not soft warnings.** When the
  emitter has to fill in a bundle id, team id, app icon, launch screen,
  or privacy manifest, it emits a `xcode.placeholder.*` finding with
  severity `blocker`. Reason: a developer who skims the report and
  ships anyway must hit the App Review wall, not the user. The wrapper's
  triage block surfaces these by category.
- **Apple-Developer-Account-required entitlements gate the build (Layer A);
  permission-prompted capabilities are Layer B manual review.** This split
  is encoded in `config/apple-entitlements.yaml` via the
  `requires_developer_account` field. Push, App Groups, iCloud, etc., land
  in Layer A; Camera, Location, Microphone, etc., land in Layer B. The
  emitter generates the entitlements plist + Info.plist usage strings
  regardless; the *reporting* is what changes.
- **Atomic per-file writes + re-parse validation in the emitter.** Every
  generated artefact (plists, YAML, storyboards, JSON, PNG) is written to
  a temp path under the output dir and `os.replace`-d into place; the
  emitter then re-parses the file with the matching stdlib parser
  (`plistlib`, `xml.etree`, `json`, naive YAML loader). Reason: a
  half-written project tree is worse than a missing one, and a syntactically
  invalid plist surfaces as an opaque Xcode error two steps later.
- **Stdlib-only template assets — no Pillow, no third-party PNG libs.**
  The 1024×1024 app-icon placeholder is generated by writing a PNG by hand
  with `struct` + `zlib`. Reason: the converter must be installable from
  a single `python3` checkout with no compiled wheels — adding a Pillow
  dependency for one placeholder PNG would inflate the dep graph, complicate
  CI cache, and break the offline-install story.
- **CI is two jobs: Linux for spec validation, macOS for actual `xcodebuild`.**
  Linux builds XcodeGen 2.39 from source (cached) and validates that the
  generated `project.yml` produces a parseable Xcode project. macOS is
  gated (push to `main`, or PRs labelled `macos-ci`) and runs
  `xcodebuild -scheme App build CODE_SIGNING_ALLOWED=NO`. Reason: macOS
  minutes are 10× Linux minutes on GitHub Actions; running macOS on every
  PR wastes the budget on changes that can't possibly affect the build.
- **The wrapper's post-convert pipeline is one helper, not two.**
  `_run_compliance_with_report` was renamed to `_run_post_conversion_steps`
  during Step 8 and now drives privacy scanner → entitlement scanner →
  emitter → report builder → renderers in order. Reason: every
  subsequent BLOCKING item (Sign-in-with-Apple stub, ATS config,
  pre-flight scanner) plugs into the same pipeline and benefits from
  the shared input fixtures, output dir, and report builder.
