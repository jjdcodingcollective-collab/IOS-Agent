# Swift for Java Developers

> Java and Swift are both statically typed and curly-braced, but the design philosophies diverge sharply. **Where Java centers on classes, Swift centers on values.** Where Java uses checked exceptions, Swift uses an opt-in `throws` mechanism. Where Java has a GC, Swift has ARC. This chapter walks you through the largest deltas a Java developer will hit.

---

## The 60-Second Mental Model

1. **Default to `struct`, not `class`.** This is the single biggest stylistic shift. Most of your "POJOs" become value-typed structs.
2. **No checked exceptions.** Swift has `throws`/`try`/`catch`, but the propagation model is different — every error is "unchecked" in the Java sense, but the compiler still forces you to acknowledge it via `try`.
3. **No GC.** Reference-counted objects, deterministic destruction, you must avoid retain cycles yourself.
4. **First-class generics with reified types.** Generic type info isn't erased at runtime the way Java's is. You can ask "what type is `T`?" inside a generic function.
5. **Protocols replace interfaces** — but Swift protocols can have associated types and default implementations, which makes them stronger than Java interfaces and harder to use as types directly.

---

## Variables, Types, Visibility

| Java | Swift | Note |
|---|---|---|
| `final String name = "Alice";` | `let name = "Alice"` | Swift's `let` is Java's `final`. |
| `String name = "Alice";` | `var name = "Alice"` | `var` is mutable. |
| `int n = 1;` | `let n: Int = 1` | Type after the name with `:`. Or just `let n = 1` — inference. |
| `private`, `protected`, `package`, `public` | `private`, `fileprivate`, `internal`, `public`, `open` | Swift's `internal` (same module) is the default. `open` allows subclassing across modules. |
| `static final int MAX = 100;` | `static let max = 100` (in a type) | No top-level `static`; put constants on a type or namespace enum. |
| `enum Color { RED, GREEN, BLUE }` | `enum Color { case red, green, blue }` | Cases are values, not subclasses. |
| `Optional<String>` | `String?` | Built into the type system, not a wrapper class. |

---

## Default to `struct`, Not `class`

Java has only classes. Swift has `struct` (value type, copied on assignment) and `class` (reference type, ARC-managed). For your typical "data carrier," `struct` is correct.

```java
// Java
public class User {
    private final String id;
    private final String name;
    private final String email;
    public User(String id, String name, String email) { ... }
    // getters, equals, hashCode, toString — Lombok or 30 lines of boilerplate
}
```

```swift
// Swift
struct User: Equatable, Hashable, Codable {
    let id: String
    let name: String
    let email: String
}
```

Swift gives you:
- Memberwise init (`User(id: ..., name: ..., email: ...)`) for free.
- `Equatable`, `Hashable`, `Codable` synthesized when you declare conformance.
- Value semantics — copies don't alias. No defensive copying needed.

**When to still use `class`:**
- The type has identity that survives copying (a database connection, a file handle).
- You need `deinit` for resource cleanup.
- You're inheriting from a framework class (`UIView`, `NSObject`).
- You need reference semantics deliberately (a shared `Coordinator` between view models).
- Objective-C interop requires it.

For 70%+ of types that you'd reflexively write as `class` in Java, the Swift answer is `struct`.

---

## Optionals Replace Nullability

Java made null its billion-dollar mistake; Swift bakes nullability into the type system.

| Java | Swift |
|---|---|
| `String s = ...;` (could be null) | `String` — never null |
| `String s = ...;` with `@Nullable` | `String?` (Optional) |
| `Optional<String>` | `String?` |
| `s != null ? s.length() : 0` | `s?.count ?? 0` |
| `Objects.requireNonNull(s)` | `guard let s else { throw ... }` |
| `s.orElse("default")` | `s ?? "default"` |
| `s.ifPresent(name -> ...)` | `if let s { ... }` |

```swift
func greet(_ name: String?) -> String {
    guard let name, !name.isEmpty else {
        return "Anonymous"
    }
    // `name` is `String` (non-optional) for the rest of the function
    return "Hello, \(name)"
}
```

`guard let` is the idiom you'll write most often. It replaces top-of-method null checks and the precondition pattern.

---

## Error Handling: `throws` Without "Checked"

