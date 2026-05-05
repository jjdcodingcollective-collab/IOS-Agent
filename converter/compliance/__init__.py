"""
Compliance modules for the iOS converter.

Houses Apple App Store compliance scaffolding: required-reason API scanner,
PrivacyInfo.xcprivacy generator, override merging, and (later) ATT, SIWA,
ATS, and usage-string detection. All modules in this package share the
api_scanner core; co-location is deliberate.

Plan: plans/tier-1-step-6-privacy-scanner.md
"""

from .api_scanner import (
    APIFinding,
    ScannerError,
    load_rules,
    scan_source,
    scan_capacitor_plugins,
    scan_all,
)
from .privacy_manifest import (
    ManifestError,
    generate_manifest,
    validate_manifest,
)

__all__ = [
    "APIFinding",
    "ScannerError",
    "load_rules",
    "scan_source",
    "scan_capacitor_plugins",
    "scan_all",
    "ManifestError",
    "generate_manifest",
    "validate_manifest",
]
