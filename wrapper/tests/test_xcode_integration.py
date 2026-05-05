"""End-to-end test: wrapper runs Step 6 + Step 8, report contains both layers.

Tier 1 Step 8.6.

This test exercises ``run_xcode_step`` against a fixture that imports the
``@capacitor/push-notifications`` plugin and calls
``navigator.geolocation.getCurrentPosition``. The expectation is:
  - Layer A includes Push Notifications (dev-account capability) +
    placeholder team-id + placeholder app-icon + placeholder launch-screen.
  - Layer B includes Location (permission-prompted).
  - The report builder validates clean against the schema (build() raises
    on any structural problem).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.report import ReportBuilder, Source
from wrapper.xcode_step import run_xcode_step


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


class TestXcodeIntegration(unittest.TestCase):
    def _run(self, *, bundle_id: str, team_id: str) -> tuple[Path, ReportBuilder]:
        with TemporaryDirectory(dir="workspace") as td:
            td_path = Path(td).resolve()
            source_dir = td_path / "src-fixture"
            output_dir = td_path / "out"
            source_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            _write(
                source_dir,
                "package.json",
                '{"dependencies":{"@capacitor/push-notifications":"^6.0.0"}}',
            )
            _write(
                source_dir,
                "src/main.ts",
                "import { PushNotifications } from '@capacitor/push-notifications';\n"
                "navigator.geolocation.getCurrentPosition(() => {});\n",
            )
            builder = ReportBuilder(
                source=Source(
                    archetype="web",
                    target_mode="wrap",
                    root=str(source_dir),
                    rev=1,
                ),
                tool_version="ios-agent test",
            )
            result = run_xcode_step(
                source_dir=source_dir,
                output_dir=output_dir,
                app_name="DemoApp",
                bundle_id=bundle_id,
                team_id=team_id,
                brief=True,
                report_builder=builder,
            )
            self.assertTrue(result.succeeded, f"xcode step failed: {result.error}")
            self.assertTrue((output_dir / "project.yml").is_file())
            return output_dir, builder

    def test_emits_project_and_pushes_findings_into_report(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            td_path = Path(td).resolve()
            source_dir = td_path / "src-fixture"
            output_dir = td_path / "out"
            source_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            _write(
                source_dir,
                "package.json",
                '{"dependencies":{"@capacitor/push-notifications":"^6.0.0"}}',
            )
            _write(
                source_dir,
                "src/main.ts",
                "import { PushNotifications } from '@capacitor/push-notifications';\n"
                "navigator.geolocation.getCurrentPosition(() => {});\n",
            )
            builder = ReportBuilder(
                source=Source(
                    archetype="web",
                    target_mode="wrap",
                    root=str(source_dir),
                    rev=1,
                ),
                tool_version="ios-agent test",
            )
            result = run_xcode_step(
                source_dir=source_dir,
                output_dir=output_dir,
                app_name="DemoApp",
                bundle_id="com.example.demo",
                team_id="TODO_TEAMID",
                brief=True,
                report_builder=builder,
            )
            self.assertTrue(result.succeeded, f"xcode step failed: {result.error}")

            report = builder.build()
            blocker_cats = {f.category for f in report.layer_a_blockers}
            warning_cats = {f.category for f in report.layer_b_manual_review}

            # Layer A: emitter placeholders + dev-account capability.
            self.assertIn("xcode.placeholder.bundle-id", blocker_cats)
            self.assertIn("xcode.placeholder.team-id", blocker_cats)
            self.assertIn("xcode.placeholder.app-icon", blocker_cats)
            self.assertIn("xcode.placeholder.launch-screen", blocker_cats)
            self.assertIn("compliance.entitlement.pushnotifications", blocker_cats)
            # has_privacy_manifest defaults to False here (no PrivacyInfo
            # written by this isolated test) so the privacy-manifest blocker
            # should also surface.
            self.assertIn("xcode.placeholder.privacy-manifest", blocker_cats)

            # Layer B: permission-prompted capability.
            self.assertIn("compliance.entitlement.location", warning_cats)

            # Spec round-trips as JSON (renderer-side proof the report is
            # well-formed for the wrapper's downstream writers).
            from converter.report import render_json
            data = json.loads(render_json(report))
            self.assertEqual(data["source"]["target_mode"], "wrap")

    def test_real_bundle_id_skips_bundle_finding(self) -> None:
        out, builder = self._run(bundle_id="com.acme.demo", team_id="ABCD123456")
        report = builder.build()
        blocker_cats = {f.category for f in report.layer_a_blockers}
        self.assertNotIn("xcode.placeholder.bundle-id", blocker_cats)
        self.assertNotIn("xcode.placeholder.team-id", blocker_cats)
        # Icon + launch-screen always emit.
        self.assertIn("xcode.placeholder.app-icon", blocker_cats)
        self.assertIn("xcode.placeholder.launch-screen", blocker_cats)


if __name__ == "__main__":
    unittest.main()
