"""
Developer disclaimer and sign-off flow — MVP DoD §9.1.

Shows a required disclaimer before any conversion runs. The developer must
actively acknowledge it. Acknowledgement is persisted to a dotfile so the
prompt only fires once per machine.

Pass --yes / -y on the command line to skip the interactive prompt (for CI
and scripted use). The disclaimer is still printed in that case.

Acknowledgement is logged with a timestamp and the disclaimer version so
legal can audit that the current text was accepted.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# Bump this whenever the disclaimer text changes materially. Any machine that
# acknowledged an older version will be re-prompted.
DISCLAIMER_VERSION = "1.0"

# Where acknowledgements are persisted. One JSON record per version.
_DOTFILE = Path.home() / ".ios-agent" / "disclaimer-accepted.json"

DISCLAIMER_TEXT = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ios-agent — Developer Disclaimer                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

This tool generates best-effort App Store compliance scaffolding for your web
application. By proceeding you acknowledge the following:

1. NO GUARANTEE OF APP STORE APPROVAL
   ios-agent automates compliance checks based on known Apple guidelines as of
   its last update. Apple's review process is discretionary. The tool cannot
   guarantee that any converted app will be approved, and approval of one
   version does not guarantee approval of future versions.

2. DEVELOPER RESPONSIBILITY
   Final responsibility for App Store submission, compliance with Apple's
   Developer Program License Agreement, and any regulatory requirements
   (export compliance, privacy laws, COPPA, GDPR, etc.) rests entirely with
   the developer submitting the app.

3. TOOL OUTPUT REQUIRES HUMAN REVIEW
   All generated files — including PrivacyInfo.xcprivacy, Info.plist, and
   project.yml — must be reviewed and validated by a qualified developer
   before submission. Placeholder values (bundle ID, team ID, usage strings)
   MUST be replaced with accurate information.

4. COMPLIANCE RULES MAY BE STALE
   Apple updates its guidelines continuously. The compliance rule data files
   in config/ reflect requirements as of the tool's last release. Check
   CHANGELOG.md for the rule-update date and review Apple's latest guidelines
   before submitting.

5. NO WARRANTY
   This software is provided "as is", without warranty of any kind. See
   LICENSE for the full MIT license terms.

For legal questions, consult your own counsel. This disclaimer is pending
formal legal review (MVP DoD §9.1) — text is subject to change.
"""


def show_and_confirm(*, assume_yes: bool) -> bool:
    """Print the disclaimer and return True if the developer accepts.

    When `assume_yes` is True (--yes / -y flag), the disclaimer is printed
    but the prompt is skipped and True is returned automatically. This allows
    CI pipelines to run without interaction while still surfacing the text.

    Returns False if the developer declines (interactive only).
    """
    print(DISCLAIMER_TEXT)

    if _already_accepted():
        accepted_at = _accepted_at()
        print(f"[disclaimer v{DISCLAIMER_VERSION} previously accepted {accepted_at}]")
        print()
        return True

    if assume_yes:
        print(f"[disclaimer v{DISCLAIMER_VERSION} auto-accepted via --yes]")
        print()
        _record_acceptance(via="--yes")
        return True

    if not sys.stdin.isatty():
        print(
            "error: disclaimer must be acknowledged interactively or via --yes",
            file=sys.stderr,
        )
        return False

    answer = input(
        "Type 'agree' to acknowledge and continue, or anything else to abort: "
    ).strip().lower()
    print()

    if answer == "agree":
        _record_acceptance(via="interactive")
        return True

    print("Aborted — disclaimer not accepted.")
    return False


def _dotfile_path() -> Path:
    return _DOTFILE


def _already_accepted() -> bool:
    data = _load_dotfile()
    return DISCLAIMER_VERSION in data


def _accepted_at() -> str:
    data = _load_dotfile()
    entry = data.get(DISCLAIMER_VERSION, {})
    return entry.get("accepted_at", "unknown")


def _record_acceptance(*, via: str) -> None:
    data = _load_dotfile()
    data[DISCLAIMER_VERSION] = {
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "via": via,
        "tool_version": _tool_version(),
    }
    _dotfile_path().parent.mkdir(parents=True, exist_ok=True)
    _dotfile_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_dotfile() -> dict:
    try:
        return json.loads(_dotfile_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _tool_version() -> str:
    try:
        from importlib.metadata import version
        return version("ios-agent")
    except Exception:
        return "unknown"
