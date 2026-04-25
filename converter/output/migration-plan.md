# iOS Migration Plan

> Generated: 2026-04-25T06:01:35.517402+00:00
> Source: `/storage/users/user_3AeOuDUrxI7LrpU6J21FpMneayM/projects/ios-agent/converter/test-fixtures/sample-app`

## Executive Summary

**4 files** to convert with **46 patterns** detected.

| Conversion Level | Count | % | Meaning |
|---|---|---|---|
| Auto | 38 | 83% | Direct 1:1 mapping exists |
| Assisted | 8 | 17% | Mapping exists but requires restructuring |
| Manual | 0 | 0% | No direct equivalent — needs rethinking |

## Recommended Conversion Order

Convert in this order to minimize dependency issues:

1. **Types / Models** — No dependencies, foundation for everything else
2. **Configuration** — Environment setup needed early
3. **Services / API Layer** — Networking code, depends on models
4. **ViewModels (Hooks)** — Business logic, depends on services + models
5. **Components / Views** — UI layer, depends on everything above
6. **Routes / Navigation** — Wire everything together last

## Target iOS Project Structure

```
MyApp/
├── App/
│   ├── MyAppApp.swift
│   └── AppState.swift
├── Services/
│   ├── ArticleService.swift
├── ViewModels/
│   ├── UseAuthViewModel.swift
├── Views/
│   ├── UserCardView.swift
├── Resources/
│   └── Assets.xcassets
└── Configuration/
    ├── Debug.xcconfig
    └── Release.xcconfig
```

## File-by-File Migration

### Phase 3: Services & API

#### `services/articleService.ts` -> `Services/ArticleService.swift`

**Target pattern:** Service struct with async methods

- [AUTO] **api_call: axios.get**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: axios.get**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: axios.post**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: axios.put**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: axios.delete**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: axios.get**
  - iOS equivalent: `APIClient`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **type_definition: Article**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **type_definition: CreateArticleInput**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **type_definition: ArticleSortBy**
  - iOS equivalent: `typealias or enum`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **env_variable: NEXT_PUBLIC_API_URL**
  - iOS equivalent: `xcconfig / Info.plist / Bundle.main`
  - Create Debug.xcconfig and Release.xcconfig files
  - Add variable: VAR_NAME = value
  - Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>
  - Access in code: Bundle.main.infoDictionary?["VarName"] as? String

### Phase 4: ViewModels (from Hooks)

#### `hooks/useAuth.ts` -> `ViewModels/UseAuthViewModel.swift`

**Target pattern:** @Observable class (ViewModel)

- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [ASSISTED] **hook: useEffect**
  - iOS equivalent: `.task / .onAppear / .onChange`
  - Replace with .task { } (async, cancels on disappear), .onAppear { } (sync, mount only), or .onChange(of:) { } (dependency change).
- [AUTO] **hook: useContext**
  - iOS equivalent: `@Environment`
  - Replace with @Environment. Define custom EnvironmentValues entry for app-specific context.
- [ASSISTED] **custom_hook: useAuth**
  - iOS equivalent: `@Observable ViewModel`
  - Create an @Observable class named {HookName}ViewModel (drop 'use' prefix)
  - Convert hook state (useState) to published properties on the class
  - Convert hook effects (useEffect) to methods called from View's .task or .onAppear
  - Convert returned values to class properties
  - Convert returned callbacks to class methods
- [ASSISTED] **custom_hook: useAuthProvider**
  - iOS equivalent: `@Observable ViewModel`
  - Create an @Observable class named {HookName}ViewModel (drop 'use' prefix)
  - Convert hook state (useState) to published properties on the class
  - Convert hook effects (useEffect) to methods called from View's .task or .onAppear
  - Convert returned values to class properties
  - Convert returned callbacks to class methods
- [AUTO] **state_management: createContext**
  - iOS equivalent: `@Observable / @Environment`
  - Replace Redux/Zustand store with @Observable class
  - Replace useSelector with @Environment access
  - Replace dispatch with direct method calls on the observable
  - Inject at app root with .environment()
  - For complex state, keep the store pattern but use @Observable instead of createStore
- [AUTO] **api_call: fetch**
  - iOS equivalent: `URLSession.shared.data(from:)`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: fetch**
  - iOS equivalent: `URLSession.shared.data(from:)`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **api_call: fetch**
  - iOS equivalent: `URLSession.shared.data(from:)`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [AUTO] **type_definition: AuthState**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **type_definition: AuthContextType**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **env_variable: NEXT_PUBLIC_API_URL**
  - iOS equivalent: `xcconfig / Info.plist / Bundle.main`
  - Create Debug.xcconfig and Release.xcconfig files
  - Add variable: VAR_NAME = value
  - Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>
  - Access in code: Bundle.main.infoDictionary?["VarName"] as? String
- [AUTO] **env_variable: NEXT_PUBLIC_API_URL**
  - iOS equivalent: `xcconfig / Info.plist / Bundle.main`
  - Create Debug.xcconfig and Release.xcconfig files
  - Add variable: VAR_NAME = value
  - Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>
  - Access in code: Bundle.main.infoDictionary?["VarName"] as? String
