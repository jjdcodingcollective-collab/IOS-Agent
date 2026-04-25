# Architecture Patterns

> How web architecture translates to iOS. If you've structured a React app with components, hooks, context, and API layers — you already understand the principles. iOS just uses different names.

---

## The Big Picture: Web vs. iOS Architecture

```
Web (React/Next.js)              iOS (SwiftUI)
─────────────────────            ─────────────────
Pages / Routes                   NavigationStack / Screens
Components                       Views (SwiftUI structs)
Hooks (useState, useEffect)      @State, .onAppear, .task
Context / Redux / Zustand        @Observable, @Environment
API Layer (fetch, axios)         Service Layer (URLSession)
DTOs / Types                     Codable Structs (Models)
Middleware                       Interceptors / Modifiers
.env / config                    xcconfig / Info.plist
```

---

## Architecture Patterns on iOS

### MVVM (Recommended for SwiftUI)

**Model-View-ViewModel** is the dominant pattern for SwiftUI apps. If you use React with custom hooks that separate data logic from UI, you're already doing something similar.

```
Web Equivalent:
Component (JSX)     ←→  View (SwiftUI)
Custom Hook          ←→  ViewModel (@Observable class)
API Types/DTOs       ←→  Model (Codable struct)
```

```swift
// Model — your data (like a TypeScript interface)
struct Article: Codable, Identifiable {
    let id: String
    let title: String
    let body: String
    let publishedAt: Date
}

// ViewModel — your logic (like a custom hook)
@Observable
class ArticleListViewModel {
    var articles: [Article] = []
    var isLoading = false
    var errorMessage: String?
    
    func loadArticles() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            articles = try await ArticleService.fetchAll()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// View — your UI (like a React component)
struct ArticleListView: View {
    @State private var viewModel = ArticleListViewModel()
    
    var body: some View {
        List(viewModel.articles) { article in
            ArticleRow(article: article)
        }
        .overlay {
            if viewModel.isLoading {
                ProgressView()
            }
        }
        .task {
            await viewModel.loadArticles()
        }
    }
}
```

### When MVVM Maps to React Patterns

| React Pattern | MVVM Equivalent |
|---|---|
| `useState` + local state | `@State` on the View |
| Custom hook with `useEffect` + `useState` | `@Observable` ViewModel |
| `useContext` for shared state | `@Environment` or shared ViewModel |
| Props drilling | Passing data through View initializers |
| `useReducer` | ViewModel with explicit action methods |

---

## State Management

### Local State (Like useState)

```swift
struct CounterView: View {
    @State private var count = 0  // Local, owned by this view
    
    var body: some View {
        Button("Count: \(count)") {
            count += 1
        }
    }
}
```

### Shared State (Like Context/Redux)

```swift
// Define your shared state
@Observable
class AppState {
    var currentUser: User?
    var isAuthenticated: Bool { currentUser != nil }
    var theme: Theme = .system
}

// Inject at the top of your app (like a Provider)
@main
struct MyApp: App {
    @State private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
        }
    }
}

// Access anywhere in the tree (like useContext)
struct ProfileView: View {
    @Environment(AppState.self) private var appState
    
    var body: some View {
        if let user = appState.currentUser {
            Text("Hello, \(user.name)")
        }
    }
}
```

### State Flow Comparison

```
React:                          SwiftUI:
┌─────────────────┐             ┌─────────────────┐
│  Context.Provider│             │  .environment()  │
│  (top of tree)  │             │  (top of tree)   │
└────────┬────────┘             └────────┬─────────┘
         │                               │
    ┌────▼────┐                    ┌─────▼─────┐
    │useContext│                    │@Environment│
    │(consume)│                    │ (consume)  │
    └─────────┘                    └────────────┘
```

---

## Navigation (Like React Router)

```swift
// Define your routes (like route config)
enum Route: Hashable {
    case home
    case article(id: String)
    case settings
    case profile(userId: String)
}

// NavigationStack (like BrowserRouter)
struct ContentView: View {
    @State private var path = NavigationPath()
    
    var body: some View {
        NavigationStack(path: $path) {
            HomeView()
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .home:
                        HomeView()
                    case .article(let id):
                        ArticleDetailView(articleId: id)
                    case .settings:
                        SettingsView()
                    case .profile(let userId):
                        ProfileView(userId: userId)
                    }
                }
        }
    }
}

// Navigate programmatically (like useNavigate)
Button("View Article") {
    path.append(Route.article(id: "abc123"))
}

// NavigationLink (like <Link>)
NavigationLink(value: Route.settings) {
    Text("Settings")
}
```

