"""
Wrapper-level compliance orchestration — Tier 1 Step 6.6.

Runs the required-reason API scanner against the user's source tree and
emits a PrivacyInfo.xcprivacy into the conversion output directory.
Surfaces any failure as a wrapper-level warning rather than a hard fail
— Step 7 (the pre-flight scanner) is what gates ship.

Plan: plans/tier-1-step-6-privacy-scanner.md (Step 6.6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from converter.compliance import (
    APIFinding,
    ATTFinding,
    ManifestError,
    ScannerError,
    generate_manifest,
    scan_all,
    scan_all_att,
    to_findings,
    to_att_findings,
)
from converter.compliance.ats_scanner import (
    ATSFinding,
    scan_all_ats,
    to_ats_findings,
)
from converter.compliance.min_functionality_checker import (
    MinFuncFinding,
    check_min_functionality,
    to_min_func_findings,
)

if TYPE_CHECKING:
    from converter.report import ReportBuilder


# Override file the developer can drop next to their source tree.
OVERRIDES_FILENAME = "privacy-overrides.yaml"

# Where the manifest lands in the conversion output. Step 8 (Xcode
# project generation) will place a copy inside the generated project's
# App/ directory; for now this is the canonical location.
MANIFEST_FILENAME = "PrivacyInfo.xcprivacy"


@dataclass(frozen=True)
class ComplianceResult:
    manifest_path: Path | None
    findings: list[APIFinding]
    att_findings: list[ATTFinding] = None  # type: ignore[assignment]
    ats_findings: list[ATSFinding] = None  # type: ignore[assignment]
    min_func_finding: MinFuncFinding | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.att_findings is None:
            object.__setattr__(self, "att_findings", [])
        if self.ats_findings is None:
            object.__setattr__(self, "ats_findings", [])

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.manifest_path is not None


def run_compliance_step(
    *,
    source_dir: Path,
    output_dir: Path,
    brief: bool = False,
    report_builder: "ReportBuilder | None" = None,
) -> ComplianceResult:
    """Scan source, generate PrivacyInfo.xcprivacy, print a summary.

    Returns a ComplianceResult. Never raises — any failure is surfaced
    via the `error` field and printed as a warning. The wrapper continues
    past compliance issues because Step 7's pre-flight scanner is the
    ship-gate, not this step.

    When `report_builder` is supplied, scanner findings are also pushed
    into it as Layer A blockers via `to_findings()`. The one-line summary
    print happens unconditionally so existing CLI output is unchanged.
    """
    overrides = source_dir / OVERRIDES_FILENAME
    overrides_path = overrides if overrides.exists() else None

    try:
        findings = scan_all(source_dir)
    except ScannerError as exc:
        msg = f"compliance scan failed: {exc}"
        print(f"warning: {msg}")
        return ComplianceResult(manifest_path=None, findings=[], att_findings=[], error=msg)

    try:
        att_findings = scan_all_att(source_dir)
    except ScannerError as exc:
        msg = f"ATT scan failed: {exc}"
        print(f"warning: {msg}")
        att_findings = []

    try:
        ats_findings = scan_all_ats(source_dir)
    except ScannerError as exc:
        msg = f"ATS scan failed: {exc}"
        print(f"warning: {msg}")
        ats_findings = []

    manifest_path = output_dir / MANIFEST_FILENAME
    try:
        generate_manifest(
            findings,
            output_path=manifest_path,
            overrides_path=overrides_path,
        )
    except ManifestError as exc:
        msg = f"privacy manifest generation failed: {exc}"
        print(f"warning: {msg}")
        return ComplianceResult(manifest_path=None, findings=findings, att_findings=att_findings, ats_findings=ats_findings, error=msg)

    min_func_finding = check_min_functionality(source_dir)

    if report_builder is not None:
        for f in to_findings(findings, source_root=source_dir):
            report_builder.add_blocker(f)
        for f in to_att_findings(att_findings, source_root=source_dir):
            report_builder.add_blocker(f)
        for f in to_ats_findings(ats_findings, source_root=source_dir):
            report_builder.add_manual_review(f)
        for f in to_min_func_findings(min_func_finding):
            report_builder.add_manual_review(f)

    _print_summary(findings, att_findings, ats_findings, min_func_finding, manifest_path, overrides_path, brief=brief)
    return ComplianceResult(manifest_path=manifest_path, findings=findings, att_findings=att_findings, ats_findings=ats_findings, min_func_finding=min_func_finding)


def _print_summary(
    findings: list[APIFinding],
    att_findings: list[ATTFinding],
    ats_findings: list[ATSFinding],
    min_func_finding: MinFuncFinding | None,
    manifest_path: Path,
    overrides_path: Path | None,
    *,
    brief: bool,
) -> None:
    counts = Counter(f.category for f in findings)
    n_findings = len(findings)
    n_categories = len(counts)
    overrides_note = (
        f" (with overrides from {overrides_path.name})"
        if overrides_path is not None
        else ""
    )
    print(
        f"privacy manifest: {n_findings} finding(s) across "
        f"{n_categories} categor{'y' if n_categories == 1 else 'ies'}"
        f"{overrides_note} → {manifest_path.name}"
    )

    if not brief and findings:
        for category, count in sorted(counts.items()):
            short = category.removeprefix("NSPrivacyAccessedAPICategory")
            print(f"  - {short}: {count}")

    if att_findings:
        n_att = len(att_findings)
        print(f"ATT/IDFA: {n_att} finding(s) — NSUserTrackingUsageDescription required")
        if not brief:
            direct = sum(1 for f in att_findings if f.reason_code == "ATT.1")
            transitive = sum(1 for f in att_findings if f.reason_code == "ATT.2")
            if direct:
                print(f"  - direct ATT/IDFA calls: {direct}")
            if transitive:
                print(f"  - transitive via analytics SDK: {transitive}")

    if ats_findings:
        n_http = sum(1 for f in ats_findings if f.kind == "http_url")
        n_arb = sum(1 for f in ats_findings if f.kind == "arbitrary_loads")
        print(f"ATS: {len(ats_findings)} warning(s) — http:// URLs or allowsArbitraryLoads detected (Layer B)")
        if not brief:
            if n_http:
                print(f"  - hardcoded http:// URLs: {n_http}")
            if n_arb:
                print(f"  - allowsArbitraryLoads: {n_arb}")

    if min_func_finding is not None:
        print(
            f"min-functionality: static wrapper detected — "
            f"{min_func_finding.route_count} route(s), 0 plugins, "
            f"0 usage keys (Guideline 4.2, Layer B)"
        )
