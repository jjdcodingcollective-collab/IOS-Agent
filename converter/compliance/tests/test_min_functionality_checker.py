"""Tests for the minimum-functionality heuristic (MVP §4.2)."""

from __future__ import annotations

import plistlib
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.min_functionality_checker import (
    MIN_FUNC_DOC_URL,
    MinFuncFinding,
    check_min_functionality,
    to_min_func_findings,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _write_plist(root: Path, rel: str, data: dict) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as fh:
        plistlib.dump(data, fh)
    return p


class TestCheckMinFunctionality(unittest.TestCase):

    # ── fires when all three signals present ──────────────────────────────

    def test_fires_for_pure_static_wrapper(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/Home.tsx", "export default function Home() { return <div/>; }")
            finding = check_min_functionality(root)
        self.assertIsNotNone(finding)

    def test_finding_has_zero_plugins_and_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "const x = 1;")
            finding = check_min_functionality(root)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.plugin_count, 0)
        self.assertEqual(finding.route_count, 0)
        self.assertEqual(finding.usage_key_count, 0)

    # ── suppressed by Capacitor plugin import ──────────────────────────────

    def test_no_finding_when_capacitor_plugin_present(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/camera.ts",
                   "import { Camera } from '@capacitor/camera';")
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    def test_capacitor_hyphen_plugin_suppresses(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/plugin.ts",
                   "import SomePlugin from 'capacitor-some-plugin';")
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    def test_require_style_capacitor_import_suppresses(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/geo.js",
                   "const { Geolocation } = require('@capacitor/geolocation');")
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    # ── suppressed by NS*UsageDescription in Info.plist ───────────────────

    def test_no_finding_when_usage_description_present(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "const x = 1;")
            _write_plist(root, "App/Info.plist",
                         {"NSCameraUsageDescription": "We need your camera."})
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    def test_multiple_usage_keys_suppress(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "const x = 1;")
            _write_plist(root, "App/Info.plist", {
                "NSCameraUsageDescription": "Camera needed.",
                "NSMicrophoneUsageDescription": "Mic needed.",
            })
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    # ── suppressed by sufficient routes ───────────────────────────────────

    def test_no_finding_when_four_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/router.tsx", """\
                <Route path="/home" component={Home} />
                <Route path="/about" component={About} />
                <Route path="/settings" component={Settings} />
                <Route path="/profile" component={Profile} />
            """)
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    def test_exactly_three_routes_fires(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/router.tsx", """\
                <Route path="/home" component={Home} />
                <Route path="/about" component={About} />
                <Route path="/settings" component={Settings} />
            """)
            finding = check_min_functionality(root)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.route_count, 3)

    def test_vue_router_path_style(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/router.ts", """\
                const routes = [
                  { path: '/home', component: Home },
                  { path: '/about', component: About },
                  { path: '/settings', component: Settings },
                  { path: '/profile', component: Profile },
                ]
            """)
            finding = check_min_functionality(root)
        self.assertIsNone(finding)

    # ── skips node_modules ────────────────────────────────────────────────

    def test_capacitor_plugin_in_node_modules_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "node_modules/@capacitor/camera/index.js",
                   "import { Camera } from '@capacitor/camera';")
            _write(root, "src/app.ts", "const x = 1;")
            finding = check_min_functionality(root)
        self.assertIsNotNone(finding)

    # ── non-existent root ─────────────────────────────────────────────────

    def test_nonexistent_root_returns_none(self) -> None:
        finding = check_min_functionality(Path("/nonexistent/path/abc123"))
        self.assertIsNone(finding)


class TestToMinFuncFindings(unittest.TestCase):

    def _make_finding(self, route_count: int = 1) -> MinFuncFinding:
        return MinFuncFinding(
            plugin_count=0,
            route_count=route_count,
            usage_key_count=0,
            source_root=Path("/fake/src"),
        )

    def test_none_input_returns_empty(self) -> None:
        self.assertEqual(to_min_func_findings(None), [])

    def test_finding_returns_one_item(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertEqual(len(out), 1)

    def test_severity_is_warning(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertEqual(out[0].severity, "warning")

    def test_category_prefix(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertTrue(out[0].category.startswith("compliance.min"))

    def test_reason_mentions_route_count(self) -> None:
        out = to_min_func_findings(self._make_finding(route_count=2))
        self.assertIn("2", out[0].reason)

    def test_reason_mentions_guideline(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertIn("4.2", out[0].reason)

    def test_doc_link_correct(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertEqual(out[0].doc_link, MIN_FUNC_DOC_URL)

    def test_id_is_stable(self) -> None:
        out = to_min_func_findings(self._make_finding())
        self.assertEqual(out[0].id, "compliance.min-functionality#0")
