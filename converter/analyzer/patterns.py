"""
Pattern Detector — Phase 1, Step 2
Identifies React/TypeScript patterns in source files and classifies them
for iOS conversion.
"""

import re
from dataclasses import dataclass, field


@dataclass
class DetectedPattern:
    """A single detected pattern within a file."""
    pattern_type: str       # e.g. "component", "hook", "route", "api_call"
    name: str               # identifier name
    line: int               # line number where detected
    details: dict = field(default_factory=dict)
    conversion_difficulty: str = "auto"  # auto | assisted | manual


@dataclass
class FileAnalysis:
    """Complete analysis of a single file."""
    relative_path: str
    extension: str
    file_type: str          # "component", "hook", "service", "route", "type", "config", "utility", "unknown"
    patterns: list[DetectedPattern] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pattern matchers — each returns a list of DetectedPattern
# ---------------------------------------------------------------------------

def detect_components(content: str) -> list[DetectedPattern]:
    """Detect React components (function and arrow)."""
    patterns = []

    # Function components: export function MyComponent(
    for m in re.finditer(
        r"(?:export\s+(?:default\s+)?)?function\s+([A-Z]\w+)\s*\(",
        content,
    ):
        line = content[:m.start()].count("\n") + 1
        props_match = re.search(r"\{([^}]*)\}", content[m.start():m.start() + 300])
        props = [p.strip().split(":")[0].strip() for p in props_match.group(1).split(",") if p.strip()] if props_match else []
        patterns.append(DetectedPattern(
            pattern_type="component",
            name=m.group(1),
            line=line,
            details={"style": "function", "props": props},
        ))

    # Arrow function components: const MyComponent = (
    # or const MyComponent: React.FC = (
    for m in re.finditer(
        r"(?:export\s+)?const\s+([A-Z]\w+)\s*(?::\s*\w+(?:\.\w+)?(?:<[^>]*>)?\s*)?=\s*(?:\([^)]*\)|[a-z]\w*)\s*(?:=>|:\s*\w)",
        content,
    ):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="component",
            name=m.group(1),
            line=line,
            details={"style": "arrow"},
        ))

    return patterns


def detect_hooks(content: str) -> list[DetectedPattern]:
    """Detect React hook usage."""
    patterns = []

    hook_map = {
        "useState": {"ios_equiv": "@State", "difficulty": "auto"},
        "useEffect": {"ios_equiv": ".task / .onAppear / .onChange", "difficulty": "assisted"},
        "useContext": {"ios_equiv": "@Environment", "difficulty": "auto"},
        "useReducer": {"ios_equiv": "@Observable ViewModel", "difficulty": "assisted"},
        "useMemo": {"ios_equiv": "computed property", "difficulty": "auto"},
        "useCallback": {"ios_equiv": "not needed (SwiftUI handles)", "difficulty": "auto"},
        "useRef": {"ios_equiv": "@State (non-rendering) or FocusState", "difficulty": "assisted"},
        "useNavigate": {"ios_equiv": "NavigationPath / @Environment(\\.dismiss)", "difficulty": "assisted"},
        "useParams": {"ios_equiv": "View initializer parameters", "difficulty": "auto"},
        "useSearchParams": {"ios_equiv": "View initializer parameters", "difficulty": "assisted"},
        "useRouter": {"ios_equiv": "NavigationPath", "difficulty": "assisted"},
    }

    for hook_name, info in hook_map.items():
        for m in re.finditer(rf"\b{hook_name}\s*(?:<[^>]*>)?\s*\(", content):
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="hook",
                name=hook_name,
                line=line,
                details={"ios_equivalent": info["ios_equiv"]},
                conversion_difficulty=info["difficulty"],
            ))

    # Custom hooks: function useXxx( or const useXxx =
    for m in re.finditer(r"(?:function|const)\s+(use[A-Z]\w+)", content):
        name = m.group(1)
        if name not in hook_map:
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="custom_hook",
                name=name,
                line=line,
                details={"ios_equivalent": "@Observable ViewModel"},
                conversion_difficulty="assisted",
            ))

    return patterns


