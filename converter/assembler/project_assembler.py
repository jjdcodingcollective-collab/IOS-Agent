"""
Project Assembler — Orchestrates Phase 4.
Takes the generated Swift files from Phase 3 and the manifest from Phase 1,
then assembles everything into a buildable iOS project structure.
"""

from pathlib import Path
from dataclasses import dataclass, field

from .entry_point import generate_entry_point, generate_content_view
from .config_generator import (
    generate_xcconfig,
    generate_package_swift,
    generate_config_enum,
)
from ..learning.notes_generator import (
    generate_learning_notes,
    generate_inline_annotations,
)
from ..rewriter.engine import ProjectRewriteResult


@dataclass
class AssemblyResult:
    """Result of assembling the iOS project."""
    generated_files: dict[str, str] = field(default_factory=dict)
    learning_notes: str = ""
    project_structure: list[str] = field(default_factory=list)
    app_name: str = "MyApp"


def assemble_project(
    manifest: dict,
    rewrite_result: ProjectRewriteResult,
    output_dir: str,
    app_name: str = "MyApp",
) -> AssemblyResult:
    """
    Assemble a complete iOS project from generated Swift files.

    Args:
        manifest: Analysis manifest from Phase 1
        rewrite_result: Result from Phase 3 rewriting
        output_dir: Root output directory
        app_name: Name of the app (default: MyApp)

    Returns:
        AssemblyResult with all generated project files
    """
    result = AssemblyResult(app_name=app_name)
    output_path = Path(output_dir)
    summary = manifest.get("summary", {})

    # ---------------------------------------------------------------
    # 1. Classify generated files for project assembly
    # ---------------------------------------------------------------
    views = []
    view_models = []
    services = []
    models = []

    for rw in rewrite_result.files:
        entry = {
            "name": _extract_type_name(rw.output_path),
            "output_path": rw.output_path,
            "source_path": rw.source_path,
            "file_type": rw.file_type,
        }

        if rw.file_type in ("component", "route"):
            views.append(entry)
        elif rw.file_type == "hook":
            view_models.append(entry)
        elif rw.file_type == "service":
            services.append(entry)
        elif rw.file_type == "type":
            models.append(entry)

    # ---------------------------------------------------------------
    # 2. Detect auth flow
    # ---------------------------------------------------------------
    has_auth = any(
        "auth" in vm["name"].lower() for vm in view_models
    ) or any(
        "login" in v["name"].lower() for v in views
    )

    # ---------------------------------------------------------------
    # 3. Generate entry point (MyAppApp.swift)
    # ---------------------------------------------------------------
    entry_code = generate_entry_point(
        app_name=app_name,
        view_models=view_models,
        root_view="ContentView",
        has_auth=has_auth,
    )
    entry_path = f"App/{app_name}App.swift"
    result.generated_files[entry_path] = entry_code

    # ---------------------------------------------------------------
    # 4. Generate ContentView with NavigationStack
    # ---------------------------------------------------------------
    has_navigation = len(views) > 1
    content_view_code = generate_content_view(
        app_name=app_name,
        views=views,
        has_navigation=has_navigation,
    )
    content_path = "App/ContentView.swift"
    result.generated_files[content_path] = content_view_code

    # ---------------------------------------------------------------
    # 5. Generate xcconfig files
    # ---------------------------------------------------------------
    env_vars = summary.get("env_variables", [])

    if env_vars:
        debug_config = generate_xcconfig(env_vars, "Debug")
        release_config = generate_xcconfig(env_vars, "Release")
        result.generated_files["Configuration/Debug.xcconfig"] = debug_config
        result.generated_files["Configuration/Release.xcconfig"] = release_config

        # AppConfig.swift for type-safe access
        config_code = generate_config_enum(app_name, env_vars)
        result.generated_files["Configuration/AppConfig.swift"] = config_code

    # ---------------------------------------------------------------
    # 6. Generate Package.swift
    # ---------------------------------------------------------------
    npm_deps = summary.get("third_party_libraries", [])
    package_code = generate_package_swift(app_name, npm_deps)
    result.generated_files["Package.swift"] = package_code

    # ---------------------------------------------------------------
    # 7. Generate Assets.xcassets stub
    # ---------------------------------------------------------------
    result.generated_files["Resources/Assets.xcassets/Contents.json"] = (
        '{\n  "info": {\n    "author": "xcode",\n    "version": 1\n  }\n}\n'
    )

    # AccentColor
    result.generated_files["Resources/Assets.xcassets/AccentColor.colorset/Contents.json"] = (
        '{\n  "colors": [\n    {\n      "idiom": "universal"\n    }\n  ],\n'
        '  "info": {\n    "author": "xcode",\n    "version": 1\n  }\n}\n'
    )

    # AppIcon
    result.generated_files["Resources/Assets.xcassets/AppIcon.appiconset/Contents.json"] = (
        '{\n  "images": [\n    {\n      "idiom": "universal",\n'
        '      "platform": "ios",\n      "size": "1024x1024"\n    }\n  ],\n'
        '  "info": {\n    "author": "xcode",\n    "version": 1\n  }\n}\n'
    )

    # ---------------------------------------------------------------
    # 8. Inject inline learning annotations into generated Swift files
    # ---------------------------------------------------------------
    for rw in rewrite_result.files:
        file_patterns = _get_patterns_for_file(rw.source_path, manifest)
        annotation_lines = generate_inline_annotations(rw.file_type, file_patterns)

        if annotation_lines:
            # Insert annotations after the file header
            code = rw.swift_code
            header_end = _find_header_end(code)
            annotated_code = (
                code[:header_end]
                + "\n".join(annotation_lines) + "\n"
                + code[header_end:]
            )
            rw.swift_code = annotated_code

    # ---------------------------------------------------------------
    # 9. Generate learning-notes.md
    # ---------------------------------------------------------------
    generated_file_info = []
    for rw in rewrite_result.files:
        file_patterns = _get_patterns_for_file(rw.source_path, manifest)
        generated_file_info.append({
            "source_path": rw.source_path,
            "output_path": rw.output_path,
            "file_type": rw.file_type,
            "patterns": file_patterns,
        })

    # Also include scaffold files
    for scaffold_path in rewrite_result.scaffold_files:
        generated_file_info.append({
            "source_path": "(scaffold)",
            "output_path": scaffold_path,
            "file_type": "service",
            "patterns": [],
        })

    result.learning_notes = generate_learning_notes(manifest, generated_file_info)

    # ---------------------------------------------------------------
    # 10. Build project structure listing
    # ---------------------------------------------------------------
    all_files = []

    # Phase 3 generated files
    for rw in rewrite_result.files:
        all_files.append(rw.output_path)
    for sp in rewrite_result.scaffold_files:
        all_files.append(sp)

    # Phase 4 generated files
    for path in result.generated_files:
        all_files.append(path)

    all_files.sort()
    result.project_structure = all_files

    # ---------------------------------------------------------------
    # 11. Write all Phase 4 files to disk
    # ---------------------------------------------------------------
    for rel_path, content in result.generated_files.items():
        full_path = output_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # Write learning notes
    notes_path = output_path.parent / "learning-notes.md"
    notes_path.write_text(result.learning_notes, encoding="utf-8")

    # Re-write Phase 3 files with inline annotations
    for rw in rewrite_result.files:
        annotated_path = output_path / rw.output_path
        annotated_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_path.write_text(rw.swift_code, encoding="utf-8")

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_type_name(output_path: str) -> str:
    """Extract the Swift type name from an output path like 'Views/UserCardView.swift'."""
    filename = Path(output_path).stem
    return filename


def _get_patterns_for_file(source_path: str, manifest: dict) -> list[dict]:
    """Look up the patterns for a file from the manifest."""
    for f in manifest.get("files", []):
        if f["relative_path"] == source_path:
            return f.get("patterns", [])
    return []


def _find_header_end(code: str) -> int:
    """Find the position after the file header comment block."""
    lines = code.split("\n")
    pos = 0

    for i, line in enumerate(lines):
        pos += len(line) + 1  # +1 for newline
        # Header ends after the first blank line after comment block
        if i > 0 and not line.strip() and (i < 2 or lines[i - 1].strip().startswith("//")):
            return pos

    # Fallback: after import statements
    pos = 0
    for line in lines:
        pos += len(line) + 1
        if line.startswith("import "):
            # Find next blank line after imports
            continue
        if not line.strip() and pos > 20:
            return pos

    return 0