Java has *checked* exceptions: a method that throws `IOException` must declare it, and callers must handle it. Swift has the same compiler enforcement but no inheritance hierarchy of error types — every `Error` is essentially "checked" at the language level.

```java
// Java
public Config readConfig() throws IOException {
    String text = Files.readString(path);
    return objectMapper.readValue(text, Config.class);
}

// Caller MUST do one of: try-catch, throws clause, or wrap.
```

```swift
// Swift
func readConfig() throws -> Config {
    let data = try Data(contentsOf: url)
    return try JSONDecoder().decode(Config.self, from: data)
}

// Caller MUST do one of:
let c1 = try readConfig()      // function must `throws`
let c2 = try? readConfig()     // returns Config? — nil on error
let c3 = try! readConfig()     // crashes on error (avoid in production)

do {
    let c = try readConfig()
} catch {
    // `error` is in scope as the caught Error
}
```

### Typed throws (Swift 6+)

```swift
enum ConfigError: Error {
    case fileNotFound, malformed
}

func readConfig() throws(ConfigError) -> Config { ... }
```

You can constrain `throws` to a specific error type — a feature Java's checked exceptions arguably tried for and made unwieldy. In Swift, typed throws are opt-in and use them where the error vocabulary is closed.

### No try-with-resources

Swift doesn't have AutoCloseable. The closest analogue is `defer`:

```swift
func readFile() throws {
    let handle = try FileHandle(forReadingFrom: url)
    defer { try? handle.close() }
    // ... use handle ...
    // close runs when function exits, by any path
}
```

Or use `class` with a `deinit` for the long-lived case.

---

## Generics: Stronger and Reified

Java's generics are erased — at runtime, `List<String>` is just `List`. Swift's generics keep type information at runtime.

```java
// Java
public <T> T parse(String json, Class<T> clazz) { ... }
// Caller has to pass the Class<T> token because of erasure.
parse(json, User.class);
```

```swift
// Swift
func parse<T: Decodable>(_ json: Data) throws -> T { ... }
// Type inferred from context, no need to pass a token:
let user: User = try parse(json)
```

### Constraints

