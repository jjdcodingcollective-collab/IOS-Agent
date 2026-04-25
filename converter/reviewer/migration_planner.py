"""
Migration Planner — Phase 2
Takes the analysis manifest and produces a detailed, file-by-file
migration plan mapping TypeScript/React patterns to Swift/SwiftUI equivalents.
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# iOS project structure mapping
# ---------------------------------------------------------------------------

FILE_TYPE_TO_IOS_DIR = {
    "component": "Views",
    "route": "Views",
    "hook": "ViewModels",
    "service": "Services",
    "type": "Models",
    "config": "Configuration",
    "utility": "Extensions",
    "unknown": "Misc",
}

FILE_TYPE_TO_IOS_PATTERN = {
    "component": "SwiftUI View struct",
    "route": "SwiftUI View + NavigationStack destination",
    "hook": "@Observable class (ViewModel)",
    "service": "Service struct with async methods",
    "type": "Codable struct",
    "config": "xcconfig file or Constants enum",
    "utility": "Extension or utility struct",
    "unknown": "Needs manual classification",
}


# ---------------------------------------------------------------------------
# Detailed pattern-to-iOS conversion rules
# ---------------------------------------------------------------------------

CONVERSION_RULES = {
    "component": {
        "description": "Convert to SwiftUI View struct",
        "steps": [
            "Create a struct conforming to View protocol",
            "Convert props to stored properties (let) on the struct",
            "Convert JSX return to SwiftUI body computed property",
            "Replace HTML elements with SwiftUI equivalents (div→VStack/HStack, p→Text, img→Image/AsyncImage)",
            "Convert CSS classes / Tailwind to SwiftUI modifiers",
            "Convert event handlers (onClick→Button action, onChange→.onChange modifier)",
        ],
    },
    "hook": {
        "description": "Convert to @State or SwiftUI lifecycle modifier",
        "rules": {
            "useState": "Replace with @State private var. For shared state, use @Observable ViewModel.",
            "useEffect": "Replace with .task { } (async, cancels on disappear), .onAppear { } (sync, mount only), or .onChange(of:) { } (dependency change).",
            "useContext": "Replace with @Environment. Define custom EnvironmentValues entry for app-specific context.",
            "useReducer": "Replace with @Observable ViewModel with explicit action methods.",
            "useMemo": "Replace with computed property on View or ViewModel. Swift is efficient enough that manual memoization is rarely needed.",
            "useCallback": "Usually not needed in SwiftUI. Closures are value types and views are structs. Remove and pass methods directly.",
            "useRef": "For DOM refs: use @FocusState. For mutable non-rendering state: use @State with a non-View type.",
            "useNavigate": "Use NavigationPath from @Environment or @Binding. Append to path for push, remove for pop.",
            "useParams": "Pass as initializer parameter to the View. Route params become View properties.",
            "useRouter": "Use NavigationPath or @Environment(\\.dismiss) for navigation control.",
        },
    },
    "custom_hook": {
        "description": "Convert to @Observable ViewModel class",
        "steps": [
            "Create an @Observable class named {HookName}ViewModel (drop 'use' prefix)",
            "Convert hook state (useState) to published properties on the class",
            "Convert hook effects (useEffect) to methods called from View's .task or .onAppear",
            "Convert returned values to class properties",
            "Convert returned callbacks to class methods",
        ],
    },
    "api_call": {
        "description": "Convert to URLSession / APIClient call",
        "steps": [
            "Replace fetch()/axios with APIClient.shared method call",
            "Define Codable request/response structs matching the JSON shape",
            "Use async/await (nearly identical syntax to JS)",
            "Handle errors with do/try/catch instead of .catch()",
            "Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case",
        ],
    },
    "routing": {
        "description": "Convert to NavigationStack pattern",
        "steps": [
            "Define a Route enum with cases for each route",
            "Use NavigationStack with .navigationDestination(for:)",
            "Replace <Link> with NavigationLink(value:)",
            "Replace router.push() with path.append()",
            "Replace <Route> definitions with switch cases in navigationDestination",
        ],
    },
    "state_management": {
        "description": "Convert to @Observable / @Environment",
        "steps": [
            "Replace Redux/Zustand store with @Observable class",
            "Replace useSelector with @Environment access",
            "Replace dispatch with direct method calls on the observable",
            "Inject at app root with .environment()",
            "For complex state, keep the store pattern but use @Observable instead of createStore",
        ],
    },
    "styling": {
        "description": "Convert to SwiftUI modifiers",
        "rules": {
            "tailwind": "Map Tailwind utilities to SwiftUI modifiers. Common: p-4→.padding(16), flex→HStack/VStack, text-lg→.font(.title3), bg-blue-500→.background(.blue), rounded-lg→.clipShape(RoundedRectangle(cornerRadius: 12)), w-full→.frame(maxWidth: .infinity)",
            "css-modules": "Extract styles into custom ViewModifier structs. Group related styles into reusable modifiers.",
            "styled-components": "Convert to custom ViewModifier structs or View extensions.",
        },
    },
    "type_definition": {
        "description": "Convert to Swift struct/enum",
        "steps": [
            "Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)",
            "Convert optional fields (field?: type) to Swift optionals (var field: Type?)",
            "Convert union types to Swift enums with associated values",
            "Convert Record<K,V> to [K: V] dictionary",
            "Convert Array<T> to [T]",
            "Convert string literal unions to String-backed enums",
        ],
    },
    "env_variable": {
        "description": "Move to xcconfig / Info.plist",
        "steps": [
            "Create Debug.xcconfig and Release.xcconfig files",
            "Add variable: VAR_NAME = value",
            "Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>",
            "Access in code: Bundle.main.infoDictionary?[\"VarName\"] as? String",
        ],
    },
    "storage": {
        "description": "Convert to iOS storage equivalent",
        "rules": {
            "localStorage": "For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).",
            "sessionStorage": "Use @State or in-memory property on ViewModel. Data cleared when view/app dismissed.",
            "cookies": "Use HTTPCookieStorage.shared or WKWebsiteDataStore for WebView cookies.",
        },
    },
    "web_api": {
        "description": "Replace with native iOS framework",
        "rules": {
            "Geolocation": "Use CoreLocation: CLLocationManager with requestWhenInUseAuthorization(). Add NSLocationWhenInUseUsageDescription to Info.plist.",
            "MediaDevices": "Use AVFoundation: AVCaptureSession for camera/mic. Add NSCameraUsageDescription and NSMicrophoneUsageDescription to Info.plist.",
            "Web Share": "Use UIActivityViewController or ShareLink (SwiftUI). Native share sheet with no permissions needed.",
            "Clipboard": "Use UIPasteboard.general. No permissions needed.",
            "WebSocket": "Use URLSession.shared.webSocketTask(with:). Nearly identical API to JS WebSocket.",
            "IntersectionObserver": "Use .onAppear modifier for visibility detection, or GeometryReader for position-based logic.",
            "rAF": "Use withAnimation { } for animations. For frame-synced work, use CADisplayLink.",
            "DOM Events": "SwiftUI handles events declaratively. Use .onTapGesture, .gesture(), .onAppear, NotificationCenter for app-level events.",
            "DOM Access": "Not applicable in SwiftUI — UI is declarative, not imperative. Restructure logic to use @State and @Binding.",
            "Web Notifications": "Use UNUserNotificationCenter. Request permission, schedule local notifications. Add push notification entitlement for remote.",
        },
    },
}


# ---------------------------------------------------------------------------
# Migration plan generation
# ---------------------------------------------------------------------------

def _swift_filename(relative_path: str, file_type: str) -> str:
    """Convert a TS/TSX file path to a Swift file path."""
    name = Path(relative_path).stem

    # PascalCase the name
    if "-" in name or "_" in name:
        parts = name.replace("-", "_").split("_")
        name = "".join(p.capitalize() for p in parts)
    elif name[0].islower():
        name = name[0].upper() + name[1:]

    # Add appropriate suffix
    suffix_map = {
        "component": "View",
        "route": "View",
        "hook": "ViewModel",
        "service": "Service",
        "type": "",
        "config": "Config",
        "utility": "+Extensions",
    }
    suffix = suffix_map.get(file_type, "")

    # Don't double-suffix
    if suffix and not name.endswith(suffix):
        name = f"{name}{suffix}"

    return f"{name}.swift"


def _get_pattern_guidance(pattern: dict) -> dict:
    """Get conversion guidance for a single pattern."""
    ptype = pattern["pattern_type"]
    name = pattern["name"]

    rule = CONVERSION_RULES.get(ptype, {})

    guidance = {
        "pattern": f"{ptype}: {name}",
        "difficulty": pattern["conversion_difficulty"],
        "ios_equivalent": pattern["details"].get("ios_equivalent", ""),
        "description": rule.get("description", ""),
    }

    # Get specific sub-rules if available
    if "rules" in rule and name in rule["rules"]:
        guidance["conversion_steps"] = [rule["rules"][name]]
    elif "steps" in rule:
        guidance["conversion_steps"] = rule["steps"]

    return guidance


def generate_migration_plan(manifest: dict) -> str:
    """Generate a complete migration plan from the analysis manifest."""
    summary = manifest["summary"]
    files = manifest["files"]

    lines = []
    lines.append("# iOS Migration Plan")
    lines.append("")
    lines.append(f"> Generated: {manifest['meta']['generated_at']}")
    lines.append(f"> Source: `{manifest['meta']['source_dir']}`")
    lines.append("")

    # Executive summary
    total = summary["total_patterns"] or 1
    auto = summary["conversion_difficulty"]["auto"]
    assisted = summary["conversion_difficulty"]["assisted"]
    manual = summary["conversion_difficulty"]["manual"]

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"**{summary['total_files']} files** to convert with **{summary['total_patterns']} patterns** detected.")
    lines.append("")
    lines.append(f"| Conversion Level | Count | % | Meaning |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| Auto | {auto} | {auto/total*100:.0f}% | Direct 1:1 mapping exists |")
    lines.append(f"| Assisted | {assisted} | {assisted/total*100:.0f}% | Mapping exists but requires restructuring |")
    lines.append(f"| Manual | {manual} | {manual/total*100:.0f}% | No direct equivalent — needs rethinking |")
    lines.append("")

    # Recommended conversion order
    lines.append("## Recommended Conversion Order")
    lines.append("")
    lines.append("Convert in this order to minimize dependency issues:")
    lines.append("")
    lines.append("1. **Types / Models** — No dependencies, foundation for everything else")
    lines.append("2. **Configuration** — Environment setup needed early")
    lines.append("3. **Services / API Layer** — Networking code, depends on models")
    lines.append("4. **ViewModels (Hooks)** — Business logic, depends on services + models")
    lines.append("5. **Components / Views** — UI layer, depends on everything above")
    lines.append("6. **Routes / Navigation** — Wire everything together last")
    lines.append("")

    # iOS project structure
    lines.append("## Target iOS Project Structure")
    lines.append("")
    lines.append("```")
    lines.append("MyApp/")
    lines.append("├── App/")
    lines.append("│   ├── MyAppApp.swift")
    lines.append("│   └── AppState.swift")

    # Group files by target directory
    dir_files: dict[str, list] = {}
    for f in files:
        if f["patterns"]:
            ios_dir = FILE_TYPE_TO_IOS_DIR.get(f["file_type"], "Misc")
            dir_files.setdefault(ios_dir, []).append(f)

    for ios_dir in ["Models", "Configuration", "Services", "ViewModels", "Views", "Extensions", "Misc"]:
        if ios_dir in dir_files:
            lines.append(f"├── {ios_dir}/")
            for f in dir_files[ios_dir]:
                swift_name = _swift_filename(f["relative_path"], f["file_type"])
                lines.append(f"│   ├── {swift_name}")

    lines.append("├── Resources/")
    lines.append("│   └── Assets.xcassets")
    lines.append("└── Configuration/")
    lines.append("    ├── Debug.xcconfig")
    lines.append("    └── Release.xcconfig")
    lines.append("```")
    lines.append("")

    # File-by-file migration plan
    # Sort by conversion order
    order = {"type": 0, "config": 1, "service": 2, "hook": 3, "utility": 4, "component": 5, "route": 6, "unknown": 7}

    sorted_files = sorted(files, key=lambda f: order.get(f["file_type"], 99))

    lines.append("## File-by-File Migration")
    lines.append("")

    current_phase = None
    phase_names = {
        "type": "Phase 1: Types & Models",
        "config": "Phase 2: Configuration",
        "service": "Phase 3: Services & API",
        "hook": "Phase 4: ViewModels (from Hooks)",
        "utility": "Phase 4b: Utilities",
        "component": "Phase 5: Views (from Components)",
        "route": "Phase 6: Navigation (from Routes)",
        "unknown": "Unclassified (Manual Review Needed)",
    }

    for f in sorted_files:
        if not f["patterns"]:
            continue

        phase = phase_names.get(f["file_type"], "Unclassified")
        if phase != current_phase:
            current_phase = phase
            lines.append(f"### {phase}")
            lines.append("")

        swift_name = _swift_filename(f["relative_path"], f["file_type"])
        ios_dir = FILE_TYPE_TO_IOS_DIR.get(f["file_type"], "Misc")
        ios_pattern = FILE_TYPE_TO_IOS_PATTERN.get(f["file_type"], "TBD")

        lines.append(f"#### `{f['relative_path']}` -> `{ios_dir}/{swift_name}`")
        lines.append("")
        lines.append(f"**Target pattern:** {ios_pattern}")
        lines.append("")

        # Conversion guidance per pattern
        for p in f["patterns"]:
            guidance = _get_pattern_guidance(p)
            diff = guidance["difficulty"].upper()
            lines.append(f"- [{diff}] **{guidance['pattern']}**")
            if guidance.get("ios_equivalent"):
                lines.append(f"  - iOS equivalent: `{guidance['ios_equivalent']}`")
            if guidance.get("conversion_steps"):
                for step in guidance["conversion_steps"]:
                    lines.append(f"  - {step}")

        lines.append("")

    # Third-party dependency mapping
    if summary["third_party_libraries"]:
        lines.append("## Dependency Mapping")
        lines.append("")
        lines.append("| Web Package | Swift Equivalent | Notes |")
        lines.append("|---|---|---|")

        dep_map = {
            "react": ("SwiftUI (built-in)", "Core framework, no package needed"),
            "react-dom": ("SwiftUI (built-in)", ""),
            "next": ("SwiftUI + NavigationStack", "No server-side rendering equivalent"),
            "react-router": ("NavigationStack (built-in)", ""),
            "react-router-dom": ("NavigationStack (built-in)", ""),
            "axios": ("URLSession (built-in)", "Or build an APIClient wrapper"),
            "swr": ("@Observable + .task", "Manual caching if needed"),
            "@tanstack/react-query": ("@Observable + .task", "Manual caching if needed"),
            "zustand": ("@Observable (built-in)", ""),
            "redux": ("@Observable (built-in)", ""),
            "@reduxjs/toolkit": ("@Observable (built-in)", ""),
            "tailwindcss": ("SwiftUI modifiers (built-in)", ""),
            "styled-components": ("SwiftUI ViewModifier", ""),
            "framer-motion": ("SwiftUI animation (built-in)", ""),
            "date-fns": ("Foundation Date/Calendar (built-in)", ""),
            "dayjs": ("Foundation Date/Calendar (built-in)", ""),
            "lodash": ("Swift stdlib (mostly built-in)", ""),
            "zod": ("Codable + custom validation", ""),
            "yup": ("Codable + custom validation", ""),
            "react-hook-form": ("SwiftUI @State + @Binding", ""),
            "@hookform/resolvers": ("Custom validation functions", ""),
            "lucide-react": ("SF Symbols (built-in)", "5000+ icons, no package needed"),
            "@heroicons/react": ("SF Symbols (built-in)", ""),
            "clsx": ("Not needed (no className concatenation)", ""),
            "class-variance-authority": ("Custom ViewModifier variants", ""),
        }

        for lib in summary["third_party_libraries"]:
            if lib in dep_map:
                swift_eq, notes = dep_map[lib]
                lines.append(f"| `{lib}` | {swift_eq} | {notes} |")
            else:
                lines.append(f"| `{lib}` | *(needs research)* | Check Swift Package Index |")

        lines.append("")

    # Environment variable migration
    if summary["env_variables"]:
        lines.append("## Environment Variable Migration")
        lines.append("")
        lines.append("Create these xcconfig entries:")
        lines.append("")
        lines.append("```")
        lines.append("// Debug.xcconfig")
        for var in summary["env_variables"]:
            clean_name = var.replace("NEXT_PUBLIC_", "").replace("VITE_", "").replace("REACT_APP_", "")
            lines.append(f"{clean_name} = $(inherited)")
        lines.append("")
        lines.append("// Release.xcconfig")
        for var in summary["env_variables"]:
            clean_name = var.replace("NEXT_PUBLIC_", "").replace("VITE_", "").replace("REACT_APP_", "")
            lines.append(f"{clean_name} = $(inherited)")
        lines.append("```")
        lines.append("")

    # Checklist
    lines.append("## Pre-Migration Checklist")
    lines.append("")
    lines.append("- [ ] Xcode installed and configured (see docs/01-getting-started/environment-setup.md)")
    lines.append("- [ ] Apple Developer account set up")
    lines.append("- [ ] New Xcode project created with SwiftUI template")
    lines.append("- [ ] Target iOS 17+ minimum deployment")
    lines.append("- [ ] xcconfig files created for Debug and Release")
    lines.append("- [ ] API base URLs configured per environment")
    lines.append("- [ ] Models (Codable structs) created and tested with sample JSON")
    lines.append("- [ ] APIClient wrapper built and tested against your staging API")
    lines.append("")

    return "\n".join(lines)
