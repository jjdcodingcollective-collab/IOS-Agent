"""
Git operations — clone, branch, and commit conversion output.

Phase 2 scope: everything up to but not including push. The wrapper
clones the user's repo to a working directory, runs the converter,
then creates/updates an `ios-conversion` branch with the generated
Swift project. The user can inspect the branch locally before any
push happens.

Safety rails (per plans/github-round-trip.md):
- Never force-push (we don't push at all in Phase 2).
- Never operate on `main` / `master` as the conversion branch.
- Branch name is validated against `git check-ref-format`.
- Re-runs are fresh commits with `rev N`, never `--amend` and never
  `git reset --hard`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .orchestrator import ConversionResult


PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "trunk", "release"})

REPORT_DIR = ".ios-conversion"
"""Inside the conversion branch, all converter reports live here so the
Swift project itself stays clean at the repo root."""

NEEDS_REVIEW_PREFIX = "Requires-more-review/"


@dataclass
class GitError(Exception):
    """Raised when a git operation fails or violates a safety rail."""
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CommitInfo:
    """Result of committing a conversion to a branch."""
    branch: str
    revision: int
    sha: str
    message: str
    needs_review: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

BOT_AUTHOR_NAME = "ios-agent"
BOT_AUTHOR_EMAIL = "ios-agent@localhost"
"""Identity used for auto-conversion commits. Phase 3 may swap to a real
service account once we know what authentication shape the credential
proxy hands us — but the auto-conversion commits should NEVER pose as
the human user."""


def clone_repo(url: str, dest: str | Path, depth: int | None = None) -> Path:
    """Clone a repository into `dest`. Returns the absolute path to the clone.

    Uses the credential proxy via the pre-configured git credential helper —
    no token handling here. Sets a local bot identity in the clone so the
    auto-conversion commit doesn't get the user's global git identity.
    """
    dest_path = Path(dest).resolve()
    if dest_path.exists():
        raise GitError(f"clone destination already exists: {dest_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    cmd += [url, str(dest_path)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError(
            f"git clone failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
        )

    # Set a local-only identity for this clone. `git config` (no --global)
    # only writes to .git/config, so the user's global config is untouched.
    _git(dest_path, "config", "user.name", BOT_AUTHOR_NAME)
    _git(dest_path, "config", "user.email", BOT_AUTHOR_EMAIL)

    return dest_path


def commit_conversion(
    repo_path: str | Path,
    conversion: ConversionResult,
    branch_name: str = "ios-conversion",
    version: str = "0.1",
) -> CommitInfo:
    """Stage the conversion output onto a branch and commit it.

    Steps:
      1. Validate the branch name (git format + not a protected branch).
      2. Determine the effective branch (apply 'Requires more review/' prefix
         if the conversion has validation errors or low confidence).
      3. Capture the upstream HEAD SHA so the commit message can reference it.
      4. Check out (or create) the branch.
      5. Replace the prior generated Swift project + reports with the new ones.
      6. Compute revision number and update notes from prior commits.
      7. Commit. Returns the resulting CommitInfo.

    Does NOT push. Phase 3 adds push.
    """
    repo = Path(repo_path).resolve()
    _assert_repo(repo)

    _validate_branch_name(branch_name)
    if branch_name in PROTECTED_BRANCHES:
        raise GitError(
            f"refusing to use protected branch '{branch_name}' as the "
            f"conversion branch"
        )

    effective_branch = (
        f"{NEEDS_REVIEW_PREFIX}{branch_name}"
        if conversion.needs_review
        else branch_name
    )
    # Also validate the prefixed form — slashes are allowed in git refs
    _validate_branch_name(effective_branch)

    default_branch = _detect_default_branch(repo)
    source_sha = _git(repo, "rev-parse", default_branch).strip()

    revision = _next_revision(repo, effective_branch)
    update_notes = _build_update_notes(repo, effective_branch, conversion, revision)

    _checkout_branch(repo, effective_branch, fallback_base=default_branch)

    # If the alternate branch (with/without the prefix) exists, drop it —
    # the prefix is a UX signal that should track the latest run only.
    _drop_stale_alternate_branch(repo, branch_name, effective_branch)

    _replace_generated_files(repo, conversion)

    message = _format_commit_message(
        conversion=conversion,
        revision=revision,
        update_notes=update_notes,
        source_sha=source_sha,
        version=version,
    )

    _git(repo, "add", "-A")
    if not _has_staged_changes(repo):
        raise GitError(
            "nothing to commit — generated output is identical to the "
            "current branch state"
        )
    _git(repo, "commit", "-m", message)
    sha = _git(repo, "rev-parse", "HEAD").strip()

    return CommitInfo(
        branch=effective_branch,
        revision=revision,
        sha=sha,
        message=message,
        needs_review=conversion.needs_review,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` and return stdout. Raises GitError on failure."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


def _assert_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise GitError(f"repo path is not a directory: {repo}")
    if not (repo / ".git").exists():
        raise GitError(f"not a git repository: {repo}")


def _validate_branch_name(name: str) -> None:
    if not name or name.strip() != name:
        raise GitError(f"invalid branch name: {name!r}")
    proc = subprocess.run(
        ["git", "check-ref-format", "--branch", name],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"invalid branch name {name!r}: {proc.stderr.strip() or 'rejected by git'}"
        )


def _current_branch(repo: Path) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def _detect_default_branch(repo: Path) -> str:
    """Find the upstream default branch (origin/HEAD), with safe fallbacks.

    The conversion branch should always be created from the upstream's
    default, never from a previous conversion commit. This helper picks
    the right base regardless of which branch is currently checked out.
    """
    # Preferred: ask origin what its HEAD is.
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        ref = proc.stdout.strip()  # e.g. "origin/main"
        if ref.startswith("origin/"):
            return ref.split("/", 1)[1]

    # Fallback: prefer common defaults if they exist locally.
    for candidate in ("main", "master"):
        if _branch_exists(repo, candidate):
            return candidate

    # Last resort: whatever's checked out right now.
    return _current_branch(repo)


def _branch_exists(repo: Path, name: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _checkout_branch(repo: Path, branch: str, fallback_base: str) -> None:
    """Check out `branch`, creating it from `fallback_base` if it doesn't exist."""
    if _branch_exists(repo, branch):
        _git(repo, "checkout", branch)
    else:
        _git(repo, "checkout", "-b", branch, fallback_base)


