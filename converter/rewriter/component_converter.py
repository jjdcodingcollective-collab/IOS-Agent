"""
Component Converter — Converts React TSX components to SwiftUI Views.
Maps JSX elements to SwiftUI views, hooks to @State, and event handlers to actions.
"""

import re
from .swift_helpers import (
    map_type, to_pascal_case, to_camel_case, swift_header, swift_mark,
    swift_todo, format_swift,
)


def convert_component_file(source: str, relative_path: str, manifest_entry: dict) -> str:
    """
    Convert a React component file to a SwiftUI View.
    Returns the generated Swift code.
    """
    filename = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    blocks = []

    # Extract the main component
    component = extract_component(source)
    if not component:
        # Fallback to manifest
        view_name = to_pascal_case(filename) + "View"
        swift_name = f"{view_name}.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import SwiftUI\n")
        blocks.append(generate_view_from_manifest(view_name, manifest_entry))
        return format_swift("\n".join(blocks))

    view_name = component["name"]
    if not view_name.endswith("View"):
        view_name += "View"
    swift_name = f"{view_name}.swift"

    blocks.append(swift_header(swift_name))
    blocks.append("import SwiftUI\n")

    # Convert inline types (interfaces in the same file)
    inline_types = extract_inline_types(source)
    for t in inline_types:
        blocks.append(t)

    # Convert the component
    blocks.append(convert_component(component, source, manifest_entry))

    # Add preview
    blocks.append(generate_preview(view_name, component))

    # Final cleanup: remove leaked JS artifacts from the output
    result = format_swift("\n".join(blocks))
    result = _cleanup_swift_output(result)
    return result


# ---------------------------------------------------------------------------
# Component extraction
# ---------------------------------------------------------------------------

def extract_component(source: str) -> dict | None:
    """Extract the main React component from source."""
    # Function component: export function Name({props}) or Name({props}: Type)
    pattern = re.compile(
        r"(?:export\s+(?:default\s+)?)?function\s+([A-Z]\w+)\s*\(\s*\{?\s*([^}]*?)\s*\}?\s*(?::\s*(?:\{[^}]*\}|\w+(?:\.\w+)?(?:<[^>]*>)?))?\s*\)",
        re.MULTILINE,
    )
    m = pattern.search(source)
    if not m:
        # Arrow component: const Name = ({props}) =>
        pattern = re.compile(
            r"(?:export\s+)?const\s+([A-Z]\w+)\s*(?::\s*\w+(?:\.\w+)?(?:<[^>]*>)?\s*)?=\s*\(\s*\{?\s*([^}]*?)\s*\}?\s*(?::\s*(?:\{[^}]*\}|\w+(?:\.\w+)?(?:<[^>]*>)?))?\s*\)\s*(?::\s*\w+)?\s*=>",
        )
        m = pattern.search(source)

    if not m:
        return None

    name = m.group(1)
    props_str = m.group(2).strip()

    # Find the component body
    # Look for the return statement with JSX
    start = m.end()
    # Find opening brace
    brace_pos = source.find("{", start)
    if brace_pos == -1:
        return None

    depth = 1
    i = brace_pos + 1
    while i < len(source) and depth > 0:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    body = source[brace_pos + 1:i - 1]

    # Parse props
    props = parse_props(props_str, source)

    return {
        "name": name,
        "props": props,
        "body": body,
    }


def parse_props(props_str: str, full_source: str) -> list[dict]:
    """Parse component props from destructured parameters."""
    props = []
    if not props_str:
        return props

    # Clean up destructuring artifacts
    # Remove type annotation suffix like }: Props or }: SomeType
    props_str = re.sub(r"\}\s*:\s*\w+(\.\w+)?(<[^>]*>)?\s*$", "", props_str)
    # Remove stray braces
    props_str = props_str.strip().strip("{}")

    for prop in props_str.split(","):
        prop = prop.strip()
        if not prop:
            continue

        # Skip spread operators (...props, ...rest)
        if prop.startswith("..."):
            continue

        # Skip renamed destructuring like `as: Tag = "button"`
        if prop.startswith("as:") or prop.startswith("as "):
            continue

        # Handle default values: prop = defaultValue
        default = None
        if "=" in prop:
            parts = prop.split("=", 1)
            prop = parts[0].strip()
            default = parts[1].strip()

        # Handle type annotations from props interface
        # Look up the interface in source
        prop_name = prop.split(":")[0].strip()

        # Skip empty or invalid prop names
        if not prop_name or not prop_name.isidentifier():
            continue

        prop_type = find_prop_type(prop_name, full_source)

        props.append({
            "name": prop_name,
            "type": prop_type,
            "default": default,
            "optional": default is not None or prop_type.endswith("?"),
        })

    return props


