# Swift for Kotlin Developers

> Kotlin and Swift are near-twins. Both are statically typed, both have null safety baked into the type system, both prefer immutability, both have value types and reference types, both have structured concurrency. **The translation cost is the lowest of any source language.** This chapter focuses on the small set of differences that will trip you up.

---

## The 60-Second Mental Model

If you write idiomatic Kotlin, idiomatic Swift will feel like the same language with different keywords. The biggest pivots are:

1. **Default to `struct`, not `class`.** Where Kotlin pushes you toward `data class`, Swift pushes harder — most of your "model" types should be structs (value types).
2. **`async`/`await` instead of coroutines.** Same idea, slightly different ergonomics, no `Dispatcher` parameter on launches.
3. **No companion objects.** Static-like members live as `static` on the type itself.
4. **Protocols can have associated types**, which makes them more powerful than Kotlin interfaces but harder to use as variables — you'll meet `any P` and `some P` (see [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md)).
5. **Strict concurrency is real.** Kotlin lets you share mutable state across coroutines and tells you "be careful." Swift 6 refuses to compile until you prove it's safe.

---

## Variables, Types, Visibility

| Kotlin | Swift | Note |
|---|---|---|
| `val name = "Alice"` | `let name = "Alice"` | Both immutable. |
| `var count = 0` | `var count = 0` | Mutable. |
| `val n: Int = 1` | `let n: Int = 1` | Type ascription is `:` in both. |
| `lateinit var x: Foo` | `var x: Foo!` (rare) or `var x: Foo?` | Swift idiom prefers Optionals; IUOs (`Foo!`) only at framework boundaries. |
| `private`, `internal`, `public` | `private`, `fileprivate`, `internal`, `public`, `open` | Swift's `internal` is the default (same module). `open` is needed to subclass across modules. |
| `const val PI = 3.14` | `static let pi = 3.14` (in a type) | No top-level `const`; use a `static let` on a `enum` namespace. |
| `companion object { ... }` | `static` members on the type | No companion in Swift. |

```kotlin
// Kotlin
class Counter {
    companion object {
        const val MAX = 100
        fun create() = Counter()
    }
}
```

```swift
// Swift
class Counter {
    static let max = 100
    static func create() -> Counter { Counter() }
}
```

---

## Null Safety

Both languages model "missing" in the type system. The mechanics differ.

| Kotlin | Swift |
|---|---|
| `String?` | `String?` (sugar for `Optional<String>`) |
| `s?.length` (safe call) | `s?.count` (optional chaining) |
| `s ?: "default"` | `s ?? "default"` |
| `s!!` (force non-null) | `s!` (force unwrap) |
| `s?.let { ... }` | `if let s { ... }` or `if let s = s { ... }` |
| `requireNotNull(s)` | `guard let s else { throw ... }` |

```kotlin
// Kotlin
fun greet(name: String?) {
    val length = name?.length ?: 0
    name?.let { println("Hello, $it") }
}
```

```swift
// Swift
func greet(_ name: String?) {
    let length = name?.count ?? 0
    if let name { print("Hello, \(name)") }
}
```

### `guard let` — Kotlin's missing piece

Kotlin has no clean equivalent of Swift's `guard let`. It's the idiomatic way to early-return on nil:

```swift
func process(_ name: String?) -> String {
    guard let name, !name.isEmpty else {
        return "anonymous"
    }
    // `name` is non-optional here, for the rest of the function
    return name.uppercased()
}
```

You'll write this constantly. It replaces both `requireNotNull(...)` and the "null check at top" patterns.

---

## `data class` → `struct`

Kotlin's `data class` gives you `equals`/`hashCode`/`copy`/`toString`. Swift's `struct` gives you all of those automatically when properties conform to the right protocols, plus value semantics.

```kotlin
// Kotlin
data class User(val id: String, val name: String, val email: String)

val u1 = User("1", "Alice", "a@x.com")
val u2 = u1.copy(name = "Bob")        // copy with one field changed
```

```swift
// Swift
struct User: Equatable, Hashable, Codable {
    let id: String
    var name: String
    let email: String
}

let u1 = User(id: "1", name: "Alice", email: "a@x.com")
var u2 = u1
u2.name = "Bob"          // mutating a copy — no `copy` function needed
// or use a custom copy-with method if you prefer the Kotlin idiom
```

**Differences worth knowing:**

- Swift structs are **value-typed by default** — assignment copies. Kotlin's `data class` is still a reference type; `copy` exists because `=` would alias.
- Swift gives you `Equatable`/`Hashable`/`Codable` automatically when you declare conformance. Kotlin's `data class` gives you `equals`/`hashCode` for free but you still have to opt into JSON serialization.
- No automatic `componentN()` destructuring — Swift uses pattern matching on tuples or labeled property access instead.

