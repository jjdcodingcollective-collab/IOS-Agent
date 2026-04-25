"""
Hook Converter — Converts React custom hooks to @Observable ViewModel classes.
Transforms useState → properties, useEffect → async methods, callbacks → methods.
"""

import re
from .swift_helpers import (
    map_type, to_pascal_case, to_camel_case, swift_header, swift_mark,
    swift_todo, format_swift,
)


def convert_hook_file(source: str, relative_path: str, manifest_entry: dict) -> str:
    """
    Convert a TypeScript custom hook file to a Swift @Observable ViewModel.
    Returns the generated Swift code.
    """
    filename = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    blocks = []

    # Extract hooks from the file
    hooks = extract_hooks(source)

    if not hooks:
        # Fallback: generate from manifest patterns
        vm_name = to_pascal_case(filename.replace("use", "")) + "ViewModel"
        swift_name = f"{vm_name}.swift"
        blocks.append(swift_header(swift_name))
        blocks.append("import Foundation\nimport SwiftUI\n")
        blocks.append(generate_viewmodel_from_manifest(vm_name, manifest_entry))
        return format_swift("\n".join(blocks))

    # Use the primary hook (usually the provider/implementation)
    primary_hook = hooks[-1] if len(hooks) > 1 else hooks[0]
    vm_name = hook_to_viewmodel_name(primary_hook["name"])
    swift_name = f"{vm_name}.swift"

    blocks.append(swift_header(swift_name))
    blocks.append("import Foundation\nimport SwiftUI\n")

    # Convert the hook to a ViewModel
    blocks.append(convert_hook_to_viewmodel(primary_hook, source))

    return format_swift("\n".join(blocks))


# ---------------------------------------------------------------------------
# Hook extraction
# ---------------------------------------------------------------------------

def extract_hooks(source: str) -> list[dict]:
    """Extract custom hook functions from source."""
    hooks = []

    # Match: export function useXxx(...) or function useXxx(...)
    pattern = re.compile(
        r"(?:export\s+)?function\s+(use\w+)\s*\(([^)]*)\)\s*(?::\s*(\w[^\{]*))?(?:\s*\{)",
        re.MULTILINE,
    )

    for m in pattern.finditer(source):
        name = m.group(1)
        params = m.group(2).strip()
        return_type = m.group(3).strip() if m.group(3) else None

        # Extract body
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[start:i - 1]

        hooks.append({
            "name": name,
            "params": params,
            "return_type": return_type,
            "body": body,
        })

    return hooks


def hook_to_viewmodel_name(hook_name: str) -> str:
    """Convert useAuth -> AuthViewModel, useArticleList -> ArticleListViewModel."""
    # Strip 'use' prefix
    name = re.sub(r"^use", "", hook_name)
    # Strip 'Provider' suffix if present
    name = re.sub(r"Provider$", "", name)
    return to_pascal_case(name) + "ViewModel"


# ---------------------------------------------------------------------------
# Hook -> ViewModel conversion
# ---------------------------------------------------------------------------

