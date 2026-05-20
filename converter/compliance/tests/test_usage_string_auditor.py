"""Tests for the usage string completeness auditor (MVP §4.5)."""

from __future__ import annotations

import plistlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.usage_string_auditor import (
    AuditorError,
    UsageStringFinding,
    audit_info_plist,
    to_usage_findings,
    USAGE_STRING_DOC_URL,
)


def _write_plist(path: Path, data: dict) -> None:
    with path.open("wb") as f:
        plistlib.dump(data, f)


class TestAuditInfoPlist(unittest.TestCase):

    def test_missing_file_returns_empty(self) -> None:
        findings = audit_info_plist(Path("/nonexistent/Info.plist"))
        self.assertEqual(findings, [])

    def test_clean_plist_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {
                "CFBundleIdentifier": "com.example.app",
                "NSCameraUsageDescription": "We use your camera to scan QR codes.",
                "NSMicrophoneUsageDescription": "We record audio for voice notes.",
            })
            findings = audit_info_plist(p)
        self.assertEqual(findings, [])

    def test_todo_placeholder_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {
                "NSCameraUsageDescription": (
                    "TODO: explain why this app needs Camera access "
                    "(replaces the auto-generated NSCameraUsageDescription)."
                ),
            })
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].key, "NSCameraUsageDescription")

    def test_empty_string_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSLocationWhenInUseUsageDescription": ""})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)

    def test_whitespace_only_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSMicrophoneUsageDescription": "   "})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)

    def test_placeholder_keyword_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSPhotoLibraryUsageDescription": "placeholder description"})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)

    def test_auto_generated_keyword_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSContactsUsageDescription": "replaces the auto-generated NSContactsUsageDescription"})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)

    def test_non_usage_keys_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {
                "CFBundleIdentifier": "TODO: replace me",
                "NSCameraUsageDescription": "We scan barcodes.",
            })
            findings = audit_info_plist(p)
        # CFBundleIdentifier is not a usage description key — should not flag.
        self.assertEqual(findings, [])

    def test_multiple_placeholders_all_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {
                "NSCameraUsageDescription": "TODO: camera",
                "NSMicrophoneUsageDescription": "",
                "NSLocationWhenInUseUsageDescription": "placeholder",
            })
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 3)

    def test_mixed_clean_and_placeholder(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {
                "NSCameraUsageDescription": "We use camera to scan QR codes.",
                "NSMicrophoneUsageDescription": "TODO: fill in",
            })
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].key, "NSMicrophoneUsageDescription")

    def test_finding_records_plist_path(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSCameraUsageDescription": "TODO: camera"})
            findings = audit_info_plist(p)
        self.assertEqual(findings[0].plist_path, p)

    def test_invalid_plist_raises_auditor_error(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            p.write_bytes(b"not a plist at all <<<")
            with self.assertRaises(AuditorError):
                audit_info_plist(p)

    def test_fixme_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSContactsUsageDescription": "FIXME: describe"})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)

    def test_nsusertrackingusagedescription_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "Info.plist"
            _write_plist(p, {"NSUserTrackingUsageDescription": "TODO: tracking reason"})
            findings = audit_info_plist(p)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].key, "NSUserTrackingUsageDescription")


class TestToUsageFindings(unittest.TestCase):

    def _finding(self, key: str = "NSCameraUsageDescription") -> UsageStringFinding:
        return UsageStringFinding(
            key=key,
            value="TODO: describe camera use",
            plist_path=Path("/output/App/Info.plist"),
        )

    def test_finding_is_blocker(self) -> None:
        out = to_usage_findings([self._finding()])
        self.assertEqual(out[0].severity, "blocker")

    def test_category_prefix(self) -> None:
        out = to_usage_findings([self._finding()])
        self.assertTrue(out[0].category.startswith("compliance.usage-string."))

    def test_reason_mentions_key(self) -> None:
        out = to_usage_findings([self._finding()])
        self.assertIn("NSCameraUsageDescription", out[0].reason)

    def test_recommended_fix_mentions_key(self) -> None:
        out = to_usage_findings([self._finding()])
        self.assertIn("NSCameraUsageDescription", out[0].recommended_fix)

    def test_doc_link_present(self) -> None:
        out = to_usage_findings([self._finding()])
        self.assertEqual(out[0].doc_link, USAGE_STRING_DOC_URL)

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(to_usage_findings([]), [])

    def test_multiple_findings_unique_ids(self) -> None:
        f1 = self._finding("NSCameraUsageDescription")
        f2 = self._finding("NSMicrophoneUsageDescription")
        out = to_usage_findings([f1, f2])
        ids = [f.id for f in out]
        self.assertEqual(len(ids), len(set(ids)))
