"""
ATT / IDFA compliance scanner — MVP §4.3.

Detects App Tracking Transparency (ATT) and IDFA usage patterns in a
web-archetype source tree. Apple Guideline 5.1.2 requires:
  1. A call to ATTrackingManager.requestTrackingAuthorization before
     accessing the IDFA.
  2. NSUserTrackingUsageDescription in Info.plist.

Rejection happens automatically when either is absent. The additional
risk: analytics SDKs (Firebase Analytics, Facebook SDK, Amplitude, etc.)
read the IDFA *transitively* — the developer may not know ATT applies.

This scanner reuses the ATTUsageDescription category added to
config/apple-required-reason-apis.yaml. Findings are emitted as Layer-A
blockers via the report adapter at the bottom of this module.

Plan: plans/mvp-section-4-compliance.md (Step 4.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .api_scanner import (
    SOURCE_EXTENSIONS,
    SKIP_DIRS,
    ScannerError,
    _compile_regex,
    _enumerate_lines,
    _walk_source_files,
    load_rules,
)
from wrapper.compatibility import _load_yaml  # type: ignore[attr-defined]


_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "apple-required-reason-apis.yaml"
)

ATT_CATEGORY_ID = "ATTUsageDescription"

# Apple doc for ATT / NSUserTrackingUsageDescription.
ATT_DOC_URL = (
    "https://developer.apple.com/documentation/apptrackingtransparency/"
    "attrackingmanager/requesttrackingauthorization(completionhandler:)"
)

# Apple info.plist key required alongside any IDFA / ATT usage.
ATT_USAGE_STRING_KEY = "NSUserTrackingUsageDescription"

PRODUCER = "compliance.att_scanner"


@dataclass(frozen=True)
class ATTFinding:
    """A single match of an ATT / IDFA pattern in source."""

    pattern: str
    pattern_type: str  # js_api | ts_import | capacitor_plugin
    reason_code: str   # ATT.1 (direct) or ATT.2 (transitive via SDK)
    file: Path
    line: int          # 1-indexed; 0 = manifest-declared plugin
    snippet: str
    notes: str | None = None


@dataclass(frozen=True)
class _ATTRule:
    pattern_type: str
    pattern: str
    default_reason_code: str
    notes: str | None
    regex: object | None  # re.Pattern | None


def load_att_rules(rules_path: Path | None = None) -> list[_ATTRule]:
    """Load ATT-specific patterns from the required-reason API config.

    Returns rules for the ATTUsageDescription category only.
    """
    path = rules_path or _DEFAULT_RULES_PATH
    if not path.exists():
        raise ScannerError(f"required-reason API rule file not found: {path}")

    try:
        raw = _load_yaml(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ScannerError(f"failed to parse {path}: {exc}") from exc

    categories = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(categories, list):
        raise ScannerError(f"{path}: top-level 'categories' must be a list")

    rules: list[_ATTRule] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        if cat.get("id") != ATT_CATEGORY_ID:
            continue
        for entry in cat.get("patterns", []) or []:
            if not isinstance(entry, dict):
                continue
            ptype = entry.get("pattern_type")
            pval = entry.get("pattern")
            reason = entry.get("default_reason_code")
            if not (isinstance(ptype, str) and isinstance(pval, str) and isinstance(reason, str)):
                continue
            notes = entry.get("notes") if isinstance(entry.get("notes"), str) else None
            rules.append(
                _ATTRule(
                    pattern_type=ptype,
                    pattern=pval,
                    default_reason_code=reason,
                    notes=notes,
                    regex=_compile_regex(ptype, pval),
                )
            )
    return rules


def scan_att_source(
    root: Path,
    *,
    rules: list[_ATTRule] | None = None,
    rules_path: Path | None = None,
) -> list[ATTFinding]:
    """Scan JS/TS source files under `root` for ATT/IDFA patterns."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    loaded = rules if rules is not None else load_att_rules(rules_path)
    source_rules = [r for r in loaded if r.pattern_type in ("js_api", "ts_import")]
    if not source_rules:
        return []

    findings: list[ATTFinding] = []
    for fpath in _walk_source_files(root):
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in _enumerate_lines(text):
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for rule in source_rules:
                assert rule.regex is not None
                if rule.regex.search(line):
                    findings.append(
                        ATTFinding(
                            pattern=rule.pattern,
                            pattern_type=rule.pattern_type,
                            reason_code=rule.default_reason_code,
                            file=fpath,
                            line=line_num,
                            snippet=line.rstrip("\n").strip(),
                            notes=rule.notes,
                        )
                    )
    return findings


