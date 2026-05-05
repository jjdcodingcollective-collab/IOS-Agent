# Plan: Tier 1 Step 7 — Three-Layer Report Schema + Emitter

**Parent plan:** `plans/mvp-tier-0-tier-1.md` (Step 7)
**Source:** `MVP-Gap-Analysis.md` §7.1, §7.2, §7.3
**Status:** ✅ Complete — all six sub-steps shipped 2026-05-05. 62 new tests; 197 tests total green.
**Owner:** Tech lead (this conversation)
**Created:** 2026-05-05

---

## Summary

Define the canonical structure every conversion finding flows through, ship the emitter library every compliance and translation module will use, and render two outputs (Markdown for humans, JSON for CI). This step does not introduce new finding sources — the only producer right now is the Step 6 scanner. The point of doing it before Step 8 is that retrofitting an emitter contract across many producers is far more painful than authoring one producer (Step 6) against a settled schema.

Step 7 also closes gap §7.2 (learnings summary) by carving Layer C inside the same schema, and lays the groundwork for §7.3 (pre-flight scanner) — the pre-flight is a *consumer* of Layer-A findings; it gets built in the next plan, not this one. The sub-plan keeps §7.3 explicitly out of scope to avoid the same "scope creep into the next thing" pattern that Step 6 narrowly avoided.

The scanner from Step 6 currently surfaces findings as a `list[APIFinding]` and prints a one-line summary. After Step 7 lands, the scanner will instead emit `Finding` records into a `Report` object that the wrapper CLI renders to `report.md` + `report.json` in the conversion output dir.

---

## Architectural choices

### Schema as data, validator in stdlib

Same posture as Step 6: the schema lives at `schemas/report.schema.json`, a JSON Schema document. The validator reuses the bounded in-house validator from `converter/compliance/privacy_manifest.py` (no `jsonschema` dep). If the report schema needs keywords the bounded validator doesn't yet support, add them there — it's already authored against exactly our needs.

### Emitter as library, not service

The emitter is a small Python module (`converter/report/emitter.py`) producing typed dataclasses. No global state, no singletons. Each producer constructs `Finding` objects and accumulates them into a `Report` builder; the builder validates on `build()` before returning. The wrapper composes builders from each producer into one report.

### Markdown layout follows the report's structure, not the producers' structure

Markdown groups by Layer (A → B → C), then by category within each layer, then by file. This mirrors how a developer reads the report: blockers first, manual review second, learnings last. Producers don't appear in the rendered output as section headers — they're metadata on the finding.

### PR-comment summary mode

GitHub PR comments cap at 65,536 characters. The `--summary` renderer emits Layer A in full (top 20 by severity), Layer B counts by category, Layer C top 5 patterns. The full report is referenced by path. This matches gap §7.1 acceptance criterion 4.

### Confidence per symbol, not per file

Layer B findings carry `confidence_score: float` on the `Finding` itself. Aggregation up to file/project is a render-time concern, not a stored field — keeps producers from having to think about averaging.

### Provenance reserved, not wired

LLM provenance fields (`model`, `prompt_template`, `seed`) are reserved on the schema but not populated by any producer in MVP. The Step 6 scanner is regex-driven; no LLM. Reserving the fields now means the Bridge/Port phases that introduce LLM translation don't have to bump the schema. The schema marks them optional with a header comment explaining the deferred wiring.

### Where the report lands

Two files in the conversion output dir, alongside `PrivacyInfo.xcprivacy`:
- `report.md` — human-readable, sorted by severity.
- `report.json` — machine-readable, CI-consumable.

The `convert-from-github` flow commits both before push, same hook point as Step 6.

---

## Deliverables

