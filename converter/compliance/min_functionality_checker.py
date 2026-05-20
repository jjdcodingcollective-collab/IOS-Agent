"""
Minimum functionality heuristic — MVP §4.2.

Apple Guideline 4.2 rejects apps that are "simple file readers, viewers,
or content containers with no direct benefit to the user beyond what a
web app provides." This checker detects the classic failure pattern: a
pure static wrapper with no native integrations and almost no navigation.

Three signals, all required to fire:
  1. Zero Capacitor plugin imports in source (no native capability).
  2. Zero NS*UsageDescription keys in any Info.plist candidate (no
     permission-gated feature).
  3. Three or fewer distinct route/screen definitions in source (minimal
     navigation = low user value).

Each signal alone is fine — a camera app has zero routes; a simple
reader legitimately has zero plugins but rich navigation. Only the
combination flags a likely static wrapper.

The finding is Layer-B (manual review) because the heuristic cannot
know the app's design intent. The developer must add native value or
justify the submission via App Review notes.

Plan: plans/mvp-section-4-compliance.md (Step 4.2).
"""

from __future__ import annotations

import re
import plistlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .api_scanner import SOURCE_EXTENSIONS, SKIP_DIRS, _walk_source_files

MIN_FUNC_DOC_URL = (
    "https://developer.apple.com/app-store/review/guidelines/#minimum-functionality"
)

PRODUCER = "compliance.min_functionality_checker"

# Any @capacitor/* or capacitor-* import indicates native plugin usage.
# Covers: import X from 'pkg', import { X } from 'pkg', require('pkg').
_CAPACITOR_PLUGIN_RE = re.compile(
    r"""(?:from|import|require)\s*\(?['"`](@capacitor/[\w-]+|capacitor-[\w-]+)['"`]\)?"""
)

# Route/screen definitions — covers React Router, Vue Router, Expo Router,
# Next.js page files, Ionic/Angular routes, and NavigationContainer screens.
_ROUTE_RE = re.compile(
    r"""(?x)
    path\s*:\s*['"`][^'"`]{1,}['"`]          # { path: '/page' }
    |
    <Route\b[^>]*path=                         # <Route path="..."
    |
    <Screen\b[^>]*name=                        # <Screen name="..."
    |
    component\s*\(\s*['"`][^'"`]{1,}['"`]     # component('PageName', ...)
    |
    page\s*:\s*['"`][^'"`]{1,}['"`]           # page: 'Home'
    """
)

# NS*UsageDescription keys in plists.
_USAGE_KEY_RE = re.compile(r"NS\w+UsageDescription$")


@dataclass(frozen=True)
class MinFuncFinding:
    """Fired when all three low-functionality signals are present."""

    plugin_count: int    # 0 (always, by definition)
    route_count: int     # ≤ 3
    usage_key_count: int # 0 (always, by definition)
    source_root: Path


def check_min_functionality(root: Path) -> MinFuncFinding | None:
    """Return a MinFuncFinding if the source looks like a static wrapper.

    Returns None when any signal is absent (the app has native value).
    Never raises — unexpected read errors are silently skipped.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        return None

    plugin_count, route_count = _scan_source(root)
    if plugin_count > 0:
        return None

    usage_key_count = _count_usage_keys(root)
    if usage_key_count > 0:
        return None

    if route_count > 3:
        return None

    return MinFuncFinding(
        plugin_count=plugin_count,
        route_count=route_count,
        usage_key_count=usage_key_count,
        source_root=root,
    )


def _scan_source(root: Path) -> tuple[int, int]:
    """Return (plugin_count, route_count) by walking JS/TS source files."""
    plugin_imports: set[str] = set()
    route_count = 0

    for fpath in _walk_source_files(root):
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _CAPACITOR_PLUGIN_RE.finditer(text):
            plugin_imports.add(match.group(1))
        for _ in _ROUTE_RE.finditer(text):
            route_count += 1

    return len(plugin_imports), route_count


def _count_usage_keys(root: Path) -> int:
    """Count NS*UsageDescription keys across any Info.plist files found."""
    count = 0
    for dirpath, dirnames, filenames in __import__("os").walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if fname != "Info.plist":
                continue
            fpath = Path(dirpath) / fname
            try:
                with fpath.open("rb") as fh:
                    data = plistlib.load(fh)
            except Exception:
                continue
            count += sum(1 for k in data if _USAGE_KEY_RE.match(k))
    return count


# --- Three-layer report adapter -----------------------------------------------


def to_min_func_findings(
    finding: MinFuncFinding | None,
) -> "list[Finding]":  # noqa: F821
    """Convert a MinFuncFinding into a Layer-B manual-review Finding list."""
    if finding is None:
        return []

    from converter.report import Finding

    reason = (
        "The source tree shows all three low-functionality signals: "
        f"zero Capacitor plugin imports, zero NS*UsageDescription keys "
        f"(no permission-gated native feature), and only {finding.route_count} "
        f"route/screen definition(s). "
        "Apple Guideline 4.2 rejects apps that offer no direct benefit beyond "
        "what a mobile browser already provides. A pure static web wrapper "
        "is a common rejection reason."
    )
    recommended_fix = (
        "Add at least one meaningful native capability before submission:\n"
        "1. Integrate a Capacitor plugin (Camera, Geolocation, Push Notifications, "
        "Haptics, etc.) that your web layer actually uses.\n"
        "2. Or, add significant in-app navigation (≥ 4 distinct screens/routes).\n"
        "3. Or, prepare a written justification for the App Review team explaining "
        "why the app provides value beyond a browser bookmark.\n"
        "Review the App Store Review Guidelines §4.2 before resubmitting."
    )

    return [
        Finding(
            id="compliance.min-functionality#0",
            category="compliance.min-functionality",
            severity="warning",
            producer=PRODUCER,
            file=str(finding.source_root),
            line=0,
            original_snippet="(heuristic — no single line)",
            attempted_translation=None,
            reason=reason,
            recommended_fix=recommended_fix,
            doc_link=MIN_FUNC_DOC_URL,
        )
    ]
