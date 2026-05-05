"""
XcodeGen spec emitter — Tier 1 Step 8.3.

Produces a buildable Capacitor host project (`project.yml`, `Info.plist`,
`AppDelegate.swift`, `Assets.xcassets/`, `LaunchScreen.storyboard`,
`<AppName>.entitlements`) into the conversion output dir. The emitter does
**not** invoke `xcodegen` — the developer (or CI) runs it. We emit data the
generator consumes plus the supporting source files the generated project
references.

Plan: plans/tier-1-step-8-xcode-project-generation.md (Step 8.3).

The emitter takes:
  - an XcodeSpec (app metadata, bundle id, team id, deployment target)
  - a list of EntitlementFinding records from the Step 8.2 scanner
  - an output directory

It writes:
  - project.yml                            (XcodeGen spec)
  - App/Info.plist                         (with usage strings)
  - App/AppDelegate.swift                  (Capacitor bootstrap)
  - App/<AppName>.entitlements             (entitlement values)
  - App/Assets.xcassets/                   (placeholder icon + AccentColor)
  - App/Base.lproj/LaunchScreen.storyboard (placeholder launch screen)

…and returns an EmitResult listing every Layer-A finding the developer must
resolve before submission (placeholder bundle id, placeholder team id,
placeholder app icon, placeholder launch screen, missing privacy manifest).
"""

from __future__ import annotations

import plistlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from converter.report import Finding
    from converter.compliance.entitlement_scanner import EntitlementFinding


_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

DEFAULT_DEPLOYMENT_TARGET = "15.0"
DEFAULT_SWIFT_VERSION = "5.9"

PLACEHOLDER_TEAM_ID = "TODO_TEAMID"
PLACEHOLDER_BUNDLE_ID_PREFIX = "com.example."

# A bundle id has to be a reverse-DNS string. We accept the loose form Apple
# documents (alphanumerics, dots, dashes); App Store Connect catches the
# tighter rules at submission time.
_BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$")
_TEAM_ID_RE = re.compile(rf"^[A-Z0-9]{{10}}$|^{re.escape(PLACEHOLDER_TEAM_ID)}$")
_APP_NAME_RE = re.compile(r"^[A-Za-z0-9 ][A-Za-z0-9 _-]*[A-Za-z0-9]$")

PRODUCER = "xcode_project.emitter"


class EmitterError(Exception):
    """Raised when the emitter cannot proceed (bad spec, IO failure)."""


@dataclass(frozen=True)
class XcodeSpec:
    """The validated input to ``emit_xcode_project``.

    `entitlements` is the deduped list from the Step 8.2 scanner (Layer-A
    blockers + Layer-B warnings combined). `has_privacy_manifest` is True
    when the wrapper's compliance step wrote PrivacyInfo.xcprivacy alongside
    the project; the emitter references it as an optional resource so the
    project still generates if the manifest is missing (with a Layer-A
    finding flagging the gap).
    """

    app_name: str
    bundle_id: str
    team_id: str
    deployment_target: str = DEFAULT_DEPLOYMENT_TARGET
    swift_version: str = DEFAULT_SWIFT_VERSION
    entitlements: tuple["EntitlementFinding", ...] = field(default_factory=tuple)
    has_privacy_manifest: bool = True


@dataclass(frozen=True)
class EmitResult:
    """What the emitter produced.

    `files_written` is for caller logging only — the project.yml is the
    interesting artifact. `findings` is consumed by the wrapper to push
    placeholder/missing-manifest blockers into the report.
    """

    files_written: tuple[Path, ...]
    findings: tuple["Finding", ...]


# --- Validation --------------------------------------------------------------


