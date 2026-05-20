"""
Pre-flight compliance scanner — MVP gap §6.2.

Runs the privacy and entitlement scanners against a source tree **without**
converting or writing any output files. Returns a ``PreflightResult`` that
tells the caller whether the source is safe to proceed.

Design contract:
  - Reads source files; writes nothing to disk.
  - Returns a ``PreflightResult`` dataclass; never raises from user-facing
    errors (scanner failures surface via the ``errors`` list).
  - Callers drive output: ``format_preflight_report()`` builds the human-
    readable text; the subcommand owns printing + exit codes.

Exit-code contract (for the CLI layer, not enforced here):
  0  — no Layer-A blockers found; safe to convert
  1  — Layer-A blockers found; App Store submission would be rejected
  2  — scanner / IO error; could not complete the scan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from converter.compliance import (
    APIFinding,
    ATTFinding,
    EntitlementFinding,
    ScannerError,
    scan_all,
    scan_all_att,
    scan_all_entitlements,
    to_findings,
    to_att_findings,
    entitlement_to_findings,
)
from converter.report import Finding

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of a pre-flight scan.

    ``blockers``  — Layer-A findings that *will* cause App Store rejection.
    ``warnings``  — Layer-B findings that require human review.
    ``api_findings``      — raw APIFinding objects from the privacy scanner.
    ``ent_findings``      — raw EntitlementFinding objects from the entitlement scanner.
    ``errors``    — scanner-level errors (rules file missing, root not found, etc.).
                    Non-empty means the scan was incomplete; treat as exit code 2.
    """

    blockers: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    api_findings: list[APIFinding] = field(default_factory=list)
    ent_findings: list[EntitlementFinding] = field(default_factory=list)
    att_findings: list[ATTFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def scan_failed(self) -> bool:
        return bool(self.errors)

    @property
    def has_blockers(self) -> bool:
        return bool(self.blockers)

    @property
    def exit_code(self) -> int:
        if self.scan_failed:
            return 2
        if self.has_blockers:
            return 1
        return 0


def run_preflight(source_dir: Path) -> PreflightResult:
    """Scan ``source_dir`` for App Store compliance issues.

    Runs the privacy API scanner and the entitlement scanner in sequence.
    If either raises ``ScannerError``, the error is captured and scanning
    continues with the other (partial results are still useful).

    Returns a ``PreflightResult``. Never raises.
    """
    source_dir = source_dir.resolve()

    api_findings: list[APIFinding] = []
    ent_findings: list[EntitlementFinding] = []
    att_findings: list[ATTFinding] = []
    errors: list[str] = []

    try:
        api_findings = scan_all(source_dir)
    except ScannerError as exc:
        errors.append(f"privacy scanner: {exc}")

    try:
        ent_findings = scan_all_entitlements(source_dir)
    except ScannerError as exc:
        errors.append(f"entitlement scanner: {exc}")

    try:
        att_findings = scan_all_att(source_dir)
    except ScannerError as exc:
        errors.append(f"ATT scanner: {exc}")

    # Convert raw findings to report Finding objects and route by severity.
    blockers: list[Finding] = []
    warnings: list[Finding] = []

    for f in to_findings(api_findings, source_root=source_dir):
        blockers.append(f)

    for f in entitlement_to_findings(ent_findings, source_root=source_dir):
        if f.severity == "blocker":
            blockers.append(f)
        else:
            warnings.append(f)

    for f in to_att_findings(att_findings, source_root=source_dir):
        blockers.append(f)

    return PreflightResult(
        blockers=blockers,
        warnings=warnings,
        api_findings=api_findings,
        ent_findings=ent_findings,
        att_findings=att_findings,
        errors=errors,
    )


def format_preflight_report(result: PreflightResult, source_dir: Path, *, brief: bool = False) -> str:
    """Render the pre-flight result as a human-readable string.

    ``brief=True`` suppresses per-finding detail; only the verdict line and
    counts are shown. Designed to match the wrapper's existing output style.
    """
    lines: list[str] = []

    # Header
    lines.append(f"Pre-flight scan: {source_dir}")
    lines.append("")

    # Scan errors first (incomplete scan is worse than blockers).
    if result.errors:
        lines.append("Scan errors (scan may be incomplete):")
        for err in result.errors:
            lines.append(f"  ✗ {err}")
        lines.append("")

    # Privacy API findings
    n_api = len(result.api_findings)
    if n_api:
        lines.append(f"Privacy APIs detected ({n_api} finding{'s' if n_api != 1 else ''}):")
        if not brief:
            seen: set[str] = set()
            for f in result.api_findings:
                key = f.category
                if key not in seen:
                    seen.add(key)
                    short = f.category.removeprefix("NSPrivacyAccessedAPICategory")
                    lines.append(f"  • {short} — requires PrivacyInfo.xcprivacy reason code")
        lines.append("")

    # ATT / IDFA findings
    n_att = len(result.att_findings)
    if n_att:
        lines.append(f"ATT/IDFA detected ({n_att} finding{'s' if n_att != 1 else ''}):")
        if not brief:
            direct = [f for f in result.att_findings if f.reason_code == "ATT.1"]
            transitive = [f for f in result.att_findings if f.reason_code == "ATT.2"]
            seen_att: set[str] = set()
            for f in direct:
                if f.pattern not in seen_att:
                    seen_att.add(f.pattern)
                    lines.append(f"  ✗ {f.pattern} — direct ATT/IDFA call (Guideline 5.1.2)")
            sdk_seen: set[str] = set()
            for f in transitive:
                if f.pattern not in sdk_seen:
                    sdk_seen.add(f.pattern)
                    lines.append(f"  ✗ {f.pattern} — reads IDFA transitively (NSUserTrackingUsageDescription required)")
        lines.append("")

    # Entitlement findings
    n_ent = len(result.ent_findings)
    if n_ent:
        blocker_ents = [f for f in result.ent_findings if f.requires_developer_account]
        warning_ents = [f for f in result.ent_findings if not f.requires_developer_account]
        lines.append(f"Entitlements detected ({n_ent} finding{'s' if n_ent != 1 else ''}):")
        if not brief:
            if blocker_ents:
                lines.append("  Requires Apple Developer account provisioning (Layer A):")
                seen_caps: set[str] = set()
                for f in blocker_ents:
                    if f.capability not in seen_caps:
                        seen_caps.add(f.capability)
                        lines.append(f"    ✗ {f.label} ({f.capability})")
            if warning_ents:
                lines.append("  Requires permission usage string (Layer B):")
                seen_caps2: set[str] = set()
                for f in warning_ents:
                    if f.capability not in seen_caps2:
                        seen_caps2.add(f.capability)
                        lines.append(f"    ⚠ {f.label} ({f.capability})")
        lines.append("")

    # Verdict
    n_blockers = len(result.blockers)
    n_warnings = len(result.warnings)

    if result.scan_failed and not result.api_findings and not result.ent_findings:
        lines.append("Verdict: SCAN INCOMPLETE — fix errors above and re-run.")
    elif result.has_blockers:
        lines.append(
            f"Verdict: BLOCKED — {n_blockers} Layer-A blocker{'s' if n_blockers != 1 else ''} "
            f"will cause App Store rejection."
        )
        if n_warnings:
            lines.append(f"         {n_warnings} Layer-B warning{'s' if n_warnings != 1 else ''} also require attention.")
        if not brief:
            lines.append("")
            lines.append("Next steps:")
            lines.append("  1. Add required reason codes to PrivacyInfo.xcprivacy")
            lines.append("     (see: https://developer.apple.com/documentation/bundleresources/privacy_manifest_files/describing_use_of_required_reason_api)")
            lines.append("  2. Provision entitlements that require a Developer Account")
            lines.append("     (see: https://developer.apple.com/account/resources/)")
            if result.att_findings:
                lines.append("  3. Add NSUserTrackingUsageDescription to Info.plist and integrate")
                lines.append("     ATTrackingManager.requestTrackingAuthorization (Guideline 5.1.2)")
                lines.append("     (see: https://developer.apple.com/documentation/apptrackingtransparency)")
                lines.append("  4. Re-run: python -m wrapper preflight <path>")
            else:
                lines.append("  3. Re-run: python -m wrapper preflight <path>")
    else:
        lines.append("Verdict: CLEAR")
        if n_warnings:
            lines.append(
                f"         {n_warnings} Layer-B warning{'s' if n_warnings != 1 else ''} "
                f"require review before submission."
            )
        else:
            lines.append("         No blockers. Safe to proceed with conversion.")

    return "\n".join(lines)
