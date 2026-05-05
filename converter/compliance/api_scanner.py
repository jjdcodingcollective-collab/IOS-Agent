"""
Required-reason API scanner — Tier 1 Step 6.2.

Walks a web-archetype source tree and emits structured APIFinding records
for every pattern that maps to an Apple-defined NSPrivacyAccessedAPI
category. The mapping is data-driven: rules live in
config/apple-required-reason-apis.yaml.

Plan: plans/tier-1-step-6-privacy-scanner.md (Step 6.2).
ADR 0001 mandates tree-sitter for AST parsing in Phase 1; for the MVP
web-source pass a regex sweep is acceptable because (a) the patterns are
identifier-shaped and (b) the failure mode is a Layer-B manual-review
finding, not a hard miss. The public interface stays the same when a
tree-sitter pass replaces the regex pass.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from wrapper.compatibility import _load_yaml  # type: ignore[attr-defined]


# Project root → config/apple-required-reason-apis.yaml
_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "apple-required-reason-apis.yaml"
)

# File extensions worth scanning for source-side patterns.
SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

# Directories to skip during walk. Mirrors converter/analyzer/scanner.py.
SKIP_DIRS = {
    "node_modules",
    ".next",
    ".vercel",
    "dist",
    "build",
    ".git",
    "coverage",
    "__pycache__",
    ".turbo",
    ".cache",
    "out",
    "workspace",
    ".ios-conversion",
}

# Capacitor config filenames in priority order.
_CAPACITOR_CONFIG_FILES = (
    "capacitor.config.ts",
    "capacitor.config.js",
    "capacitor.config.json",
)


class ScannerError(Exception):
    """Raised when the scanner cannot start (bad rules file, missing root)."""


@dataclass(frozen=True)
class APIFinding:
    """A single match of a required-reason API pattern in source."""

    category: str  # NSPrivacyAccessedAPICategory*
    pattern: str  # the matched source pattern
    pattern_type: str  # js_api | ts_import | capacitor_plugin | native_api
    file: Path
    line: int  # 1-indexed
    snippet: str
    reason_code: str  # default reason code from the rule file
    severity: str = "blocker"


@dataclass(frozen=True)
class _Pattern:
    """Internal: one rule-file pattern, expanded for matching."""

    category: str
    pattern_type: str
    pattern: str
    default_reason_code: str
    notes: str | None
    regex: re.Pattern[str] | None  # None for capacitor_plugin / native_api


def load_rules(rules_path: Path | None = None) -> list[_Pattern]:
    """Load patterns from the required-reason API rule file.

    Returns a flat list of _Pattern objects ready for matching.
    Raises ScannerError if the file cannot be loaded or is malformed.
    """
    path = rules_path or _DEFAULT_RULES_PATH
    if not path.exists():
        raise ScannerError(f"required-reason API rule file not found: {path}")

    try:
        text = path.read_text(encoding="utf-8")
        raw = _load_yaml(text)
    except Exception as exc:
        raise ScannerError(f"failed to parse {path}: {exc}") from exc

    categories = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(categories, list):
        raise ScannerError(f"{path}: top-level 'categories' must be a list")

    patterns: list[_Pattern] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        cat_id = cat.get("id")
        if not isinstance(cat_id, str):
            continue
        for entry in cat.get("patterns", []) or []:
            if not isinstance(entry, dict):
                continue
            ptype = entry.get("pattern_type")
            pval = entry.get("pattern")
            reason = entry.get("default_reason_code")
            if not (isinstance(ptype, str) and isinstance(pval, str) and isinstance(reason, str)):
                continue
            patterns.append(
                _Pattern(
                    category=cat_id,
                    pattern_type=ptype,
                    pattern=pval,
                    default_reason_code=reason,
                    notes=entry.get("notes") if isinstance(entry.get("notes"), str) else None,
                    regex=_compile_regex(ptype, pval),
                )
            )
    return patterns


def _compile_regex(pattern_type: str, pattern: str) -> re.Pattern[str] | None:
    """Compile a per-line regex for source-pass patterns.

    Plugin and native-API patterns are matched separately, not via this
    regex.
    """
    if pattern_type in ("capacitor_plugin", "native_api"):
        return None
    # js_api / ts_import: match as a contiguous identifier-with-dots
    # surrounded by non-identifier boundaries. Escape dots and `@`/`/`
    # so package-style patterns ('@capacitor/preferences') match
    # exactly.
    escaped = re.escape(pattern)
    return re.compile(rf"(?<![A-Za-z0-9_$]){escaped}(?![A-Za-z0-9_$])")


def scan_source(
    root: Path,
    *,
    rules_path: Path | None = None,
    rules: list[_Pattern] | None = None,
) -> list[APIFinding]:
    """Scan JS/TS source files under `root` for required-reason API usage.

    `rules` may be passed directly to avoid re-parsing the rule file on
    successive calls; otherwise the file at `rules_path` is loaded.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    patterns = rules if rules is not None else load_rules(rules_path)
    source_patterns = [p for p in patterns if p.pattern_type in ("js_api", "ts_import")]
    if not source_patterns:
        return []

    findings: list[APIFinding] = []
    for fpath in _walk_source_files(root):
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in _enumerate_lines(text):
            stripped = line.lstrip()
            # Skip pure comment lines — common false-positive source.
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for pat in source_patterns:
                assert pat.regex is not None
                if pat.regex.search(line):
                    findings.append(
                        APIFinding(
                            category=pat.category,
                            pattern=pat.pattern,
                            pattern_type=pat.pattern_type,
                            file=fpath,
                            line=line_num,
                            snippet=line.rstrip("\n").strip(),
                            reason_code=pat.default_reason_code,
                        )
                    )
    return findings


