"""End-to-end integration test for Tier 1 Step 7 — report.md + report.json.

Drives ``_run_post_conversion_steps`` (Step 8 superset of the old
``_run_compliance_with_report``) against a real fixture (the same
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
    PLACEHOLDER_TEAM_ID,
    REPORT_FILENAME_JSON,
    REPORT_FILENAME_MD,
    _default_bundle_id,
    _run_post_conversion_steps,
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


def _run(src: Path, out: Path) -> tuple[object, str]:
    """Wrap ``_run_post_conversion_steps`` with the test's default Step-8 args.

    The Step-7 tests pre-date the Step-8 args; we pin app_name=DemoApp and
    the placeholder bundle/team ids so the emitter still emits its
    placeholder Layer-A findings (matching the original Step-7 behaviour
    of "every fixture run produces *some* blockers").
    """
    return _capture_stdout(
        _run_post_conversion_steps,
        source_dir=src,
        output_dir=out,
        app_name="DemoApp",
        bundle_id=_default_bundle_id("DemoApp"),
        team_id=PLACEHOLDER_TEAM_ID,
        brief=True,
    )


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

            _, output = _run(src, out)
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

            _run(src, out)

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            errors = _validate_against_schema(data, _SCHEMA)
            self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_layer_a_contains_compliance_and_emitter_blockers(self) -> None:
        # Step 6 contributes: localStorage source + @capacitor/filesystem plugin.
        # Step 8 contributes: placeholder bundle-id, placeholder team-id,
        # placeholder app-icon, placeholder launch-screen. The fixture has
        # no entitlement-bearing patterns (filesystem isn't in the
        # entitlement catalogue), so no compliance.entitlement blockers.
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _run(src, out)

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            categories = {f["category"] for f in data["layer_a_blockers"]}
            for expected in (
                "compliance.privacy-manifest.userdefaults",
                "compliance.privacy-manifest.filetimestamp",
                "xcode.placeholder.bundle-id",
                "xcode.placeholder.team-id",
                "xcode.placeholder.app-icon",
                "xcode.placeholder.launch-screen",
            ):
                self.assertIn(expected, categories, f"missing blocker: {expected}")
            for f in data["layer_a_blockers"]:
                self.assertEqual(f["severity"], "blocker")

    def test_markdown_report_contains_layer_headers(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            _make_source(src)

            _run(src, out)

            md = (out / REPORT_FILENAME_MD).read_text(encoding="utf-8")
            self.assertIn("# Conversion Report", md)
            self.assertIn("Layer A — Blockers", md)
            self.assertIn("Layer B — Manual Review", md)
            self.assertIn("Layer C — Learnings", md)

    def test_clean_source_only_emits_emitter_placeholder_blockers(self) -> None:
        # No required-reason APIs, no entitlement patterns — but the emitter
        # always emits placeholder findings for app-icon + launch-screen, plus
        # bundle-id and team-id (since the test runs under the placeholder
        # defaults).
        with TemporaryDirectory(dir="workspace") as td:
            src = Path(td) / "src-tree"
            out = Path(td) / "ios-out"
            src.mkdir()
            out.mkdir()
            (src / "src").mkdir()
            (src / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

            _run(src, out)

            data = json.loads((out / REPORT_FILENAME_JSON).read_text(encoding="utf-8"))
            categories = {f["category"] for f in data["layer_a_blockers"]}
            for expected in (
                "xcode.placeholder.bundle-id",
                "xcode.placeholder.team-id",
                "xcode.placeholder.app-icon",
                "xcode.placeholder.launch-screen",
            ):
                self.assertIn(expected, categories)
            # No compliance findings for an empty TS file.
            self.assertFalse(any(c.startswith("compliance.") for c in categories))
            self.assertEqual(data["layer_b_manual_review"], [])
            self.assertEqual(data["layer_c_learnings"], [])
            errors = _validate_against_schema(data, _SCHEMA)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
