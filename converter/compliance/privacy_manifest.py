"""
Privacy manifest generator — Tier 1 Step 6.3.

Takes APIFinding records from the api_scanner and an optional
privacy-overrides.yaml file, emits a valid PrivacyInfo.xcprivacy
property list, and validates the result against the bundled JSON Schema
(config/apple-privacy-manifest.schema.json).

Plan: plans/tier-1-step-6-privacy-scanner.md (Step 6.3).
ADR 0001: stdlib only — no PyYAML, no jsonschema. The schema validator
in this module handles exactly the JSON Schema subset we author in
config/apple-privacy-manifest.schema.json. If a future schema change
introduces unsupported keywords, the validator must be extended in the
same PR.
"""

from __future__ import annotations

import json
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from wrapper.compatibility import _load_yaml  # type: ignore[attr-defined]

from .api_scanner import APIFinding


_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "apple-privacy-manifest.schema.json"
)


class ManifestError(Exception):
    """Raised when manifest generation or validation fails."""


@dataclass(frozen=True)
class _OverrideData:
    """Parsed privacy-overrides.yaml contents."""

    additional_categories: list[dict[str, Any]]
    tracking_enabled: bool
    tracking_domains: list[str]
    third_party_sdks: list[dict[str, Any]]
    excluded_findings: list[str]
    collected_data_types: list[dict[str, Any]]


def generate_manifest(
    findings: Sequence[APIFinding],
    *,
    output_path: Path,
    overrides_path: Path | None = None,
    schema_path: Path | None = None,
) -> Path:
    """Generate PrivacyInfo.xcprivacy from scanner findings + overrides.

    Returns the output_path on success. Raises ManifestError on validation
    failure — a partially-written manifest is never left on disk.
    """
    overrides = _load_overrides(overrides_path) if overrides_path else _empty_overrides()
    manifest_dict = _build_manifest_dict(findings, overrides)

    errors = _validate_against_schema(manifest_dict, schema_path or _DEFAULT_SCHEMA_PATH)
    if errors:
        raise ManifestError(
            "manifest failed schema validation:\n  - " + "\n  - ".join(errors)
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fh:
        plistlib.dump(manifest_dict, fh, sort_keys=False)
    return output_path


def validate_manifest(
    path: Path,
    *,
    schema_path: Path | None = None,
) -> list[str]:
    """Validate an existing PrivacyInfo.xcprivacy at `path`.

    Returns a list of human-readable error strings. An empty list means
    valid.
    """
    path = Path(path)
    if not path.exists():
        return [f"manifest file not found: {path}"]
    try:
        with path.open("rb") as fh:
            data = plistlib.load(fh)
    except (plistlib.InvalidFileException, OSError, ValueError) as exc:
        return [f"failed to parse plist: {exc}"]
    return _validate_against_schema(data, schema_path or _DEFAULT_SCHEMA_PATH)


# --- manifest construction ---------------------------------------------------


def _build_manifest_dict(
    findings: Sequence[APIFinding],
    overrides: _OverrideData,
) -> dict[str, Any]:
    """Compose the manifest dict from findings + overrides."""

    excluded = set(overrides.excluded_findings)

    # Group findings by category, dedup reason codes within each.
    by_category: dict[str, set[str]] = {}
    for f in findings:
        finding_id = f"{f.category}:{f.pattern}:{f.file}:{f.line}"
        if finding_id in excluded:
            continue
        by_category.setdefault(f.category, set()).add(f.reason_code)

    # Layer overrides on top.
    for entry in overrides.additional_categories:
        cat = entry.get("category")
        codes = entry.get("reason_codes") or []
        if not isinstance(cat, str) or not isinstance(codes, list):
            continue
        target = by_category.setdefault(cat, set())
        for code in codes:
            if isinstance(code, str):
                target.add(code)

    accessed: list[dict[str, Any]] = []
    for cat in sorted(by_category):
        codes = sorted(by_category[cat])
        accessed.append(
            {
                "NSPrivacyAccessedAPIType": cat,
                "NSPrivacyAccessedAPITypeReasons": codes,
            }
        )

    return {
        "NSPrivacyTracking": overrides.tracking_enabled,
        "NSPrivacyTrackingDomains": list(overrides.tracking_domains),
        "NSPrivacyCollectedDataTypes": list(overrides.collected_data_types),
        "NSPrivacyAccessedAPITypes": accessed,
    }


# --- override loading --------------------------------------------------------


def _empty_overrides() -> _OverrideData:
    return _OverrideData(
        additional_categories=[],
        tracking_enabled=False,
        tracking_domains=[],
        third_party_sdks=[],
        excluded_findings=[],
        collected_data_types=[],
    )


def _load_overrides(path: Path) -> _OverrideData:
    path = Path(path)
    if not path.exists():
        return _empty_overrides()
    try:
        text = path.read_text(encoding="utf-8")
        raw = _load_yaml(text)
    except Exception as exc:
        raise ManifestError(f"failed to parse overrides {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: top-level must be a mapping")

    tracking = raw.get("tracking") or {}
    if not isinstance(tracking, dict):
        tracking = {}

    return _OverrideData(
        additional_categories=_as_dict_list(raw.get("additional_categories")),
        tracking_enabled=bool(tracking.get("enabled", False)),
        tracking_domains=_as_str_list(tracking.get("tracking_domains")),
        third_party_sdks=_as_dict_list(raw.get("third_party_sdks")),
        excluded_findings=_as_str_list(raw.get("excluded_findings")),
        collected_data_types=_as_dict_list(raw.get("collected_data_types")),
    )


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


# --- schema validation -------------------------------------------------------
#
# Bounded JSON Schema subset: type, required, enum, properties,
# additionalProperties (false-only), items, minItems, uniqueItems,
# pattern, allOf, if/then, $defs / $ref (intra-document only).
#
# The schema we author lives in config/apple-privacy-manifest.schema.json;
# anything outside this subset must be added here in the same change.


_TYPE_CHECKS: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
}


