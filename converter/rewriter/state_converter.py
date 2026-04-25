"""
State Management Converter — Phase C (BUILD-8)
Converts Zustand stores, Redux slices, Jotai atoms, and React Context providers
to their SwiftUI @Observable equivalents.

Mapping:
  Zustand create(...)       → @Observable class with state properties + actions
  Redux createSlice(...)    → @Observable class with action methods
  Redux configureStore(...) → App-level environment injection comment
  Jotai atom(...)           → @State or @AppStorage
  React createContext(...)  → @Environment with a custom EnvironmentKey
"""

import re
from .swift_helpers import (
    map_type, to_pascal_case, to_camel_case, swift_header, swift_mark,
    swift_todo, format_swift,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def convert_state_file(source: str, relative_path: str, manifest_entry: dict) -> str:
    """Convert a state management file to Swift.

    Detects the library in use and routes to the appropriate converter.
    Returns generated Swift code.
    """
    filename = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    blocks = []

    # Detect which library
    if _uses_zustand(source):
        swift_name = f"{to_pascal_case(filename)}Store.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(convert_zustand_store(source, filename))

    elif _uses_redux_slice(source):
        swift_name = f"{to_pascal_case(filename)}ViewModel.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(convert_redux_slice(source, filename))

    elif _uses_redux_store(source):
        # configureStore — generate a combined app store comment
        swift_name = f"{to_pascal_case(filename)}AppStore.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(convert_redux_configure_store(source, filename))

    elif _uses_jotai(source):
        swift_name = f"{to_pascal_case(filename)}Atoms.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(convert_jotai_atoms(source, filename))

    elif _uses_context(source):
        swift_name = f"{to_pascal_case(filename)}Environment.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(convert_react_context(source, filename))

    else:
        # Fallback: generic @Observable stub
        swift_name = f"{to_pascal_case(filename)}ViewModel.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(_generate_generic_observable(filename))

    return format_swift("\n".join(blocks))


# ---------------------------------------------------------------------------
# Library detection
# ---------------------------------------------------------------------------

def _uses_zustand(source: str) -> bool:
    return bool(re.search(r"from\s+['\"]zustand['\"]|create\s*\(.*set\s*=>", source))


def _uses_redux_slice(source: str) -> bool:
    return bool(re.search(r"createSlice\s*\(", source))


def _uses_redux_store(source: str) -> bool:
    return bool(re.search(r"configureStore\s*\(", source))


def _uses_jotai(source: str) -> bool:
    return bool(re.search(r"from\s+['\"]jotai['\"]|atom\s*\(", source))


def _uses_context(source: str) -> bool:
    return bool(re.search(r"createContext\s*[<(]", source))


# ---------------------------------------------------------------------------
# Zustand → @Observable class
# ---------------------------------------------------------------------------

def convert_zustand_store(source: str, filename: str) -> str:
    """Convert a Zustand store to a Swift @Observable class."""
    store_name = to_pascal_case(filename.replace("store", "").replace("Store", "") or filename) + "Store"
    lines = []

    # Extract state properties from the set callback
    state_props = _extract_zustand_state(source)
    # Extract action methods
    actions = _extract_zustand_actions(source)

    lines.append("// 💡 Learn: @Observable (iOS 17+) replaces Zustand for local/app-wide state.")
    lines.append("//    Inject into the view hierarchy via .environment(store) and")
    lines.append("//    read with @Environment(MyStore.self) in child views.")
    lines.append("")
    lines.append("@Observable")
    lines.append(f"final class {store_name} {{")
    lines.append("")

    if state_props:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")
        for prop in state_props:
            lines.append(f"    {prop}")
        lines.append("")
    else:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")
        lines.append(f"    {swift_todo('Add state properties')}")
        lines.append("")

    lines.append(f"    {swift_mark('Actions')}")
    lines.append("")

    if actions:
        for action in actions:
            lines.append(action)
            lines.append("")
    else:
        lines.append(f"    {swift_todo('Add action methods')}")
        lines.append("")

    lines.append("}")
    lines.append("")
    lines.append("// Usage:")
    lines.append(f"// 1. Create in App: @State private var store = {store_name}()")
    lines.append(f"// 2. Inject: .environment(store)")
    lines.append(f"// 3. Read in views: @Environment({store_name}.self) private var store")
    lines.append("")

    return "\n".join(lines)


def _extract_zustand_state(source: str) -> list[str]:
    """Extract initial state properties from a Zustand store."""
    props = []
    # Match set callback body: create((set) => ({ prop: value, ... }))
    store_match = re.search(r"create\s*(?:<[^>]*>)?\s*\(\s*(?:async\s*)?\(?\s*set\s*\)?\s*=>\s*\(?\s*\{", source)
    if not store_match:
        return props

    start = store_match.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    body = source[start:i - 1]

    # Extract plain property assignments (not functions)
    prop_pattern = re.compile(r"^\s*(\w+)\s*:\s*([^,({]+),?$", re.MULTILINE)
    for m in prop_pattern.finditer(body):
        name = m.group(1)
        value = m.group(2).strip()
        if name in ("set", "get"):
            continue
        # Skip if it looks like a function
        if "=>" in value or "function" in value:
            continue
        swift_type = _infer_swift_type_from_value(value)
        swift_val = _convert_js_value_to_swift(value)
        props.append(f"var {name}: {swift_type} = {swift_val}")

    return props


def _extract_zustand_actions(source: str) -> list[str]:
    """Extract action methods from a Zustand store."""
    actions = []
    # Match arrow function properties: actionName: (args) => { ... }
    action_pattern = re.compile(
        r"(\w+)\s*:\s*(?:async\s+)?\(([^)]*)\)\s*=>\s*\{"
    )
    store_match = re.search(r"create\s*(?:<[^>]*>)?\s*\(\s*\(?\s*set\s*\)?\s*=>\s*\(?\s*\{", source)
    body_start = store_match.end() if store_match else 0

    for m in action_pattern.finditer(source, body_start):
        name = m.group(1)
        params_str = m.group(2).strip()
        if name in ("set", "get"):
            continue
        is_async = "async" in source[max(0, m.start() - 5):m.start()]

        # Extract function body
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        func_body = source[start:i - 1]

        params = _convert_params(params_str)
        async_kw = "async " if is_async else ""
        method_lines = [f"    func {to_camel_case(name)}({params}) {async_kw}{{"]

        # Detect set() calls for state updates
        set_calls = re.findall(r"set\s*\(\s*\{([^}]+)\}", func_body)
        for sc in set_calls:
            for item in sc.split(","):
                item = item.strip()
                if ":" in item:
                    prop, val = item.split(":", 1)
                    prop = prop.strip()
                    val = val.strip()
                    if val in ("true", "false") or val.replace(".", "").isdigit():
                        method_lines.append(f"        {prop} = {val}")
                    else:
                        method_lines.append(f"        {swift_todo(f'Set {prop} = {val}')}")

        if not set_calls:
            method_lines.append(f"        {swift_todo(f'Port action: {name}')}")

        method_lines.append("    }")
        actions.append("\n".join(method_lines))

    return actions


# ---------------------------------------------------------------------------
# Redux createSlice → @Observable class
# ---------------------------------------------------------------------------

def convert_redux_slice(source: str, filename: str) -> str:
    """Convert a Redux createSlice to a Swift @Observable class."""
    # Extract slice name
    name_match = re.search(r"createSlice\s*\(\s*\{[^}]*name\s*:\s*['\"](\w+)['\"]", source, re.DOTALL)
    slice_name = to_pascal_case(name_match.group(1)) if name_match else to_pascal_case(filename)
    class_name = f"{slice_name}ViewModel"
    lines = []

    lines.append("// 💡 Learn: Redux createSlice → @Observable class with typed action methods.")
    lines.append("//    SwiftUI's @Observable + @Environment eliminates the need for Redux in iOS apps.")
    lines.append("//    Actions become plain Swift methods — no reducers, no dispatch needed.")
    lines.append("")
    lines.append("@Observable")
    lines.append(f"final class {class_name} {{")
    lines.append("")

    # Extract initialState
    init_match = re.search(r"initialState\s*:\s*(\{[^}]+\})", source, re.DOTALL)
    if init_match:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")
        state_body = init_match.group(1)
        props = _parse_object_properties(state_body)
        for prop in props:
            lines.append(f"    {prop}")
        lines.append("")
    else:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")
        lines.append(f"    {swift_todo('Add state properties from initialState')}")
        lines.append("")

    # Extract reducers → methods
    lines.append(f"    {swift_mark('Actions (formerly reducers)')}")
    lines.append("")
    reducers_match = re.search(r"reducers\s*:\s*\{", source)
    if reducers_match:
        start = reducers_match.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        reducers_body = source[start:i - 1]

        reducer_pattern = re.compile(r"(\w+)\s*:\s*\(state\s*(?:,\s*action)?\)\s*=>\s*\{")
        for m in reducer_pattern.finditer(reducers_body):
            action_name = m.group(1)
            has_action = "action" in m.group(0)
            param = "_ value: Any" if has_action else ""
            lines.append(f"    func {to_camel_case(action_name)}({param}) {{")
            lines.append(f"        {swift_todo(f'Port reducer: {action_name}')}")
            lines.append("    }")
            lines.append("")
    else:
        lines.append(f"    {swift_todo('Port reducer methods')}")
        lines.append("")

    lines.append("}")
    lines.append("")
    lines.append(f"// Usage:")
    lines.append(f"// 1. @State private var vm = {class_name}() in parent view")
    lines.append(f"// 2. .environment(vm) to inject")
    lines.append(f"// 3. @Environment({class_name}.self) in child views")
    lines.append("")
    return "\n".join(lines)


def convert_redux_configure_store(source: str, filename: str) -> str:
    """Convert a Redux configureStore to a Swift app-level environment setup comment."""
    lines = []
    lines.append("// 💡 Learn: Redux configureStore → inject @Observable ViewModels via .environment()")
    lines.append("//    Instead of one global store, inject each ViewModel at the appropriate")
    lines.append("//    level of the view hierarchy using .environment().")
    lines.append("")
    lines.append("// Example App-level setup:")
    lines.append("//")
    lines.append("// @main")
    lines.append("// struct MyApp: App {")
    lines.append("//     @State private var authStore = AuthViewModel()")
    lines.append("//     @State private var cartStore = CartViewModel()")
    lines.append("//")
    lines.append("//     var body: some Scene {")
    lines.append("//         WindowGroup {")
    lines.append("//             ContentView()")
    lines.append("//                 .environment(authStore)")
    lines.append("//                 .environment(cartStore)")
    lines.append("//         }")
    lines.append("//     }")
    lines.append("// }")
    lines.append("")
    lines.append(f"{swift_todo('Extract each Redux slice into its own @Observable ViewModel')}")
    lines.append(f"{swift_todo('Inject each ViewModel at the appropriate view hierarchy level')}")
    lines.append("")

    # List detected slice imports
    slice_imports = re.findall(r"import\s+\{?\s*(\w+Reducer|\w+Slice)\s*\}?\s+from", source)
    if slice_imports:
        lines.append("// Slices to convert:")
        for s in slice_imports:
            lines.append(f"//   {s} → {to_pascal_case(s.replace('Reducer', '').replace('Slice', ''))}ViewModel")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Jotai atoms → @State / @AppStorage
# ---------------------------------------------------------------------------

def convert_jotai_atoms(source: str, filename: str) -> str:
    """Convert Jotai atom definitions to Swift @State / @AppStorage guidance."""
    lines = []

    lines.append("// 💡 Learn: Jotai atoms → @State (local) or @AppStorage (persisted)")
    lines.append("//    Each atom becomes a @State property in the view that owns it.")
    lines.append("//    For cross-view sharing, lift the state to a shared @Observable class")
    lines.append("//    and inject it via .environment().")
    lines.append("")

    # Extract atom declarations
    atoms = _extract_jotai_atoms(source)
    if atoms:
        for atom in atoms:
            lines.append(atom)
        lines.append("")
    else:
        lines.append(f"{swift_todo('Port Jotai atoms to @State or @AppStorage properties')}")
        lines.append("")

    lines.append("// Atom usage in views:")
    lines.append("// React:   const [value, setValue] = useAtom(myAtom)")
    lines.append("// Swift:   @State private var value = initialValue")
    lines.append("//          or @AppStorage(\"key\") var value = initialValue  // for persistence")
    lines.append("")

    return "\n".join(lines)


def _extract_jotai_atoms(source: str) -> list[str]:
    """Extract atom declarations and produce Swift property hints."""
    result = []
    # const myAtom = atom(initialValue)
    atom_pattern = re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*atom\s*(?:<[^>]*>)?\s*\(([^)]*)\)")
    for m in atom_pattern.finditer(source):
        name = m.group(1)
        initial = m.group(2).strip()
        swift_type = _infer_swift_type_from_value(initial)
        swift_val = _convert_js_value_to_swift(initial)
        # Detect if likely persisted (contains "storage" / "persist" context)
        if "storage" in name.lower() or "persist" in name.lower() or "pref" in name.lower():
            clean_name = name.rstrip("Atom")
            result.append(f"// {name} → @AppStorage (persisted)")
            result.append(f'// @AppStorage("{to_camel_case(clean_name)}") var {to_camel_case(clean_name)}: {swift_type} = {swift_val}')
        else:
            result.append(f"// {name} → @State")
            result.append(f"// @State private var {to_camel_case(name.rstrip('Atom'))}: {swift_type} = {swift_val}")
        result.append("")
    return result


