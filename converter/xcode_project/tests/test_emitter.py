"""Tests for the XcodeGen spec emitter (Tier 1 Step 8.3)."""

from __future__ import annotations

import plistlib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.entitlement_scanner import EntitlementFinding
from converter.xcode_project.emitter import (
    DEFAULT_DEPLOYMENT_TARGET,
    DEFAULT_SWIFT_VERSION,
    EmitterError,
    PLACEHOLDER_BUNDLE_ID_PREFIX,
    PLACEHOLDER_TEAM_ID,
    XcodeSpec,
    emit_xcode_project,
)


def _push_finding() -> EntitlementFinding:
    return EntitlementFinding(
        entitlement_key="aps-environment",
        capability="PushNotifications",
        label="Push Notifications",
        pattern="@capacitor/push-notifications",
        pattern_type="capacitor_plugin",
        file=Path("/tmp/package.json"),
        line=0,
        snippet="declared plugin: @capacitor/push-notifications",
        requires_developer_account=True,
    )


def _location_finding() -> EntitlementFinding:
    return EntitlementFinding(
        entitlement_key="",
        capability="Location",
        label="Location",
        pattern="navigator.geolocation.getCurrentPosition",
        pattern_type="js_api",
        file=Path("/tmp/src/loc.ts"),
        line=4,
        snippet="navigator.geolocation.getCurrentPosition(() => {});",
        requires_developer_account=False,
        usage_strings=("NSLocationWhenInUseUsageDescription",),
    )


def _camera_finding() -> EntitlementFinding:
    return EntitlementFinding(
        entitlement_key="",
        capability="Camera",
        label="Camera",
        pattern="@capacitor/camera",
        pattern_type="capacitor_plugin",
        file=Path("/tmp/package.json"),
        line=0,
        snippet="declared plugin: @capacitor/camera",
        requires_developer_account=False,
        usage_strings=("NSCameraUsageDescription",),
    )


