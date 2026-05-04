"""
Learning Annotations — WHY Apple does it this way.

Each annotation maps a conversion pattern to an educational explanation
about Apple's design philosophy and the reasoning behind the iOS approach.
These are embedded as comments in generated Swift files and collected
into a companion learning-notes.md document.
"""


# ---------------------------------------------------------------------------
# Core annotation database — keyed by pattern or concept
# ---------------------------------------------------------------------------

ANNOTATIONS: dict[str, dict] = {
    # -- Struct vs Class --
    "struct_model": {
        "title": "Why Structs Instead of Classes for Models",
        "short": "Apple defaults to structs (value types) because they prevent shared mutable state bugs.",
        "detail": (
            "In JavaScript, objects are reference types — two variables can point to the "
            "same object, and mutating one silently affects the other. This is a major source "
            "of bugs in large codebases. Swift structs are value types: when you assign or "
            "pass a struct, you get an independent copy. This makes your data predictable — "
            "no spooky action at a distance. Apple recommends structs for models, and reserves "
            "classes for when you explicitly need shared identity (e.g., ViewModels observed "
            "by multiple views)."
        ),
        "web_analogy": "Like Object.freeze() on every object, but enforced by the compiler.",
        "apple_doc": "https://developer.apple.com/documentation/swift/choosing-between-structures-and-classes",
    },

    "codable": {
        "title": "Why Codable Instead of Manual JSON Parsing",
        "short": "Codable lets the compiler generate JSON encoding/decoding automatically.",
        "detail": (
            "In TypeScript, you typically parse JSON with response.json() and hope the shape "
            "matches your interface — there's no runtime guarantee. Swift's Codable protocol "
            "generates type-safe encoding and decoding at compile time. If the JSON doesn't "
            "match your struct, you get a clear error instead of undefined values silently "
            "propagating. The compiler writes the boring boilerplate, you get safety for free."
        ),
        "web_analogy": "Like Zod validation built into the language, but zero runtime cost.",
        "apple_doc": "https://developer.apple.com/documentation/swift/codable",
    },

    # -- SwiftUI Views --
    "swiftui_view_struct": {
        "title": "Why Views Are Structs, Not Classes",
        "short": "SwiftUI views are lightweight value types — recreated often, not mutated.",
        "detail": (
            "React components re-render by calling the function again. SwiftUI does the same "
            "thing — your View struct's body is called whenever state changes. Because structs "
            "are cheap value types (allocated on the stack, not the heap), SwiftUI can create "
            "thousands of view descriptions per frame with minimal overhead. This is why views "
            "are structs: they're disposable blueprints, not long-lived objects. SwiftUI's "
            "diffing engine compares the old and new struct to figure out what actually changed "
            "on screen."
        ),
        "web_analogy": "Like React's virtual DOM diffing, but using value-type structs instead of JS objects.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/view",
    },

    "body_computed_property": {
        "title": "Why body Is a Computed Property",
        "short": "body is recalculated on every state change — it's your render function.",
        "detail": (
            "In React, your component function IS the render function. In SwiftUI, the struct "
            "is the component and body is the render function. It's a computed property (not a "
            "stored one) because SwiftUI calls it every time state changes. Think of it exactly "
            "like a React function component's return statement — it describes what the UI "
            "should look like right now, and the framework handles the diffing."
        ),
        "web_analogy": "Equivalent to the return statement in a React function component.",
    },

    # -- State Management --
    "state_property_wrapper": {
        "title": "Why @State Instead of useState()",
        "short": "@State tells SwiftUI to own and persist this value across re-renders.",
        "detail": (
            "React's useState() returns a value and setter because functions don't persist "
            "state between calls. SwiftUI's @State solves the same problem differently — it's "
            "a property wrapper that tells SwiftUI 'store this value for me and re-render when "
            "it changes.' The view struct itself is recreated on each render, but @State values "
            "persist because SwiftUI manages them externally. You mutate the property directly "
            "(no setter function needed) and SwiftUI triggers the re-render automatically."
        ),
        "web_analogy": "Like useState(), but you write directly to the variable instead of calling a setter.",
    },

    "observable_viewmodel": {
        "title": "Why @Observable Class for ViewModels",
        "short": "@Observable makes a class's properties automatically trigger view updates.",
        "detail": (
            "Custom React hooks bundle related state and logic. Swift's @Observable macro does "
            "the same for classes — it automatically tracks which properties each view reads, "
            "and only re-renders views that depend on changed properties. This is more efficient "
            "than React's approach where any state change re-renders the entire component tree "
            "below the hook. @Observable uses classes (not structs) because ViewModels need "
            "shared identity — multiple views observe the same instance."
        ),
        "web_analogy": "Like a custom hook with automatic fine-grained reactivity (similar to Solid.js signals).",
        "apple_doc": "https://developer.apple.com/documentation/observation/observable()",
    },

    "environment": {
        "title": "Why @Environment Instead of useContext()",
        "short": "@Environment injects shared dependencies down the view tree.",
        "detail": (
            "React Context and SwiftUI Environment solve the same problem: passing data deep "
            "into the view tree without prop drilling. The key difference is SwiftUI's is "
            "built into the framework from day one and type-safe. You define an EnvironmentKey "
            "with a default value, and any child view can read it with @Environment. Changes "
            "automatically propagate. Apple provides many built-in environment values "
            "(colorScheme, locale, dismiss action) that would need separate packages in React."
        ),
        "web_analogy": "Like React Context, but type-safe, built-in, and with many pre-defined system values.",
    },

    # -- Networking --
    "actor_api_client": {
        "title": "Why Actor for the API Client",
        "short": "Actors prevent data races in concurrent code — thread safety guaranteed by the compiler.",
        "detail": (
            "In JavaScript, you don't worry about thread safety because JS is single-threaded. "
            "Swift's async/await can run tasks on multiple threads simultaneously. If two tasks "
            "tried to read/write the auth token at the same time on a regular class, you'd get "
            "a data race. An actor guarantees that only one task can access its properties at a "
            "time — the compiler enforces this with 'await' at call sites. It's like having a "
            "built-in mutex that you can't forget to use."
        ),
        "web_analogy": "Like a Web Worker with built-in message passing, but the compiler enforces the safety.",
        "apple_doc": "https://developer.apple.com/documentation/swift/actor",
    },

    "urlsession": {
        "title": "Why URLSession Instead of fetch()/Axios",
        "short": "URLSession is Apple's built-in networking layer — no packages needed.",
        "detail": (
            "URLSession is to iOS what fetch() is to the browser — the native HTTP client. "
            "It supports async/await (just like fetch), automatic cookie handling, caching, "
            "background downloads, and certificate pinning. Unlike the web ecosystem where you "
            "might reach for Axios for interceptors or defaults, URLSession handles all of that "
            "natively. Apple discourages third-party networking libraries because URLSession "
            "integrates with the OS for power management, connectivity monitoring, and "
            "background task scheduling."
        ),
        "web_analogy": "The native fetch() API, but with built-in caching, background downloads, and OS integration.",
    },

    "async_await_swift": {
        "title": "Why Swift async/await Looks Like JavaScript's",
        "short": "Swift adopted async/await after JavaScript — nearly identical syntax, stricter safety.",
        "detail": (
            "Swift's async/await was inspired by the same academic work as JavaScript's, so the "
            "syntax is almost identical. The difference is safety: Swift's concurrency model uses "
            "Sendable types and actors to prevent data races at compile time. In JS, you can "
            "share mutable state between async functions freely (single-threaded). In Swift, "
            "the compiler prevents you from accidentally sharing non-thread-safe data between "
            "concurrent tasks."
        ),
        "web_analogy": "Same syntax as JS async/await, but with compile-time thread safety checks.",
    },

    # -- Security & Storage --
    "keychain": {
        "title": "Why Keychain Instead of localStorage for Tokens",
        "short": "Keychain encrypts data at the hardware level — localStorage equivalent would be insecure.",
        "detail": (
            "localStorage on the web stores plain text that any script on the page can read "
            "(XSS vulnerability). iOS Keychain stores credentials in a hardware-encrypted "
            "enclave that persists across app reinstalls and is protected by the device passcode "
            "or biometrics. Apple requires apps that handle sensitive data (tokens, passwords, "
            "API keys) to use Keychain — storing them in UserDefaults (the closest localStorage "
            "equivalent) would fail App Store review for security violations."
        ),
        "web_analogy": "Like an HttpOnly secure cookie, but encrypted at the hardware level by the device.",
        "apple_doc": "https://developer.apple.com/documentation/security/keychain_services",
    },

    "userdefaults": {
        "title": "Why UserDefaults for Preferences (Not Tokens)",
        "short": "UserDefaults is for non-sensitive settings — fast, simple, unencrypted.",
        "detail": (
            "UserDefaults is the iOS equivalent of localStorage for non-sensitive data: theme "
            "preference, onboarding completion, feature flags. It's a simple key-value plist "
            "backed by the file system. It's fast for reads (cached in memory) but not "
            "encrypted — never store tokens, passwords, or PII. For those, use Keychain."
        ),
        "web_analogy": "Like localStorage, but only for non-sensitive preferences. Tokens go in Keychain instead.",
    },

    # -- Navigation --
    "navigation_stack": {
        "title": "Why NavigationStack Instead of React Router",
        "short": "NavigationStack is SwiftUI's built-in, type-safe navigation system.",
        "detail": (
            "React Router maps URL paths to components. SwiftUI's NavigationStack maps typed "
            "values to destinations. Instead of string-based routes ('/users/:id'), you push "
            "a User value onto a NavigationPath and SwiftUI resolves the destination view via "
            ".navigationDestination(for: User.self). This is type-safe — you can't navigate "
            "to a route with the wrong parameter types. The path is just an array you can "
            "manipulate: append to push, removeLast to pop, removeAll for root."
        ),
        "web_analogy": "Like React Router, but type-safe and value-based instead of string-based URLs.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/navigationstack",
    },

    # -- Patterns & Architecture --
    "mvvm": {
        "title": "Why MVVM Instead of Component + Hook",
        "short": "MVVM separates state/logic (ViewModel) from UI (View) — Apple's recommended pattern.",
        "detail": (
            "React encourages collocating state and UI in the same component (or custom hook). "
            "SwiftUI's preferred pattern is MVVM: Views are pure UI descriptions, ViewModels "
            "hold state and business logic. This separation matters more on iOS because views "
            "are structs (can't hold complex logic easily) and because Xcode previews work "
            "best when views are simple. The ViewModel is a class that persists state while "
            "the view struct is recreated each render cycle."
        ),
        "web_analogy": "Like separating a React component's logic into a custom hook, but as a formalized pattern.",
    },

    "view_modifier": {
        "title": "Why .modifier() Chaining Instead of CSS Classes",
        "short": "SwiftUI modifiers are type-safe, composable functions — not string class names.",
        "detail": (
            "Tailwind/CSS applies styles via string class names that the browser interprets. "
            "SwiftUI modifiers are actual function calls that the compiler type-checks. "
            ".padding(16) returns a new view with padding, .font(.title) returns a view with "
            "that font. Because they're functions, the compiler catches typos and invalid "
            "combinations. You can also create custom ViewModifier structs to bundle common "
            "styling patterns — like a reusable Tailwind @apply, but type-safe."
        ),
        "web_analogy": "Like Tailwind utility classes, but as type-checked function calls instead of strings.",
    },

    # -- Project Structure --
    "xcconfig": {
        "title": "Why xcconfig Instead of .env Files",
        "short": "xcconfig files configure Xcode builds per-environment — .env equivalent for iOS.",
        "detail": (
            "Web projects use .env files loaded at runtime by bundlers (Vite, Next.js). iOS "
            "apps use xcconfig files that configure the build at compile time. Values are baked "
            "into Info.plist during the build, not read from disk at runtime. This means you "
            "can't change config without rebuilding — but it also means your production app "
            "can't accidentally load development values. Xcode supports Debug and Release "
            "configurations that map to different xcconfig files."
        ),
        "web_analogy": "Like .env.development and .env.production, but resolved at compile time, not runtime.",
    },

    "package_swift": {
        "title": "Why Package.swift Instead of package.json",
        "short": "Swift Package Manager is Apple's built-in dependency manager — no npm equivalent needed.",
        "detail": (
            "Package.swift is the iOS equivalent of package.json. It declares dependencies, "
            "targets, and build settings in actual Swift code (not JSON/YAML). SPM is built "
            "into Xcode — no separate install step. Dependencies are fetched from Git repos "
            "(not a central registry like npm). The ecosystem is smaller but more curated, and "
            "many common web dependencies (routing, state management, HTTP, date formatting) "
            "are built into Apple's frameworks — no packages needed."
        ),
        "web_analogy": "Like package.json + npm, but built into the IDE and using Swift code instead of JSON.",
    },

    "app_entry_point": {
        "title": "Why @main and WindowGroup",
        "short": "@main marks the app entry point — WindowGroup creates the root window.",
        "detail": (
            "In React, you have index.tsx with ReactDOM.createRoot().render(<App />). In "
            "SwiftUI, @main marks your App struct as the entry point, and WindowGroup creates "
            "the window that holds your view hierarchy. WindowGroup supports multi-window on "
            "iPad and Mac. You inject global state here with .environment() — equivalent to "
            "wrapping your React app in Context providers."
        ),
        "web_analogy": "Like index.tsx with createRoot().render(<App />), but the OS manages the window lifecycle.",
    },

    # -- iOS-specific concepts --
    "task_modifier": {
        "title": "Why .task {} Instead of useEffect()",
        "short": ".task starts async work when a view appears and auto-cancels when it disappears.",
        "detail": (
            "React's useEffect runs side effects after render and requires a manual cleanup "
            "function. SwiftUI's .task {} modifier does the same but with a key advantage: it "
            "automatically cancels the async task when the view is removed from the hierarchy. "
            "No more 'can't perform a React state update on an unmounted component' warnings. "
            "For dependency-based effects, use .task(id: someValue) {} — it restarts the task "
            "when the id changes, like useEffect's dependency array."
        ),
        "web_analogy": "Like useEffect with automatic cleanup — cancels async work when the component unmounts.",
    },

    "identifiable": {
        "title": "Why Identifiable Protocol for List Items",
        "short": "Identifiable gives each item a stable identity for efficient list diffing.",
        "detail": (
            "React needs a key prop on list items so its reconciler can track which items "
            "changed. Swift's Identifiable protocol serves the same purpose — it requires an "
            "id property that SwiftUI uses for diffing. The difference is it's enforced by the "
            "type system: if you try to use a non-Identifiable type in a List, the compiler "
            "errors. No more runtime warnings about missing keys."
        ),
        "web_analogy": "Like React's key prop on list items, but enforced by the compiler instead of a warning.",
    },

    "sendable": {
        "title": "Why Sendable Matters for Concurrency",
        "short": "Sendable types can be safely shared between threads — the compiler checks this.",
        "detail": (
            "JavaScript is single-threaded, so sharing data between async operations is safe. "
            "Swift can run async tasks on different threads. Sendable is a protocol that marks "
            "types as safe to send across thread boundaries. Value types (structs, enums) are "
            "automatically Sendable. Classes need explicit conformance and immutability. The "
            "compiler warns you when you try to pass non-Sendable data to another task — "
            "catching concurrency bugs before they happen."
        ),
        "web_analogy": "No direct web equivalent — JS is single-threaded. Like Rust's Send trait for thread safety.",
    },

    # -- Anti-patterns (GAP-E2) — what NOT to do --
    "antipattern_any_view": {
        "title": "Don't Use AnyView Everywhere",
        "short": "AnyView erases type information SwiftUI needs for efficient diffing.",
        "detail": (
            "Web developers sometimes wrap views in AnyView to 'make types work.' This is like "
            "wrapping everything in React.Fragment — it works but kills performance. SwiftUI "
            "uses concrete view types for its diffing algorithm, comparing structurally identical "
            "trees in O(1). AnyView forces runtime type checks instead of compile-time "
            "optimization, defeating the framework's main performance trick. Use @ViewBuilder "
            "(returns the right opaque type) or generic constraints (some View) instead."
        ),
        "web_analogy": "Like using 'any' in TypeScript — it compiles but defeats the type system's purpose.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/anyview",
    },

    "antipattern_force_unwrap": {
        "title": "Never Force-Unwrap in Production Code",
        "short": "The ! operator crashes your app if the value is nil — use if let or guard.",
        "detail": (
            "JavaScript silently propagates undefined; Swift makes nil explicit through Optionals. "
            "Force-unwrapping with ! says 'I'm certain this isn't nil — crash if I'm wrong.' That "
            "produces a runtime crash users see as an app freeze, not a recoverable error. Prefer "
            "if let, guard let, ?? defaults, or optional chaining (?.). Reserve ! for IBOutlets "
            "and a few well-known exceptions (e.g., URL(string: hardcodedLiteral)!)."
        ),
        "web_analogy": "Like calling .toString() on undefined — Swift makes you handle the nil case explicitly.",
    },

    "antipattern_body_logic": {
        "title": "Keep var body Simple — No Heavy Logic",
        "short": "body is called on every state change. Move logic to methods or computed props.",
        "detail": (
            "var body is called every time SwiftUI re-evaluates the view — potentially many times "
            "per second during scrolling or animation. Putting heavy work there (sorting, "
            "filtering, network calls, JSON decoding) makes the UI janky. Move expensive "
            "computations to the ViewModel, cache results in @State, or use computed properties "
            "outside body. Treat body like the return statement of a React component — purely "
            "describe the UI, don't compute data there."
        ),
        "web_analogy": "Like avoiding heavy work in a React component's render — same rule, same reason.",
    },

    "antipattern_observableobject_legacy": {
        "title": "Prefer @Observable over ObservableObject",
        "short": "@Observable (iOS 17+) is the modern macro — fewer property wrappers, better perf.",
        "detail": (
            "Older SwiftUI code uses ObservableObject + @Published + @StateObject + @ObservedObject. "
            "iOS 17 introduced @Observable, which eliminates @Published and lets SwiftUI track "
            "exactly which properties each view reads (fine-grained reactivity). Less boilerplate, "
            "better performance. Use @State to own an instance, @Bindable for two-way binding, "
            "@Environment to inject. Only fall back to ObservableObject if you must support "
            "iOS 16 and earlier."
        ),
        "web_analogy": "Like migrating from class components to hooks — same job, much less ceremony.",
        "apple_doc": "https://developer.apple.com/documentation/observation/observable()",
    },

    "antipattern_geometry_reader_overuse": {
        "title": "Don't Reach for GeometryReader First",
        "short": "GeometryReader fills its parent and breaks intrinsic sizing — try modifiers first.",
        "detail": (
            "Web developers reach for GeometryReader because it feels like getBoundingClientRect. "
            "It works, but it greedily fills the available space, which often breaks layouts that "
            "expected a child to size to its content. Try .frame(maxWidth: .infinity), "
            ".aspectRatio, .containerRelativeFrame, or alignment guides first. Use GeometryReader "
            "only when you need the actual measured size for math (custom shapes, gauges)."
        ),
        "web_analogy": "Like reaching for ResizeObserver when CSS would have worked.",
    },

    # -- Missing concepts (GAP-E3) --
    "app_lifecycle": {
        "title": "Why App Lifecycle Matters More on Mobile",
        "short": "iOS can suspend or terminate your app at any time — save state proactively.",
        "detail": (
            "Web apps run until the user closes the tab. iOS apps move through scene phases: "
            "active → inactive → background → suspended → terminated. The OS can kill a "
            "background app at any moment to reclaim memory — without warning, without a chance "
            "to run cleanup code. You must save important state in .onChange(of: scenePhase) "
            "when transitioning to .background, and restore it on launch. This is also when "
            "you stop timers, pause downloads, and release resources you don't need backgrounded."
        ),
        "web_analogy": "Like the Page Visibility API, but the OS can kill your tab entirely without notice.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/scenephase",
    },

    "memory_management_arc": {
        "title": "Why Swift Uses ARC Instead of Garbage Collection",
        "short": "ARC is deterministic — objects are freed immediately when no longer referenced.",
        "detail": (
            "JavaScript uses garbage collection: the runtime periodically scans for unreachable "
            "objects and frees them. Swift uses Automatic Reference Counting (ARC): the compiler "
            "inserts retain/release calls so objects are freed the instant their reference count "
            "hits zero. This gives predictable performance (no GC pauses) and lower memory "
            "overhead — critical on resource-constrained mobile devices. The trade-off is "
            "retain cycles: if A holds B and B holds A, neither ever reaches zero. Solve this "
            "with [weak self] in closures, just as you'd avoid circular references in JS."
        ),
        "web_analogy": "Like RAII in C++ or Rust's ownership — deterministic cleanup, no GC pauses.",
    },

    "swiftui_layout_system": {
        "title": "How SwiftUI Layout Differs from CSS",
        "short": "SwiftUI negotiates size between parent and child — no box model, no flow.",
        "detail": (
            "CSS uses a box model with flow, flexbox, and grid. SwiftUI uses a three-step "
            "negotiation: parent proposes a size, child chooses its size, parent places the "
            "child. There's no margin (use padding on parent), no float, no position:absolute "
            "(use overlays/ZStack). VStack/HStack are like flex-direction column/row but with "
            "intrinsic content sizing as the default. .frame() does NOT set a size — it "
            "proposes one to the child. GeometryReader gives you the parent's size for "
            "measurement-driven layout, but use it sparingly."
        ),
        "web_analogy": "Like flexbox where every child negotiates its size with its parent instead of being told.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/layout",
    },

    "binding_property_wrapper": {
        "title": "Why @Binding for Two-Way Data Flow",
        "short": "@Binding is a reference to a parent's @State — the child can read AND write.",
        "detail": (
            "React passes value + onChange as separate props for two-way binding. SwiftUI bundles "
            "them into a single @Binding. When a parent has @State var name = '' and passes $name "
            "(the dollar sign creates a Binding) to a child with @Binding var name: String, the "
            "child can mutate it directly and SwiftUI rebuilds the parent. This is type-safe "
            "and impossible to misuse — you can't accidentally pass a value without its setter."
        ),
        "web_analogy": "Like passing { value, onChange } as one prop — but bundled and type-safe.",
        "apple_doc": "https://developer.apple.com/documentation/swiftui/binding",
    },

    "sheet_presentation": {
        "title": "Why .sheet() Instead of Modal Components",
        "short": "iOS manages modal presentation at the system level — sheets, alerts, popovers.",
        "detail": (
            "Web modals are usually rendered by your component tree (React portals, custom <dialog>). "
            "On iOS, the system owns presentation: .sheet() slides up a card with platform-correct "
            "animations, swipe-to-dismiss gestures, and accessibility focus management. .alert() "
            "for confirmations, .popover() for contextual menus, .fullScreenCover() for takeovers. "
            "Each is a state-driven modifier (bind to a Bool or optional Item). The OS handles "
            "the visuals — your job is just describing what content goes inside."
        ),
        "web_analogy": "Like a polished <dialog> element with a built-in animation library and a11y baked in.",
    },

    "accessibility_first": {
        "title": "Why Accessibility Is a Core iOS Feature",
        "short": "VoiceOver and Dynamic Type are required, not optional — Apple ships them on every device.",
        "detail": (
            "Web accessibility is often retrofitted with aria attributes. iOS accessibility is "
            "built into every framework: VoiceOver reads screens for blind users, Dynamic Type "
            "scales text for low-vision users, Switch Control lets users navigate with one button. "
            "These ship on every iPhone — millions of users rely on them daily. SwiftUI exposes "
            ".accessibilityLabel, .accessibilityHint, .accessibilityAddTraits, and "
            ".accessibilityValue as first-class modifiers. Apple often rejects apps that don't "
            "label their controls."
        ),
        "web_analogy": "Like aria-label and role, but a Human Interface Guidelines requirement, not a nice-to-have.",
        "apple_doc": "https://developer.apple.com/accessibility/",
    },

    "error_handling_swift": {
        "title": "Why Swift Errors Are Explicit and Exhaustive",
        "short": "throws / try / catch is a typed contract — the compiler ensures every error is handled.",
        "detail": (
            "JavaScript errors are dynamic: any function might throw, you find out at runtime. "
            "Swift requires you to mark throwing functions with throws and call them with try. "
            "Errors are typed (conform to Error), and the compiler checks that callers either "
            "handle them in catch or propagate them by re-marking themselves throws. do { try } "
            "catch is exhaustive — you can pattern-match specific error cases. This makes error "
            "paths visible in code review and impossible to ignore by accident."
        ),
        "web_analogy": "Like Result<T, E> in Rust — error possibility is part of the function signature.",
        "apple_doc": "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/errorhandling/",
    },

    "compile_time_safety": {
        "title": "Why Swift Catches Errors Before You Run",
        "short": "Swift is ahead-of-time compiled — type errors block the build, not your runtime.",
        "detail": (
            "TypeScript erases types at runtime; you can run code that has type errors. Swift "
            "compiles to native machine code through swiftc/LLVM — type errors stop the build. "
            "If your app builds, the compiler has already verified that no value is the wrong "
            "type, no Optional is unhandled, no error is uncaught, no actor is touched without "
            "await. The trade-off is slower iteration during a refactor (compile times), but "
            "the payoff is far fewer 'undefined is not a function' surprises in production."
        ),
        "web_analogy": "Like running tsc --noEmit before every deploy, but enforced — and applied to memory and concurrency too.",
    },
}


