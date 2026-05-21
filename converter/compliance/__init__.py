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
    ENCRYPTION_EXPORT_CATEGORY,
    ENCRYPTION_EXPORT_DOC_URL,
    PRIVACY_MANIFEST_DOC_URL,
    PRODUCER,
    ScannerError,
    load_rules,
    scan_source,
    scan_capacitor_plugins,
    scan_all,
    to_findings,
)
from .entitlement_scanner import (
    ENTITLEMENT_DOC_URL,
    EntitlementFinding,
)
from .entitlement_scanner import PRODUCER as ENTITLEMENT_PRODUCER
from .entitlement_scanner import scan_all as scan_all_entitlements
from .entitlement_scanner import to_findings as entitlement_to_findings
from .privacy_manifest import (
    ManifestError,
    generate_manifest,
    validate_manifest,
)
from .att_scanner import (
    ATTFinding,
    ATT_DOC_URL,
    ATT_USAGE_STRING_KEY,
    load_att_rules,
    scan_att_source,
    scan_att_plugins,
    scan_all_att,
    to_att_findings,
)
from .att_scanner import PRODUCER as ATT_PRODUCER
from .usage_string_auditor import (
    AuditorError,
    UsageStringFinding,
    audit_info_plist,
    to_usage_findings,
)
from .usage_string_auditor import PRODUCER as USAGE_AUDITOR_PRODUCER
from .ats_scanner import (
    ATSFinding,
    scan_all_ats,
    scan_ats_source,
    scan_ats_configs,
    to_ats_findings,
)
from .ats_scanner import PRODUCER as ATS_PRODUCER
from .min_functionality_checker import (
    MinFuncFinding,
    check_min_functionality,
    to_min_func_findings,
)
from .min_functionality_checker import PRODUCER as MIN_FUNC_PRODUCER

__all__ = [
    "APIFinding",
    "ENCRYPTION_EXPORT_CATEGORY",
    "ENCRYPTION_EXPORT_DOC_URL",
    "PRIVACY_MANIFEST_DOC_URL",
    "PRODUCER",
    "ScannerError",
    "load_rules",
    "scan_source",
    "scan_capacitor_plugins",
    "scan_all",
    "to_findings",
    "ENTITLEMENT_DOC_URL",
    "ENTITLEMENT_PRODUCER",
    "EntitlementFinding",
    "scan_all_entitlements",
    "entitlement_to_findings",
    "ManifestError",
    "generate_manifest",
    "validate_manifest",
    "ATTFinding",
    "ATT_DOC_URL",
    "ATT_USAGE_STRING_KEY",
    "ATT_PRODUCER",
    "load_att_rules",
    "scan_att_source",
    "scan_att_plugins",
    "scan_all_att",
    "to_att_findings",
    "AuditorError",
    "UsageStringFinding",
    "USAGE_AUDITOR_PRODUCER",
    "audit_info_plist",
    "to_usage_findings",
    "ATSFinding",
    "ATS_PRODUCER",
    "scan_all_ats",
    "scan_ats_source",
    "scan_ats_configs",
    "to_ats_findings",
    "MinFuncFinding",
    "MIN_FUNC_PRODUCER",
    "check_min_functionality",
    "to_min_func_findings",
]
