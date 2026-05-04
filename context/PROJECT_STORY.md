# Project Story

Last curated: 2026-05-04 (Phase E complete)

## Narrative

`ios-agent` started as a guidebook for web developers (containerized builds,
Vercel deployments) bringing their products to native iOS — then grew an
automated converter that takes their TypeScript/React code and produces a
buildable Swift/SwiftUI project.

The converter pipeline (analyze → review → rewrite → assemble → validate) was
built across four phases tracked as BUILD-1 through BUILD-15. By 2026-04-25
all 15 items had shipped and the converter could handle a small fixture
end-to-end. The remaining open question was: how does a real user actually
use this thing?

The answer, per the agent-interaction-design plan, is three surfaces:

1. The **CLI** — a one-shot pure function (TS dir → Swift project + reports).
2. A **conversational wrapper** — orchestrates the CLI, clones GitHub repos,
   manages branches, and surfaces a triage summary.
3. **Claude Code** — how the project is built and maintained day-to-day.

Phase 1 of the wrapper (local convert) and Phase 2 (clone + commit, no push)
shipped over 2026-04-30 → 2026-05-04. The first real-world test against
`jjdcodingcollective-collab/the-survival-bible` (a Next.js + React Native
monorepo) surfaced two issues that have since been fixed:

- The wrapper had no way to scope to a monorepo subdirectory; added
  `--source-subdir`.
- The rewriter leaked `=>` arrow-function syntax into Swift output for JSX
  prop callbacks (`style={({pressed}) => [...]}`, render-props,
  `.map((x) => (...))`). Three-point fix in `component_converter.py`
  (Text-content guard, JSX-expression dispatcher, post-processor) brought
  the survival-bible run from 5 validation errors to 0.

Phase 3 (push) is next. The eventual product vision is a paid hosted
service: "point us at your repo, get an iOS PR" — but only after the local
round-trip is rock-solid.

A second track opened on 2026-05-04: a focused review of the human-facing
`docs/` guide against the project's broader brief of "transposing popular
coding languages to Swift" found the docs were monolingual (JS/TS only),
missing an Objective-C interop chapter, and underweighting Swift's strict
concurrency model and ARC discipline. The review also caught a handful of
internal inconsistencies (sample code using `try!` / `as!` in chapters that
forbid them, and an `@ObservedObject ↔ useContext` mismap that misleads
React readers). These are now tracked as GAP-D1…D9 / BUILD-16…30 under a
new Phase E in the build guide, sequenced so correctness fixes ship before
any new source-language chapters. The converter scope is intentionally
unchanged — docs first, converter later, because docs are cheaper to
experiment with.

**Phase E shipped end-to-end on 2026-05-04** in seven commits. Tier 0
correctness fixes (BUILD-20) plus Tier 1 chapters on ObjC interop, strict
concurrency, ARC, generics, persistence, and Kotlin/Java/Python landed
first. BUILD-26 (deeper JS/TS) and BUILD-29 (App Store operations) followed.
The Tier 2/3/4 niche tail closed in three reviewable commits: BUILD-23
(UIKit), BUILD-24/25 (C#, Dart/Flutter), and BUILD-27/28/30 (C++ interop,
Rust FFI, Go/Ruby/PHP). The `docs/` guide now spans **JavaScript/TypeScript,
Kotlin, Java, Python, C#, Dart/Flutter, and Go/Ruby/PHP** as source
languages, plus operational depth on ObjC, C++, and Rust interop, UIKit
for non-greenfield codebases, and an App Store operations checklist.

With Phase E complete, the active roadmap narrows back to a single track:
**wrapper Phase 4 (conversational polish) and Phase 5 (`--open-pr` via
`gh pr create`)** — both build on the Phase 3 push plumbing already in
place. Brand alignment is now resolved in favour of the broad scope; the
README "Scope" section reflects the wider language coverage and the
remaining-backlog line was replaced with a "Phase E complete" callout.