# ---------------------------------------------------------------------------
# Pattern-to-annotation mapping
# ---------------------------------------------------------------------------

# Maps (pattern_type, optional sub-key) to annotation keys
PATTERN_ANNOTATION_MAP: dict[str, list[str]] = {
    # File-type level annotations
    "component": ["swiftui_view_struct", "body_computed_property", "view_modifier"],
    "hook": ["observable_viewmodel", "mvvm"],
    "service": ["actor_api_client", "urlsession", "async_await_swift"],
    "type": ["struct_model", "codable"],
    "config": ["xcconfig"],
    "route": ["navigation_stack"],

    # Pattern-type level annotations
    "state_management": ["state_property_wrapper", "binding_property_wrapper", "antipattern_observableobject_legacy"],
    "useState": ["state_property_wrapper"],
    "useEffect": ["task_modifier", "antipattern_body_logic"],
    "useContext": ["environment"],
    "api_call": ["urlsession", "async_await_swift", "codable", "error_handling_swift"],
    "routing": ["navigation_stack"],
    "env_variable": ["xcconfig"],
    "storage": ["keychain", "userdefaults"],
    "localStorage": ["keychain", "userdefaults"],

    # Anti-pattern triggers — surfaced when the converter generates fallback/risky code
    "any_view_fallback": ["antipattern_any_view"],
    "force_unwrap": ["antipattern_force_unwrap"],
    "geometry_reader": ["antipattern_geometry_reader_overuse"],

    # iOS-specific concept patterns
    "scene_phase": ["app_lifecycle"],
    "modal_presentation": ["sheet_presentation"],
    "accessibility": ["accessibility_first"],
    "layout": ["swiftui_layout_system"],
    "memory": ["memory_management_arc"],
    "throws_function": ["error_handling_swift", "compile_time_safety"],
}


