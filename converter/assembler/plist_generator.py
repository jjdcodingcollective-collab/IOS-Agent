"""
Info.plist Generator — Creates Info.plist from detected patterns.

Phase B: BUILD-4 (GAP-I2)

Generates a complete Info.plist by:
1. Setting required app metadata (bundle ID, version, display name)
2. Detecting Web API usage that requires iOS privacy descriptions
3. Adding App Transport Security exceptions for HTTP URLs
4. Setting up launch screen and orientation configuration
"""


# ---------------------------------------------------------------------------
# Web API → iOS permission mapping
# ---------------------------------------------------------------------------

# Maps patterns detected in the web source to required Info.plist privacy keys.
# Apple rejects apps that request permissions without a usage description.
WEB_API_TO_PLIST_KEYS: dict[str, dict] = {
    # Geolocation
    "Geolocation": {
        "keys": {
            "NSLocationWhenInUseUsageDescription":
                "This app needs your location to provide nearby results.",
        },
        "learn": "iOS requires a human-readable reason for location access. "
                 "This string is shown to the user in the permission prompt.",
    },
    "navigator.geolocation": {
        "keys": {
            "NSLocationWhenInUseUsageDescription":
                "This app needs your location to provide nearby results.",
        },
    },

    # Camera / Microphone
    "MediaDevices": {
        "keys": {
            "NSCameraUsageDescription":
                "This app needs camera access to take photos.",
            "NSMicrophoneUsageDescription":
                "This app needs microphone access for audio recording.",
        },
        "learn": "Camera and microphone are separate permissions on iOS. "
                 "The user can grant one without the other.",
    },
    "getUserMedia": {
        "keys": {
            "NSCameraUsageDescription":
                "This app needs camera access to capture video.",
            "NSMicrophoneUsageDescription":
                "This app needs microphone access for audio.",
        },
    },

    # Photo library
    "FileReader": {
        "keys": {
            "NSPhotoLibraryUsageDescription":
                "This app needs photo library access to select images.",
        },
    },
    "file_upload": {
        "keys": {
            "NSPhotoLibraryUsageDescription":
                "This app needs photo library access to select files.",
        },
    },

    # Notifications
    "Web Notifications": {
        "keys": {},  # No plist key needed — handled via UNUserNotificationCenter at runtime
        "learn": "iOS notifications don't need an Info.plist entry. "
                 "You request permission at runtime via UNUserNotificationCenter.",
    },
    "Notification": {
        "keys": {},
    },

    # Clipboard (no plist needed on iOS)
    "Clipboard": {
        "keys": {},
        "learn": "UIPasteboard doesn't require a privacy description. "
                 "However, iOS shows a banner when your app reads the clipboard.",
    },

    # Bluetooth
    "Bluetooth": {
        "keys": {
            "NSBluetoothAlwaysUsageDescription":
                "This app uses Bluetooth to connect to nearby devices.",
        },
    },

    # Face ID
    "FaceID": {
        "keys": {
            "NSFaceIDUsageDescription":
                "This app uses Face ID for secure authentication.",
        },
    },

    # Contacts
    "Contacts": {
        "keys": {
            "NSContactsUsageDescription":
                "This app needs access to your contacts.",
        },
    },

    # Calendar
    "Calendar": {
        "keys": {
            "NSCalendarsUsageDescription":
                "This app needs access to your calendar.",
        },
    },
}


# Patterns in source code that indicate HTTP (non-HTTPS) API calls
HTTP_URL_INDICATORS = [
    "http://",
    "http://localhost",
    "http://127.0.0.1",
    "http://0.0.0.0",
]


