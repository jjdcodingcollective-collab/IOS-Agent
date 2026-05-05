"""End-to-end integration test for Tier 1 Step 7 — report.md + report.json.

Drives ``_run_compliance_with_report`` against a real fixture (the same
``localStorage`` + ``@capacitor/filesystem`` shape Step 6 already uses) and
verifies that both report files land in the output dir, both validate
against the schema, and the rendered counts agree with the builder.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.privacy_manifest import _validate_against_schema
from wrapper.__main__ import (
    REPORT_FILENAME_JSON,
    REPORT_FILENAME_MD,
    _run_compliance_with_report,
)
from wrapper.compliance_step import MANIFEST_FILENAME


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = _REPO_ROOT / "schemas" / "report.schema.json"


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


class TestReportIntegration(unittest.TestCase):
    def test_writes_both_report_files(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _, output = _capture_stdout(
                _run_compliance_with_report,
                source_dir=src,
                output_dir=out,
                brief=True,
            )
            self.assertTrue((out / REPORT_FILENAME_MD).exists())
            self.assertTrue((out / REPORT_FILENAME_JSON).exists())
            self.assertTrue((out / MANIFEST_FILENAME).exists())
            self.assertIn("report:", output)

    def test_json_report_validates_against_schema(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _capture_stdout(
                _run_compliance_with_report,
                source_dir=src,
                output_dir=out,
                brief=True,
            )

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            errors = _validate_against_schema(data, _SCHEMA)
            self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_layer_a_contains_two_blockers_for_fixture(self) -> None:
        # localStorage source finding + @capacitor/filesystem plugin finding.
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _capture_stdout(
                _run_compliance_with_report,
                source_dir=src,
                output_dir=out,
                brief=True,
            )

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            self.assertEqual(len(data["layer_a_blockers"]), 2)
            self.assertEqual(len(data["layer_b_manual_review"]), 0)
            self.assertEqual(len(data["layer_c_learnings"]), 0)
            for f in data["layer_a_blockers"]:
                self.assertEqual(f["producer"], "compliance.api_scanner")
                self.assertTrue(f["category"].startswith("compliance.privacy-manifest"))
                self.assertEqual(f["severity"], "blocker")

    def test_markdown_report_contains_layer_headers(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _capture_stdout(
                _run_compliance_with_report,
                source_dir=src,
                output_dir=out,
                brief=True,
            )

            md = (out / REPORT_FILENAME_MD).read_text(encoding="utf-8")
            self.assertIn("# Conversion Report", md)
            self.assertIn("Layer A — Blockers", md)
            self.assertIn("Layer B — Manual Review", md)
            self.assertIn("Layer C — Learnings", md)

    def test_no_findings_still_writes_valid_reports(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            (src / "src").mkdir()
            (src / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

            _capture_stdout(
                _run_compliance_with_report,
                source_dir=src,
                output_dir=out,
                brief=True,
            )

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            self.assertEqual(data["layer_a_blockers"], [])
            self.assertEqual(data["layer_b_manual_review"], [])
            self.assertEqual(data["layer_c_learnings"], [])
            errors = _validate_against_schema(data, _SCHEMA)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