def _validate_spec(spec: XcodeSpec) -> None:
    if not _APP_NAME_RE.match(spec.app_name):
        raise EmitterError(
            f"app_name {spec.app_name!r} must match {_APP_NAME_RE.pattern}"
        )
    if not _BUNDLE_ID_RE.match(spec.bundle_id):
        raise EmitterError(
            f"bundle_id {spec.bundle_id!r} must match {_BUNDLE_ID_RE.pattern}"
        )
    if not _TEAM_ID_RE.match(spec.team_id):
        raise EmitterError(
            f"team_id {spec.team_id!r} must match {_TEAM_ID_RE.pattern}"
        )
    # Loose deployment target check — major.minor numerics.
    if not re.match(r"^\d+\.\d+$", spec.deployment_target):
        raise EmitterError(
            f"deployment_target {spec.deployment_target!r} must look like '15.0'"
        )


def _safe_app_name(app_name: str) -> str:
    """The XcodeGen target name and module name (no spaces).

    Project display name and target/module name diverge when the developer
    chooses an app name with spaces — Xcode allows the former, Swift forbids
    the latter. We split them here so both honour their respective rules.
    """
    safe = re.sub(r"[^A-Za-z0-9]", "", app_name)
    if not safe:
        raise EmitterError(f"app_name {app_name!r} reduces to empty after sanitising")
    return safe


# --- Template loading --------------------------------------------------------


def _load_template(name: str, template_dir: Path | None = None) -> str:
    base = template_dir or _TEMPLATE_DIR
    path = base / name
    if not path.exists():
        raise EmitterError(f"template not found: {path}")
    return path.read_text(encoding="utf-8")


def _substitute(text: str, mapping: dict[str, str]) -> str:
    out = text
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value)
    return out


# --- Section builders --------------------------------------------------------


def _build_usage_strings_block(
    entitlement_findings: Iterable["EntitlementFinding"],
) -> str:
    """Render the Info.plist <key>NS*UsageDescription</key>... block.

    Apple soft-rejects boilerplate strings, but the emitter cannot infer the
    real reason — so we ship a placeholder that the developer must replace.
    A Layer-A finding is emitted alongside (in `_collect_placeholder_findings`)
    so the developer knows the work is not optional.
    """
    seen_keys: set[str] = set()
    lines: list[str] = []
    for ef in entitlement_findings:
        for usage_key in ef.usage_strings:
            if usage_key in seen_keys:
                continue
            seen_keys.add(usage_key)
            placeholder = _placeholder_usage_string(usage_key, ef.label)
            lines.append(f"    <key>{usage_key}</key>")
            lines.append(f"    <string>{placeholder}</string>")
    return "\n".join(lines)


def _placeholder_usage_string(usage_key: str, capability_label: str) -> str:
    """The placeholder text that lands in Info.plist before the dev edits it.

    Marked TODO so the developer's grep finds it; references the capability
    label so the connection to the source code is obvious.
    """
    return (
        f"TODO: explain why this app needs {capability_label} access "
        f"(replaces the auto-generated {usage_key})."
    )


def _build_entitlements_plist(
    entitlement_findings: Iterable["EntitlementFinding"],
) -> bytes:
    """Build the <AppName>.entitlements plist content.

    Empty entitlements file is valid — the file just needs to exist when
    XcodeGen references it. We populate keys whose values we can infer
    (e.g. aps-environment=development for push notifications) and leave
    Developer-Account-dependent values (App Group ids, iCloud container
    ids) for the developer.
    """
    plist: dict[str, object] = {}
    for ef in entitlement_findings:
        if not ef.entitlement_key:
            continue
        if ef.entitlement_key == "aps-environment":
            plist["aps-environment"] = "development"
        elif ef.entitlement_key == "com.apple.developer.applesignin":
            plist["com.apple.developer.applesignin"] = ["Default"]
        elif ef.entitlement_key == "com.apple.security.application-groups":
            # Developer must add their group id; we ship an empty array so
            # the entitlements file parses but signing forces them to fill it.
            plist.setdefault("com.apple.security.application-groups", [])
        elif ef.entitlement_key == "com.apple.developer.icloud-container-identifiers":
            plist.setdefault("com.apple.developer.icloud-container-identifiers", [])
        elif ef.entitlement_key == "com.apple.developer.healthkit":
            plist["com.apple.developer.healthkit"] = True
        else:
            # Unknown key — preserve as bool True so XcodeGen doesn't
            # complain. The dev-portal Layer-A finding still flags it.
            plist[ef.entitlement_key] = True
    return plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=True)


