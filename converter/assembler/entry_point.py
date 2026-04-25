"""
Entry Point Generator — Creates MyAppApp.swift with @main, WindowGroup,
and global environment injection.
"""

from ..rewriter.swift_helpers import swift_header, format_swift


def generate_entry_point(
    app_name: str,
    view_models: list[dict],
    root_view: str = "ContentView",
    has_auth: bool = False,
) -> str:
    """
    Generate the @main App entry point.

    Args:
        app_name: Name of the app (e.g., "MyApp")
        view_models: List of ViewModels to inject as environment objects
        root_view: The root view to display (default: ContentView)
        has_auth: Whether auth flow should be included
    """
    lines = []
    lines.append(swift_header(f"{app_name}App.swift", app_name))
    lines.append("import SwiftUI")
    lines.append("")

    # Inline learning annotation
    lines.append("// 💡 Learn: @main marks the app entry point — like index.tsx with createRoot().render(<App />)")
    lines.append("//    WindowGroup creates the root window. The OS manages the window lifecycle.")
    lines.append("")

    lines.append("@main")
    lines.append(f"struct {app_name}App: App {{")

    # State objects that need to be injected
    if view_models:
        lines.append("")
        lines.append("    // MARK: - App State")
        lines.append("")
        lines.append("    // 💡 Learn: @State here keeps ViewModels alive for the app's lifetime.")
        lines.append("    //    Equivalent to wrapping your React app in Context providers.")
        for vm in view_models:
            vm_name = vm["name"]
            vm_var = vm_name[0].lower() + vm_name[1:]
            lines.append(f"    @State private var {vm_var} = {vm_name}()")

    lines.append("")
    lines.append("    var body: some Scene {")
    lines.append("        WindowGroup {")

    if has_auth:
        lines.append("            Group {")
        lines.append("                if authViewModel.isAuthenticated {")
        lines.append(f"                    {root_view}()")
        lines.append("                } else {")
        lines.append("                    LoginView()")
        lines.append("                }")
        lines.append("            }")
    else:
        lines.append(f"            {root_view}()")

    # Inject environment objects
    if view_models:
        for vm in view_models:
            vm_name = vm["name"]
            vm_var = vm_name[0].lower() + vm_name[1:]
            lines.append(f"            .environment({vm_var})")

    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return format_swift("\n".join(lines))


def generate_content_view(
    app_name: str,
    views: list[dict],
    has_navigation: bool = True,
) -> str:
    """
    Generate a ContentView that serves as the root navigation container.

    Args:
        app_name: Name of the app
        views: List of generated view dicts with name/output_path
        has_navigation: Whether to wrap in NavigationStack
    """
    lines = []
    lines.append(swift_header("ContentView.swift", app_name))
    lines.append("import SwiftUI")
    lines.append("")

    lines.append("struct ContentView: View {")
    lines.append("")

    if has_navigation:
        lines.append("    // 💡 Learn: NavigationStack is SwiftUI's built-in router — type-safe, value-based.")
        lines.append("    //    Unlike React Router's string paths, you push typed values and resolve destinations.")
        lines.append("    @State private var navigationPath = NavigationPath()")
        lines.append("")

    lines.append("    var body: some View {")

    if has_navigation:
        lines.append("        NavigationStack(path: $navigationPath) {")
        lines.append("            List {")

        for view in views:
            view_name = view["name"]
            lines.append(f'                NavigationLink("{_display_name(view_name)}", value: Route.{_route_case(view_name)})')

        lines.append("            }")
        lines.append(f'            .navigationTitle("{app_name}")')
        lines.append("            .navigationDestination(for: Route.self) { route in")
        lines.append("                switch route {")

        for view in views:
            view_name = view["name"]
            lines.append(f"                case .{_route_case(view_name)}:")
            lines.append(f"                    {view_name}()")

        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
    else:
        if views:
            lines.append(f"            {views[0]['name']}()")
        else:
            lines.append('            Text("Welcome to the app")')

    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Generate Route enum
    if has_navigation and views:
        lines.append("// MARK: - Routes")
        lines.append("")
        lines.append("// 💡 Learn: Using an enum for routes gives you exhaustive switching —")
        lines.append("//    the compiler ensures every route has a destination. No 404s possible.")
        lines.append("enum Route: Hashable {")
        for view in views:
            lines.append(f"    case {_route_case(view['name'])}")
        lines.append("}")
        lines.append("")

    # Preview
    lines.append("#Preview {")
    lines.append("    ContentView()")
    lines.append("}")
    lines.append("")

    return format_swift("\n".join(lines))


def _display_name(view_name: str) -> str:
    """Convert ViewName to 'View Name' for display."""
    import re
    # Remove 'View' suffix for display
    name = view_name
    if name.endswith("View"):
        name = name[:-4]
    # Split on caps
    parts = re.findall(r"[A-Z][a-z]*", name)
    return " ".join(parts) if parts else name


def _route_case(view_name: str) -> str:
    """Convert ViewName to routeCase for enum."""
    name = view_name
    if name.endswith("View"):
        name = name[:-4]
    if name:
        return name[0].lower() + name[1:]
    return "home"
