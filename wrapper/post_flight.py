"""
Post-flight PR-ready next steps for the wrapper.

Phase 4: after a successful push, print the exact ``gh pr create`` command
the user needs (with the generated summary as the body), plus a fallback
``…/compare/<base>...<head>`` URL for users who don't have ``gh`` installed.

This module **does not** invoke ``gh``. Phase 5 will add ``--open-pr`` to
actually run it; Phase 4 only prints the command so the human stays in
control of the irreversible "open a PR" action.
"""

from __future__ import annotations

import re
from pathlib import Path

from .git_ops import CommitInfo, PushInfo
from .repo_metadata import RepoMetadata


# Mirror of repo_metadata's URL parsers — but here we accept any GitHub
# remote URL (including ``https://...``, ``git@...``) and return the
# (owner, repo) pair so we can build a compare URL from a remote.
_HTTPS_REMOTE_RE = re.compile(
    r"^(?:https?://)?(?:[^@]+@)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
)
_SSH_REMOTE_RE = re.compile(r"^(?:ssh://)?git@github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$")


def _parse_remote(remote_url: str) -> tuple[str, str] | None:
    """Extract ``(owner, repo)`` from any GitHub remote URL form."""
    if not remote_url:
        return None
    remote_url = remote_url.strip()
    for pattern in (_SSH_REMOTE_RE, _HTTPS_REMOTE_RE):
        match = pattern.match(remote_url)
        if match:
            return match.group(1), match.group(2)
    return None


def default_base_branch(meta: RepoMetadata | None) -> str:
    """Choose the PR base. Prefer the metadata default; fall back to ``main``."""
    if meta and meta.default_branch:
        return meta.default_branch
    return "main"


def format_compare_url(
    remote_url: str,
    base_branch: str,
    head_branch: str,
) -> str | None:
    """Build a ``compare/<base>...<head>?expand=1`` URL or ``None`` for non-GitHub.

    The ``?expand=1`` query opens GitHub's PR-creation form pre-populated.
    """
    parsed = _parse_remote(remote_url)
    if not parsed:
        return None
    owner, repo = parsed
    return (
        f"https://github.com/{owner}/{repo}/compare/"
        f"{base_branch}...{head_branch}?expand=1"
    )


def format_pr_command(
    commit: CommitInfo,
    base_branch: str,
    summary_path: str | Path | None = None,
) -> str:
    """Render a copy-pasteable ``gh pr create`` command."""
    title = f"iOS conversion (rev {commit.revision})"
    lines = [
        "  gh pr create \\",
        f"    --base {base_branch} \\",
        f"    --head {commit.branch} \\",
        f'    --title "{title}"',
    ]
    if summary_path is not None:
        # Insert --body-file before the trailing line (which has no \).
        body_arg = f'    --body-file "{summary_path}" \\'
        lines.insert(-1, body_arg)
        # Re-add the title line as the final non-continued line.
        lines[-1] = f'    --title "{title}"'
    return "\n".join(lines)


def format_post_flight(
    commit: CommitInfo,
    push: PushInfo,
    *,
    meta: RepoMetadata | None = None,
    summary_path: str | Path | None = None,
) -> str:
    """Render the full post-flight block shown after a successful push."""
    base = default_base_branch(meta)
    pr_command = format_pr_command(commit, base, summary_path=summary_path)
    compare = format_compare_url(push.remote_url or "", base, commit.branch)

    lines = ["Open a PR:", pr_command]
    if compare:
        lines.append("")
        lines.append("  …or open in browser:")
        lines.append(f"  {compare}")
    return "\n".join(lines)