def find_prop_type(prop_name: str, source: str) -> str:
    """Try to find a prop's type from the Props interface in source."""
    # Special case: children is always a view/content
    if prop_name == "children":
        return "AnyView"

    # Special case: common callback patterns
    if prop_name.startswith("on") and prop_name[2:3].isupper():
        return "() -> Void"

    # Look for PropName?: type or PropName: type in interfaces
    pattern = re.compile(rf"\b{re.escape(prop_name)}\??:\s*([^;\n,}}]+)", re.MULTILINE)
    m = pattern.search(source)
    if m:
        raw = m.group(1).strip()
        # Skip if the match is from a destructuring or assignment, not an interface
        # (interface fields end with ; or are on their own line)
        return map_type(raw)
    return "String"


# ---------------------------------------------------------------------------
# Component conversion
# ---------------------------------------------------------------------------

def convert_component(component: dict, source: str, manifest_entry: dict) -> str:
    """Convert a React component to a SwiftUI View."""
    name = component["name"]
    if not name.endswith("View"):
        name += "View"
    body = component["body"]
    lines = []

    lines.append(f"struct {name}: View {{")

    # Convert props to properties
    if component["props"]:
        lines.append(f"    {swift_mark('Props')}")
        lines.append("")
        for prop in component["props"]:
            prop_decl = convert_prop(prop)
            lines.append(f"    {prop_decl}")
        lines.append("")

    # Extract useState -> @State
    state_vars = extract_use_state_from_body(body)
    if state_vars:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")
        for sv in state_vars:
            lines.append(f"    @State private var {sv['name']}: {sv['type']} = {sv['initial']}")
        lines.append("")

    # Check for useNavigate
    has_navigate = "useNavigate" in body
    if has_navigate:
        lines.append(f"    {swift_mark('Navigation')}")
        lines.append("    @Environment(\\.dismiss) private var dismiss")
        lines.append("")

    # Convert JSX to SwiftUI body
    lines.append("    var body: some View {")
    jsx_body = extract_jsx_return(body)
    if jsx_body:
        swift_ui = convert_jsx_to_swiftui(jsx_body, state_vars, component)
        for line in swift_ui.split("\n"):
            lines.append(f"        {line}")
    else:
        lines.append(f"        {swift_todo('Convert JSX to SwiftUI')}")
        lines.append("        Text(\"TODO\")")
    lines.append("    }")

    # Convert event handler functions
    handlers = extract_handlers(body)
    if handlers:
        lines.append("")
        lines.append(f"    {swift_mark('Actions')}")
        lines.append("")
        for handler in handlers:
            lines.append(convert_handler(handler, state_vars))

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def convert_prop(prop: dict) -> str:
    """Convert a React prop to a Swift property."""
    name = prop["name"]
    swift_type = prop["type"]

    # Special handling for children — use @ViewBuilder content closure
    if name == "children":
        return "let content: AnyView  // 💡 Children prop — consider using @ViewBuilder instead"

    # Special handling for callback props
    if swift_type == "() -> Void":
        if prop["optional"]:
            return f"var {name}: (() -> Void)? = nil"
        return f"let {name}: () -> Void"

    if prop["default"] is not None:
        default_val = convert_default(prop["default"], swift_type)
        return f"var {name}: {swift_type} = {default_val}"
    elif prop["optional"]:
        return f"var {name}: {swift_type}"
    else:
        return f"let {name}: {swift_type}"


def convert_default(default: str, swift_type: str) -> str:
    """Convert a JS default value to Swift."""
    if default in ("true", "false"):
        return default
    if default.isdigit():
        return default
    if default in ("null", "undefined"):
        return "nil"
    if default.startswith('"') or default.startswith("'"):
        clean = default.strip("\"'")
        return f'"{clean}"'
    return default


# ---------------------------------------------------------------------------
# State extraction
# ---------------------------------------------------------------------------

def extract_use_state_from_body(body: str) -> list[dict]:
    """Extract useState calls from component body."""
    states = []
    pattern = re.compile(
        r"const\s+\[(\w+),\s*set\w+\]\s*=\s*useState(?:<([^>]+)>)?\s*\(([^)]*)\)"
    )
    for m in pattern.finditer(body):
        name = m.group(1)
        ts_type = m.group(2)
        initial = m.group(3).strip()

        swift_type = map_type(ts_type) if ts_type else infer_type(initial)
        swift_initial = convert_initial_value(initial, swift_type)

        if initial in ("null", "nil", "") and not swift_type.endswith("?"):
            swift_type += "?"

        states.append({
            "name": name,
            "type": swift_type,
            "initial": swift_initial,
            "setter": f"set{name[0].upper()}{name[1:]}",
        })
    return states


def infer_type(initial: str) -> str:
    """Infer Swift type from initial value."""
    if initial in ("true", "false"):
        return "Bool"
    if initial.isdigit():
        return "Int"
    if initial.startswith('"') or initial.startswith("'"):
        return "String"
    if initial in ("null", "nil", ""):
        return "Any?"
    if initial.startswith("["):
        return "[Any]"
    return "Any"


