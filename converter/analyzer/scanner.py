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


def scan_project(source_dir: str) -> list[dict]:
    """
    Scan a project directory and return a list of file records.
    Each record contains the file path, relative path, and raw content.
    """
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
    return files
