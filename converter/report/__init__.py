"""
Three-layer conversion report — emitter + renderers.

Plan: plans/tier-1-step-7-three-layer-report.md
Schema: schemas/report.schema.json
"""

from converter.report.emitter import (
    Finding,
    LearningPattern,
    Provenance,
    Report,
    ReportBuilder,
    ReportError,
    Source,
    SCHEMA_VERSION,
)
from converter.report.render import (
    render_json,
    render_markdown,
    render_summary,
)

__all__ = [
    "Finding",
    "LearningPattern",
    "Provenance",
    "Report",
    "ReportBuilder",
    "ReportError",
    "Source",
    "SCHEMA_VERSION",
    "render_json",
    "render_markdown",
    "render_summary",
]
