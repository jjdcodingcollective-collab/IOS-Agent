"""
Educational mode: a short "what just landed on this branch" summary so
first-time users know how to review the conversion output.

Phase 4: shown after the local commit, before the push prompt. Suppressed
by ``--brief`` for power users.

Two flavours:
  - Branches without the ``Requires-more-review/`` prefix get the "passed
    validation" version.
  - Branches with the prefix get the "look here first" version, which
    points the reviewer at the report files and the per-file confidence
    scores.
"""

from __future__ import annotations

from .git_ops import CommitInfo


def format_branch_explainer(commit: CommitInfo) -> str:
    """Return the multi-line explainer text for the given commit."""
    base_lines = [
        "What's on this branch:",
        "  • Sources/        the generated Swift app",
        "  • Tests/          one stub per converted screen",
        "  • .ios-conversion/  five reports, including generation-summary.md",
        "                    with per-file confidence scores",
        "  • project.yml     XcodeGen spec (Step 8) — generates the .xcodeproj",
        "",
        "Build:",
        "  cd <output-dir>",
        "  xcodegen generate && open *.xcodeproj",
    ]
    if commit.needs_review:
        base_lines.append("")
        base_lines.append(
            f"  • Branch is prefixed with 'Requires-more-review/' because "
            f"the run had validation errors or low confidence."
        )
        base_lines.append(
            "    Start with .ios-conversion/generation-summary.md — its "
            "confidence table flags which files need a human pass."
        )
    else:
        base_lines.append("")
        base_lines.append(
            "  • Branch is unprefixed because validation passed. A "
            "'Requires-more-review/' prefix would have meant "
            "\"look here first.\""
        )
    return "\n".join(base_lines)
