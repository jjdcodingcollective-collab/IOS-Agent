"""
Shared Swift code generation helpers.
Utilities for type mapping, naming conventions, and code formatting.
"""

import re
from textwrap import indent, dedent


# ---------------------------------------------------------------------------
# TypeScript -> Swift type mapping
# ---------------------------------------------------------------------------

TS_TO_SWIFT_TYPES = {
    "string": "String",
    "number": "Int",
    "boolean": "Bool",
    "Date": "Date",
    "any": "Any",
    "void": "Void",
    "null": "nil",
    "undefined": "nil",
    "object": "[String: Any]",
    "never": "Never",
    "unknown": "Any",
    "bigint": "Int64",
    "symbol": "String",
    # React-specific types
    "React.ReactNode": "AnyView",
    "ReactNode": "AnyView",
    "React.ReactElement": "AnyView",
    "JSX.Element": "AnyView",
    "React.CSSProperties": "[String: Any]",
    "React.ChangeEvent": "Any",
    "React.FormEvent": "Any",
    "React.MouseEvent": "Any",
    "HTMLButtonElement": "Any",
    "HTMLInputElement": "Any",
    "HTMLFormElement": "Any",
}

# Common complex type patterns
GENERIC_TYPE_MAP = {
    "Array": lambda inner: f"[{map_type(inner)}]",
    "Promise": lambda inner: map_type(inner),  # async handles this
    "Record": lambda inner: f"[{map_type(inner.split(',')[0].strip())}: {map_type(inner.split(',')[1].strip())}]" if "," in inner else f"[String: {map_type(inner)}]",
    "Partial": lambda inner: map_type(inner),  # all fields become optional
    "Omit": lambda inner: map_type(inner.split(",")[0].strip()),
    "Pick": lambda inner: map_type(inner.split(",")[0].strip()),
    "Set": lambda inner: f"Set<{map_type(inner)}>",
    "Map": lambda inner: f"[{map_type(inner.split(',')[0].strip())}: {map_type(inner.split(',')[1].strip())}]" if "," in inner else f"[String: {map_type(inner)}]",
}


def map_type(ts_type: str) -> str:
    """Convert a TypeScript type string to Swift."""
    ts_type = ts_type.strip()

    if not ts_type:
        return "Any"

    # Handle optionals: type | null, type | undefined
    if " | null" in ts_type or " | undefined" in ts_type:
        base = ts_type.replace(" | null", "").replace(" | undefined", "").strip()
        return f"{map_type(base)}?"

    # Handle union of string literals: "a" | "b" | "c" -> String (enum generated separately)
    if re.match(r'^"[^"]*"(\s*\|\s*"[^"]*")+$', ts_type):
        return "String"  # Will be handled as enum by type_converter

    # Handle array shorthand: type[]
    if ts_type.endswith("[]"):
        inner = ts_type[:-2]
        return f"[{map_type(inner)}]"

    # Handle generics: Type<Inner>
    generic_match = re.match(r"(\w+)<(.+)>$", ts_type)
    if generic_match:
        outer = generic_match.group(1)
        inner = generic_match.group(2)
        if outer in GENERIC_TYPE_MAP:
            return GENERIC_TYPE_MAP[outer](inner)
        return f"{outer}<{map_type(inner)}>"

    # Handle simple types
    if ts_type in TS_TO_SWIFT_TYPES:
        return TS_TO_SWIFT_TYPES[ts_type]

    # Handle number subtypes
    if ts_type in ("float", "double", "Float", "Double"):
        return "Double"

    # Pass through PascalCase types (likely custom types)
    if ts_type[0].isupper():
        return ts_type

    return "Any"


# ---------------------------------------------------------------------------
# Naming conventions
# ---------------------------------------------------------------------------

def to_pascal_case(name: str) -> str:
    """Convert any name to PascalCase."""
    if "-" in name or "_" in name:
        parts = re.split(r"[-_]", name)
        return "".join(p.capitalize() for p in parts if p)
    if name and name[0].islower():
        return name[0].upper() + name[1:]
    return name


def to_camel_case(name: str) -> str:
    """Convert any name to camelCase."""
    pascal = to_pascal_case(name)
    if pascal:
        return pascal[0].lower() + pascal[1:]
    return name


def swift_filename(name: str, file_type: str) -> str:
    """Generate a Swift filename from a component/type name."""
    base = to_pascal_case(name)
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
    if suffix and not base.endswith(suffix):
        base = f"{base}{suffix}"
    return f"{base}.swift"


# ---------------------------------------------------------------------------
# Code formatting
# ---------------------------------------------------------------------------

def swift_indent(code: str, level: int = 1) -> str:
    """Indent Swift code by N levels (4 spaces each)."""
    return indent(code, "    " * level)


def swift_comment(text: str) -> str:
    """Create a Swift line comment."""
    return f"// {text}"


def swift_mark(section: str) -> str:
    """Create a MARK comment (Xcode section divider)."""
    return f"// MARK: - {section}"


def swift_todo(text: str) -> str:
    """Create a TODO comment that Xcode will highlight."""
    return f"// TODO: {text}"


def swift_header(filename: str, module: str = "MyApp") -> str:
    """Generate a Swift file header."""
    return f"""//
//  {filename}
//  {module}
//
//  Auto-generated by iOS Code Converter
//  Review all TODO comments before using in production
//
"""


def format_swift(code: str) -> str:
    """Basic Swift code formatting — normalize whitespace and blank lines."""
    lines = code.split("\n")
    result = []
    prev_blank = False

    for line in lines:
        is_blank = not line.strip()
        # Collapse multiple blank lines to one
        if is_blank and prev_blank:
            continue
        result.append(line.rstrip())
        prev_blank = is_blank

    # Remove trailing blank lines
    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result) + "\n"