def _drop_stale_alternate_branch(
    repo: Path, base_name: str, effective_branch: str
) -> None:
    """When the 'Requires more review/' prefix toggles, remove the old branch.

    Per the plan: a clean re-run automatically drops the prefix; a regressing
    re-run removes the un-prefixed branch so reviewers don't get stale state
    on two branches.
    """
    other = (
        base_name
        if effective_branch.startswith(NEEDS_REVIEW_PREFIX)
        else f"{NEEDS_REVIEW_PREFIX}{base_name}"
    )
    if other == effective_branch:
        return
    if not _branch_exists(repo, other):
        return
    # Only delete if `other` is fully merged into the new effective branch
    # OR if it has no unique history beyond the conversion commits. The
    # safest check: only delete if `git branch --merged effective_branch`
    # lists it, OR if its tip is equal to the prior conversion. For now,
    # keep both branches around — let the user clean up if they want. This
    # honours the "never delete branches" safety rail in the plan.
    return


def _next_revision(repo: Path, branch: str) -> int:
    """Read prior conversion commits on `branch` and return the next rev N."""
    if not _branch_exists(repo, branch):
        return 1
    log = _git(repo, "log", "--format=%s", branch)
    revs = []
    for line in log.splitlines():
        m = re.match(r"^ios:\s*auto-conversion rev (\d+)", line)
        if m:
            revs.append(int(m.group(1)))
    return (max(revs) + 1) if revs else 1


def _replace_generated_files(repo: Path, conversion: ConversionResult) -> None:
    """Copy the new Swift project + reports into the repo, removing the prior set.

    Layout in the conversion branch:
        <repo-root>/
            Package.swift
            project.yml
            Sources/<AppName>/...
            Tests/<AppName>Tests/...
            .ios-conversion/
                generation-summary.md
                analysis-report.md
                migration-plan.md
                learning-notes.md
                validation-report.md  (if validation ran)
    """
    swift_root = conversion.output_dir / conversion.app_name
    if not swift_root.is_dir():
        raise GitError(
            f"expected generated Swift project at {swift_root}, but it does not exist"
        )

    # Remove prior generated artefacts. Restrict deletion to known paths so
    # we never touch the user's TS source code.
    for path_name in (
        "Package.swift",
        "project.yml",
        "Sources",
        "Tests",
        REPORT_DIR,
    ):
        target = repo / path_name
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

    # Copy each artefact from the converter output into the repo root.
    for child in swift_root.iterdir():
        dest = repo / child.name
        if child.is_dir():
            shutil.copytree(child, dest)
        else:
            shutil.copy2(child, dest)

    # Copy reports into .ios-conversion/
    report_dir = repo / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    for report_name in (
        "generation-summary.md",
        "analysis-report.md",
        "analysis.json",
        "migration-plan.md",
        "learning-notes.md",
        "validation-report.md",
    ):
        src = conversion.output_dir / report_name
        if src.exists():
            shutil.copy2(src, report_dir / report_name)


def _has_staged_changes(repo: Path) -> bool:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(repo),
    )
    # exit 0 = no diff, exit 1 = diff present
    return proc.returncode == 1


