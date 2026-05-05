"""
Wrapper-level Xcode project orchestration — Tier 1 Step 8.4.

Runs the entitlement scanner against the user's source tree, builds an
``XcodeSpec``, and calls ``emit_xcode_project`` to drop a buildable
XcodeGen spec + supporting files into the conversion output directory.
Routes every entitlement and placeholder finding into the same
``ReportBuilder`` the compliance step populates so ``report.md`` lists
all Layer-A blockers in one pass.

Plan: plans/tier-1-step-8-xcode-project-generation.md (Step 8.4).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from converter.compliance import (
    EntitlementFinding,
    ScannerError,
    entitlement_to_findings,
    scan_all_entitlements,
)
from converter.xcode_project import (
    EmitResult,
    EmitterError,
    XcodeSpec,
    emit_xcode_project,
)

if TYPE_CHECKING:
    from converter.report import ReportBuilder


# Where the privacy manifest lives in the conversion output. Must match
# wrapper/compliance_step.py — the emitter checks for this filename to set
# ``has_privacy_manifest`` on the XcodeSpec.
PRIVACY_MANIFEST_FILENAME = "PrivacyInfo.xcprivacy"


@dataclass(frozen=True)
class XcodeStepResult:
    """What the wrapper's xcode step produced.

    ``project_yml`` is None when the emitter raised before writing it; the
    wrapper surfaces that as a warning rather than failing the run.
    """

    project_yml: Path | None
    entitlement_findings: list[EntitlementFinding]
    emit_result: EmitResult | None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.project_yml is not None


def run_xcode_step(
    *,
    source_dir: Path,
    output_dir: Path,
    app_name: str,
    bundle_id: str,
    team_id: str,
    brief: bool = False,
    report_builder: "ReportBuilder | None" = None,
) -> XcodeStepResult:
    """Scan for entitlements, emit the XcodeGen spec, accumulate findings.

    Returns an XcodeStepResult. Never raises — failures surface via the
    ``error`` field and a warning print. Step 7's pre-flight scanner is the
    ship-gate, not this step.

    When ``report_builder`` is supplied, both entitlement findings and the
    emitter's placeholder findings are pushed into it. Severity routes the
    add-call: ``blocker`` → ``add_blocker``, ``warning`` → ``add_manual_review``.
    """
    try:
        ent_findings = scan_all_entitlements(source_dir)
    except ScannerError as exc:
        msg = f"entitlement scan failed: {exc}"
        print(f"warning: {msg}")
        return XcodeStepResult(
            project_yml=None,
            entitlement_findings=[],
            emit_result=None,
            error=msg,
        )

    spec = XcodeSpec(
        app_name=app_name,
        bundle_id=bundle_id,
        team_id=team_id,
        entitlements=tuple(ent_findings),
        has_privacy_manifest=(output_dir / PRIVACY_MANIFEST_FILENAME).exists(),
    )

    try:
        emit_result = emit_xcode_project(spec=spec, output_dir=output_dir)
    except EmitterError as exc:
        msg = f"xcode project emission failed: {exc}"
        print(f"warning: {msg}")
        return XcodeStepResult(
            project_yml=None,
            entitlement_findings=ent_findings,
            emit_result=None,
            error=msg,
        )

    if report_builder is not None:
        for f in entitlement_to_findings(ent_findings, source_root=source_dir):
            if f.severity == "blocker":
                report_builder.add_blocker(f)
            else:
                report_builder.add_manual_review(f)
        for f in emit_result.findings:
            if f.severity == "blocker":
                report_builder.add_blocker(f)
            else:
                report_builder.add_manual_review(f)

    project_yml = output_dir / "project.yml"
    _print_summary(ent_findings, emit_result, project_yml, brief=brief)
    return XcodeStepResult(
        project_yml=project_yml,
        entitlement_findings=ent_findings,
        emit_result=emit_result,
    )


def _print_summary(
    ent_findings: list[EntitlementFinding],
    emit_result: EmitResult,
    project_yml: Path,
    *,
    brief: bool,
) -> None:
    cap_counts = Counter(f.capability for f in ent_findings)
    n_caps = len(cap_counts)
    n_placeholders = len(emit_result.findings)
    n_files = len(emit_result.files_written)
    print(
        f"xcode project: {n_caps} capabilit{'y' if n_caps == 1 else 'ies'}, "
        f"{n_placeholders} placeholder finding(s), "
        f"{n_files} file(s) → {project_yml.name}"
    )

    if brief or not ent_findings:
        return

    for cap, count in sorted(cap_counts.items()):
        print(f"  - {cap}: {count}")
