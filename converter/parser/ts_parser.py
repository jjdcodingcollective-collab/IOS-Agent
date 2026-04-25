"""
TypeScript/TSX AST Parser using tree-sitter.

Provides structured extraction of React/TypeScript constructs that regex
cannot reliably handle: nested JSX, complex generics, scope-aware variables,
and multi-line destructuring.

This addresses GAP-P1: the regex-only approach hits a ceiling on complex
real-world code. The AST parser is used as the primary extraction method,
with regex-based detectors kept as a fallback for simple pattern matching.

Design:
    - Parse once, query many times
    - Return structured Python dicts/dataclasses, not AST nodes
    - Gracefully degrade if tree-sitter is unavailable (import guard)
    - Never modify source code — read-only analysis
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Import tree-sitter with graceful fallback
_HAS_TREE_SITTER = False
try:
    import tree_sitter
    import tree_sitter_typescript as ts_ts
    _HAS_TREE_SITTER = True
except ImportError:
    pass


def is_available() -> bool:
    """Check if tree-sitter is available."""
    return _HAS_TREE_SITTER


# ---------------------------------------------------------------------------
# Dataclasses for structured AST results
# ---------------------------------------------------------------------------

@dataclass
class ASTField:
    """A field in an interface or type."""
    name: str
    type_annotation: str
    optional: bool = False
    line: int = 0


@dataclass
class ASTInterface:
    """A parsed TypeScript interface."""
    name: str
    fields: list[ASTField] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)
    exported: bool = False
    line: int = 0


@dataclass
class ASTTypeAlias:
    """A parsed TypeScript type alias."""
    name: str
    value: str
    exported: bool = False
    line: int = 0


@dataclass
class ASTParam:
    """A function/component parameter."""
    name: str
    type_annotation: str = ""
    default_value: str = ""
    optional: bool = False
    is_rest: bool = False


@dataclass
class ASTHookCall:
    """A React hook call within a component/hook body."""
    hook_name: str
    type_arg: str = ""          # Generic type argument: useState<User>
    arguments: list[str] = field(default_factory=list)
    bindings: list[str] = field(default_factory=list)  # [state, setState] for useState
    line: int = 0


@dataclass
class ASTJSXNode:
    """A node in the JSX tree."""
    tag: str                    # "div", "Button", "UserCard", "" for fragments
    is_component: bool = False  # True if PascalCase (custom component)
    is_fragment: bool = False   # True for <> or <React.Fragment>
    is_self_closing: bool = False
    attributes: dict[str, str] = field(default_factory=dict)  # prop=value pairs
    children: list[ASTJSXNode | str] = field(default_factory=list)  # Nested nodes or text
    expressions: list[str] = field(default_factory=list)  # {expr} children
    line: int = 0


@dataclass
class ASTHandler:
    """An event handler function within a component."""
    name: str
    params: list[ASTParam] = field(default_factory=list)
    body: str = ""
    is_async: bool = False
    line: int = 0


@dataclass
class ASTComponent:
    """A fully parsed React component."""
    name: str
    params: list[ASTParam] = field(default_factory=list)
    props_type: str = ""        # The type annotation for props
    hooks: list[ASTHookCall] = field(default_factory=list)
    jsx_tree: ASTJSXNode | None = None
    handlers: list[ASTHandler] = field(default_factory=list)
    local_vars: list[dict] = field(default_factory=list)  # [{name, type, value}]
    body_source: str = ""       # Raw source of the component body
    exported: bool = False
    is_default_export: bool = False
    line: int = 0


@dataclass
class ASTHook:
    """A parsed custom React hook."""
    name: str
    params: list[ASTParam] = field(default_factory=list)
    return_type: str = ""
    hooks: list[ASTHookCall] = field(default_factory=list)
    inner_functions: list[ASTHandler] = field(default_factory=list)
    state_vars: list[dict] = field(default_factory=list)  # [{name, setter, type, initial}]
    body_source: str = ""
    exported: bool = False
    line: int = 0


@dataclass
class ASTImport:
    """A parsed import statement."""
    source: str = ""            # The module path
    default_name: str = ""      # import Name from ...
    named: list[str] = field(default_factory=list)  # import { A, B } from ...
    namespace: str = ""         # import * as X from ...
    is_type_only: bool = False  # import type { ... }
    line: int = 0


@dataclass
class ParseResult:
    """Complete parse result for a single file."""
    imports: list[ASTImport] = field(default_factory=list)
    interfaces: list[ASTInterface] = field(default_factory=list)
    type_aliases: list[ASTTypeAlias] = field(default_factory=list)
    components: list[ASTComponent] = field(default_factory=list)
    hooks: list[ASTHook] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    used_ast: bool = False      # True if AST parsing was used


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------

class TSParser:
    """
    Lightweight TypeScript/TSX parser using tree-sitter.

    Usage:
        parser = TSParser()
        result = parser.parse_file(source_code, "component.tsx")
        for comp in result.components:
            print(comp.name, comp.hooks, comp.jsx_tree)
    """

    def __init__(self):
        if not _HAS_TREE_SITTER:
            self._tsx_parser = None
            self._ts_parser = None
            return

        tsx_lang = tree_sitter.Language(ts_ts.language_tsx())
        ts_lang = tree_sitter.Language(ts_ts.language_typescript())

        self._tsx_parser = tree_sitter.Parser(tsx_lang)
        self._ts_parser = tree_sitter.Parser(ts_lang)

    def parse_file(self, source: str, filename: str = "") -> ParseResult:
        """
        Parse a TypeScript/TSX file and extract all constructs.

        Args:
            source: The file content
            filename: Used to determine parser (TSX vs TS)

        Returns:
            ParseResult with all extracted constructs
        """
        if not _HAS_TREE_SITTER:
            return ParseResult(errors=["tree-sitter not available"])

        is_tsx = filename.endswith(".tsx") or filename.endswith(".jsx")
        parser = self._tsx_parser if is_tsx else self._ts_parser
        source_bytes = source.encode("utf-8")

        try:
            tree = parser.parse(source_bytes)
        except Exception as e:
            return ParseResult(errors=[f"Parse error: {e}"])

        result = ParseResult(used_ast=True)
        root = tree.root_node

        # Extract top-level constructs
        for child in root.children:
            try:
                if child.type == "import_statement":
                    imp = self._extract_import(child, source_bytes)
                    if imp:
                        result.imports.append(imp)

                elif child.type == "interface_declaration":
                    iface = self._extract_interface(child, source_bytes)
                    if iface:
                        result.interfaces.append(iface)

                elif child.type == "type_alias_declaration":
                    alias = self._extract_type_alias(child, source_bytes)
                    if alias:
                        result.type_aliases.append(alias)

                elif child.type == "export_statement":
                    self._extract_export(child, source_bytes, result)

                elif child.type == "function_declaration":
                    self._extract_function_or_component(child, source_bytes, result, exported=False)

                elif child.type in ("lexical_declaration", "variable_declaration"):
                    self._extract_variable_decl(child, source_bytes, result, exported=False)

            except Exception as e:
                result.errors.append(f"Error extracting {child.type} at L{child.start_point[0]+1}: {e}")

        return result

    # ---------------------------------------------------------------------------
    # Node text helper
    # ---------------------------------------------------------------------------

    def _text(self, node, source_bytes: bytes) -> str:
        """Get the text content of a node."""
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8")

    def _find_children(self, node, type_name: str) -> list:
        """Find all direct children of a specific type."""
        return [c for c in node.children if c.type == type_name]

    def _find_descendants(self, node, type_name: str) -> list:
        """Recursively find all descendant nodes of a specific type."""
        results = []
        if node.type == type_name:
            results.append(node)
        for child in node.children:
            results.extend(self._find_descendants(child, type_name))
        return results

    # ---------------------------------------------------------------------------
    # Import extraction
    # ---------------------------------------------------------------------------

    def _extract_import(self, node, source_bytes: bytes) -> ASTImport | None:
        """Extract an import statement."""
        text = self._text(node, source_bytes)
        imp = ASTImport(line=node.start_point[0] + 1)

        # Check if type-only import
        imp.is_type_only = "import type" in text

        # Extract source module — it's a 'string' child node of the import_statement
        source_node = node.child_by_field_name("source")
        if source_node:
            imp.source = self._text(source_node, source_bytes).strip("'\"")
        else:
            # tree-sitter TSX: source is a 'string' child, not a named field
            for child in node.children:
                if child.type == "string":
                    imp.source = self._text(child, source_bytes).strip("'\"")
                    break
            if not imp.source:
                # Last resort: regex fallback
                m = re.search(r"""from\s+['"]([^'"]+)['"]""", text)
                if m:
                    imp.source = m.group(1)
                else:
                    return None

        # Extract imports from import_clause
        for child in node.children:
            if child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "identifier":
                        imp.default_name = self._text(clause_child, source_bytes)
                    elif clause_child.type == "named_imports":
                        for spec in self._find_children(clause_child, "import_specifier"):
                            name_node = spec.child_by_field_name("name")
                            alias_node = spec.child_by_field_name("alias")
                            if alias_node:
                                imp.named.append(self._text(alias_node, source_bytes))
                            elif name_node:
                                imp.named.append(self._text(name_node, source_bytes))
                    elif clause_child.type == "namespace_import":
                        ident = clause_child.child_by_field_name("name") or next(
                            (c for c in clause_child.children if c.type == "identifier"), None
                        )
                        if ident:
                            imp.namespace = self._text(ident, source_bytes)

        return imp

    # ---------------------------------------------------------------------------
    # Interface extraction
    # ---------------------------------------------------------------------------

    def _extract_interface(self, node, source_bytes: bytes, exported: bool = False) -> ASTInterface | None:
        """Extract a TypeScript interface declaration."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        iface = ASTInterface(
            name=self._text(name_node, source_bytes),
            exported=exported,
            line=node.start_point[0] + 1,
        )

        # Extract extends
        for child in node.children:
            if child.type == "extends_type_clause":
                for type_node in child.children:
                    if type_node.type in ("type_identifier", "generic_type"):
                        iface.extends.append(self._text(type_node, source_bytes))

        # Extract fields from body
        body = node.child_by_field_name("body")
        if body:
            for prop in self._find_descendants(body, "property_signature"):
                field = self._extract_property_field(prop, source_bytes)
                if field:
                    iface.fields.append(field)

        return iface

    def _extract_property_field(self, node, source_bytes: bytes) -> ASTField | None:
        """Extract a single property from an interface body."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._text(name_node, source_bytes)
        optional = any(c.type == "?" for c in node.children)

        # Get type annotation
        type_ann = ""
        type_node = node.child_by_field_name("type")
        if type_node:
            type_ann = self._text(type_node, source_bytes)
        else:
            # Look for type_annotation child
            for child in node.children:
                if child.type == "type_annotation":
                    # Extract just the type, skipping the ":"
                    for tc in child.children:
                        if tc.type != ":":
                            type_ann = self._text(tc, source_bytes)

        return ASTField(
            name=name,
            type_annotation=type_ann,
            optional=optional,
            line=node.start_point[0] + 1,
        )

    # ---------------------------------------------------------------------------
    # Type alias extraction
    # ---------------------------------------------------------------------------

    def _extract_type_alias(self, node, source_bytes: bytes, exported: bool = False) -> ASTTypeAlias | None:
        """Extract a type alias declaration."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        value_node = node.child_by_field_name("value")
        value = self._text(value_node, source_bytes) if value_node else ""

        return ASTTypeAlias(
            name=self._text(name_node, source_bytes),
            value=value,
            exported=exported,
            line=node.start_point[0] + 1,
        )

    # ---------------------------------------------------------------------------
    # Export statement processing
    # ---------------------------------------------------------------------------

    def _extract_export(self, node, source_bytes: bytes, result: ParseResult):
        """Process an export statement, extracting the inner declaration."""
        text = self._text(node, source_bytes)
        is_default = "export default" in text[:30]

        for child in node.children:
            if child.type == "function_declaration":
                self._extract_function_or_component(child, source_bytes, result, exported=True, is_default=is_default)
            elif child.type in ("lexical_declaration", "variable_declaration"):
                self._extract_variable_decl(child, source_bytes, result, exported=True, is_default=is_default)
            elif child.type == "interface_declaration":
                iface = self._extract_interface(child, source_bytes, exported=True)
                if iface:
                    result.interfaces.append(iface)
            elif child.type == "type_alias_declaration":
                alias = self._extract_type_alias(child, source_bytes, exported=True)
                if alias:
                    result.type_aliases.append(alias)
            elif child.type == "identifier":
                result.exports.append(self._text(child, source_bytes))
            elif child.type == "export_clause":
                for spec in self._find_children(child, "export_specifier"):
                    name_node = spec.child_by_field_name("name")
                    if name_node:
                        result.exports.append(self._text(name_node, source_bytes))

    # ---------------------------------------------------------------------------
    # Function / Component extraction
    # ---------------------------------------------------------------------------

    def _extract_function_or_component(
        self, node, source_bytes: bytes, result: ParseResult,
        exported: bool = False, is_default: bool = False,
    ):
        """Extract a function declaration — classify as component or hook."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._text(name_node, source_bytes)
        body_node = node.child_by_field_name("body")
        body_source = self._text(body_node, source_bytes) if body_node else ""

        # Extract parameters
        params = self._extract_params(node, source_bytes)

        # Classify: component (PascalCase), hook (use*), or plain function
        if name[0].isupper():
            comp = self._build_component(name, params, body_node, body_source, source_bytes)
            comp.exported = exported
            comp.is_default_export = is_default
            comp.line = node.start_point[0] + 1
            result.components.append(comp)
        elif name.startswith("use") and len(name) > 3 and name[3].isupper():
            hook = self._build_hook(name, params, body_node, body_source, source_bytes)
            hook.exported = exported
            hook.line = node.start_point[0] + 1
            result.hooks.append(hook)
        # else: plain helper function — not extracted separately

    def _extract_variable_decl(
        self, node, source_bytes: bytes, result: ParseResult,
        exported: bool = False, is_default: bool = False,
    ):
        """Extract arrow function components/hooks from variable declarations."""
        for declarator in self._find_descendants(node, "variable_declarator"):
            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")

            if not name_node or not value_node:
                continue

            name = self._text(name_node, source_bytes)

            # Check if the value is an arrow function or function expression
            if value_node.type in ("arrow_function", "function"):
                body_node = value_node.child_by_field_name("body")
                body_source = self._text(body_node, source_bytes) if body_node else ""
                params = self._extract_params(value_node, source_bytes)

                if name[0].isupper():
                    comp = self._build_component(name, params, body_node, body_source, source_bytes)
                    comp.exported = exported
                    comp.is_default_export = is_default
                    comp.line = node.start_point[0] + 1
                    result.components.append(comp)
                elif name.startswith("use") and len(name) > 3 and name[3].isupper():
                    hook = self._build_hook(name, params, body_node, body_source, source_bytes)
                    hook.exported = exported
                    hook.line = node.start_point[0] + 1
                    result.hooks.append(hook)

    # ---------------------------------------------------------------------------
    # Parameter extraction
    # ---------------------------------------------------------------------------

    def _extract_params(self, func_node, source_bytes: bytes) -> list[ASTParam]:
        """Extract function parameters from a function/arrow node."""
        params = []
        param_nodes = self._find_descendants(func_node, "formal_parameters")
        if not param_nodes:
            return params

        param_list = param_nodes[0]
        for child in param_list.children:
            if child.type == "required_parameter" or child.type == "optional_parameter":
                param = self._extract_single_param(child, source_bytes)
                if param:
                    params.append(param)
            elif child.type == "rest_pattern":
                name_node = next((c for c in child.children if c.type == "identifier"), None)
                if name_node:
                    params.append(ASTParam(
                        name=self._text(name_node, source_bytes),
                        is_rest=True,
                    ))

        return params

    def _extract_single_param(self, node, source_bytes: bytes) -> ASTParam | None:
        """Extract a single parameter."""
        # Handle destructured params: { name, age = 25 }: Props
        pattern_node = node.child_by_field_name("pattern")
        if pattern_node and pattern_node.type == "object_pattern":
            # Extract the type annotation for the whole destructured param
            type_ann = ""
            for child in node.children:
                if child.type == "type_annotation":
                    for tc in child.children:
                        if tc.type != ":":
                            type_ann = self._text(tc, source_bytes)

            # Extract individual destructured names
            names = []
            defaults = {}
            for prop in pattern_node.children:
                if prop.type == "shorthand_property_identifier_pattern":
                    names.append(self._text(prop, source_bytes))
                elif prop.type == "pair_pattern":
                    key = prop.child_by_field_name("key")
                    value = prop.child_by_field_name("value")
                    if key:
                        name = self._text(key, source_bytes)
                        names.append(name)
                elif prop.type == "assignment_pattern":
                    left = prop.child_by_field_name("left")
                    right = prop.child_by_field_name("right")
                    if left:
                        name = self._text(left, source_bytes)
                        names.append(name)
                        if right:
                            defaults[name] = self._text(right, source_bytes)

            # Return a param for each destructured name
            # But for the component converter, we often want them as individual props
            # We'll use a single param with a structured name for now
            return ASTParam(
                name=",".join(names),
                type_annotation=type_ann,
                optional=node.type == "optional_parameter",
                default_value=str(defaults) if defaults else "",
            )

        # Simple parameter
        name_node = node.child_by_field_name("pattern") or next(
            (c for c in node.children if c.type == "identifier"), None
        )
        if not name_node:
            return None

        type_ann = ""
        for child in node.children:
            if child.type == "type_annotation":
                for tc in child.children:
                    if tc.type != ":":
                        type_ann = self._text(tc, source_bytes)

        default_val = ""
        value_node = node.child_by_field_name("value")
        if value_node:
            default_val = self._text(value_node, source_bytes)

        return ASTParam(
            name=self._text(name_node, source_bytes),
            type_annotation=type_ann,
            optional=node.type == "optional_parameter",
            default_value=default_val,
        )

    # ---------------------------------------------------------------------------
    # Component builder
    # ---------------------------------------------------------------------------

    def _build_component(
        self, name: str, params: list[ASTParam],
        body_node, body_source: str, source_bytes: bytes,
    ) -> ASTComponent:
        """Build a complete ASTComponent from parsed pieces."""
        comp = ASTComponent(
            name=name,
            params=params,
            body_source=body_source,
        )

        # Extract props type from first param
        if params and params[0].type_annotation:
            comp.props_type = params[0].type_annotation

        if body_node:
            # Extract hook calls
            comp.hooks = self._extract_hook_calls(body_node, source_bytes)

            # Extract handlers (inner functions)
            comp.handlers = self._extract_inner_handlers(body_node, source_bytes)

            # Extract local variable declarations
            comp.local_vars = self._extract_local_vars(body_node, source_bytes)

            # Extract JSX return
            comp.jsx_tree = self._extract_jsx_return(body_node, source_bytes)

        return comp

    def _build_hook(
        self, name: str, params: list[ASTParam],
        body_node, body_source: str, source_bytes: bytes,
    ) -> ASTHook:
        """Build an ASTHook from parsed pieces."""
        hook = ASTHook(
            name=name,
            params=params,
            body_source=body_source,
        )

        if body_node:
            hook.hooks = self._extract_hook_calls(body_node, source_bytes)
            hook.inner_functions = self._extract_inner_handlers(body_node, source_bytes)
            hook.state_vars = self._extract_state_vars(body_node, source_bytes)

        return hook

    # ---------------------------------------------------------------------------
    # Hook call extraction
    # ---------------------------------------------------------------------------

    def _extract_hook_calls(self, body_node, source_bytes: bytes) -> list[ASTHookCall]:
        """Extract React hook calls from a function body."""
        calls = []
        call_nodes = self._find_descendants(body_node, "call_expression")

        for call in call_nodes:
            func_node = call.child_by_field_name("function")
            if not func_node:
                continue

            func_name = self._text(func_node, source_bytes)
            # Only capture hooks (use* convention)
            if not (func_name.startswith("use") and len(func_name) > 3):
                continue

            hook_call = ASTHookCall(
                hook_name=func_name,
                line=call.start_point[0] + 1,
            )

            # Extract type argument: useState<User>
            type_args = self._find_children(call, "type_arguments")
            if type_args:
                hook_call.type_arg = self._text(type_args[0], source_bytes).strip("<>")

            # Extract call arguments
            args_node = call.child_by_field_name("arguments")
            if args_node:
                for arg in args_node.children:
                    if arg.type not in ("(", ")", ","):
                        hook_call.arguments.append(self._text(arg, source_bytes))

            # Check for array destructuring binding: const [state, setter] = useState(...)
            parent = call.parent
            if parent and parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node and name_node.type == "array_pattern":
                    for child in name_node.children:
                        if child.type == "identifier":
                            hook_call.bindings.append(self._text(child, source_bytes))

            calls.append(hook_call)

        return calls

    def _extract_state_vars(self, body_node, source_bytes: bytes) -> list[dict]:
        """Extract useState declarations as state variables."""
        state_vars = []
        for hook in self._extract_hook_calls(body_node, source_bytes):
            if hook.hook_name == "useState" and len(hook.bindings) >= 2:
                state_vars.append({
                    "name": hook.bindings[0],
                    "setter": hook.bindings[1],
                    "type": hook.type_arg,
                    "initial": hook.arguments[0] if hook.arguments else "",
                })
        return state_vars

    # ---------------------------------------------------------------------------
    # Handler / inner function extraction
    # ---------------------------------------------------------------------------

    def _extract_inner_handlers(self, body_node, source_bytes: bytes) -> list[ASTHandler]:
        """Extract inner function declarations and arrow function assignments."""
        handlers = []

        # Function declarations: function handleClick() { ... }
        for func in self._find_children(body_node, "function_declaration"):
            name_node = func.child_by_field_name("name")
            if name_node:
                handler_body = func.child_by_field_name("body")
                handlers.append(ASTHandler(
                    name=self._text(name_node, source_bytes),
                    params=self._extract_params(func, source_bytes),
                    body=self._text(handler_body, source_bytes) if handler_body else "",
                    is_async=any(c.type == "async" for c in func.children),
                    line=func.start_point[0] + 1,
                ))

        # Arrow functions: const handleClick = () => { ... }
        for decl in self._find_children(body_node, "lexical_declaration"):
            for declarator in self._find_children(decl, "variable_declarator"):
                name_node = declarator.child_by_field_name("name")
                value_node = declarator.child_by_field_name("value")
                if name_node and value_node and value_node.type == "arrow_function":
                    handler_body = value_node.child_by_field_name("body")
                    handlers.append(ASTHandler(
                        name=self._text(name_node, source_bytes),
                        params=self._extract_params(value_node, source_bytes),
                        body=self._text(handler_body, source_bytes) if handler_body else "",
                        is_async=any(c.type == "async" for c in value_node.children),
                        line=decl.start_point[0] + 1,
                    ))

        return handlers

    # ---------------------------------------------------------------------------
    # Local variable extraction
    # ---------------------------------------------------------------------------

    def _extract_local_vars(self, body_node, source_bytes: bytes) -> list[dict]:
        """Extract non-hook variable declarations from the body."""
        vars_ = []
        for decl in self._find_children(body_node, "lexical_declaration"):
            for declarator in self._find_children(decl, "variable_declarator"):
                name_node = declarator.child_by_field_name("name")
                value_node = declarator.child_by_field_name("value")

                if not name_node:
                    continue

                # Skip arrow functions (already captured as handlers)
                if value_node and value_node.type == "arrow_function":
                    continue

                # Skip hook calls (already captured)
                if value_node and value_node.type == "call_expression":
                    func = value_node.child_by_field_name("function")
                    if func:
                        fname = self._text(func, source_bytes)
                        if fname.startswith("use") and len(fname) > 3:
                            continue

                name = self._text(name_node, source_bytes)
                value = self._text(value_node, source_bytes) if value_node else ""

                # Get type annotation if present
                type_ann = ""
                for child in declarator.children:
                    if child.type == "type_annotation":
                        for tc in child.children:
                            if tc.type != ":":
                                type_ann = self._text(tc, source_bytes)

                vars_.append({
                    "name": name,
                    "type": type_ann,
                    "value": value,
                })

        return vars_

    # ---------------------------------------------------------------------------
    # JSX extraction
    # ---------------------------------------------------------------------------

    def _extract_jsx_return(self, body_node, source_bytes: bytes) -> ASTJSXNode | None:
        """Find the main JSX return statement and extract the tree.
        Uses the LAST component-level return with JSX — early returns
        (loading/error guards) come first, the main render is last."""
        returns = self._find_descendants(body_node, "return_statement")
        # Collect all component-level returns with JSX
        jsx_returns: list[ASTJSXNode] = []

        for ret in returns:
            # Skip returns inside nested functions
            if self._is_nested_in_function(ret, body_node):
                continue

            # Find JSX within the return
            jsx = None
            for child in ret.children:
                jsx = self._find_jsx_root(child, source_bytes)
                if jsx:
                    break

            # Check parenthesized expression: return ( <div>... )
            if not jsx:
                parens = self._find_descendants(ret, "parenthesized_expression")
                for paren in parens:
                    for child in paren.children:
                        jsx = self._find_jsx_root(child, source_bytes)
                        if jsx:
                            break
                    if jsx:
                        break

            if jsx:
                jsx_returns.append(jsx)

        # Return the last (main) JSX return, or None
        return jsx_returns[-1] if jsx_returns else None

    def _is_nested_in_function(self, node, stop_at) -> bool:
        """Check if a node is inside a nested function (not the outer body)."""
        current = node.parent
        while current and current != stop_at:
            if current.type in ("function_declaration", "arrow_function", "function"):
                return True
            current = current.parent
        return False

    def _find_jsx_root(self, node, source_bytes: bytes) -> ASTJSXNode | None:
        """Find and extract the root JSX node from an expression."""
        if node.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
            return self._extract_jsx_node(node, source_bytes)

        # Recurse into parenthesized expressions
        if node.type == "parenthesized_expression":
            for child in node.children:
                result = self._find_jsx_root(child, source_bytes)
                if result:
                    return result

        # Check children
        for child in node.children:
            if child.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
                return self._extract_jsx_node(child, source_bytes)

        return None

    def _extract_jsx_node(self, node, source_bytes: bytes) -> ASTJSXNode:
        """Recursively extract a JSX node and its children."""
        if node.type == "jsx_fragment":
            jsx = ASTJSXNode(
                tag="",
                is_fragment=True,
                line=node.start_point[0] + 1,
            )
            for child in node.children:
                self._process_jsx_child(child, jsx, source_bytes)
            return jsx

        if node.type == "jsx_self_closing_element":
            tag = self._get_jsx_tag(node, source_bytes)
            jsx = ASTJSXNode(
                tag=tag,
                is_component=tag[0].isupper() if tag else False,
                is_self_closing=True,
                attributes=self._extract_jsx_attributes(node, source_bytes),
                line=node.start_point[0] + 1,
            )
            return jsx

        # jsx_element — has opening tag, children, closing tag
        tag = ""
        opening = node.child_by_field_name("open_tag") or next(
            (c for c in node.children if c.type == "jsx_opening_element"), None
        )
        if opening:
            tag = self._get_jsx_tag(opening, source_bytes)

        jsx = ASTJSXNode(
            tag=tag,
            is_component=tag[0].isupper() if tag else False,
            attributes=self._extract_jsx_attributes(opening, source_bytes) if opening else {},
            line=node.start_point[0] + 1,
        )

        # Process children
        for child in node.children:
            if child.type in ("jsx_opening_element", "jsx_closing_element"):
                continue
            self._process_jsx_child(child, jsx, source_bytes)

        return jsx

    def _process_jsx_child(self, child, parent_jsx: ASTJSXNode, source_bytes: bytes):
        """Process a child node within JSX."""
        if child.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
            parent_jsx.children.append(self._extract_jsx_node(child, source_bytes))
        elif child.type == "jsx_expression":
            expr_text = self._text(child, source_bytes)
            # Strip outer { }
            expr_inner = expr_text[1:-1].strip() if expr_text.startswith("{") else expr_text
            parent_jsx.expressions.append(expr_inner)

            # Check for JSX inside the expression (conditional rendering)
            for desc in child.children:
                if desc.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
                    parent_jsx.children.append(self._extract_jsx_node(desc, source_bytes))
        elif child.type == "jsx_text":
            text = self._text(child, source_bytes).strip()
            if text:
                parent_jsx.children.append(text)

    def _get_jsx_tag(self, node, source_bytes: bytes) -> str:
        """Extract the tag name from a JSX element."""
        for child in node.children:
            if child.type in ("identifier", "member_expression", "nested_identifier"):
                return self._text(child, source_bytes)
        return ""

    def _extract_jsx_attributes(self, node, source_bytes: bytes) -> dict[str, str]:
        """Extract attributes from a JSX opening/self-closing element."""
        attrs = {}
        if not node:
            return attrs

        for child in node.children:
            if child.type == "jsx_attribute":
                name_node = next(
                    (c for c in child.children if c.type in ("property_identifier", "identifier")), None
                )
                value_node = next(
                    (c for c in child.children if c.type not in ("property_identifier", "identifier", "=")), None
                )
                if name_node:
                    name = self._text(name_node, source_bytes)
                    if value_node:
                        value = self._text(value_node, source_bytes)
                        # Strip quotes from string values
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        elif value.startswith("{") and value.endswith("}"):
                            value = value[1:-1].strip()
                        attrs[name] = value
                    else:
                        attrs[name] = "true"  # Boolean attribute

        return attrs

    # ---------------------------------------------------------------------------
    # Convenience methods
    # ---------------------------------------------------------------------------

    def extract_components(self, source: str, filename: str = "") -> list[ASTComponent]:
        """Parse and return only components."""
        return self.parse_file(source, filename).components

    def extract_interfaces(self, source: str, filename: str = "") -> list[ASTInterface]:
        """Parse and return only interfaces."""
        return self.parse_file(source, filename).interfaces

    def extract_hooks(self, source: str, filename: str = "") -> list[ASTHook]:
        """Parse and return only hooks."""
        return self.parse_file(source, filename).hooks

    def extract_jsx_tree(self, source: str, filename: str = "") -> ASTJSXNode | None:
        """Parse and return the JSX tree of the first component."""
        comps = self.extract_components(source, filename)
        return comps[0].jsx_tree if comps else None
