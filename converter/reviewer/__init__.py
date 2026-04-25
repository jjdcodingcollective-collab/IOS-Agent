"""
Code Reviewer — Phase 2
Takes analysis manifest and produces a migration plan
by mapping detected patterns to iOS equivalents.
"""

from .migration_planner import generate_migration_plan

__all__ = ["generate_migration_plan"]
