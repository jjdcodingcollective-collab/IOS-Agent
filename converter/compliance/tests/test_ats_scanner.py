"""Tests for the ATS configuration scanner (MVP §4.9)."""

from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.ats_scanner import (
    ATSFinding,
    scan_all_ats,
    scan_ats_configs,
    scan_ats_source,
    to_ats_findings,
    ATS_DOC_URL,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _write_json(root: Path, rel: str, data: dict) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


class TestScanAtsSource(unittest.TestCase):

    def test_detects_http_url_in_fetch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", """\
                const data = await fetch('http://api.example.com/endpoint');
            """)
            findings = scan_ats_source(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "http_url")
        self.assertIn("api.example.com", findings[0].url)

    def test_detects_http_url_in_axios(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", """\
                axios.get('http://backend.myapp.io/data');
            """)
            findings = scan_ats_source(root)
        self.assertTrue(any(f.kind == "http_url" for f in findings))

    def test_ignores_https_urls(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", """\
                fetch('https://api.example.com/data');
            """)
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])

    def test_ignores_localhost(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/dev.ts", """\
                const base = 'http://localhost:3000/api';
                const local2 = 'http://127.0.0.1:8080/health';
            """)
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])

    def test_ignores_loopback_ipv6(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/dev.ts", "const u = 'http://[::1]:3000/api';")
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])

    def test_skips_comment_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", """\
                // TODO: switch to http://api.example.com eventually
                const url = 'https://api.example.com';
            """)
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])

    def test_skips_node_modules(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "node_modules/lib/index.js", """\
                const url = 'http://cdn.example.com/asset';
            """)
            _write(root, "src/clean.ts", "const x = 1;")
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])

    def test_finding_has_correct_line(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", """\
                const a = 1;
                const b = 2;
                fetch('http://external.api.com/v1');
            """)
            findings = scan_ats_source(root)
        self.assertEqual(findings[0].line, 3)

    def test_deduplicates_same_url_same_line(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Same URL appears twice on same line — should produce 1 finding.
            _write(root, "src/api.ts",
                   "const x = 'http://a.com/b' || 'http://a.com/b';")
            findings = scan_ats_source(root)
        urls = [f.url for f in findings]
        self.assertEqual(urls.count("http://a.com/b"), 1)

    def test_clean_source_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "import React from 'react';")
            findings = scan_ats_source(root)
        self.assertEqual(findings, [])


class TestScanAtsConfigs(unittest.TestCase):

    def test_detects_allows_arbitrary_loads_json(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root, "config.json", {"allowsArbitraryLoads": True})
            findings = scan_ats_configs(root)
        self.assertTrue(any(f.kind == "arbitrary_loads" for f in findings))

    def test_detects_ns_arbitrary_loads_in_yaml(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "app.yaml", "NSAllowsArbitraryLoads: true\n")
            findings = scan_ats_configs(root)
        self.assertTrue(any(f.kind == "arbitrary_loads" for f in findings))

    def test_ignores_package_lock(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # package-lock.json should be skipped even with suspicious content.
            _write(root, "package-lock.json",
                   '{"allowsArbitraryLoads": true}')
            findings = scan_ats_configs(root)
        self.assertEqual(findings, [])

    def test_skips_comment_lines_in_config(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "app.yaml", """\
                # allowsArbitraryLoads: true  (disabled)
                secure: true
            """)
            findings = scan_ats_configs(root)
        self.assertEqual(findings, [])

    def test_capacitor_config_scanned(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root, "capacitor.config.json",
                        {"ios": {"allowsArbitraryLoads": True}})
            findings = scan_ats_configs(root)
        self.assertTrue(any(f.kind == "arbitrary_loads" for f in findings))

    def test_clean_config_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root, "config.json", {"secure": True})
            findings = scan_ats_configs(root)
        self.assertEqual(findings, [])


class TestScanAllAts(unittest.TestCase):

    def test_combines_source_and_config(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts",
                   "fetch('http://external.com/data');")
            _write_json(root, "config.json", {"allowsArbitraryLoads": True})
            findings = scan_all_ats(root)
        kinds = {f.kind for f in findings}
        self.assertIn("http_url", kinds)
        self.assertIn("arbitrary_loads", kinds)

    def test_empty_tree_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/clean.ts", "const x = 1;")
            findings = scan_all_ats(root)
        self.assertEqual(findings, [])


class TestToAtsFindings(unittest.TestCase):

    def _http_finding(self) -> ATSFinding:
        return ATSFinding(
            kind="http_url",
            file=Path("/src/api.ts"),
            line=5,
            snippet="fetch('http://example.com')",
            url="http://example.com",
        )

    def _arb_finding(self) -> ATSFinding:
        return ATSFinding(
            kind="arbitrary_loads",
            file=Path("/config.json"),
            line=3,
            snippet='{"allowsArbitraryLoads": true}',
        )

    def test_http_finding_is_warning(self) -> None:
        out = to_ats_findings([self._http_finding()])
        self.assertEqual(out[0].severity, "warning")

    def test_arbitrary_loads_finding_is_warning(self) -> None:
        out = to_ats_findings([self._arb_finding()])
        self.assertEqual(out[0].severity, "warning")

    def test_category_prefix(self) -> None:
        out = to_ats_findings([self._http_finding()])
        self.assertTrue(out[0].category.startswith("compliance.ats."))

    def test_http_reason_mentions_url(self) -> None:
        out = to_ats_findings([self._http_finding()])
        self.assertIn("http://example.com", out[0].reason)

    def test_arbitrary_loads_reason_mentions_guideline(self) -> None:
        out = to_ats_findings([self._arb_finding()])
        self.assertIn("4.5.4", out[0].reason)

    def test_doc_link_present(self) -> None:
        out = to_ats_findings([self._http_finding()])
        self.assertEqual(out[0].doc_link, ATS_DOC_URL)

    def test_source_root_strips_prefix(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts", "fetch('http://x.com/y');")
            findings = scan_ats_source(root)
        out = to_ats_findings(findings, source_root=root)
        self.assertFalse(out[0].file.startswith("/"))
        self.assertTrue(out[0].file.startswith("src/"))

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(to_ats_findings([]), [])

    def test_multiple_findings_unique_ids(self) -> None:
        out = to_ats_findings([self._http_finding(), self._arb_finding()])
        ids = [f.id for f in out]
        self.assertEqual(len(ids), len(set(ids)))
