"""Tests for ``wrapper.post_flight`` and ``wrapper.explainer``.

Run with::

    python -m unittest wrapper.tests.test_post_flight
"""

from __future__ import annotations

import unittest

from wrapper.explainer import format_branch_explainer
from wrapper.git_ops import CommitInfo, PushInfo
from wrapper.post_flight import (
    _parse_remote,
    default_base_branch,
    format_compare_url,
    format_post_flight,
    format_pr_command,
)
from wrapper.repo_metadata import RepoMetadata


def _commit(branch: str = "ios-conversion", revision: int = 1, needs_review: bool = False) -> CommitInfo:
    return CommitInfo(
        branch=branch,
        revision=revision,
        sha="abcdef1234567890",
        message="msg",
        needs_review=needs_review,
    )


def _push(remote_url: str | None = "https://github.com/acme/web-app.git", pushed: bool = True) -> PushInfo:
    return PushInfo(
        branch="ios-conversion",
        remote="origin",
        remote_url=remote_url,
        pushed=pushed,
        error=None,
    )


def _meta(default_branch: str = "main") -> RepoMetadata:
    return RepoMetadata(
        owner="acme",
        repo="web-app",
        default_branch=default_branch,
        visibility="public",
        primary_language="TypeScript",
        pushed_at="2026-05-02T12:00:00Z",
        stars=0,
        open_issues=0,
    )


class TestParseRemote(unittest.TestCase):
    def test_https_with_dot_git(self):
        self.assertEqual(_parse_remote("https://github.com/acme/web-app.git"), ("acme", "web-app"))

    def test_https_no_dot_git(self):
        self.assertEqual(_parse_remote("https://github.com/acme/web-app"), ("acme", "web-app"))

    def test_https_with_user(self):
        self.assertEqual(
            _parse_remote("https://user@github.com/acme/web-app.git"),
            ("acme", "web-app"),
        )

    def test_ssh(self):
        self.assertEqual(_parse_remote("git@github.com:acme/web-app.git"), ("acme", "web-app"))

    def test_ssh_protocol_form(self):
        self.assertEqual(
            _parse_remote("ssh://git@github.com/acme/web-app.git"),
            ("acme", "web-app"),
        )

    def test_non_github(self):
        self.assertIsNone(_parse_remote("https://gitlab.com/acme/web-app.git"))

    def test_blank(self):
        self.assertIsNone(_parse_remote(""))


class TestDefaultBaseBranch(unittest.TestCase):
    def test_uses_metadata_when_present(self):
        self.assertEqual(default_base_branch(_meta("trunk")), "trunk")

    def test_falls_back_to_main(self):
        self.assertEqual(default_base_branch(None), "main")

    def test_falls_back_when_default_branch_blank(self):
        meta = RepoMetadata(
            owner="x", repo="y", default_branch="", visibility="public",
            primary_language=None, pushed_at=None, stars=0, open_issues=0,
        )
        self.assertEqual(default_base_branch(meta), "main")


class TestFormatCompareUrl(unittest.TestCase):
    def test_https_remote(self):
        url = format_compare_url("https://github.com/acme/web-app.git", "main", "ios-conversion")
        self.assertEqual(
            url,
            "https://github.com/acme/web-app/compare/main...ios-conversion?expand=1",
        )

    def test_ssh_remote(self):
        url = format_compare_url("git@github.com:acme/web-app.git", "main", "ios-conversion")
        self.assertEqual(
            url,
            "https://github.com/acme/web-app/compare/main...ios-conversion?expand=1",
        )

    def test_non_github_returns_none(self):
        self.assertIsNone(
            format_compare_url("https://gitlab.com/acme/web-app.git", "main", "x"),
        )

    def test_branch_with_slash(self):
        url = format_compare_url(
            "https://github.com/acme/web-app",
            "main",
            "Requires-more-review/ios-conversion",
        )
        self.assertIn("compare/main...Requires-more-review/ios-conversion", url)


class TestFormatPrCommand(unittest.TestCase):
    def test_includes_branch_and_base(self):
        out = format_pr_command(_commit(), "main")
        self.assertIn("--head ios-conversion", out)
        self.assertIn("--base main", out)
        self.assertIn('--title "iOS conversion (rev 1)"', out)

    def test_revision_in_title(self):
        out = format_pr_command(_commit(revision=4), "main")
        self.assertIn('"iOS conversion (rev 4)"', out)

    def test_with_body_file(self):
        out = format_pr_command(
            _commit(),
            "main",
            summary_path=".ios-conversion/generation-summary.md",
        )
        self.assertIn('--body-file ".ios-conversion/generation-summary.md"', out)
        # title remains as the final line (no trailing \).
        self.assertTrue(out.rstrip().endswith('--title "iOS conversion (rev 1)"'))

    def test_without_body_file(self):
        out = format_pr_command(_commit(), "main")
        self.assertNotIn("--body-file", out)


class TestFormatPostFlight(unittest.TestCase):
    def test_includes_pr_command_and_compare_url(self):
        out = format_post_flight(_commit(), _push(), meta=_meta())
        self.assertIn("Open a PR:", out)
        self.assertIn("gh pr create", out)
        self.assertIn("…or open in browser:", out)
        self.assertIn("https://github.com/acme/web-app/compare/main...ios-conversion?expand=1", out)

    def test_no_compare_url_for_non_github_remote(self):
        push = PushInfo(
            branch="ios-conversion",
            remote="origin",
            remote_url="https://gitlab.com/acme/web-app.git",
            pushed=True,
            error=None,
        )
        out = format_post_flight(_commit(), push, meta=_meta())
        self.assertIn("gh pr create", out)
        self.assertNotIn("…or open in browser:", out)

    def test_uses_metadata_default_branch(self):
        out = format_post_flight(_commit(), _push(), meta=_meta(default_branch="trunk"))
        self.assertIn("--base trunk", out)
        self.assertIn("compare/trunk...ios-conversion", out)

    def test_falls_back_to_main_without_metadata(self):
        out = format_post_flight(_commit(), _push(), meta=None)
        self.assertIn("--base main", out)


class TestFormatBranchExplainer(unittest.TestCase):
    def test_clean_run(self):
        out = format_branch_explainer(_commit(needs_review=False))
        self.assertIn("What's on this branch:", out)
        self.assertIn("Sources/", out)
        self.assertIn(".ios-conversion/", out)
        self.assertIn("unprefixed because validation passed", out)
        # The clean-run version explains what the prefix WOULD have meant, but
        # does NOT instruct the reviewer to start with the summary report.
        self.assertNotIn("Start with .ios-conversion/generation-summary.md", out)

    def test_needs_review_run(self):
        out = format_branch_explainer(_commit(needs_review=True))
        self.assertIn("Requires-more-review/", out)
        self.assertIn("validation errors or low confidence", out)
        self.assertIn("generation-summary.md", out)


if __name__ == "__main__":
    unittest.main()
