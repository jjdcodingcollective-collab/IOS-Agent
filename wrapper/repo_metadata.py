"""
GitHub repo metadata fetch for the wrapper's pre-flight banner.

Phase 4: before cloning, surface what GitHub already knows about the target
(default branch, last push, primary language, visibility, star count) so the
user can catch a wrong-repo typo before the clone runs.

Soft-fail design: every failure mode (no network, no auth, non-GitHub URL,
404, rate-limit) returns ``None``. The banner is decorative; the conversion
is the product.

Auth resolution order:
  1. ``gh auth token`` subprocess output, if ``gh`` is installed and signed in
  2. ``GITHUB_TOKEN`` env var
  3. anonymous (60 req/hr/IP — fine for one-off conversions, not CI loops)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


GITHUB_API_ROOT = "https://api.github.com"
USER_AGENT = "ios-agent-wrapper"

_GITHUB_HOSTS = ("github.com", "www.github.com")

# Capture (owner, repo) from the four URL shapes we care about:
#   https://github.com/owner/repo
#   https://github.com/owner/repo.git
#   git@github.com:owner/repo.git
#   github.com/owner/repo  (no scheme)
_HTTPS_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
)
_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class RepoMetadata:
    owner: str
    repo: str
    default_branch: str
    visibility: str  # "public" | "private"
    primary_language: str | None
    pushed_at: str | None  # ISO-8601 string from GitHub
    stars: int
    open_issues: int  # GitHub returns issues+PRs lumped in this field


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract ``(owner, repo)`` from a GitHub URL, or ``None`` if not GitHub.

    Accepts HTTPS, SSH, and scheme-less forms. Returns ``None`` for any other
    host (GitLab/Bitbucket) — Phase 4 only surfaces GitHub metadata; the
    conversion itself works against any git remote.
    """
    if not url:
        return None
    url = url.strip()
    for pattern in (_HTTPS_RE, _SSH_RE):
        match = pattern.match(url)
        if match:
            owner, repo = match.group(1), match.group(2)
            if owner and repo:
                return owner, repo
    return None


def _resolve_token() -> str | None:
    """Return a GitHub token from ``gh auth token`` or ``GITHUB_TOKEN``, else None."""
    # Try `gh auth token` first — it's quiet on success and on failure
    # (missing/expired login) just exits non-zero. Never prompts.
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token:
                return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    env_token = os.environ.get("GITHUB_TOKEN", "").strip()
    return env_token or None


def fetch_repo_metadata(
    owner: str,
    repo: str,
    *,
    token: str | None = None,
    timeout: float = 5.0,
) -> RepoMetadata | None:
    """Fetch metadata for ``owner/repo``. Returns ``None`` on any failure.

    Pass ``token=None`` to use the resolver above. Pass an explicit token
    (including the empty string for forced-anonymous) to override.
    """
    if token is None:
        token = _resolve_token()

    request = urllib.request.Request(
        f"{GITHUB_API_ROOT}/repos/{owner}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None

    return _parse_repo_payload(payload)


def _parse_repo_payload(payload: dict) -> RepoMetadata | None:
    """Parse a GitHub ``/repos/{owner}/{repo}`` response into ``RepoMetadata``."""
    try:
        owner_obj = payload.get("owner") or {}
        owner = owner_obj.get("login") or payload.get("full_name", "/").split("/")[0]
        repo = payload.get("name") or payload.get("full_name", "/").split("/")[-1]
        default_branch = payload.get("default_branch") or "main"
        visibility = "private" if payload.get("private") else "public"
        primary_language = payload.get("language")  # may be None
        pushed_at = payload.get("pushed_at")  # ISO-8601 string
        stars = int(payload.get("stargazers_count") or 0)
        open_issues = int(payload.get("open_issues_count") or 0)
    except (AttributeError, TypeError, ValueError):
        return None

    if not owner or not repo:
        return None

    return RepoMetadata(
        owner=owner,
        repo=repo,
        default_branch=default_branch,
        visibility=visibility,
        primary_language=primary_language,
        pushed_at=pushed_at,
        stars=stars,
        open_issues=open_issues,
    )


def format_metadata_banner(meta: RepoMetadata, *, now: datetime | None = None) -> str:
    """Build a single-line banner string used in the pre-flight summary."""
    parts: list[str] = [f"{meta.owner}/{meta.repo}", meta.visibility]
    if meta.primary_language:
        parts.append(meta.primary_language)
    parts.append(f"default branch '{meta.default_branch}'")

    if meta.pushed_at:
        relative = _format_relative_time(meta.pushed_at, now=now)
        if relative:
            parts.append(f"last push {relative}")

    if meta.stars:
        parts.append(f"{meta.stars} stars")
    if meta.open_issues:
        parts.append(f"{meta.open_issues} open issues/PRs")

    return " · ".join(parts)


def _format_relative_time(iso_ts: str, *, now: datetime | None = None) -> str | None:
    """Convert an ISO-8601 timestamp into 'N days ago' / 'N hours ago' / etc."""
    try:
        # GitHub returns UTC timestamps with a trailing 'Z'; normalise.
        normalised = iso_ts.replace("Z", "+00:00")
        ts = datetime.fromisoformat(normalised)
    except (ValueError, AttributeError):
        return None

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if now is None:
        now = datetime.now(timezone.utc)

    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 90:
        return "just now"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 36:
        return f"{hours} hours ago"
    days = hours // 24
    if days < 14:
        return f"{days} days ago"
    weeks = days // 7
    if weeks < 9:
        return f"{weeks} weeks ago"
    months = days // 30
    if months < 18:
        return f"{months} months ago"
    years = days // 365
    return f"{years} years ago"


def banner_for_url(url: str, *, now: datetime | None = None) -> str | None:
    """One-shot helper: parse + fetch + format. Returns ``None`` on any failure.

    The CLI uses this directly. Tests target the lower-level functions.
    """
    parsed = parse_github_url(url)
    if not parsed:
        return None
    owner, repo = parsed
    meta = fetch_repo_metadata(owner, repo)
    if meta is None:
        return None
    return format_metadata_banner(meta, now=now)
