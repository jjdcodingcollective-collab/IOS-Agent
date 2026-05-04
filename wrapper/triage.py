"""
Triage rendering — turn a ConversionResult into a short, scannable summary.

This is the wrapper's "what should I look at first?" response mode. It
deliberately does NOT paste markdown report bodies; it points at the
files on disk and surfaces only the top-N issues.
"""

from __future__ import annotations

from .orchestrator import ConversionResult


def format_triage(result: ConversionResult, top_n: int = 3) -> str:
    """Render a one-screen triage summary for the user."""
    if not result.success:
        return _format_failure(result)

    lines: list[str] = []
    lines.append(f"Conversion complete — {result.app_name}")
    lines.append(f"  Source:  {result.source_dir}")
    lines.append(f"  Output:  {result.output_dir}")
    lines.append("")

    # Headline numbers
    lines.append("Stats")
    lines.append(f"  Files converted:     {result.files_converted}")
    lines.append(f"  Scaffold files:      {result.scaffold_files}")
    lines.append(f"  Project files:       {result.project_files}")
    if result.average_confidence is not None:
        lines.append(f"  Average confidence:  {result.average_confidence}%")
    lines.append(f"  TODOs in Swift:      {result.todo_count}")
    if result.validation_ran:
        lines.append(
            f"  Validation:          {result.validation_errors} errors, "
            f"{result.validation_warnings} warnings"
        )

    # Lowest-confidence files — these are the user's first review targets
    low = sorted(result.confidence_rows, key=lambda r: r.confidence_pct)[:top_n]
    if low:
        lines.append("")
        lines.append(f"Top {len(low)} files to review (lowest confidence)")
        for row in low:
            lines.append(
                f"  [{row.band:<6}] {row.confidence_pct:>3}%  "
                f"{row.output_path}"
            )
            if row.issues and row.issues != "none":
                lines.append(f"           issues: {row.issues}")

    # Pointers to the full reports — never paste them inline
    lines.append("")
    lines.append("Reports")
    for name in (
        "generation-summary.md",
        "validation-report.md",
        "learning-notes.md",
        "migration-plan.md",
    ):
        path = result.output_dir / name
        if path.exists():
            lines.append(f"  {path}")

    if result.needs_review:
        lines.append("")
        lines.append("⚠  Result flagged 'needs review' "
                     "(validation errors or avg confidence < 60%).")

    return "\n".join(lines)


def _format_failure(result: ConversionResult) -> str:
    """Render an error summary when the CLI itself failed."""
    lines = [
        f"Conversion failed (exit code {result.exit_code})",
        f"  Source:  {result.source_dir}",
        f"  Output:  {result.output_dir}",
    ]
    if result.cli_stderr:
        lines.append("")
        lines.append("CLI stderr (last 20 lines):")
        for line in result.cli_stderr.strip().splitlines()[-20:]:
            lines.append(f"  {line}")
    if result.cli_stdout and not result.cli_stderr:
        lines.append("")
        lines.append("CLI stdout (last 20 lines):")
        for line in result.cli_stdout.strip().splitlines()[-20:]:
            lines.append(f"  {line}")
    return "\n".join(lines)
