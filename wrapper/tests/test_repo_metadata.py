"""Tests for ``wrapper.repo_metadata``.

Run with::

    python -m unittest wrapper.tests.test_repo_metadata

These tests do not hit the network. ``fetch_repo_metadata`` is exercised
via ``_parse_repo_payload`` directly.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from wrapper.repo_metadata import (
    RepoMetadata,
    _format_relative_time,
    _parse_repo_payload,
    format_metadata_banner,
    parse_github_url,
)


class TestParseGithubUrl(unittest.TestCase):
    def test_https_with_scheme(self):
        self.assertEqual(parse_github_url("https://github.com/acme/web-app"), ("acme", "web-app"))

    def test_https_with_dot_git(self):
        self.assertEqual(parse_github_url("https://github.com/acme/web-app.git"), ("acme", "web-app"))

    def test_https_with_trailing_slash(self):
        self.assertEqual(parse_github_url("https://github.com/acme/web-app/"), ("acme", "web-app"))

    def test_ssh_url(self):
        self.assertEqual(parse_github_url("git@github.com:acme/web-app.git"), ("acme", "web-app"))

    def test_ssh_url_no_dot_git(self):
        self.assertEqual(parse_github_url("git@github.com:acme/web-app"), ("acme", "web-app"))

    def test_no_scheme(self):
        self.assertEqual(parse_github_url("github.com/acme/web-app"), ("acme", "web-app"))

    def test_www_subdomain(self):
        self.assertEqual(parse_github_url("https://www.github.com/acme/web-app"), ("acme", "web-app"))

    def test_non_github_host_returns_none(self):
        self.assertIsNone(parse_github_url("https://gitlab.com/acme/web-app"))

    def test_non_github_ssh_returns_none(self):
        self.assertIsNone(parse_github_url("git@gitlab.com:acme/web-app.git"))

    def test_blank_input(self):
        self.assertIsNone(parse_github_url(""))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_github_url("not a url"))

    def test_partial_path_returns_none(self):
        # A URL like https://github.com/acme is not a repo URL.
        self.assertIsNone(parse_github_url("https://github.com/acme"))


class TestParseRepoPayload(unittest.TestCase):
    def test_full_payload(self):
        payload = {
            "name": "web-app",
            "full_name": "acme/web-app",
            "owner": {"login": "acme"},
            "default_branch": "main",
            "private": False,
            "language": "TypeScript",
            "pushed_at": "2026-05-02T10:00:00Z",
            "stargazers_count": 142,
            "open_issues_count": 31,
        }
        meta = _parse_repo_payload(payload)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.owner, "acme")
        self.assertEqual(meta.repo, "web-app")
        self.assertEqual(meta.default_branch, "main")
        self.assertEqual(meta.visibility, "public")
        self.assertEqual(meta.primary_language, "TypeScript")
        self.assertEqual(meta.stars, 142)
        self.assertEqual(meta.open_issues, 31)

    def test_private_repo(self):
        payload = {
            "name": "secret",
            "owner": {"login": "acme"},
            "default_branch": "main",
            "private": True,
        }
        meta = _parse_repo_payload(payload)
        self.assertEqual(meta.visibility, "private")

    def test_missing_language(self):
        payload = {
            "name": "x",
            "owner": {"login": "y"},
            "default_branch": "main",
            "private": False,
            "language": None,
        }
        meta = _parse_repo_payload(payload)
        self.assertIsNone(meta.primary_language)

    def test_missing_default_branch_falls_back(self):
        payload = {
            "name": "x",
            "owner": {"login": "y"},
            "private": False,
        }
        meta = _parse_repo_payload(payload)
        self.assertEqual(meta.default_branch, "main")

    def test_missing_owner_returns_none(self):
        payload = {"name": "x"}
        self.assertIsNone(_parse_repo_payload(payload))

    def test_garbage_payload_returns_none(self):
        self.assertIsNone(_parse_repo_payload({"owner": "not-a-dict"}))


class TestFormatBanner(unittest.TestCase):
    NOW = datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc)

    def _meta(self, **overrides):
        defaults = dict(
            owner="acme",
            repo="web-app",
            default_branch="main",
            visibility="public",
            primary_language="TypeScript",
            pushed_at="2026-05-02T12:00:00Z",  # 2 days before NOW
            stars=142,
            open_issues=31,
        )
        defaults.update(overrides)
        return RepoMetadata(**defaults)

    def test_full_banner(self):
        banner = format_metadata_banner(self._meta(), now=self.NOW)
        self.assertIn("acme/web-app", banner)
        self.assertIn("public", banner)
        self.assertIn("TypeScript", banner)
        self.assertIn("default branch 'main'", banner)
        self.assertIn("last push 2 days ago", banner)
        self.assertIn("142 stars", banner)
        self.assertIn("31 open issues/PRs", banner)

    def test_skips_zero_stars(self):
        banner = format_metadata_banner(self._meta(stars=0), now=self.NOW)
        self.assertNotIn("stars", banner)

    def test_skips_zero_issues(self):
        banner = format_metadata_banner(self._meta(open_issues=0), now=self.NOW)
        self.assertNotIn("open issues", banner)

    def test_skips_missing_language(self):
        banner = format_metadata_banner(self._meta(primary_language=None), now=self.NOW)
        self.assertNotIn("TypeScript", banner)
        self.assertIn("acme/web-app", banner)

    def test_skips_missing_pushed_at(self):
        banner = format_metadata_banner(self._meta(pushed_at=None), now=self.NOW)
        self.assertNotIn("last push", banner)

    def test_private_visibility(self):
        banner = format_metadata_banner(self._meta(visibility="private"), now=self.NOW)
        self.assertIn("private", banner)


class TestRelativeTime(unittest.TestCase):
    NOW = datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc)

    def test_just_now(self):
        ts = "2026-05-04T11:59:30Z"  # 30s ago
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "just now")

    def test_minutes(self):
        ts = "2026-05-04T11:30:00Z"  # 30m ago
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "30 minutes ago")

    def test_hours(self):
        ts = "2026-05-04T08:00:00Z"  # 4h ago
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "4 hours ago")

    def test_days(self):
        ts = "2026-05-02T12:00:00Z"  # 2d ago
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "2 days ago")

    def test_weeks(self):
        ts = "2026-04-15T12:00:00Z"  # ~19 days ago → 2 weeks
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "2 weeks ago")

    def test_months(self):
        ts = "2026-02-04T12:00:00Z"  # ~89 days → 2 months
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "2 months ago")

    def test_years(self):
        ts = "2024-05-04T12:00:00Z"  # 2 years ago
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "2 years ago")

    def test_future_clamps_to_just_now(self):
        ts = "2026-06-01T00:00:00Z"  # in the future
        self.assertEqual(_format_relative_time(ts, now=self.NOW), "just now")

    def test_invalid_returns_none(self):
        self.assertIsNone(_format_relative_time("not-a-date", now=self.NOW))


if __name__ == "__main__":
    unittest.main()
