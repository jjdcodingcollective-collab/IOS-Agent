"""Tests for ``wrapper.pr_ops``.

Run with::

    python -m unittest wrapper.tests.test_pr_ops

No real ``gh`` invocations — ``subprocess.run`` is monkey-patched.
"""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from wrapper.pr_ops import PrInfo, extract_pr_url, gh_available, open_pr


class TestExtractPrUrl(unittest.TestCase):
    def test_url_alone(self):
        self.assertEqual(
            extract_pr_url("https://github.com/acme/web-app/pull/42"),
            "https://github.com/acme/web-app/pull/42",
        )

    def test_url_with_preamble(self):
        out = (
            "Creating pull request for ios-conversion into main "
            "in acme/web-app\n\n"
            "https://github.com/acme/web-app/pull/42\n"
        )
        self.assertEqual(
            extract_pr_url(out),
            "https://github.com/acme/web-app/pull/42",
        )

    def test_grabs_last_url_when_multiple(self):
        out = (
            "see https://github.com/acme/web-app/pull/41 for previous\n"
            "https://github.com/acme/web-app/pull/42\n"
        )
        self.assertEqual(
            extract_pr_url(out),
            "https://github.com/acme/web-app/pull/42",
        )

    def test_blank(self):
        self.assertIsNone(extract_pr_url(""))

    def test_no_url(self):
        self.assertIsNone(extract_pr_url("nothing here"))


class TestGhAvailable(unittest.TestCase):
    @mock.patch("wrapper.pr_ops.shutil.which", return_value=None)
    def test_gh_not_installed(self, _which):
        ok, hint = gh_available()
        self.assertFalse(ok)
        self.assertIn("brew install gh", hint)

    @mock.patch("wrapper.pr_ops.shutil.which", return_value="/usr/local/bin/gh")
    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_gh_not_authenticated(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=1,
            stdout="",
            stderr="not logged in",
        )
        ok, hint = gh_available()
        self.assertFalse(ok)
        self.assertIn("gh auth login", hint)

    @mock.patch("wrapper.pr_ops.shutil.which", return_value="/usr/local/bin/gh")
    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_gh_ok(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=0,
            stdout="logged in",
            stderr="",
        )
        ok, hint = gh_available()
        self.assertTrue(ok)
        self.assertIsNone(hint)


class TestOpenPr(unittest.TestCase):
    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_success_returns_url(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout=(
                "Creating pull request for ios-conversion into main in acme/web-app\n\n"
                "https://github.com/acme/web-app/pull/42\n"
            ),
            stderr="",
        )
        info = open_pr(
            "/tmp/fakerepo",
            base="main",
            head="ios-conversion",
            title="iOS conversion (rev 1)",
            body_path=".ios-conversion/generation-summary.md",
        )
        self.assertIsInstance(info, PrInfo)
        self.assertTrue(info.opened)
        self.assertEqual(info.url, "https://github.com/acme/web-app/pull/42")
        self.assertIsNone(info.error)

    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_existing_pr_surfaces_stderr(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=1,
            stdout="",
            stderr="a pull request for branch \"ios-conversion\" already exists",
        )
        info = open_pr(
            "/tmp/fakerepo",
            base="main",
            head="ios-conversion",
            title="iOS conversion (rev 2)",
        )
        self.assertFalse(info.opened)
        self.assertIsNone(info.url)
        self.assertIn("already exists", info.error)

    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_command_includes_body_file_when_supplied(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr="",
        )
        open_pr(
            "/tmp/fakerepo",
            base="main",
            head="branch",
            title="t",
            body_path="path/to/body.md",
        )
        args = run.call_args.args[0]
        self.assertIn("--body-file", args)
        self.assertIn("path/to/body.md", args)

    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_command_omits_body_file_when_none(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr="",
        )
        open_pr("/tmp/fakerepo", base="main", head="b", title="t")
        args = run.call_args.args[0]
        self.assertNotIn("--body-file", args)

    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_runs_inside_repo_path(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/x/y/pull/1", stderr="",
        )
        open_pr("/tmp/specificrepo", base="main", head="b", title="t")
        self.assertEqual(str(run.call_args.kwargs.get("cwd")), "/tmp/specificrepo")

    @mock.patch("wrapper.pr_ops.subprocess.run")
    def test_success_but_no_url_in_output(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="weird success", stderr="",
        )
        info = open_pr("/tmp/r", base="main", head="b", title="t")
        self.assertFalse(info.opened)
        self.assertIsNone(info.url)
        self.assertIn("no PR URL was found", info.error)

    @mock.patch(
        "wrapper.pr_ops.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["gh"], timeout=60),
    )
    def test_timeout_returns_error(self, _run):
        info = open_pr("/tmp/r", base="main", head="b", title="t")
        self.assertFalse(info.opened)
        self.assertIn("failed to invoke gh", info.error)


if __name__ == "__main__":
    unittest.main()
