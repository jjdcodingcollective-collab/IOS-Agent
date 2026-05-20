"""Tests for ``wrapper.preflight``.

Run with::

    python -m pytest wrapper/tests/test_preflight.py

All tests use ``unittest.mock`` to patch the scanner calls — no real file I/O
beyond a temporary directory, and no network calls.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from converter.compliance import APIFinding, EntitlementFinding
from converter.compliance import ScannerError
from converter.report import Finding
from wrapper.preflight import (
    PreflightResult,
    format_preflight_report,
    run_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_finding(category: str = "NSPrivacyAccessedAPICategoryUserDefaults") -> APIFinding:
    return APIFinding(
        category=category,
        pattern="localStorage",
        pattern_type="js_api",
        file=Path("app.ts"),
        line=1,
        snippet="localStorage.getItem",
        reason_code="CA92.1",
        severity="blocker",
    )


def _ent_finding(capability: str = "push-notifications", requires_dev: bool = True) -> EntitlementFinding:
    return EntitlementFinding(
        entitlement_key="aps-environment",
        capability=capability,
        label="Push Notifications",
        pattern="@capacitor/push-notifications",
        pattern_type="capacitor_plugin",
        file=Path("package.json"),
        line=5,
        snippet='"@capacitor/push-notifications": "^5.0.0"',
        requires_developer_account=requires_dev,
        usage_strings=[],
    )


def _report_finding(severity: str = "blocker") -> Finding:
    return Finding(
        id="TEST-001",
        category="test",
        severity=severity,
        producer="test",
        file="app.ts",
        line=1,
        original_snippet="localStorage.getItem",
        reason="Test reason",
        recommended_fix="Fix it",
        doc_link="https://example.com",
    )


# ---------------------------------------------------------------------------
# PreflightResult unit tests
# ---------------------------------------------------------------------------

class TestPreflightResult(unittest.TestCase):
    def test_exit_code_clean(self):
        r = PreflightResult()
        self.assertEqual(r.exit_code, 0)
        self.assertFalse(r.has_blockers)
        self.assertFalse(r.scan_failed)

    def test_exit_code_blockers(self):
        r = PreflightResult(blockers=[_report_finding("blocker")])
        self.assertEqual(r.exit_code, 1)
        self.assertTrue(r.has_blockers)

    def test_exit_code_scan_error(self):
        r = PreflightResult(errors=["privacy scanner: root not found"])
        self.assertEqual(r.exit_code, 2)
        self.assertTrue(r.scan_failed)

    def test_scan_error_takes_priority_over_blockers(self):
        r = PreflightResult(
            blockers=[_report_finding("blocker")],
            errors=["something went wrong"],
        )
        self.assertEqual(r.exit_code, 2)

    def test_warnings_alone_give_exit_code_zero(self):
        r = PreflightResult(warnings=[_report_finding("warning")])
        self.assertEqual(r.exit_code, 0)
        self.assertFalse(r.has_blockers)


# ---------------------------------------------------------------------------
# run_preflight integration (scanners mocked)
# ---------------------------------------------------------------------------

class TestRunPreflight(unittest.TestCase):
    """run_preflight is tested by mocking the three scanner calls
    so no real file I/O occurs beyond the Path.resolve() call."""

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements", return_value=[])
    @patch("wrapper.preflight.scan_all", return_value=[])
    def test_clean_source_returns_no_findings(self, mock_api, mock_ent, mock_att):
        r = run_preflight(Path("/some/source"))
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.blockers, [])
        self.assertEqual(r.warnings, [])
        self.assertEqual(r.errors, [])
        mock_api.assert_called_once()
        mock_ent.assert_called_once()
        mock_att.assert_called_once()

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements", return_value=[])
    @patch("wrapper.preflight.scan_all")
    def test_api_findings_become_blockers(self, mock_api, mock_ent, mock_att):
        af = _api_finding()
        mock_api.return_value = [af]
        r = run_preflight(Path("/some/source"))
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(len(r.api_findings), 1)
        self.assertGreater(len(r.blockers), 0)

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements")
    @patch("wrapper.preflight.scan_all", return_value=[])
    def test_requires_dev_account_entitlement_is_blocker(self, mock_api, mock_ent, mock_att):
        ef = _ent_finding(requires_dev=True)
        mock_ent.return_value = [ef]
        r = run_preflight(Path("/some/source"))
        self.assertEqual(r.exit_code, 1)
        self.assertTrue(r.has_blockers)

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements")
    @patch("wrapper.preflight.scan_all", return_value=[])
    def test_permission_only_entitlement_is_warning(self, mock_api, mock_ent, mock_att):
        ef = _ent_finding(requires_dev=False)
        mock_ent.return_value = [ef]
        r = run_preflight(Path("/some/source"))
        self.assertEqual(r.exit_code, 0)
        self.assertFalse(r.has_blockers)
        self.assertGreater(len(r.warnings), 0)

    @patch("wrapper.preflight.scan_all_att", side_effect=ScannerError("att failed"))
    @patch("wrapper.preflight.scan_all_entitlements", side_effect=ScannerError("ent failed"))
    @patch("wrapper.preflight.scan_all", side_effect=ScannerError("api failed"))
    def test_scanner_errors_captured_not_raised(self, mock_api, mock_ent, mock_att):
        r = run_preflight(Path("/some/source"))
        self.assertEqual(r.exit_code, 2)
        self.assertEqual(len(r.errors), 3)
        self.assertIn("privacy scanner", r.errors[0])
        self.assertIn("entitlement scanner", r.errors[1])
        self.assertIn("ATT scanner", r.errors[2])

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements", return_value=[])
    @patch("wrapper.preflight.scan_all", side_effect=ScannerError("api failed"))
    def test_partial_scan_still_returns_ent_findings(self, mock_api, mock_ent, mock_att):
        """If the API scanner fails, we still run the entitlement scanner."""
        ef = _ent_finding(requires_dev=False)
        mock_ent.return_value = [ef]
        r = run_preflight(Path("/some/source"))
        # errors from api scanner
        self.assertIn("privacy scanner", r.errors[0])
        # but ent scanner ran and produced a warning
        self.assertEqual(len(r.ent_findings), 1)

    @patch("wrapper.preflight.scan_all_att", return_value=[])
    @patch("wrapper.preflight.scan_all_entitlements", return_value=[])
    @patch("wrapper.preflight.scan_all", return_value=[])
    def test_resolves_source_path(self, mock_api, mock_ent, mock_att):
        """run_preflight calls resolve() so scanners receive an absolute path."""
        r = run_preflight(Path("relative/path"))
        called_path = mock_api.call_args[0][0]
        self.assertTrue(called_path.is_absolute())


# ---------------------------------------------------------------------------
# format_preflight_report
# ---------------------------------------------------------------------------

class TestFormatPreflightReport(unittest.TestCase):
    SOURCE = Path("/project/my-app")

    def _clean_result(self) -> PreflightResult:
        return PreflightResult()

    def _blocked_result(self) -> PreflightResult:
        return PreflightResult(
            blockers=[_report_finding("blocker")],
            api_findings=[_api_finding()],
        )

    def _warning_result(self) -> PreflightResult:
        return PreflightResult(
            warnings=[_report_finding("warning")],
            ent_findings=[_ent_finding(requires_dev=False)],
        )

    def _error_result(self) -> PreflightResult:
        return PreflightResult(errors=["privacy scanner: root not found"])

    # Header
    def test_header_contains_source_path(self):
        out = format_preflight_report(self._clean_result(), self.SOURCE)
        self.assertIn("Pre-flight scan:", out)
        self.assertIn("my-app", out)

    # Clean path
    def test_clean_verdict(self):
        out = format_preflight_report(self._clean_result(), self.SOURCE)
        self.assertIn("Verdict: CLEAR", out)
        self.assertIn("No blockers", out)

    # Blocked path
    def test_blocked_verdict(self):
        out = format_preflight_report(self._blocked_result(), self.SOURCE)
        self.assertIn("Verdict: BLOCKED", out)
        self.assertIn("Layer-A blocker", out)

    def test_blocked_shows_api_category(self):
        out = format_preflight_report(self._blocked_result(), self.SOURCE)
        self.assertIn("UserDefaults", out)

    def test_blocked_shows_next_steps(self):
        out = format_preflight_report(self._blocked_result(), self.SOURCE)
        self.assertIn("Next steps:", out)
        self.assertIn("PrivacyInfo.xcprivacy", out)

    def test_brief_suppresses_per_finding_detail(self):
        out = format_preflight_report(self._blocked_result(), self.SOURCE, brief=True)
        self.assertIn("Verdict: BLOCKED", out)
        # Category detail is suppressed in brief mode
        self.assertNotIn("UserDefaults", out)
        # Next steps also suppressed
        self.assertNotIn("Next steps:", out)

    # Warning path
    def test_warning_verdict_is_clear_with_note(self):
        out = format_preflight_report(self._warning_result(), self.SOURCE)
        self.assertIn("Verdict: CLEAR", out)
        self.assertIn("Layer-B warning", out)

    def test_warning_shows_entitlement_label(self):
        out = format_preflight_report(self._warning_result(), self.SOURCE)
        self.assertIn("Push Notifications", out)

    # Error path
    def test_scan_error_shown(self):
        out = format_preflight_report(self._error_result(), self.SOURCE)
        self.assertIn("Scan errors", out)
        self.assertIn("root not found", out)

    def test_scan_error_verdict_says_incomplete(self):
        out = format_preflight_report(self._error_result(), self.SOURCE)
        self.assertIn("SCAN INCOMPLETE", out)

    # Both blockers and warnings
    def test_blockers_and_warnings_reported(self):
        r = PreflightResult(
            blockers=[_report_finding("blocker")],
            warnings=[_report_finding("warning")],
            api_findings=[_api_finding()],
            ent_findings=[_ent_finding(requires_dev=False)],
        )
        out = format_preflight_report(r, self.SOURCE)
        self.assertIn("Verdict: BLOCKED", out)
        self.assertIn("Layer-B warning", out)


# ---------------------------------------------------------------------------
# cmd_preflight integration (argparse → exit code)
# ---------------------------------------------------------------------------

class TestCmdPreflightArgparse(unittest.TestCase):
    """Smoke-test that the subcommand is wired correctly via build_parser."""

    def test_preflight_subcommand_registered(self):
        from wrapper.__main__ import build_parser
        parser = build_parser()
        # Parsing 'preflight /some/path' should not error
        args = parser.parse_args(["preflight", "/some/path"])
        self.assertEqual(args.command, "preflight")
        self.assertEqual(args.source, "/some/path")
        self.assertFalse(args.brief)

    def test_preflight_brief_flag(self):
        from wrapper.__main__ import build_parser
        parser = build_parser()
        args = parser.parse_args(["preflight", "/some/path", "--brief"])
        self.assertTrue(args.brief)

    @patch("wrapper.preflight.scan_all_entitlements", return_value=[])
    @patch("wrapper.preflight.scan_all", return_value=[])
    def test_cmd_preflight_returns_zero_on_clean(self, mock_api, mock_ent):
        import tempfile
        from wrapper.__main__ import cmd_preflight, build_parser
        with tempfile.TemporaryDirectory() as td:
            parser = build_parser()
            args = parser.parse_args(["preflight", td])
            code = cmd_preflight(args)
        self.assertEqual(code, 0)

    def test_cmd_preflight_returns_two_on_missing_dir(self):
        from wrapper.__main__ import cmd_preflight, build_parser
        parser = build_parser()
        args = parser.parse_args(["preflight", "/nonexistent/xyz/123"])
        code = cmd_preflight(args)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
