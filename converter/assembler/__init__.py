"""
Phase 4: Project Assembler — Combines generated Swift files into
a buildable SPM package with entry point, navigation, Package.swift,
Info.plist, xcconfig files, and project.yml (XcodeGen).

Phase B additions:
- SPM executable package layout (Sources/{AppName}/)
- Info.plist generation from detected Web API patterns
- project.yml for XcodeGen (optional)
- Test target placeholder
"""

from .project_assembler import assemble_project, AssemblyResult
from .plist_generator import generate_info_plist
