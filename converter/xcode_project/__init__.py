"""XcodeGen project emitter — Tier 1 Step 8."""

from .emitter import (
    DEFAULT_DEPLOYMENT_TARGET,
    DEFAULT_SWIFT_VERSION,
    EmitResult,
    EmitterError,
    PLACEHOLDER_BUNDLE_ID_PREFIX,
    PLACEHOLDER_TEAM_ID,
    PRODUCER,
    XcodeSpec,
    emit_xcode_project,
)

__all__ = [
    "DEFAULT_DEPLOYMENT_TARGET",
    "DEFAULT_SWIFT_VERSION",
    "EmitResult",
    "EmitterError",
    "PLACEHOLDER_BUNDLE_ID_PREFIX",
    "PLACEHOLDER_TEAM_ID",
    "PRODUCER",
    "XcodeSpec",
    "emit_xcode_project",
]
