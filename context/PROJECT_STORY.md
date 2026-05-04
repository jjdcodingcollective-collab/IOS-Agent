# Project Story

Last curated: 2026-05-04

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
