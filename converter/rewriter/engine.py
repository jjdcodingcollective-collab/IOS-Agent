"""
Rewriter Engine — Orchestrates all converters.
Routes each file to the appropriate converter based on its file_type
from the analysis manifest, then assembles the output.

Phase A enhancements:
- Uses DependencyGraph for cross-file type resolution and conversion ordering
- Passes AST parser to converters when available
- Tracks per-file confidence scores
"""

import json
from pathlib import Path
from dataclasses import dataclass, field

from .swift_helpers import format_swift, swift_header, swift_todo
from .type_converter import convert_types_file
from .service_converter import (
    convert_service_file,
    generate_api_client_scaffold,
    generate_load_state_scaffold,
)
from .hook_converter import convert_hook_file
from .component_converter import convert_component_file
from .state_converter import convert_state_file


@dataclass
class RewriteResult:
    """Result of rewriting a single file."""
    source_path: str
    output_path: str
    swift_code: str
    file_type: str
    success: bool = True
    notes: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    confidence_breakdown: dict = field(default_factory=dict)


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
    "state": "ViewModels",    # BUILD-8: state management stores → ViewModels
    "config": "Configuration",
    "utility": "Extensions",
    "unknown": "Misc",
}


def rewrite_project(
    manifest: dict,
    source_files: dict[str, str],
    output_dir: str,
    dependency_graph=None,
) -> ProjectRewriteResult:
    """
    Rewrite an entire project from TypeScript to Swift.

    Args:
        manifest: The analysis manifest (from Phase 1)
        source_files: Dict mapping relative_path -> file content
        output_dir: Directory to write Swift files to
        dependency_graph: Optional DependencyGraph for cross-file type resolution

    Returns:
        ProjectRewriteResult with all generated files
    """
    result = ProjectRewriteResult()
    output_path = Path(output_dir)

    # Always generate infrastructure scaffolds
    # Note: files are stored in result but NOT written to disk here —
    # the assembler handles all disk I/O after relocating into SPM layout
    api_client_code = generate_api_client_scaffold()
    result.scaffold_files["Services/APIClient.swift"] = api_client_code

    # Phase B: LoadState<T> for ViewModel state management
    load_state_code = generate_load_state_scaffold()
    result.scaffold_files["Models/LoadState.swift"] = load_state_code

    # Determine file processing order
    # If we have a dependency graph, use topological sort (types first, then
    # services, then hooks/ViewModels, then components)
    file_entries_by_path = {
        entry["relative_path"]: entry
        for entry in manifest.get("files", [])
    }

    if dependency_graph:
        ordered_paths = dependency_graph.get_conversion_order()
    else:
        ordered_paths = [e["relative_path"] for e in manifest.get("files", [])]

    # Process each file in dependency order
    for rel_path in ordered_paths:
        file_entry = file_entries_by_path.get(rel_path)
        if not file_entry:
            continue

        file_type = file_entry["file_type"]
        source = source_files.get(rel_path, "")

        if not source:
            continue

        # Skip files with no detected patterns
        if not file_entry.get("patterns"):
            continue

        # Route to the appropriate converter
        # Note: files are NOT written to disk here — the assembler handles
        # all disk I/O after relocating into SPM layout (Phase B)
        try:
            rewrite = convert_file(
                source, rel_path, file_type, file_entry,
                dependency_graph=dependency_graph,
            )
            result.files.append(rewrite)

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
    dependency_graph=None,
) -> RewriteResult:
    """Route a file to the correct converter and return the result."""

    ios_dir = FILE_TYPE_TO_DIR.get(file_type, "Misc")
    filename = Path(relative_path).stem
    notes = []

    # Add cross-file type context from dependency graph
    if dependency_graph:
        imports = dependency_graph.get_imports_for(relative_path)
        internal_imports = [e for e in imports if not e.is_external]
        if internal_imports:
            imported_types = []
            for edge in internal_imports:
                for name in edge.imported_names:
                    shape = dependency_graph.get_type_shape(name)
                    if shape:
                        imported_types.append(name)
            if imported_types:
                notes.append(f"Cross-file types resolved: {', '.join(imported_types)}")

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

    elif file_type == "state":
        # BUILD-8: State management stores (Zustand / Redux / Jotai / Context)
        swift_code = convert_state_file(source, relative_path, manifest_entry)
        # Derive output filename based on library
        name = _pascal(filename)
        if "Slice" in filename or "Reducer" in filename:
            name = name.replace("Slice", "").replace("Reducer", "") + "ViewModel"
        elif "Store" in filename or "store" in filename.lower():
            name = name.replace("Store", "").replace("store", "") + "Store"
        else:
            name = name + "ViewModel"
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

    score, breakdown = score_rewrite(swift_code, manifest_entry, file_type)

    return RewriteResult(
        source_path=relative_path,
        output_path=output_path,
        swift_code=swift_code,
        file_type=file_type,
        notes=notes,
        confidence_score=score,
        confidence_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# BUILD-14: Per-file confidence scoring
# ---------------------------------------------------------------------------

def score_rewrite(swift_code: str, manifest_entry: dict, file_type: str) -> tuple[float, dict]:
    """Compute a 0.0–1.0 confidence score for a generated Swift file.

    The score starts at 1.0 and is reduced by each weak signal in the output:
    TODOs, EmptyView fallbacks, Any-type fallbacks, and patterns the analyzer
    flagged as ``manual``. Scores are clamped to [0.0, 1.0]. The breakdown
    dict explains every deduction so users can see exactly why a file scored
    low and prioritise their manual review.
    """
    breakdown: dict = {}
    score = 1.0

    todo_count = swift_code.count("// TODO")
    if todo_count:
        delta = -0.05 * todo_count
        score += delta
        breakdown["todos"] = {"count": todo_count, "delta": round(delta, 3)}

    empty_view_count = swift_code.count("EmptyView()")
    if empty_view_count:
        delta = -0.10 * empty_view_count
        score += delta
        breakdown["empty_views"] = {"count": empty_view_count, "delta": round(delta, 3)}

    any_count = swift_code.count(": Any") + swift_code.count(":Any")
    if any_count:
        delta = -0.03 * any_count
        score += delta
        breakdown["any_fallbacks"] = {"count": any_count, "delta": round(delta, 3)}

    force_unwrap_count = _count_force_unwraps(swift_code)
    if force_unwrap_count:
        delta = -0.04 * force_unwrap_count
        score += delta
        breakdown["force_unwraps"] = {"count": force_unwrap_count, "delta": round(delta, 3)}

    # Pattern difficulty distribution (analyzer signal — independent of generated code)
    auto = assisted = manual = 0
    for p in manifest_entry.get("patterns", []) or []:
        difficulty = (p.get("conversion_difficulty") if isinstance(p, dict) else None) or ""
        if difficulty == "auto":
            auto += 1
        elif difficulty == "assisted":
            assisted += 1
        elif difficulty == "manual":
            manual += 1

    if manual:
        delta = -0.08 * manual
        score += delta
        breakdown["manual_patterns"] = {"count": manual, "delta": round(delta, 3)}
    if assisted:
        # Smaller penalty — assisted patterns generate decent output but need review
        delta = -0.02 * assisted
        score += delta
        breakdown["assisted_patterns"] = {"count": assisted, "delta": round(delta, 3)}

    # Clamp and round
    score = max(0.0, min(1.0, score))
    breakdown["final"] = round(score, 3)
    breakdown["file_type"] = file_type
    return round(score, 3), breakdown


def _count_force_unwraps(swift_code: str) -> int:
    """Count force-unwrap operators (``!``) excluding type declarations and comments."""
    import re as _re
    count = 0
    for line in swift_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Skip implicitly-unwrapped optionals in declarations: `var x: T!`
        if _re.search(r":\s*\w+!", line):
            continue
        # Match ! that follows an identifier/closer and is not !=
        for m in _re.finditer(r"[\w\)\]]!", line):
            idx = m.end()
            if idx < len(line) and line[idx] == "=":
                continue
            count += 1
    return count


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
