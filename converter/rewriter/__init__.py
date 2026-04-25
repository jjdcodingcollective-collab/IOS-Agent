"""
Code Rewriter — Phase 3
Takes analysis manifest + source files and generates Swift/SwiftUI code.
Each converter handles a specific file type (types, services, hooks, components).
"""

from .engine import rewrite_project

__all__ = ["rewrite_project"]
