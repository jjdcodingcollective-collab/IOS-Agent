"""
Entitlement scanner — Tier 1 Step 8.2.

Walks a web-archetype source tree for patterns that imply iOS entitlements
or Info.plist usage strings. The mapping is data-driven: rules live in
config/apple-entitlements.yaml.

This module mirrors converter/compliance/api_scanner.py in shape — same
walk infrastructure, same pattern types, same dedup contract — but emits
EntitlementFinding records instead of APIFinding. The entitlement
emitter (Step 8.3) consumes these findings to drive XcodeGen capability
flags and Info.plist usage-string injection.

Plan: plans/tier-1-step-8-xcode-project-generation.md (Step 8.2).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from wrapper.compatibility import _load_yaml  # type: ignore[attr-defined]

from .api_scanner import SOURCE_EXTENSIONS, SKIP_DIRS, ScannerError


_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "apple-entitlements.yaml"
)

_CAPACITOR_CONFIG_FILES = (
    "capacitor.config.ts",
    "capacitor.config.js",
    "capacitor.config.json",
)

PRODUCER = "compliance.entitlement_scanner"


@dataclass(frozen=True)
class EntitlementFinding:
    """A single match of an entitlement-bearing pattern in source.

    `entitlement_key` is the full Apple key (e.g. ``aps-environment``) or
    the empty string for permission-only capabilities (camera, location,
    etc.) that ride on Info.plist usage strings without a separate
    entitlement. `usage_strings` lists every NS*UsageDescription key the
    capability needs. `requires_developer_account` flags capabilities the
    developer must enable in their Apple Developer Account before the
    entitlement value will sign — these become Layer-A blockers in the
    report.

    `siwa_trigger` is True when the matched pattern is a third-party SSO
    that triggers the Guideline 4.8 SIWA parity requirement, rather than
    being a direct SIWA import that satisfies it.
    """

    entitlement_key: str
    capability: str
    label: str
    pattern: str
    pattern_type: str
    file: Path
    line: int
    snippet: str
    requires_developer_account: bool
    usage_strings: tuple[str, ...] = field(default_factory=tuple)
    siwa_trigger: bool = False


@dataclass(frozen=True)
class _EntitlementRule:
    """Internal: one rule-file entitlement, expanded for matching."""

    key: str
    label: str
    capability: str
    requires_developer_account: bool
    usage_strings: tuple[str, ...]
    pattern_type: str
    pattern: str
    regex: re.Pattern[str] | None  # None for capacitor_plugin
    siwa_trigger: bool = False


def load_rules(rules_path: Path | None = None) -> list[_EntitlementRule]:
    """Load entitlement rules from the catalogue file.

    Returns a flat list of rules, one per (entitlement, pattern) pair, so
    the matcher can iterate without nesting.
    """
    path = rules_path or _DEFAULT_RULES_PATH
    if not path.exists():
        raise ScannerError(f"entitlement rule file not found: {path}")

    try:
        text = path.read_text(encoding="utf-8")
        raw = _load_yaml(text)
    except Exception as exc:
        raise ScannerError(f"failed to parse {path}: {exc}") from exc

    entitlements = raw.get("entitlements") if isinstance(raw, dict) else None
    if not isinstance(entitlements, list):
        raise ScannerError(f"{path}: top-level 'entitlements' must be a list")

    rules: list[_EntitlementRule] = []
    for ent in entitlements:
        if not isinstance(ent, dict):
            continue
        key = ent.get("key", "")
        label = ent.get("label")
        capability = ent.get("capability")
        if not (isinstance(key, str) and isinstance(label, str) and isinstance(capability, str)):
            continue
        requires = bool(ent.get("requires_developer_account", False))
        usage = ent.get("usage_strings") or []
        if not isinstance(usage, list):
            continue
        usage_tuple = tuple(s for s in usage if isinstance(s, str))
        for entry in ent.get("patterns", []) or []:
            if not isinstance(entry, dict):
                continue
            ptype = entry.get("pattern_type")
            pval = entry.get("pattern")
            if not (isinstance(ptype, str) and isinstance(pval, str)):
                continue
            siwa_trigger = bool(entry.get("siwa_trigger", False))
            rules.append(
                _EntitlementRule(
                    key=key,
                    label=label,
                    capability=capability,
                    requires_developer_account=requires,
                    usage_strings=usage_tuple,
                    pattern_type=ptype,
                    pattern=pval,
                    regex=_compile_regex(ptype, pval),
                    siwa_trigger=siwa_trigger,
                )
            )
    return rules


def _compile_regex(pattern_type: str, pattern: str) -> re.Pattern[str] | None:
    if pattern_type == "capacitor_plugin":
        return None
    escaped = re.escape(pattern)
    return re.compile(rf"(?<![A-Za-z0-9_$]){escaped}(?![A-Za-z0-9_$])")


def scan_source(
    root: Path,
    *,
    rules_path: Path | None = None,
    rules: list[_EntitlementRule] | None = None,
) -> list[EntitlementFinding]:
    """Scan JS/TS source files under `root` for entitlement-bearing patterns."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    loaded = rules if rules is not None else load_rules(rules_path)
    source_rules = [r for r in loaded if r.pattern_type in ("js_api", "ts_import")]
    if not source_rules:
        return []

    findings: list[EntitlementFinding] = []
    for fpath in _walk_source_files(root):
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for rule in source_rules:
                assert rule.regex is not None
                if rule.regex.search(line):
                    findings.append(
                        EntitlementFinding(
                            entitlement_key=rule.key,
                            capability=rule.capability,
                            label=rule.label,
                            pattern=rule.pattern,
                            pattern_type=rule.pattern_type,
                            file=fpath,
                            line=line_num,
                            snippet=line.rstrip("\n").strip(),
                            requires_developer_account=rule.requires_developer_account,
                            usage_strings=rule.usage_strings,
                            siwa_trigger=rule.siwa_trigger,
                        )
                    )
    return findings


