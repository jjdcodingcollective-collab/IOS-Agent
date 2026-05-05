"""
Open a GitHub pull request via the ``gh`` CLI.

Phase 5: ``--open-pr`` makes the wrapper invoke the same ``gh pr create``
command Phase 4 prints. Off by default — opening a PR is irreversible
(notifications, CI, teammates) so it stays opt-in even though the
wrapper has already done the equally-irreversible push.

Hard-fail on missing/unauthenticated ``gh``: the user explicitly asked
to open a PR, so silently skipping would be the wrong shape. Print a
clear install hint and exit non-zero from the caller.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# Match an https://github.com/.../pull/<n> URL anywhere in `gh pr create` output.
# `gh` historically prints the URL on the last line, sometimes after a
# "Creating pull request for ..." preamble. Grab the last match.
_PR_URL_RE = re.compile(r"https://github\.com/[^\s]+/pull/\d+")


@dataclass(frozen=True)
class PrInfo:
    opened: bool
    url: str | None
    error: str | None


def gh_available() -> tuple[bool, str | None]:
    """Return ``(True, None)`` if ``gh`` is installed and authenticated.

    On failure, the second element is a short install/login hint suitable
    for printing to the user.
    """
    if shutil.which("gh") is None:
        return False, (
            "`--open-pr` requires the GitHub CLI. Install: brew install gh "
            "(or see https://cli.github.com/), then run `gh auth login`."
        )

    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"could not run `gh auth status`: {exc}"

    if result.returncode != 0:
        return False, (
            "`gh` is installed but not authenticated. Run `gh auth login` "
            "and retry."
        )
    return True, None


def extract_pr_url(stdout: str) -> str | None:
    """Pull the last ``https://github.com/.../pull/<n>`` URL from ``gh`` output."""
    if not stdout:
        return None
    matches = _PR_URL_RE.findall(stdout)
    return matches[-1] if matches else None


def open_pr(
    repo_path: str | Path,
    *,
    base: str,
    head: str,
    title: str,
    body_path: str | None = None,
) -> PrInfo:
    """Run ``gh pr create`` from inside ``repo_path``.

    Returns a ``PrInfo``. ``opened=True`` means ``gh`` returned 0 and we
    extracted a PR URL from its stdout. ``opened=False`` carries the raw
    error text — typically ``gh``'s stderr, which already includes useful
    hints (e.g. "a pull request for branch X already exists").
    """
    repo_path = Path(repo_path)
    cmd = ["gh", "pr", "create", "--base", base, "--head", head, "--title", title]
    if body_path is not None:
        cmd += ["--body-file", str(body_path)]

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return PrInfo(opened=False, url=None, error=f"failed to invoke gh: {exc}")

    if result.returncode != 0:
        # gh writes the human-friendly error to stderr.
        err = (result.stderr or result.stdout or "").strip()
        return PrInfo(opened=False, url=None, error=err or "gh pr create failed")

    url = extract_pr_url(result.stdout) or extract_pr_url(result.stderr)
    if not url:
        # gh succeeded but we couldn't find a PR URL. Surface raw output so
        # the user has something to work with.
        return PrInfo(
            opened=False,
            url=None,
            error=(
                "gh pr create reported success but no PR URL was found in "
                f"its output:\n{result.stdout.strip()}"
            ),
        )

    return PrInfo(opened=True, url=url, error=None)