---

## Sealed Classes ↔ Enums with Associated Values

Kotlin's `sealed class` and Swift's `enum` with associated values cover the same ground: a closed sum type with payloads.

```kotlin
// Kotlin
sealed class LoadState {
    object Idle : LoadState()
    object Loading : LoadState()
    data class Loaded(val articles: List<Article>) : LoadState()
    data class Failed(val error: Throwable) : LoadState()
}

when (state) {
    is LoadState.Idle -> showEmpty()
    is LoadState.Loading -> showSpinner()
    is LoadState.Loaded -> show(state.articles)
    is LoadState.Failed -> showError(state.error)
}
```

```swift
// Swift
enum LoadState {
    case idle
    case loading
    case loaded([Article])
    case failed(Error)
}

switch state {
case .idle: showEmpty()
case .loading: showSpinner()
case .loaded(let articles): show(articles)
case .failed(let error): showError(error)
}
```

Same idea, less ceremony. Swift's `switch` is exhaustive by default — adding a new case forces every `switch` to handle it (or use `default`/`@unknown default`).

### Sealed interfaces, multiple "shapes"

Kotlin's `sealed interface` for shared shape across cases maps to a Swift `protocol` plus an `enum` if you want both polymorphism and a closed set:

```swift
protocol Stateful {
    var canRetry: Bool { get }
}

enum LoadState: Stateful {
    case idle, loading, loaded([Article]), failed(Error)
    var canRetry: Bool {
        switch self {
        case .failed: true
        default: false
        }
    }
}
```

---

## Coroutines → `async`/`await` and `Task`

This is where the analogy is tightest, because Kotlin's coroutine design clearly inspired pieces of Swift Concurrency. Same vocabulary, different mechanics.

| Kotlin | Swift |
|---|---|
| `suspend fun foo()` | `func foo() async` |
| `suspend fun foo(): T` throwing | `func foo() async throws -> T` |
| `coroutineScope { ... }` | `await withTaskGroup(of: T.self) { ... }` |
| `async { ... }` (returns `Deferred<T>`) | `Task { ... }` (returns `Task<T, Error>`) |
| `launch { ... }` | `Task { ... }` (don't store if you don't need to) |
| `withContext(Dispatchers.Main) { ... }` | `await MainActor.run { ... }` |
| `withContext(Dispatchers.IO) { ... }` | Not needed — see below. |
| `Mutex.withLock { ... }` | `actor` — covered in [Concurrency & Sendable](concurrency-and-sendable.md). |
| `Flow<T>` | `AsyncSequence` (`AsyncStream`, etc.) |
| `MutableStateFlow<T>` | `@Published` (Combine) or `Observable` macro / `@State` for SwiftUI. |
| `SharedFlow<T>` | `PassthroughSubject` (Combine) or `AsyncStream` with continuation. |

### `Dispatchers.IO` doesn't exist in Swift

This catches Kotlin developers off-guard. Swift's concurrency runtime uses **cooperative threading** — there's no "I/O dispatcher" you switch to. When you call an async I/O function (`URLSession.data(from:)`, etc.), the runtime handles parking your task off the cooperative pool. You don't manually move work to a "blocking" pool.

What you *do* control is **actor isolation**. Code on `@MainActor` runs on the main thread; code on a custom actor runs serialized on that actor; everything else runs on the cooperative pool.

```kotlin
// Kotlin — explicit dispatcher hop
suspend fun loadAndUpdate() {
    val data = withContext(Dispatchers.IO) { fetchFromDisk() }
    withContext(Dispatchers.Main) { updateUI(data) }
}
```

```swift
// Swift — declare actor isolation, the runtime handles threading
@MainActor
func loadAndUpdate() async {
    let data = await fetchFromDisk()    // hops off main, comes back
    updateUI(data)
}
```

### `Flow` ↔ `AsyncSequence`

Cold streams in Kotlin map to `AsyncSequence` / `AsyncStream`:

```kotlin
fun ticker(): Flow<Int> = flow {
    var i = 0
    while (true) { emit(i++); delay(1000) }
}

ticker().collect { println(it) }
```

```swift
func ticker() -> AsyncStream<Int> {
    AsyncStream { continuation in
        Task {
            var i = 0
            while !Task.isCancelled {
                continuation.yield(i)
                i += 1
                try? await Task.sleep(for: .seconds(1))
            }
            continuation.finish()
        }
    }
}

for await i in ticker() {
    print(i)
}
```

