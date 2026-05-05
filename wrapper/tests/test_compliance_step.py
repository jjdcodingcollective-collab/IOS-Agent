"""Tests for the wrapper-level compliance orchestration (Tier 1 Step 6.6)."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wrapper.compliance_step import (
    MANIFEST_FILENAME,
    OVERRIDES_FILENAME,
    run_compliance_step,
)


def _capture_stdout(callable_, *args, **kwargs):
    buf = io.StringIO()
    saved = sys.stdout
    sys.stdout = buf
    try:
        result = callable_(*args, **kwargs)
    finally:
        sys.stdout = saved
    return result, buf.getvalue()


def _make_source(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.ts").write_text(
        'localStorage.setItem("k", "v");\n', encoding="utf-8"
    )
    (root / "package.json").write_text(
        json.dumps(
            {"name": "fake", "dependencies": {"@capacitor/filesystem": "^6.0.0"}}
        ),
        encoding="utf-8",
    )


class TestSuccessfulRun(unittest.TestCase):
    def test_writes_manifest_and_returns_success(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            result, _output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out
            )
            self.assertTrue(result.succeeded)
            self.assertEqual(result.error, None)
            self.assertEqual(result.manifest_path, out / MANIFEST_FILENAME)
            self.assertTrue((out / MANIFEST_FILENAME).exists())
            # 1 source finding (localStorage) + 1 plugin finding (@capacitor/filesystem) = 2
            self.assertEqual(len(result.findings), 2)

    def test_summary_lists_per_category_when_not_brief(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out, brief=False
            )
            self.assertIn("privacy manifest:", output)
            self.assertIn("FileTimestamp", output)
            self.assertIn("UserDefaults", output)

    def test_brief_suppresses_per_category_breakdown(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out, brief=True
            )
            self.assertIn("privacy manifest:", output)
            self.assertNotIn("FileTimestamp", output)
            self.assertNotIn("UserDefaults", output)

    def test_no_findings_emits_empty_manifest_and_terse_summary(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            (src / "src").mkdir()
            (src / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

            result, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out
            )
            self.assertTrue(result.succeeded)
            self.assertEqual(len(result.findings), 0)
            self.assertIn("0 finding(s) across 0 categories", output)
            self.assertTrue((out / MANIFEST_FILENAME).exists())


class TestOverrideDiscovery(unittest.TestCase):
    def test_picks_up_overrides_next_to_source(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)
            (src / OVERRIDES_FILENAME).write_text(
                "tracking:\n  enabled: true\n  tracking_domains: [analytics.example.com]\n",
                encoding="utf-8",
            )
            result, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out
            )
            self.assertTrue(result.succeeded)
            self.assertIn(f"with overrides from {OVERRIDES_FILENAME}", output)

    def test_no_overrides_file_is_silent_about_overrides(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)
            _, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out
            )
            self.assertNotIn("overrides", output)


class TestFailureModes(unittest.TestCase):
    def test_missing_source_dir_returns_warning_not_raise(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "ios-out"
            out.mkdir()
            result, output = _capture_stdout(
                run_compliance_step,
                source_dir=Path(td) / "does-not-exist",
                output_dir=out,
            )
            self.assertFalse(result.succeeded)
            self.assertIsNotNone(result.error)
            self.assertIn("warning:", output)
            self.assertFalse((out / MANIFEST_FILENAME).exists())

    def test_malformed_overrides_file_returns_warning_not_raise(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)
            # An overrides file whose top-level is a scalar, not a mapping.
            (src / OVERRIDES_FILENAME).write_text(
                "just a string, not a mapping\n", encoding="utf-8"
            )
            result, output = _capture_stdout(
                run_compliance_step, source_dir=src, output_dir=out
            )
            self.assertFalse(result.succeeded)
            self.assertIsNotNone(result.error)
            self.assertIn("warning:", output)
            self.assertIn("manifest", output.lower())


if __name__ == "__main__":
    unittest.main()
