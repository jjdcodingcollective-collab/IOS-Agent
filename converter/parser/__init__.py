"""
AST Parser — Lightweight TypeScript/TSX parser using tree-sitter.
Provides structured AST extraction as a complement to regex-based detectors.
"""

from .ts_parser import TSParser, ASTComponent, ASTInterface, ASTHook

__all__ = [
    "TSParser",
    "ASTComponent",
    "ASTInterface",
    "ASTHook",
]