- [AUTO] **env_variable: NEXT_PUBLIC_API_URL**
  - iOS equivalent: `xcconfig / Info.plist / Bundle.main`
  - Create Debug.xcconfig and Release.xcconfig files
  - Add variable: VAR_NAME = value
  - Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>
  - Access in code: Bundle.main.infoDictionary?["VarName"] as? String
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).

### Phase 5: Views (from Components)

#### `components/UserCard.tsx` -> `Views/UserCardView.swift`

**Target pattern:** SwiftUI View struct

- [AUTO] **component: UserCard**
  - Create a struct conforming to View protocol
  - Convert props to stored properties (let) on the struct
  - Convert JSX return to SwiftUI body computed property
  - Replace HTML elements with SwiftUI equivalents (div→VStack/HStack, p→Text, img→Image/AsyncImage)
  - Convert CSS classes / Tailwind to SwiftUI modifiers
  - Convert event handlers (onClick→Button action, onChange→.onChange modifier)
- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [AUTO] **hook: useState**
  - iOS equivalent: `@State`
  - Replace with @State private var. For shared state, use @Observable ViewModel.
- [ASSISTED] **hook: useEffect**
  - iOS equivalent: `.task / .onAppear / .onChange`
  - Replace with .task { } (async, cancels on disappear), .onAppear { } (sync, mount only), or .onChange(of:) { } (dependency change).
- [ASSISTED] **hook: useEffect**
  - iOS equivalent: `.task / .onAppear / .onChange`
  - Replace with .task { } (async, cancels on disappear), .onAppear { } (sync, mount only), or .onChange(of:) { } (dependency change).
- [ASSISTED] **hook: useNavigate**
  - iOS equivalent: `NavigationPath / @Environment(\.dismiss)`
  - Use NavigationPath from @Environment or @Binding. Append to path for push, remove for pop.
- [AUTO] **api_call: fetch**
  - iOS equivalent: `URLSession.shared.data(from:)`
  - Replace fetch()/axios with APIClient.shared method call
  - Define Codable request/response structs matching the JSON shape
  - Use async/await (nearly identical syntax to JS)
  - Handle errors with do/try/catch instead of .catch()
  - Use JSONDecoder with .convertFromSnakeCase if your API uses snake_case
- [ASSISTED] **routing: navigate-hook**
  - iOS equivalent: `NavigationStack / NavigationLink`
  - Define a Route enum with cases for each route
  - Use NavigationStack with .navigationDestination(for:)
  - Replace <Link> with NavigationLink(value:)
  - Replace router.push() with path.append()
  - Replace <Route> definitions with switch cases in navigationDestination
- [ASSISTED] **styling: tailwind**
  - iOS equivalent: `SwiftUI modifiers`
  - Map Tailwind utilities to SwiftUI modifiers. Common: p-4→.padding(16), flex→HStack/VStack, text-lg→.font(.title3), bg-blue-500→.background(.blue), rounded-lg→.clipShape(RoundedRectangle(cornerRadius: 12)), w-full→.frame(maxWidth: .infinity)
- [AUTO] **type_definition: User**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **type_definition: UserCardProps**
  - iOS equivalent: `struct: Codable`
  - Convert interface/type to struct conforming to Codable (if used with API) and Identifiable (if used in lists)
  - Convert optional fields (field?: type) to Swift optionals (var field: Type?)
  - Convert union types to Swift enums with associated values
  - Convert Record<K,V> to [K: V] dictionary
  - Convert Array<T> to [T]
  - Convert string literal unions to String-backed enums
- [AUTO] **env_variable: NEXT_PUBLIC_API_URL**
  - iOS equivalent: `xcconfig / Info.plist / Bundle.main`
  - Create Debug.xcconfig and Release.xcconfig files
  - Add variable: VAR_NAME = value
  - Reference in Info.plist: <key>VarName</key><string>$(VAR_NAME)</string>
  - Access in code: Bundle.main.infoDictionary?["VarName"] as? String
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).
- [AUTO] **storage: localStorage**
  - iOS equivalent: `UserDefaults or Keychain`
  - For non-sensitive data: UserDefaults.standard.set(value, forKey: key). For tokens/secrets: use Keychain (see security guide).

## Dependency Mapping

| Web Package | Swift Equivalent | Notes |
|---|---|---|
| `axios` | URLSession (built-in) | Or build an APIClient wrapper |
| `date-fns` | Foundation Date/Calendar (built-in) |  |
| `react` | SwiftUI (built-in) | Core framework, no package needed |
| `react-router-dom` | NavigationStack (built-in) |  |

## Environment Variable Migration

Create these xcconfig entries:

```
// Debug.xcconfig
API_URL = $(inherited)

// Release.xcconfig
API_URL = $(inherited)
```

## Pre-Migration Checklist

- [ ] Xcode installed and configured (see docs/01-getting-started/environment-setup.md)
- [ ] Apple Developer account set up
- [ ] New Xcode project created with SwiftUI template
- [ ] Target iOS 17+ minimum deployment
- [ ] xcconfig files created for Debug and Release
- [ ] API base URLs configured per environment
- [ ] Models (Codable structs) created and tested with sample JSON
- [ ] APIClient wrapper built and tested against your staging API