def convert_hook_to_viewmodel(hook: dict, full_source: str) -> str:
    """Convert a single hook to an @Observable ViewModel class."""
    vm_name = hook_to_viewmodel_name(hook["name"])
    body = hook["body"]
    lines = []

    # Extract useState calls -> properties
    state_vars = extract_use_state(body)

    # Detect if this ViewModel does async data fetching
    inner_functions = extract_inner_functions(body)
    api_calls = extract_api_calls_from_body(body)
    effects = extract_use_effects(body)
    has_async_data = bool(api_calls) or any(f["is_async"] for f in inner_functions)
    has_mount_effect = any(e["type"] == "mount" for e in effects)

    # Determine the primary data type for LoadState
    primary_data_type = _detect_primary_data_type(state_vars)

    lines.append("// 💡 Learn: @Observable (iOS 17+) replaces the older ObservableObject/@Published pattern.")
    lines.append("//    SwiftUI automatically tracks which properties each view reads and only")
    lines.append("//    re-renders when those specific properties change. No manual @Published needed.")
    lines.append("")
    lines.append(f"@Observable")
    lines.append(f"class {vm_name} {{")
    lines.append("")

    if state_vars:
        lines.append(f"    {swift_mark('State')}")
        lines.append("")

        # Phase B: If there's async data fetching, use LoadState for the
        # primary data property instead of separate isLoading/error/data vars
        if has_async_data and primary_data_type:
            # Generate LoadState property for the primary data
            load_state_emitted = False
            for sv in state_vars:
                name = sv["name"]
                # Detect loading/error state vars — replace with LoadState
                if name in ("isLoading", "loading"):
                    if not load_state_emitted:
                        lines.append(f"    // 💡 Learn: LoadState<T> replaces separate isLoading/error/data properties.")
                        lines.append(f"    //    It makes illegal states unrepresentable — you can't be loading AND have an error.")
                        lines.append(f"    var state: LoadState<{primary_data_type}> = .idle")
                        load_state_emitted = True
                    continue
                elif name in ("error", "errorMessage"):
                    continue  # Covered by LoadState
                else:
                    lines.append(f"    {sv['swift_declaration']}")
            if not load_state_emitted:
                # No isLoading var found, but there's async work — add LoadState anyway
                lines.append(f"    var state: LoadState<{primary_data_type}> = .idle")
        else:
            for sv in state_vars:
                lines.append(f"    {sv['swift_declaration']}")

        lines.append("")

    # Extract computed properties from return statement
    computed = extract_computed_from_return(body)
    if computed:
        lines.append(f"    {swift_mark('Computed Properties')}")
        lines.append("")
        for c in computed:
            lines.append(f"    {c}")
        lines.append("")

    # Generate init if there's a mount effect
    if has_mount_effect:
        lines.append(f"    {swift_mark('Initialization')}")
        lines.append("")
        lines.append("    init() {")
        lines.append("        Task { await loadInitialData() }")
        lines.append("    }")
        lines.append("")

    # Generate async methods
    lines.append(f"    {swift_mark('Methods')}")
    lines.append("")

    # Mount effect -> loadInitialData
    if has_mount_effect:
        lines.append("    func loadInitialData() async {")
        mount_effects = [e for e in effects if e["type"] == "mount"]
        for effect in mount_effects:
            for call in extract_function_calls(effect["body"]):
                if call in [f["name"] for f in inner_functions]:
                    lines.append(f"        await {to_camel_case(call)}()")
                else:
                    lines.append(f"        {swift_todo(f'Port: {call}()')}")
        if not any(extract_function_calls(e["body"]) for e in mount_effects):
            lines.append(f"        {swift_todo('Port mount effect logic')}")
        lines.append("    }")
        lines.append("")

    # Convert inner functions to methods — use LoadState-aware version
    for func in inner_functions:
        lines.append(convert_inner_function(func, state_vars, use_load_state=has_async_data))
        lines.append("")

    # If no inner functions but there are API calls, generate LoadState-aware stubs
    if not inner_functions and api_calls:
        for call in api_calls:
            lines.append(f"    {swift_todo(f'Implement API call: {call}')}")
            lines.append(f"    func fetchData() async {{")
            lines.append(f"        state = .loading")
            lines.append(f"        do {{")
            lines.append(f"            {swift_todo('Call APIClient here')}")
            lines.append(f"            // let result: YourType = try await APIClient.shared.get(url)")
            lines.append(f"            // state = .loaded(result)")
            lines.append(f"        }} catch {{")
            lines.append(f"            state = .error(error)")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _detect_primary_data_type(state_vars: list[dict]) -> str | None:
    """Detect the primary data type from state variables for LoadState<T>.

    Looks for the main data-carrying state var (not isLoading, error, etc.)
    and returns its Swift type.
    """
    skip_names = {"isLoading", "loading", "error", "errorMessage", "isError"}
    for sv in state_vars:
        if sv["name"] in skip_names:
            continue
        swift_type = sv["swift_type"]
        # Return the first non-trivial data type
        if swift_type not in ("Bool", "String") or sv["name"] not in ("isLoading", "loading"):
            return swift_type
    return "Any"