def scan_att_plugins(
    root: Path,
    *,
    rules: list[_ATTRule] | None = None,
    rules_path: Path | None = None,
) -> list[ATTFinding]:
    """Detect ATT-bearing Capacitor plugins declared in package.json."""
    import json as _json

    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    loaded = rules if rules is not None else load_att_rules(rules_path)
    plugin_rules = {r.pattern: r for r in loaded if r.pattern_type == "capacitor_plugin"}
    if not plugin_rules:
        return []

    declared: dict[str, Path] = {}
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = _json.loads(pkg_json.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            data = {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name in (data.get(section) or {}):
                if name in plugin_rules and name not in declared:
                    declared[name] = pkg_json

    findings: list[ATTFinding] = []
    for plugin_name, source_file in sorted(declared.items()):
        rule = plugin_rules[plugin_name]
        findings.append(
            ATTFinding(
                pattern=plugin_name,
                pattern_type="capacitor_plugin",
                reason_code=rule.default_reason_code,
                file=source_file,
                line=0,
                snippet=f"declared plugin: {plugin_name}",
                notes=rule.notes,
            )
        )
    return findings


def scan_all_att(
    root: Path,
    *,
    rules_path: Path | None = None,
) -> list[ATTFinding]:
    """Run source + plugin passes; return deduplicated findings."""
    rules = load_att_rules(rules_path)
    src = sorted(
        scan_att_source(root, rules=rules),
        key=lambda f: (str(f.file), f.line, f.pattern),
    )
    plugins = sorted(
        scan_att_plugins(root, rules=rules),
        key=lambda f: (str(f.file), f.pattern),
    )
    return src + plugins


# --- Three-layer report adapter ----------------------------------------------


def to_att_findings(
    att_findings: Iterable[ATTFinding],
    *,
    source_root: Path | None = None,
) -> list["Finding"]:  # noqa: F821
    """Convert ATTFinding records into Layer-A report Finding records."""
    from converter.report import Finding

    out: list[Finding] = []
    counters: dict[str, int] = {}

    for af in att_findings:
        slug = "direct" if af.reason_code == "ATT.1" else "transitive"
        idx = counters.get(slug, 0)
        counters[slug] = idx + 1
        finding_id = f"compliance.att.{slug}#{idx}"

        if af.pattern_type == "capacitor_plugin":
            file_str = "(plugins)"
            line = 0
            reason = (
                f"Capacitor plugin `{af.pattern}` triggers Apple's App Tracking "
                f"Transparency requirement. Add `NSUserTrackingUsageDescription` "
                f"to Info.plist and call ATTrackingManager.requestTrackingAuthorization "
                f"before accessing user data."
            )
        else:
            if source_root is not None:
                root_abs = source_root.resolve()
                file_abs = af.file.resolve()
                try:
                    file_str = str(file_abs.relative_to(root_abs))
                except ValueError:
                    file_str = str(af.file)
            else:
                file_str = str(af.file)
            line = af.line

            if af.reason_code == "ATT.1":
                reason = (
                    f"Source calls `{af.pattern}` — a direct ATT / IDFA API. "
                    f"`NSUserTrackingUsageDescription` is required in Info.plist "
                    f"and ATTrackingManager.requestTrackingAuthorization must be "
                    f"called before accessing the identifier (Guideline 5.1.2)."
                )
            else:
                sdk_note = f" ({af.notes})" if af.notes else ""
                reason = (
                    f"Source imports `{af.pattern}`{sdk_note}, which reads the IDFA "
                    f"transitively on iOS. Apple requires `NSUserTrackingUsageDescription` "
                    f"in Info.plist even when IDFA access is indirect (Guideline 5.1.2)."
                )

        out.append(
            Finding(
                id=finding_id,
                category=f"compliance.att.{slug}",
                severity="blocker",
                producer=PRODUCER,
                file=file_str,
                line=line,
                original_snippet=af.snippet,
                attempted_translation=None,
                reason=reason,
                recommended_fix=(
                    f"1. Add `{ATT_USAGE_STRING_KEY}` to Info.plist with a plain-English "
                    f"explanation of why tracking is needed.\n"
                    f"2. Call ATTrackingManager.requestTrackingAuthorization at app launch "
                    f"(or on first relevant user action) via the Capacitor ATT plugin.\n"
                    f"3. Handle the .denied case — do not assume consent."
                ),
                doc_link=ATT_DOC_URL,
            )
        )
    return out