def scan_capacitor_plugins(
    root: Path,
    *,
    rules_path: Path | None = None,
    rules: list[_Pattern] | None = None,
) -> list[APIFinding]:
    """Detect declared Capacitor plugins and emit findings for known mappings.

    Reads `package.json` dependencies/devDependencies plus any
    `capacitor.config.*` file so plugins declared in either place are
    counted. Each plugin found whose name matches a `capacitor_plugin`
    pattern in the rule file produces one finding (line=0 is a sentinel
    for "declared in manifest, not in source").
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    patterns = rules if rules is not None else load_rules(rules_path)
    plugin_patterns = {p.pattern: p for p in patterns if p.pattern_type == "capacitor_plugin"}
    if not plugin_patterns:
        return []

    declared: dict[str, Path] = {}  # plugin name → file where declared

    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name in (data.get(section) or {}):
                if name in plugin_patterns and name not in declared:
                    declared[name] = pkg_json

    for fname in _CAPACITOR_CONFIG_FILES:
        cfg = root / fname
        if not cfg.exists():
            continue
        try:
            text = cfg.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for plugin_name in plugin_patterns:
            if plugin_name in text and plugin_name not in declared:
                declared[plugin_name] = cfg

    findings: list[APIFinding] = []
    for plugin_name, source_file in sorted(declared.items()):
        pat = plugin_patterns[plugin_name]
        findings.append(
            APIFinding(
                category=pat.category,
                pattern=plugin_name,
                pattern_type="capacitor_plugin",
                file=source_file,
                line=0,
                snippet=f"declared plugin: {plugin_name}",
                reason_code=pat.default_reason_code,
            )
        )
    return findings


def scan_all(
    root: Path,
    *,
    rules_path: Path | None = None,
) -> list[APIFinding]:
    """Run both passes and return the combined finding list.

    Loads rules once and passes them to each pass — avoids re-parsing the
    rule file. Findings are returned in the order: source pass first,
    then plugin pass, sorted within each pass by (file, line).
    """
    rules = load_rules(rules_path)
    src = sorted(
        scan_source(root, rules=rules),
        key=lambda f: (str(f.file), f.line, f.pattern),
    )
    plugins = sorted(
        scan_capacitor_plugins(root, rules=rules),
        key=lambda f: (str(f.file), f.pattern),
    )
    return src + plugins


def _walk_source_files(root: Path) -> Iterable[Path]:
    """Yield JS/TS source files under root, skipping vendor/build dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.suffix in SOURCE_EXTENSIONS:
                yield fpath


