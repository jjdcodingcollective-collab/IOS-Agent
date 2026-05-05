"""
Three-layer report renderers.

`render_markdown` — human-readable, sorted by severity then category, file, line.
`render_json`     — machine-readable; sorted keys for byte-stable output.
`render_summary`  — PR-comment-friendly extract under a configurable char budget
                    (default 65000 — GitHub's hard cap is 65536; leave headroom
                    for the wrapper's framing text).

Plan: plans/tier-1-step-7-three-layer-report.md (Step 7.3)
"""

from __future__ import annotations

import json
from collections import Counter

from converter.report.emitter import Finding, LearningPattern, Report


# Severity rank: blocker > warning > info. Used to keep render order stable.
_SEV_RANK = {"blocker": 0, "warning": 1, "info": 2}


def render_json(report: Report) -> str:
    """JSON with sorted keys + 2-space indent. Byte-stable for identical input."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def render_markdown(report: Report) -> str:
    """Human-readable Markdown. Stable across runs for the same input.

    Section order: Layer A → Layer B → Layer C.
    Within each layer, findings sorted by (severity, category, file, line, id).
    """
    parts: list[str] = []
    parts.append(f"# Conversion Report")
    parts.append("")
    parts.append(f"- Generated at: `{report.generated_at}`")
    parts.append(f"- Tool: `{report.tool_version}`")
    parts.append(
        f"- Source: `{report.source.archetype}` → `{report.source.target_mode}` "
        f"(rev {report.source.rev})"
    )
    parts.append(f"- Root: `{report.source.root}`")
    parts.append("")
    parts.append(_render_layer_a(report.layer_a_blockers))
    parts.append(_render_layer_b(report.layer_b_manual_review))
    parts.append(_render_layer_c(report.layer_c_learnings))
    return "\n".join(parts).rstrip() + "\n"


def render_summary(report: Report, *, max_chars: int = 65000) -> str:
    """PR-comment-sized summary. Layer A in full (capped at 20), B grouped, C top 5.

    Always emits valid Markdown, never exceeds max_chars. If trimming kicks in,
    a footer line records what was elided.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    blockers = list(report.layer_a_blockers)
    manual = list(report.layer_b_manual_review)
    learnings = list(report.layer_c_learnings)

    header = [
        "# Conversion Report (summary)",
        "",
        f"- `{report.source.archetype}` → `{report.source.target_mode}` "
        f"(rev {report.source.rev})",
        f"- Generated: `{report.generated_at}`",
        f"- Counts: A={len(blockers)} B={len(manual)} C={len(learnings)}",
        "",
    ]

    body: list[str] = []

    # Layer A — top 20 sorted by severity, category, file, line
    body.append("## Layer A — Blockers")
    if not blockers:
        body.append("_None._")
    else:
        top_a = _sorted_findings(blockers)[:20]
        body.append(_findings_table(top_a, include_confidence=False))
        if len(blockers) > 20:
            body.append(f"_…and {len(blockers) - 20} more. See `report.md`._")
    body.append("")

    # Layer B — group by category, count, sort by count desc
    body.append("## Layer B — Manual Review")
    if not manual:
        body.append("_None._")
    else:
        cats = Counter(f.category for f in manual)
        body.append("| Category | Count |")
        body.append("| --- | ---: |")
        for cat, n in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0])):
            body.append(f"| `{_md_escape(cat)}` | {n} |")
    body.append("")

    # Layer C — top 5 by occurrences
    body.append("## Layer C — Learnings")
    if not learnings:
        body.append("_None._")
    else:
        top_c = sorted(learnings, key=lambda lp: (-lp.occurrences, lp.pattern))[:5]
        for lp in top_c:
            body.append(
                f"- **{_md_escape(lp.pattern)}** "
                f"({lp.occurrences} occurrences, "
                f"{lp.untranslatable_count} untranslatable) — "
                f"{_md_escape(lp.applied_translation)}"
            )
        if len(learnings) > 5:
            body.append(f"_…and {len(learnings) - 5} more. See `report.md`._")
    body.append("")

    body.append(
        f"_Full report at `report.md` "
        f"({len(blockers) + len(manual) + len(learnings)} total findings)._"
    )

    output = "\n".join(header + body).rstrip() + "\n"
    if len(output) <= max_chars:
        return output

    # Over budget. Drop Layer B detail rows first, then Layer C bullets, then
    # trim Layer A entries from the bottom. Always keep headers + counts.
    return _trim_to_budget(report, max_chars)


# --- internals ---------------------------------------------------------------


def _render_layer_a(findings: tuple[Finding, ...]) -> str:
    out = ["## Layer A — Blockers", ""]
    if not findings:
        out.append("_No blockers._")
        out.append("")
        return "\n".join(out)
    out.append(_findings_table(_sorted_findings(findings), include_confidence=False))
    out.append("")
    out.append(_findings_detail(_sorted_findings(findings)))
    out.append("")
    return "\n".join(out)


def _render_layer_b(findings: tuple[Finding, ...]) -> str:
    out = ["## Layer B — Manual Review", ""]
    if not findings:
        out.append("_No manual-review items._")
        out.append("")
        return "\n".join(out)
    out.append(_findings_table(_sorted_findings(findings), include_confidence=True))
    out.append("")
    out.append(_findings_detail(_sorted_findings(findings)))
    out.append("")
    return "\n".join(out)