1. **Report schema** — `schemas/report.schema.json`. Three-layer structure (A blockers / B manual review / C learnings), every finding's required fields, optional provenance fields, schema version pin.
2. **Emitter library** — `converter/report/emitter.py`. `Finding`, `LearningPattern`, `Report`, `ReportBuilder`. Frozen dataclasses; `build()` validates against the schema before returning.
3. **Renderers** — `converter/report/render.py`. `render_markdown(report) -> str`, `render_json(report) -> str`, `render_summary(report, *, max_chars=65000) -> str`.
4. **Schema validator integration** — extend `_validate_against_schema` from `converter/compliance/privacy_manifest.py` to a shared module if the report schema requires keywords beyond what's already supported, or accept the existing bounded validator if it covers the new schema unchanged.
5. **Step 6 scanner retrofit** — `converter/compliance/api_scanner.py` gains `to_findings(api_findings) -> list[Finding]`. The wrapper-level `compliance_step.py` accumulates these into the `ReportBuilder` instead of (or in addition to) printing the one-line summary.
6. **Wrapper integration** — `wrapper/__main__.py` passes a shared `ReportBuilder` through both the conversion and the compliance step, then renders `report.md` + `report.json` into the output dir.
7. **Tests** — schema round-trips, emitter rejects invalid findings before render, renderers handle empty / single-layer / full reports, summary renderer respects the char budget, Step 6 retrofit produces exactly the expected `Finding` set.

Out of scope for this step (handled later in Tier 1 / Phase 2):
- The pre-flight scanner itself (§7.3). Step 7 builds the report; Step 7+1 reads it and gates ship.
- LLM-translation provenance population. Schema fields reserved; no producer populates them yet.
- Trend data (rev > 1 deltas). Schema fields reserved (`prior_rev_confidence`, `delta`); the wrapper doesn't yet know how to read a prior rev's report. Trend wiring lands when revision-aware branching does.
- HIG / accessibility findings. New producers in later steps.

---

## Sub-steps (strict order)

### Step 7.1 — Author the schema

**File:** `schemas/report.schema.json`

**Top-level shape:**

```jsonc
{
  "schema_version": "1.0.0",
  "generated_at": "2026-05-05T12:00:00Z",
  "tool_version": "ios-agent 0.x.y",
  "source": {
    "archetype": "web",
    "target_mode": "wrap",
    "root": "...",
    "rev": 1
  },
  "layer_a_blockers": [Finding, ...],
  "layer_b_manual_review": [Finding, ...],
  "layer_c_learnings": [LearningPattern, ...]
}
```

