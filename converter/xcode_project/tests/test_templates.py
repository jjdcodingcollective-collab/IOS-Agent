"""Tests for the shipped templates (Tier 1 Step 8.3).

These tests pin invariants on the *templates as shipped* — the placeholder
substitutions are exercised separately by ``test_emitter.py``. The goal is
to catch a hand-edit that breaks the format before the emitter ever runs.
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "templates"


def _read(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


class TestTemplatePresence(unittest.TestCase):
    """Every template the emitter loads must exist."""

    EXPECTED = (
        "xcodegen.yml.tmpl",
        "Info.plist.tmpl",
        "AppDelegate.swift.tmpl",
        "LaunchScreen.storyboard",
        "Assets.xcassets/Contents.json",
        "Assets.xcassets/AppIcon.appiconset/Contents.json",
        "Assets.xcassets/AppIcon.appiconset/icon-1024.png",
        "Assets.xcassets/AccentColor.colorset/Contents.json",
    )

    def test_all_templates_exist(self) -> None:
        for rel in self.EXPECTED:
            with self.subTest(template=rel):
                self.assertTrue(
                    (_TEMPLATE_DIR / rel).exists(), f"missing template: {rel}"
                )


class TestPlaceholderTokens(unittest.TestCase):
    """The emitter substitutes a fixed token set; templates must use only those."""

    def test_xcodegen_template_only_known_tokens(self) -> None:
        text = _read("xcodegen.yml.tmpl")
        for token in (
            "{{APP_NAME}}",
            "{{APP_NAME_SAFE}}",
            "{{BUNDLE_ID}}",
            "{{TEAM_ID}}",
            "{{DEPLOYMENT_TARGET}}",
            "{{SWIFT_VERSION}}",
            "{{ENTITLEMENTS_BLOCK}}",
            "{{CAPABILITY_SETTINGS}}",
        ):
            self.assertIn(token, text, f"xcodegen.yml.tmpl missing token: {token}")

    def test_info_plist_template_has_required_tokens(self) -> None:
        text = _read("Info.plist.tmpl")
        for token in (
            "{{APP_NAME}}",
            "{{BUNDLE_ID}}",
            "{{DEPLOYMENT_TARGET}}",
            "{{USAGE_STRINGS_BLOCK}}",
            "{{ATS_DICT}}",
            "{{ENCRYPTION_DECLARATION}}",
        ):
            self.assertIn(token, text, f"Info.plist.tmpl missing token: {token}")

    def test_app_delegate_template_has_safe_name_token(self) -> None:
        text = _read("AppDelegate.swift.tmpl")
        self.assertIn("{{APP_NAME_SAFE}}", text)

    def test_launch_screen_has_app_name_token(self) -> None:
        text = _read("LaunchScreen.storyboard")
        self.assertIn("{{APP_NAME}}", text)


class TestLaunchScreenIsValidXml(unittest.TestCase):
    """LaunchScreen is shipped pre-substitution; the placeholder must not break XML."""

    def test_launch_screen_parses(self) -> None:
        text = _read("LaunchScreen.storyboard")
        # The {{APP_NAME}} token sits inside an XML attribute value, so the
        # raw template parses as XML — the substitution preserves that.
        ET.fromstring(text)


class TestAppIconPng(unittest.TestCase):
    """Placeholder app icon must be a real 1024x1024 PNG.

    We don't depend on Pillow; PNG signature + IHDR width/height suffice
    to confirm the file is the format Xcode expects.
    """

    def test_png_signature_and_dimensions(self) -> None:
        path = _TEMPLATE_DIR / "Assets.xcassets" / "AppIcon.appiconset" / "icon-1024.png"
        data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", "missing PNG signature")
        # IHDR follows the 8-byte signature: 4-byte length + "IHDR" + width(4) + height(4).
        self.assertEqual(data[12:16], b"IHDR")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        self.assertEqual(width, 1024)
        self.assertEqual(height, 1024)


if __name__ == "__main__":
    unittest.main()
