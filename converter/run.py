#!/usr/bin/env python3
"""
iOS Code Converter — CLI Runner
Analyzes a TypeScript/React project and produces:
  1. analysis.json   — structured manifest of all detected patterns
  2. analysis-report.md — human-readable analysis summary
  3. migration-plan.md  — file-by-file iOS conversion plan

Usage:
    python converter/run.py <source_directory> [--output <output_directory>]

Examples:
    python converter/run.py ./my-react-app
    python converter/run.py ./my-react-app --output ./converter/output
    python converter/run.py ./converter/test-fixtures/sample-app
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter.analyzer.scanner import scan_project
from converter.analyzer.patterns import analyze_file
from converter.analyzer.manifest import build_manifest, generate_report
from converter.reviewer.migration_planner import generate_migration_plan


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a TypeScript/React project for iOS conversion"
    )
    parser.add_argument(
        "source",
        help="Path to the source directory to analyze",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: converter/output/)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output the JSON manifest (skip reports)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    if not source_dir.is_dir():
        print(f"Error: '{source_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    log = (lambda msg: None) if args.quiet else (lambda msg: print(msg))

    # --- Phase 1: Analyze ---
    log(f"Scanning: {source_dir}")
    files = scan_project(str(source_dir))
    log(f"  Found {len(files)} source files")

    log("Analyzing patterns...")
    analyses = []
    for f in files:
        analysis = analyze_file(f["relative_path"], f["content"])
        analyses.append(analysis)
        pattern_count = len(analysis.patterns)
        if pattern_count > 0 and not args.quiet:
            log(f"  {analysis.relative_path}: {pattern_count} patterns ({analysis.file_type})")

    log("Building manifest...")
    manifest = build_manifest(analyses, str(source_dir))

    # Write analysis.json
    json_path = output_dir / "analysis.json"
    json_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    log(f"  Wrote: {json_path}")

    if args.json_only:
        log("Done (JSON only mode).")
        return

    # Write analysis-report.md
    log("Generating analysis report...")
    report = generate_report(manifest)
    report_path = output_dir / "analysis-report.md"
    report_path.write_text(report, encoding="utf-8")
    log(f"  Wrote: {report_path}")

    # --- Phase 2: Review ---
    log("Generating migration plan...")
    plan = generate_migration_plan(manifest)
    plan_path = output_dir / "migration-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    log(f"  Wrote: {plan_path}")

    # --- Summary ---
    s = manifest["summary"]
    total = s["total_patterns"] or 1
    auto_pct = (s["conversion_difficulty"]["auto"] / total) * 100

    log("")
    log("=" * 60)
    log(f"  Analysis complete!")
    log(f"  Files scanned:    {s['total_files']}")
    log(f"  Patterns found:   {s['total_patterns']}")
    log(f"  Auto-convert:     {s['conversion_difficulty']['auto']} ({auto_pct:.0f}%)")
    log(f"  Needs assistance: {s['conversion_difficulty']['assisted']}")
    log(f"  Manual required:  {s['conversion_difficulty']['manual']}")
    log(f"")
    log(f"  Output:")
    log(f"    {json_path}")
    log(f"    {report_path}")
    log(f"    {plan_path}")
    log("=" * 60)


if __name__ == "__main__":
    main()
