"""Tests for schemas/report.schema.json — Tier 1 Step 7.6."""

from __future__ import annotations

import unittest
from pathlib import Path

from converter.compliance.privacy_manifest import _validate_against_schema


_SCHEMA = Path(__file__).resolve().parents[3] / "schemas" / "report.schema.json"


def _well_formed_report() -> dict:
    return {
        "schema_version": "1.0.0",
        "generated_at": "2026-05-05T12:00:00Z",
        "tool_version": "ios-agent 0.1.0",
        "source": {
            "archetype": "web",
            "target_mode": "wrap",
            "root": "/repo/x",
            "rev": 1,
        },
        "layer_a_blockers": [],
        "layer_b_manual_review": [],
        "layer_c_learnings": [],
    }


def _well_formed_finding() -> dict:
    return {
        "id": "compliance.privacy-manifest.userdefaults#0",
        "category": "compliance.privacy-manifest",
        "severity": "blocker",
        "producer": "compliance.api_scanner",
        "file": "src/app.ts",
        "line": 1,
        "original_snippet": 'localStorage.setItem("k", "v");',
        "attempted_translation": None,
        "reason": "Source uses localStorage which Apple classifies as UserDefaults.",
        "recommended_fix": "Confirm reason code or add an override.",
        "doc_link": "https://developer.apple.com/documentation/...",
        "confidence_score": None,
        "provenance": None,
    }


def _well_formed_learning() -> dict:
    return {
        "pattern": "localStorage-via-capacitor-preferences",
        "occurrences": 5,
        "applied_translation": "Mapped to @capacitor/preferences",
        "untranslatable_count": 1,
        "refactor_recommendation": "Consolidate keys behind a typed wrapper",
        "prior_rev_confidence": None,
        "delta": None,
    }


class TestHappyPath(unittest.TestCase):
    def test_empty_report_validates(self) -> None:
        self.assertEqual(_validate_against_schema(_well_formed_report(), _SCHEMA), [])

    def test_report_with_one_of_each_layer_validates(self) -> None:
        report = _well_formed_report()
        report["layer_a_blockers"].append(_well_formed_finding())
        b = dict(_well_formed_finding())
        b["id"] = "translation.force-unwrap#0"
        b["confidence_score"] = 0.42
        report["layer_b_manual_review"].append(b)
        report["layer_c_learnings"].append(_well_formed_learning())
        self.assertEqual(_validate_against_schema(report, _SCHEMA), [])

    def test_provenance_with_all_fields_validates(self) -> None:
        report = _well_formed_report()
        f = _well_formed_finding()
        f["provenance"] = {
            "model": "claude-opus-4-7",
            "prompt_template": "tmpl-1",
            "seed": 7,
        }
        report["layer_a_blockers"].append(f)
        self.assertEqual(_validate_against_schema(report, _SCHEMA), [])

    def test_seed_accepts_string_or_int(self) -> None:
        for seed_val in ("abc", 42):
            report = _well_formed_report()
            f = _well_formed_finding()
            f["provenance"] = {
                "model": None,
                "prompt_template": None,
                "seed": seed_val,
            }
            report["layer_a_blockers"].append(f)
            self.assertEqual(
                _validate_against_schema(report, _SCHEMA), [], f"seed={seed_val!r}"
            )


class TestRejectsMalformed(unittest.TestCase):
    def test_missing_top_level_field(self) -> None:
        report = _well_formed_report()
        del report["schema_version"]
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("schema_version" in e for e in errors), errors)

    def test_unknown_top_level_key(self) -> None:
        report = _well_formed_report()
        report["layer_d_extra"] = []
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("layer_d_extra" in e for e in errors), errors)

    def test_bad_archetype(self) -> None:
        report = _well_formed_report()
        report["source"]["archetype"] = "cobol"
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("cobol" in e for e in errors), errors)

    def test_bad_target_mode(self) -> None:
        report = _well_formed_report()
        report["source"]["target_mode"] = "uplink"
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("uplink" in e for e in errors), errors)

    def test_bad_severity(self) -> None:
        report = _well_formed_report()
        f = _well_formed_finding()
        f["severity"] = "catastrophic"
        report["layer_a_blockers"].append(f)
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("catastrophic" in e for e in errors), errors)

    def test_finding_missing_required_field(self) -> None:
        report = _well_formed_report()
        f = _well_formed_finding()
        del f["recommended_fix"]
        report["layer_a_blockers"].append(f)
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("recommended_fix" in e for e in errors), errors)

    def test_learning_missing_required_field(self) -> None:
        report = _well_formed_report()
        lp = _well_formed_learning()
        del lp["pattern"]
        report["layer_c_learnings"].append(lp)
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("pattern" in e for e in errors), errors)

    def test_finding_extra_unknown_property(self) -> None:
        report = _well_formed_report()
        f = _well_formed_finding()
        f["mystery"] = "x"
        report["layer_a_blockers"].append(f)
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("mystery" in e for e in errors), errors)

    def test_bad_schema_version_format(self) -> None:
        report = _well_formed_report()
        report["schema_version"] = "1"
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("pattern" in e for e in errors), errors)

    def test_bad_generated_at_format(self) -> None:
        report = _well_formed_report()
        report["generated_at"] = "yesterday"
        errors = _validate_against_schema(report, _SCHEMA)
        self.assertTrue(any("pattern" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