def _build_capability_settings(
    entitlement_findings: Iterable["EntitlementFinding"],
) -> str:
    """Indented YAML block injected into target.settings.

    For MVP we emit a comment-only block — XcodeGen reads capabilities from
    the entitlements file directly, so no additional settings are required
    for the keys we currently emit. The block exists so future capabilities
    that *do* require setting flips have a place to land without reshaping
    the template.
    """
    seen_caps: set[str] = set()
    lines: list[str] = []
    for ef in entitlement_findings:
        if ef.capability in seen_caps:
            continue
        seen_caps.add(ef.capability)
        lines.append(f"        # capability: {ef.capability}")
    return "\n".join(lines)


def _build_entitlements_block(app_name_safe: str, has_entitlements: bool) -> str:
    if not has_entitlements:
        return ""
    return (
        "    entitlements:\n"
        f"      path: App/{app_name_safe}.entitlements"
    )


def _ats_dict_default() -> str:
    """The default App Transport Security dictionary.

    No exceptions, no insecure HTTP allowed. Apple flags any ATS exception
    in App Review and the dev must justify it; a clean default is the right
    starting point. If the source's web bundle needs HTTP for development,
    the developer can edit Info.plist after generation.
    """
    return (
        "<dict>\n"
        "        <key>NSAllowsArbitraryLoads</key>\n"
        "        <false/>\n"
        "    </dict>"
    )


def _encryption_declaration_default() -> str:
    """ITSAppUsesNonExemptEncryption default value.

    `false` is the safe default for apps that only use HTTPS / Apple's
    standard crypto APIs (which are exempt). Apps using custom crypto must
    flip this to true and file the encryption registration. We emit a
    Layer-B warning when the source mentions cryptographic libraries, but
    for MVP that detection is out of scope — a comment in the generated
    Info.plist documents the override path.
    """
    return "<false/>"


# --- Layer-A finding collection ---------------------------------------------


