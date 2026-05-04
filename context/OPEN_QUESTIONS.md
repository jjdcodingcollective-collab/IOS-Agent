# Open Questions

The chat agent should inspect this file when Project Knowledge is enabled, then surface questions only when they materially affect the current task.

## Active

- **Converter source-language expansion.** Phase E shipped seven source-language chapters (Kotlin, Java, Python, C#, Dart/Flutter, Go/Ruby/PHP) in `docs/`, plus three interop chapters (ObjC, C++, Rust). The converter remains TypeScript-only. Does the converter follow (Kotlin → Swift, Java → Swift converters), and on what timeline? Currently un-scoped — defer until wrapper Phase 4/5 ship and we have real-user signal on which source language to add second. Recorded 2026-05-04, status unchanged after Phase E completion.

## Resolved

- **Brand alignment** *(resolved 2026-05-04 by Phase E completion)* — Option (a) won by execution: Phase E shipped end-to-end and the README "Scope" section now lists JS/TS + Kotlin + Java + Python + C# + Dart/Flutter + Go/Ruby/PHP. The broad-brand framing is the steady state.
- **Per-language template authoring** *(resolved 2026-05-04 by use)* — The template established in BUILD-21 (Kotlin/Java/Python) was applied unchanged to BUILD-24 (C#), BUILD-25 (Dart/Flutter), and BUILD-30 (Go/Ruby/PHP) without modification. Locked-in form: `from-{lang}.md` with sections for type-system mapping, idiom translation, concurrency, memory model, "where it gets weird", real-world port, and cross-links. Authored and owned by the project maintainer; future chapters follow the same shape.