def convert_initial_value(initial: str, swift_type: str) -> str:
    """Convert JS initial value to Swift."""
    if initial in ("null", "nil", ""):
        return "nil"
    if initial in ("true", "false"):
        return initial
    if initial.isdigit():
        return initial
    if initial.startswith('"') or initial.startswith("'"):
        clean = initial.strip("\"'")
        return f'"{clean}"'
    if initial.startswith("["):
        return "[]"
    return "nil"


# ---------------------------------------------------------------------------
# JSX -> SwiftUI conversion
# ---------------------------------------------------------------------------

def extract_jsx_return(body: str) -> str | None:
    """Extract the JSX from the return statement."""
    # Find return ( ... ) or return <...>
    return_match = re.search(r"return\s*\(\s*", body)
    if return_match:
        start = return_match.end()
        depth = 1
        i = start
        while i < len(body) and depth > 0:
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
            i += 1
        return body[start:i - 1].strip()

    # Bare return <...>
    return_match = re.search(r"return\s+(<.+)", body, re.DOTALL)
    if return_match:
        return return_match.group(1).strip()

    return None


def convert_jsx_to_swiftui(jsx: str, state_vars: list, component: dict) -> str:
    """Convert JSX to SwiftUI code. High-level structural conversion."""
    lines = []
    jsx = jsx.strip()

    # Build context for conversion
    state_names = {sv["name"] for sv in state_vars}
    setters = {sv["setter"]: sv["name"] for sv in state_vars}

    # Process the JSX tree
    result = process_jsx_element(jsx, state_names, setters, indent_level=0)
    return result


