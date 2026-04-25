"""
File Scanner — Phase 1, Step 1
Discovers and reads TypeScript/TSX files from a source directory.
"""

import os
import re
from pathlib import Path
from typing import Generator


# Directories to skip during scanning
SKIP_DIRS = {
    "node_modules", ".next", ".vercel", "dist", "build", ".git",
    "coverage", "__pycache__", ".turbo", ".cache", "out",
}

# File extensions to scan
SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def discover_files(source_dir: str) -> Generator[Path, None, None]:
    """Walk the source directory and yield scannable files."""
    root = Path(source_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Source directory not found: {root}")

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.suffix in SCAN_EXTENSIONS:
                yield fpath


def read_file(filepath: Path) -> str:
    """Read file contents, returning empty string on failure."""
    try:
        return filepath.read_text(encoding="utf-8")
    except Exception:
        return ""


def get_relative_path(filepath: Path, source_dir: str) -> str:
    """Return the path relative to source_dir."""
    return str(filepath.relative_to(Path(source_dir).resolve()))


def detect_monorepo(source_dir: str) -> dict | None:
    """Detect if a directory is a monorepo and find available app directories.
    Fix #12: Returns monorepo info or None if not a monorepo."""
    root = Path(source_dir).resolve()

    # Check for monorepo markers
    markers = {
        "turbo.json": "turborepo",
        "pnpm-workspace.yaml": "pnpm",
        "lerna.json": "lerna",
        "nx.json": "nx",
        "rush.json": "rush",
    }

    detected_tool = None
    for marker, tool in markers.items():
        if (root / marker).exists():
            detected_tool = tool
            break

    if not detected_tool:
        # Also check for apps/ or packages/ directories without a marker
        has_apps = (root / "apps").is_dir()
        has_packages = (root / "packages").is_dir()
        if not (has_apps or has_packages):
            return None
        detected_tool = "unknown"

    # Find available app/package directories
    app_dirs = []
    for subdir_name in ("apps", "packages", "projects", "services", "modules"):
        subdir = root / subdir_name
        if subdir.is_dir():
            for child in sorted(subdir.iterdir()):
                if child.is_dir() and child.name not in SKIP_DIRS:
                    # Check if it has scannable files
                    has_ts = any(
                        f.suffix in SCAN_EXTENSIONS
                        for f in child.rglob("*")
                        if not any(skip in str(f) for skip in SKIP_DIRS)
                    )
                    if has_ts:
                        # Check for package.json to get the package name
                        pkg_json = child / "package.json"
                        pkg_name = child.name
                        if pkg_json.exists():
                            try:
                                import json
                                pkg_data = json.loads(pkg_json.read_text())
                                pkg_name = pkg_data.get("name", child.name)
                            except Exception:
                                pass

                        app_dirs.append({
                            "path": str(child),
                            "relative_path": str(child.relative_to(root)),
                            "name": pkg_name,
                            "parent": subdir_name,
                        })

    return {
        "is_monorepo": True,
        "tool": detected_tool,
        "app_dirs": app_dirs,
        "root": str(root),
    }


def scan_project(source_dir: str) -> list[dict]:
    """
    Scan a project directory and return a list of file records.
    Each record contains the file path, relative path, and raw content.

    Fix #12: Now detects monorepos and includes monorepo info in results.
    """
    root = Path(source_dir).resolve()

    # Check for monorepo structure
    monorepo = detect_monorepo(source_dir)

    files = []
    for fpath in discover_files(source_dir):
        content = read_file(fpath)
        if content:
            files.append({
                "path": str(fpath),
                "relative_path": get_relative_path(fpath, source_dir),
                "extension": fpath.suffix,
                "size_bytes": len(content.encode("utf-8")),
                "content": content,
            })

    # Attach monorepo metadata if detected
    if monorepo and files:
        files[0]["_monorepo"] = monorepo

    return files
