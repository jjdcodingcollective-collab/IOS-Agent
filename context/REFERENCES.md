# References

Last curated: 2026-05-04

## Sources

### Test Repositories

- **jjdcodingcollective-collab/the-survival-bible** — Real-world monorepo used
  for end-to-end smoke testing. Contains `apps/web` (Next.js), `apps/mobile`
  (React Native), and 4 shared packages. The `apps/mobile` subdir (42 files)
  is the canonical test target for the iOS converter. First run surfaced the
  arrow-function leak; second run (with `--source-subdir apps/mobile`) achieved
  50/50 validation pass.

### Key Plans

- `plans/gap-analysis-and-build-guide.md` — capability matrix and full
  remediation plan. **All 15 original BUILD items complete.** Revised
  2026-05-04 to add dimension 6 (Documentation & Source-Language Coverage),
  GAP-D1…D9, BUILD-16…22, Tier 2/3/4 backlog (BUILD-23…30), and Phase E
  roadmap. **Phase E Tier 0 + Tier 1 (BUILD-16…22) shipped 2026-05-04.**
  **BUILD-26 + BUILD-29 also shipped 2026-05-04** out of the Tier 2/3 backlog.
- `plans/github-round-trip.md` — design spec for the wrapper's GitHub round-trip
  (Phases 1–5). Phases 1, 2, and 3 delivered. Phase 3 added `--push`/`--no-push`
  on `convert-from-github`, `push_branch()` + `PushInfo` in `wrapper/git_ops.py`,
  protected-branch refusal at push time, and a read-only fallback when
  credentials are missing.
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper /
  Claude Code) and long-term product vision.
- `plans/ios-code-converter.md` — original converter design (historical).

### Reviews & external deliverables

- `plans/reviews/2026-05-04-language-transposition.md` — 2026-05-04 review
  of `docs/` against the "transposing popular coding languages to Swift"
  brief. Source for GAP-D1…D9 and BUILD-16…30. (A copy also lives at
  `/storage/outputs/ios-agent/Language-Transposition-Gap-Analysis.md` for
  the user's Files panel; the in-repo copy is canonical.)

### Documentation Chapters (Phase E)

Phase E Tier 0 + Tier 1 (2026-05-04, BUILD-16…22):
- `docs/02-swift-fundamentals/concurrency-and-sendable.md` — strict concurrency, actors, `@MainActor`, `Sendable`.
- `docs/02-swift-fundamentals/arc-and-lifetimes.md` — ARC, retain cycles, `weak`/`unowned`, capture lists, `Task` retention.
- `docs/02-swift-fundamentals/swift-objc-interop.md` — `@objc`, bridging, `#selector`, KVO, NSError, framework header reading.
- `docs/02-swift-fundamentals/generics-and-protocols-deep.md` — generics, `some` (opaque) vs `any` (existential), PATs, type erasure.
- `docs/02-swift-fundamentals/from-kotlin.md` — Kotlin → Swift transposition.
- `docs/02-swift-fundamentals/from-java.md` — Java → Swift transposition.
- `docs/02-swift-fundamentals/from-python.md` — Python → Swift transposition.
- `docs/03-architecture/persistence.md` — UserDefaults / Keychain / FileManager / SwiftData / Core Data / CloudKit; ORM mappings (Prisma / Drizzle / ActiveRecord / SQLAlchemy / Hibernate / Room).

Phase E Tier 2/3 partial (2026-05-04, BUILD-26 + BUILD-29):
- `docs/02-swift-fundamentals/combine-and-async-streams.md` — Combine for RxJS readers, AsyncSequence, `@Published`/`AnyCancellable`/`AnyPublisher`, `Observable` macro decision table.
- `docs/02-swift-fundamentals/codable-deep.md` — CodingKeys, dates, polymorphism, lossy arrays, property-wrapper-based decoders, JSON-library mappings.
- `docs/02-swift-fundamentals/swift-toolkit-for-web-devs.md` — KeyPaths, property-wrapper authoring, result builders / `@ViewBuilder`, IUOs.
- `docs/09-deployment/app-store-operations.md` — privacy manifest, ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements, pre-submission checklist.

### Wrapper Command Surface

```
python -m wrapper convert <path>             # local only (Phase 1)
python -m wrapper convert-from-github <url>  # clone + convert + commit + push (Phases 2/3)
  --branch <name>       override ios-conversion default
  --app-name <name>     override derived app name
  --source-subdir <dir> scope to monorepo subdirectory
  --no-validate         skip structural validation
  --yes                 skip confirmation prompt; implies --push
  --reuse-clone         skip re-cloning if workspace exists
  --push                push the conversion branch to origin (Phase 3)
  --no-push             commit locally only; do not push (Phase 3)
```
