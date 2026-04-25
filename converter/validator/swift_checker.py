"""
Swift Output Validator — Post-Phase 4 validation.

Checks generated Swift code for issues at multiple levels:
1. Static analysis — pattern-based checks (always available)
2. Syntax check — via `swiftc -parse` (if Swift toolchain is available)
3. Cross-file references — checks that referenced types/views exist
4. Confidence scoring — per-file quality assessment

This addresses GAP-T1: the converter previously reported success based on
whether Python ran without exceptions, not whether the generated Swift was valid.
"""

import re
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationIssue:
    """A single validation issue found in generated code."""
    severity: str       # "error", "warning", "info"
    category: str       # "syntax", "type", "reference", "pattern", "style"
    message: str
    line: int = 0
    file: str = ""


@dataclass
class ValidationResult:
    """Validation result for a single Swift file."""
    file_path: str
    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    confidence_score: float = 1.0
    confidence_breakdown: dict = field(default_factory=dict)
    swift_syntax_checked: bool = False  # True if swiftc was used


@dataclass
class ProjectValidationResult:
    """Validation result for the entire generated project."""
    files: list[ValidationResult] = field(default_factory=list)
    overall_confidence: float = 0.0
    swift_available: bool = False
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Static analysis checks (always available — no Swift toolchain needed)
# ---------------------------------------------------------------------------

def _check_todo_comments(content: str, file_path: str) -> list[ValidationIssue]:
    """Count TODO comments — each indicates incomplete conversion."""
    issues = []
    for i, line in enumerate(content.split("\n"), 1):
        if "// TODO:" in line:
            msg = line.strip().replace("// TODO: ", "")
            issues.append(ValidationIssue(
                severity="warning",
                category="pattern",
                message=f"Incomplete conversion: {msg}",
                line=i,
                file=file_path,
            ))
    return issues


def _check_empty_views(content: str, file_path: str) -> list[ValidationIssue]:
    """Find EmptyView() fallbacks — indicate elements that couldn't be converted."""
    issues = []
    for i, line in enumerate(content.split("\n"), 1):
        if "EmptyView()" in line:
            issues.append(ValidationIssue(
                severity="warning",
                category="pattern",
                message="EmptyView() fallback — element could not be converted",
                line=i,
                file=file_path,
            ))
    return issues


