# Plan: Tier 1 Step 6 — API-Usage Scanner + Privacy Manifest Generator

**Parent plan:** `plans/mvp-tier-0-tier-1.md` (Step 6)
**Source:** `MVP-Gap-Analysis.md` §4.1
**Status:** ✅ Complete — all sub-steps (6.1 → 6.7) shipped 2026-05-05.
**Owner:** Tech lead (this conversation)
**Created:** 2026-05-05

---

## Summary

Build the foundation that every later compliance module reuses: a scanner that detects Apple "required-reason API" usage in source-side code (web archetype: HTML/CSS/JS/TS), and a generator that emits a valid `PrivacyInfo.xcprivacy` from those detections. Future modules (ATT, SIWA, ATS, usage strings, pre-flight scanner) bolt onto the same scanner.

Tier 1 ordering is strict: Step 6 → Step 7 → Step 8. The scanner is built first because Step 7's report schema needs real findings to validate against, and Step 8's Xcode project generation needs the manifest output to embed.

For MVP (web → Wrap), the scanner walks the source codebase plus declared Capacitor plugins. It does not yet walk emitted Swift, because Wrap mode emits very little Swift (mostly Capacitor bootstrap). Future Bridge/Port phases will extend the scanner to emitted Swift; the scanner's interface should accommodate that without rework.

---

## Deliverables

1. **Required-reason API list** — `config/apple-required-reason-apis.yaml`. Versioned data file, not code. Initial coverage: the four categories Apple has published (NSPrivacyAccessedAPICategoryUserDefaults, FileTimestamp, SystemBootTime, DiskSpace) plus ActiveKeyboards. Each entry maps an API surface to its NSPrivacyAccessedAPIType + the allowed reason codes Apple has approved.
2. **Scanner core** — `converter/compliance/api_scanner.py`. Walks source files, returns structured findings.
3. **Privacy manifest generator** — `converter/compliance/privacy_manifest.py`. Takes scanner findings + a `privacy-overrides.yaml` (user-editable) and emits a valid `PrivacyInfo.xcprivacy`.
4. **Schema validator** — validates the emitted manifest against Apple's published schema before write.
5. **Manual override support** — a per-project `privacy-overrides.yaml` schema that lets the developer add reasons the scanner can't infer (e.g. tracking domains, third-party SDK declarations).
6. **Findings emitter** — produces a structured finding-record list. Step 7 will swallow this into the report; for now, emit a typed dataclass list.
7. **Tests** — fixture-driven tests covering: (a) detection of every API in the list, (b) clean handling of false-positive shapes, (c) manifest schema validation, (d) override merging, (e) graceful failure on malformed override files.
8. **Wiring** — a thin entry point that the wrapper CLI can call after a successful conversion to produce the manifest. Wired but not yet gated as a hard blocker — that comes in Step 7's pre-flight scanner.

Out of scope for this step (handled later in Tier 1):
- ATT, SIWA, usage strings, ATS, encryption — all reuse the scanner; built in the next plan after Step 8.
- Three-layer report integration — Step 7. The scanner emits typed findings now; Step 7 wires them into the report schema.
- Xcode project embedding — Step 8 picks up the generated manifest and places it into the spec.

---

## Architectural choices

### Why source-side scanning, not emitted-Swift scanning, for MVP

In Wrap mode, the bulk of "code" that hits Apple's required-reason APIs is **the developer's web app**, not the generated Swift wrapper. The Capacitor host project itself uses very few required-reason APIs directly; what matters is which Capacitor plugins are declared. So the scanner has two pass shapes:

- **Source pass** — scan JS/TS source for usage patterns that imply required-reason API behaviour after Capacitor wraps them (e.g. `localStorage` → `UserDefaults` semantics; `Capacitor.Plugins.Filesystem.stat()` → file-timestamp APIs; `navigator.userAgent` checks → no required-reason but worth noting for analytics).
- **Plugin pass** — read `capacitor.config.ts` / `package.json` to enumerate declared plugins and map each to its known required-reason API set.

Bridge/Port phases will add a third pass on emitted Swift. The scanner core is built so adding a pass is a new function, not a refactor.

### Why YAML for the required-reason list

Apple updates the list. Versioning the list as data (not code) means we can update it without a code release and ship rule-set updates as a project file. Tier 0 ADR 0001 forbids hand-writing parsers we don't need; the existing `wrapper/compatibility.py` YAML reader (Step 2) covers our subset.

### Why a separate `converter/compliance/` package

