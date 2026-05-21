"""Tests for the developer disclaimer and sign-off flow (MVP DoD §9.1)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wrapper.disclaimer import (
    DISCLAIMER_TEXT,
    DISCLAIMER_VERSION,
    show_and_confirm,
    _already_accepted,
    _load_dotfile,
    _record_acceptance,
)


def _patch_dotfile(tmp: Path):
    """Context manager: redirect the dotfile to a temp directory."""
    return patch("wrapper.disclaimer._DOTFILE", tmp / "disclaimer-accepted.json")


class TestShowAndConfirm(unittest.TestCase):

    def test_assume_yes_returns_true(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                result = show_and_confirm(assume_yes=True)
        self.assertTrue(result)

    def test_assume_yes_records_acceptance(self) -> None:
        with TemporaryDirectory() as tmp:
            dotfile = Path(tmp) / "disclaimer-accepted.json"
            with _patch_dotfile(Path(tmp)):
                show_and_confirm(assume_yes=True)
                data = json.loads(dotfile.read_text())
        self.assertIn(DISCLAIMER_VERSION, data)
        self.assertEqual(data[DISCLAIMER_VERSION]["via"], "--yes")

    def test_assume_yes_prints_disclaimer(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                with patch("builtins.print") as mock_print:
                    show_and_confirm(assume_yes=True)
        printed = " ".join(str(c) for call in mock_print.call_args_list for c in call.args)
        self.assertIn("ios-agent", printed)
        self.assertIn("NO GUARANTEE", printed)

    def test_already_accepted_skips_prompt(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                _record_acceptance(via="test")
                # Second call — no input() should be triggered
                with patch("builtins.input", side_effect=AssertionError("should not prompt")):
                    result = show_and_confirm(assume_yes=False)
        self.assertTrue(result)

    def test_interactive_agree_returns_true(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                with patch("sys.stdin.isatty", return_value=True):
                    with patch("builtins.input", return_value="agree"):
                        result = show_and_confirm(assume_yes=False)
        self.assertTrue(result)

    def test_interactive_decline_returns_false(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                with patch("sys.stdin.isatty", return_value=True):
                    with patch("builtins.input", return_value="no"):
                        result = show_and_confirm(assume_yes=False)
        self.assertFalse(result)

    def test_non_tty_without_yes_returns_false(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                with patch("sys.stdin.isatty", return_value=False):
                    result = show_and_confirm(assume_yes=False)
        self.assertFalse(result)

    def test_interactive_records_via_interactive(self) -> None:
        with TemporaryDirectory() as tmp:
            dotfile = Path(tmp) / "disclaimer-accepted.json"
            with _patch_dotfile(Path(tmp)):
                with patch("sys.stdin.isatty", return_value=True):
                    with patch("builtins.input", return_value="agree"):
                        show_and_confirm(assume_yes=False)
                data = json.loads(dotfile.read_text())
        self.assertEqual(data[DISCLAIMER_VERSION]["via"], "interactive")


class TestAlreadyAccepted(unittest.TestCase):

    def test_false_when_dotfile_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                self.assertFalse(_already_accepted())

    def test_false_when_different_version(self) -> None:
        with TemporaryDirectory() as tmp:
            dotfile = Path(tmp) / "disclaimer-accepted.json"
            dotfile.write_text(json.dumps({"0.0": {"accepted_at": "2020-01-01"}}))
            with _patch_dotfile(Path(tmp)):
                self.assertFalse(_already_accepted())

    def test_true_when_current_version_present(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                _record_acceptance(via="test")
                self.assertTrue(_already_accepted())


class TestLoadDotfile(unittest.TestCase):

    def test_returns_empty_dict_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            with _patch_dotfile(Path(tmp)):
                self.assertEqual(_load_dotfile(), {})

    def test_returns_empty_dict_on_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp:
            dotfile = Path(tmp) / "disclaimer-accepted.json"
            dotfile.write_text("not json at all", encoding="utf-8")
            with _patch_dotfile(Path(tmp)):
                self.assertEqual(_load_dotfile(), {})


class TestDisclaimerText(unittest.TestCase):

    def test_contains_no_guarantee(self) -> None:
        self.assertIn("NO GUARANTEE", DISCLAIMER_TEXT)

    def test_contains_developer_responsibility(self) -> None:
        self.assertIn("DEVELOPER RESPONSIBILITY", DISCLAIMER_TEXT)

    def test_contains_no_warranty(self) -> None:
        self.assertIn("NO WARRANTY", DISCLAIMER_TEXT)

    def test_contains_version_reference(self) -> None:
        self.assertIsNotNone(DISCLAIMER_VERSION)
        self.assertGreater(len(DISCLAIMER_VERSION), 0)