`StateFlow`/`SharedFlow` reactive UI patterns map to either Combine (`@Published`) or — increasingly — the new `Observable` macro for SwiftUI. See [Architecture Patterns](../03-architecture/patterns.md).

### Structured concurrency — the same, but stricter

Both languages enforce parent-child task lifetimes. Kotlin's `coroutineScope` is the Swift `withTaskGroup`. Cancellation propagates the same way: cancel the parent, children unwind.

The big behavior difference: **Swift cancellation is cooperative.** Your task must explicitly check `Task.isCancelled` (or call a cancellation-aware API like `Task.sleep` that throws `CancellationError`). Kotlin's coroutines also need to be cooperative, but the canonical `withTimeoutOrNull` and built-in `delay` make it look automatic.

```swift
func longJob() async throws {
    for i in 0..<1_000_000 {
        try Task.checkCancellation()    // throws if cancelled
        await processItem(i)
    }
}
```

---

## Property Delegates ↔ Property Wrappers

Kotlin's `by` delegate syntax is conceptually the same as Swift's `@PropertyWrapper`:

```kotlin
// Kotlin
class Settings {
    var darkMode by Delegates.observable(false) { _, old, new ->
        println("changed: $old → $new")
    }
}
```

```swift
// Swift
class Settings {
    @Observed var darkMode = false
}

@propertyWrapper
struct Observed<Value> {
    private var value: Value
    init(wrappedValue: Value) { self.value = wrappedValue }
    var wrappedValue: Value {
        get { value }
        set { print("changed: \(value) → \(newValue)"); value = newValue }
    }
}
```

You'll see property wrappers everywhere in SwiftUI: `@State`, `@Binding`, `@StateObject`, `@ObservedObject`, `@EnvironmentObject`, `@Environment`, `@AppStorage`, `@Query`. They are not "magic" — they are this same delegate pattern, sometimes with a `projectedValue` (the `$` prefix) for the bound version.

---

## Scope Functions: `let`, `run`, `apply`, `also`, `with`

Kotlin's scope functions are a major idiom. Swift gives you only some equivalents — and idiomatic Swift simply uses fewer of them.

| Kotlin | Closest Swift |
|---|---|
| `obj?.let { ... }` | `if let obj { ... }` |
| `obj.run { ... }` | Just inline the code; no general analogue. |
| `obj.apply { ... }` | Use a builder closure or just construct + assign. |
| `obj.also { ... }` | Just call the side-effect; no chaining sugar. |
| `with(obj) { ... }` | Just inline; no `with` in Swift. |

The pragmatic translation: drop the scope-function chains. Swift code prefers explicit naming and short statements. If you find yourself missing `apply { }`, the answer is usually a static factory or a regular initializer with default parameters.

---

## Memory Model: GC → ARC

Kotlin/JVM: garbage collected, cycles are free, deinit-equivalent (`finalize`) is unreliable.

Swift: **deterministic reference counting**. No cycle collector — you must break cycles with `weak`/`unowned`. `deinit` runs predictably when the last reference drops.

```kotlin
// Kotlin — no leak even if a and b reference each other
class A { var b: B? = null }
class B { var a: A? = null }
```

```swift
// Swift — leaks unless one side is weak
class A { var b: B? }
class B { weak var a: A? }       // break the cycle here
```

This is the single biggest mental shift for Kotlin developers. Closures that capture `self` and live longer than the function call need `[weak self]`. See [ARC, Captures & Lifetimes](arc-and-lifetimes.md) for the full discipline.

---

## Generics & Protocols (Quick Pointers)

Kotlin's generic system is close to Java's. Swift's is closer to Rust's, with two big additions that surprise Kotlin developers:

1. **Protocols can have `associatedtype`** — like Kotlin's `interface Repo<T>` but with the type parameter on the *protocol*, not its uses.
2. **`some P` (opaque return) and `any P` (existential)** — Swift forces you to choose how a protocol is "used as a type" because PATs can't be used as ordinary types.

The full discussion is in [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md). The shortest summary:

| Kotlin | Swift |
|---|---|
| `interface Repo<T>` with `T` in method signatures | `protocol Repo` with `associatedtype Element` |
| `interface Drawable` (no generics) used as `List<Drawable>` | `[any Drawable]` (existential) |
| Function returning `Drawable` | `func make() -> some Drawable` (opaque) — preferred |
| `where T : Foo, T : Bar` | `where T: Foo & Bar` or generic constraints — same idea |

---

## Error Handling

Kotlin: exceptions, all unchecked. `Result<T>` for explicit handling.

Swift: `throws` functions with **typed** errors (Swift 6+: `throws(MyError)`), and explicit `do/try/catch`. Errors are propagated synchronously and across `await`.