# ---------------------------------------------------------------------------
# React Context → @Environment with custom EnvironmentKey
# ---------------------------------------------------------------------------

def convert_react_context(source: str, filename: str) -> str:
    """Convert React Context to a SwiftUI @Environment pattern."""
    ctx_name_m = re.search(r"(?:const|let)\s+(\w+Context)\s*=\s*createContext", source)
    ctx_raw = ctx_name_m.group(1) if ctx_name_m else to_pascal_case(filename) + "Context"
    ctx_name = ctx_raw.replace("Context", "")
    value_class = f"{to_pascal_case(ctx_name)}ViewModel"
    key_name = f"{ctx_name[0].lower()}{ctx_name[1:]}ViewModelKey"
    lines = []

    lines.append("// 💡 Learn: React Context → @Environment with a custom EnvironmentKey.")
    lines.append("//    EnvironmentKey defines the default value; .environment() injects it;")
    lines.append("//    @Environment reads it. This is SwiftUI's built-in DI system.")
    lines.append("")

    # Generate the @Observable ViewModel for the context value
    lines.append("@Observable")
    lines.append(f"final class {value_class} {{")
    lines.append("")
    lines.append(f"    {swift_mark('State')}")
    lines.append("")

    # Extract default value from createContext(defaultValue)
    default_match = re.search(r"createContext\s*(?:<[^>]*>)?\s*\(\s*(\{[^}]+\})", source, re.DOTALL)
    if default_match:
        props = _parse_object_properties(default_match.group(1))
        for prop in props:
            lines.append(f"    {prop}")
    else:
        lines.append(f"    {swift_todo('Add context value properties')}")

    lines.append("")
    lines.append(f"    {swift_mark('Methods')}")
    lines.append("")
    lines.append(f"    {swift_todo('Add context methods / actions')}")
    lines.append("")
    lines.append("}")
    lines.append("")

    # Generate EnvironmentKey
    lines.append(f"// MARK: - Environment Key")
    lines.append("")
    lines.append(f"private struct {key_name.capitalize()}Key: EnvironmentKey {{")
    lines.append(f"    static let defaultValue = {value_class}()")
    lines.append("}")
    lines.append("")
    lines.append("extension EnvironmentValues {")
    lines.append(f"    var {to_camel_case(ctx_name)}: {value_class} {{")
    lines.append(f"        get {{ self[{key_name.capitalize()}Key.self] }}")
    lines.append(f"        set {{ self[{key_name.capitalize()}Key.self] = newValue }}")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Extract Provider component if present
    provider_match = re.search(r"(?:const|function)\s+(\w+Provider)\s*[=(]", source)
    if provider_match:
        provider_name = provider_match.group(1)
        view_name = provider_name.replace("Provider", "")
        lines.append(f"// Former <{provider_name}> wrapper:")
        lines.append(f"// Replace with .environment(\\. {to_camel_case(ctx_name)}, {value_class}()) on your root view")
        lines.append(f"// or inject via: .environment(myViewModel)")
        lines.append("")

    lines.append("// Usage in views:")
    lines.append(f"// @Environment(\\. {to_camel_case(ctx_name)}) private var {to_camel_case(ctx_name)}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generic @Observable fallback
# ---------------------------------------------------------------------------

def _generate_generic_observable(filename: str) -> str:
    vm_name = to_pascal_case(filename) + "ViewModel"
    return "\n".join([
        "// 💡 Learn: @Observable replaces external state management in SwiftUI",
        "",
        "@Observable",
        f"final class {vm_name} {{",
        "",
        f"    {swift_mark('State')}",
        "",
        f"    {swift_todo('Add state properties')}",
        "",
        f"    {swift_mark('Methods')}",
        "",
        f"    {swift_todo('Add action methods')}",
        "",
        "}",
        "",
    ])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _infer_swift_type_from_value(value: str) -> str:
    value = value.strip()
    if value in ("true", "false"):
        return "Bool"
    if value.isdigit():
        return "Int"
    if re.match(r"^\d+\.\d+$", value):
        return "Double"
    if value.startswith('"') or value.startswith("'"):
        return "String"
    if value in ("null", "nil", "undefined", ""):
        return "Any?"
    if value.startswith("["):
        return "[Any]"
    if value.startswith("{"):
        return "[String: Any]"
    return "Any"


def _convert_js_value_to_swift(value: str) -> str:
    value = value.strip()
    if value in ("null", "nil", "undefined", ""):
        return "nil"
    if value in ("true", "false"):
        return value
    if value.isdigit() or re.match(r"^\d+\.\d+$", value):
        return value
    if value.startswith('"') or value.startswith("'"):
        return f'"{value.strip(chr(34) + chr(39))}"'
    if value.startswith("["):
        return "[]"
    if value.startswith("{"):
        return "[:]"
    return "nil"


def _parse_object_properties(obj_str: str) -> list[str]:
    """Parse a JS object literal and return Swift property declarations."""
    result = []
    prop_pattern = re.compile(r"^\s*(\w+)\s*:\s*(.+?)(?:,\s*$|$)", re.MULTILINE)
    for m in prop_pattern.finditer(obj_str):
        name = m.group(1)
        value = m.group(2).strip().rstrip(",")
        if "=>" in value or "function" in value:
            result.append(f"    {swift_todo(f'Add method: {name}')}")
            continue
        swift_type = _infer_swift_type_from_value(value)
        swift_val = _convert_js_value_to_swift(value)
        result.append(f"var {name}: {swift_type} = {swift_val}")
    return result


def _convert_params(params_str: str) -> str:
    if not params_str.strip():
        return ""
    parts = []
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        if ":" in p:
            name, ts_type = p.split(":", 1)
            parts.append(f"_ {name.strip()}: {map_type(ts_type.strip())}")
        else:
            parts.append(f"_ {p.split('=')[0].strip()}: Any")
    return ", ".join(parts)
