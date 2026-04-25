"""
Code Analyzer — Phase 1
Scans TypeScript/React projects and produces a structured analysis manifest.
"""

from .scanner import scan_project
from .patterns import analyze_file, FileAnalysis
from .manifest import build_manifest, generate_report
from .dependency_graph import DependencyGraph

__all__ = [
    "scan_project",
    "analyze_file",
    "FileAnalysis",
    "build_manifest",
    "generate_report",
    "DependencyGraph",
]