def _validate_against_schema(data: Any, schema_path: Path) -> list[str]:
    schema_path = Path(schema_path)
    if not schema_path.exists():
        return [f"schema file not found: {schema_path}"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"failed to load schema {schema_path}: {exc}"]
    errors: list[str] = []
    _validate(data, schema, schema, "$", errors)
    return errors


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ManifestError(f"only intra-document $ref supported, got: {ref}")
    node: Any = root_schema
    for segment in ref[2:].split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            node = node.get(segment)
        else:
            raise ManifestError(f"$ref path not found: {ref}")
        if node is None:
            raise ManifestError(f"$ref path not found: {ref}")
    if not isinstance(node, dict):
        raise ManifestError(f"$ref must resolve to a schema object: {ref}")
    return node


def _validate(
    data: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    if "$ref" in schema:
        try:
            schema = _resolve_ref(schema["$ref"], root_schema)
        except ManifestError as exc:
            errors.append(f"{path}: {exc}")
            return

    expected_type = schema.get("type")
    if expected_type:
        py_type = _TYPE_CHECKS.get(expected_type)
        if py_type is None:
            errors.append(f"{path}: unsupported schema type {expected_type!r}")
            return
        # JSON Schema booleans are not numbers; guard the (int,float) overlap.
        if expected_type in ("number", "integer") and isinstance(data, bool):
            errors.append(f"{path}: expected {expected_type}, got boolean")
            return
        if not isinstance(data, py_type):
            errors.append(
                f"{path}: expected {expected_type}, got {type(data).__name__}"
            )
            return

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: value {data!r} not in enum {schema['enum']!r}")

    if "pattern" in schema and isinstance(data, str):
        if not re.search(schema["pattern"], data):
            errors.append(f"{path}: {data!r} does not match pattern {schema['pattern']!r}")

    if isinstance(data, dict):
        _validate_object(data, schema, root_schema, path, errors)
    elif isinstance(data, list):
        _validate_array(data, schema, root_schema, path, errors)

    for sub in schema.get("allOf", []):
        if not isinstance(sub, dict):
            continue
        _validate(data, sub, root_schema, path, errors)

    if "if" in schema and isinstance(schema["if"], dict):
        if not _matches(data, schema["if"], root_schema):
            pass  # if-clause failed → skip then-branch
        else:
            then_branch = schema.get("then")
            if isinstance(then_branch, dict):
                _validate(data, then_branch, root_schema, path, errors)


def _validate_object(
    data: dict[str, Any],
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    properties = schema.get("properties") or {}
    additional = schema.get("additionalProperties", True)

    for key in schema.get("required", []) or []:
        if key not in data:
            errors.append(f"{path}: missing required property {key!r}")

    for key, value in data.items():
        sub_schema = properties.get(key)
        sub_path = f"{path}.{key}"
        if sub_schema is None:
            if additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            continue
        if isinstance(sub_schema, dict):
            _validate(value, sub_schema, root_schema, sub_path, errors)


def _validate_array(
    data: list[Any],
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(data) < min_items:
        errors.append(f"{path}: array has {len(data)} items, minimum is {min_items}")

    if schema.get("uniqueItems") is True:
        seen: list[Any] = []
        for item in data:
            if item in seen:
                errors.append(f"{path}: duplicate item {item!r}")
                break
            seen.append(item)

    items_schema = schema.get("items")
    if isinstance(items_schema, dict):
        for i, item in enumerate(data):
            _validate(item, items_schema, root_schema, f"{path}[{i}]", errors)


def _matches(data: Any, schema: dict[str, Any], root_schema: dict[str, Any]) -> bool:
    """Lightweight 'does data match this schema?' for if/then dispatch.

    Only checks the keywords actually used in our schema's if-clauses
    (type and properties.<key>.const).
    """
    if "$ref" in schema:
        try:
            schema = _resolve_ref(schema["$ref"], root_schema)
        except ManifestError:
            return False
    expected_type = schema.get("type")
    if expected_type:
        py_type = _TYPE_CHECKS.get(expected_type)
        if py_type is None or not isinstance(data, py_type):
            return False
    for key, sub_schema in (schema.get("properties") or {}).items():
        if not isinstance(sub_schema, dict):
            continue
        if "const" in sub_schema:
            if not (isinstance(data, dict) and data.get(key) == sub_schema["const"]):
                return False
    for required in schema.get("required", []) or []:
        if not (isinstance(data, dict) and required in data):
            return False
    return True