def process_jsx_element(jsx: str, state_names: set, setters: dict, indent_level: int) -> str:
    """Recursively process JSX elements into SwiftUI."""
    jsx = jsx.strip()
    ind = "    " * indent_level
    lines = []

    # Handle conditional rendering: {condition && <Element>}
    # Handle ternary: {condition ? <A> : <B>}
    # Handle fragments: <> ... </>

    # For the MVP, do a structural conversion that captures the key patterns

    # Detect the outermost element
    if jsx.startswith("<div") or jsx.startswith("<section") or jsx.startswith("<main"):
        # Detect flex direction from className
        if 'flex-col' in jsx or 'flex flex-col' in jsx:
            container = "VStack"
        elif 'flex ' in jsx and 'flex-col' not in jsx:
            container = "HStack"
        else:
            container = "VStack"

        # Extract alignment/spacing from Tailwind
        spacing = extract_spacing(jsx)
        alignment = extract_alignment(jsx)

        params = []
        if alignment:
            params.append(f"alignment: .{alignment}")
        if spacing:
            params.append(f"spacing: {spacing}")

        params_str = f"({', '.join(params)})" if params else ""
        lines.append(f"{ind}{container}{params_str} {{")

        # Extract children and process
        children = extract_jsx_children(jsx)
        for child in children:
            child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
            if child_result.strip():
                lines.append(child_result)

        lines.append(f"{ind}}}")

        # Add SwiftUI modifiers from Tailwind classes
        modifiers = extract_tailwind_modifiers(jsx)
        for mod in modifiers:
            lines.append(f"{ind}{mod}")

    elif jsx.startswith("<h1") or jsx.startswith("<h2") or jsx.startswith("<h3"):
        text_content = extract_text_content(jsx)
        font = ".title" if "<h1" in jsx else ".title2" if "<h2" in jsx else ".title3"
        text_expr = convert_text_expression(text_content, state_names)
        lines.append(f"{ind}Text({text_expr})")
        lines.append(f"{ind}    .font({font})")
        lines.append(f"{ind}    .fontWeight(.bold)")

    elif jsx.startswith("<p") or jsx.startswith("<span"):
        text_content = extract_text_content(jsx)
        text_expr = convert_text_expression(text_content, state_names)
        lines.append(f"{ind}Text({text_expr})")
        # Apply text styling from Tailwind
        text_mods = extract_text_modifiers(jsx)
        for mod in text_mods:
            lines.append(f"{ind}    {mod}")

    elif jsx.startswith("<img") or jsx.startswith("<Image"):
        src = extract_attr(jsx, "src")
        if src and ("{" in src or "http" in src.lower()):
            lines.append(f"{ind}AsyncImage(url: URL(string: {convert_text_expression(src, state_names)})) {{ image in")
            lines.append(f"{ind}    image.resizable().scaledToFill()")
            lines.append(f"{ind}}} placeholder: {{")
            lines.append(f"{ind}    ProgressView()")
            lines.append(f"{ind}}}")
        else:
            lines.append(f"{ind}Image(\"{src or 'placeholder'}\")")
            lines.append(f"{ind}    .resizable()")
            lines.append(f"{ind}    .scaledToFit()")

        img_mods = extract_image_modifiers(jsx)
        for mod in img_mods:
            lines.append(f"{ind}    {mod}")

    elif jsx.startswith("<button") or jsx.startswith("<Button"):
        on_click = extract_attr(jsx, "onClick")
        text_content = extract_text_content(jsx)
        text_expr = convert_text_expression(text_content, state_names)

        action = convert_action(on_click, state_names, setters) if on_click else swift_todo("Add button action")
        lines.append(f"{ind}Button {{")
        lines.append(f"{ind}    {action}")
        lines.append(f"{ind}}} label: {{")
        lines.append(f"{ind}    Text({text_expr})")

        btn_mods = extract_tailwind_modifiers(jsx)
        for mod in btn_mods:
            lines.append(f"{ind}        {mod}")

        lines.append(f"{ind}}}")

    elif jsx.startswith("<input") or jsx.startswith("<Input"):
        placeholder = extract_attr(jsx, "placeholder") or "Enter text"
        value_binding = extract_attr(jsx, "value")
        if value_binding and value_binding in state_names:
            lines.append(f'{ind}TextField("{placeholder}", text: ${value_binding})')
        else:
            lines.append(f'{ind}TextField("{placeholder}", text: .constant(""))')
            lines.append(f'{ind}    {swift_todo("Bind to state variable")}')

    elif jsx.startswith("{") and jsx.endswith("}"):
        # Expression: {condition && <X>} or {condition ? <A> : <B>} or {expression}
        inner = jsx[1:-1].strip()
        if "&&" in inner:
            parts = inner.split("&&", 1)
            condition = convert_condition(parts[0].strip(), state_names)
            element = parts[1].strip()
            lines.append(f"{ind}if {condition} {{")
            child_result = process_jsx_element(element, state_names, setters, indent_level + 1)
            lines.append(child_result)
            lines.append(f"{ind}}}")
        elif "?" in inner and ":" in inner:
            parts = inner.split("?", 1)
            condition = convert_condition(parts[0].strip(), state_names)
            branches = parts[1].split(":", 1)
            lines.append(f"{ind}if {condition} {{")
            lines.append(process_jsx_element(branches[0].strip(), state_names, setters, indent_level + 1))
            lines.append(f"{ind}}} else {{")
            lines.append(process_jsx_element(branches[1].strip(), state_names, setters, indent_level + 1))
            lines.append(f"{ind}}}")
        else:
            text_expr = convert_text_expression(inner, state_names)
            lines.append(f"{ind}Text({text_expr})")

    elif jsx.startswith("<a ") or jsx.startswith("<a>"):
        href = extract_attr(jsx, "href")
        text_content = extract_text_content(jsx)
        text_expr = convert_text_expression(text_content, state_names)
        if href:
            lines.append(f"{ind}Link({text_expr}, destination: URL(string: \"{href}\")!)")
        else:
            lines.append(f"{ind}Text({text_expr})")

    elif jsx.startswith("<ul") or jsx.startswith("<ol"):
        children = extract_jsx_children(jsx)
        lines.append(f"{ind}VStack(alignment: .leading, spacing: 8) {{")
        for child in children:
            child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
            if child_result.strip():
                lines.append(child_result)
        lines.append(f"{ind}}}")

    elif jsx.startswith("<li"):
        text_content = extract_text_content(jsx)
        text_expr = convert_text_expression(text_content, state_names)
        lines.append(f"{ind}HStack(alignment: .top, spacing: 8) {{")
        lines.append(f"{ind}    Text(\"•\")")
        lines.append(f"{ind}    Text({text_expr})")
        lines.append(f"{ind}}}")

    elif jsx.startswith("<form"):
        children = extract_jsx_children(jsx)
        lines.append(f"{ind}VStack(spacing: 16) {{")
        for child in children:
            child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
            if child_result.strip():
                lines.append(child_result)
        lines.append(f"{ind}}}")

    elif jsx.startswith("<textarea"):
        placeholder = extract_attr(jsx, "placeholder") or ""
        value_binding = extract_attr(jsx, "value")
        if value_binding and value_binding in state_names:
            lines.append(f'{ind}TextEditor(text: ${value_binding})')
        else:
            lines.append(f'{ind}TextEditor(text: .constant(""))')
        lines.append(f'{ind}    .frame(minHeight: 100)')

    elif jsx.startswith("<select"):
        lines.append(f"{ind}{swift_todo('Convert <select> to Picker')}")
        lines.append(f"{ind}EmptyView()")

    elif jsx.startswith("<label"):
        text_content = extract_text_content(jsx)
        text_expr = convert_text_expression(text_content, state_names)
        lines.append(f"{ind}Text({text_expr})")
        lines.append(f"{ind}    .font(.caption)")
        lines.append(f"{ind}    .foregroundStyle(.secondary)")

    else:
        # Unknown element — check if it's a React component or HTML element
        tag = re.match(r"<([\w.]+)", jsx)
        tag_name = tag.group(1) if tag else "element"

        # Check if it has children — if so, try to process as a container
        children = extract_jsx_children(jsx)
        if children and len(children) > 0 and not _looks_like_raw_html(jsx):
            lines.append(f"{ind}{swift_todo(f'Convert <{tag_name}> element')}")
            lines.append(f"{ind}VStack {{")
            for child in children:
                child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
                if child_result.strip():
                    lines.append(child_result)
            lines.append(f"{ind}}}")
        else:
            text = extract_text_content(jsx)
            if text and not _looks_like_raw_html(text):
                lines.append(f"{ind}{swift_todo(f'Convert <{tag_name}> element')}")
                text_expr = convert_text_expression(text, state_names)
                lines.append(f"{ind}Text({text_expr})")
            else:
                lines.append(f"{ind}{swift_todo(f'Convert <{tag_name}> element')}")
                lines.append(f"{ind}EmptyView()")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Event handler extraction