---

## Dependency Injection

On the web, you might use module imports, context, or DI containers. Swift uses **protocols** and **environment** for testable dependency injection.

```swift
// Define what your service does (like a TypeScript interface)
protocol ArticleServiceProtocol {
    func fetchAll() async throws -> [Article]
    func fetch(id: String) async throws -> Article
}

// Real implementation
struct ArticleService: ArticleServiceProtocol {
    func fetchAll() async throws -> [Article] {
        // Real API call
    }
    func fetch(id: String) async throws -> Article {
        // Real API call
    }
}

// Mock for testing
struct MockArticleService: ArticleServiceProtocol {
    func fetchAll() async throws -> [Article] {
        return [Article(id: "1", title: "Test", body: "...", publishedAt: .now)]
    }
    func fetch(id: String) async throws -> Article {
        return Article(id: id, title: "Test", body: "...", publishedAt: .now)
    }
}

// Inject via environment for SwiftUI
extension EnvironmentValues {
    @Entry var articleService: ArticleServiceProtocol = ArticleService()
}

// Use in views
struct ArticleListView: View {
    @Environment(\.articleService) private var service
    // ...
}

// Swap for tests or previews
#Preview {
    ArticleListView()
        .environment(\.articleService, MockArticleService())
}
```

---

## Project Organization

### Recommended Structure for SwiftUI Apps

```
MyApp/
├── App/
│   ├── MyAppApp.swift          // Entry point (@main)
│   └── AppState.swift          // Global state
├── Models/
│   ├── User.swift              // Data models (Codable structs)
│   └── Article.swift
├── ViewModels/
│   ├── ArticleListViewModel.swift
│   └── AuthViewModel.swift
├── Views/
│   ├── Home/
│   │   ├── HomeView.swift
│   │   └── HomeComponents.swift
│   ├── Articles/
│   │   ├── ArticleListView.swift
│   │   └── ArticleDetailView.swift
│   └── Shared/
│       ├── LoadingView.swift
│       └── ErrorView.swift
├── Services/
│   ├── APIClient.swift         // Base networking
│   ├── ArticleService.swift
│   └── AuthService.swift
├── Extensions/
│   └── Date+Formatting.swift
├── Resources/
│   └── Assets.xcassets
└── Configuration/
    ├── Debug.xcconfig
    └── Release.xcconfig
```

**Mapping from web structure:**
- `Views/` = your `components/` and `pages/`
- `ViewModels/` = your custom hooks
- `Services/` = your API layer
- `Models/` = your TypeScript types/interfaces
- `Extensions/` = your utility functions

---

## Lifecycle Events (Like useEffect)

```swift
struct MyView: View {
    var body: some View {
        Text("Hello")
            .onAppear {
                // Like useEffect(() => { ... }, []) — runs on mount
                print("View appeared")
            }
            .onDisappear {
                // Like useEffect cleanup — runs on unmount
                print("View disappeared")
            }
            .task {
                // Like useEffect with async — runs on appear, cancels on disappear
                await loadData()
            }
            .onChange(of: someValue) { oldValue, newValue in
                // Like useEffect(() => { ... }, [someValue]) — runs on change
                print("Value changed from \(oldValue) to \(newValue)")
            }
    }
}
```

---

## Deprecated Patterns to Avoid

> **Deprecated:** `ObservableObject` with `@Published` — Use `@Observable` macro instead (iOS 17+). The old pattern required `@ObservedObject` or `@StateObject` wrappers; the new macro-based approach is simpler and more performant.

> **Deprecated:** `NavigationView` — Use `NavigationStack` (iOS 16+). `NavigationView` has been deprecated and has layout bugs that won't be fixed.

> **Deprecated:** Massive View Controllers (MVC "Massive View Controller" anti-pattern) — This was a UIKit problem. SwiftUI's composable views and MVVM naturally avoid it.

---

**Next:** [UI Development with SwiftUI](../04-ui-development/swiftui-guide.md) — Building interfaces mapped from web components.

*Last updated: 2026-04-25*
