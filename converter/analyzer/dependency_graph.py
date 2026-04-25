"""
Dependency Graph — Phase 1, Step 4
Builds an import dependency graph from analyzed files, resolving cross-file
type references and determining optimal conversion order.

This addresses GAP-P2: files were previously converted in isolation,
breaking cross-file type references in Swift's strict nominal type system.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportEdge:
    """A single import relationship between two files."""
    source_file: str        # the file doing the importing
    target_file: str        # the file being imported (resolved path)
    imported_names: list[str] = field(default_factory=list)
    is_external: bool = False  # True if importing from node_modules


@dataclass
class ExportedSymbol:
    """A symbol exported from a file."""
    name: str
    kind: str           # "type", "function", "component", "hook", "constant", "class", "default"
    file_path: str
    fields: list[dict] = field(default_factory=list)  # For interfaces: [{name, type, optional}]


@dataclass
class TypeShape:
    """The shape of a type (interface/type alias) for cross-file resolution."""
    name: str
    file_path: str
    fields: list[dict] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)
    is_enum: bool = False
    enum_values: list[str] = field(default_factory=list)


class DependencyGraph:
    """
    Builds and queries an import dependency graph for a project.

    Given a set of analyzed files and their source content, this graph:
    1. Collects all exports from each file
    2. Resolves import paths to actual files
    3. Builds directed edges (importer -> imported)
    4. Maintains a type registry for cross-file type lookups
    5. Provides topological sort for optimal conversion order
    """

    def __init__(self, manifest: dict, source_files: dict[str, str]):
        self.edges: list[ImportEdge] = []
        self.exports: dict[str, list[ExportedSymbol]] = {}   # file -> exported symbols
        self.type_registry: dict[str, TypeShape] = {}         # type name -> shape
        self._file_paths: set[str] = set()                    # all known file paths
        self._path_index: dict[str, str] = {}                 # basename -> full relative path
        self._source_files = source_files

        self._build(manifest, source_files)

    def _build(self, manifest: dict, source_files: dict[str, str]):
        """Build the full dependency graph."""
        # Index all known file paths
        for file_entry in manifest.get("files", []):
            rel_path = file_entry["relative_path"]
            self._file_paths.add(rel_path)
            # Index by various path forms for resolution
            stem = Path(rel_path).stem
            self._path_index[stem] = rel_path
            self._path_index[rel_path] = rel_path
            # Also index without extension
            no_ext = str(Path(rel_path).with_suffix(""))
            self._path_index[no_ext] = rel_path

        # Step 1: Collect exports from each file
        for rel_path, content in source_files.items():
            self.exports[rel_path] = self._extract_exports(content, rel_path)

        # Step 2: Build type registry from type definitions
        for rel_path, content in source_files.items():
            self._extract_types(content, rel_path)

        # Step 3: Resolve imports and build edges
        for file_entry in manifest.get("files", []):
            rel_path = file_entry["relative_path"]
            content = source_files.get(rel_path, "")
            if content:
                self._resolve_imports(content, rel_path)

    def _extract_exports(self, content: str, file_path: str) -> list[ExportedSymbol]:
        """Extract all exported symbols from a file."""
        symbols = []

        # Named exports: export function/const/class/interface/type/enum Name
        for m in re.finditer(
            r"export\s+(?:default\s+)?(?:async\s+)?(function|const|class|interface|type|enum)\s+(\w+)",
            content,
        ):
            kind = m.group(1)
            name = m.group(2)
            # Map to our kind categories
            kind_map = {
                "function": "function",
                "const": "constant",
                "class": "class",
                "interface": "type",
                "type": "type",
                "enum": "type",
            }
            # Detect if it's a component (PascalCase function returning JSX)
            if kind == "function" and name[0].isupper():
                symbol_kind = "component"
            elif kind == "function" and name.startswith("use"):
                symbol_kind = "hook"
            else:
                symbol_kind = kind_map.get(kind, "constant")

            symbols.append(ExportedSymbol(
                name=name,
                kind=symbol_kind,
                file_path=file_path,
            ))

        # export default Name (re-export of local)
        for m in re.finditer(r"export\s+default\s+(\w+)\s*;", content):
            name = m.group(1)
            # Check it's not already captured
            if not any(s.name == name for s in symbols):
                symbols.append(ExportedSymbol(
                    name=name,
                    kind="default",
                    file_path=file_path,
                ))

        # export { Name1, Name2 }
        for m in re.finditer(r"export\s*\{([^}]+)\}", content):
            names = [n.strip().split(" as ")[0].strip() for n in m.group(1).split(",")]
            for name in names:
                if name and not any(s.name == name for s in symbols):
                    symbols.append(ExportedSymbol(
                        name=name,
                        kind="constant",
                        file_path=file_path,
                    ))

        # Const object exports: export const serviceName = { ... }
        for m in re.finditer(r"export\s+const\s+(\w+)\s*=\s*\{", content):
            name = m.group(1)
            if not any(s.name == name for s in symbols):
                symbols.append(ExportedSymbol(
                    name=name,
                    kind="constant",
                    file_path=file_path,
                ))

        return symbols

    def _extract_types(self, content: str, file_path: str):
        """Extract type shapes (interfaces/type aliases) for cross-file resolution."""
        # Interfaces
        pattern = r"(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
        for m in re.finditer(pattern, content, re.DOTALL):
            name = m.group(1)
            extends = [e.strip() for e in m.group(2).split(",")] if m.group(2) else []
            body = m.group(3)
            fields = self._parse_fields(body)
            self.type_registry[name] = TypeShape(
                name=name,
                file_path=file_path,
                fields=fields,
                extends=extends,
            )

        # String literal union types (enums)
        for m in re.finditer(
            r"(?:export\s+)?type\s+(\w+)\s*=\s*(\"[^\"]*\"(?:\s*\|\s*\"[^\"]*\")+)",
            content,
        ):
            name = m.group(1)
            values = [v.strip().strip('"') for v in m.group(2).split("|")]
            self.type_registry[name] = TypeShape(
                name=name,
                file_path=file_path,
                is_enum=True,
                enum_values=values,
            )

        # Simple type aliases
        for m in re.finditer(r"(?:export\s+)?type\s+(\w+)\s*=\s*([^;{]+);", content):
            name = m.group(1)
            if name not in self.type_registry:  # Don't overwrite richer definitions
                self.type_registry[name] = TypeShape(
                    name=name,
                    file_path=file_path,
                )

    def _parse_fields(self, body: str) -> list[dict]:
        """Parse interface fields for the type registry.
        Handles nested inline objects by tracking brace depth."""
        fields = []
        lines = body.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("//"):
                i += 1
                continue

            m = re.match(r"(\w+)(\?)?:\s*(.+?)\s*;?\s*$", line)
            if m:
                fname = m.group(1)
                optional = m.group(2) == "?"
                ftype = m.group(3).rstrip(";").strip()

                # If the type opens a brace, consume the nested object
                if "{" in ftype:
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

    def _resolve_imports(self, content: str, file_path: str):
        """Resolve import statements to actual files and build edges."""
        # ES module imports: import { X, Y } from './path'
        for m in re.finditer(
            r"import\s+(?:(?:(\w+)|(?:\{([^}]+)\})|\*\s+as\s+(\w+))\s*,?\s*)*from\s+['\"]([^'\"]+)['\"]",
            content,
        ):
            import_path = m.group(4)
            full_match = m.group(0)

            # Extract imported names
            imported_names = []
            # Default import
            default_m = re.match(r"import\s+(\w+)\s", full_match)
            if default_m and default_m.group(1) not in ("type", "from"):
                imported_names.append(default_m.group(1))
            # Named imports
            named_m = re.search(r"\{([^}]+)\}", full_match)
            if named_m:
                for name in named_m.group(1).split(","):
                    name = name.strip()
                    if " as " in name:
                        name = name.split(" as ")[1].strip()
                    if name and name != "type":
                        imported_names.append(name)
            # Namespace import
            ns_m = re.search(r"\*\s+as\s+(\w+)", full_match)
            if ns_m:
                imported_names.append(ns_m.group(1))

            # Resolve the import path
            is_external = not import_path.startswith(".") and not import_path.startswith("@/")
            resolved = self._resolve_path(import_path, file_path) if not is_external else import_path

            self.edges.append(ImportEdge(
                source_file=file_path,
                target_file=resolved,
                imported_names=imported_names,
                is_external=is_external,
            ))

        # require() calls
        for m in re.finditer(r"(?:const|let|var)\s+(?:(\w+)|\{([^}]+)\})\s*=\s*require\(['\"]([^'\"]+)['\"]\)", content):
            import_path = m.group(3)
            imported_names = []
            if m.group(1):
                imported_names.append(m.group(1))
            if m.group(2):
                imported_names.extend(n.strip() for n in m.group(2).split(","))

            is_external = not import_path.startswith(".")
            resolved = self._resolve_path(import_path, file_path) if not is_external else import_path

            self.edges.append(ImportEdge(
                source_file=file_path,
                target_file=resolved,
                imported_names=imported_names,
                is_external=is_external,
            ))

    def _resolve_path(self, import_path: str, from_file: str) -> str:
        """
        Resolve a relative import path to an actual file in the project.

        Handles:
        - Relative paths: ./types, ../utils/date
        - Extension inference: .ts, .tsx, .js, .jsx
        - Index files: ./components -> ./components/index.ts
        - Alias paths: @/components -> components (basic support)
        """
        # Handle alias paths (@/ prefix)
        if import_path.startswith("@/"):
            import_path = import_path[2:]  # Strip @/
            # Try direct resolution from project root
            return self._find_file(import_path)

        if import_path.startswith("."):
            # Resolve relative to the importing file's directory
            from_dir = str(Path(from_file).parent)
            if from_dir == ".":
                candidate = import_path.lstrip("./")
            else:
                # Normalize the path
                candidate = str(Path(from_dir) / import_path)
                # Clean up path (resolve .. etc.)
                parts = candidate.replace("\\", "/").split("/")
                resolved_parts = []
                for part in parts:
                    if part == "..":
                        if resolved_parts:
                            resolved_parts.pop()
                    elif part != ".":
                        resolved_parts.append(part)
                candidate = "/".join(resolved_parts)

            return self._find_file(candidate)

        # Non-relative, non-alias — likely external
        return import_path

    def _find_file(self, path_stem: str) -> str:
        """Find a file by path stem, trying various extensions and index files."""
        # Direct match
        if path_stem in self._file_paths:
            return path_stem

        # Try with extensions
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            candidate = path_stem + ext
            if candidate in self._file_paths:
                return candidate

        # Try as directory with index file
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            candidate = f"{path_stem}/index{ext}"
            if candidate in self._file_paths:
                return candidate

        # Try the path index (basename matching)
        stem = Path(path_stem).stem
        if stem in self._path_index:
            return self._path_index[stem]

        # Not found — return the stem as-is (will be flagged as unresolved)
        return path_stem

    # ---------------------------------------------------------------------------
    # Query methods
    # ---------------------------------------------------------------------------

    def get_type_shape(self, name: str) -> TypeShape | None:
        """Look up a type's fields by name."""
        return self.type_registry.get(name)

    def get_all_types(self) -> dict[str, TypeShape]:
        """Return the full type registry."""
        return dict(self.type_registry)

    def get_imports_for(self, file_path: str) -> list[ImportEdge]:
        """Get all imports for a specific file."""
        return [e for e in self.edges if e.source_file == file_path]

    def get_dependents(self, file_path: str) -> list[str]:
        """Get files that import from the given file."""
        return list(set(
            e.source_file for e in self.edges
            if e.target_file == file_path and not e.is_external
        ))

    def get_external_deps(self) -> list[str]:
        """Get all external (npm) dependencies used across the project."""
        return sorted(set(
            e.target_file for e in self.edges if e.is_external
        ))

    def get_internal_edges(self) -> list[ImportEdge]:
        """Get only internal (project file) import edges."""
        return [e for e in self.edges if not e.is_external]

    def resolve_imported_type(self, type_name: str, from_file: str) -> TypeShape | None:
        """
        Given a type name used in a file, resolve it by checking:
        1. Types defined in the same file
        2. Types imported from other files
        """
        # Check if defined in the type registry
        shape = self.type_registry.get(type_name)
        if shape:
            return shape

        # Check imports of this file to find where it comes from
        for edge in self.get_imports_for(from_file):
            if type_name in edge.imported_names:
                # Look in the target file's exports
                target_exports = self.exports.get(edge.target_file, [])
                for exp in target_exports:
                    if exp.name == type_name:
                        return self.type_registry.get(type_name)

        return None

    def get_conversion_order(self) -> list[str]:
        """
        Return files in optimal conversion order via topological sort.

        Order: types first, then services, then hooks/ViewModels, then components.
        Within each tier, dependencies come before dependents.
        """
        # Build adjacency list for internal edges only
        graph: dict[str, set[str]] = {f: set() for f in self._file_paths}
        for edge in self.edges:
            if not edge.is_external and edge.target_file in self._file_paths:
                graph.setdefault(edge.source_file, set()).add(edge.target_file)

        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = {f: 0 for f in self._file_paths}
        for node, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0)  # don't increment — we want deps first
        # Actually: for topo sort, in_degree counts incoming edges
        in_degree = {f: 0 for f in self._file_paths}
        for node, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] = in_degree.get(node, 0) + 1

        # Start with nodes that have no dependencies
        queue = [f for f in self._file_paths if in_degree.get(f, 0) == 0]
        queue.sort()  # Deterministic ordering
        result = []
        visited = set()

        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            result.append(node)

            # Find nodes that depend on this one
            for other, deps in graph.items():
                if node in deps and other not in visited:
                    in_degree[other] -= 1
                    if in_degree[other] <= 0:
                        queue.append(other)
                        queue.sort()

        # Add any remaining nodes (cycles or disconnected)
        for f in sorted(self._file_paths):
            if f not in visited:
                result.append(f)

        return result

    def get_unresolved_imports(self) -> list[dict]:
        """Find imports that couldn't be resolved to project files."""
        unresolved = []
        for edge in self.edges:
            if not edge.is_external and edge.target_file not in self._file_paths:
                unresolved.append({
                    "from": edge.source_file,
                    "import_path": edge.target_file,
                    "names": edge.imported_names,
                })
        return unresolved

    def summary(self) -> dict:
        """Return a summary of the dependency graph for reporting."""
        internal_edges = self.get_internal_edges()
        return {
            "total_files": len(self._file_paths),
            "total_edges": len(self.edges),
            "internal_edges": len(internal_edges),
            "external_deps": len(self.get_external_deps()),
            "types_registered": len(self.type_registry),
            "unresolved_imports": len(self.get_unresolved_imports()),
            "conversion_order": self.get_conversion_order(),
        }