def detect_state_management(content: str) -> list[DetectedPattern]:
    """Detect state management patterns (Redux, Zustand, Jotai, Context, etc.)."""
    patterns = []

    state_libs = {
        "createStore": ("zustand", "assisted"),
        "createSlice": ("redux-toolkit", "assisted"),
        "configureStore": ("redux-toolkit", "assisted"),
        "useSelector": ("redux", "assisted"),
        "useDispatch": ("redux", "assisted"),
        "atom": ("jotai/recoil", "assisted"),
        "useAtom": ("jotai", "assisted"),
        "createContext": ("react-context", "auto"),
    }

    for func_name, (lib, difficulty) in state_libs.items():
        for m in re.finditer(rf"\b{func_name}\s*[<(]", content):
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="state_management",
                name=func_name,
                line=line,
                details={"library": lib, "ios_equivalent": "@Observable / @Environment"},
                conversion_difficulty=difficulty,
            ))

    return patterns


def detect_api_calls(content: str) -> list[DetectedPattern]:
    """Detect API/network calls."""
    patterns = []

    # fetch() calls
    for m in re.finditer(r"\bfetch\s*\(\s*[`'\"]([^`'\"]*)[`'\"]", content):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="api_call",
            name="fetch",
            line=line,
            details={"url": m.group(1), "ios_equivalent": "URLSession.shared.data(from:)"},
            conversion_difficulty="auto",
        ))

    # axios calls
    for m in re.finditer(r"\baxios\.(get|post|put|patch|delete)\s*\(\s*[`'\"]([^`'\"]*)[`'\"]", content):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="api_call",
            name=f"axios.{m.group(1)}",
            line=line,
            details={"method": m.group(1), "url": m.group(2), "ios_equivalent": "APIClient"},
            conversion_difficulty="auto",
        ))

    # Generic API service patterns
    for m in re.finditer(r"(?:api|client|service)\.(get|post|put|patch|delete)\s*[<(]", content, re.IGNORECASE):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="api_call",
            name=f"service.{m.group(1)}",
            line=line,
            details={"method": m.group(1), "ios_equivalent": "APIClient"},
            conversion_difficulty="auto",
        ))

    return patterns


def detect_routing(content: str) -> list[DetectedPattern]:
    """Detect routing patterns."""
    patterns = []

    # React Router / Next.js patterns
    route_patterns = [
        (r"<Route\s+path=['\"]([^'\"]+)['\"]", "react-router"),
        (r"<Link\s+(?:to|href)=['\"]([^'\"]+)['\"]", "link"),
        (r"router\.push\(['\"]([^'\"]+)['\"]", "programmatic-nav"),
        (r"useNavigate\(\)", "navigate-hook"),
    ]

    for pattern, route_type in route_patterns:
        for m in re.finditer(pattern, content):
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="routing",
                name=route_type,
                line=line,
                details={
                    "path": m.group(1) if m.lastindex else "",
                    "ios_equivalent": "NavigationStack / NavigationLink",
                },
                conversion_difficulty="assisted",
            ))

    return patterns


