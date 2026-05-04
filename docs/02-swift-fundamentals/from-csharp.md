# Swift for C# Developers

> C# and Swift are siblings, not twins. Both are statically typed, both have value types and reference types, both have async/await, both have generics with constraints, both have nullable references. **If you write modern C# you'll be productive in Swift in days, not weeks.** The friction sits at the edges: Swift has no GC, no `internal` access across modules, no LINQ, no reflection-based serialisation, and no `IDisposable` pattern — `defer`, ARC, and `Codable` cover the same ground differently.

> **Audience:** Xamarin/MAUI maintainers porting to native iOS as Microsoft winds the platform down, and Unity gameplay developers porting C# game logic into a native Swift app shell.

---

## The 60-second mental model

1. **`struct` is the default.** C# nudges you toward classes; Swift pushes harder for structs (value types). Reach for `class` only when you genuinely need reference semantics or `deinit`.
2. **No GC — ARC.** Memory is reference-counted at compile time. `using`/`IDisposable` becomes `defer` for scope-bound cleanup; finalizer-style cleanup goes in `deinit`.
3. **LINQ → sequence operations.** `Where` / `Select` / `Aggregate` are `filter` / `map` / `reduce`. They're eager by default in Swift; explicit laziness via `.lazy`.
4. **Nullable references → Optionals.** Swift's `T?` is `Optional<T>`, an enum, not a runtime nullable annotation. The compiler enforces unwrapping; there is no `?.` permissive read of a non-optional.
5. **Properties are first-class but slightly different.** Auto-properties → stored properties; computed properties have explicit `get`/`set`; `init`-only setters → `let` or `private(set)`.
6. **Strict concurrency is checked at compile time.** Where C# lets you share state across `Task`s with a stern docstring, Swift 6 refuses to compile until you prove it's safe — actors, `Sendable`, `@MainActor`. See [Strict Concurrency & Sendable](concurrency-and-sendable.md).

---

## Type-system mapping

| C# | Swift | Note |
|---|---|---|
| `int`, `long`, `double`, `bool` | `Int`, `Int64`, `Double`, `Bool` | `Int` is platform-width (64-bit on iOS). |
| `string` | `String` | Unicode-correct, value semantics. Indexing is by `String.Index`, not `Int`. |
| `byte` / `byte[]` | `UInt8` / `[UInt8]` or `Data` | `Data` is the idiomatic byte buffer. |
| `List<T>` | `[T]` (sugar for `Array<T>`) | Value type, copy-on-write. |
| `IEnumerable<T>` | `some Sequence<T>` or `AnySequence<T>` | Use `some` / `any` carefully — see generics chapter. |
| `Dictionary<K, V>` | `[K: V]` | Keys must be `Hashable`. |
| `HashSet<T>` | `Set<T>` | Elements must be `Hashable`. |
| `T?` (nullable reference) | `T?` (Optional) | Swift optionals are an enum; explicit unwrapping required. |
| `Nullable<T>` (`T?` for value types) | `T?` | Same syntax, no boxing. |
| `class` | `class` | Reference type. Subclassable. |
| `struct` | `struct` | Value type. No inheritance. |
| `record` | `struct: Equatable, Hashable` | Synthesised conformances; same intent. |
| `record class` | `final class: Equatable, Hashable` | Manual conformances if needed. |
| `enum` | `enum` | Swift enums are far richer — see below. |
| `interface` | `protocol` | Can have associated types and default impls. |
| `delegate Action`, `Action<T>`, `Func<T,U>` | `() -> Void`, `(T) -> Void`, `(T) -> U` | Functions are first-class types. |
| `Task<T>` | `async` function returning `T`, or explicit `Task<T, Error>` | The keyword spelling is the same; the type plumbing differs slightly. |
| `IAsyncEnumerable<T>` | `some AsyncSequence<T>` | Same shape; see [Combine & AsyncStream](combine-and-async-streams.md). |
| `IDisposable` + `using` | `defer { ... }` | Lexical, deterministic; covered by ARC for memory. |
| `Exception` + `try`/`catch` | `Error` + `do`/`try`/`catch` | Throwing functions are part of the type — `func foo() throws -> T`. |

### Enums are different

C# enums are integers in disguise. Swift enums are **algebraic data types** — they can carry associated values per case, like F# discriminated unions or Rust enums.

```csharp
// C# — flag enum at most
public enum Status { Loading, Loaded, Failed }
```

```swift
// Swift — values per case
enum Status {
    case loading
    case loaded(items: [Item])
    case failed(error: Error)
}

switch status {
case .loading:                 print("…")
case .loaded(let items):       print("\(items.count) items")
case .failed(let error):       print(error)
}
```