**`Finding` fields (Layer A and B share the shape; B adds confidence):**
- `id` — stable string id, e.g. `compliance.required-reason-api.userdefaults#0`.
- `category` — short tag, e.g. `compliance.privacy-manifest`, `translation.force-unwrap`.
- `severity` — `blocker` | `warning` | `info`.
- `producer` — module that emitted it, e.g. `compliance.api_scanner`.
- `file` — repo-relative path (or `(plugins)` sentinel for plugin findings).
- `line` — int (0 if synthetic / plugin-derived).
- `original_snippet` — string (may be empty for synthetic findings).
- `attempted_translation` — string | null (always null for compliance findings; populated by translation producers later).
- `reason` — why this was flagged, in plain English.
- `recommended_fix` — what the developer should do.
- `doc_link` — URL.
- `confidence_score` — float 0..1, optional (Layer A doesn't carry one; Layer B does).
- `provenance` — object | null. Reserved fields: `model`, `prompt_template`, `seed`. All null in MVP.

**`LearningPattern` fields (Layer C):**
- `pattern` — short tag, e.g. `localStorage-via-capacitor-preferences`.
- `occurrences` — int.
- `applied_translation` — string description.
- `untranslatable_count` — int.
- `refactor_recommendation` — string.
- `prior_rev_confidence` — float | null.
- `delta` — float | null.

**Acceptance:** Schema validates a synthetic well-formed report and rejects each of: missing `severity`, unknown layer key, malformed `file` (non-string), `confidence_score` > 1.0.

---

### Step 7.2 — Emitter library

**File:** `converter/report/emitter.py`

**Public interface:**

```python
@dataclass(frozen=True)
class Finding: ...

@dataclass(frozen=True)
class LearningPattern: ...

@dataclass(frozen=True)
class Report:
    schema_version: str
    generated_at: str
    tool_version: str
    source: Source
    layer_a_blockers: tuple[Finding, ...]
    layer_b_manual_review: tuple[Finding, ...]
    layer_c_learnings: tuple[LearningPattern, ...]

class ReportBuilder:
    def __init__(self, *, source: Source, tool_version: str): ...
    def add_blocker(self, f: Finding) -> None: ...
    def add_manual_review(self, f: Finding) -> None: ...
    def add_learning(self, lp: LearningPattern) -> None: ...
    def build(self) -> Report: ...   # validates against schema; raises ReportError
```

`Report.to_dict()` produces the JSON-serialisable shape that matches the schema.

**Implementation notes:**
- Builder de-duplicates by `Finding.id`. Producers that emit the same id twice get one entry — the second call is a no-op, not an error.
- `build()` runs schema validation on the dict shape, not the dataclass tree. Validation failure raises `ReportError` with the schema validator's path-pointed message.

**Acceptance:** Builder rejects findings with empty `id`. `build()` on a builder with one finding in each layer round-trips through `to_dict()` → schema validation cleanly.

---

### Step 7.3 — Renderers

**File:** `converter/report/render.py`

**`render_markdown(report)`:**
- Top heading with source archetype, target mode, generated_at.
- `## Layer A — Blockers` — table of findings sorted by `(category, file, line)`. One row per finding with file:line link, category, reason, recommended fix.
- `## Layer B — Manual Review` — same shape + confidence column.
- `## Layer C — Learnings` — bullet list per pattern with occurrences, applied translation, refactor recommendation.
- Stable output for the same input (no timestamps in body except `generated_at` once at top).

**`render_json(report)`:**
- `json.dumps(report.to_dict(), indent=2, sort_keys=True)`. Stable key order.

**`render_summary(report, *, max_chars=65000)`:**
- Layer A in full (or first 20 by severity then category).
- Layer B grouped by category with counts.
- Layer C top 5 by occurrences.
- Footer: "Full report: report.md (N total findings)".
- Trims gracefully if over budget; never emits invalid Markdown.

**Acceptance:** A fixture report with 50 Layer-A and 200 Layer-B findings renders to summary under 65,000 characters. Markdown output is byte-identical across two runs with the same input (modulo `generated_at`).

---

### Step 7.4 — Step 6 scanner retrofit

**Files:** `converter/compliance/api_scanner.py`, `wrapper/compliance_step.py`

**Behaviour:**
- Add `to_findings(api_findings: Iterable[APIFinding]) -> list[Finding]` in the scanner module. Maps:
  - `category=NSPrivacyAccessedAPICategory*` → Finding `category=compliance.privacy-manifest.<short>`.
  - `severity=blocker` → Layer A.
  - `reason` template: "Source uses `<pattern>` which Apple classifies as `<category-short>` (required-reason API)."
  - `recommended_fix`: "Confirm the manifest entry's reason code is correct, or add an override in `privacy-overrides.yaml`."
  - `doc_link`: pinned Apple URL captured in the rules YAML.
- `wrapper/compliance_step.py` accepts an optional `ReportBuilder`. If provided, it adds the findings to the builder *and* writes the manifest. If not provided, current behaviour is preserved (one-line summary). This keeps `compliance_step` independently usable and testable.

**Acceptance:** A scan against the existing fixture (`localStorage` + `@capacitor/filesystem`) produces exactly 2 Layer-A findings with stable ids, both pointing at `compliance.privacy-manifest.*`.

---

### Step 7.5 — Wrapper integration

**File:** `wrapper/__main__.py`

**Behaviour:**
- Both `cmd_convert` and `cmd_convert_from_github` construct a `ReportBuilder` after the matrix gate passes.
- The builder is passed into the (existing) conversion flow as a kwarg; the conversion already prints a triage but doesn't yet emit findings — Step 7 leaves conversion findings empty for now (the converter will gain its own producers in later plans).
- The builder is passed into `run_compliance_step(..., report_builder=builder)`.
- After both steps finish, the builder is built and rendered to `report.md` + `report.json` in `output_dir`.
- Failure to build the report (validation error) surfaces as a wrapper-level warning, same posture as Step 6 — Step 7+1's pre-flight gate is the ship-blocker, not the report writer.

**Acceptance:** End-to-end run on the existing fixture produces `report.md` and `report.json` in the output dir. Both pass schema validation. The compliance one-line summary still prints.

---

### Step 7.6 — Tests

**Files:**
- `converter/report/tests/test_schema.py` — schema-level round-trip + rejection tests.
- `converter/report/tests/test_emitter.py` — builder semantics, dedup, invalid-finding rejection.
- `converter/report/tests/test_render.py` — Markdown stability, JSON ordering, summary char budget.
- `wrapper/tests/test_report_integration.py` — end-to-end run produces both files in the output dir; both validate.

**Coverage targets:**
- Every public function in `emitter.py` and `render.py` has at least one direct test.
- Every required schema field has at least one rejection test (missing → ReportError).
- The retrofit test (`test_compliance_step.py` extension) verifies the new builder pathway without regressing the existing 8 tests.

---

## Acceptance for the whole step

All of the following must hold:

1. `schemas/report.schema.json` is loadable, version-pinned, and validates against the bounded validator.
2. The emitter accepts well-formed findings, rejects malformed ones, and de-duplicates by `id`.
3. The Markdown, JSON, and summary renderers all produce stable output for the same input.
4. The Step 6 scanner emits findings exclusively through the emitter when the wrapper supplies a builder. The pre-existing one-line summary path still works when no builder is passed.
5. The wrapper writes `report.md` + `report.json` into the conversion output dir on every run.
6. The summary renderer respects a 65,000-character budget and never produces invalid Markdown.
7. Tests cover schema, emitter, renderers, and end-to-end wrapper integration. All green.

When all seven pass, Step 7 is done. The next plan introduces the pre-flight scanner (§7.3) which consumes Layer-A findings to gate ship-readiness.

---

## Notes / risks

- **Schema churn before producers arrive.** The schema is being designed with one real producer (Step 6) and several speculative ones (translation, ATT, SIWA, ATS). If a future producer needs a field we haven't reserved, we bump `schema_version` and the renderers handle missing fields. Keep the schema *narrow* now; widen later.
- **Markdown stability.** Tests assert byte equality across runs. Sort keys in JSON, sort findings in Markdown. Don't let dict ordering or file-system iteration order leak in.
- **PR-comment budget drift.** GitHub's 65,536 cap is the hard wall; `max_chars=65000` leaves headroom for the wrapper's own framing text. If we ever post via API in Step 8 we'll re-tune.
- **Validator coverage.** The bounded JSON Schema validator only handles the keywords used in the privacy manifest schema. Authoring this schema against the same keyword set keeps that constraint silent. If we reach for `oneOf` / `not` / `anyOf`, extend the validator and add coverage tests in `test_privacy_manifest.py`.

---

## File inventory (for review)

After Step 7:

```
schemas/
  report.schema.json                          (new)
converter/
  compliance/
    api_scanner.py                            (modified — adds to_findings)
  report/
    __init__.py                               (new)
    emitter.py                                (new)
    render.py                                 (new)
    tests/
      __init__.py                             (new)
      test_schema.py                          (new)
      test_emitter.py                         (new)
      test_render.py                          (new)
wrapper/
  __main__.py                                 (modified — wires report builder)
  compliance_step.py                          (modified — accepts ReportBuilder)
  tests/
    test_compliance_step.py                   (modified — adds builder pathway)
    test_report_integration.py                (new)
```

No edits to existing converter modules outside `compliance/`. No changes to the matrix, scope doc, ADR, or the privacy-manifest schema/template.