# ---------------------------------------------------------------------------
# useState extraction
# ---------------------------------------------------------------------------

def extract_use_state(body: str) -> list[dict]:
    """Extract useState calls and convert to Swift property declarations."""
    states = []
    # Match: const [name, setName] = useState<Type>(initialValue)
    pattern = re.compile(
        r"const\s+\[(\w+),\s*set\w+\]\s*=\s*useState(?:<([^>]+)>)?\s*\(([^)]*)\)"
    )
    for m in pattern.finditer(body):
        name = m.group(1)
        ts_type = m.group(2)
        initial = m.group(3).strip()

        swift_type, swift_initial = convert_state_init(name, ts_type, initial)

        states.append({
            "name": name,
            "swift_type": swift_type,
            "swift_initial": swift_initial,
            "swift_declaration": f"var {name}: {swift_type} = {swift_initial}",
        })
    return states


def convert_state_init(name: str, ts_type: str | None, initial: str) -> tuple[str, str]:
    """Convert useState type and initial value to Swift.
    Fix #6: Ensures all nil-initialized state consistently gets ? suffix."""
    # Determine type
    if ts_type:
        swift_type = map_type(ts_type)
    elif initial in ("true", "false"):
        swift_type = "Bool"
    elif initial.isdigit():
        swift_type = "Int"
    elif initial.startswith('"') or initial.startswith("'"):
        swift_type = "String"
    elif initial in ("null", "nil", ""):
        swift_type = "Any?"
    elif initial.startswith("["):
        swift_type = "[Any]"
    else:
        swift_type = "Any"

    # Determine initial value
    if initial in ("null", "nil", ""):
        # Fix #6: Always ensure ? suffix for nil-initialized state
        if not swift_type.endswith("?"):
            swift_type += "?"
        swift_initial = "nil"
    elif initial == "true":
        swift_initial = "true"
    elif initial == "false":
        swift_initial = "false"
    elif initial.isdigit():
        swift_initial = initial
    elif initial.startswith('"') or initial.startswith("'"):
        clean = initial.strip("\"'")
        swift_initial = f'"{clean}"'
    elif initial.startswith("["):
        swift_initial = "[]"
    else:
        swift_initial = initial

    # Fix #6: If the TS type itself contained | null or | undefined,
    # map_type already added ?, but ensure initial value matches
    if swift_type.endswith("?") and swift_initial not in ("nil", "[]"):
        # Type is optional but has a non-nil initial — that's fine, keep it
        pass
    elif "| null" in (ts_type or "") or "| undefined" in (ts_type or ""):
        if not swift_type.endswith("?"):
            swift_type += "?"

    return swift_type, swift_initial


# ---------------------------------------------------------------------------
# useEffect extraction
# ---------------------------------------------------------------------------

def extract_use_effects(body: str) -> list[dict]:
    """Extract useEffect calls and classify them."""
    effects = []
    # Match: useEffect(() => { ... }, [deps])
    pattern = re.compile(r"useEffect\s*\(\s*(?:async\s*)?\(\)\s*=>\s*\{")

    for m in pattern.finditer(body):
        start = m.end()
        depth = 1
        i = start
        while i < len(body) and depth > 0:
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
            i += 1
        effect_body = body[start:i - 1]

        # Find the dependency array
        remaining = body[i:i + 50]
        deps_match = re.search(r",\s*\[([^\]]*)\]", remaining)
        deps = [d.strip() for d in deps_match.group(1).split(",") if d.strip()] if deps_match else None

        effect_type = "mount" if deps is not None and len(deps) == 0 else "dependency" if deps else "every_render"

        effects.append({
            "type": effect_type,
            "deps": deps or [],
            "body": effect_body,
        })

    return effects


# ---------------------------------------------------------------------------
# Inner function extraction
# ---------------------------------------------------------------------------