If you've used Roslyn analyzers to model state with sealed class hierarchies, Swift enums collapse the same pattern into the type system natively. This is the single biggest stylistic shift for C# devs — you'll find yourself reaching for enums where you used to reach for class hierarchies.

---

## Idiom translation

### LINQ → sequence operations

```csharp
// C#
var adults = users
    .Where(u => u.Age >= 18)
    .Select(u => u.Name)
    .OrderBy(n => n)
    .ToList();
```

```swift
// Swift
let adults = users
    .filter { $0.age >= 18 }
    .map(\.name)
    .sorted()
```

`\.name` is a key-path expression — equivalent to `u => u.Name` but compiled to a value, not a closure. See [The Swift Toolkit](swift-toolkit-for-web-devs.md) for the depth.

`Aggregate` → `reduce`:

```csharp
var total = orders.Aggregate(0m, (acc, o) => acc + o.Total);
```

```swift
let total = orders.reduce(0) { $0 + $1.total }
// or
let total = orders.map(\.total).reduce(0, +)
```

**Lazy vs eager.** LINQ is lazy by default — chains build up an `IEnumerable` and execute on `ToList()`/iteration. Swift sequence ops on `Array` are **eager** — each `filter` allocates a new array. To get LINQ-like laziness, prefix with `.lazy`:

```swift
let firstTen = users.lazy
    .filter { $0.age >= 18 }
    .map(\.name)
    .prefix(10)
```

This avoids materialising the intermediate filter result. For large collections or when you only need a prefix, `.lazy` is the right reflex.

### Async/await

```csharp
// C#
public async Task<User> LoadUserAsync(int id, CancellationToken ct)
{
    var resp = await _http.GetAsync($"/users/{id}", ct);
    resp.EnsureSuccessStatusCode();
    return await resp.Content.ReadFromJsonAsync<User>(cancellationToken: ct);
}
```

```swift
// Swift
func loadUser(id: Int) async throws -> User {
    let url = URL(string: "https://example.com/users/\(id)")!
    let (data, response) = try await URLSession.shared.data(from: url)
    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
        throw URLError(.badServerResponse)
    }
    return try JSONDecoder().decode(User.self, from: data)
}
```

Note the differences:

- **Cancellation is implicit.** Swift's `Task` carries cancellation; `try Task.checkCancellation()` is the explicit check, and `URLSession`/`Task.sleep` already respect it. No `CancellationToken` parameter to thread through every signature.
- **`throws` is part of the type.** `Task<T>` in C# erases the error type; in Swift, `async throws -> T` says "this can throw, await it with `try`."
- **`Task` is for spawning, not for typing returns.** `func foo() async -> T` is the C# `Task<T>` equivalent; `Task { … }` is the C# `Task.Run(…)` equivalent.

`IAsyncEnumerable<T>` maps to `AsyncSequence`:

```csharp
public async IAsyncEnumerable<Tick> StreamTicks([EnumeratorCancellation] CancellationToken ct)
{
    while (!ct.IsCancellationRequested) {
        yield return await NextTickAsync(ct);
    }
}
```

```swift
func streamTicks() -> AsyncStream<Tick> {
    AsyncStream { continuation in
        let task = Task {
            while !Task.isCancelled {
                continuation.yield(await nextTick())
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in task.cancel() }
    }
}
```

### Properties

```csharp
// C# auto-property + init-only
public record Person {
    public string Name { get; init; }
    public int Age { get; set; }
}
```

```swift
// Swift — let for init-only, var for settable
struct Person: Equatable, Hashable {
    let name: String      // init-only
    var age: Int          // settable
}
```

Computed properties:

```csharp
public string FullName => $"{First} {Last}";
public string Greeting { get => $"Hi {First}"; set => First = value; }
```

```swift
var fullName: String { "\(first) \(last)" }
var greeting: String {
    get { "Hi \(first)" }
    set { first = newValue }   // newValue is the implicit parameter name
}
```

### Pattern matching

C#'s switch expressions and Swift's switch are conceptually the same — exhaustive matching with extraction.

```csharp
var label = result switch {
    Loaded(var items) when items.Count > 0 => $"{items.Count} items",
    Loaded                                  => "empty",
    Failed(var err)                         => err.Message,
    _                                       => "loading…"
};
```

```swift
let label: String = switch result {
case .loaded(let items) where !items.isEmpty: "\(items.count) items"
case .loaded:                                 "empty"
case .failed(let err):                        err.localizedDescription
case .loading:                                "loading…"
}
```

`switch` is an expression in Swift since 5.9 — drop the curly braces and assign directly.

### Generics & constraints

```csharp
public T MaxBy<T, K>(IEnumerable<T> source, Func<T, K> key)
    where K : IComparable<K>
{ /* … */ }
```