class TestSpecValidation(unittest.TestCase):
    def test_valid_spec_round_trips(self) -> None:
        spec = XcodeSpec(app_name="DemoApp", bundle_id="com.acme.demo", team_id="ABCD123456")
        self.assertEqual(spec.app_name, "DemoApp")
        self.assertEqual(spec.deployment_target, DEFAULT_DEPLOYMENT_TARGET)
        self.assertEqual(spec.swift_version, DEFAULT_SWIFT_VERSION)

    def test_bad_bundle_id_rejected(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            spec = XcodeSpec(app_name="DemoApp", bundle_id="bad bundle id!", team_id="ABCD123456")
            with self.assertRaises(EmitterError):
                emit_xcode_project(spec=spec, output_dir=Path(td).resolve())

    def test_bad_team_id_rejected(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            spec = XcodeSpec(app_name="DemoApp", bundle_id="com.acme.demo", team_id="lowercase!")
            with self.assertRaises(EmitterError):
                emit_xcode_project(spec=spec, output_dir=Path(td).resolve())

    def test_placeholder_team_id_accepted(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id="com.acme.demo",
                team_id=PLACEHOLDER_TEAM_ID,
            )
            # No raise — placeholder is a deliberate ship-blocker, not invalid.
            emit_xcode_project(spec=spec, output_dir=Path(td).resolve())


class TestEmit(unittest.TestCase):
    def _spec(self, **overrides: object) -> XcodeSpec:
        defaults: dict[str, object] = {
            "app_name": "DemoApp",
            "bundle_id": "com.acme.demo",
            "team_id": "ABCD123456",
            "entitlements": (_push_finding(), _camera_finding(), _location_finding()),
            "has_privacy_manifest": True,
        }
        defaults.update(overrides)
        return XcodeSpec(**defaults)  # type: ignore[arg-type]

    def test_emits_all_expected_files(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            result = emit_xcode_project(spec=self._spec(), output_dir=out)
            self.assertTrue((out / "project.yml").is_file())
            self.assertTrue((out / "App" / "Info.plist").is_file())
            self.assertTrue((out / "App" / "AppDelegate.swift").is_file())
            self.assertTrue((out / "App" / "DemoApp.entitlements").is_file())
            self.assertTrue(
                (out / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "icon-1024.png").is_file()
            )
            self.assertTrue(
                (out / "App" / "Base.lproj" / "LaunchScreen.storyboard").is_file()
            )
            self.assertGreaterEqual(len(result.files_written), 7)

    def test_project_yml_has_expected_structure(self) -> None:
        """The emitter's own _validate_artifacts pass already round-trips
        the YAML through the wrapper's naive loader; here we pin
        line-level invariants the developer can grep for."""
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            emit_xcode_project(spec=self._spec(app_name="HelloApp"), output_dir=out)
            text = (out / "project.yml").read_text(encoding="utf-8")
            self.assertIn("name: HelloApp", text)
            self.assertIn("targets:", text)
            self.assertIn("PRODUCT_BUNDLE_IDENTIFIER: com.acme.demo", text)
            self.assertIn("DEVELOPMENT_TEAM: ABCD123456", text)
            self.assertIn(f'IPHONEOS_DEPLOYMENT_TARGET: "{DEFAULT_DEPLOYMENT_TARGET}"', text)
            # Entitlements block should reference the per-target file.
            self.assertIn("App/HelloApp.entitlements", text)

    def test_info_plist_includes_usage_strings(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            emit_xcode_project(spec=self._spec(), output_dir=out)
            plist = plistlib.loads((out / "App" / "Info.plist").read_bytes())
            self.assertIn("NSCameraUsageDescription", plist)
            self.assertIn("NSLocationWhenInUseUsageDescription", plist)
            # Push notifications is an entitlement, not a usage string —
            # must not leak a placeholder string for it.
            self.assertNotIn("NSPushNotificationsUsageDescription", plist)

    def test_entitlements_plist_contains_aps_environment(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            emit_xcode_project(spec=self._spec(), output_dir=out)
            plist = plistlib.loads((out / "App" / "DemoApp.entitlements").read_bytes())
            self.assertEqual(plist.get("aps-environment"), "development")

    def test_launch_screen_substitutes_app_name(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            emit_xcode_project(spec=self._spec(app_name="HelloApp"), output_dir=out)
            xml_text = (out / "App" / "Base.lproj" / "LaunchScreen.storyboard").read_text(
                encoding="utf-8"
            )
            ET.fromstring(xml_text)  # parses
            self.assertIn("HelloApp", xml_text)
            self.assertNotIn("{{APP_NAME}}", xml_text)


class TestPlaceholderFindings(unittest.TestCase):
    def test_placeholder_bundle_id_emits_finding(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id=f"{PLACEHOLDER_BUNDLE_ID_PREFIX}demo",
                team_id="ABCD123456",
            )
            result = emit_xcode_project(spec=spec, output_dir=out)
            categories = {f.category for f in result.findings}
            self.assertIn("xcode.placeholder.bundle-id", categories)

    def test_placeholder_team_id_emits_finding(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id="com.acme.demo",
                team_id=PLACEHOLDER_TEAM_ID,
            )
            result = emit_xcode_project(spec=spec, output_dir=out)
            categories = {f.category for f in result.findings}
            self.assertIn("xcode.placeholder.team-id", categories)

    def test_app_icon_finding_always_emitted(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id="com.acme.demo",
                team_id="ABCD123456",
            )
            result = emit_xcode_project(spec=spec, output_dir=out)
            categories = {f.category for f in result.findings}
            self.assertIn("xcode.placeholder.app-icon", categories)
            self.assertIn("xcode.placeholder.launch-screen", categories)

    def test_missing_privacy_manifest_emits_finding(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id="com.acme.demo",
                team_id="ABCD123456",
                has_privacy_manifest=False,
            )
            result = emit_xcode_project(spec=spec, output_dir=out)
            categories = {f.category for f in result.findings}
            self.assertIn("xcode.placeholder.privacy-manifest", categories)

    def test_findings_have_blocker_severity(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td).resolve()
            spec = XcodeSpec(
                app_name="DemoApp",
                bundle_id=f"{PLACEHOLDER_BUNDLE_ID_PREFIX}demo",
                team_id=PLACEHOLDER_TEAM_ID,
                has_privacy_manifest=False,
            )
            result = emit_xcode_project(spec=spec, output_dir=out)
            for f in result.findings:
                self.assertEqual(f.severity, "blocker", f"non-blocker: {f.id}")


if __name__ == "__main__":
    unittest.main()
