"""
Rewriter Engine — Orchestrates all converters.
Routes each file to the appropriate converter based on its file_type
from the analysis manifest, then assembles the output.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field

from .swift_helpers import format_swift, swift_header, swift_todo
from .type_converter import convert_types_file
from .service_converter import convert_service_file, generate_api_client_scaffold
from .hook_converter import convert_hook_file
from .component_converter import convert_component_file


@dataclass
class RewriteResult:
    """Result of rewriting a single file."""
    source_path: str
    output_path: str
    swift_code: str
    file_type: str
    success: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass
class ProjectRewriteResult:
    """Result of rewriting an entire project."""
    files: list[RewriteResult] = field(default_factory=list)
    scaffold_files: dict[str, str] = field(default_factory=dict)


# iOS project directory mapping
FILE_TYPE_TO_DIR = {
    "type": "Models",
    "service": "Services",
    "hook": "ViewModels",
    "component": "Views",
    "route": "Views",
    "config": "Configuration",
    "utility": "Extensions",
    "unknown": "Misc",
}


def rewrite_project(
    manifest: dict,
    source_files: dict[str, str],
    output_dir: str,
) -> ProjectRewriteResult:
    """
    Rewrite an entire project from TypeScript to Swift.

    Args:
        manifest: The analysis manifest (from Phase 1)
        source_files: Dict mapping relative_path -> file content
        output_dir: Directory to write Swift files to

    Returns:
        ProjectRewriteResult with all generated files
    """
    result = ProjectRewriteResult()
    output_path = Path(output_dir)

    # Always generate the APIClient scaffold
    api_client_code = generate_api_client_scaffold()
    scaffold_path = "Services/APIClient.swift"
    result.scaffold_files[scaffold_path] = api_client_code
    _write_file(output_path / scaffold_path, api_client_code)

    # Process each file from the manifest
    for file_entry in manifest.get("files", []):
        rel_path = file_entry["relative_path"]
        file_type = file_entry["file_type"]
        source = source_files.get(rel_path, "")

        if not source:
            continue

        # Skip files with no detected patterns
        if not file_entry.get("patterns"):
            continue

        # Route to the appropriate converter
        try:
            rewrite = convert_file(source, rel_path, file_type, file_entry)
            result.files.append(rewrite)

            # Write the output file
            _write_file(output_path / rewrite.output_path, rewrite.swift_code)

        except Exception as e:
            result.files.append(RewriteResult(
                source_path=rel_path,
                output_path=f"Misc/{Path(rel_path).stem}.swift",
                swift_code=f"// ERROR: Failed to convert {rel_path}\n// {str(e)}\n",
                file_type=file_type,
                success=False,
                notes=[f"Conversion failed: {str(e)}"],
            ))

    return result


def convert_file(
    source: str,
    relative_path: str,
    file_type: str,
    manifest_entry: dict,
) -> RewriteResult:
    """Route a file to the correct converter and return the result."""

    ios_dir = FILE_TYPE_TO_DIR.get(file_type, "Misc")
    filename = Path(relative_path).stem
    notes = []

    if file_type == "type":
        swift_code = convert_types_file(source, relative_path)
        swift_filename = f"{_pascal(filename)}.swift"

    elif file_type == "service":
        swift_code = convert_service_file(source, relative_path, manifest_entry)
        name = _pascal(filename)
        if not name.endswith("Service"):
            name += "Service"
        swift_filename = f"{name}.swift"

    elif file_type in ("hook",):
        swift_code = convert_hook_file(source, relative_path, manifest_entry)
        # Derive ViewModel name
        name = filename.replace("use", "").replace("Use", "")
        name = _pascal(name) + "ViewModel"
        swift_filename = f"{name}.swift"

    elif file_type in ("component", "route"):
        swift_code = convert_component_file(source, relative_path, manifest_entry)
        name = _pascal(filename)
        if not name.endswith("View"):
            name += "View"
        swift_filename = f"{name}.swift"

    elif file_type == "utility":
        swift_code = convert_utility_file(source, relative_path)
        swift_filename = f"{_pascal(filename)}+Extensions.swift"

    elif file_type == "config":
        swift_code = convert_config_file(source, relative_path)
        swift_filename = f"{_pascal(filename)}Config.swift"

    else:
        swift_code = generate_fallback(source, relative_path, manifest_entry)
        swift_filename = f"{_pascal(filename)}.swift"
        notes.append("Unrecognized file type — generated stub with TODOs")

    output_path = f"{ios_dir}/{swift_filename}"

    return RewriteResult(
        source_path=relative_path,
        output_path=output_path,
        swift_code=swift_code,
        file_type=file_type,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Utility and config converters (simpler, inline here)
# ---------------------------------------------------------------------------

def convert_utility_file(source: str, relative_path: str) -> str:
    """Convert utility functions to Swift extensions."""
    filename = Path(relative_path).stem
    name = _pascal(filename)
    lines = []
    lines.append(swift_header(f"{name}+Extensions.swift"))
    lines.append("import Foundation\n")

    # Extract exported functions
    func_pattern = r"(?:export\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?\s*\{"
    for m in __import__("re").finditer(func_pattern, source):
        fname = m.group(1)
        params = m.group(2)
        ret_type = m.group(3)

        swift_ret = f" -> {_map_simple_type(ret_type)}" if ret_type else ""
        lines.append(f"{swift_todo(f'Port utility function: {fname}')}")
        lines.append(f"func {fname}({_convert_params(params)}){swift_ret} {{")
        lines.append(f"    {swift_todo('Implement')}")
        if ret_type == "string":
            lines.append('    return ""')
        elif ret_type == "boolean":
            lines.append("    return false")
        elif ret_type == "number":
            lines.append("    return 0")
        lines.append("}")
        lines.append("")

    return format_swift("\n".join(lines))


def convert_config_file(source: str, relative_path: str) -> str:
    """Convert config files to Swift constants."""
    filename = Path(relative_path).stem
    name = _pascal(filename)
    lines = []
    lines.append(swift_header(f"{name}Config.swift"))
    lines.append("import Foundation\n")
    lines.append(f"enum {name}Config {{")

    # Extract exported constants
    const_pattern = r"(?:export\s+)?const\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(.+?)(?:;|\n)"
    for m in __import__("re").finditer(const_pattern, source):
        cname = m.group(1)
        value = m.group(2).strip().rstrip(";")
        if value.startswith('"') or value.startswith("'"):
            clean_val = value.strip("\"'")
            lines.append(f'    static let {cname} = "{clean_val}"')
        elif value in ("true", "false"):
            lines.append(f"    static let {cname} = {value}")
        elif value.replace(".", "").isdigit():
            lines.append(f"    static let {cname} = {value}")
        else:
            lines.append(f"    {swift_todo(f'Port constant: {cname} = {value}')}")
            lines.append(f'    static let {cname} = ""')

    lines.append("}")
    lines.append("")
    return format_swift("\n".join(lines))


def generate_fallback(source: str, relative_path: str, manifest_entry: dict) -> str:
    """Generate a fallback stub file with TODOs."""
    filename = Path(relative_path).stem
    name = _pascal(filename)
    lines = []
    lines.append(swift_header(f"{name}.swift"))
    lines.append("import Foundation\nimport SwiftUI\n")
    lines.append(f"// Source: {relative_path}")
    lines.append(f"// File type: {manifest_entry.get('file_type', 'unknown')}")
    lines.append(f"// Patterns: {len(manifest_entry.get('patterns', []))}")
    lines.append("")
    lines.append(f"{swift_todo(f'Manually convert {relative_path}')}")
    lines.append(f"// This file could not be automatically converted.")
    lines.append(f"// Review the migration plan for guidance.")
    lines.append("")

    for p in manifest_entry.get("patterns", []):
        equiv = p.get("details", {}).get("ios_equivalent", "")
        lines.append(f"// {p['pattern_type']}: {p['name']} -> {equiv}")

    return format_swift("\n".join(lines))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pascal(name: str) -> str:
    """Quick PascalCase conversion."""
    import re as _re
    if "-" in name or "_" in name:
        parts = _re.split(r"[-_]", name)
        return "".join(p.capitalize() for p in parts if p)
    if name and name[0].islower():
        return name[0].upper() + name[1:]
    return name


def _map_simple_type(ts_type: str | None) -> str:
    """Quick type mapping for simple cases."""
    if not ts_type:
        return "Any"
    mapping = {"string": "String", "number": "Int", "boolean": "Bool", "void": "Void"}
    return mapping.get(ts_type, ts_type)


def _convert_params(params_str: str) -> str:
    """Quick parameter conversion."""
    if not params_str.strip():
        return ""
    parts = []
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        if ":" in p:
            name, ts_type = p.split(":", 1)
            name = name.strip()
            swift_type = _map_simple_type(ts_type.strip())
            parts.append(f"_ {name}: {swift_type}")
        else:
            parts.append(f"_ {p.split('=')[0].strip()}: Any")
    return ", ".join(parts)


def _write_file(path: Path, content: str):
    """Write a file, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
