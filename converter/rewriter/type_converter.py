"""
Type Converter — Converts TypeScript interfaces/types to Swift Codable structs.
This is the foundation layer — models are converted first since everything else depends on them.
"""

import re
from .swift_helpers import (
    map_type, to_pascal_case, swift_header, swift_mark, swift_todo, format_swift,
)


def convert_types_file(source: str, relative_path: str) -> str:
    """
    Convert a TypeScript file containing interfaces/types to Swift structs.
    Returns the generated Swift code.
    """
    blocks = []
    filename = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    swift_name = to_pascal_case(filename) + ".swift"

    blocks.append(swift_header(swift_name))
    blocks.append("import Foundation\n")

    # Extract and convert interfaces
    interfaces = extract_interfaces(source)
    for iface in interfaces:
        blocks.append(convert_interface(iface))

    # Extract and convert type aliases
    type_aliases = extract_type_aliases(source)
    for alias in type_aliases:
        blocks.append(convert_type_alias(alias))

    # Extract and convert string literal union types as enums
    enums = extract_string_enums(source)
    for enum in enums:
        blocks.append(convert_string_enum(enum))

    if not interfaces and not type_aliases and not enums:
        blocks.append(swift_todo("No types detected — verify source file manually"))

    return format_swift("\n".join(blocks))


# ---------------------------------------------------------------------------
# Interface extraction and conversion
# ---------------------------------------------------------------------------

def extract_interfaces(source: str) -> list[dict]:
    """Extract TypeScript interface definitions."""
    interfaces = []
    # Match interface Name { ... }
    pattern = r"(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
    for m in re.finditer(pattern, source, re.DOTALL):
        name = m.group(1)
        extends = [e.strip() for e in m.group(2).split(",")] if m.group(2) else []
        body = m.group(3)
        fields = parse_interface_fields(body)
        interfaces.append({"name": name, "extends": extends, "fields": fields})
    return interfaces


def parse_interface_fields(body: str) -> list[dict]:
    """Parse fields from an interface body."""
    fields = []
    # Handle nested objects by tracking brace depth
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("//"):
            i += 1
            continue

        # Match: fieldName: type; or fieldName?: type;
        field_match = re.match(
            r"(\w+)(\?)?:\s*(.+?)\s*;?\s*$", line
        )
        if field_match:
            fname = field_match.group(1)
            optional = field_match.group(2) == "?"
            ftype = field_match.group(3).rstrip(";").strip()

            # Check if type is an inline object
            if ftype == "{" or ftype.endswith("{"):
                # Collect nested object
                depth = ftype.count("{") - ftype.count("}")
                nested_lines = [ftype]
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    nested_lines.append(lines[i].strip())
                    depth += lines[i].count("{") - lines[i].count("}")
                ftype = " ".join(nested_lines)

            fields.append({
                "name": fname,
                "type": ftype,
                "optional": optional,
            })
        i += 1
    return fields


def convert_interface(iface: dict) -> str:
    """Convert a parsed interface to a Swift struct."""
    name = to_pascal_case(iface["name"])
    lines = []

    # Determine conformances
    conformances = ["Codable"]
    if any(f["name"] == "id" for f in iface["fields"]):
        conformances.append("Identifiable")
    if iface["extends"]:
        conformances.extend(to_pascal_case(e) for e in iface["extends"])

    conformance_str = ", ".join(conformances)
    lines.append(f"struct {name}: {conformance_str} {{")

    for field in iface["fields"]:
        swift_field = convert_field(field)
        lines.append(f"    {swift_field}")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def convert_field(field: dict) -> str:
    """Convert a single interface field to a Swift property."""
    name = field["name"]
    ts_type = field["type"]
    optional = field["optional"]

    # Handle inline object types
    if "{" in ts_type:
        # Extract inline fields
        inner = re.search(r"\{(.+)\}", ts_type, re.DOTALL)
        if inner:
            swift_type = to_pascal_case(name)  # Will need a nested struct
            return f"{swift_todo(f'Define nested struct {swift_type} for inline object')}\n    let {name}: {swift_type}{'?' if optional else ''}"

    swift_type = map_type(ts_type)

    if optional and not swift_type.endswith("?"):
        swift_type = f"{swift_type}?"

    keyword = "var" if optional else "let"
    return f"{keyword} {name}: {swift_type}"


# ---------------------------------------------------------------------------
# Type alias extraction and conversion
# ---------------------------------------------------------------------------

def extract_type_aliases(source: str) -> list[dict]:
    """Extract TypeScript type aliases (non-string-literal ones)."""
    aliases = []
    pattern = r"(?:export\s+)?type\s+(\w+)\s*=\s*(.+?)(?:;|\n)"
    for m in re.finditer(pattern, source):
        name = m.group(1)
        value = m.group(2).strip().rstrip(";")
        # Skip string literal unions (handled separately)
        if re.match(r'^"[^"]*"(\s*\|\s*"[^"]*")*$', value):
            continue
        # Skip if it's just extending another type with &
        aliases.append({"name": name, "value": value})
    return aliases


def convert_type_alias(alias: dict) -> str:
    """Convert a type alias to Swift."""
    name = to_pascal_case(alias["name"])
    value = alias["value"]

    # Intersection types (A & B) -> protocol composition or struct
    if "&" in value:
        parts = [map_type(p.strip()) for p in value.split("&")]
        return f"{swift_todo(f'Intersection type — consider combining into a single struct')}\ntypealias {name} = {parts[0]}\n"

    swift_type = map_type(value)
    return f"typealias {name} = {swift_type}\n"


# ---------------------------------------------------------------------------
# String enum extraction and conversion
# ---------------------------------------------------------------------------

def extract_string_enums(source: str) -> list[dict]:
    """Extract TypeScript string literal union types."""
    enums = []
    pattern = r"(?:export\s+)?type\s+(\w+)\s*=\s*(\"[^\"]*\"(?:\s*\|\s*\"[^\"]*\")+)\s*;?"
    for m in re.finditer(pattern, source):
        name = m.group(1)
        values_str = m.group(2)
        values = [v.strip().strip('"') for v in values_str.split("|")]
        enums.append({"name": name, "values": values})
    return enums


def convert_string_enum(enum: dict) -> str:
    """Convert a string literal union to a Swift enum."""
    name = to_pascal_case(enum["name"])
    lines = [f"enum {name}: String, Codable {{"]
    for val in enum["values"]:
        case_name = val.replace("-", "_").replace(" ", "_")
        if case_name != val:
            lines.append(f'    case {case_name} = "{val}"')
        else:
            lines.append(f"    case {case_name}")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)
