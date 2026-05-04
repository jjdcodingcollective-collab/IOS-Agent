#!/usr/bin/env python3
"""
iOS Code Converter — CLI Runner
Analyzes a TypeScript/React project and produces:
  1. analysis.json      — structured manifest of all detected patterns
  2. analysis-report.md — human-readable analysis summary
  3. migration-plan.md  — file-by-file iOS conversion plan
  4. swift/             — generated Swift/SwiftUI source files
  5. swift/App/         — entry point + navigation (Phase 4)
  6. swift/Config/      — xcconfig + Package.swift (Phase 4)
  7. learning-notes.md  — educational guide: WHY Apple does it this way

Usage:
    python converter/run.py <source_directory> [--output <output_directory>]

Examples:
    python converter/run.py ./my-react-app
    python converter/run.py ./my-react-app --output ./converter/output
    python converter/run.py ./converter/test-fixtures/sample-app
    python converter/run.py ./my-react-app --analyze-only   # Skip code generation
    python converter/run.py ./my-react-app --app-name MyApp # Set app name
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
from converter.analyzer.dependency_graph import DependencyGraph
from converter.reviewer.migration_planner import generate_migration_plan
from converter.rewriter.engine import rewrite_project
from converter.assembler.project_assembler import assemble_project
from converter.validator.swift_checker import validate_project, generate_validation_report


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
        "--app-name",
        default="MyApp",
        help="Name for the generated iOS app (default: MyApp)",
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
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip output validation step after code generation",
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

    # Build dependency graph (Phase A: BUILD-2)
    log("Building dependency graph...")
    source_files_map = {f["relative_path"]: f["content"] for f in files}
    dep_graph = DependencyGraph(manifest, source_files_map)
    graph_summary = dep_graph.summary()
    log(f"  Files: {graph_summary['total_files']}, "
        f"Internal edges: {graph_summary['internal_edges']}, "
        f"Types registered: {graph_summary['types_registered']}")

    unresolved = dep_graph.get_unresolved_imports()
    if unresolved:
        log(f"  Unresolved imports: {len(unresolved)}")
        for u in unresolved[:5]:
            log(f"    {u['from']} -> {u['import_path']}: {u['names']}")

    log(f"  Conversion order: {' -> '.join(Path(p).stem for p in graph_summary['conversion_order'])}")

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

    # Phase B: Output goes to a project root dir (SPM layout built by assembler)
    project_output_dir = output_dir / args.app_name
    swift_output_dir = project_output_dir

    result = rewrite_project(
        manifest, source_files, str(swift_output_dir),
        dependency_graph=dep_graph,
    )

    # Report results
    for rewrite in result.files:
        status = "OK" if rewrite.success else "FAIL"
        log(f"  [{status}] {rewrite.source_path} -> {rewrite.output_path}")
        for note in rewrite.notes:
            log(f"         {note}")

    for scaffold_path in result.scaffold_files:
        log(f"  [SCAFFOLD] {scaffold_path}")

    # =====================================================================
    # Phase 4: Assemble (Phase B: SPM package layout)
    # =====================================================================
    log(f"\n{'='*60}")
    log(f"  PHASE 4: Assembling iOS project (SPM package layout)")
    log(f"{'='*60}")

    assembly = assemble_project(
        manifest=manifest,
        rewrite_result=result,
        output_dir=str(swift_output_dir),
        app_name=args.app_name,
    )

    for rel_path in sorted(assembly.generated_files.keys()):
        log(f"  [ASSEMBLE] {rel_path}")

    log(f"  [LEARN] learning-notes.md")
    log(f"  [SPM] Package.swift — open in Xcode: File > Open > Package.swift")

    # =====================================================================
    # Phase 5: Validate (Phase A: BUILD-9)
    # =====================================================================
    validation = None
    if not args.no_validate:
        log(f"\n{'='*60}")
        log(f"  PHASE 5: Validating generated Swift code")
        log(f"{'='*60}")

        validation = validate_project(str(swift_output_dir), use_swiftc=True)

        for vr in sorted(validation.files, key=lambda r: r.confidence_score):
            pct = int(vr.confidence_score * 100)
            status = "PASS" if vr.is_valid else "FAIL"
            errors = sum(1 for i in vr.issues if i.severity == "error")
            warns = sum(1 for i in vr.issues if i.severity == "warning")
            log(f"  [{status}] {pct:3d}% | {vr.file_path} ({errors}E {warns}W)")

        # Write validation report
        val_report = generate_validation_report(validation)
        val_path = output_dir / "validation-report.md"
        val_path.write_text(val_report, encoding="utf-8")
        log(f"  -> {val_path}")

    # =====================================================================
    # Write conversion summary
    # =====================================================================
    summary_lines = ["# Code Generation Summary\n"]
    summary_lines.append(f"**App Name:** {args.app_name}\n")
    summary_lines.append(f"**{len(result.files)} files converted**, "
                         f"{len(result.scaffold_files)} scaffold files, "
                         f"{len(assembly.generated_files)} project files generated.\n")

    summary_lines.append("## Generated Files\n")
    summary_lines.append("| Source | Output | Status |")
    summary_lines.append("|---|---|---|")
    for r in result.files:
        status = "OK" if r.success else "NEEDS REVIEW"
        summary_lines.append(f"| `{r.source_path}` | `{r.output_path}` | {status} |")
    for sp in result.scaffold_files:
        summary_lines.append(f"| *(generated)* | `{sp}` | SCAFFOLD |")
    for ap in sorted(assembly.generated_files.keys()):
        summary_lines.append(f"| *(assembled)* | `{ap}` | PROJECT |")

    # BUILD-14: Per-file rewriter confidence (independent of swiftc validation)
    scored = [r for r in result.files if r.confidence_breakdown]
    if scored:
        avg = round(sum(r.confidence_score for r in scored) / len(scored) * 100)
        summary_lines.append("\n## Conversion Confidence\n")
        summary_lines.append(
            f"Per-file rewriter confidence based on TODOs, fallbacks, and "
            f"analyzer-flagged manual patterns. Average: **{avg}%**.\n"
        )
        summary_lines.append("| File | Confidence | Issues |")
        summary_lines.append("|---|---|---|")
        for r in sorted(scored, key=lambda x: x.confidence_score):
            pct = int(r.confidence_score * 100)
            badge = "HIGH" if pct >= 80 else ("MEDIUM" if pct >= 50 else "LOW")
            issues = []
            for k, v in r.confidence_breakdown.items():
                if isinstance(v, dict) and "count" in v:
                    label = k.replace("_", " ")
                    issues.append(f"{v['count']} {label}")
            issue_str = ", ".join(issues) if issues else "none"
            summary_lines.append(f"| `{r.output_path}` | {pct}% {badge} | {issue_str} |")

    summary_lines.append("\n## iOS Project Structure\n")
    summary_lines.append("```")
    summary_lines.append(f"{args.app_name}/")
    for path in assembly.project_structure:
        depth = path.count("/")
        prefix = "│   " * depth + "├── "
        filename = Path(path).name
        summary_lines.append(f"{prefix}{filename}")
    summary_lines.append("```")

    # Validation summary
    if validation:
        summary_lines.append("\n## Validation Results\n")
        summary_lines.append(f"Average confidence: **{validation.summary.get('average_confidence', 0)}%**\n")
        summary_lines.append("| File | Confidence | Status |")
        summary_lines.append("|---|---|---|")
        for vr in sorted(validation.files, key=lambda r: r.confidence_score):
            pct = int(vr.confidence_score * 100)
            badge = "HIGH" if pct >= 80 else ("MEDIUM" if pct >= 50 else "LOW")
            status = "PASS" if vr.is_valid else "FAIL"
            summary_lines.append(f"| `{vr.file_path}` | {pct}% {badge} | {status} |")
        summary_lines.append("\nSee `validation-report.md` for full details.")

    summary_lines.append("\n## Next Steps\n")
    summary_lines.append(f"1. Open in Xcode: **File > Open** → select `{args.app_name}/Package.swift`")
    summary_lines.append("2. Xcode will resolve SPM dependencies automatically")
    summary_lines.append("3. Review all generated `.swift` files for `// TODO:` comments")
    summary_lines.append("4. Read `learning-notes.md` to understand iOS patterns")
    summary_lines.append("5. Update `Debug.xcconfig` / `Release.xcconfig` with real API URLs")
    summary_lines.append("6. Review `Info.plist` — update privacy descriptions for your app")
    summary_lines.append("7. Resolve any compilation errors (check validation report)")
    summary_lines.append("8. Test each view in SwiftUI previews (Cmd+Option+P)")
    summary_lines.append("9. Build and run on Simulator (Cmd+R)")
    summary_lines.append("")
    summary_lines.append("### Alternative: XcodeGen")
    summary_lines.append("If you prefer a `.xcodeproj`, install XcodeGen and run:")
    summary_lines.append(f"```")
    summary_lines.append(f"cd {args.app_name} && xcodegen generate")
    summary_lines.append(f"```")

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
    for ap in assembly.generated_files:
        all_outputs.append(swift_output_dir / ap)
    all_outputs.append(output_dir / "learning-notes.md")

    _print_summary(log, manifest, all_outputs, result, assembly, validation)


def _print_summary(log, manifest, output_files, rewrite_result=None, assembly=None, validation=None):
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

    if assembly:
        log(f"  Project files:        {len(assembly.generated_files)}")
        log(f"  Learning notes:       learning-notes.md")
        log(f"  Project layout:       SPM executable package")
        log(f"  Open in Xcode:        File > Open > Package.swift")

    if validation:
        vs = validation.summary
        log(f"")
        log(f"  Validation:")
        log(f"    Files validated:    {vs.get('total_files', 0)}")
        log(f"    Avg confidence:    {vs.get('average_confidence', 0)}%")
        log(f"    Errors:            {vs.get('errors', 0)}")
        log(f"    Warnings:          {vs.get('warnings', 0)}")
        if vs.get('swift_syntax_checked'):
            log(f"    Swift syntax:      checked (swiftc)")
        else:
            log(f"    Swift syntax:      static analysis only (swiftc not available)")

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