```kotlin
// Kotlin
fun readConfig(): Config {
    return File("config.json").readText().let { Json.decodeFromString(it) }
}
// Caller may or may not realize this throws.
```

```swift
// Swift
func readConfig() throws -> Config {
    let url = URL.documentsDirectory.appending(path: "config.json")
    let data = try Data(contentsOf: url)
    return try JSONDecoder().decode(Config.self, from: data)
}
// Caller is forced to handle: try? / try! / try with do-catch.
```

`try?` returns `T?` on failure; `try!` traps on failure (avoid in production paths); plain `try` requires the surrounding function to be `throws` or wrapped in `do/catch`.

---

## Testing Idioms

| Kotlin | Swift |
|---|---|
| JUnit 5 / Kotest | XCTest (built-in), Swift Testing (newer, macro-based) |
| `@Test fun foo()` | `func testFoo()` (XCTest) or `@Test func foo()` (Swift Testing) |
| `assertEquals(expected, actual)` | `XCTAssertEqual(actual, expected)` or `#expect(actual == expected)` |
| MockK | No mainstream mocking lib; protocol-oriented hand-written mocks dominate. |
| `runTest { ... }` for coroutines | `func test() async throws { ... }` directly. |

The protocol-oriented design pushes you to inject dependencies as protocol parameters and write small in-test conforming structs. It's a different rhythm than `every { mock.foo() } returns ...` — you write one fake implementation per protocol, reuse it across tests.

---

## Module / Visibility

| Kotlin | Swift |
|---|---|
| `private` (file-level) | `fileprivate` |
| `private` (class member) | `private` |
| `internal` (module-level) | `internal` (same — and is the default) |
| `protected` | No equivalent — closest is internal + a comment, or a separate module. |
| `public` | `public` (and `open` to allow subclassing across modules) |

Swift's `private` actually means "this declaration only" plus extensions in the same file. Kotlin's `private` on a class member is similar but doesn't extend to extensions defined elsewhere.

---

## The Five Most Surprising Things

1. **Default to `struct`.** Your model layer should be almost entirely value types. If you reach for `class`, justify why (identity, shared mutable state, Objective-C interop, framework requirement).
2. **You must break retain cycles yourself.** No GC will save you. Closures stored on `self` need `[weak self]`. Tasks stored on `self` need `[weak self]` and cancellation in `deinit`.
3. **`@MainActor` everywhere on view models.** Don't `withContext(Dispatchers.Main)` your way through it — annotate the class once and the compiler tracks it for you.
4. **Strict concurrency rejects shared mutable state by default.** Your Kotlin habit of "I'll just put a `Mutex` around it" is wrong here — use an `actor`. The compiler will tell you when sharing is unsafe.
5. **No companion object.** `static let` and `static func` on the type or on a dedicated `enum SomeNamespace` (an empty enum used as a namespace).

---

## Mapping Cheat Sheet

| Kotlin | Swift |
|---|---|
| `data class User(...)` | `struct User: Equatable, Hashable, Codable { ... }` |
| `class Foo : Bar()` | `class Foo: Bar { ... }` |
| `interface P` | `protocol P` |
| `sealed class S` with subclasses | `enum S` with associated values |
| `object Singleton` | `enum Singleton { static ... }` or `final class Singleton` with `static let shared` |
| `companion object` | `static` members on the type |
| `lateinit var` | `var x: T?` (preferred) or `var x: T!` (rare) |
| `val x by lazy { ... }` | `lazy var x = ...` (only inside classes/structs) |
| `s?.length ?: 0` | `s?.count ?? 0` |
| `s!!` | `s!` |
| `s?.let { ... }` | `if let s { ... }` |
| `when (x) { is Foo -> ... }` | `switch x { case let foo as Foo: ... }` |
| `suspend fun f()` | `func f() async` |
| `withContext(Dispatchers.Main)` | `@MainActor` annotation, or `await MainActor.run { ... }` |
| `Flow<T>` | `AsyncSequence` / `AsyncStream<T>` |
| `MutableStateFlow<T>` | `@Published var ...` (Combine) or `@Observable` (new) |
| `Mutex().withLock { }` | `actor` |
| `runBlocking` | Don't. Avoid blocking the current thread; use `Task` and let the caller `await`. |
| `try { } catch (e: Exception) { }` | `do { try ... } catch { }` |
| Property delegate `by` | `@propertyWrapper` |
| `@JvmStatic` | Not needed — Swift `static` is already callable from objc as a class method. |

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — full coverage of `actor`, `@MainActor`, `Sendable`.
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — the GC→ARC mental shift.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — `some` vs `any`, PATs.

**Next:** [Swift for Java Developers](from-java.md).

*Last updated: 2026-05-04*