def _enumerate_lines(text: str) -> Iterable[tuple[int, str]]:
    """Yield (1-indexed line number, line) pairs."""
    for i, line in enumerate(text.splitlines(), start=1):
        yield i, line


# --- Three-layer report adapter (Step 7.4) -----------------------------------
#
# Bridges APIFinding (this module's native shape) to converter.report.Finding
# so the scanner can emit findings into a ReportBuilder. Kept here rather than
# in converter/report/ to avoid creating a back-edge from report → compliance:
# the compliance package owns the producer identity + canonical doc URL.

# Apple's canonical documentation page for required-reason API categories.
# Captured 2026-05-05 from config/apple-required-reason-apis.yaml header.
PRIVACY_MANIFEST_DOC_URL = (
    "https://developer.apple.com/documentation/bundleresources/"
    "app-privacy-configuration/nsprivacyaccessedapitypes/"
    "nsprivacyaccessedapitype"
)

# Producer identifier stamped on every Finding emitted from this module.
PRODUCER = "compliance.api_scanner"


def to_findings(
    api_findings: Iterable[APIFinding],
    *,
    source_root: Path | None = None,
) -> list["Finding"]:  # noqa: F821 — forward ref, imported lazily below
    """Convert APIFinding records into report Finding records.

    All scanner findings are Layer A blockers (severity=blocker), per gap §4.1
    — a missing privacy-manifest entry blocks ship. Plugin-derived findings
    use the (plugins) sentinel for `file` since they have no source location.

    `source_root`, when provided, is used to render `file` as a repo-relative
    path. Without it, the absolute path from the APIFinding is preserved.
    """
    # Lazy import: keeps the compliance package import-clean for code paths
    # that don't need the report shape (e.g. the existing one-line summary).
    from converter.report import Finding

    out: list[Finding] = []
    counters: dict[str, int] = {}
    for af in api_findings:
        category_short = af.category.removeprefix("NSPrivacyAccessedAPICategory")
        slug = category_short.lower()
        idx = counters.get(slug, 0)
        counters[slug] = idx + 1
        finding_id = f"compliance.privacy-manifest.{slug}#{idx}"

        if af.pattern_type == "capacitor_plugin":
            file_str = "(plugins)"
            line = 0
            reason = (
                f"Capacitor plugin `{af.pattern}` exposes "
                f"{category_short} APIs (required-reason)."
            )
        else:
            if source_root is not None:
                # source_root may be a relative path (e.g. from a temp dir);
                # the scanner walks os.walk which yields absolute paths. Resolve
                # both sides so relative_to() can match.
                root_abs = source_root.resolve()
                file_abs = af.file.resolve()
                try:
                    file_str = str(file_abs.relative_to(root_abs))
                except ValueError:
                    file_str = str(af.file)
            else:
                file_str = str(af.file)
            line = af.line
            reason = (
                f"Source uses `{af.pattern}`, which Apple classifies as "
                f"{category_short} (required-reason API)."
            )

        recommended_fix = (
            f"Confirm the manifest entry's reason code (`{af.reason_code}`) "
            f"matches the actual use, or add an override in "
            f"`privacy-overrides.yaml`."
        )

        out.append(
            Finding(
                id=finding_id,
                category=f"compliance.privacy-manifest.{slug}",
                severity="blocker",
                producer=PRODUCER,
                file=file_str,
                line=line,
                original_snippet=af.snippet,
                attempted_translation=None,
                reason=reason,
                recommended_fix=recommended_fix,
                doc_link=PRIVACY_MANIFEST_DOC_URL,
            )
        )
    return out