| Java | Swift |
|---|---|
| `<T extends Foo>` | `<T: Foo>` |
| `<T extends Foo & Bar>` | `<T: Foo & Bar>` or `<T> where T: Foo, T: Bar` |
| Wildcards `<? extends T>` | Not directly — use generic functions or opaque types. |
| `<T extends Comparable<T>>` | `<T: Comparable>` (Swift's `Comparable` is self-comparable) |

### Protocols with Associated Types — the Java surprise

Java's `interface Repo<T>` lets you use `Repo<User>` as a variable type. Swift's `protocol Repo` with `associatedtype Entity` *does not* — you can't write `var r: Repo` because the associated type isn't resolved.

```swift
protocol Repo {
    associatedtype Entity
    func find(id: String) -> Entity?
}

// Won't compile:
// var r: Repo                      // error: PAT can't be used as a variable type

// Two options to use it as a "variable":
var r1: any Repo                    // existential — type-erased
func makeRepo() -> some Repo { ... } // opaque — concrete but hidden
```

This is the single most-confusing Swift surprise for Java developers. Read [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) in full when you hit your first PAT compile error.

---

## Streams → Sequence, lazy, async

| Java | Swift |
|---|---|
| `list.stream().map(...).filter(...).collect(toList())` | `list.map(...).filter(...)` (eager, on `Array`) |
| `list.stream().lazy()` (rare) | `list.lazy.map(...).filter(...)` |
| `Stream.iterate(...)` | `sequence(first:next:)` |
| `Collectors.groupingBy` | `Dictionary(grouping:by:)` |
| `Stream` (one-shot) | `Sequence` (multi-shot in most cases), `IteratorProtocol` |
| `parallelStream()` | `TaskGroup` / `withTaskGroup` |
| `Stream.flatMap` | `flatMap` (and `compactMap` for filtering nils) |

```swift
let names = users
    .filter { $0.isActive }
    .map { $0.name.uppercased() }
    .sorted()

let byCity = Dictionary(grouping: users, by: \.city)
```

### Async pipelines

For Java's reactive streams (RxJava, Project Reactor, Flow API), Swift has two answers:

- **Combine** — Apple's reactive framework. `Publisher`, `.map`, `.filter`, `.sink`. Used heavily in pre-`async`/`await` SwiftUI/Combine codebases. See [Reactive Patterns](../03-architecture/patterns.md).
- **AsyncSequence** — built into the language. `for await x in stream { }` is the loop form.

---

## Concurrency: Goodbye `synchronized`, Hello `actor`

Java's primitives: `synchronized`, `ReentrantLock`, `volatile`, `ConcurrentHashMap`, `ExecutorService`, `CompletableFuture`.

Swift's primitives: `async`/`await`, `Task`, `actor`, `@MainActor`, `Sendable`. The runtime is cooperative — there's no thread-per-task; tasks share a small pool.

| Java | Swift |
|---|---|
| `synchronized` block / method | `actor` (state isolated to the actor; outside callers `await`) |
| `volatile` | Usually not needed — actor isolation handles visibility. |
| `ExecutorService.submit(callable)` | `Task { ... }` |
| `CompletableFuture<T>` | `Task<T, Error>` or `async` function |
| `CompletableFuture.thenCompose` | `await` — sequential by default |
| `CountDownLatch` | `await` on a `Task` or use a `TaskGroup` |
| `ConcurrentHashMap` | `actor MyMap { var dict: [K:V] = [:]; ... }` |
| `ThreadLocal<T>` | `@TaskLocal` |

```swift
actor SessionCache {
    private var entries: [String: Session] = [:]
    func get(_ id: String) -> Session? { entries[id] }
    func set(_ s: Session, id: String) { entries[id] = s }
}

let cache = SessionCache()
let s = await cache.get("abc")    // serialized access to the actor's state
```

The Swift compiler enforces data-race freedom (Swift 6 strict concurrency). Crossing actors requires `Sendable` data. Read [Concurrency & Sendable](concurrency-and-sendable.md) before your first PR.

### `@MainActor` ↔ "must run on UI thread"

Swing/JavaFX have "must run on EDT" rules; Android has "must run on UI thread." Swift formalizes this as the **main actor**:

```swift
@MainActor
final class HomeViewModel: ObservableObject {
    @Published var items: [Item] = []

    func load() async {
        let fetched = await api.fetch()      // hops off main, comes back
        items = fetched                       // safe — back on main
    }
}
```

The annotation propagates through the class. The compiler refuses to call main-actor methods from background contexts without an `await`.

---

## Memory Model: GC → ARC

Java relies on the JVM GC. Swift uses **deterministic reference counting**. The shifts:

1. **No cycle collector.** Two objects pointing at each other strongly will leak. Use `weak` or `unowned` to break cycles.
2. **`deinit` is reliable.** Unlike Java's `finalize` (deprecated, unreliable), Swift's `deinit` runs the moment the last reference drops.
3. **Closures capture references too.** Storing a closure on `self` that references `self` creates a cycle until you write `[weak self]`.

```swift
class Author { var book: Book? }
class Book { weak var author: Author? }       // weak breaks the cycle
```

See [ARC, Captures & Lifetimes](arc-and-lifetimes.md) for the full discipline.

---

## JSON & Records → `Codable`

Java records (Java 14+) are conceptually similar to Swift structs, but have no built-in JSON. You combine records with Jackson or Gson. Swift's `Codable` handles encoding and decoding directly.

```java
// Java
record User(String id, String name) {}
ObjectMapper mapper = new ObjectMapper();
User u = mapper.readValue(json, User.class);
```

```swift
// Swift
struct User: Codable {
    let id: String
    let name: String
}

let u = try JSONDecoder().decode(User.self, from: data)
let json = try JSONEncoder().encode(u)
```

For mismatched JSON keys, override `CodingKeys`:

```swift
struct User: Codable {
    let id: String
    let displayName: String

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
    }
}
```

For dates, custom strategies, and deeper customization, see [JSON & Codable](../05-networking/json-and-codable.md).

---

## Testing Idioms

| Java | Swift |
|---|---|
| JUnit 5 | XCTest (built-in), Swift Testing (newer) |
| `@Test void foo()` | `func testFoo()` (XCTest) or `@Test func foo()` (Swift Testing) |
| `assertEquals(expected, actual)` | `XCTAssertEqual(actual, expected)` or `#expect(actual == expected)` |
| Mockito | No mainstream library — protocols + small fake structs are idiomatic. |
| `@BeforeEach` | `override func setUp()` (XCTest) |
| Parameterized tests (JUnit 5) | `@Test(arguments: [...])` (Swift Testing) |
| `assertThrows` | `XCTAssertThrowsError` or `#expect(throws: ErrorType.self)` |

The protocol-driven dependency-injection style is universal: define a protocol for the dependency, implement a fake conforming struct for tests, inject via initializer.

---

## Build & Modules

| Java | Swift |
|---|---|
| Maven `pom.xml`, Gradle `build.gradle` | `Package.swift` (Swift Package Manager) |
| Maven Central | Swift Package Index, GitHub URLs directly |
| `package com.example.foo;` | No file-level package; modules == SPM packages or Xcode targets |
| Bytecode `.class`, JAR | `.swiftmodule`, native binary |
| Gradle `compileOnly`, `runtimeOnly` | No equivalent — usual `dependencies: [...]` in SPM |

There is no per-file `package` declaration. A *module* (an SPM package or an Xcode target) is the unit of `internal` visibility. Files within a module can see each other's `internal` declarations directly without imports.

---

## The Five Most Surprising Things

1. **Default to value types.** "I'll just write a class" is the wrong reflex. Use `struct` for data, `class` for identity.
2. **Strict concurrency rejects shared mutable state.** Java's "wrap it in `synchronized`" muscle memory is wrong — use an `actor` and let the compiler help you.
3. **Protocols with associated types are not interfaces.** When you need to use one as a "variable," you have to pick `any P` or `some P`. Don't fight it; learn it.
4. **No checked exceptions, but errors are still mandatory.** `try` is forced. The verbosity of `do/catch` becomes natural; you rarely silently ignore errors the way `catch (Exception ignored) {}` lets Java callers do.
5. **No companion-object workaround.** Static-like state lives directly on the type or in a namespace `enum`. There's no class-singleton-with-static-fields anti-pattern to migrate.

---

## Mapping Cheat Sheet

| Java | Swift |
|---|---|
| `class Foo { ... }` | `struct Foo { ... }` (default) or `class Foo { ... }` |
| `interface I { ... }` | `protocol I { ... }` |
| `abstract class A` | `class A { ... }` (Swift has no `abstract` keyword; use protocols + extensions for shared behavior) |
| `record User(String id, String name)` | `struct User: Equatable, Hashable { let id: String; let name: String }` |
| `enum Color { RED, GREEN }` | `enum Color { case red, green }` |
| `final` field | `let` |
| `static` field | `static` (on a type) |
| `Optional<T>` | `T?` |
| `List<T>` | `[T]` (Array) |
| `Map<K, V>` | `[K: V]` (Dictionary) |
| `Set<T>` | `Set<T>` |
| `String.format("...")` | `"\(value)"` (string interpolation) |
| `try { ... } catch (E e) { ... }` | `do { try ... } catch let e as E { ... }` |
| `throw new IOException("...")` | `throw MyError.fileNotFound` |
| `synchronized (lock) { ... }` | `actor` |
| `CompletableFuture<T>` | `Task<T, Error>` or `async` function |
| `ExecutorService.submit` | `Task { ... }` |
| `@Override` | `override` |
| `@Nullable T` | `T?` |
| `@NotNull T` | `T` (non-optional is the default) |
| `instanceof Foo` | `is Foo` (test) or `as? Foo` (cast) |
| `(Foo) x` | `x as! Foo` (force) or `x as? Foo` (safe) |
| `Object` | `Any` (any type) or `AnyObject` (any class) |
| `getClass()` | `type(of: x)` |
| Java 8 lambdas `(x) -> x * 2` | `{ $0 * 2 }` or `{ x in x * 2 }` |
| Method reference `String::length` | `\.count` (key path) where applicable |
| `BigDecimal` | `Decimal` |
| `LocalDateTime` | `Date` (with `Calendar`) — see [Dates](../06-platform-services/dates.md) |
| `UUID.randomUUID()` | `UUID()` |

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — for the `actor`/`@MainActor`/`Sendable` model.
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — for the GC→ARC mental shift.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — for the PAT/`some P`/`any P` topic.

**Next:** [Swift for Python Developers](from-python.md).

*Last updated: 2026-05-04*
