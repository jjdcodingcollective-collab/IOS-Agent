"""
App Transport Security (ATS) scanner — MVP §4.9.

Detects source-side patterns that would fail silently at runtime under
iOS's App Transport Security policy (Guideline 4.5.4). Our Info.plist
template defaults to NSAllowsArbitraryLoads: false (secure), so the
generated project is safe — but if the source fetches from http:// URLs
or a config file enables arbitrary loads, those calls will fail in the
wrapped app.

Findings are Layer-B (manual review), not Layer-A blockers:
  - http:// is common for localhost/development URLs and may be
    intentional.
  - The developer must decide whether to add an ATS exception domain or
    migrate to https://.

Plan: plans/mvp-section-4-compliance.md (Step 4.9).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .api_scanner import SOURCE_EXTENSIONS, SKIP_DIRS, ScannerError, _enumerate_lines, _walk_source_files


ATS_DOC_URL = (
    "https://developer.apple.com/documentation/bundleresources/"
    "information_property_list/nsapptransportsecurity"
)

PRODUCER = "compliance.ats_scanner"

# Config filenames that might contain allowsArbitraryLoads: true.
_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".env", ".config.js", ".config.ts"}

# Regex: http:// inside a string literal in a fetch/axios/XHR/import call.
# Excludes https://, http://localhost, http://127.0.0.1, http://0.0.0.0
# (those are safe dev-only addresses).
_HTTP_URL_RE = re.compile(
    r"""(['"`])http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])([^'"`\s]+)\1"""
)

# Broad http:// string — catches variables and template literals too.
_HTTP_BARE_RE = re.compile(
    r"""http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])[\w\-./?=%&#+@:]{4,}"""
)

# allowsArbitraryLoads set to true in any config format.
# Handles JSON ("allowsArbitraryLoads": true), YAML (allowsArbitraryLoads: true),
# and JS/TS object literals (allowsArbitraryLoads: true / = true).
_ARBITRARY_LOADS_RE = re.compile(
    r"""["']?allowsArbitraryLoads["']?\s*[=:]\s*(true|True|TRUE|1|yes|Yes)""",
    re.IGNORECASE,
)

# NSAllowsArbitraryLoads in plist/XML or YAML style.
_NS_ARBITRARY_RE = re.compile(
    r"NSAllowsArbitraryLoads", re.IGNORECASE
)


@dataclass(frozen=True)
class ATSFinding:
    """A single ATS-related finding in source or config."""

    kind: str       # "http_url" | "arbitrary_loads"
    file: Path
    line: int       # 1-indexed; 0 for manifest-level
    snippet: str
    url: str | None = None   # the http:// URL, when kind == "http_url"


def scan_ats_source(root: Path) -> list[ATSFinding]:
    """Scan JS/TS source files for hardcoded http:// URLs (non-localhost)."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    findings: list[ATSFinding] = []
    seen: set[tuple[str, int, str]] = set()

    for fpath in _walk_source_files(root):
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in _enumerate_lines(text):
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for match in _HTTP_BARE_RE.finditer(line):
                url = match.group(0)
                key = (str(fpath), line_num, url)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    ATSFinding(
                        kind="http_url",
                        file=fpath,
                        line=line_num,
                        snippet=line.rstrip("\n").strip()[:120],
                        url=url,
                    )
                )
    return findings


def scan_ats_configs(root: Path) -> list[ATSFinding]:
    """Scan config files for allowsArbitraryLoads: true."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ScannerError(f"source root not found or not a directory: {root}")

    findings: list[ATSFinding] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            # Match any file whose name or extension suggests config.
            if not _is_config_file(fpath):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_num, line in _enumerate_lines(text):
                stripped = line.lstrip()
                if stripped.startswith("//") or stripped.startswith("#"):
                    continue
                if _ARBITRARY_LOADS_RE.search(line) or _NS_ARBITRARY_RE.search(line):
                    findings.append(
                        ATSFinding(
                            kind="arbitrary_loads",
                            file=fpath,
                            line=line_num,
                            snippet=line.rstrip("\n").strip()[:120],
                        )
                    )
    return findings


def scan_all_ats(root: Path) -> list[ATSFinding]:
    """Run source + config passes; return combined findings sorted by file/line."""
    src = sorted(scan_ats_source(root), key=lambda f: (str(f.file), f.line))
    cfg = sorted(scan_ats_configs(root), key=lambda f: (str(f.file), f.line))
    return src + cfg


def _is_config_file(path: Path) -> bool:
    name = path.name.lower()
    # Explicit config filenames.
    if name in ("capacitor.config.json", "capacitor.config.ts", "app.json",
                "next.config.js", "next.config.ts", "vite.config.ts",
                "vite.config.js", ".env", ".env.production", ".env.local"):
        return True
    # Any .json / .yaml / .yml / .toml that isn't a package lockfile.
    if path.suffix in (".json", ".yaml", ".yml", ".toml"):
        if name not in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            return True
    return False


# --- Three-layer report adapter ----------------------------------------------


def to_ats_findings(
    ats_findings: Iterable[ATSFinding],
    *,
    source_root: Path | None = None,
) -> list["Finding"]:  # noqa: F821
    """Convert ATSFinding records into Layer-B manual-review Finding records."""
    from converter.report import Finding

    out: list[Finding] = []
    counters: dict[str, int] = {}

    for af in ats_findings:
        slug = af.kind.replace("_", "-")
        idx = counters.get(slug, 0)
        counters[slug] = idx + 1
        finding_id = f"compliance.ats.{slug}#{idx}"

        if source_root is not None:
            root_abs = source_root.resolve()
            file_abs = af.file.resolve()
            try:
                file_str = str(file_abs.relative_to(root_abs))
            except ValueError:
                file_str = str(af.file)
        else:
            file_str = str(af.file)

        if af.kind == "http_url":
            reason = (
                f"Source contains a hardcoded `http://` URL (`{af.url}`). "
                f"iOS App Transport Security blocks non-HTTPS connections by "
                f"default. This call will fail silently at runtime in the "
                f"Capacitor wrapper unless an ATS exception domain is added "
                f"or the URL is migrated to `https://`."
            )
            recommended_fix = (
                f"Option A (preferred): migrate `{af.url}` to `https://`.\n"
                f"Option B: add an NSExceptionDomain entry for the host in "
                f"Info.plist with NSExceptionAllowsInsecureHTTPLoads: true — "
                f"requires justification in App Review."
            )
        else:
            reason = (
                f"Config file sets `allowsArbitraryLoads: true` or "
                f"`NSAllowsArbitraryLoads`. The generated Info.plist defaults "
                f"to `false` (secure), but this setting in source suggests the "
                f"app may require HTTP connections that will be blocked at "
                f"runtime (Guideline 4.5.4)."
            )
            recommended_fix = (
                "Audit all HTTP calls in the app. If any non-HTTPS endpoint is "
                "required, add a scoped NSExceptionDomain in Info.plist rather "
                "than enabling NSAllowsArbitraryLoads globally. Apple rejects "
                "apps with blanket arbitrary-loads enabled without justification."
            )

        out.append(
            Finding(
                id=finding_id,
                category=f"compliance.ats.{slug}",
                severity="warning",
                producer=PRODUCER,
                file=file_str,
                line=af.line,
                original_snippet=af.snippet,
                attempted_translation=None,
                reason=reason,
                recommended_fix=recommended_fix,
                doc_link=ATS_DOC_URL,
            )
        )
    return out