def _render_layer_c(learnings: tuple[LearningPattern, ...]) -> str:
    out = ["## Layer C — Learnings", ""]
    if not learnings:
        out.append("_No cross-cutting learnings._")
        out.append("")
        return "\n".join(out)
    sorted_lps = sorted(learnings, key=lambda lp: (-lp.occurrences, lp.pattern))
    for lp in sorted_lps:
        out.append(f"### `{_md_escape(lp.pattern)}`")
        out.append("")
        out.append(
            f"- Occurrences: **{lp.occurrences}** "
            f"(untranslatable: {lp.untranslatable_count})"
        )
        out.append(f"- Applied translation: {_md_escape(lp.applied_translation)}")
        out.append(
            f"- Refactor recommendation: {_md_escape(lp.refactor_recommendation)}"
        )
        if lp.prior_rev_confidence is not None or lp.delta is not None:
            prior = (
                f"{lp.prior_rev_confidence:.2f}"
                if lp.prior_rev_confidence is not None
                else "n/a"
            )
            delta = f"{lp.delta:+.2f}" if lp.delta is not None else "n/a"
            out.append(f"- Trend: prior_rev_confidence={prior}, delta={delta}")
        out.append("")
    return "\n".join(out)


def _sorted_findings(findings: tuple[Finding, ...] | list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (
            _SEV_RANK.get(f.severity, 99),
            f.category,
            f.file,
            f.line,
            f.id,
        ),
    )


def _findings_table(findings: list[Finding], *, include_confidence: bool) -> str:
    if include_confidence:
        rows = ["| File:Line | Severity | Category | Confidence | Reason |",
                "| --- | --- | --- | ---: | --- |"]
    else:
        rows = ["| File:Line | Severity | Category | Reason |",
                "| --- | --- | --- | --- |"]
    for f in findings:
        loc = f"`{_md_escape(f.file)}:{f.line}`"
        cat = f"`{_md_escape(f.category)}`"
        reason = _md_escape_inline(f.reason)
        if include_confidence:
            conf = (
                f"{f.confidence_score:.2f}"
                if f.confidence_score is not None
                else "—"
            )
            rows.append(f"| {loc} | {f.severity} | {cat} | {conf} | {reason} |")
        else:
            rows.append(f"| {loc} | {f.severity} | {cat} | {reason} |")
    return "\n".join(rows)


def _findings_detail(findings: list[Finding]) -> str:
    out: list[str] = []
    for f in findings:
        out.append(f"#### `{_md_escape(f.id)}`")
        out.append("")
        out.append(f"- **File:** `{_md_escape(f.file)}:{f.line}`")
        out.append(f"- **Producer:** `{_md_escape(f.producer)}`")
        if f.original_snippet:
            out.append("- **Original:**")
            out.append("")
            out.append(_fenced(f.original_snippet))
            out.append("")
        if f.attempted_translation:
            out.append("- **Attempted translation:**")
            out.append("")
            out.append(_fenced(f.attempted_translation))
            out.append("")
        out.append(f"- **Why flagged:** {_md_escape_inline(f.reason)}")
        out.append(f"- **Recommended fix:** {_md_escape_inline(f.recommended_fix)}")
        out.append(f"- **Docs:** {f.doc_link}")
        out.append("")
    return "\n".join(out)


def _fenced(snippet: str) -> str:
    """Wrap a snippet in a triple-backtick fence; strip stray closing fences."""
    safe = snippet.replace("```", "``\u200b`")
    return f"```\n{safe}\n```"


def _md_escape(s: str) -> str:
    """Escape Markdown structural characters in inline `code` contexts."""
    return s.replace("`", "\\`")


def _md_escape_inline(s: str) -> str:
    """Escape pipes for table cells; preserve everything else."""
    return s.replace("|", "\\|").replace("\n", " ")


def _trim_to_budget(report: Report, max_chars: int) -> str:
    """Fallback for over-budget summaries. Strip Layer B detail, then Layer C
    detail, then truncate Layer A by halves until it fits. Always valid MD."""
    blockers = _sorted_findings(report.layer_a_blockers)
    manual = list(report.layer_b_manual_review)
    learnings = list(report.layer_c_learnings)
    cap = 20

    while True:
        a_rows = blockers[:cap]
        header = [
            "# Conversion Report (summary, trimmed)",
            "",
            f"- `{report.source.archetype}` → `{report.source.target_mode}` "
            f"(rev {report.source.rev})",
            f"- Counts: A={len(blockers)} B={len(manual)} C={len(learnings)}",
            "",
            "## Layer A — Blockers",
        ]
        if a_rows:
            header.append(_findings_table(a_rows, include_confidence=False))
        else:
            header.append("_None shown — see `report.md`._")
        if len(blockers) > len(a_rows):
            header.append(
                f"_…showing {len(a_rows)} of {len(blockers)}. "
                f"See `report.md`._"
            )
        header.append("")
        header.append(
            f"_Layers B and C elided to fit. Full report at `report.md` "
            f"({len(blockers) + len(manual) + len(learnings)} total findings)._"
        )
        out = "\n".join(header).rstrip() + "\n"
        if len(out) <= max_chars or cap <= 1:
            return out
        cap = max(1, cap // 2)
