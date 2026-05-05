"""Tests for the privacy manifest generator + validator (Tier 1 Step 6.3)."""

from __future__ import annotations

import json
import plistlib
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.api_scanner import APIFinding, scan_all
from converter.compliance.privacy_manifest import (
    ManifestError,
    generate_manifest,
    validate_manifest,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _finding(
    *,
    category: str = "NSPrivacyAccessedAPICategoryUserDefaults",
    pattern: str = "localStorage",
    pattern_type: str = "js_api",
    file: Path = Path("src/a.ts"),
    line: int = 1,
    snippet: str = "localStorage.setItem('k','v');",
    reason_code: str = "CA92.1",
) -> APIFinding:
    return APIFinding(
        category=category,
        pattern=pattern,
        pattern_type=pattern_type,
        file=file,
        line=line,
        snippet=snippet,
        reason_code=reason_code,
    )


def _decode(path: Path) -> dict:
    with path.open("rb") as fh:
        return plistlib.load(fh)


class TestHappyPathGeneration(unittest.TestCase):
    def test_generates_valid_manifest_from_findings(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            generate_manifest([_finding()], output_path=out)
            self.assertTrue(out.exists())
            self.assertEqual(validate_manifest(out), [])

            data = _decode(out)
            self.assertEqual(data["NSPrivacyTracking"], False)
            self.assertEqual(data["NSPrivacyTrackingDomains"], [])
            self.assertEqual(data["NSPrivacyCollectedDataTypes"], [])
            self.assertEqual(len(data["NSPrivacyAccessedAPITypes"]), 1)
            entry = data["NSPrivacyAccessedAPITypes"][0]
            self.assertEqual(entry["NSPrivacyAccessedAPIType"], "NSPrivacyAccessedAPICategoryUserDefaults")
            self.assertEqual(entry["NSPrivacyAccessedAPITypeReasons"], ["CA92.1"])

    def test_findings_dedupe_within_category(self) -> None:
        """Multiple findings for the same (category, reason_code) collapse to one entry."""
        findings = [_finding(line=1), _finding(line=2), _finding(line=3, file=Path("src/b.ts"))]
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            generate_manifest(findings, output_path=out)
            data = _decode(out)
            self.assertEqual(len(data["NSPrivacyAccessedAPITypes"]), 1)
            self.assertEqual(data["NSPrivacyAccessedAPITypes"][0]["NSPrivacyAccessedAPITypeReasons"], ["CA92.1"])

    def test_multiple_categories_each_get_own_entry(self) -> None:
        findings = [
            _finding(category="NSPrivacyAccessedAPICategoryUserDefaults", reason_code="CA92.1"),
            _finding(
                category="NSPrivacyAccessedAPICategoryFileTimestamp",
                reason_code="C617.1",
                pattern="@capacitor/filesystem",
                pattern_type="capacitor_plugin",
            ),
            _finding(
                category="NSPrivacyAccessedAPICategoryDiskSpace",
                reason_code="E174.1",
                pattern="navigator.storage.estimate",
            ),
        ]
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            generate_manifest(findings, output_path=out)
            data = _decode(out)
            categories = {e["NSPrivacyAccessedAPIType"] for e in data["NSPrivacyAccessedAPITypes"]}
            self.assertEqual(
                categories,
                {
                    "NSPrivacyAccessedAPICategoryUserDefaults",
                    "NSPrivacyAccessedAPICategoryFileTimestamp",
                    "NSPrivacyAccessedAPICategoryDiskSpace",
                },
            )

    def test_empty_findings_produces_valid_empty_manifest(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            generate_manifest([], output_path=out)
            self.assertEqual(validate_manifest(out), [])
            data = _decode(out)
            self.assertEqual(data["NSPrivacyAccessedAPITypes"], [])

    def test_creates_parent_directory(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "deeply" / "nested" / "PrivacyInfo.xcprivacy"
            generate_manifest([_finding()], output_path=out)
            self.assertTrue(out.exists())


class TestSchemaValidation(unittest.TestCase):
    """The validator must accept the generator's own output and reject corrupted manifests."""

    def test_round_trip_against_real_scan(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            _write(root, "src/a.ts", "localStorage.setItem('k','v');\n")
            (root / "package.json").write_text(
                json.dumps({"name": "x", "dependencies": {"@capacitor/filesystem": "^6.0.0"}}),
                encoding="utf-8",
            )
            findings = scan_all(root)
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest(findings, output_path=out)
            self.assertEqual(validate_manifest(out), [])

    def test_invalid_reason_code_for_category_is_rejected(self) -> None:
        """Using CA92.1 (UserDefaults) under FileTimestamp must fail validation."""
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.xcprivacy"
            with bad.open("wb") as fh:
                plistlib.dump(
                    {
                        "NSPrivacyTracking": False,
                        "NSPrivacyTrackingDomains": [],
                        "NSPrivacyCollectedDataTypes": [],
                        "NSPrivacyAccessedAPITypes": [
                            {
                                "NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryFileTimestamp",
                                "NSPrivacyAccessedAPITypeReasons": ["CA92.1"],
                            }
                        ],
                    },
                    fh,
                )
            errors = validate_manifest(bad)
            self.assertTrue(errors)
            self.assertTrue(any("CA92.1" in e for e in errors))

    def test_tracking_on_with_no_domains_is_rejected(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.xcprivacy"
            with bad.open("wb") as fh:
                plistlib.dump(
                    {
                        "NSPrivacyTracking": True,
                        "NSPrivacyTrackingDomains": [],
                        "NSPrivacyCollectedDataTypes": [],
                        "NSPrivacyAccessedAPITypes": [],
                    },
                    fh,
                )
            errors = validate_manifest(bad)
            self.assertTrue(errors)
            self.assertTrue(any("minimum" in e.lower() for e in errors))

    def test_unknown_category_is_rejected(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.xcprivacy"
            with bad.open("wb") as fh:
                plistlib.dump(
                    {
                        "NSPrivacyTracking": False,
                        "NSPrivacyTrackingDomains": [],
                        "NSPrivacyCollectedDataTypes": [],
                        "NSPrivacyAccessedAPITypes": [
                            {
                                "NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryNotARealCategory",
                                "NSPrivacyAccessedAPITypeReasons": ["CA92.1"],
                            }
                        ],
                    },
                    fh,
                )
            errors = validate_manifest(bad)
            self.assertTrue(errors)

    def test_missing_required_top_level_key_is_rejected(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.xcprivacy"
            with bad.open("wb") as fh:
                # Missing NSPrivacyTracking entirely.
                plistlib.dump(
                    {
                        "NSPrivacyTrackingDomains": [],
                        "NSPrivacyCollectedDataTypes": [],
                        "NSPrivacyAccessedAPITypes": [],
                    },
                    fh,
                )
            errors = validate_manifest(bad)
            self.assertTrue(any("NSPrivacyTracking" in e for e in errors))

    def test_missing_manifest_file_returns_error(self) -> None:
        errors = validate_manifest(Path("/tmp/does-not-exist.xcprivacy"))
        self.assertEqual(len(errors), 1)
        self.assertIn("not found", errors[0])

    def test_corrupted_plist_returns_error(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            bad = Path(td) / "bad.xcprivacy"
            bad.write_text("this is not a plist at all", encoding="utf-8")
            errors = validate_manifest(bad)
            self.assertTrue(errors)
            self.assertTrue(any("parse" in e.lower() or "plist" in e.lower() for e in errors))


class TestOverrideMerging(unittest.TestCase):
    def test_overrides_add_additional_reason_codes(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "privacy-overrides.yaml"
            ovr.write_text(
                "additional_categories:\n"
                "  - category: NSPrivacyAccessedAPICategoryUserDefaults\n"
                "    reason_codes: ['1C8F.1']\n",
                encoding="utf-8",
            )
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest([_finding()], output_path=out, overrides_path=ovr)
            data = _decode(out)
            self.assertEqual(len(data["NSPrivacyAccessedAPITypes"]), 1)
            reasons = data["NSPrivacyAccessedAPITypes"][0]["NSPrivacyAccessedAPITypeReasons"]
            # CA92.1 from the finding + 1C8F.1 from the override, sorted.
            self.assertEqual(reasons, ["1C8F.1", "CA92.1"])

    def test_override_duplicate_reason_code_does_not_double(self) -> None:
        """Override that re-asserts the scanner's reason code does not produce duplicates."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "privacy-overrides.yaml"
            ovr.write_text(
                "additional_categories:\n"
                "  - category: NSPrivacyAccessedAPICategoryUserDefaults\n"
                "    reason_codes: ['CA92.1']\n",
                encoding="utf-8",
            )
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest([_finding()], output_path=out, overrides_path=ovr)
            data = _decode(out)
            self.assertEqual(
                data["NSPrivacyAccessedAPITypes"][0]["NSPrivacyAccessedAPITypeReasons"],
                ["CA92.1"],
            )

    def test_override_enables_tracking(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "privacy-overrides.yaml"
            ovr.write_text(
                "tracking:\n"
                "  enabled: true\n"
                "  tracking_domains: [analytics.example.com]\n",
                encoding="utf-8",
            )
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest([], output_path=out, overrides_path=ovr)
            data = _decode(out)
            self.assertTrue(data["NSPrivacyTracking"])
            self.assertEqual(data["NSPrivacyTrackingDomains"], ["analytics.example.com"])

    def test_override_excludes_finding_by_id(self) -> None:
        f = _finding()
        finding_id = f"{f.category}:{f.pattern}:{f.file}:{f.line}"
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "privacy-overrides.yaml"
            ovr.write_text(
                f"excluded_findings:\n  - '{finding_id}'\n",
                encoding="utf-8",
            )
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest([f], output_path=out, overrides_path=ovr)
            data = _decode(out)
            self.assertEqual(data["NSPrivacyAccessedAPITypes"], [])

    def test_override_collected_data_types_pass_through(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "privacy-overrides.yaml"
            ovr.write_text(
                "collected_data_types:\n"
                "  - NSPrivacyCollectedDataType: NSPrivacyCollectedDataTypeEmailAddress\n"
                "    NSPrivacyCollectedDataTypeLinked: true\n"
                "    NSPrivacyCollectedDataTypeTracking: false\n"
                "    NSPrivacyCollectedDataTypePurposes: [NSPrivacyCollectedDataTypePurposeAppFunctionality]\n",
                encoding="utf-8",
            )
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest([], output_path=out, overrides_path=ovr)
            data = _decode(out)
            self.assertEqual(len(data["NSPrivacyCollectedDataTypes"]), 1)
            entry = data["NSPrivacyCollectedDataTypes"][0]
            self.assertEqual(entry["NSPrivacyCollectedDataType"], "NSPrivacyCollectedDataTypeEmailAddress")
            self.assertEqual(entry["NSPrivacyCollectedDataTypeLinked"], True)
            self.assertEqual(
                entry["NSPrivacyCollectedDataTypePurposes"],
                ["NSPrivacyCollectedDataTypePurposeAppFunctionality"],
            )

    def test_missing_override_file_is_not_an_error(self) -> None:
        """An overrides_path that points at a non-existent file must not raise."""
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            out = root / "PrivacyInfo.xcprivacy"
            generate_manifest(
                [_finding()],
                output_path=out,
                overrides_path=root / "does-not-exist.yaml",
            )
            self.assertTrue(out.exists())
            self.assertEqual(validate_manifest(out), [])

    def test_malformed_override_file_raises(self) -> None:
        with TemporaryDirectory(dir="workspace") as td:
            root = Path(td)
            ovr = root / "bad.yaml"
            ovr.write_text("just a string, not a mapping", encoding="utf-8")
            out = root / "PrivacyInfo.xcprivacy"
            with self.assertRaises(ManifestError):
                generate_manifest([_finding()], output_path=out, overrides_path=ovr)

    def test_shipped_template_loads_cleanly(self) -> None:
        """The committed privacy-overrides.yaml.template must load without error.

        Catches drift where someone updates the template but forgets to
        keep it parseable by the override loader.
        """
        template = Path(__file__).resolve().parents[3] / "templates" / "privacy-overrides.yaml.template"
        self.assertTrue(template.exists(), f"template missing: {template}")
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            generate_manifest([_finding()], output_path=out, overrides_path=template)
            self.assertEqual(validate_manifest(out), [])


class TestFailureModes(unittest.TestCase):
    def test_findings_with_invalid_reason_code_fail_validation_pre_write(self) -> None:
        """If a finding carries a reason code not in Apple's list, generation fails."""
        bogus = APIFinding(
            category="NSPrivacyAccessedAPICategoryUserDefaults",
            pattern="bogus",
            pattern_type="js_api",
            file=Path("x.ts"),
            line=1,
            snippet="",
            reason_code="ZZZZ.9",
        )
        with TemporaryDirectory(dir="workspace") as td:
            out = Path(td) / "PrivacyInfo.xcprivacy"
            with self.assertRaises(ManifestError):
                generate_manifest([bogus], output_path=out)
            # Critical: no partial file is left on disk.
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