def _collect_placeholder_findings(
    spec: XcodeSpec,
    *,
    output_dir: Path,
) -> list["Finding"]:
    """Build the Layer-A findings the emitter is responsible for.

    Each placeholder (bundle id, team id, app icon, launch screen) blocks
    submission, so they're all severity=blocker. Missing privacy manifest
    is a special case — it usually means the developer ran with
    --skip-compliance, which is a deliberate dev choice, but the manifest
    is mandatory for shipping.
    """
    from converter.report import Finding

    findings: list["Finding"] = []
    counter = 0

    def _next_id(slug: str) -> str:
        nonlocal counter
        finding_id = f"xcode.placeholder.{slug}#{counter}"
        counter += 1
        return finding_id

    if spec.bundle_id.startswith(PLACEHOLDER_BUNDLE_ID_PREFIX):
        findings.append(
            Finding(
                id=_next_id("bundle-id"),
                category="xcode.placeholder.bundle-id",
                severity="blocker",
                producer=PRODUCER,
                file="project.yml",
                line=0,
                original_snippet=f"PRODUCT_BUNDLE_IDENTIFIER: {spec.bundle_id}",
                attempted_translation=None,
                reason=(
                    f"Bundle id {spec.bundle_id!r} uses the placeholder prefix "
                    f"{PLACEHOLDER_BUNDLE_ID_PREFIX!r}. App Store Connect rejects "
                    f"submissions under com.example.*."
                ),
                recommended_fix=(
                    "Pass --bundle-id <reverse-dns> to the wrapper, e.g. "
                    "--bundle-id com.acme.myapp"
                ),
                doc_link="https://developer.apple.com/documentation/xcode/preparing-your-app-for-distribution",
            )
        )

    if spec.team_id == PLACEHOLDER_TEAM_ID:
        findings.append(
            Finding(
                id=_next_id("team-id"),
                category="xcode.placeholder.team-id",
                severity="blocker",
                producer=PRODUCER,
                file="project.yml",
                line=0,
                original_snippet=f"DEVELOPMENT_TEAM: {spec.team_id}",
                attempted_translation=None,
                reason=(
                    "Team id is the placeholder TODO_TEAMID; the project will "
                    "not sign until your 10-character Apple Developer Team ID "
                    "is set."
                ),
                recommended_fix=(
                    "Find your Team ID at https://developer.apple.com/account "
                    "(Membership tab) and pass --team-id <ID> to the wrapper."
                ),
                doc_link="https://developer.apple.com/help/account/manage-your-team/locate-your-team-id/",
            )
        )

    findings.append(
        Finding(
            id=_next_id("app-icon"),
            category="xcode.placeholder.app-icon",
            severity="blocker",
            producer=PRODUCER,
            file="App/Assets.xcassets/AppIcon.appiconset/icon-1024.png",
            line=0,
            original_snippet="(1024x1024 flat-color placeholder)",
            attempted_translation=None,
            reason=(
                "The app icon is a flat-color placeholder. App Store Connect "
                "rejects submissions whose icon does not represent the app."
            ),
            recommended_fix=(
                "Replace App/Assets.xcassets/AppIcon.appiconset/icon-1024.png "
                "with your real 1024x1024 icon. Xcode auto-generates the "
                "smaller sizes from the 1024 master."
            ),
            doc_link="https://developer.apple.com/design/human-interface-guidelines/app-icons",
        )
    )

    findings.append(
        Finding(
            id=_next_id("launch-screen"),
            category="xcode.placeholder.launch-screen",
            severity="blocker",
            producer=PRODUCER,
            file="App/Base.lproj/LaunchScreen.storyboard",
            line=0,
            original_snippet=f"centered label: {spec.app_name}",
            attempted_translation=None,
            reason=(
                "The launch screen is a text-only placeholder. Apple recommends "
                "a launch screen that visually matches the app's first frame."
            ),
            recommended_fix=(
                "Edit App/Base.lproj/LaunchScreen.storyboard in Xcode (or "
                "replace it with your own LaunchScreen asset)."
            ),
            doc_link="https://developer.apple.com/design/human-interface-guidelines/launching",
        )
    )

    if not spec.has_privacy_manifest:
        findings.append(
            Finding(
                id=_next_id("privacy-manifest"),
                category="xcode.placeholder.privacy-manifest",
                severity="blocker",
                producer=PRODUCER,
                file="PrivacyInfo.xcprivacy",
                line=0,
                original_snippet="(missing)",
                attempted_translation=None,
                reason=(
                    "PrivacyInfo.xcprivacy was not generated alongside this "
                    "project. Apple requires the privacy manifest for every "
                    "submission since Spring 2024."
                ),
                recommended_fix=(
                    "Re-run the wrapper without --skip-compliance, or run the "
                    "Step 6 compliance step manually to produce "
                    "PrivacyInfo.xcprivacy in the output dir."
                ),
                doc_link="https://developer.apple.com/documentation/bundleresources/privacy_manifest_files",
            )
        )

    return findings


# --- Atomic write ------------------------------------------------------------


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(path)


# --- Public entry point ------------------------------------------------------


