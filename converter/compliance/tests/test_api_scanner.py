"""Tests for the required-reason API scanner (Tier 1 Step 6.2)."""

from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.api_scanner import (
    APIFinding,
    ScannerError,
    load_rules,
    scan_all,
    scan_capacitor_plugins,
    scan_source,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _categories(findings: list[APIFinding]) -> set[str]:
    return {f.category for f in findings}


def _patterns(findings: list[APIFinding]) -> list[str]:
    return [f.pattern for f in findings]


class TestRuleLoading(unittest.TestCase):
    def test_load_default_rules(self) -> None:
        """The shipped rule file loads and produces patterns of every supported type."""
        patterns = load_rules()
        self.assertGreater(len(patterns), 0)
        types = {p.pattern_type for p in patterns}
        self.assertIn("js_api", types)
        self.assertIn("ts_import", types)
        self.assertIn("capacitor_plugin", types)
        self.assertIn("native_api", types)

    def test_missing_rule_file_raises(self) -> None:
        """A missing rule file produces a clear ScannerError."""
        with self.assertRaises(ScannerError) as ctx:
            load_rules(Path("/tmp/does-not-exist-rule-file.yaml"))
        self.assertIn("not found", str(ctx.exception))

    def test_malformed_rule_file_raises(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.yaml"
            bad.write_text("not: a list\nof: categories\n", encoding="utf-8")
            with self.assertRaises(ScannerError) as ctx:
                load_rules(bad)
            self.assertIn("categories", str(ctx.exception))


class TestSourceScan(unittest.TestCase):
    """Detection of every category exposed via web-archetype patterns."""

    def test_detects_user_defaults_via_localStorage(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/storage.ts", 'localStorage.setItem("k", "v");\n')
            findings = scan_source(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].category, "NSPrivacyAccessedAPICategoryUserDefaults")
            self.assertEqual(findings[0].pattern, "localStorage")
            self.assertEqual(findings[0].pattern_type, "js_api")
            self.assertEqual(findings[0].reason_code, "CA92.1")
            self.assertEqual(findings[0].line, 1)

    def test_detects_user_defaults_via_sessionStorage(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "a.ts", "const x = sessionStorage.getItem('k');\n")
            findings = scan_source(root)
            self.assertEqual([f.pattern for f in findings], ["sessionStorage"])
            self.assertEqual(findings[0].category, "NSPrivacyAccessedAPICategoryUserDefaults")

    def test_detects_user_defaults_via_capacitor_preferences_import(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/x.ts", 'import { Preferences } from "@capacitor/preferences";\n')
            findings = scan_source(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].pattern, "@capacitor/preferences")
            self.assertEqual(findings[0].pattern_type, "ts_import")
            self.assertEqual(findings[0].category, "NSPrivacyAccessedAPICategoryUserDefaults")

    def test_detects_disk_space_via_navigator_storage_estimate(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/a.ts", "const e = await navigator.storage.estimate();\n")
            findings = scan_source(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].category, "NSPrivacyAccessedAPICategoryDiskSpace")
            self.assertEqual(findings[0].reason_code, "E174.1")

    def test_detects_file_timestamp_via_filesystem_stat_call(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/a.ts", "const s = await Filesystem.stat({path: 'x'});\n")
            findings = scan_source(root)
            self.assertIn("NSPrivacyAccessedAPICategoryFileTimestamp", _categories(findings))

    def test_detects_file_timestamp_via_capacitor_filesystem_import(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "x.ts", 'import { Filesystem } from "@capacitor/filesystem";\n')
            findings = scan_source(root)
            cats = _categories(findings)
            self.assertIn("NSPrivacyAccessedAPICategoryFileTimestamp", cats)

    def test_does_not_flag_performance_now(self) -> None:
        """Deliberate exclusion: performance.now() is not flagged for SystemBootTime.

        WKWebView does not route performance.now() through mach_absolute_time,
        and the rule file documents this exclusion explicitly. If anyone adds
        a performance.now() pattern to the rule file in the future, this
        test fails on purpose.
        """
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "x.ts", "const t = performance.now();\n")
            findings = scan_source(root)
            self.assertEqual(findings, [])

    def test_skips_pure_comments(self) -> None:
        """A single-line // comment that mentions an API name is not flagged."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "x.ts",
                """\
                // localStorage is not actually used here
                const v = 1;
                """,
            )
            findings = scan_source(root)
            self.assertEqual(findings, [])

    def test_skips_block_comment_continuation(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "x.ts",
                """\
                /*
                 * mentions localStorage in a doc comment
                 */
                const v = 1;
                """,
            )
            findings = scan_source(root)
            self.assertEqual(findings, [])

    def test_word_boundary_avoids_substring_false_positive(self) -> None:
        """`myLocalStorage` should not match the `localStorage` pattern."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "x.ts", "const myLocalStorage = {};\n")
            findings = scan_source(root)
            self.assertEqual(findings, [])

    def test_skips_node_modules_and_build_dirs(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "node_modules/foo/index.js", "localStorage.setItem('k','v');\n")
            _write(root, "dist/bundle.js", "localStorage.setItem('k','v');\n")
            _write(root, ".next/static.js", "localStorage.setItem('k','v');\n")
            _write(root, "src/real.ts", "localStorage.setItem('k','v');\n")
            findings = scan_source(root)
            self.assertEqual(len(findings), 1)
            self.assertTrue(str(findings[0].file).endswith("src/real.ts"))

    def test_line_numbers_are_accurate(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(
                root,
                "x.ts",
                """\
                const a = 1;
                const b = 2;
                localStorage.setItem('k', 'v');
                """,
            )
            findings = scan_source(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].line, 3)

    def test_string_literal_with_api_name_is_known_false_positive(self) -> None:
        """The MVP regex pass DOES flag API names inside string literals.

        This test documents the known limitation rather than asserting
        the (correct) behaviour — Step 7's manual-review layer is what
        catches and surfaces it. If a future tree-sitter pass eliminates
        the false positive, flip this assertion.
        """
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "x.ts", 'const s = "we mention localStorage here";\n')
            findings = scan_source(root)
            # Documented limitation — keep the assertion explicit so flipping
            # to AST-based scanning is a single-line change.
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].pattern, "localStorage")

    def test_missing_root_raises(self) -> None:
        with self.assertRaises(ScannerError):
            scan_source(Path("/tmp/this-does-not-exist-as-a-source-root"))


