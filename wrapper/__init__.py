"""
ios-agent wrapper — conversational orchestration around the converter CLI.

Phase 1: local round-trip only. Takes a local source path, runs the CLI,
parses the generated reports, and surfaces a triage summary. No git or
GitHub operations yet — those land in Phase 2 and 3.
"""