def scan_capacitor_plugins(
    root: Path,
    *,
    rules_path: Path | None = None,
    rules: list[_EntitlementRule] | None = None,
) -> list[EntitlementFinding]:
    """Detect declared Capacitor plugins that imply entitlements."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    loaded = rules if rules is not None else load_rules(rules_path)
    plugin_rules = {r.pattern: r for r in loaded if r.pattern_type == "capacitor_plugin"}
    if not plugin_rules:
        return []

    declared: dict[str, Path] = {}

    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name in (data.get(section) or {}):
                if name in plugin_rules and name not in declared:
                    declared[name] = pkg_json

    for fname in _CAPACITOR_CONFIG_FILES:
        cfg = root / fname
        if not cfg.exists():
            continue
        try:
            text = cfg.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for plugin_name in plugin_rules:
            if plugin_name in text and plugin_name not in declared:
                declared[plugin_name] = cfg

    findings: list[EntitlementFinding] = []
    for plugin_name, source_file in sorted(declared.items()):
        rule = plugin_rules[plugin_name]
        findings.append(
            EntitlementFinding(
                entitlement_key=rule.key,
                capability=rule.capability,
                label=rule.label,
                pattern=plugin_name,
                pattern_type="capacitor_plugin",
                file=source_file,
                line=0,
                snippet=f"declared plugin: {plugin_name}",
                requires_developer_account=rule.requires_developer_account,
                usage_strings=rule.usage_strings,
                siwa_trigger=rule.siwa_trigger,
            )
        )
    return findings


def scan_all(
    root: Path,
    *,
    rules_path: Path | None = None,
) -> list[EntitlementFinding]:
    """Run both passes, dedup, then apply SIWA parity rewriting."""
    rules = load_rules(rules_path)
    src = scan_source(root, rules=rules)
    plugins = scan_capacitor_plugins(root, rules=rules)
    return _apply_siwa_parity(_dedupe(src + plugins))


def _apply_siwa_parity(
    findings: list[EntitlementFinding],
) -> list[EntitlementFinding]:
    """Rewrite SIWA findings to reflect the Guideline 4.8 parity state.

    Three cases for the SignInWithApple capability:
    1. No SIWA findings at all → nothing to do.
    2. Only siwa_trigger=True findings (third-party SSO, no SIWA) →
       keep all trigger findings but mark them as
       siwa_trigger=True so to_findings() emits the correct "SIWA required"
       message instead of the generic "enable capability" message.
    3. siwa_trigger=False findings present (direct SIWA import) →
       the requirement is satisfied; drop all trigger-only findings for
       the SIWA capability so the report is clean.
    """
    siwa_cap = "SignInWithApple"
    siwa_findings = [f for f in findings if f.capability == siwa_cap]
    if not siwa_findings:
        return findings

    has_direct = any(not f.siwa_trigger for f in siwa_findings)
    if has_direct:
        # SIWA present — drop trigger-only findings, keep direct ones.
        return [
            f for f in findings
            if not (f.capability == siwa_cap and f.siwa_trigger)
        ]
    # Only triggers, no direct SIWA — keep all (to_findings sees siwa_trigger=True).
    return findings


def _dedupe(findings: list[EntitlementFinding]) -> list[EntitlementFinding]:
    """Collapse multiple matches of the same (capability, pattern, file) tuple.

    Multiple call sites of getUserMedia in the same file should not produce
    multiple Camera findings — first occurrence wins for the location. The
    capability still surfaces once per source file so the developer knows
    *where* it appeared, but we don't carpet-bomb the report with one
    finding per line.
    """
    seen: dict[tuple[str, str, str], EntitlementFinding] = {}
    for f in findings:
        key = (f.capability, f.pattern, str(f.file))
        if key not in seen:
            seen[key] = f
    return sorted(
        seen.values(),
        key=lambda f: (f.capability, str(f.file), f.line, f.pattern),
    )


def _walk_source_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.suffix in SOURCE_EXTENSIONS:
                yield fpath


# --- Three-layer report adapter (Step 8.4) -----------------------------------
#
# Bridges EntitlementFinding to converter.report.Finding so the wrapper can
# accumulate entitlement findings into the same ReportBuilder Step 6 uses.

ENTITLEMENT_DOC_URL = (
    "https://developer.apple.com/documentation/bundleresources/entitlements"
)


def to_findings(
    entitlement_findings: Iterable[EntitlementFinding],
    *,
    source_root: Path | None = None,
) -> list["Finding"]:  # noqa: F821 — forward ref, lazy-imported
    """Convert EntitlementFinding records into report Finding records.

    Findings whose capability requires Apple-Developer-Account configuration
    are emitted as Layer-A blockers. Permission-prompted capabilities (camera,
    location, etc.) are emitted as Layer-B warnings — the app builds without
    them, but the OS will terminate the process the first time the API is
    called without an Info.plist usage string.
    """
    from converter.report import Finding

    out: list[Finding] = []
    counters: dict[str, int] = {}
    # One report finding per capability — plugin + source for the same
    # capability (e.g. @capacitor/push-notifications imported AND declared)
    # collapses into a single Layer-A entry. The first finding's location
    # wins; subsequent matches are dropped.
    seen_caps: set[str] = set()
    for ef in entitlement_findings:
        slug = ef.capability.lower()
        if slug in seen_caps:
            continue
        seen_caps.add(slug)
        idx = counters.get(slug, 0)
        counters[slug] = idx + 1
        finding_id = f"compliance.entitlement.{slug}#{idx}"

        if ef.pattern_type == "capacitor_plugin":
            file_str = "(plugins)"
            line = 0
            reason_lead = (
                f"Capacitor plugin `{ef.pattern}` requires the {ef.label} capability"
            )
        else:
            if source_root is not None:
                root_abs = source_root.resolve()
                file_abs = ef.file.resolve()
                try:
                    file_str = str(file_abs.relative_to(root_abs))
                except ValueError:
                    file_str = str(ef.file)
            else:
                file_str = str(ef.file)
            line = ef.line
            reason_lead = (
                f"Source uses `{ef.pattern}`, which requires the {ef.label} capability"
            )

        if ef.requires_developer_account and ef.siwa_trigger:
            severity = "blocker"
            reason = (
                f"{reason_lead}, which is a third-party login. Apple Guideline 4.8 "
                f"requires Sign in with Apple parity: any app that offers a "
                f"third-party login (Google, Facebook, etc.) must also offer "
                f"Sign in with Apple as an equivalent option."
            )
            recommended_fix = (
                "Add Sign in with Apple as a login option:\n"
                "1. Enable the SignInWithApple capability in your Apple Developer "
                "Account at https://developer.apple.com/account/resources/identifiers/\n"
                "2. Add `@capacitor-community/apple-sign-in` (or an equivalent) "
                "to your project.\n"
                "3. Present the SIWA button alongside your existing login options."
            )
        elif ef.requires_developer_account:
            severity = "blocker"
            reason = (
                f"{reason_lead}. The {ef.label} capability must be enabled in "
                f"your Apple Developer Account before the build will sign."
            )
            recommended_fix = (
                f"Enable the {ef.label} capability for your app id at "
                f"https://developer.apple.com/account/resources/identifiers/, "
                f"then run `xcodegen generate` again."
            )
        else:
            severity = "warning"
            usage_list = ", ".join(ef.usage_strings) if ef.usage_strings else "(none)"
            reason = (
                f"{reason_lead}. iOS will terminate the process the first time "
                f"this API is called unless Info.plist contains: {usage_list}."
            )
            recommended_fix = (
                "The emitter inserts placeholder usage strings; replace them "
                "with descriptions that explain *why* your app needs the data. "
                "Apple soft-rejects boilerplate strings on review."
            )

        out.append(
            Finding(
                id=finding_id,
                category=f"compliance.entitlement.{slug}",
                severity=severity,
                producer=PRODUCER,
                file=file_str,
                line=line,
                original_snippet=ef.snippet,
                attempted_translation=None,
                reason=reason,
                recommended_fix=recommended_fix,
                doc_link=ENTITLEMENT_DOC_URL,
            )
        )
    return out