Compliance modules will accumulate (ATT, SIWA, usage strings, ATS, encryption, scanner). Keeping them under one package gives a single import surface and one place for tests. They share the scanner; co-locating them is correct.

### Manifest schema validation

Apple publishes a JSON schema for `PrivacyInfo.xcprivacy`. We won't fetch it at runtime — bundle a captured copy under `config/apple-privacy-manifest.schema.json` with a version pin. CI quarterly review (per ADR 0001) re-checks it.

### Output format

Apple expects `PrivacyInfo.xcprivacy` as a property list (XML plist). We'll emit XML plist directly; Python's stdlib `plistlib` handles encode/decode. No third-party dep needed.

---

## Steps

### Step 6.1 — Build the required-reason API data file ✅ shipped 2026-05-05

**File:** `config/apple-required-reason-apis.yaml`

**Contents:**
- Version field (Apple's privacy manifest spec version we're targeting).
- Categories (NSPrivacyAccessedAPICategoryUserDefaults, FileTimestamp, SystemBootTime, DiskSpace, ActiveKeyboards).
- For each category: list of source-side patterns (JS/TS API names, Capacitor plugin names) that imply the category's API surface, plus the canonical reason codes Apple has approved (e.g. `CA92.1`, `1C8F.1`, etc.).
- Each entry: `category`, `pattern_type` (`js_api` | `ts_import` | `capacitor_plugin` | `native_api`), `pattern`, `default_reason_code`, `notes`.

**Acceptance:** YAML loads via the existing `wrapper.compatibility._load_yaml`. Linted by a smoke test that confirms required fields exist on every entry.

---

### Step 6.2 — Author the scanner core

**File:** `converter/compliance/api_scanner.py`

**Public interface:**

```python
@dataclass(frozen=True)
class APIFinding:
    category: str          # NSPrivacyAccessedAPICategory*
    pattern: str           # the matched source pattern
    pattern_type: str      # js_api | ts_import | capacitor_plugin | native_api
    file: Path
    line: int
    snippet: str
    reason_code: str       # the default reason code from the rule file
    severity: str          # "blocker" — missing manifest entry blocks ship

def scan_source(root: Path, *, rules_path: Path | None = None) -> list[APIFinding]: ...
def scan_capacitor_plugins(root: Path, *, rules_path: Path | None = None) -> list[APIFinding]: ...
def scan_all(root: Path, *, rules_path: Path | None = None) -> list[APIFinding]: ...
```

**Implementation notes:**
- Pattern matching: regex-driven for v1; AST-driven via tree-sitter is a Step 8+ improvement (per ADR 0001 the AST tooling is mandated for Phase 1, but for *web source* parsing the regex pass is acceptable now and the AST pass replaces it without changing the public interface). Document this trade-off inline.
- File walk: respect `.gitignore` semantics where reasonably easy, skip `node_modules/`, `dist/`, `build/`, `.next/`, `.git/`, `workspace/`.
- Per-finding line numbers from regex match positions.

**Acceptance:** Scanner runs against a fixture project containing one of each category and produces exactly the expected `APIFinding` list.

---

### Step 6.3 — Author the privacy manifest generator

**File:** `converter/compliance/privacy_manifest.py`

**Public interface:**

```python
def generate_manifest(
    findings: Sequence[APIFinding],
    *,
    overrides_path: Path | None = None,
    output_path: Path,
) -> Path: ...

def validate_manifest(path: Path, *, schema_path: Path | None = None) -> list[str]: ...
```

**Behaviour:**
- Group findings by category.
- For each category: emit one `NSPrivacyAccessedAPIType` entry with a deduplicated `NSPrivacyAccessedAPITypeReasons` array (the union of `reason_code`s from findings + overrides).
- Merge overrides on top of scanner findings.
- Emit XML plist via `plistlib`.
- Re-read and validate against Apple's schema before returning success. Any validation error is raised — manifest output should never be silently invalid.

**Acceptance:** Round-trip test — scan fixture → generate manifest → re-load via `plistlib` → assert structure matches expected dict.

---

### Step 6.4 — Manual override schema

