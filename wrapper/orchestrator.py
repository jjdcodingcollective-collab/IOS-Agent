"""
Orchestrator — runs the converter CLI as a subprocess and parses its output.

The wrapper deliberately treats the CLI as an opaque tool: it invokes it,
waits for it to finish, then reads the markdown/JSON reports it left on
disk. This keeps the wrapper decoupled from CLI internals, matches the
"state lives on disk" principle from agent-interaction-design.md, and
means the wrapper can target any CLI version that produces the same
report contract.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ConfidenceRow:
    """A single row from the Conversion Confidence table."""
    output_path: str
    confidence_pct: int
    band: str  # HIGH / MEDIUM / LOW
    issues: str


@dataclass
class ConversionResult:
    """Structured outcome of a single conversion run.

    The wrapper hands this to the conversational layer, which decides what
    to surface to the user. Anything in here is safe to render directly —
    no markdown bodies, no raw report text.
    """
    success: bool
    exit_code: int
    source_dir: Path
    output_dir: Path
    app_name: str

    files_converted: int = 0
    scaffold_files: int = 0
    project_files: int = 0
    average_confidence: int | None = None
    todo_count: int = 0
    confidence_rows: list[ConfidenceRow] = field(default_factory=list)
    validation_errors: int = 0
    validation_warnings: int = 0
    validation_avg_confidence: int | None = None
    validation_ran: bool = False

    cli_stdout: str = ""
    cli_stderr: str = ""

    @property
    def has_errors(self) -> bool:
        """True if validation reported errors or the CLI failed."""
        return not self.success or self.validation_errors > 0

    @property
    def needs_review(self) -> bool:
        """Heuristic for the 'Requires more review/' branch prefix in Phase 3."""
        if self.validation_errors > 0:
            return True
        if self.average_confidence is not None and self.average_confidence < 60:
            return True
        return False

    @property
    def low_confidence_files(self) -> list[ConfidenceRow]:
        """Confidence rows below 50% (the LOW band)."""
        return [r for r in self.confidence_rows if r.band == "LOW"]


def run_conversion(
    source_dir: str | Path,
    output_dir: str | Path,
    app_name: str = "MyApp",
    validate: bool = True,
    quiet: bool = True,
) -> ConversionResult:
    """Run the converter CLI against a local directory and parse the results.

    Args:
        source_dir: TypeScript source root.
        output_dir: Directory where the CLI should write its output.
        app_name: Name for the generated iOS app.
        validate: Pass `--no-validate` to the CLI when False.
        quiet: Pass `--quiet` to the CLI when True. The wrapper relies on
               the on-disk reports, not stdout, so quiet is the default.

    Returns:
        ConversionResult with parsed statistics. The result's `success`
        field reflects the CLI exit code; partial results are still
        populated so the caller can surface what it can.
    """
    source_path = Path(source_dir).resolve()
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    if not source_path.is_dir():
        return ConversionResult(
            success=False,
            exit_code=2,
            source_dir=source_path,
            output_dir=out_path,
            app_name=app_name,
            cli_stderr=f"Source directory does not exist: {source_path}",
        )

    cmd = [
        sys.executable,
        "-m",
        "converter.run",
        str(source_path),
        "--output",
        str(out_path),
        "--app-name",
        app_name,
    ]
    if not validate:
        cmd.append("--no-validate")
    if quiet:
        cmd.append("--quiet")

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    result = ConversionResult(
        success=(proc.returncode == 0),
        exit_code=proc.returncode,
        source_dir=source_path,
        output_dir=out_path,
        app_name=app_name,
        cli_stdout=proc.stdout,
        cli_stderr=proc.stderr,
    )

    _populate_from_reports(result)
    return result


# ---------------------------------------------------------------------------
# Report parsing — turns the CLI's markdown reports into structured fields.
# ---------------------------------------------------------------------------

_CONFIDENCE_HEADER_RE = re.compile(
    r"Average:\s*\*\*(\d+)%\*\*", re.IGNORECASE
)
_FILE_COUNT_RE = re.compile(
    r"\*\*(\d+) files? converted\*\*,\s*(\d+) scaffold files?,\s*(\d+) project files?",
    re.IGNORECASE,
)
_CONFIDENCE_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*(\d+)%\s*(HIGH|MEDIUM|LOW)\s*\|\s*([^|]+?)\s*\|\s*$"
)
_VALIDATION_HEADER_RE = re.compile(
    r"Average confidence:\s*\*\*(\d+)%\*\*", re.IGNORECASE
)


def _populate_from_reports(result: ConversionResult) -> None:
    """Read the CLI's on-disk reports and fill in the structured fields."""
    summary_path = result.output_dir / "generation-summary.md"
    if summary_path.exists():
        _parse_generation_summary(summary_path.read_text(encoding="utf-8"), result)

    validation_path = result.output_dir / "validation-report.md"
    if validation_path.exists():
        _parse_validation_report(validation_path.read_text(encoding="utf-8"), result)

    # TODO count comes from grepping the generated Swift files — fast and
    # robust against report-format changes.
    swift_root = result.output_dir / result.app_name
    if swift_root.is_dir():
        result.todo_count = sum(
            f.read_text(encoding="utf-8", errors="replace").count("// TODO")
            for f in swift_root.rglob("*.swift")
        )


def _parse_generation_summary(text: str, result: ConversionResult) -> None:
    """Pull file counts, average confidence, and per-file confidence rows."""
    files_match = _FILE_COUNT_RE.search(text)
    if files_match:
        result.files_converted = int(files_match.group(1))
        result.scaffold_files = int(files_match.group(2))
        result.project_files = int(files_match.group(3))

    # Average confidence appears under "## Conversion Confidence"
    in_confidence_section = False
    for line in text.splitlines():
        if line.startswith("## Conversion Confidence"):
            in_confidence_section = True
            continue
        if in_confidence_section:
            if line.startswith("## "):
                # Hit the next section
                break
            avg_match = _CONFIDENCE_HEADER_RE.search(line)
            if avg_match:
                result.average_confidence = int(avg_match.group(1))
            row_match = _CONFIDENCE_ROW_RE.match(line)
            if row_match:
                result.confidence_rows.append(
                    ConfidenceRow(
                        output_path=row_match.group(1),
                        confidence_pct=int(row_match.group(2)),
                        band=row_match.group(3),
                        issues=row_match.group(4).strip(),
                    )
                )


def _parse_validation_report(text: str, result: ConversionResult) -> None:
    """Pull validation pass/fail counts and average swiftc confidence."""
    result.validation_ran = True

    avg_match = _VALIDATION_HEADER_RE.search(text)
    if avg_match:
        result.validation_avg_confidence = int(avg_match.group(1))

    # Errors and warnings appear in the per-file table. Cheapest to count
    # the explicit error/warning markers the CLI emits.
    result.validation_errors = text.count(" error:") + text.count("**Errors:**")
    result.validation_warnings = text.count(" warning:") + text.count("**Warnings:**")

    # Prefer the structured "Errors: N" / "Warnings: N" lines if present.
    err_line = re.search(r"Errors:\s*\*\*(\d+)\*\*", text)
    if err_line:
        result.validation_errors = int(err_line.group(1))
    warn_line = re.search(r"Warnings:\s*\*\*(\d+)\*\*", text)
    if warn_line:
        result.validation_warnings = int(warn_line.group(1))