def detect_styles(content: str) -> list[DetectedPattern]:
    """Detect styling approaches."""
    patterns = []

    # Tailwind classes
    tailwind_matches = re.findall(r'className=["\']([^"\']+)["\']', content)
    if tailwind_matches:
        # Count unique Tailwind utilities used
        all_classes = set()
        for match in tailwind_matches:
            all_classes.update(match.split())
        patterns.append(DetectedPattern(
            pattern_type="styling",
            name="tailwind",
            line=1,
            details={
                "class_count": len(all_classes),
                "ios_equivalent": "SwiftUI modifiers",
                "sample_classes": sorted(list(all_classes))[:10],
            },
            conversion_difficulty="assisted",
        ))

    # CSS Modules
    if re.search(r"import\s+\w+\s+from\s+['\"].+\.module\.css['\"]", content):
        patterns.append(DetectedPattern(
            pattern_type="styling",
            name="css-modules",
            line=1,
            details={"ios_equivalent": "SwiftUI modifiers / custom ViewModifiers"},
            conversion_difficulty="assisted",
        ))

    # Styled-components
    if re.search(r"styled\.\w+|styled\(", content):
        patterns.append(DetectedPattern(
            pattern_type="styling",
            name="styled-components",
            line=1,
            details={"ios_equivalent": "SwiftUI modifiers / custom ViewModifiers"},
            conversion_difficulty="assisted",
        ))

    return patterns


def detect_types(content: str) -> list[DetectedPattern]:
    """Detect TypeScript type/interface definitions."""
    patterns = []

    # Interfaces
    for m in re.finditer(r"(?:export\s+)?interface\s+(\w+)", content):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="type_definition",
            name=m.group(1),
            line=line,
            details={"kind": "interface", "ios_equivalent": "struct: Codable"},
            conversion_difficulty="auto",
        ))

    # Type aliases
    for m in re.finditer(r"(?:export\s+)?type\s+(\w+)\s*=", content):
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="type_definition",
            name=m.group(1),
            line=line,
            details={"kind": "type_alias", "ios_equivalent": "typealias or enum"},
            conversion_difficulty="auto",
        ))

    return patterns


def detect_env_usage(content: str) -> list[DetectedPattern]:
    """Detect environment variable usage."""
    patterns = []

    for m in re.finditer(r"process\.env\.(\w+)|import\.meta\.env\.(\w+)", content):
        var_name = m.group(1) or m.group(2)
        line = content[:m.start()].count("\n") + 1
        patterns.append(DetectedPattern(
            pattern_type="env_variable",
            name=var_name,
            line=line,
            details={"ios_equivalent": "xcconfig / Info.plist / Bundle.main"},
            conversion_difficulty="auto",
        ))

    return patterns


def detect_storage(content: str) -> list[DetectedPattern]:
    """Detect browser storage patterns."""
    patterns = []

    storage_map = {
        r"localStorage\.(get|set|remove)Item": ("localStorage", "UserDefaults or Keychain"),
        r"sessionStorage\.(get|set|remove)Item": ("sessionStorage", "in-memory / @State"),
        r"document\.cookie": ("cookies", "HTTPCookieStorage"),
    }

    for pattern, (name, ios_equiv) in storage_map.items():
        for m in re.finditer(pattern, content):
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="storage",
                name=name,
                line=line,
                details={"ios_equivalent": ios_equiv},
                conversion_difficulty="auto",
            ))

    return patterns


def detect_web_apis(content: str) -> list[DetectedPattern]:
    """Detect browser-specific Web APIs that need native equivalents."""
    patterns = []

    web_apis = {
        r"navigator\.geolocation": ("Geolocation", "CoreLocation", "assisted"),
        r"navigator\.mediaDevices": ("MediaDevices", "AVFoundation", "assisted"),
        r"navigator\.share": ("Web Share", "UIActivityViewController", "auto"),
        r"navigator\.clipboard": ("Clipboard", "UIPasteboard", "auto"),
        r"new\s+WebSocket": ("WebSocket", "URLSessionWebSocketTask", "assisted"),
        r"new\s+IntersectionObserver": ("IntersectionObserver", "onAppear / GeometryReader", "assisted"),
        r"requestAnimationFrame": ("rAF", "withAnimation / CADisplayLink", "assisted"),
        r"window\.addEventListener": ("DOM Events", "NotificationCenter / SwiftUI events", "assisted"),
        r"document\.(querySelector|getElementById)": ("DOM Access", "Not applicable (declarative UI)", "manual"),
        r"new\s+Notification|Notification\.requestPermission": ("Web Notifications", "UNUserNotificationCenter", "assisted"),
    }

    for pattern, (name, ios_equiv, difficulty) in web_apis.items():
        for m in re.finditer(pattern, content):
            line = content[:m.start()].count("\n") + 1
            patterns.append(DetectedPattern(
                pattern_type="web_api",
                name=name,
                line=line,
                details={"ios_equivalent": ios_equiv},
                conversion_difficulty=difficulty,
            ))

    return patterns