**File:** `templates/privacy-overrides.yaml.template` (the canonical form a developer's project includes)

**Schema:**
- `additional_categories:` — list of `{category, reason_codes, justification}` triples.
- `tracking:` — `{enabled: bool, tracking_domains: [str]}`.
- `third_party_sdks:` — list of `{name, privacy_manifest_url, justification}`.
- `excluded_findings:` — list of finding IDs the developer has reviewed and acknowledged should not appear in the manifest.

**Acceptance:** Sample override file loads, merges into manifest output, emits valid plist.

---

### Step 6.5 — Tests

**File:** `converter/compliance/tests/test_api_scanner.py`, `test_privacy_manifest.py`

Coverage:
- Detection of every category in the rule file (one fixture file per category).
- False-positive guard: a fixture that *resembles* a required-reason API but isn't (e.g. a string literal mentioning `UserDefaults`).
- Manifest XML round-trips correctly.
- Schema validation rejects a known-bad manifest (corrupted fixture).
- Overrides merge on top of findings without duplication.
- Missing rule file → clear error.
- Missing override file → no error (overrides are optional).

**Acceptance:** All tests pass; coverage of `api_scanner.py` and `privacy_manifest.py` is meaningful (every public function exercised, every category in the rule file represented in a fixture).

---

### Step 6.6 — Wire into the wrapper CLI

**File:** `wrapper/__main__.py` and (new) `wrapper/compliance_step.py`

**Behaviour:**
- After a successful conversion (both `convert` and `convert-from-github`), run the scanner against the source dir and write `PrivacyInfo.xcprivacy` into the conversion output directory.
- Print a one-line summary: `privacy manifest: N findings across M categories → PrivacyInfo.xcprivacy`.
- Surface any manifest-generation error as a wrapper-level warning (not a hard fail yet — the pre-flight scanner in Step 7 is what blocks ship).

**Acceptance:** End-to-end run on the existing test fixture produces a manifest file at the expected location.

---

### Step 6.7 — Bundle Apple's privacy manifest schema ✅ shipped 2026-05-05

**File:** `config/apple-privacy-manifest.schema.json`

Capture Apple's published schema (a copy, version-pinned via a header comment with the date of capture). Quarterly review per ADR 0001 will refresh it.

**Acceptance:** `validate_manifest()` uses this schema; a synthetic invalid manifest fails validation; a synthetic valid manifest passes.

---

## Acceptance for the whole step

All of the following must hold:

1. The required-reason API list is data-driven and loadable.
2. The scanner produces structured `APIFinding` records for every supported category.
3. The generator emits a valid `PrivacyInfo.xcprivacy` that round-trips through `plistlib`.
4. Schema validation rejects malformed manifests.
5. Overrides merge cleanly.
6. The wrapper CLI runs the scanner on every conversion and writes the manifest into the output directory.
7. Tests cover scanner, generator, validator, and overrides — all green.
8. Adding a new required-reason API to the YAML data file picks it up on next run with no code change.

When all eight pass, Step 6 is done. Step 7 (three-layer report schema) starts next; the scanner's `APIFinding` type becomes one of the inputs to the Layer-A finding shape.

---

## Notes / risks

- **Schema drift.** Apple has expanded the privacy manifest spec twice in 2024 alone. The captured schema must be reviewed quarterly per ADR 0001. If Apple's schema URL is unstable, document the fetch-and-pin process in the YAML header.
- **Regex vs AST.** The MVP regex approach has known false-positive risk on string literals that look like API calls. Step 7 manual-review findings will surface this. Tree-sitter AST parsing replaces regex in a follow-on plan; the public interface stays.
- **Capacitor plugin coverage.** The MVP only knows the required-reason mappings for the most common Capacitor plugins. Less-common plugins fall through to "unknown" findings that emit a Layer-B (manual review) flag in Step 7. The plugin map lives in the same YAML data file so it can be extended without code changes.
- **No false-negative safety net.** A Capacitor plugin we don't know about can use a required-reason API without us catching it. The Step 7 pre-flight scanner will warn loudly when third-party plugins are detected without manifest entries — this is the catch-all.

---

## File inventory (for review)

After Step 6:

```
config/
  apple-required-reason-apis.yaml          (new)
  apple-privacy-manifest.schema.json       (new)
converter/
  compliance/
    __init__.py                            (new)
    api_scanner.py                         (new)
    privacy_manifest.py                    (new)
    tests/
      __init__.py                          (new)
      test_api_scanner.py                  (new)
      test_privacy_manifest.py             (new)
      fixtures/
        web-app-with-userdefaults/...      (new)
        web-app-with-filetimestamp/...     (new)
        web-app-with-overrides/...         (new)
templates/
  privacy-overrides.yaml.template          (new)
wrapper/
  __main__.py                              (modified)
  compliance_step.py                       (new — thin orchestration)
```

No edits to existing converter modules. No changes to the matrix, scope doc, or ADR.