```swift
func maxBy<T, K: Comparable>(_ source: [T], key: (T) -> K) -> T? {
    source.max(by: { key($0) < key($1) })
}
```

The big asymmetry: Swift has no `where T : struct` or `where T : class` constraint exactly. The closest are:

- `where T: AnyObject` — equivalent to C#'s `where T : class` (reference type).
- *(no equivalent for `where T : struct`)* — Swift instead lets you constrain by protocol conformance (`T: Equatable`, `T: Sendable`, etc.). Most "needs to be a value type" requirements don't actually need that constraint; they need `Hashable` or `Sendable`.

For the deep dive (PATs, opaque types, existentials), see [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md).

---

## Concurrency model

C# and Swift converged on async/await but the surrounding machinery differs.

| Concept | C# | Swift |
|---|---|---|
| Spawn a top-level task | `Task.Run(…)` | `Task { … }` |
| Wait for many | `Task.WhenAll(t1, t2)` | `async let a = …; async let b = …; let (x, y) = try await (a, b)` or `withTaskGroup` |
| Cooperative cancel | `CancellationToken` parameter | `Task.checkCancellation()`; cancellation flows automatically through `await` |
| Run on UI thread | `await` resumes on captured context (`SynchronizationContext`) | `@MainActor` annotation on the function or type |
| Lock | `lock(obj) { … }` or `Mutex` | `actor` (preferred) or `NSLock` (rare) |
| Thread-safe collection | `ConcurrentDictionary` etc. | Wrap mutation in an `actor` |

The mental shift: in C# you carry a `CancellationToken` through every async signature. In Swift, cancellation is part of the `Task` itself — `await`s respect it automatically, and you opt in to checking with `try Task.checkCancellation()`.

The other big shift: **actors**. They are Swift's headline answer to "shared mutable state across tasks." An actor serialises access to its mutable state at the type level, with the type system enforcing isolation:

```swift
actor BookCache {
    private var byID: [Book.ID: Book] = [:]

    func store(_ book: Book) { byID[book.id] = book }
    func book(id: Book.ID) -> Book? { byID[id] }
}

// Calling actor methods is await
let book = await cache.book(id: bookID)
```

There is no C# direct equivalent — the closest analogue is "a class wrapped in `lock`" but with compile-time checking that you can never forget to lock.

---

## Memory model

| C# | Swift |
|---|---|
| GC pause-and-mark | ARC at compile time — no pauses, deterministic |
| Finalizer (`~Foo()`) | `deinit` — runs immediately when refcount hits zero |
| `IDisposable` + `using (var x = …) { … }` | `defer { x.cleanup() }` inside the scope |
| `WeakReference<T>` | `weak var x: Foo?` (must be optional + class) |
| Retain cycles handled by GC tracing | **You handle retain cycles manually** — `[weak self]` in closures, `weak` references in delegates |

The biggest practical pitfall: **closures capture strong references by default.** In C# this matters mostly for performance; in Swift, with ARC, it can cause hard memory leaks. The pattern to internalise:

```swift
// Strong capture — leaks if `self` owns the closure (common in completion handlers)
networkClient.fetch { result in
    self.handle(result)
}

// Weak capture — `self` may be deallocated before completion
networkClient.fetch { [weak self] result in
    self?.handle(result)
}
```

See [ARC, Captures & Lifetimes](arc-and-lifetimes.md) for a complete treatment.

---

## Where it gets weird

1. **No `internal` across assemblies.** C# lets `InternalsVisibleTo` open a back door. Swift doesn't — `internal` is module-scoped and there is no override. If you need a public-but-not-API symbol, prefix it with `_` by convention or put it in a separate target with a clearer SPI.

2. **No `protected`.** Swift only has `private` / `fileprivate` / `internal` / `public` / `open`. To get protected-style access, factor the shared logic into a base class with `internal` access and a different module from consumers, or use `open` + final overrides — both clunky. Most teams sidestep by preferring composition over inheritance.

3. **`Codable` replaces `[Serializable]` + `JsonSerializer`.** No reflection at runtime — encoding/decoding is generated by the compiler from `Codable` conformance. Custom keys, dates, polymorphism patterns: see [Codable Customization](codable-deep.md).

4. **Trailing closures.** Swift lets you pull the last closure argument out of the parens entirely, which makes APIs read like control flow. C# devs sometimes parse this as "what just happened." Example:
    ```swift
    users.sort { $0.age < $1.age }     // trailing closure
    users.sort(by: { $0.age < $1.age }) // same call, paren'd
    ```