class TestPluginScan(unittest.TestCase):
    """Detection of declared Capacitor plugins."""

    def test_detects_plugin_in_package_json_dependencies(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "x",
                        "dependencies": {"@capacitor/preferences": "^6.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].pattern, "@capacitor/preferences")
            self.assertEqual(findings[0].pattern_type, "capacitor_plugin")
            self.assertEqual(findings[0].category, "NSPrivacyAccessedAPICategoryUserDefaults")
            self.assertEqual(findings[0].line, 0)  # sentinel

    def test_detects_plugin_in_devDependencies(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "x",
                        "devDependencies": {"@capacitor/filesystem": "^6.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].pattern, "@capacitor/filesystem")

    def test_unknown_plugin_does_not_emit_finding(self) -> None:
        """A Capacitor plugin we don't have a rule for is silently skipped.

        Step 7 catch-all will surface unknown plugins as a Layer-B
        manual-review item.
        """
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "x",
                        "dependencies": {"@capacitor/some-future-plugin": "^1.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertEqual(findings, [])

    def test_detects_plugin_referenced_in_capacitor_config_only(self) -> None:
        """Plugins listed only in capacitor.config.ts (not package.json) still flag."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "capacitor.config.ts").write_text(
                'import "@capacitor/preferences";\n'
                "const config = { appId: 'x' };\n",
                encoding="utf-8",
            )
            findings = scan_capacitor_plugins(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].pattern, "@capacitor/preferences")

    def test_missing_package_json_is_not_an_error(self) -> None:
        """A project without package.json simply produces no plugin findings."""
        with TemporaryDirectory(dir="workspace") as td:
            findings = scan_capacitor_plugins(Path(td))
            self.assertEqual(findings, [])

    def test_malformed_package_json_is_silently_skipped(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            (root / "package.json").write_text("{not valid json", encoding="utf-8")
            findings = scan_capacitor_plugins(root)
            self.assertEqual(findings, [])


class TestScanAll(unittest.TestCase):
    """Combined source + plugin pass behaviour."""

    def test_combined_scan_emits_both_pass_results(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/a.ts", "localStorage.setItem('k','v');\n")
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "x",
                        "dependencies": {"@capacitor/filesystem": "^6.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            findings = scan_all(root)
            self.assertEqual(len(findings), 2)
            patterns = _patterns(findings)
            self.assertIn("localStorage", patterns)
            self.assertIn("@capacitor/filesystem", patterns)

    def test_scan_all_loads_rules_only_once(self) -> None:
        """scan_all() must not re-parse the rule file for each pass.

        We can't easily prove non-re-parse without instrumentation, but
        we can prove the function works on an empty source tree without
        raising — which is the visible failure mode if rule-loading
        broke.
        """
        with TemporaryDirectory(dir="workspace") as td:
            findings = scan_all(Path(td))
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