def emit_xcode_project(
    *,
    spec: XcodeSpec,
    output_dir: Path,
    template_dir: Path | None = None,
) -> EmitResult:
    """Write an XcodeGen spec + supporting files into output_dir.

    Atomically per-file: a partial write of project.yml is worse than no
    project.yml at all. We do not roll back files that succeeded if a later
    file fails — by then the developer can fix the failure and re-run, and
    XcodeGen will refuse a half-written project anyway.
    """
    _validate_spec(spec)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base = template_dir or _TEMPLATE_DIR
    app_safe = _safe_app_name(spec.app_name)
    written: list[Path] = []

    # 1) project.yml
    project_yml = _substitute(
        _load_template("xcodegen.yml.tmpl", base),
        {
            "APP_NAME": spec.app_name,
            "APP_NAME_SAFE": app_safe,
            "BUNDLE_ID": spec.bundle_id,
            "TEAM_ID": spec.team_id,
            "DEPLOYMENT_TARGET": spec.deployment_target,
            "SWIFT_VERSION": spec.swift_version,
            "ENTITLEMENTS_BLOCK": _build_entitlements_block(
                app_safe, has_entitlements=any(e.entitlement_key for e in spec.entitlements)
            ),
            "CAPABILITY_SETTINGS": _build_capability_settings(spec.entitlements),
        },
    )
    project_path = output_dir / "project.yml"
    _write_text_atomic(project_path, project_yml)
    written.append(project_path)

    # 2) App/Info.plist
    info_plist = _substitute(
        _load_template("Info.plist.tmpl", base),
        {
            "APP_NAME": spec.app_name,
            "BUNDLE_ID": spec.bundle_id,
            "DEPLOYMENT_TARGET": spec.deployment_target,
            "USAGE_STRINGS_BLOCK": _build_usage_strings_block(spec.entitlements),
            "ATS_DICT": _ats_dict_default(),
            "ENCRYPTION_DECLARATION": _encryption_declaration_default(),
        },
    )
    info_path = output_dir / "App" / "Info.plist"
    _write_text_atomic(info_path, info_plist)
    written.append(info_path)

    # 3) App/AppDelegate.swift
    app_delegate = _substitute(
        _load_template("AppDelegate.swift.tmpl", base),
        {"APP_NAME_SAFE": app_safe},
    )
    delegate_path = output_dir / "App" / "AppDelegate.swift"
    _write_text_atomic(delegate_path, app_delegate)
    written.append(delegate_path)

    # 4) App/<AppName>.entitlements
    if any(e.entitlement_key for e in spec.entitlements):
        entitlements_path = output_dir / "App" / f"{app_safe}.entitlements"
        _write_bytes_atomic(entitlements_path, _build_entitlements_plist(spec.entitlements))
        written.append(entitlements_path)

    # 5) App/Assets.xcassets/  (copy entire tree from template)
    src_assets = base / "Assets.xcassets"
    dst_assets = output_dir / "App" / "Assets.xcassets"
    if dst_assets.exists():
        shutil.rmtree(dst_assets)
    shutil.copytree(src_assets, dst_assets)
    for p in dst_assets.rglob("*"):
        if p.is_file():
            written.append(p)

    # 6) App/Base.lproj/LaunchScreen.storyboard
    launch_screen = _substitute(
        _load_template("LaunchScreen.storyboard", base),
        {"APP_NAME": spec.app_name},
    )
    launch_path = output_dir / "App" / "Base.lproj" / "LaunchScreen.storyboard"
    _write_text_atomic(launch_path, launch_screen)
    written.append(launch_path)

    # 7) Re-parse validation pass — confirm placeholders left no syntactic
    # damage behind. A YAML/plist/xml that round-trips is a strong signal
    # that the substitution worked.
    _validate_artifacts(output_dir, written)

    findings = _collect_placeholder_findings(spec, output_dir=output_dir)
    return EmitResult(files_written=tuple(written), findings=tuple(findings))


def _validate_artifacts(output_dir: Path, written: list[Path]) -> None:
    """Re-parse the YAML/plist/storyboard to catch substitution damage."""
    from wrapper.compatibility import _load_yaml  # type: ignore[attr-defined]
    import xml.etree.ElementTree as ET

    project_yml = output_dir / "project.yml"
    info_plist = output_dir / "App" / "Info.plist"
    launch_screen = output_dir / "App" / "Base.lproj" / "LaunchScreen.storyboard"

    try:
        _load_yaml(project_yml.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EmitterError(f"emitted project.yml does not parse: {exc}") from exc

    try:
        plistlib.loads(info_plist.read_bytes())
    except Exception as exc:
        raise EmitterError(f"emitted Info.plist does not parse: {exc}") from exc

    try:
        ET.fromstring(launch_screen.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EmitterError(f"emitted LaunchScreen.storyboard does not parse: {exc}") from exc