def generate_info_plist(
    app_name: str,
    manifest: dict,
    env_vars: list[str] | None = None,
) -> str:
    """
    Generate Info.plist from the analysis manifest.

    Args:
        app_name: Name of the app
        manifest: Phase 1 analysis manifest
        env_vars: Environment variables detected in the source

    Returns:
        XML string containing the Info.plist
    """
    entries: dict[str, str] = {}

    # ----- Core app metadata -----
    entries["CFBundleDevelopmentRegion"] = "$(DEVELOPMENT_LANGUAGE)"
    entries["CFBundleExecutable"] = "$(EXECUTABLE_NAME)"
    entries["CFBundleIdentifier"] = f"$(PRODUCT_BUNDLE_IDENTIFIER)"
    entries["CFBundleInfoDictionaryVersion"] = "6.0"
    entries["CFBundleName"] = app_name
    entries["CFBundlePackageType"] = "$(PRODUCT_BUNDLE_PACKAGE_TYPE)"
    entries["CFBundleShortVersionString"] = "1.0.0"
    entries["CFBundleVersion"] = "1"

    # ----- Launch screen (required for full-screen apps) -----
    # Using dict marker — will be serialized as empty <dict/>
    entries["UILaunchScreen"] = "__EMPTY_DICT__"

    # ----- Supported orientations -----
    entries["UISupportedInterfaceOrientations"] = "__ARRAY__:UIInterfaceOrientationPortrait,UIInterfaceOrientationLandscapeLeft,UIInterfaceOrientationLandscapeRight"

    # ----- Detect privacy permissions from patterns -----
    all_patterns = _collect_all_patterns(manifest)
    pattern_names = {p.get("name", "") for p in all_patterns}
    pattern_types = {p.get("pattern_type", "") for p in all_patterns}

    # Also check raw source content hints from the manifest
    detected_apis = set()
    for f in manifest.get("files", []):
        for p in f.get("patterns", []):
            name = p.get("name", "")
            ptype = p.get("pattern_type", "")
            details = p.get("details", {})
            detected_apis.add(name)
            detected_apis.add(ptype)

            # Check for specific Web API usage in details
            ios_equiv = details.get("ios_equivalent", "")
            if "CLLocation" in ios_equiv or "location" in name.lower():
                detected_apis.add("Geolocation")
            if "camera" in name.lower() or "AVCapture" in ios_equiv:
                detected_apis.add("MediaDevices")
            if "notification" in name.lower():
                detected_apis.add("Notification")

    # Map detected APIs to plist keys
    for api_name, mapping in WEB_API_TO_PLIST_KEYS.items():
        if api_name in detected_apis or api_name in pattern_names or api_name in pattern_types:
            for key, value in mapping.get("keys", {}).items():
                if key not in entries:
                    entries[key] = value

    # ----- App Transport Security -----
    needs_ats_exception = _detect_http_urls(manifest, env_vars or [])
    if needs_ats_exception:
        entries["NSAppTransportSecurity"] = "__ATS_EXCEPTIONS__"

    # ----- Env vars as Info.plist entries (for xcconfig injection) -----
    if env_vars:
        for var in env_vars:
            clean = _clean_env_name(var)
            entries[clean] = f"$({clean})"

    return _serialize_plist(entries, app_name)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_plist(entries: dict[str, str], app_name: str) -> str:
    """Serialize entries dict to XML plist format."""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"')
    lines.append('    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">')
    lines.append("<!--")
    lines.append(f"  Info.plist — {app_name}")
    lines.append("  Auto-generated by iOS Code Converter")
    lines.append("")
    lines.append("  Learn: Info.plist is the iOS equivalent of a web app's manifest.json +")
    lines.append("  .env file combined. It declares app metadata, required permissions, and")
    lines.append("  system integration points. Apple's App Review checks this file — missing")
    lines.append("  privacy descriptions cause automatic rejection.")
    lines.append("-->")
    lines.append('<plist version="1.0">')
    lines.append("<dict>")

    for key in sorted(entries.keys()):
        value = entries[key]

        if value == "__EMPTY_DICT__":
            lines.append(f"    <key>{key}</key>")
            lines.append("    <dict/>")

        elif value == "__ATS_EXCEPTIONS__":
            lines.append(f"    <key>{key}</key>")
            lines.append("    <dict>")
            lines.append("        <!-- Allow HTTP for local development. Remove for production. -->")
            lines.append("        <key>NSAllowsLocalNetworking</key>")
            lines.append("        <true/>")
            lines.append("    </dict>")

        elif value.startswith("__ARRAY__:"):
            items = value[len("__ARRAY__:"):].split(",")
            lines.append(f"    <key>{key}</key>")
            lines.append("    <array>")
            for item in items:
                lines.append(f"        <string>{item.strip()}</string>")
            lines.append("    </array>")

        elif key.startswith("NS") and "UsageDescription" in key:
            # Privacy descriptions — add learn comment
            lines.append(f"    <!-- Privacy: {_privacy_description_context(key)} -->")
            lines.append(f"    <key>{key}</key>")
            lines.append(f"    <string>{_xml_escape(value)}</string>")

        else:
            lines.append(f"    <key>{key}</key>")
            lines.append(f"    <string>{_xml_escape(value)}</string>")

    lines.append("</dict>")
    lines.append("</plist>")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _collect_all_patterns(manifest: dict) -> list[dict]:
    """Flatten all patterns from all files in the manifest."""
    patterns = []
    for f in manifest.get("files", []):
        patterns.extend(f.get("patterns", []))
    return patterns


def _detect_http_urls(manifest: dict, env_vars: list[str]) -> bool:
    """Check if the project uses any HTTP (non-HTTPS) URLs."""
    # Check env vars for HTTP URLs
    for var in env_vars:
        if any(indicator in var.lower() for indicator in ["localhost", "127.0.0.1"]):
            return True

    # Check patterns for HTTP API calls
    for f in manifest.get("files", []):
        for p in f.get("patterns", []):
            url = p.get("details", {}).get("url", "")
            if any(url.startswith(h) for h in HTTP_URL_INDICATORS):
                return True

    return False


def _privacy_description_context(key: str) -> str:
    """Return a brief context string for a privacy key."""
    context_map = {
        "NSLocationWhenInUseUsageDescription": "Location — shown when app requests GPS access",
        "NSCameraUsageDescription": "Camera — shown when app requests camera access",
        "NSMicrophoneUsageDescription": "Microphone — shown when app requests mic access",
        "NSPhotoLibraryUsageDescription": "Photo Library — shown when app requests photo access",
        "NSBluetoothAlwaysUsageDescription": "Bluetooth — shown when app requests BLE access",
        "NSFaceIDUsageDescription": "Face ID — shown when app requests biometric auth",
        "NSContactsUsageDescription": "Contacts — shown when app requests address book",
        "NSCalendarsUsageDescription": "Calendar — shown when app requests calendar access",
    }
    return context_map.get(key, "Update this description for your app's specific use case")


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _clean_env_name(var: str) -> str:
    """Strip web-specific prefixes from env variable names."""
    for prefix in ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "GATSBY_"):
        if var.startswith(prefix):
            return var[len(prefix):]
    return var
