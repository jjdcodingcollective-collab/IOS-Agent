#!/usr/bin/env python3
"""
iOS Code Converter — CLI Runner
Analyzes a TypeScript/React project and produces:
  1. analysis.json      — structured manifest of all detected patterns
  2. analysis-report.md — human-readable analysis summary
  3. migration-plan.md  — file-by-file iOS conversion plan
  4. swift/             — generated Swift/SwiftUI source files

Usage:
    python converter/run.py <source_directory> [--output <output_directory>]

Examples:
    python converter/run.py ./my-react-app
    python converter/run.py ./my-react-app --output ./converter/output
    python converter/run.py ./converter/test-fixtures/sample-app
    python converter/run.py ./my-react-app --analyze-only   # Skip code generation
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
from converter.rewriter.engine import rewrite_project


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and convert a TypeScript/React project to Swift/SwiftUI"
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
        "--analyze-only",
        action="store_true",
        help="Only run Phase 1 (Analyze) and Phase 2 (Review) — skip code generation",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output the JSON manifest (skip reports and code generation)",
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

    # =====================================================================
    # Phase 1: Analyze
    # =====================================================================
    log(f"\n{'='*60}")
    log(f"  PHASE 1: Analyzing source code")
    log(f"{'='*60}")
    log(f"Scanning: {source_dir}")
    files = scan_project(str(source_dir))
    log(f"  Found {len(files)} source files")

    log("Detecting patterns...")
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
    log(f"  -> {json_path}")

    if args.json_only:
        log("Done (JSON only mode).")
        return

    # Write analysis-report.md
    report = generate_report(manifest)
    report_path = output_dir / "analysis-report.md"
    report_path.write_text(report, encoding="utf-8")
    log(f"  -> {report_path}")

    # =====================================================================
    # Phase 2: Review
    # =====================================================================
    log(f"\n{'='*60}")
    log(f"  PHASE 2: Generating migration plan")
    log(f"{'='*60}")
    plan = generate_migration_plan(manifest)
    plan_path = output_dir / "migration-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    log(f"  -> {plan_path}")

    if args.analyze_only:
        _print_summary(log, manifest, [json_path, report_path, plan_path])
        return

    # =====================================================================
    # Phase 3: Rewrite
    # =====================================================================
    log(f"\n{'='*60}")
    log(f"  PHASE 3: Generating Swift code")
    log(f"{'='*60}")

    # Build source file map
    source_files = {f["relative_path"]: f["content"] for f in files}
    swift_output_dir = output_dir / "swift"

    result = rewrite_project(manifest, source_files, str(swift_output_dir))

    # Report results
    for rewrite in result.files:
        status = "OK" if rewrite.success else "FAIL"
        log(f"  [{status}] {rewrite.source_path} -> {rewrite.output_path}")
        for note in rewrite.notes:
            log(f"         {note}")

    for scaffold_path in result.scaffold_files:
        log(f"  [SCAFFOLD] {scaffold_path}")

    # Write conversion summary
    summary_lines = ["# Code Generation Summary\n"]
    summary_lines.append(f"**{len(result.files)} files converted**, {len(result.scaffold_files)} scaffold files generated.\n")
    summary_lines.append("## Generated Files\n")
    summary_lines.append("| Source | Output | Status |")
    summary_lines.append("|---|---|---|")
    for r in result.files:
        status = "OK" if r.success else "NEEDS REVIEW"
        summary_lines.append(f"| `{r.source_path}` | `{r.output_path}` | {status} |")
    for sp in result.scaffold_files:
        summary_lines.append(f"| *(generated)* | `{sp}` | SCAFFOLD |")
    summary_lines.append("\n## Next Steps\n")
    summary_lines.append("1. Review all generated `.swift` files for `// TODO:` comments")
    summary_lines.append("2. Create an Xcode project and add these files")
    summary_lines.append("3. Resolve any compilation errors")
    summary_lines.append("4. Test each view in SwiftUI previews")
    summary_lines.append("5. Wire up navigation in the app entry point")

    gen_summary_path = output_dir / "generation-summary.md"
    gen_summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    log(f"  -> {gen_summary_path}")

    # =====================================================================
    # Final Summary
    # =====================================================================
    all_outputs = [json_path, report_path, plan_path, gen_summary_path]
    for r in result.files:
        all_outputs.append(swift_output_dir / r.output_path)
    for sp in result.scaffold_files:
        all_outputs.append(swift_output_dir / sp)

    _print_summary(log, manifest, all_outputs, result)


def _print_summary(log, manifest, output_files, rewrite_result=None):
    """Print the final summary."""
    s = manifest["summary"]
    total = s["total_patterns"] or 1
    auto_pct = (s["conversion_difficulty"]["auto"] / total) * 100

    log(f"\n{'='*60}")
    log(f"  Conversion complete!")
    log(f"{'='*60}")
    log(f"  Files scanned:       {s['total_files']}")
    log(f"  Patterns detected:   {s['total_patterns']}")
    log(f"  Auto-convertible:    {s['conversion_difficulty']['auto']} ({auto_pct:.0f}%)")
    log(f"  Needs assistance:    {s['conversion_difficulty']['assisted']}")
    log(f"  Manual required:     {s['conversion_difficulty']['manual']}")

    if rewrite_result:
        success_count = sum(1 for r in rewrite_result.files if r.success)
        total_files = len(rewrite_result.files) + len(rewrite_result.scaffold_files)
        log(f"")
        log(f"  Swift files generated: {total_files}")
        log(f"  Successful:           {success_count}/{len(rewrite_result.files)}")
        log(f"  Scaffold files:       {len(rewrite_result.scaffold_files)}")

    log(f"")
    log(f"  Output directory:")
    seen_dirs = set()
    for p in output_files:
        d = str(Path(p).parent)
        if d not in seen_dirs:
            log(f"    {d}/")
            seen_dirs.add(d)
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
