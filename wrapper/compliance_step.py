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

from converter.compliance import (
    APIFinding,
    ManifestError,
    ScannerError,
    generate_manifest,
    scan_all,
)


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
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.manifest_path is not None


def run_compliance_step(
    *,
    source_dir: Path,
    output_dir: Path,
    brief: bool = False,
) -> ComplianceResult:
    """Scan source, generate PrivacyInfo.xcprivacy, print a summary.

    Returns a ComplianceResult. Never raises — any failure is surfaced
    via the `error` field and printed as a warning. The wrapper continues
    past compliance issues because Step 7's pre-flight scanner is the
    ship-gate, not this step.
    """
    overrides = source_dir / OVERRIDES_FILENAME
    overrides_path = overrides if overrides.exists() else None

    try:
        findings = scan_all(source_dir)
    except ScannerError as exc:
        msg = f"compliance scan failed: {exc}"
        print(f"warning: {msg}")
        return ComplianceResult(manifest_path=None, findings=[], error=msg)

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
        return ComplianceResult(manifest_path=None, findings=findings, error=msg)

    _print_summary(findings, manifest_path, overrides_path, brief=brief)
    return ComplianceResult(manifest_path=manifest_path, findings=findings)


def _print_summary(
    findings: list[APIFinding],
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

    if brief or not findings:
        return

    for category, count in sorted(counts.items()):
        short = category.removeprefix("NSPrivacyAccessedAPICategory")
        print(f"  - {short}: {count}")