5. **`extension` is closer to C# extension methods, but more capable.** You can add stored-property-like behaviour via associated objects, conform a type to a protocol after the fact, and add nested types. Swift extensions are *part of the type's API surface within their visibility scope*, not just sugar over static methods.

6. **Nullable references vs Optionals.** C#'s nullable reference types are an annotation system layered on top of a runtime where every reference can technically be null. Swift's optionals are a real type — `T` and `T?` are different types, and there is no implicit nullability anywhere. Forgetting this leads to over-using `!` (force-unwrap) where you meant `??` (default).

7. **Static-on-protocols with associated types.** `interface` in C# can have static abstract members (since C# 11). Swift protocols have static requirements too, but combined with associated types you may need to use `some`/`any` to refer to them from variables. See the generics chapter.

---

## Real-world port: an MVVM ViewModel

C# MVVM with `INotifyPropertyChanged`:

```csharp
public sealed class UserListViewModel : INotifyPropertyChanged {
    public event PropertyChangedEventHandler? PropertyChanged;

    private bool _isLoading;
    public bool IsLoading {
        get => _isLoading;
        private set { _isLoading = value; OnChanged(nameof(IsLoading)); }
    }

    private List<User> _users = new();
    public List<User> Users {
        get => _users;
        private set { _users = value; OnChanged(nameof(Users)); }
    }

    private readonly IUserService _service;
    public UserListViewModel(IUserService service) => _service = service;

    public async Task LoadAsync(CancellationToken ct = default) {
        IsLoading = true;
        try {
            Users = await _service.FetchAsync(ct);
        } finally {
            IsLoading = false;
        }
    }

    private void OnChanged(string n) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
}
```

Swift with `@Observable` (iOS 17+):

```swift
import Observation

@Observable
@MainActor
final class UserListViewModel {
    private(set) var isLoading = false
    private(set) var users: [User] = []

    private let service: UserService

    init(service: UserService) {
        self.service = service
    }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            users = try await service.fetch()
        } catch {
            // surface error state — omitted for brevity
        }
    }
}
```

What disappeared:

- The `INotifyPropertyChanged` boilerplate. `@Observable` synthesises change tracking at compile time; SwiftUI views observing this VM rebuild automatically.
- The explicit `CancellationToken` plumbing. The caller's `Task` cancellation flows into `service.fetch()` automatically.
- The `try/finally`. `defer` is the Swift idiom — clearer at the call site.
- The mutable `_field` + property pair. `private(set)` makes a stored property externally read-only.

What appeared:

- `@MainActor`. The VM is touched from SwiftUI views and bindings; making the type main-actor-isolated means every property access from a background context becomes a compile-time `await`, not a runtime race.

---

## Xamarin/MAUI sunset specifics

If you're porting a Xamarin or MAUI app to native iOS, the practical migration shape:

1. **Extract platform-agnostic business logic** from your shared project into a Swift package. ViewModels, domain models, networking — port these directly. Most of `System.Net.Http` maps cleanly to `URLSession`, and `System.Text.Json` maps to `JSONDecoder`/`JSONEncoder`.

2. **Replace XAML with SwiftUI.** Bindings translate well: `{Binding Users}` becomes a SwiftUI `List(viewModel.users)` reading from an `@Observable` VM. Triggers and value converters map to view modifiers and computed properties.

3. **Replace `DependencyService` / `IServiceCollection` with constructor injection.** Swift has no built-in DI container; pass dependencies through initialisers. For larger apps, libraries like Factory or Needle exist, but for most Xamarin-scale apps the constructor-injection pattern is enough.

4. **Replace platform-specific code paths.** Anything in `#if IOS` blocks becomes the new app's primary code; the rest is dropped.

5. **Replace MessagingCenter with Combine, NotificationCenter, or AsyncStream.** Pick by use case — Combine for UI-bound streams, NotificationCenter for system events, AsyncStream for pull-style consumers.

The hardest part is usually XAML behaviour translation. SwiftUI is closer to MAUI than to WPF, but trigger-heavy XAML with custom value converters often needs reshaping into observable view models with computed properties.

---

## Where this fits with the rest of the guide

- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — `some` vs `any`, PATs, type erasure
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — actors, `@MainActor`, Swift 6 enforcement
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — closures, retain cycles, `[weak self]`
- [Codable Customization](codable-deep.md) — JSON encoding/decoding without reflection
- [Combine & AsyncStream](combine-and-async-streams.md) — Rx-shaped streams
- [Persistence](../03-architecture/persistence.md) — Core Data / SwiftData ↔ EF Core
- [UIKit for Web & Imperative-UI Developers](../04-ui-development/uikit-guide.md) — useful if your Xamarin app used renderers that exposed UIKit

---

*Last updated: 2026-05-04 — BUILD-24.*
