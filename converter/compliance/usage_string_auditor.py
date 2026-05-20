"""
Usage string completeness auditor — MVP §4.5.

Reads a generated Info.plist and flags any NS*UsageDescription entry
whose value is a placeholder or empty string. Apple hard-rejects apps
where required usage strings are absent (the OS terminates the process
on first API call), and soft-rejects apps where the description is
boilerplate that doesn't explain the actual use.

This auditor runs *after* the XcodeGen emitter has written Info.plist so
it can verify the emitter's output. Findings are Layer-A blockers —
a placeholder description is functionally equivalent to a missing one.

Plan: plans/mvp-section-4-compliance.md (Step 4.5).
"""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Keys we care about — all NS*UsageDescription keys Apple validates.
# The scanner flags any of these whose value matches a placeholder pattern.
_USAGE_DESCRIPTION_SUFFIX = "UsageDescription"

# Patterns that identify a string as a placeholder rather than a real desc.
# Matched case-insensitively against the full value.
_PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*$"),                            # empty / whitespace only
    re.compile(r"\bTODO\b", re.IGNORECASE),          # our emitter's sentinel
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bXXX\b"),
    re.compile(r"auto.generated", re.IGNORECASE),    # our emitter includes this
    re.compile(r"replaces the auto.generated", re.IGNORECASE),
    re.compile(r"<describe\b", re.IGNORECASE),        # common template pattern
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"^This app (uses|needs|requires|accesses)\s*\.$", re.IGNORECASE),
]

# Apple doc for NS*UsageDescription keys.
USAGE_STRING_DOC_URL = (
    "https://developer.apple.com/documentation/bundleresources/information_property_list"
    "/protected_resources"
)

PRODUCER = "compliance.usage_string_auditor"


class AuditorError(Exception):
    """Raised when the auditor cannot parse the Info.plist."""


@dataclass(frozen=True)
class UsageStringFinding:
    """A single NS*UsageDescription key whose value is a placeholder."""

    key: str          # e.g. NSCameraUsageDescription
    value: str        # the placeholder value found
    plist_path: Path  # path to the Info.plist file audited


def _is_placeholder(value: str) -> bool:
    return any(p.search(value) for p in _PLACEHOLDER_PATTERNS)


def audit_info_plist(plist_path: Path) -> list[UsageStringFinding]:
    """Parse `plist_path` and return findings for placeholder usage strings.

    Raises AuditorError if the file cannot be parsed as a plist.
    Returns an empty list if the file does not exist (no plist = no usage
    strings = nothing to audit; the emitter's own placeholder-findings
    cover the "missing plist" case).
    """
    plist_path = Path(plist_path)
    if not plist_path.exists():
        return []

    try:
        with plist_path.open("rb") as f:
            data = plistlib.load(f)
    except Exception as exc:
        raise AuditorError(f"cannot parse {plist_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AuditorError(f"{plist_path}: root object is not a dict")

    findings: list[UsageStringFinding] = []
    for key, value in data.items():
        if not key.endswith(_USAGE_DESCRIPTION_SUFFIX):
            continue
        if not isinstance(value, str):
            continue
        if _is_placeholder(value):
            findings.append(
                UsageStringFinding(key=key, value=value, plist_path=plist_path)
            )
    return findings


# --- Three-layer report adapter ----------------------------------------------


def to_usage_findings(
    audit_findings: Iterable[UsageStringFinding],
) -> list["Finding"]:  # noqa: F821
    """Convert UsageStringFinding records into Layer-A report Finding records."""
    from converter.report import Finding

    out: list[Finding] = []
    for i, af in enumerate(audit_findings):
        key_slug = af.key.lower().replace("ns", "", 1)
        finding_id = f"compliance.usage-string.{key_slug}#{i}"
        out.append(
            Finding(
                id=finding_id,
                category=f"compliance.usage-string.{key_slug}",
                severity="blocker",
                producer=PRODUCER,
                file=str(af.plist_path),
                line=0,
                original_snippet=f"{af.key} = \"{af.value[:60]}\"",
                attempted_translation=None,
                reason=(
                    f"`{af.key}` in Info.plist contains a placeholder value. "
                    f"Apple requires a plain-English explanation of *why* the app "
                    f"needs this access — boilerplate or TODO strings cause "
                    f"App Store review rejection."
                ),
                recommended_fix=(
                    f"Replace the value of `{af.key}` in Info.plist with a "
                    f"specific, user-facing description. Example for camera: "
                    f"\"We use your camera to scan QR codes for quick sign-in.\" "
                    f"Apple rejects generic strings like \"This app uses your camera.\""
                ),
                doc_link=USAGE_STRING_DOC_URL,
            )
        )
    return out
