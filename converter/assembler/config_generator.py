"""
Configuration Generator — Creates xcconfig files, Package.swift,
project.yml (XcodeGen), and build configuration from detected
environment variables and dependencies.
"""

from ..rewriter.swift_helpers import swift_header, format_swift


# ---------------------------------------------------------------------------
# XcodeGen project.yml generation
# ---------------------------------------------------------------------------

def generate_xcodegen_project(
    app_name: str,
    npm_dependencies: list[str],
    ios_version: str = "17.0",
    has_resources: bool = True,
) -> str:
    """
    Generate a project.yml for XcodeGen — an alternative to Package.swift
    that produces a full .xcodeproj when `xcodegen generate` is run.

    This is optional: the SPM Package.swift works on its own.
    """
    spm_packages = _resolve_spm_packages(npm_dependencies)

    lines = []
    lines.append(f"name: {app_name}")
    lines.append("")
    lines.append("options:")
    lines.append("  bundleIdPrefix: com.example")
    lines.append("  deploymentTarget:")
    lines.append(f"    iOS: \"{ios_version}\"")
    lines.append("  xcodeVersion: \"15.0\"")
    lines.append("")

    # SPM packages
    if spm_packages:
        lines.append("packages:")
        for pkg in spm_packages:
            lines.append(f"  {pkg['name']}:")
            lines.append(f"    url: {pkg['url']}")
            lines.append(f"    from: \"{pkg['version']}\"")
        lines.append("")

    lines.append("targets:")
    lines.append(f"  {app_name}:")
    lines.append("    type: application")
    lines.append("    platform: iOS")
    lines.append(f"    deploymentTarget: \"{ios_version}\"")
    lines.append("    sources:")
    lines.append(f"      - Sources/{app_name}")
    if has_resources:
        lines.append("    resources:")
        lines.append(f"      - Sources/{app_name}/Resources")
    lines.append("    settings:")
    lines.append("      base:")
    lines.append(f"        PRODUCT_BUNDLE_IDENTIFIER: com.example.{app_name.lower()}")
    lines.append(f"        PRODUCT_NAME: {app_name}")
    lines.append("        SWIFT_VERSION: \"5.9\"")
    lines.append("        GENERATE_INFOPLIST_FILE: NO")
    lines.append(f"        INFOPLIST_FILE: Sources/{app_name}/Info.plist")
    lines.append("      configs:")
    lines.append("        Debug:")
    lines.append(f"          base: Sources/{app_name}/Configuration/Debug.xcconfig")
    lines.append("        Release:")
    lines.append(f"          base: Sources/{app_name}/Configuration/Release.xcconfig")

    if spm_packages:
        lines.append("    dependencies:")
        for pkg in spm_packages:
            lines.append(f"      - package: {pkg['name']}")

    lines.append("")
    lines.append(f"  {app_name}Tests:")
    lines.append("    type: bundle.unit-test")
    lines.append("    platform: iOS")
    lines.append("    sources:")
    lines.append(f"      - Tests/{app_name}Tests")
    lines.append("    dependencies:")
    lines.append(f"      - target: {app_name}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# npm package -> Swift Package mapping
# ---------------------------------------------------------------------------

NPM_TO_SPM: dict[str, dict] = {
    # Networking
    "axios": None,  # Built-in: URLSession
    "node-fetch": None,

    # State management
    "redux": None,  # Built-in: @Observable
    "@reduxjs/toolkit": None,
    "zustand": None,
    "recoil": None,
    "jotai": None,
    "mobx": None,

    # Routing
    "react-router": None,  # Built-in: NavigationStack
    "react-router-dom": None,
    "next": None,

    # UI
    "react": None,  # Built-in: SwiftUI
    "react-dom": None,
    "tailwindcss": None,
    "styled-components": None,
    "framer-motion": None,

    # Date/time
    "date-fns": None,  # Built-in: Foundation Date
    "dayjs": None,
    "moment": None,

    # Validation
    "zod": None,  # Built-in: Codable + custom
    "yup": None,

    # Forms
    "react-hook-form": None,  # Built-in: @State + @Binding
    "formik": None,

    # Utilities
    "lodash": None,  # Built-in: Swift stdlib
    "clsx": None,
    "class-variance-authority": None,

    # Icons
    "lucide-react": None,  # Built-in: SF Symbols
    "@heroicons/react": None,

    # Actual SPM packages for features that need them
    "socket.io-client": {
        "name": "Starscream",
        "url": "https://github.com/nicklockwood/SwiftFormat",
        "version": "4.0.0",
        "note": "WebSocket client (or use built-in URLSession.webSocketTask)",
    },
    "@sentry/react": {
        "name": "Sentry",
        "url": "https://github.com/getsentry/sentry-cocoa",
        "version": "8.0.0",
        "note": "Error tracking and performance monitoring",
    },
    "firebase": {
        "name": "Firebase",
        "url": "https://github.com/firebase/firebase-ios-sdk",
        "version": "10.0.0",
        "note": "Firebase SDK for iOS",
    },
    "@stripe/stripe-js": {
        "name": "StripePaymentSheet",
        "url": "https://github.com/stripe/stripe-ios",
        "version": "23.0.0",
        "note": "Stripe payments SDK",
    },
}


def generate_xcconfig(
    env_vars: list[str],
    config_type: str = "Debug",
) -> str:
    """
    Generate an xcconfig file from detected environment variables.

    Args:
        env_vars: List of env variable names (e.g., NEXT_PUBLIC_API_URL)
        config_type: "Debug" or "Release"
    """
    lines = []
    lines.append(f"// {config_type}.xcconfig")
    lines.append(f"// Auto-generated by iOS Code Converter")
    lines.append(f"//")
    lines.append(f"// 💡 Learn: xcconfig files are the iOS equivalent of .env files.")
    lines.append(f"//    Values are resolved at compile time and baked into the app binary.")
    lines.append(f"//    Unlike .env, you can't change these without rebuilding.")
    lines.append(f"//")
    lines.append("")

    # Standard build settings
    lines.append("// Build settings")
    if config_type == "Debug":
        lines.append("SWIFT_OPTIMIZATION_LEVEL = -Onone")
        lines.append("DEBUG_INFORMATION_FORMAT = dwarf-with-dsym")
        lines.append("ENABLE_TESTABILITY = YES")
    else:
        lines.append("SWIFT_OPTIMIZATION_LEVEL = -O")
        lines.append("DEBUG_INFORMATION_FORMAT = dwarf-with-dsym")
        lines.append("ENABLE_TESTABILITY = NO")

    lines.append("")
    lines.append("// App configuration")
    lines.append("// These values are accessible via Bundle.main.infoDictionary")
    lines.append("")

    for var in env_vars:
        clean_name = _clean_env_name(var)
        if config_type == "Debug":
            if "URL" in var.upper() or "API" in var.upper():
                lines.append(f"{clean_name} = https://staging-api.example.com")
            else:
                lines.append(f"{clean_name} = DEBUG_VALUE")
        else:
            if "URL" in var.upper() or "API" in var.upper():
                lines.append(f"{clean_name} = https://api.example.com")
            else:
                lines.append(f"{clean_name} = PRODUCTION_VALUE")

        lines.append(f"// Source: {var}")
        lines.append("")

    return "\n".join(lines)


def generate_package_swift(
    app_name: str,
    npm_dependencies: list[str],
    ios_version: str = "17.0",
    has_resources: bool = True,
) -> str:
    """
    Generate Package.swift from detected npm dependencies.

    The generated package uses SPM's executable target layout so Xcode can
    open Package.swift directly — no .xcodeproj needed.

    Directory layout expected:
        Package.swift
        Sources/{AppName}/
            App/
            Views/
            ViewModels/
            Models/
            Services/
            Configuration/
            Resources/
        Tests/{AppName}Tests/

    Args:
        app_name: Name of the app
        npm_dependencies: List of npm package names from the web project
        ios_version: Minimum iOS version target
        has_resources: Whether to include resource processing rules
    """
    spm_packages = _resolve_spm_packages(npm_dependencies)
    builtin_notes = _resolve_builtin_notes(npm_dependencies)

    lines = []
    lines.append("// swift-tools-version: 5.9")
    lines.append(f"// Package.swift — {app_name}")
    lines.append("//")
    lines.append("// Auto-generated by iOS Code Converter")
    lines.append("//")
    lines.append("// 💡 Learn: Package.swift is the iOS equivalent of package.json.")
    lines.append("//    It's actual Swift code (not JSON), and SPM is built into Xcode.")
    lines.append("//    Open this file in Xcode: File > Open > select Package.swift")
    lines.append("//    Many web dependencies map to built-in Apple frameworks — no package needed.")
    lines.append("//")

    if builtin_notes:
        lines.append("// The following web dependencies are BUILT INTO iOS (no package needed):")
        for dep in builtin_notes:
            lines.append(f"//   - {dep}")
        lines.append("//")

    lines.append("")
    lines.append("import PackageDescription")
    lines.append("")
    lines.append("let package = Package(")
    lines.append(f'    name: "{app_name}",')
    lines.append("    platforms: [")
    lines.append(f'        .iOS(.v{ios_version.replace(".", "_")}),')
    lines.append("    ],")

    # Dependencies
    lines.append("    dependencies: [")
    if spm_packages:
        for pkg in spm_packages:
            lines.append(f'        // {pkg.get("note", "")}')
            lines.append(f'        .package(url: "{pkg["url"]}", from: "{pkg["version"]}"),')
    else:
        lines.append("        // No external dependencies needed — Apple frameworks cover everything!")
    lines.append("    ],")

    # Targets
    lines.append("    targets: [")
    lines.append(f'        .executableTarget(')
    lines.append(f'            name: "{app_name}",')

    if spm_packages:
        lines.append("            dependencies: [")
        for pkg in spm_packages:
            lines.append(f'                .product(name: "{pkg["name"]}", package: "{pkg["name"]}"),')
        lines.append("            ],")

    lines.append(f'            path: "Sources/{app_name}",')

    # Resource processing rules
    if has_resources:
        lines.append("            resources: [")
        lines.append(f'                .process("Resources"),')
        lines.append("            ],")

    # Exclude non-Swift files from compilation
    lines.append("            exclude: [")
    lines.append('                "Info.plist",')
    lines.append("            ]")
    lines.append("        ),")

    # Test target
    lines.append(f'        .testTarget(')
    lines.append(f'            name: "{app_name}Tests",')
    lines.append(f'            dependencies: ["{app_name}"],')
    lines.append(f'            path: "Tests/{app_name}Tests"')
    lines.append("        ),")

    lines.append("    ]")
    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def generate_config_enum(
    app_name: str,
    env_vars: list[str],
) -> str:
    """
    Generate an AppConfig.swift enum that reads values from Info.plist
    (which are populated from xcconfig at build time).
    """
    lines = []
    lines.append(swift_header("AppConfig.swift", app_name))
    lines.append("import Foundation")
    lines.append("")
    lines.append("// 💡 Learn: This enum provides type-safe access to build configuration.")
    lines.append("//    Values come from xcconfig → Info.plist → Bundle at compile time.")
    lines.append("//    Unlike .env, these can't be changed without rebuilding the app.")
    lines.append("")
    lines.append("enum AppConfig {")
    lines.append("")

    for var in env_vars:
        clean_name = _clean_env_name(var)
        swift_name = _to_camel(clean_name)
        lines.append(f'    static let {swift_name}: String = {{')
        lines.append(f'        guard let value = Bundle.main.infoDictionary?["{clean_name}"] as? String else {{')
        lines.append(f'            #if DEBUG')
        lines.append(f'            fatalError("Missing config: {clean_name} — check xcconfig")')
        lines.append(f'            #else')
        lines.append(f'            return ""')
        lines.append(f'            #endif')
        lines.append(f'        }}')
        lines.append(f'        return value')
        lines.append(f'    }}()')
        lines.append(f'    // Source: {var}')
        lines.append("")

    lines.append("}")
    lines.append("")

    return format_swift("\n".join(lines))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_spm_packages(npm_dependencies: list[str]) -> list[dict]:
    """Map npm dependencies to SPM packages, excluding built-ins."""
    spm_packages = []
    for npm_dep in npm_dependencies:
        if npm_dep in NPM_TO_SPM:
            spm_info = NPM_TO_SPM[npm_dep]
            if spm_info is not None:
                if not any(p["name"] == spm_info["name"] for p in spm_packages):
                    spm_packages.append(spm_info)
    return spm_packages


def _resolve_builtin_notes(npm_dependencies: list[str]) -> list[str]:
    """Return npm packages that map to built-in iOS frameworks."""
    return [
        dep for dep in npm_dependencies
        if dep in NPM_TO_SPM and NPM_TO_SPM[dep] is None
    ]


def _clean_env_name(var: str) -> str:
    """Strip web-specific prefixes from env variable names."""
    for prefix in ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "GATSBY_"):
        if var.startswith(prefix):
            return var[len(prefix):]
    return var


def _to_camel(name: str) -> str:
    """Convert UPPER_SNAKE to camelCase."""
    parts = name.lower().split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
