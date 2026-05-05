"""
Three-layer report emitter.

Public surface: Finding / LearningPattern / Source / Provenance dataclasses,
the Report record, and ReportBuilder which accumulates findings and produces
a schema-validated Report on build().

Plan: plans/tier-1-step-7-three-layer-report.md (Step 7.2)
Schema: schemas/report.schema.json
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from converter.compliance.privacy_manifest import _validate_against_schema


SCHEMA_VERSION = "1.0.0"

_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "report.schema.json"
)


_VALID_SEVERITIES = ("blocker", "warning", "info")
_VALID_ARCHETYPES = ("web", "java", "kotlin", "typescript", "python", "objc")
_VALID_TARGET_MODES = ("wrap", "bridge", "port")


class ReportError(Exception):
    """Raised when a Finding is invalid or a Report fails schema validation."""


@dataclass(frozen=True)
class Provenance:
    model: str | None = None
    prompt_template: str | None = None
    seed: str | int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_template": self.prompt_template,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class Source:
    archetype: str
    target_mode: str
    root: str
    rev: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "target_mode": self.target_mode,
            "root": self.root,
            "rev": self.rev,
        }


@dataclass(frozen=True)
class Finding:
    id: str
    category: str
    severity: str
    producer: str
    file: str
    line: int
    original_snippet: str
    reason: str
    recommended_fix: str
    doc_link: str
    attempted_translation: str | None = None
    confidence_score: float | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ReportError("Finding.id must be non-empty")
        if not self.category:
            raise ReportError("Finding.category must be non-empty")
        if self.severity not in _VALID_SEVERITIES:
            raise ReportError(
                f"Finding.severity must be one of {_VALID_SEVERITIES}, "
                f"got {self.severity!r}"
            )
        if not self.producer:
            raise ReportError("Finding.producer must be non-empty")
        if not self.file:
            raise ReportError("Finding.file must be non-empty")
        if not self.reason:
            raise ReportError("Finding.reason must be non-empty")
        if not self.recommended_fix:
            raise ReportError("Finding.recommended_fix must be non-empty")
        if not self.doc_link:
            raise ReportError("Finding.doc_link must be non-empty")
        if self.confidence_score is not None:
            if not (0.0 <= self.confidence_score <= 1.0):
                raise ReportError(
                    f"Finding.confidence_score must be in [0.0, 1.0], "
                    f"got {self.confidence_score!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "producer": self.producer,
            "file": self.file,
            "line": self.line,
            "original_snippet": self.original_snippet,
            "attempted_translation": self.attempted_translation,
            "reason": self.reason,
            "recommended_fix": self.recommended_fix,
            "doc_link": self.doc_link,
            "confidence_score": self.confidence_score,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass(frozen=True)
class LearningPattern:
    pattern: str
    occurrences: int
    applied_translation: str
    untranslatable_count: int
    refactor_recommendation: str
    prior_rev_confidence: float | None = None
    delta: float | None = None

    def __post_init__(self) -> None:
        if not self.pattern:
            raise ReportError("LearningPattern.pattern must be non-empty")
        if self.occurrences < 0:
            raise ReportError(
                f"LearningPattern.occurrences must be >= 0, got {self.occurrences}"
            )
        if self.untranslatable_count < 0:
            raise ReportError(
                "LearningPattern.untranslatable_count must be >= 0, "
                f"got {self.untranslatable_count}"
            )
        if self.untranslatable_count > self.occurrences:
            raise ReportError(
                "LearningPattern.untranslatable_count cannot exceed occurrences "
                f"({self.untranslatable_count} > {self.occurrences})"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "occurrences": self.occurrences,
            "applied_translation": self.applied_translation,
            "untranslatable_count": self.untranslatable_count,
            "refactor_recommendation": self.refactor_recommendation,
            "prior_rev_confidence": self.prior_rev_confidence,
            "delta": self.delta,
        }


@dataclass(frozen=True)
class Report:
    schema_version: str
    generated_at: str
    tool_version: str
    source: Source
    layer_a_blockers: tuple[Finding, ...]
    layer_b_manual_review: tuple[Finding, ...]
    layer_c_learnings: tuple[LearningPattern, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "tool_version": self.tool_version,
            "source": self.source.to_dict(),
            "layer_a_blockers": [f.to_dict() for f in self.layer_a_blockers],
            "layer_b_manual_review": [f.to_dict() for f in self.layer_b_manual_review],
            "layer_c_learnings": [lp.to_dict() for lp in self.layer_c_learnings],
        }


class ReportBuilder:
    """Accumulates findings and learnings; produces a validated Report on build().

    De-duplicates findings by id within each layer (the second add of an
    already-seen id is a no-op, not an error). LearningPattern entries are
    de-duplicated by `pattern`.

    The builder validates the assembled dict shape against
    schemas/report.schema.json before returning. Validation failure raises
    ReportError; partial reports are never returned.
    """

    def __init__(
        self,
        *,
        source: Source,
        tool_version: str,
        schema_path: Path | None = None,
        clock: Any = None,
    ) -> None:
        if source.archetype not in _VALID_ARCHETYPES:
            raise ReportError(
                f"Source.archetype must be one of {_VALID_ARCHETYPES}, "
                f"got {source.archetype!r}"
            )
        if source.target_mode not in _VALID_TARGET_MODES:
            raise ReportError(
                f"Source.target_mode must be one of {_VALID_TARGET_MODES}, "
                f"got {source.target_mode!r}"
            )
        if not source.root:
            raise ReportError("Source.root must be non-empty")
        if source.rev < 1:
            raise ReportError(f"Source.rev must be >= 1, got {source.rev}")
        if not tool_version:
            raise ReportError("tool_version must be non-empty")

        self._source = source
        self._tool_version = tool_version
        self._schema_path = schema_path or _DEFAULT_SCHEMA_PATH
        self._clock = clock or _utc_now_iso

        self._blockers: list[Finding] = []
        self._manual: list[Finding] = []
        self._learnings: list[LearningPattern] = []
        self._seen_ids: set[str] = set()
        self._seen_patterns: set[str] = set()

    def add_blocker(self, finding: Finding) -> None:
        if finding.id in self._seen_ids:
            return
        self._seen_ids.add(finding.id)
        self._blockers.append(finding)

    def add_manual_review(self, finding: Finding) -> None:
        if finding.id in self._seen_ids:
            return
        self._seen_ids.add(finding.id)
        self._manual.append(finding)

    def add_learning(self, learning: LearningPattern) -> None:
        if learning.pattern in self._seen_patterns:
            return
        self._seen_patterns.add(learning.pattern)
        self._learnings.append(learning)

    def build(self) -> Report:
        report = Report(
            schema_version=SCHEMA_VERSION,
            generated_at=self._clock(),
            tool_version=self._tool_version,
            source=self._source,
            layer_a_blockers=tuple(self._blockers),
            layer_b_manual_review=tuple(self._manual),
            layer_c_learnings=tuple(self._learnings),
        )
        errors = _validate_against_schema(report.to_dict(), self._schema_path)
        if errors:
            raise ReportError(
                "report failed schema validation:\n  - " + "\n  - ".join(errors)
            )
        return report


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp, second precision, trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