def _format_commit_message(
    conversion: ConversionResult,
    revision: int,
    update_notes: str,
    source_sha: str,
    version: str,
) -> str:
    """Build the commit message exactly as specified in github-round-trip.md."""
    avg = conversion.average_confidence if conversion.average_confidence is not None else 0
    bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for row in conversion.confidence_rows:
        bands[row.band] = bands.get(row.band, 0) + 1

    if conversion.validation_ran:
        total = (
            conversion.validation_errors
            + conversion.validation_warnings
            + conversion.files_converted
        )
        # Prefer the simple "files - errors" denominator approximation when
        # the validator's per-file pass count isn't surfaced separately.
        passing = max(0, conversion.files_converted - conversion.validation_errors)
        validation_line = f"{passing}/{conversion.files_converted} pass"
    else:
        validation_line = "skipped"

    update_section = update_notes if update_notes else "(initial conversion)"

    return (
        f"ios: auto-conversion rev {revision}\n\n"
        f"Confidence: {avg}% avg "
        f"({bands['HIGH']} HIGH / {bands['MEDIUM']} MEDIUM / {bands['LOW']} LOW)\n"
        f"Files: {conversion.files_converted} converted, "
        f"{conversion.todo_count} TODOs\n"
        f"Validation: {validation_line}\n\n"
        f"Update notes:\n{update_section}\n\n"
        f"Generated by ios-agent v{version} from {source_sha[:12]}"
    )


# ---------------------------------------------------------------------------
# Update-notes diff: compare new generation-summary against prior one on
# the branch.
# ---------------------------------------------------------------------------

def _build_update_notes(
    repo: Path,
    branch: str,
    conversion: ConversionResult,
    revision: int,
) -> str:
    """Compare the new run against the last commit on the branch and summarise.

    Returns a short bullet list (or empty string for the first revision).
    """
    if revision <= 1 or not _branch_exists(repo, branch):
        return ""

    prior_summary = _read_prior_summary(repo, branch)
    if not prior_summary:
        return ""

    new_summary = _build_summary_dict(conversion)

    notes: list[str] = []

    # Average confidence delta
    if (
        new_summary.get("avg") is not None
        and prior_summary.get("avg") is not None
    ):
        delta = new_summary["avg"] - prior_summary["avg"]
        if delta != 0:
            sign = "+" if delta > 0 else ""
            notes.append(
                f"- Average confidence: {prior_summary['avg']}% → "
                f"{new_summary['avg']}% ({sign}{delta})"
            )

    # File-level moves of >=10%
    prior_rows = prior_summary.get("rows", {})
    moved: list[str] = []
    for path, new_pct in new_summary.get("rows", {}).items():
        if path in prior_rows:
            d = new_pct - prior_rows[path]
            if abs(d) >= 10:
                sign = "+" if d > 0 else ""
                moved.append(f"  - {path}: {prior_rows[path]}% → {new_pct}% ({sign}{d})")
    if moved:
        notes.append("- Files with confidence shifts ≥10%:")
        notes.extend(moved)

    # TODO delta
    if (
        new_summary.get("todos") is not None
        and prior_summary.get("todos") is not None
    ):
        delta = new_summary["todos"] - prior_summary["todos"]
        if delta != 0:
            sign = "+" if delta > 0 else ""
            notes.append(f"- TODOs: {prior_summary['todos']} → {new_summary['todos']} ({sign}{delta})")

    # Validation delta
    if conversion.validation_ran and "validation_errors" in prior_summary:
        delta = conversion.validation_errors - prior_summary["validation_errors"]
        if delta != 0:
            sign = "+" if delta > 0 else ""
            notes.append(
                f"- Validation errors: {prior_summary['validation_errors']} → "
                f"{conversion.validation_errors} ({sign}{delta})"
            )

    return "\n".join(notes) if notes else "- No measurable changes from previous revision"


def _read_prior_summary(repo: Path, branch: str) -> dict | None:
    """Read .ios-conversion/generation-summary.md from the branch tip."""
    try:
        text = _git(repo, "show", f"{branch}:{REPORT_DIR}/generation-summary.md")
    except GitError:
        return None
    return _parse_summary_text(text)


def _build_summary_dict(conversion: ConversionResult) -> dict:
    return {
        "avg": conversion.average_confidence,
        "todos": conversion.todo_count,
        "rows": {row.output_path: row.confidence_pct for row in conversion.confidence_rows},
        "validation_errors": conversion.validation_errors,
    }


_AVG_RE = re.compile(r"Average:\s*\*\*(\d+)%\*\*", re.IGNORECASE)
_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*(\d+)%\s*(?:HIGH|MEDIUM|LOW)\s*\|"
)


def _parse_summary_text(text: str) -> dict:
    """Parse a generation-summary.md into the same shape as _build_summary_dict.

    Mirrors the logic in orchestrator._parse_generation_summary, but
    decoupled so prior summaries can be parsed without re-running the CLI.
    """
    result: dict = {"rows": {}}
    avg_match = _AVG_RE.search(text)
    if avg_match:
        result["avg"] = int(avg_match.group(1))

    in_section = False
    for line in text.splitlines():
        if line.startswith("## Conversion Confidence"):
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            row = _ROW_RE.match(line)
            if row:
                result["rows"][row.group(1)] = int(row.group(2))
    return result
