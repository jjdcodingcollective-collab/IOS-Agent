"""Tests for converter/report/emitter.py — Tier 1 Step 7.6."""

from __future__ import annotations

import unittest

from converter.report import (
    Finding,
    LearningPattern,
    Provenance,
    ReportBuilder,
    ReportError,
    SCHEMA_VERSION,
    Source,
)


def _good_finding(**overrides) -> Finding:
    base = dict(
        id="x#0",
        category="compliance.privacy-manifest",
        severity="blocker",
        producer="compliance.api_scanner",
        file="src/app.ts",
        line=1,
        original_snippet="...",
        reason="r",
        recommended_fix="f",
        doc_link="https://example.com",
    )
    base.update(overrides)
    return Finding(**base)


def _good_learning(**overrides) -> LearningPattern:
    base = dict(
        pattern="p",
        occurrences=2,
        applied_translation="t",
        untranslatable_count=0,
        refactor_recommendation="r",
    )
    base.update(overrides)
    return LearningPattern(**base)


def _builder(**source_overrides) -> ReportBuilder:
    src_kwargs = dict(archetype="web", target_mode="wrap", root="/tmp/x", rev=1)
    src_kwargs.update(source_overrides)
    return ReportBuilder(
        source=Source(**src_kwargs),
        tool_version="ios-agent 0.1.0",
        clock=lambda: "2026-05-05T12:00:00Z",
    )


class TestFindingValidation(unittest.TestCase):
    def test_empty_id_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(id="")

    def test_empty_category_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(category="")

    def test_bad_severity_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(severity="catastrophic")

    def test_empty_producer_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(producer="")

    def test_empty_file_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(file="")

    def test_empty_reason_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(reason="")

    def test_empty_recommended_fix_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(recommended_fix="")

    def test_empty_doc_link_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(doc_link="")

    def test_confidence_above_one_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(confidence_score=1.5)

    def test_confidence_below_zero_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_finding(confidence_score=-0.1)

    def test_confidence_at_bounds_accepted(self) -> None:
        _good_finding(confidence_score=0.0)
        _good_finding(confidence_score=1.0)

    def test_provenance_optional(self) -> None:
        f = _good_finding(provenance=Provenance(model="m"))
        self.assertEqual(f.provenance.model, "m")


class TestLearningValidation(unittest.TestCase):
    def test_empty_pattern_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_learning(pattern="")

    def test_negative_occurrences_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_learning(occurrences=-1)

    def test_negative_untranslatable_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_learning(untranslatable_count=-1)

    def test_untranslatable_exceeding_occurrences_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _good_learning(occurrences=2, untranslatable_count=3)

    def test_zero_zero_accepted(self) -> None:
        _good_learning(occurrences=0, untranslatable_count=0)


class TestBuilderSourceValidation(unittest.TestCase):
    def test_bad_archetype_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _builder(archetype="cobol")

    def test_bad_target_mode_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _builder(target_mode="uplink")

    def test_empty_root_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _builder(root="")

    def test_zero_rev_rejected(self) -> None:
        with self.assertRaises(ReportError):
            _builder(rev=0)

    def test_empty_tool_version_rejected(self) -> None:
        with self.assertRaises(ReportError):
            ReportBuilder(
                source=Source(archetype="web", target_mode="wrap", root="/x", rev=1),
                tool_version="",
            )


class TestBuilderBehaviour(unittest.TestCase):
    def test_build_empty_validates(self) -> None:
        report = _builder().build()
        self.assertEqual(report.schema_version, SCHEMA_VERSION)
        self.assertEqual(report.layer_a_blockers, ())
        self.assertEqual(report.layer_b_manual_review, ())
        self.assertEqual(report.layer_c_learnings, ())

    def test_round_trip_through_to_dict(self) -> None:
        b = _builder()
        b.add_blocker(_good_finding(id="a#0"))
        b.add_manual_review(_good_finding(id="b#0", severity="warning"))
        b.add_learning(_good_learning(pattern="p1"))
        report = b.build()
        d = report.to_dict()
        self.assertEqual(len(d["layer_a_blockers"]), 1)
        self.assertEqual(len(d["layer_b_manual_review"]), 1)
        self.assertEqual(len(d["layer_c_learnings"]), 1)

    def test_dedup_on_finding_id(self) -> None:
        b = _builder()
        b.add_blocker(_good_finding(id="dup#0"))
        b.add_blocker(_good_finding(id="dup#0", reason="other"))
        report = b.build()
        self.assertEqual(len(report.layer_a_blockers), 1)
        self.assertEqual(report.layer_a_blockers[0].reason, "r")  # first wins

    def test_dedup_on_finding_id_across_layers(self) -> None:
        # If a producer accidentally adds the same id to both A and B, we
        # keep the first call (Layer A) and silently drop the duplicate.
        b = _builder()
        b.add_blocker(_good_finding(id="x#0"))
        b.add_manual_review(_good_finding(id="x#0", severity="warning"))
        report = b.build()
        self.assertEqual(len(report.layer_a_blockers), 1)
        self.assertEqual(len(report.layer_b_manual_review), 0)

    def test_dedup_on_learning_pattern(self) -> None:
        b = _builder()
        b.add_learning(_good_learning(pattern="p"))
        b.add_learning(_good_learning(pattern="p", occurrences=99))
        report = b.build()
        self.assertEqual(len(report.layer_c_learnings), 1)
        self.assertEqual(report.layer_c_learnings[0].occurrences, 2)

    def test_generated_at_uses_injected_clock(self) -> None:
        b = _builder()
        report = b.build()
        self.assertEqual(report.generated_at, "2026-05-05T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