# ---------------------------------------------------------------------------
# Import / Export detection
# ---------------------------------------------------------------------------

def detect_imports(content: str) -> list[str]:
    """Extract import sources."""
    imports = []
    for m in re.finditer(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", content):
        imports.append(m.group(1))
    for m in re.finditer(r"require\(['\"]([^'\"]+)['\"]\)", content):
        imports.append(m.group(1))
    return imports


def detect_exports(content: str) -> list[str]:
    """Extract export names."""
    exports = []
    for m in re.finditer(r"export\s+(?:default\s+)?(?:function|const|class|interface|type|enum)\s+(\w+)", content):
        exports.append(m.group(1))
    for m in re.finditer(r"export\s+default\s+(\w+)", content):
        exports.append(m.group(1))
    return list(set(exports))


# ---------------------------------------------------------------------------
# File type classification
# ---------------------------------------------------------------------------

def classify_file(relative_path: str, content: str, patterns: list[DetectedPattern]) -> str:
    """Classify the file type based on path, content, and detected patterns."""
    path_lower = relative_path.lower()

    # Path-based classification
    if any(seg in path_lower for seg in ["route", "page", "app/", "pages/"]):
        if any(p.pattern_type == "component" for p in patterns):
            return "route"
    if any(seg in path_lower for seg in ["/hooks/", "/hook/"]):
        return "hook"
    if any(seg in path_lower for seg in ["/service", "/api/", "/client"]):
        return "service"
    if any(seg in path_lower for seg in ["/type", "/interface", "/model", ".d.ts"]):
        return "type"
    if any(seg in path_lower for seg in ["/config", ".config.", "/constants"]):
        return "config"
    if any(seg in path_lower for seg in ["/util", "/helper", "/lib/"]):
        return "utility"
    if any(seg in path_lower for seg in ["/component", "/ui/"]):
        if any(p.pattern_type == "component" for p in patterns):
            return "component"

    # Content-based classification
    component_count = sum(1 for p in patterns if p.pattern_type == "component")
    hook_count = sum(1 for p in patterns if p.pattern_type in ("hook", "custom_hook"))
    api_count = sum(1 for p in patterns if p.pattern_type == "api_call")
    type_count = sum(1 for p in patterns if p.pattern_type == "type_definition")

    if component_count > 0 and hook_count == 0 and api_count == 0:
        return "component"
    if component_count > 0:
        return "component"
    if hook_count > 0:
        return "hook"
    if api_count > 0:
        return "service"
    if type_count > 0 and component_count == 0:
        return "type"

    return "unknown"


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

ALL_DETECTORS = [
    detect_components,
    detect_hooks,
    detect_state_management,
    detect_api_calls,
    detect_routing,
    detect_styles,
    detect_types,
    detect_env_usage,
    detect_storage,
    detect_web_apis,
]


def analyze_file(relative_path: str, content: str) -> FileAnalysis:
    """Run all pattern detectors on a single file."""
    all_patterns = []
    for detector in ALL_DETECTORS:
        all_patterns.extend(detector(content))

    file_type = classify_file(relative_path, content, all_patterns)
    imports = detect_imports(content)
    exports = detect_exports(content)

    return FileAnalysis(
        relative_path=relative_path,
        extension=relative_path.rsplit(".", 1)[-1] if "." in relative_path else "",
        file_type=file_type,
        patterns=all_patterns,
        imports=imports,
        exports=exports,
    )
