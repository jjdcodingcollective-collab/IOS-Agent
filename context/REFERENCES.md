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
  roadmap.
- `plans/github-round-trip.md` — design spec for the wrapper's GitHub round-trip
  (Phases 1–5). Phases 1 and 2 delivered.
- `plans/agent-interaction-design.md` — three-surface model (CLI / wrapper /
  Claude Code) and long-term product vision.
- `plans/ios-code-converter.md` — original converter design (historical).

### Reviews & external deliverables

- `plans/reviews/2026-05-04-language-transposition.md` — 2026-05-04 review
  of `docs/` against the "transposing popular coding languages to Swift"
  brief. Source for GAP-D1…D9 and BUILD-16…30. (A copy also lives at
  `/storage/outputs/ios-agent/Language-Transposition-Gap-Analysis.md` for
  the user's Files panel; the in-repo copy is canonical.)

### Wrapper Command Surface

```
python -m wrapper convert <path>             # local only (Phase 1)
python -m wrapper convert-from-github <url>  # clone + convert + commit (Phase 2)
  --branch <name>       override ios-conversion default
  --app-name <name>     override derived app name
  --source-subdir <dir> scope to monorepo subdirectory
  --no-validate         skip structural validation
  --yes                 skip confirmation prompt
  --reuse-clone         skip re-cloning if workspace exists
```
