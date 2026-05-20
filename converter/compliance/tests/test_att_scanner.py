"""Tests for the ATT / IDFA compliance scanner (MVP §4.3)."""

from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.att_scanner import (
    ATTFinding,
    load_att_rules,
    scan_all_att,
    scan_att_plugins,
    scan_att_source,
    to_att_findings,
    ATT_USAGE_STRING_KEY,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _pkg(root: Path, deps: dict[str, str]) -> None:
    (root / "package.json").write_text(
        json.dumps({"dependencies": deps}), encoding="utf-8"
    )


class TestLoadAttRules(unittest.TestCase):
    def test_loads_att_rules(self) -> None:
        rules = load_att_rules()
        self.assertGreater(len(rules), 0)

    def test_rules_have_correct_category(self) -> None:
        rules = load_att_rules()
        patterns = [r.pattern for r in rules]
        self.assertIn("requestTrackingAuthorization", patterns)
        self.assertIn("firebase/analytics", patterns)

    def test_direct_rules_have_att1_reason(self) -> None:
        rules = load_att_rules()
        direct = [r for r in rules if r.pattern == "requestTrackingAuthorization"]
        self.assertEqual(direct[0].default_reason_code, "ATT.1")

    def test_sdk_rules_have_att2_reason(self) -> None:
        rules = load_att_rules()
        sdk = [r for r in rules if r.pattern == "firebase/analytics"]
        self.assertEqual(sdk[0].default_reason_code, "ATT.2")


class TestScanAttSource(unittest.TestCase):
    def test_detects_direct_att_call(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", """\
                import { ATTrackingManager } from 'some-lib';
                ATTrackingManager.requestTrackingAuthorization();
            """)
            findings = scan_att_source(root)
        self.assertTrue(any(f.pattern == "requestTrackingAuthorization" for f in findings))

    def test_detects_firebase_analytics_import(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/analytics.ts", """\
                import { getAnalytics } from 'firebase/analytics';
            """)
            findings = scan_att_source(root)
        self.assertTrue(any(f.pattern == "firebase/analytics" for f in findings))

    def test_detects_amplitude_import(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/track.ts", """\
                import * as amplitude from '@amplitude/analytics-browser';
            """)
            findings = scan_att_source(root)
        self.assertTrue(any("amplitude" in f.pattern for f in findings))

    def test_detects_facebook_sdk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/fb.ts", """\
                import FBSDK from 'react-native-fbsdk-next';
            """)
            findings = scan_att_source(root)
        self.assertTrue(any("fbsdk" in f.pattern for f in findings))

    def test_skips_comment_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", """\
                // ATTrackingManager.requestTrackingAuthorization — not called yet
                const x = 1;
            """)
            findings = scan_att_source(root)
        self.assertEqual(findings, [])

    def test_clean_source_produces_no_findings(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", """\
                import React from 'react';
                export default function App() { return null; }
            """)
            findings = scan_att_source(root)
        self.assertEqual(findings, [])

    def test_skips_node_modules(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "node_modules/firebase/analytics/index.js", """\
                export const getAnalytics = () => {};
            """)
            _write(root, "src/clean.ts", "const x = 1;")
            findings = scan_att_source(root)
        self.assertEqual(findings, [])

    def test_finding_has_correct_file_and_line(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/track.ts", """\
                const x = 1;
                import analytics from 'firebase/analytics';
            """)
            findings = scan_att_source(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 2)
        self.assertTrue(str(findings[0].file).endswith("track.ts"))


class TestScanAttPlugins(unittest.TestCase):
    def test_detects_capacitor_att_plugin(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _pkg(root, {"@capacitor-community/app-tracking-transparency": "^2.0.0"})
            findings = scan_att_plugins(root)
        self.assertTrue(
            any(f.pattern == "@capacitor-community/app-tracking-transparency" for f in findings)
        )

    def test_no_att_plugins_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _pkg(root, {"react": "^18.0.0"})
            findings = scan_att_plugins(root)
        self.assertEqual(findings, [])

    def test_plugin_finding_line_is_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _pkg(root, {"@capacitor-community/app-tracking-transparency": "^2.0.0"})
            findings = scan_att_plugins(root)
        self.assertEqual(findings[0].line, 0)


class TestScanAllAtt(unittest.TestCase):
    def test_source_and_plugin_combined(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", """\
                import analytics from 'firebase/analytics';
            """)
            _pkg(root, {"@capacitor-community/app-tracking-transparency": "^2.0.0"})
            findings = scan_all_att(root)
        patterns = {f.pattern for f in findings}
        self.assertIn("firebase/analytics", patterns)
        self.assertIn("@capacitor-community/app-tracking-transparency", patterns)

    def test_empty_tree_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/clean.ts", "const x = 1;")
            findings = scan_all_att(root)
        self.assertEqual(findings, [])


class TestToAttFindings(unittest.TestCase):
    def test_direct_finding_is_blocker(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "ATTrackingManager.requestTrackingAuthorization();")
            att = scan_all_att(root)
        findings = to_att_findings(att, source_root=root)
        self.assertTrue(all(f.severity == "blocker" for f in findings))

    def test_finding_category_prefix(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "ATTrackingManager.requestTrackingAuthorization();")
            att = scan_all_att(root)
        findings = to_att_findings(att, source_root=root)
        self.assertTrue(all(f.category.startswith("compliance.att.") for f in findings))

    def test_recommended_fix_mentions_usage_key(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "import analytics from 'firebase/analytics';")
            att = scan_all_att(root)
        findings = to_att_findings(att, source_root=root)
        self.assertTrue(
            all(ATT_USAGE_STRING_KEY in f.recommended_fix for f in findings)
        )

    def test_plugin_finding_uses_plugins_sentinel(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _pkg(root, {"@capacitor-community/app-tracking-transparency": "^2.0.0"})
            att = scan_att_plugins(root)
        findings = to_att_findings(att)
        self.assertEqual(findings[0].file, "(plugins)")

    def test_source_root_strips_prefix(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "import analytics from 'firebase/analytics';")
            att = scan_att_source(root)
        findings = to_att_findings(att, source_root=root)
        self.assertFalse(findings[0].file.startswith("/"))
        self.assertTrue(findings[0].file.startswith("src/"))