def get_annotations_for_pattern(pattern_type: str, name: str = "") -> list[dict]:
    """Get learning annotations relevant to a specific pattern."""
    keys = set()

    # Check pattern type
    if pattern_type in PATTERN_ANNOTATION_MAP:
        keys.update(PATTERN_ANNOTATION_MAP[pattern_type])

    # Check specific name (e.g., "useState", "localStorage")
    if name in PATTERN_ANNOTATION_MAP:
        keys.update(PATTERN_ANNOTATION_MAP[name])

    return [ANNOTATIONS[k] for k in keys if k in ANNOTATIONS]


def get_annotations_for_file(file_type: str, patterns: list[dict]) -> list[dict]:
    """Get all learning annotations relevant to a file and its patterns."""
    seen_keys = set()
    result = []

    # File-type annotations
    if file_type in PATTERN_ANNOTATION_MAP:
        for key in PATTERN_ANNOTATION_MAP[file_type]:
            if key not in seen_keys and key in ANNOTATIONS:
                seen_keys.add(key)
                result.append(ANNOTATIONS[key])

    # Pattern-level annotations
    for p in patterns:
        ptype = p.get("pattern_type", "") if isinstance(p, dict) else getattr(p, "pattern_type", "")
        pname = p.get("name", "") if isinstance(p, dict) else getattr(p, "name", "")

        for lookup in (ptype, pname):
            if lookup in PATTERN_ANNOTATION_MAP:
                for key in PATTERN_ANNOTATION_MAP[lookup]:
                    if key not in seen_keys and key in ANNOTATIONS:
                        seen_keys.add(key)
                        result.append(ANNOTATIONS[key])

    return result


def get_inline_comment(annotation_key: str) -> str:
    """Get a short inline comment for embedding in generated Swift code."""
    ann = ANNOTATIONS.get(annotation_key)
    if not ann:
        return ""
    return f"// 💡 Learn: {ann['short']}"


def get_all_annotations() -> dict[str, dict]:
    """Return the full annotation database."""
    return ANNOTATIONS.copy()