def extract_inner_functions(body: str) -> list[dict]:
    """Extract inner function definitions from the hook body."""
    functions = []
    # async function name(...) { ... }
    pattern = re.compile(r"(async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{")

    for m in pattern.finditer(body):
        is_async = bool(m.group(1))
        name = m.group(2)
        params = m.group(3).strip()

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

        functions.append({
            "name": name,
            "is_async": is_async,
            "params": params,
            "body": func_body,
        })

    # Also match: const name = async (...) => { ... }
    arrow_pattern = re.compile(r"(?:const|let)\s+(\w+)\s*=\s*(async\s+)?\(([^)]*)\)\s*=>\s*\{")
    for m in arrow_pattern.finditer(body):
        name = m.group(1)
        is_async = bool(m.group(2))
        params = m.group(3).strip()

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

        # Skip setter functions (setXxx)
        if name.startswith("set") and name[3:4].isupper():
            continue

        functions.append({
            "name": name,
            "is_async": is_async,
            "params": params,
            "body": func_body,
        })

    return functions


def convert_inner_function(func: dict, state_vars: list[dict], use_load_state: bool = False) -> str:
    """Convert an inner function to a Swift method.

    Args:
        func: Extracted function dict with name, is_async, params, body
        state_vars: Extracted state variables from the hook
        use_load_state: If True, wrap async calls with LoadState transitions
    """
    name = to_camel_case(func["name"])
    is_async = func["is_async"]
    body = func["body"]
    lines = []

    # Parse parameters
    params = []
    if func["params"]:
        for p in func["params"].split(","):
            p = p.strip()
            if not p:
                continue
            parts = p.split(":")
            pname = parts[0].strip()
            ptype = map_type(parts[1].strip()) if len(parts) > 1 else "String"
            params.append(f"{pname}: {ptype}")

    params_str = ", ".join(params)
    async_kw = "async " if is_async else ""

    # Convert body — detect key patterns
    has_try = "await" in body or "fetch" in body or "axios" in body

    # Only add throws if we're NOT using LoadState (LoadState catches internally)
    throws_kw = ""
    if not use_load_state and ("throw" in body or "try" in body or is_async):
        throws_kw = "throws "

    lines.append(f"    func {name}({params_str}) {async_kw}{throws_kw}{{")

    if has_try:
        # Phase B: Use LoadState transitions for async data fetching
        if use_load_state:
            lines.append("        state = .loading")
        lines.append("        do {")

        # Detect fetch/API calls
        fetch_matches = list(re.finditer(r"(?:await\s+)?fetch\s*\(\s*[`'\"]([^`'\"]+)", body))
        if fetch_matches:
            for fm in fetch_matches:
                url = fm.group(1)
                lines.append(f"            {swift_todo(f'Call API: {url}')}")
                lines.append(f"            // let result: ResponseType = try await APIClient.shared.get(url)")

        # Detect state updates
        for sv in state_vars:
            setter = f"set{sv['name'][0].upper()}{sv['name'][1:]}"
            if setter in body:
                # Find what it's set to
                set_match = re.search(rf"{setter}\s*\(([^)]+)\)", body)
                if set_match:
                    val = set_match.group(1).strip()
                    if val in ("null", "nil"):
                        lines.append(f"            {sv['name']} = nil")
                    elif val == "data" or val.startswith("data."):
                        sv_name = sv["name"]
                        if use_load_state:
                            lines.append(f"            {swift_todo(f'Assign decoded response: state = .loaded(result)')}")
                        else:
                            lines.append(f"            {swift_todo(f'Assign decoded response to {sv_name}')}")
                    elif val == "true" or val == "false":
                        lines.append(f"            {sv['name']} = {val}")
                    else:
                        sv_name = sv["name"]
                        lines.append(f"            {swift_todo(f'Set {sv_name} = {val}')}")

        if use_load_state:
            lines.append("            // state = .loaded(result)")
        lines.append("        } catch {")
        if use_load_state:
            lines.append("            state = .error(error)")
        else:
            lines.append(f"            {swift_todo('Handle error')}")
            lines.append("            print(\"Error in \\(#function): \\(error)\")")
        lines.append("        }")
    else:
        # Simple synchronous function
        for sv in state_vars:
            setter = f"set{sv['name'][0].upper()}{sv['name'][1:]}"
            if setter in body:
                set_match = re.search(rf"{setter}\s*\(([^)]+)\)", body)
                if set_match:
                    val = set_match.group(1).strip()
                    if val in ("null", "nil"):
                        lines.append(f"        {sv['name']} = nil")
                    elif val == "true" or val == "false":
                        lines.append(f"        {sv['name']} = {val}")
                    else:
                        lines.append(f"        {sv['name']} = {val}")

        # Detect localStorage operations
        if "localStorage.setItem" in body:
            ls_match = re.search(r"localStorage\.setItem\s*\(\s*[`'\"]([^`'\"]+)[`'\"]", body)
            if ls_match:
                key = ls_match.group(1)
                todo_msg = f"Replace with: UserDefaults.standard.set(value, forKey: \"{key}\")"
                lines.append(f"        {swift_todo(todo_msg)}")

        if "localStorage.removeItem" in body:
            ls_match = re.search(r"localStorage\.removeItem\s*\(\s*[`'\"]([^`'\"]+)[`'\"]", body)
            if ls_match:
                key = ls_match.group(1)
                lines.append(f'        UserDefaults.standard.removeObject(forKey: "{key}")')

        if not any(line.strip() for line in lines[1:]):
            lines.append(f"        {swift_todo('Port function logic')}")

    lines.append("    }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_function_calls(body: str) -> list[str]:
    """Extract function calls from a body."""
    calls = re.findall(r"\b(\w+)\s*\(", body)
    # Filter out keywords and common non-functions
    skip = {"if", "for", "while", "switch", "catch", "return", "console", "JSON", "async", "await", "try", "new"}
    return [c for c in calls if c not in skip and not c[0].isupper()]


def extract_api_calls_from_body(body: str) -> list[str]:
    """Extract API call URLs from body."""
    urls = re.findall(r"fetch\s*\(\s*[`'\"]([^`'\"]+)", body)
    urls += re.findall(r"axios\.\w+\s*\(\s*[`'\"]([^`'\"]+)", body)
    return urls


def extract_computed_from_return(body: str) -> list[str]:
    """Extract computed properties from the return statement."""
    computed = []
    # Look for return { ...state, isAuthenticated: !!user }
    return_match = re.search(r"return\s*\{([^}]+)\}", body)
    if return_match:
        for item in return_match.group(1).split(","):
            item = item.strip()
            if ":" in item:
                name, expr = item.split(":", 1)
                name = name.strip()
                expr = expr.strip()
                # Simple boolean computed
                if expr.startswith("!!"):
                    var_name = expr[2:].strip()
                    computed.append(f"var {name}: Bool {{ {var_name} != nil }}")
    return computed


def generate_viewmodel_from_manifest(vm_name: str, manifest_entry: dict) -> str:
    """Generate a ViewModel stub from manifest data when source parsing fails."""
    lines = [f"@Observable", f"class {vm_name} {{", ""]

    patterns = manifest_entry.get("patterns", [])
    state_patterns = [p for p in patterns if p["pattern_type"] == "hook" and p["name"] == "useState"]
    api_patterns = [p for p in patterns if p["pattern_type"] == "api_call"]

    lines.append(f"    {swift_mark('State')}")
    lines.append("")

    if api_patterns:
        # Use LoadState for ViewModels that fetch data
        lines.append("    var state: LoadState<Any> = .idle")
    if state_patterns:
        for i, _ in enumerate(state_patterns):
            lines.append(f"    {swift_todo(f'Add state property {i + 1}')}")
            lines.append(f"    var property{i + 1}: Any?")
    lines.append("")

    lines.append(f"    {swift_mark('Methods')}")
    lines.append("")

    if api_patterns:
        for p in api_patterns:
            url = p.get("details", {}).get("url", "/endpoint")
            lines.append(f"    {swift_todo(f'Implement: {url}')}")
            lines.append(f"    func fetchData() async {{")
            lines.append(f"        state = .loading")
            lines.append(f"        do {{")
            lines.append(f"            // let result = try await APIClient.shared.get(url)")
            lines.append(f"            // state = .loaded(result)")
            lines.append(f"        }} catch {{")
            lines.append(f"            state = .error(error)")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)
