# Open Questions

The chat agent should inspect this file when Project Knowledge is enabled, then surface questions only when they materially affect the current task.

## Active

- **Converter source-language expansion.** Phase E shipped seven source-language chapters (Kotlin, Java, Python, C#, Dart/Flutter, Go/Ruby/PHP) in `docs/`, plus three interop chapters (ObjC, C++, Rust). The converter remains TypeScript-only. Does the converter follow (Kotlin → Swift, Java → Swift converters), and on what timeline? Explicitly **out of scope for MVP** per `docs/mvp-scope.md` §2 (Java/Kotlin → Phase 2; Python → Phase 5). The MVP-tier-0-tier-1 plan reaffirmed this 2026-05-05. The question now is whether real-user signal post-MVP-launch justifies starting Phase 2 with Kotlin (near-twin language, smallest converter delta) or Java (largest enterprise audience). Recorded 2026-05-04; deferred again 2026-05-05 after Tier 1 closure; no new signal in 2026-05-09 review session.

## Resolved

- **Brand alignment** *(resolved 2026-05-04 by Phase E completion)* — Option (a) won by execution: Phase E shipped end-to-end and the README "Scope" section now lists JS/TS + Kotlin + Java + Python + C# + Dart/Flutter + Go/Ruby/PHP. The broad-brand framing is the steady state.
- **Per-language template authoring** *(resolved 2026-05-04 by use)* — The template established in BUILD-21 (Kotlin/Java/Python) was applied unchanged to BUILD-24 (C#), BUILD-25 (Dart/Flutter), and BUILD-30 (Go/Ruby/PHP) without modification. Locked-in form: `from-{lang}.md` with sections for type-system mapping, idiom translation, concurrency, memory model, "where it gets weird", real-world port, and cross-links. Authored and owned by the project maintainer; future chapters follow the same shape.

## Suggested status changes (curator-flagged, awaiting user confirmation)

*(No status changes surfaced from the 2026-05-09 review/verification session. The session confirmed all prior work is complete and pushed; no new task completions, conflict resolutions, or question answers were implied.)*
