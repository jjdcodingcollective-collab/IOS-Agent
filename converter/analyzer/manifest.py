"""
Manifest Generator — Phase 1, Step 3
Produces a structured JSON manifest and human-readable report
from the analysis results.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone

from .patterns import FileAnalysis, DetectedPattern


def build_manifest(analyses: list[FileAnalysis], source_dir: str) -> dict:
    """Build the full analysis manifest."""
    # Aggregate stats
    total_files = len(analyses)
    file_types = {}
    all_patterns = []
    difficulty_counts = {"auto": 0, "assisted": 0, "manual": 0}

    for analysis in analyses:
        file_types[analysis.file_type] = file_types.get(analysis.file_type, 0) + 1
        for pattern in analysis.patterns:
            all_patterns.append(pattern)
            difficulty_counts[pattern.conversion_difficulty] += 1

    # Pattern type summary
    pattern_type_counts = {}
    for p in all_patterns:
        pattern_type_counts[p.pattern_type] = pattern_type_counts.get(p.pattern_type, 0) + 1

    # Unique libraries/frameworks detected
    libraries = set()
    for analysis in analyses:
        for imp in analysis.imports:
            if not imp.startswith(".") and not imp.startswith("@/"):
                # Extract package name (handles scoped packages)
                parts = imp.split("/")
                if imp.startswith("@") and len(parts) >= 2:
                    libraries.add(f"{parts[0]}/{parts[1]}")
                else:
                    libraries.add(parts[0])

    # All env vars used
    env_vars = set()
    for analysis in analyses:
        for p in analysis.patterns:
            if p.pattern_type == "env_variable":
                env_vars.add(p.name)

    # All API endpoints
    api_endpoints = []
    for analysis in analyses:
        for p in analysis.patterns:
            if p.pattern_type == "api_call" and "url" in p.details:
                api_endpoints.append({
                    "url": p.details["url"],
                    "method": p.details.get("method", "GET"),
                    "file": analysis.relative_path,
                })

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": source_dir,
            "tool_version": "0.1.0",
        },
        "summary": {
            "total_files": total_files,
            "file_types": file_types,
            "total_patterns": len(all_patterns),
            "pattern_types": pattern_type_counts,
            "conversion_difficulty": difficulty_counts,
            "third_party_libraries": sorted(libraries),
            "env_variables": sorted(env_vars),
            "api_endpoints": api_endpoints,
        },
        "files": [_serialize_analysis(a) for a in analyses],
    }


def _serialize_analysis(analysis: FileAnalysis) -> dict:
    """Convert a FileAnalysis to a serializable dict."""
    return {
        "relative_path": analysis.relative_path,
        "extension": analysis.extension,
        "file_type": analysis.file_type,
        "imports": analysis.imports,
        "exports": analysis.exports,
        "patterns": [
            {
                "pattern_type": p.pattern_type,
                "name": p.name,
                "line": p.line,
                "details": p.details,
                "conversion_difficulty": p.conversion_difficulty,
            }
            for p in analysis.patterns
        ],
    }


def generate_report(manifest: dict) -> str:
    """Generate a human-readable markdown report from the manifest."""
    s = manifest["summary"]
    lines = []

    lines.append("# Code Analysis Report")
    lines.append("")
    lines.append(f"> Generated: {manifest['meta']['generated_at']}")
    lines.append(f"> Source: `{manifest['meta']['source_dir']}`")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total files scanned | {s['total_files']} |")
    lines.append(f"| Total patterns detected | {s['total_patterns']} |")
    lines.append(f"| Auto-convertible patterns | {s['conversion_difficulty']['auto']} |")
    lines.append(f"| Needs assistance | {s['conversion_difficulty']['assisted']} |")
    lines.append(f"| Manual conversion needed | {s['conversion_difficulty']['manual']} |")
    lines.append("")

    # Conversion readiness score
    total = s["total_patterns"] or 1
    auto_pct = (s["conversion_difficulty"]["auto"] / total) * 100
    lines.append(f"**Conversion readiness: {auto_pct:.0f}% auto-convertible**")
    lines.append("")

    # File types breakdown
    lines.append("## File Types")
    lines.append("")
    lines.append("| Type | Count | iOS Equivalent |")
    lines.append("|---|---|---|")
    type_mapping = {
        "component": "SwiftUI View struct",
        "hook": "@Observable ViewModel",
        "service": "Service struct / APIClient",
        "route": "NavigationStack destination",
        "type": "Codable struct",
        "config": "xcconfig / Info.plist",
        "utility": "Extension / utility struct",
        "unknown": "(needs manual classification)",
    }
    for ftype, count in sorted(s["file_types"].items()):
        ios_equiv = type_mapping.get(ftype, "TBD")
        lines.append(f"| {ftype} | {count} | {ios_equiv} |")
    lines.append("")

    # Pattern breakdown
    lines.append("## Detected Patterns")
    lines.append("")
    lines.append("| Pattern | Count |")
    lines.append("|---|---|")
    for ptype, count in sorted(s["pattern_types"].items(), key=lambda x: -x[1]):
        lines.append(f"| {ptype} | {count} |")
    lines.append("")

    # Third-party libraries
    if s["third_party_libraries"]:
        lines.append("## Third-Party Dependencies")
        lines.append("")
        lines.append("These will need Swift equivalents or removal:")
        lines.append("")
        for lib in s["third_party_libraries"]:
            lines.append(f"- `{lib}`")
        lines.append("")

    # Environment variables
    if s["env_variables"]:
        lines.append("## Environment Variables")
        lines.append("")
        lines.append("These need to move to xcconfig / Info.plist:")
        lines.append("")
        for var in s["env_variables"]:
            lines.append(f"- `{var}`")
        lines.append("")

    # API endpoints
    if s["api_endpoints"]:
        lines.append("## API Endpoints")
        lines.append("")
        lines.append("These will be called via URLSession/APIClient:")
        lines.append("")
        lines.append("| Method | URL | Source File |")
        lines.append("|---|---|---|")
        seen = set()
        for ep in s["api_endpoints"]:
            key = f"{ep['method']}:{ep['url']}"
            if key not in seen:
                seen.add(key)
                lines.append(f"| {ep['method'].upper()} | `{ep['url']}` | {ep['file']} |")
        lines.append("")

    # Per-file details
    lines.append("## File-by-File Analysis")
    lines.append("")
    for f in manifest["files"]:
        if not f["patterns"]:
            continue
        lines.append(f"### `{f['relative_path']}` ({f['file_type']})")
        lines.append("")
        for p in f["patterns"]:
            difficulty_badge = {
                "auto": "AUTO",
                "assisted": "ASSISTED",
                "manual": "MANUAL",
            }.get(p["conversion_difficulty"], "?")
            equiv = p["details"].get("ios_equivalent", "")
            equiv_str = f" -> `{equiv}`" if equiv else ""
            lines.append(f"- [{difficulty_badge}] **{p['pattern_type']}**: `{p['name']}` (line {p['line']}){equiv_str}")
        lines.append("")

    return "\n".join(lines)