def _check_any_types(content: str, file_path: str) -> list[ValidationIssue]:
    """Find 'Any' type fallbacks — indicate types that couldn't be resolved."""
    issues = []
    # Match ': Any' or ': [String: Any]' but not 'AnyView' or 'AnyObject'
    for i, line in enumerate(content.split("\n"), 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Match standalone Any type usage
        if re.search(r":\s*Any\b(?!View|Object|Hashable|Identifiable|Codable|Sequence|Collection)", line):
            issues.append(ValidationIssue(
                severity="info",
                category="type",
                message="Type resolved to 'Any' — consider using a specific type",
                line=i,
                file=file_path,
            ))
    return issues


def _check_syntax_patterns(content: str, file_path: str) -> list[ValidationIssue]:
    """Check for common Swift syntax issues in generated code."""
    issues = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue

        # JavaScript/TypeScript leaks
        if re.search(r"\bconst\s+\w+\s*=", stripped):
            issues.append(ValidationIssue(
                severity="error",
                category="syntax",
                message="JavaScript 'const' leaked into Swift output",
                line=i,
                file=file_path,
            ))

        if re.search(r"\bfunction\s+\w+\s*\(", stripped) and "// " not in stripped:
            issues.append(ValidationIssue(
                severity="error",
                category="syntax",
                message="JavaScript 'function' keyword leaked into Swift output",
                line=i,
                file=file_path,
            ))

        if "=>" in stripped and "// " not in stripped and '"""' not in stripped:
            # Arrow functions — but skip string literals and comments
            if not re.search(r'["\'].*=>.*["\']', stripped):
                issues.append(ValidationIssue(
                    severity="error",
                    category="syntax",
                    message="JavaScript arrow function '=>' leaked into Swift output",
                    line=i,
                    file=file_path,
                ))

        if re.search(r"\breturn\s*\(?\s*<\w+", stripped):
            issues.append(ValidationIssue(
                severity="error",
                category="syntax",
                message="JSX return statement leaked into Swift output",
                line=i,
                file=file_path,
            ))

        # Unbalanced braces (simple check)
        if stripped == "}" and i < len(lines):
            # Check for orphan closing brace not matching scope
            pass

        # Invalid Swift patterns
        if "undefined" in stripped and "// " not in stripped:
            issues.append(ValidationIssue(
                severity="warning",
                category="syntax",
                message="JavaScript 'undefined' in Swift code — use 'nil'",
                line=i,
                file=file_path,
            ))

        if "null" in stripped and "nil" not in stripped and "// " not in stripped:
            if not re.search(r'["\'].*null.*["\']', stripped):
                issues.append(ValidationIssue(
                    severity="warning",
                    category="syntax",
                    message="JavaScript 'null' in Swift code — use 'nil'",
                    line=i,
                    file=file_path,
                ))

    return issues


def _check_missing_imports(content: str, file_path: str) -> list[ValidationIssue]:
    """Check for common missing import statements."""
    issues = []

    # Map of symbols to required imports
    symbol_imports = {
        "NavigationStack": "SwiftUI",
        "NavigationLink": "SwiftUI",
        "AsyncImage": "SwiftUI",
        "@State": "SwiftUI",
        "@Observable": "Observation",
        "@Environment": "SwiftUI",
        "URLSession": "Foundation",
        "JSONDecoder": "Foundation",
        "JSONEncoder": "Foundation",
        "UserDefaults": "Foundation",
        "DateFormatter": "Foundation",
        "VideoPlayer": "AVKit",
        "AVPlayer": "AVKit",
        "CLLocationManager": "CoreLocation",
        "MKMapView": "MapKit",
        "UNUserNotificationCenter": "UserNotifications",
    }

    # Extract existing imports
    existing_imports = set(re.findall(r"import\s+(\w+)", content))

    for symbol, required_import in symbol_imports.items():
        if symbol in content and required_import not in existing_imports:
            issues.append(ValidationIssue(
                severity="warning",
                category="reference",
                message=f"'{symbol}' used but 'import {required_import}' may be missing",
                line=0,
                file=file_path,
            ))

    return issues


def _check_cross_references(content: str, file_path: str, all_types: set[str]) -> list[ValidationIssue]:
    """Check that referenced custom types exist in the project."""
    issues = []

    # Find type references in the file (: TypeName, <TypeName>, TypeName())
    type_refs = set(re.findall(r"(?::\s*|<|\.init\()([A-Z]\w+)(?:\?|\)|\]|,|\s|>|$)", content))

    # Standard Swift/SwiftUI types that don't need to be in our project
    swift_builtins = {
        "String", "Int", "Double", "Float", "Bool", "Date", "Data",
        "Any", "Void", "Never", "Optional", "Array", "Dictionary", "Set",
        "Error", "Codable", "Identifiable", "Hashable", "Equatable",
        "View", "AnyView", "EmptyView", "Text", "Image", "Button",
        "VStack", "HStack", "ZStack", "List", "ScrollView", "Form",
        "NavigationStack", "NavigationLink", "NavigationPath",
        "AsyncImage", "ProgressView", "Divider", "Spacer",
        "Color", "Font", "GeometryReader", "Group", "ForEach",
        "Section", "Toggle", "TextField", "TextEditor", "Picker",
        "Slider", "Stepper", "DatePicker", "ColorPicker",
        "Alert", "Sheet", "ToolbarItem", "Menu", "Label",
        "Circle", "Rectangle", "RoundedRectangle", "Capsule",
        "ObservableObject", "Published", "StateObject", "ObservedObject",
        "EnvironmentObject", "EnvironmentValues", "EnvironmentKey",
        "URL", "URLSession", "URLRequest", "URLResponse",
        "JSONDecoder", "JSONEncoder", "UserDefaults", "Bundle",
        "Task", "MainActor", "Sendable",
        "Timer", "NotificationCenter", "Locale", "Calendar", "TimeZone",
        "CGFloat", "CGPoint", "CGSize", "CGRect",
        "LinearGradient", "RadialGradient", "AngularGradient",
        "WindowGroup", "Scene", "App",
    }

    for ref in type_refs:
        if ref not in swift_builtins and ref not in all_types:
            issues.append(ValidationIssue(
                severity="info",
                category="reference",
                message=f"Reference to '{ref}' — verify this type is defined in the project",
                line=0,
                file=file_path,
            ))

    return issues


# ---------------------------------------------------------------------------
# Swift compiler check (optional — requires Swift toolchain)
# ---------------------------------------------------------------------------

def _check_swift_available() -> bool:
    """Check if swiftc is available on the system."""
    return shutil.which("swiftc") is not None


def _run_swiftc_parse(file_path: str) -> list[ValidationIssue]:
    """Run swiftc -parse on a single file to check syntax."""
    issues = []
    try:
        result = subprocess.run(
            ["swiftc", "-parse", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            for line in result.stderr.splitlines():
                if "error:" in line:
                    # Extract line number if available
                    line_match = re.search(r":(\d+):", line)
                    line_num = int(line_match.group(1)) if line_match else 0
                    msg = line.split("error:", 1)[-1].strip()
                    issues.append(ValidationIssue(
                        severity="error",
                        category="syntax",
                        message=f"Swift syntax error: {msg}",
                        line=line_num,
                        file=file_path,
                    ))
                elif "warning:" in line:
                    line_match = re.search(r":(\d+):", line)
                    line_num = int(line_match.group(1)) if line_match else 0
                    msg = line.split("warning:", 1)[-1].strip()
                    issues.append(ValidationIssue(
                        severity="warning",
                        category="syntax",
                        message=f"Swift warning: {msg}",
                        line=line_num,
                        file=file_path,
                    ))
    except subprocess.TimeoutExpired:
        issues.append(ValidationIssue(
            severity="warning",
            category="syntax",
            message="swiftc timed out (file may be too complex)",
            file=file_path,
        ))
    except FileNotFoundError:
        pass  # swiftc not available
    return issues


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _calculate_confidence(content: str, issues: list[ValidationIssue]) -> tuple[float, dict]:
    """
    Calculate a confidence score (0.0 to 1.0) for a generated file.

    Scoring:
    - Start at 1.0
    - Each TODO: -0.03
    - Each EmptyView(): -0.08
    - Each Any type fallback: -0.02
    - Each syntax error: -0.15
    - Each JS leak: -0.20
    - Each warning: -0.01
    """
    score = 1.0
    breakdown = {
        "todo_count": 0,
        "empty_view_count": 0,
        "any_type_count": 0,
        "syntax_error_count": 0,
        "js_leak_count": 0,
        "warning_count": 0,
    }

    for issue in issues:
        if issue.category == "pattern" and "Incomplete conversion" in issue.message:
            breakdown["todo_count"] += 1
            score -= 0.03
        elif issue.category == "pattern" and "EmptyView" in issue.message:
            breakdown["empty_view_count"] += 1
            score -= 0.08
        elif issue.category == "type" and "Any" in issue.message:
            breakdown["any_type_count"] += 1
            score -= 0.02
        elif issue.severity == "error" and "leaked" in issue.message:
            breakdown["js_leak_count"] += 1
            score -= 0.20
        elif issue.severity == "error":
            breakdown["syntax_error_count"] += 1
            score -= 0.15
        elif issue.severity == "warning":
            breakdown["warning_count"] += 1
            score -= 0.01

    # Bonus: if file has actual Swift structure (struct/class/func)
    has_structure = bool(re.search(r"\b(struct|class|enum|func|var|let)\b", content))
    if not has_structure:
        score -= 0.3
        breakdown["no_swift_structure"] = True

    # Clamp to 0-1
    score = max(0.0, min(1.0, score))

    return round(score, 2), breakdown


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_swift_file(
    file_path: str,
    content: str | None = None,
    all_types: set[str] | None = None,
    use_swiftc: bool = True,
) -> ValidationResult:
    """
    Validate a single generated Swift file.

    Args:
        file_path: Path to the Swift file
        content: File content (read from disk if not provided)
        all_types: Set of all known type names in the project (for cross-ref checking)
        use_swiftc: Whether to run swiftc -parse if available

    Returns:
        ValidationResult with issues and confidence score
    """
    if content is None:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except Exception as e:
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                issues=[ValidationIssue(
                    severity="error",
                    category="syntax",
                    message=f"Could not read file: {e}",
                    file=file_path,
                )],
                confidence_score=0.0,
            )

    issues: list[ValidationIssue] = []

    # Static analysis (always runs)
    issues.extend(_check_todo_comments(content, file_path))
    issues.extend(_check_empty_views(content, file_path))
    issues.extend(_check_any_types(content, file_path))
    issues.extend(_check_syntax_patterns(content, file_path))
    issues.extend(_check_missing_imports(content, file_path))

    if all_types:
        issues.extend(_check_cross_references(content, file_path, all_types))

    # Swift compiler check (optional)
    swift_checked = False
    if use_swiftc and _check_swift_available():
        swift_issues = _run_swiftc_parse(file_path)
        issues.extend(swift_issues)
        swift_checked = True

    # Calculate confidence
    confidence, breakdown = _calculate_confidence(content, issues)

    # Determine validity
    has_errors = any(i.severity == "error" for i in issues)

    return ValidationResult(
        file_path=file_path,
        is_valid=not has_errors,
        issues=issues,
        confidence_score=confidence,
        confidence_breakdown=breakdown,
        swift_syntax_checked=swift_checked,
    )


def validate_project(
    output_dir: str,
    use_swiftc: bool = True,
) -> ProjectValidationResult:
    """
    Validate all generated Swift files in a project.

    Args:
        output_dir: Directory containing generated Swift files
        use_swiftc: Whether to run swiftc -parse if available

    Returns:
        ProjectValidationResult with per-file results and summary
    """
    output_path = Path(output_dir)
    swift_files = sorted(output_path.rglob("*.swift"))

    if not swift_files:
        return ProjectValidationResult(
            summary={"error": "No .swift files found in output directory"},
        )

    # Collect all known type names for cross-reference checking
    all_types: set[str] = set()
    file_contents: dict[str, str] = {}

    for sf in swift_files:
        content = sf.read_text(encoding="utf-8")
        file_contents[str(sf)] = content
        # Extract struct/class/enum names
        for m in re.finditer(r"\b(?:struct|class|enum)\s+(\w+)", content):
            all_types.add(m.group(1))

    # Validate each file
    swift_available = _check_swift_available()
    results = []

    for sf in swift_files:
        rel_path = str(sf.relative_to(output_path))
        result = validate_swift_file(
            file_path=str(sf),
            content=file_contents[str(sf)],
            all_types=all_types,
            use_swiftc=use_swiftc,
        )
        result.file_path = rel_path  # Use relative path for readability
        results.append(result)

    # Calculate overall stats
    total_files = len(results)
    valid_files = sum(1 for r in results if r.is_valid)
    total_issues = sum(len(r.issues) for r in results)
    avg_confidence = sum(r.confidence_score for r in results) / total_files if total_files else 0

    error_count = sum(
        sum(1 for i in r.issues if i.severity == "error")
        for r in results
    )
    warning_count = sum(
        sum(1 for i in r.issues if i.severity == "warning")
        for r in results
    )

    return ProjectValidationResult(
        files=results,
        overall_confidence=round(avg_confidence, 2),
        swift_available=swift_available,
        summary={
            "total_files": total_files,
            "valid_files": valid_files,
            "total_issues": total_issues,
            "errors": error_count,
            "warnings": warning_count,
            "average_confidence": round(avg_confidence * 100, 1),
            "swift_syntax_checked": swift_available,
        },
    )


def generate_validation_report(result: ProjectValidationResult) -> str:
    """Generate a markdown validation report."""
    lines = ["# Validation Report\n"]

    s = result.summary
    lines.append("## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Files validated | {s.get('total_files', 0)} |")
    lines.append(f"| Files passing | {s.get('valid_files', 0)} |")
    lines.append(f"| Total issues | {s.get('total_issues', 0)} |")
    lines.append(f"| Errors | {s.get('errors', 0)} |")
    lines.append(f"| Warnings | {s.get('warnings', 0)} |")
    lines.append(f"| Average confidence | {s.get('average_confidence', 0)}% |")
    lines.append(f"| Swift syntax checked | {'Yes' if s.get('swift_syntax_checked') else 'No (swiftc not available)'} |")
    lines.append("")

    # Per-file results table
    lines.append("## Per-File Confidence\n")
    lines.append("| File | Confidence | Status | Issues |")
    lines.append("|---|---|---|---|")

    for file_result in sorted(result.files, key=lambda r: r.confidence_score):
        pct = int(file_result.confidence_score * 100)
        if pct >= 80:
            badge = "HIGH"
        elif pct >= 50:
            badge = "MEDIUM"
        else:
            badge = "LOW"

        error_count = sum(1 for i in file_result.issues if i.severity == "error")
        warn_count = sum(1 for i in file_result.issues if i.severity == "warning")
        issue_str = f"{error_count}E {warn_count}W" if error_count or warn_count else "clean"

        lines.append(f"| `{file_result.file_path}` | {pct}% {badge} | {'PASS' if file_result.is_valid else 'FAIL'} | {issue_str} |")
    lines.append("")

    # Detailed issues for files with errors
    error_files = [r for r in result.files if not r.is_valid]
    if error_files:
        lines.append("## Errors\n")
        for file_result in error_files:
            lines.append(f"### `{file_result.file_path}`\n")
            for issue in file_result.issues:
                if issue.severity == "error":
                    loc = f" (line {issue.line})" if issue.line else ""
                    lines.append(f"- **ERROR**{loc}: {issue.message}")
            lines.append("")

    # Top warnings
    all_warnings = [
        (r.file_path, i)
        for r in result.files
        for i in r.issues
        if i.severity == "warning"
    ]
    if all_warnings:
        lines.append("## Warnings\n")
        # Group by category
        categories = {}
        for file_path, issue in all_warnings:
            cat = issue.category
            categories.setdefault(cat, []).append((file_path, issue))

        for cat, items in sorted(categories.items()):
            lines.append(f"### {cat.title()} ({len(items)})\n")
            for file_path, issue in items[:20]:  # Cap at 20 per category
                loc = f" L{issue.line}" if issue.line else ""
                lines.append(f"- `{file_path}`{loc}: {issue.message}")
            if len(items) > 20:
                lines.append(f"- *... and {len(items) - 20} more*")
            lines.append("")

    return "\n".join(lines)