# ---------------------------------------------------------------------------

def extract_handlers(body: str) -> list[dict]:
    """Extract event handler functions from the component body."""
    handlers = []

    # const handleXxx = (...) => { ... }
    pattern = re.compile(r"const\s+(handle\w+)\s*=\s*\(([^)]*)\)\s*(?::\s*\w+)?\s*=>\s*\{")
    for m in pattern.finditer(body):
        name = m.group(1)
        params = m.group(2).strip()

        start = m.end()
        depth = 1
        i = start
        while i < len(body) and depth > 0:
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
            i += 1
        func_body = body[start:i - 1]

        handlers.append({"name": name, "params": params, "body": func_body})

    # function handleXxx(...) { ... }
    pattern2 = re.compile(r"function\s+(handle\w+)\s*\(([^)]*)\)\s*\{")
    for m in pattern2.finditer(body):
        name = m.group(1)
        params = m.group(2).strip()

        start = m.end()
        depth = 1
        i = start
        while i < len(body) and depth > 0:
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
            i += 1
        func_body = body[start:i - 1]

        handlers.append({"name": name, "params": params, "body": func_body})

    return handlers


def convert_handler(handler: dict, state_vars: list[dict]) -> str:
    """Convert a React event handler to a Swift method."""
    name = to_camel_case(handler["name"])
    body = handler["body"]
    lines = []

    lines.append(f"    func {name}() {{")

    # Detect state mutations
    for sv in state_vars:
        setter = sv.get("setter", f"set{sv['name'][0].upper()}{sv['name'][1:]}")
        if setter in body:
            # Check for toggle: setX(!x)
            toggle_match = re.search(rf"{setter}\s*\(\s*!{sv['name']}\s*\)", body)
            if toggle_match:
                lines.append(f"        {sv['name']}.toggle()")
                continue

            # Check for specific value
            set_match = re.search(rf"{setter}\s*\(([^)]+)\)", body)
            if set_match:
                val = set_match.group(1).strip()
                if val in ("true", "false"):
                    lines.append(f"        {sv['name']} = {val}")
                elif val in ("null", "nil", "undefined"):
                    lines.append(f"        {sv['name']} = nil")
                else:
                    # Replace null/undefined in compound expressions
                    val = val.replace("null", "nil").replace("undefined", "nil")
                    lines.append(f"        {sv['name']} = {val}")

    # Detect localStorage operations
    if "localStorage.setItem" in body:
        ls_match = re.search(r"localStorage\.setItem\s*\([^,]+,\s*([^)]+)\)", body)
        if ls_match:
            lines.append(f"        {swift_todo('Persist to UserDefaults')}")

    if "localStorage.removeItem" in body:
        lines.append(f"        {swift_todo('Remove from UserDefaults')}")

    # Detect navigation
    if "navigate" in body:
        lines.append(f"        {swift_todo('Navigate using NavigationPath')}")

    # If body is empty of detected patterns, add a TODO
    if len(lines) == 1:
        lines.append(f"        {swift_todo('Port handler logic')}")

    lines.append("    }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSX parsing helpers
# ---------------------------------------------------------------------------

def extract_text_content(jsx: str) -> str:
    """Extract text content from an element like <h2>Hello {name}</h2>."""
    # Remove the opening and closing tags
    m = re.match(r"<\w+[^>]*>(.*?)</\w+>", jsx, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def extract_attr(jsx: str, attr_name: str) -> str | None:
    """Extract an attribute value from JSX."""
    # String attribute: attr="value"
    m = re.search(rf'{attr_name}=["\']([^"\']+)["\']', jsx)
    if m:
        return m.group(1)
    # Expression attribute: attr={expression}
    m = re.search(rf'{attr_name}=\{{([^}}]+)\}}', jsx)
    if m:
        return m.group(1).strip()
    return None


def extract_jsx_children(jsx: str) -> list[str]:
    """Extract top-level child elements from a JSX container."""
    # Find the content between the opening and closing tags
    m = re.match(r"<\w+[^>]*>(.*)</\w+\s*>", jsx, re.DOTALL)
    if not m:
        return []

    content = m.group(1).strip()
    children = []
    i = 0

    while i < len(content):
        # Skip whitespace
        while i < len(content) and content[i] in " \t\n\r":
            i += 1
        if i >= len(content):
            break

        if content[i] == "<":
            # HTML/JSX element
            depth = 0
            start = i
            # Handle self-closing tags
            tag_end = content.find(">", i)
            if tag_end != -1 and content[tag_end - 1] == "/":
                children.append(content[start:tag_end + 1])
                i = tag_end + 1
                continue

            # Track nested tags
            depth = 1
            i = tag_end + 1 if tag_end != -1 else i + 1
            while i < len(content) and depth > 0:
                if content[i] == "<":
                    if i + 1 < len(content) and content[i + 1] == "/":
                        depth -= 1
                        if depth == 0:
                            close_end = content.find(">", i)
                            children.append(content[start:close_end + 1])
                            i = close_end + 1
                            break
                    else:
                        # Check for self-closing
                        next_gt = content.find(">", i)
                        if next_gt != -1 and content[next_gt - 1] == "/":
                            i = next_gt + 1
                        else:
                            depth += 1
                            i = next_gt + 1 if next_gt != -1 else i + 1
                else:
                    i += 1

        elif content[i] == "{":
            # Expression block
            depth = 1
            start = i
            i += 1
            while i < len(content) and depth > 0:
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                i += 1
            children.append(content[start:i])

        else:
            # Text content
            start = i
            while i < len(content) and content[i] not in "<{":
                i += 1
            text = content[start:i].strip()
            if text:
                children.append(text)

    return children


# ---------------------------------------------------------------------------
# Tailwind -> SwiftUI modifier conversion
# ---------------------------------------------------------------------------

TAILWIND_TO_SWIFTUI = {
    "p-1": ".padding(4)", "p-2": ".padding(8)", "p-3": ".padding(12)",
    "p-4": ".padding(16)", "p-5": ".padding(20)", "p-6": ".padding(24)",
    "p-8": ".padding(32)",
    "px-2": ".padding(.horizontal, 8)", "px-4": ".padding(.horizontal, 16)",
    "py-1": ".padding(.vertical, 4)", "py-2": ".padding(.vertical, 8)",
    "bg-white": ".background(.white)",
    "bg-gray-100": ".background(Color(.systemGray6))",
    "bg-gray-200": ".background(Color(.systemGray5))",
    "bg-blue-500": ".background(.blue)",
    "bg-blue-100": ".background(.blue.opacity(0.15))",
    "bg-yellow-400": ".background(.yellow)",
    "rounded": ".clipShape(RoundedRectangle(cornerRadius: 4))",
    "rounded-lg": ".clipShape(RoundedRectangle(cornerRadius: 8))",
    "rounded-xl": ".clipShape(RoundedRectangle(cornerRadius: 12))",
    "rounded-full": ".clipShape(Circle())",
    "shadow-md": ".shadow(radius: 4)",
    "shadow-lg": ".shadow(radius: 8)",
    "text-white": ".foregroundStyle(.white)",
    "text-gray-400": ".foregroundStyle(.secondary)",
    "text-gray-500": ".foregroundStyle(.secondary)",
    "text-gray-900": ".foregroundStyle(.primary)",
    "text-red-500": ".foregroundStyle(.red)",
    "text-blue-800": ".foregroundStyle(.blue)",
    "text-yellow-900": ".foregroundStyle(.yellow)",
    "text-center": ".multilineTextAlignment(.center)",
    "text-xs": ".font(.caption2)", "text-sm": ".font(.caption)",
    "text-lg": ".font(.title3)", "text-xl": ".font(.title2)",
    "text-2xl": ".font(.title)",
    "font-bold": ".fontWeight(.bold)", "font-medium": ".fontWeight(.medium)",
    "w-full": ".frame(maxWidth: .infinity)",
    "w-20": ".frame(width: 80)", "h-20": ".frame(height: 80)",
    "h-32": ".frame(height: 128)",
    "object-cover": "", # handled by scaledToFill
    "flex-1": "",  # handled by container
    "gap-2": "", "gap-4": "",  # handled by stack spacing
    "items-center": "",  # handled by stack alignment
    "transition": "",  # handled by .animation
}


def extract_tailwind_modifiers(jsx: str) -> list[str]:
    """Extract SwiftUI modifiers from Tailwind classes in className."""
    class_match = re.search(r'className=["\']([^"\']+)["\']', jsx)
    if not class_match:
        # Check for template literal className
        class_match = re.search(r'className=\{[`"]([^`"]+)[`"]\}', jsx)
    if not class_match:
        return []

    classes = class_match.group(1).split()
    modifiers = []
    seen = set()

    for cls in classes:
        # Strip conditional class prefixes
        cls = cls.strip()
        if cls in TAILWIND_TO_SWIFTUI:
            mod = TAILWIND_TO_SWIFTUI[cls]
            if mod and mod not in seen:
                modifiers.append(mod)
                seen.add(mod)

    return modifiers


def extract_text_modifiers(jsx: str) -> list[str]:
    """Extract text-specific modifiers from Tailwind."""
    modifiers = []
    class_match = re.search(r'className=["\']([^"\']+)["\']', jsx)
    if not class_match:
        return modifiers

    classes = class_match.group(1).split()
    for cls in classes:
        if cls in TAILWIND_TO_SWIFTUI:
            mod = TAILWIND_TO_SWIFTUI[cls]
            if mod:
                modifiers.append(mod)
    return modifiers


def extract_image_modifiers(jsx: str) -> list[str]:
    """Extract image-specific modifiers from Tailwind."""
    modifiers = []
    class_match = re.search(r'className=["\']([^"\']+)["\']', jsx)
    if not class_match:
        return modifiers

    classes = class_match.group(1).split()
    for cls in classes:
        if cls in TAILWIND_TO_SWIFTUI:
            mod = TAILWIND_TO_SWIFTUI[cls]
            if mod:
                modifiers.append(mod)
        # Size extraction
        size_match = re.match(r"[wh]-(\d+)", cls)
        if size_match:
            px = int(size_match.group(1)) * 4
            if cls.startswith("w-"):
                modifiers.append(f".frame(width: {px})")
            else:
                modifiers.append(f".frame(height: {px})")
    return modifiers


def extract_spacing(jsx: str) -> str | None:
    """Extract spacing from Tailwind gap classes."""
    m = re.search(r'gap-(\d+)', jsx)
    if m:
        return str(int(m.group(1)) * 4)
    return None


def extract_alignment(jsx: str) -> str | None:
    """Extract alignment from Tailwind classes."""
    if "items-center" in jsx:
        return "center"
    if "items-start" in jsx:
        return "leading"
    if "items-end" in jsx:
        return "trailing"
    return None


# ---------------------------------------------------------------------------
# Expression conversion
# ---------------------------------------------------------------------------

def _looks_like_raw_html(text: str) -> bool:
    """Check if text looks like unconverted HTML/JSX — shouldn't go in Text()."""
    tag_count = text.count("<")
    return tag_count > 2 or ("</" in text and "style=" in text) or "className=" in text


def convert_text_expression(text: str, state_names: set) -> str:
    """Convert a JSX text expression to Swift string."""
    text = text.strip()

    # Replace JS null/undefined with Swift nil
    text = text.replace("null", "nil").replace("undefined", "nil")

    # If it looks like unconverted JSX/HTML (contains < tags), don't dump it into Text()
    if "<" in text and ">" in text and not text.startswith('"'):
        # This is unconverted JSX — generate a TODO instead of raw HTML in a string
        return '"TODO"'

    # Pure variable reference: {user.name}
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        # Handle optional chaining
        inner = inner.replace("?.", "?.")
        return inner

    # Text with interpolation: Hello {name}!
    if "{" in text:
        # Convert {expr} to \(expr)
        result = re.sub(r"\{([^}]+)\}", lambda m: f"\\({m.group(1).strip()})", text)
        return f'"{result}"'

    # Plain text — escape any inner quotes
    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'


def convert_condition(condition: str, state_names: set) -> str:
    """Convert a JS condition to Swift."""
    condition = condition.strip()

    # Replace JS null/undefined with Swift nil
    condition = condition.replace("=== null", "== nil").replace("!== null", "!= nil")
    condition = condition.replace("=== undefined", "== nil").replace("!== undefined", "!= nil")
    condition = condition.replace("== null", "== nil").replace("!= null", "!= nil")
    condition = condition.replace("=== ", "== ").replace("!== ", "!= ")

    # !value -> value == nil (for optionals) or !value (for booleans)
    if condition.startswith("!"):
        inner = condition[1:].strip()
        if inner in state_names:
            return f"{inner} == nil"
        return f"!{inner}"
    # Truthy check
    if condition in state_names:
        return f"{condition} != nil"
    return condition


def convert_action(on_click: str, state_names: set, setters: dict) -> str:
    """Convert an onClick handler to a Swift action."""
    on_click = on_click.strip()

    # Arrow function: () => navigate(...)
    arrow_match = re.match(r"\(\)\s*=>\s*(.+)", on_click)
    if arrow_match:
        action = arrow_match.group(1).strip()
        if "navigate" in action:
            return swift_todo("NavigationLink or path.append() for navigation")
        # Setter call: setX(!x)
        for setter_name, state_name in setters.items():
            if setter_name in action:
                return f"{state_name}.toggle()"
        return swift_todo(f"Port action: {action}")

    # Direct function reference: handleClick
    if on_click.startswith("handle") or on_click.startswith("on"):
        return f"{to_camel_case(on_click)}()"

    return swift_todo(f"Port action: {on_click}")


# ---------------------------------------------------------------------------
# Inline types
# ---------------------------------------------------------------------------

def extract_inline_types(source: str) -> list[str]:
    """Extract and convert interface definitions that appear before the component."""
    types = []
    pattern = re.compile(
        r"(?:export\s+)?interface\s+(\w+)\s*\{([^}]+)\}",
        re.DOTALL,
    )
    for m in pattern.finditer(source):
        name = m.group(1)
        if "Props" in name:
            continue  # Skip props interfaces — handled as view properties
        body = m.group(2)
        fields = parse_interface_fields(body)
        types.append(convert_inline_struct(name, fields))
    return types


def parse_interface_fields(body: str) -> list[dict]:
    """Parse fields from interface body."""
    fields = []
    for line in body.split("\n"):
        line = line.strip()
        m = re.match(r"(\w+)(\?)?:\s*(.+?);?\s*$", line)
        if m:
            fields.append({
                "name": m.group(1),
                "optional": m.group(2) == "?",
                "type": map_type(m.group(3).rstrip(";")),
            })
    return fields


def convert_inline_struct(name: str, fields: list[dict]) -> str:
    """Convert to a Swift struct."""
    lines = [f"struct {name}: Codable, Identifiable {{"]
    has_id = any(f["name"] == "id" for f in fields)
    if not has_id:
        lines[0] = f"struct {name}: Codable {{"

    for f in fields:
        kw = "var" if f["optional"] else "let"
        opt = "?" if f["optional"] else ""
        lines.append(f"    {kw} {f['name']}: {f['type']}{opt}")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Preview generation
# ---------------------------------------------------------------------------

def generate_preview(view_name: str, component: dict) -> str:
    """Generate a SwiftUI preview."""
    lines = ["#Preview {"]

    # Build initializer with sample values
    args = []
    for prop in component["props"]:
        if prop["default"] is not None:
            continue  # Skip props with defaults
        sample = get_sample_value(prop["type"])
        args.append(f'{prop["name"]}: {sample}')

    args_str = ", ".join(args)
    lines.append(f"    {view_name}({args_str})")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def get_sample_value(swift_type: str) -> str:
    """Get a sample value for a Swift type (for previews)."""
    type_clean = swift_type.rstrip("?")
    samples = {
        "String": '"Sample"',
        "Int": "1",
        "Double": "1.0",
        "Bool": "true",
        "URL": 'URL(string: "https://example.com")!',
        "Date": ".now",
    }
    return samples.get(type_clean, '""')


# ---------------------------------------------------------------------------
# Manifest fallback
# ---------------------------------------------------------------------------

def _cleanup_swift_output(code: str) -> str:
    """
    Post-processing cleanup to remove leaked JavaScript artifacts.
    This catches anything the structural converter missed.
    """
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are clearly leaked JS/TS (not in a comment)
        if not stripped.startswith("//") and not stripped.startswith("*"):
            # Leaked JS: const declarations (not valid Swift keyword)
            if re.match(r"^\s*const\s+", stripped):
                cleaned.append(f"        {swift_todo(f'Port JS logic: {stripped[:60]}')}")
                continue
            # Leaked JSX: raw HTML tags not inside a comment or string
            if re.match(r"^\s*<[A-Z]\w+", stripped) and "Text(" not in stripped:
                cleaned.append(f"        {swift_todo(f'Convert component: {stripped[:50]}')}")
                cleaned.append(f"        EmptyView()")
                continue
            # Leaked JS: arrow functions
            if "() =>" in stripped and "Text(" not in stripped and "//" not in stripped:
                cleaned.append(f"        {swift_todo(f'Port callback: {stripped[:50]}')}")
                continue
            # Leaked JS: .map( or .filter( chains outside comments
            if re.match(r"^\s*\.\w+\(", stripped) and ("map(" in stripped or "filter(" in stripped):
                cleaned.append(f"        {swift_todo(f'Port iteration: {stripped[:50]}')}")
                continue
            # Replace any remaining null/undefined literals
            if " null " in line or " null)" in line or " null}" in line or "= null" in line:
                if "//" not in line:
                    line = line.replace("null", "nil")
            if " undefined " in line or " undefined)" in line or "= undefined" in line:
                if "//" not in line:
                    line = line.replace("undefined", "nil")
        cleaned.append(line)
    return "\n".join(cleaned)


def generate_view_from_manifest(view_name: str, manifest_entry: dict) -> str:
    """Generate a View stub from manifest data."""
    lines = [f"struct {view_name}: View {{"]
    lines.append("")
    lines.append("    var body: some View {")
    lines.append(f"        {swift_todo('Build SwiftUI view from component JSX')}")
    lines.append("        Text(\"TODO\")")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append(f"#Preview {{")
    lines.append(f"    {view_name}()")
    lines.append(f"}}")
    lines.append("")
    return "\n".join(lines)
