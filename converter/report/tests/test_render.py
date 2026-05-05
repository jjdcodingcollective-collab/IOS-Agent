"""Tests for converter/report/render.py — Tier 1 Step 7.6."""

from __future__ import annotations

import json
import unittest

from converter.report import (
    Finding,
    LearningPattern,
    Provenance,
    ReportBuilder,
    Source,
    render_json,
    render_markdown,
    render_summary,
)


def _builder() -> ReportBuilder:
    return ReportBuilder(
        source=Source(archetype="web", target_mode="wrap", root="/r", rev=1),
        tool_version="ios-agent 0.1.0",
        clock=lambda: "2026-05-05T12:00:00Z",
    )


def _blocker(i: int) -> Finding:
    return Finding(
        id=f"compliance.x#{i}",
        category="compliance.privacy-manifest",
        severity="blocker",
        producer="compliance.api_scanner",
        file=f"src/file_{i}.ts",
        line=i + 1,
        original_snippet=f"snippet {i}",
        reason=f"Reason {i}",
        recommended_fix=f"Fix {i}",
        doc_link="https://example.com/doc",
    )


def _manual(i: int) -> Finding:
    return Finding(
        id=f"translation.x#{i}",
        category=f"translation.cat{i % 3}",
        severity="warning",
        producer="translator.swift",
        file=f"src/manual_{i}.swift",
        line=i + 1,
        original_snippet=f"orig {i}",
        attempted_translation=f"attempt {i}",
        reason=f"Manual reason {i}",
        recommended_fix=f"Manual fix {i}",
        doc_link="https://example.com/doc",
        confidence_score=(i % 10) / 10,
        provenance=Provenance(model="claude-opus-4-7"),
    )


def _learning(i: int) -> LearningPattern:
    return LearningPattern(
        pattern=f"pattern-{i}",
        occurrences=i + 1,
        applied_translation=f"applied {i}",
        untranslatable_count=0,
        refactor_recommendation=f"refactor {i}",
    )


class TestRenderJson(unittest.TestCase):
    def test_empty_report_round_trips(self) -> None:
        b = _builder()
        report = b.build()
        out = render_json(report)
        loaded = json.loads(out)
        self.assertEqual(loaded["layer_a_blockers"], [])

    def test_byte_stable_for_same_input(self) -> None:
        b1 = _builder()
        b1.add_blocker(_blocker(0))
        b1.add_manual_review(_manual(0))
        b1.add_learning(_learning(0))
        b2 = _builder()
        b2.add_blocker(_blocker(0))
        b2.add_manual_review(_manual(0))
        b2.add_learning(_learning(0))
        self.assertEqual(render_json(b1.build()), render_json(b2.build()))

    def test_keys_are_sorted(self) -> None:
        b = _builder()
        b.add_blocker(_blocker(0))
        out = render_json(b.build())
        first_keys = list(json.loads(out).keys())
        self.assertEqual(first_keys, sorted(first_keys))


class TestRenderMarkdown(unittest.TestCase):
    def test_empty_report_renders_no_findings_placeholders(self) -> None:
        out = render_markdown(_builder().build())
        self.assertIn("# Conversion Report", out)
        self.assertIn("Layer A — Blockers", out)
        self.assertIn("_No blockers._", out)
        self.assertIn("_No manual-review items._", out)
        self.assertIn("_No cross-cutting learnings._", out)

    def test_byte_stable_for_same_input(self) -> None:
        b1 = _builder()
        b2 = _builder()
        for i in range(3):
            b1.add_blocker(_blocker(i))
            b2.add_blocker(_blocker(i))
            b1.add_manual_review(_manual(i))
            b2.add_manual_review(_manual(i))
            b1.add_learning(_learning(i))
            b2.add_learning(_learning(i))
        self.assertEqual(render_markdown(b1.build()), render_markdown(b2.build()))

    def test_findings_appear_in_severity_order(self) -> None:
        # Layer A is all blockers, Layer B all warnings — but ensure both
        # render their categories in stable sorted order.
        b = _builder()
        # Add manual-review entries in shuffled category order
        for cat_idx in (2, 0, 1, 0, 2):
            i = cat_idx * 10 + len([x for x in b._manual if x.category.endswith(str(cat_idx))])
            b.add_manual_review(_manual(i))
        out = render_markdown(b.build())
        # categories should be listed alphabetically in the sorted table
        cat0 = out.find("translation.cat0")
        cat1 = out.find("translation.cat1")
        cat2 = out.find("translation.cat2")
        self.assertGreater(cat1, cat0)
        self.assertGreater(cat2, cat1)

    def test_metadata_header_present(self) -> None:
        out = render_markdown(_builder().build())
        self.assertIn("`web`", out)
        self.assertIn("`wrap`", out)
        self.assertIn("`ios-agent 0.1.0`", out)
        self.assertIn("`2026-05-05T12:00:00Z`", out)

    def test_finding_detail_includes_snippet_and_attempt(self) -> None:
        b = _builder()
        b.add_manual_review(_manual(0))
        out = render_markdown(b.build())
        self.assertIn("**Original:**", out)
        self.assertIn("**Attempted translation:**", out)
        self.assertIn("attempt 0", out)


class TestRenderSummary(unittest.TestCase):
    def test_default_budget_under_65000(self) -> None:
        b = _builder()
        for i in range(50):
            b.add_blocker(_blocker(i))
        for i in range(200):
            b.add_manual_review(_manual(i))
        out = render_summary(b.build())
        self.assertLessEqual(len(out), 65000)

    def test_layer_a_capped_at_20(self) -> None:
        b = _builder()
        for i in range(50):
            b.add_blocker(_blocker(i))
        out = render_summary(b.build())
        self.assertIn("…and 30 more", out)

    def test_layer_c_capped_at_5(self) -> None:
        b = _builder()
        for i in range(10):
            b.add_learning(_learning(i))
        out = render_summary(b.build())
        self.assertIn("…and 5 more", out)

    def test_tight_budget_trims_to_fit(self) -> None:
        b = _builder()
        for i in range(50):
            b.add_blocker(_blocker(i))
        for i in range(200):
            b.add_manual_review(_manual(i))
        out = render_summary(b.build(), max_chars=2000)
        self.assertLessEqual(len(out), 2000)
        self.assertTrue(
            "trimmed" in out or "elided" in out or "showing" in out,
            f"expected trimming markers, got:\n{out[:200]}",
        )

    def test_tiny_budget_still_valid(self) -> None:
        b = _builder()
        for i in range(50):
            b.add_blocker(_blocker(i))
        out = render_summary(b.build(), max_chars=500)
        self.assertLessEqual(len(out), 500)
        self.assertTrue(out.startswith("# "))

    def test_zero_budget_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render_summary(_builder().build(), max_chars=0)

    def test_empty_summary_emits_nones(self) -> None:
        out = render_summary(_builder().build())
        self.assertIn("Layer A — Blockers", out)
        self.assertIn("_None._", out)
        self.assertIn("Counts: A=0 B=0 C=0", out)


if __name__ == "__main__":
    unittest.main()
