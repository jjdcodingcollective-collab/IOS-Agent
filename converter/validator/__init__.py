"""
Validator — Post-Phase 4 output validation.
Checks generated Swift code for syntax errors, cross-file reference issues,
and produces a validation report with per-file confidence scores.
"""

from .swift_checker import (
    validate_swift_file,
    validate_project,
    ValidationResult,
    ProjectValidationResult,
)

__all__ = [
    "validate_swift_file",
    "validate_project",
    "ValidationResult",
    "ProjectValidationResult",
]
