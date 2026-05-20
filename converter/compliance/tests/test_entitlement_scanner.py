"""Tests for the entitlement scanner (Tier 1 Step 8.2)."""

from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.entitlement_scanner import (
    EntitlementFinding,
    ScannerError,
    _apply_siwa_parity,
    load_rules,
    scan_all,
    scan_capacitor_plugins,
    scan_source,
    to_findings,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _capabilities(findings: list[EntitlementFinding]) -> set[str]:
    return {f.capability for f in findings}


class TestRuleLoading(unittest.TestCase):
    def test_load_default_rules(self) -> None:
        rules = load_rules()
        self.assertGreater(len(rules), 0)
        types = {r.pattern_type for r in rules}
        self.assertIn("ts_import", types)
        self.assertIn("capacitor_plugin", types)
        # The catalogue must cover every Apple-Developer-Account-required
        # capability the plan calls out — losing one of these silently breaks
        # ship-readiness gating.
        caps = {r.capability for r in rules if r.requires_developer_account}
        for cap in (
            "PushNotifications",
            "AppGroups",
            "iCloud",
            "HealthKit",
            "SignInWithApple",
        ):
            self.assertIn(cap, caps, f"missing dev-account capability: {cap}")

    def test_missing_rule_file_raises(self) -> None:
        with self.assertRaises(ScannerError) as ctx:
            load_rules(Path("/tmp/no-such-entitlements.yaml"))
        self.assertIn("not found", str(ctx.exception))


class TestSourceScan(unittest.TestCase):
    def test_detects_push_via_ts_import(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "src/main.ts",
                "import { PushNotifications } from '@capacitor/push-notifications';\n",
            )
            findings = scan_source(root)
            caps = _capabilities(findings)
            self.assertIn("PushNotifications", caps)

    def test_detects_geolocation_via_js_api(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "src/loc.ts",
                "navigator.geolocation.getCurrentPosition(() => {});\n",
            )
            findings = scan_source(root)
            self.assertIn("Location", _capabilities(findings))
            # Location is permission-prompted — must not require dev-account.
            for f in findings:
                if f.capability == "Location":
                    self.assertFalse(f.requires_developer_account)
                    self.assertIn("NSLocationWhenInUseUsageDescription", f.usage_strings)

    def test_detects_camera_via_getUserMedia(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "src/cam.ts",
                "navigator.mediaDevices.getUserMedia({ video: true });\n",
            )
            findings = scan_source(root)
            self.assertIn("Camera", _capabilities(findings))

    def test_skips_comment_lines(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "src/comment.ts",
                "// import { PushNotifications } from '@capacitor/push-notifications';\n",
            )
            findings = scan_source(root)
            self.assertEqual(findings, [])

    def test_skips_node_modules(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "node_modules/foo/bar.ts",
                "import { PushNotifications } from '@capacitor/push-notifications';\n",
            )
            findings = scan_source(root)
            self.assertEqual(findings, [])


class TestPluginScan(unittest.TestCase):
    def test_detects_plugin_via_package_json(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text(
                '{"dependencies":{"@capacitor/push-notifications":"^6.0.0"}}',
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertIn("PushNotifications", _capabilities(findings))

    def test_detects_plugin_via_capacitor_config(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "capacitor.config.ts").write_text(
                "plugins: { '@capacitor/camera': {} }",
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertIn("Camera", _capabilities(findings))


class TestScanAll(unittest.TestCase):
    def test_dedupes_plugin_and_source_for_same_capability(self) -> None:
        """A plugin declared in package.json AND imported in source should
        produce one finding per (capability, pattern, file) tuple."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text(
                '{"dependencies":{"@capacitor/push-notifications":"^6.0.0"}}',
                encoding="utf-8",
            )
            _write(
                root,
                "src/main.ts",
                "import { PushNotifications } from '@capacitor/push-notifications';\n"
                "import { PushNotifications as P2 } from '@capacitor/push-notifications';\n",
            )
            findings = scan_all(root)
            push = [f for f in findings if f.capability == "PushNotifications"]
            # One plugin finding (package.json) + one source finding (the
            # ts_import — multiple lines in the same file dedupe).
            self.assertEqual(len(push), 2)


class TestToFindings(unittest.TestCase):
    def test_dev_account_capability_is_blocker(self) -> None:
        ef = EntitlementFinding(
            entitlement_key="aps-environment",
            capability="PushNotifications",
            label="Push Notifications",
            pattern="@capacitor/push-notifications",
            pattern_type="capacitor_plugin",
            file=Path("/tmp/package.json"),
            line=0,
            snippet="declared plugin: @capacitor/push-notifications",
            requires_developer_account=True,
            usage_strings=tuple(),
        )
        out = to_findings([ef])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "blocker")
        self.assertIn("Apple Developer Account", out[0].reason)

    def test_permission_capability_is_warning(self) -> None:
        ef = EntitlementFinding(
            entitlement_key="",
            capability="Location",
            label="Location",
            pattern="navigator.geolocation.getCurrentPosition",
            pattern_type="js_api",
            file=Path("/tmp/src/loc.ts"),
            line=42,
            snippet="navigator.geolocation.getCurrentPosition(...)",
            requires_developer_account=False,
            usage_strings=("NSLocationWhenInUseUsageDescription",),
        )
        out = to_findings([ef])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "warning")
        self.assertIn("NSLocationWhenInUseUsageDescription", out[0].reason)

    def test_dedupes_capability_across_findings(self) -> None:
        """Two findings for the same capability collapse to one report Finding."""
        plugin = EntitlementFinding(
            entitlement_key="aps-environment",
            capability="PushNotifications",
            label="Push Notifications",
            pattern="@capacitor/push-notifications",
            pattern_type="capacitor_plugin",
            file=Path("/tmp/package.json"),
            line=0,
            snippet="declared plugin",
            requires_developer_account=True,
            usage_strings=tuple(),
        )
        source = EntitlementFinding(
            entitlement_key="aps-environment",
            capability="PushNotifications",
            label="Push Notifications",
            pattern="PushNotifications.register",
            pattern_type="js_api",
            file=Path("/tmp/src/m.ts"),
            line=3,
            snippet="PushNotifications.register()",
            requires_developer_account=True,
            usage_strings=tuple(),
        )
        out = to_findings([plugin, source])
        self.assertEqual(len(out), 1)
        # First finding wins for location.
        self.assertEqual(out[0].file, "(plugins)")


def _siwa_finding(*, siwa_trigger: bool, pattern: str = "test-pattern") -> EntitlementFinding:
    return EntitlementFinding(
        entitlement_key="com.apple.developer.applesignin",
        capability="SignInWithApple",
        label="Sign in with Apple",
        pattern=pattern,
        pattern_type="ts_import",
        file=Path("/tmp/src/auth.ts"),
        line=1,
        snippet=f"import {pattern}",
        requires_developer_account=True,
        usage_strings=tuple(),
        siwa_trigger=siwa_trigger,
    )


class TestSiwaParityLogic(unittest.TestCase):
    """_apply_siwa_parity() rewrites findings correctly for all three states."""

    def test_no_siwa_findings_unchanged(self) -> None:
        other = EntitlementFinding(
            entitlement_key="aps-environment",
            capability="PushNotifications",
            label="Push Notifications",
            pattern="PushNotifications.register",
            pattern_type="js_api",
            file=Path("/tmp/src/app.ts"),
            line=5,
            snippet="PushNotifications.register()",
            requires_developer_account=True,
            usage_strings=tuple(),
        )
        result = _apply_siwa_parity([other])
        self.assertEqual(result, [other])

    def test_trigger_only_findings_kept(self) -> None:
        trigger = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        result = _apply_siwa_parity([trigger])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].siwa_trigger)

    def test_direct_siwa_drops_trigger_findings(self) -> None:
        trigger = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        direct = _siwa_finding(siwa_trigger=False, pattern="@capacitor-community/apple-sign-in")
        result = _apply_siwa_parity([trigger, direct])
        # Only the direct SIWA finding survives.
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].siwa_trigger)

    def test_multiple_triggers_all_kept_when_no_direct(self) -> None:
        t1 = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        t2 = _siwa_finding(siwa_trigger=True, pattern="react-native-fbsdk-next")
        result = _apply_siwa_parity([t1, t2])
        self.assertEqual(len(result), 2)

    def test_non_siwa_findings_preserved_alongside_direct(self) -> None:
        direct = _siwa_finding(siwa_trigger=False)
        push = EntitlementFinding(
            entitlement_key="aps-environment",
            capability="PushNotifications",
            label="Push Notifications",
            pattern="PushNotifications.register",
            pattern_type="js_api",
            file=Path("/tmp/src/app.ts"),
            line=5,
            snippet="PushNotifications.register()",
            requires_developer_account=True,
            usage_strings=tuple(),
        )
        result = _apply_siwa_parity([direct, push])
        caps = {f.capability for f in result}
        self.assertIn("SignInWithApple", caps)
        self.assertIn("PushNotifications", caps)


class TestSiwaParityToFindings(unittest.TestCase):
    """to_findings() emits the correct Guideline 4.8 message for trigger findings."""

    def test_trigger_finding_mentions_guideline_4_8(self) -> None:
        trigger = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        out = to_findings([trigger])
        self.assertEqual(len(out), 1)
        self.assertIn("4.8", out[0].reason)
        self.assertIn("Sign in with Apple", out[0].reason)

    def test_trigger_finding_recommended_fix_has_steps(self) -> None:
        trigger = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        out = to_findings([trigger])
        self.assertIn("SignInWithApple", out[0].recommended_fix)

    def test_direct_siwa_finding_has_standard_message(self) -> None:
        direct = _siwa_finding(siwa_trigger=False, pattern="@capacitor-community/apple-sign-in")
        out = to_findings([direct])
        self.assertEqual(len(out), 1)
        self.assertNotIn("4.8", out[0].reason)
        self.assertIn("Apple Developer Account", out[0].reason)

    def test_trigger_is_blocker(self) -> None:
        trigger = _siwa_finding(siwa_trigger=True, pattern="@react-oauth/google")
        out = to_findings([trigger])
        self.assertEqual(out[0].severity, "blocker")


class TestSiwaDetectionEndToEnd(unittest.TestCase):
    """Integration: scan_all() detects SSO patterns and applies parity correctly."""

    def _write(self, root: Path, rel: str, body: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body), encoding="utf-8")

    def test_google_oauth_import_triggers_siwa_requirement(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "src/auth.ts", """\
                import { GoogleLogin } from '@react-oauth/google';
            """)
            findings = scan_all(root)
        siwa = [f for f in findings if f.capability == "SignInWithApple"]
        self.assertTrue(len(siwa) > 0)
        self.assertTrue(all(f.siwa_trigger for f in siwa))

    def test_firebase_sign_in_with_popup_triggers_siwa(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "src/auth.ts", """\
                import { signInWithPopup } from 'firebase/auth';
            """)
            findings = scan_all(root)
        siwa = [f for f in findings if f.capability == "SignInWithApple"]
        self.assertTrue(len(siwa) > 0)

    def test_direct_siwa_with_google_drops_trigger(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "src/auth.ts", """\
                import { GoogleLogin } from '@react-oauth/google';
                import { SignInWithApple } from '@capacitor-community/apple-sign-in';
            """)
            findings = scan_all(root)
        siwa = [f for f in findings if f.capability == "SignInWithApple"]
        # Direct SIWA present — no trigger findings should remain.
        self.assertTrue(all(not f.siwa_trigger for f in siwa))

    def test_clean_source_no_siwa_findings(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "src/app.ts", """\
                import React from 'react';
                export default function App() { return null; }
            """)
            findings = scan_all(root)
        siwa = [f for f in findings if f.capability == "SignInWithApple"]
        self.assertEqual(siwa, [])


if __name__ == "__main__":
    unittest.main()
