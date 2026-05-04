# Swift for Python Developers

> Swift is everything Python isn't: statically typed, ahead-of-time compiled, no GIL, deterministic memory management, and pickier about what counts as "true." If you've spent years trusting duck-typing and runtime introspection, this chapter is your acclimatization. The good news: once the compiler is on your side, you write fewer tests and ship fewer crashes.

---

## The 60-Second Mental Model

1. **Static, inferred types.** You won't write types everywhere, but the compiler will know them everywhere. There is no `Any`-by-default.
2. **No truthy/falsy.** `if x:` doesn't work. You explicitly compare: `if x.isEmpty`, `if x != nil`, `if count > 0`.
3. **Optionals are not `None`.** `Optional<T>` is a real type in the type system; you can't accidentally call a method on `nil`.
4. **Default to `struct`, not `class`.** Most Python classes that are just data carriers (`dataclass`-shaped) become Swift structs.
5. **No GIL — real parallelism.** Swift's concurrency is built around `actor`s and `async`/`await`; multiple threads run truly in parallel.
6. **Compile errors are your friend.** Most "tests" you'd write in Python become compiler-enforced invariants in Swift.

---

## Variables, Types, Visibility

| Python | Swift | Note |
|---|---|---|
| `x = 1` | `let x = 1` (immutable) or `var x = 1` (mutable) | Type inferred to `Int`. |
| `x: int = 1` | `let x: Int = 1` | Explicit type ascription with `:`. |
| `X = 100` (constant convention) | `let X = 100` (compiler-enforced) | Swift `let` is a real binding constraint. |
| `_private` (convention) | `private var ...` (enforced) | Swift `private` blocks access; Python's `_` is naming-only. |
| `__name` (name mangling) | `private` is enough — no name mangling needed. | |

```swift
let pi = 3.14                    // Double
let count: Int = 10              // explicit
var name = "Alice"               // mutable String
name = "Bob"                     // OK
// pi = 3.15                     // ❌ — `let` is constant
```

You'll find the compiler refusing to "just figure it out" in places Python would. That's the point.

---

## Static Typing — Retraining Your Reflexes

Where Python lets you write:

```python
def add(a, b):
    return a + b
```

…and pass anything that supports `+`, Swift demands you commit:

```swift
func add(_ a: Int, _ b: Int) -> Int { a + b }
// or generic:
func add<T: Numeric>(_ a: T, _ b: T) -> T { a + b }
```

The generic form (`T: Numeric`) is Swift's analogue of duck typing — except the duck has a contract (a *protocol*) that the compiler verifies.

### Type inference still does a lot

You don't need to annotate every variable. Inference covers most local code:

```swift
let users = [User(name: "A"), User(name: "B")]    // [User]
let active = users.filter { $0.isActive }         // [User]
let names = users.map(\.name)                     // [String]
```

Annotate at *boundaries*: function signatures, public properties, ambiguous initializers. Inside function bodies, inference is enough.

---

## Optionals Replace `None`

Python's `None` can be assigned to anything. Swift's `nil` belongs only to `Optional<T>`, which is a real type — `T?` is sugar for `Optional<T>`.

```python
# Python
def find_user(id):
    if id == "missing":
        return None
    return User(id=id, name="Alice")

u = find_user("missing")
print(u.name)                # AttributeError at runtime
```

```swift
// Swift
func findUser(id: String) -> User? {
    id == "missing" ? nil : User(id: id, name: "Alice")
}

let u = findUser(id: "missing")
// print(u.name)            // ❌ compile error — u is User?, not User
print(u?.name ?? "unknown")   // explicitly handles nil
```

### Idioms to learn

```swift
// Optional chaining — call a method only if non-nil
let length = name?.count           // Int? — nil if name is nil

// Nil coalescing — provide a default
let display = name ?? "Anonymous"  // String

// if let — bind if non-nil
if let name {
    print(name)                    // name is String here
}

// guard let — early return if nil
guard let name else { return }
print(name)                        // name is String for the rest of the scope
```

`guard let` is the Swift idiom for "validate this isn't None and bail otherwise" — your `if x is None: return` translation.

---

## Classes → Structs (Mostly)

Swift's `class` is closest to Python's class. But Swift gives you `struct` (a value type, copied on assignment) — and most "data classes" you'd write in Python are better as structs in Swift.

```python
# Python
from dataclasses import dataclass

@dataclass
class User:
    id: str
    name: str
    email: str
```

```swift
// Swift
struct User: Equatable, Hashable, Codable {
    let id: String
    var name: String
    let email: String
}
// — auto-generated init, ==, hash, JSON encode/decode
// — copies have value semantics: assigning one doesn't alias
```

**Use `class` instead of `struct` when:**
- The object has identity that survives copying (a database connection, an API client).
- You need inheritance (rare in Swift; protocols + extensions usually do better).
- You're inheriting from a framework class (`UIView`, `NSObject`).
- Reference semantics are deliberate (a shared `Coordinator`).
- Objective-C interop forces it.

For Python's `@dataclass`-style "bag of data," **always struct**.

---

## "Truthiness" Doesn't Exist

Python:

```python
if user_name:                # truthy if non-empty
    greet(user_name)
if items:                    # truthy if non-empty list
    process(items)
```

Swift:

```swift
if !userName.isEmpty {        // explicit
    greet(userName)
}
if !items.isEmpty {
    process(items)
}
if count > 0 { ... }
if let value { ... }          // bind & test in one step
```

**You must compare explicitly.** This catches a remarkable amount of bugs at compile time. If you instinctively type `if x:`, you'll hit a compile error.

---

## List/Dict Comprehensions → `map`/`filter`/`reduce`

| Python | Swift |
|---|---|
| `[x * 2 for x in xs]` | `xs.map { $0 * 2 }` |
| `[x for x in xs if x > 0]` | `xs.filter { $0 > 0 }` |
| `[x.name for x in users if x.active]` | `users.filter(\.active).map(\.name)` |
| `{k: v for k, v in pairs}` | `Dictionary(uniqueKeysWithValues: pairs)` |
| `{x.id: x for x in users}` | `Dictionary(uniqueKeysWithValues: users.map { ($0.id, $0) })` |
| `sum(xs)` | `xs.reduce(0, +)` or `xs.reduce(0) { $0 + $1 }` |
| `any(p(x) for x in xs)` | `xs.contains(where: p)` |
| `all(p(x) for x in xs)` | `xs.allSatisfy(p)` |
| `sorted(xs, key=lambda x: x.name)` | `xs.sorted(by: { $0.name < $1.name })` or `xs.sorted(using: KeyPathComparator(\.name))` |
| `zip(a, b)` | `zip(a, b)` (returns `Zip2Sequence`) |

`$0`, `$1`, etc. are positional shorthand inside closures. The key path syntax `\.name` replaces `lambda x: x.name`.

---

## Inheritance & Multiple Inheritance → Protocol Composition

Python supports multiple inheritance. Swift supports **single class inheritance** — but classes (and structs and enums) can conform to multiple **protocols**.

```python
# Python
class Loggable:
    def log(self): ...

class Cacheable:
    def cache_key(self): ...

class User(Loggable, Cacheable):
    pass
```

```swift
// Swift
protocol Loggable { func log() }
protocol Cacheable { var cacheKey: String { get } }

struct User: Loggable, Cacheable {
    func log() { ... }
    var cacheKey: String { ... }
}
```

Protocols can have **default implementations** via extensions:

```swift
extension Loggable {
    func log() { print(self) }    // default — implementers can override
}

struct User: Loggable {}          // gets the default automatically
```

This covers most uses of mixins / multiple inheritance from Python — and Swift verifies the contracts at compile time.

---

## Duck Typing → Protocols

The Python motto "if it walks like a duck and quacks like a duck, it's a duck" maps to Swift protocols:

```python
def describe(x):
    return f"{x.name} ({x.age})"
# Works on anything with .name and .age
```

```swift
protocol Describable {
    var name: String { get }
    var age: Int { get }
}

func describe(_ x: some Describable) -> String {
    "\(x.name) (\(x.age))"
}
```

The compiler now enforces what was previously discovered at runtime. The cost is one `protocol` declaration; the benefit is "this function works on these types" being checked statically.

For more advanced uses (associated types, opaque returns, existentials), see [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md).

---

## Exception Handling: `throws` Without `Exception`

Python's `try/except` translates to Swift's `do/try/catch`:

```python
# Python
try:
    config = read_config()
except FileNotFoundError as e:
    config = default_config()
except Exception as e:
    log(e)
    raise
```

```swift
// Swift
do {
    let config = try readConfig()
} catch ConfigError.fileNotFound {
    config = defaultConfig
} catch {
    log(error)                  // `error` is auto-bound as `Error`
    throw error
}
```

Differences:

- A function that can throw must declare `throws`. Callers must use `try`. There's no implicit propagation.
- There's no class hierarchy — `Error` is a protocol you make custom enums conform to.
- `try?` returns `T?` on failure; `try!` traps. Use `try!` only when failure is a programmer error.

```swift
enum ConfigError: Error {
    case fileNotFound, malformed
}

func readConfig() throws -> Config {
    guard FileManager.default.fileExists(atPath: path) else {
        throw ConfigError.fileNotFound
    }
    // ...
}
```

---

## No GIL — Real Parallelism

Python's GIL means only one thread runs Python bytecode at a time. Swift has no such restriction. **Multiple threads run in parallel for real.** That makes the language faster, and also makes data races a real risk that the compiler catches.

### `actor` instead of `threading.Lock`

```python
# Python — typical pattern
import threading

class Cache:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}
    def get(self, k):
        with self._lock: return self._data.get(k)
    def set(self, k, v):
        with self._lock: self._data[k] = v
```

```swift
// Swift
actor Cache {
    private var data: [String: Value] = [:]
    func get(_ k: String) -> Value? { data[k] }
    func set(_ v: Value, for k: String) { data[k] = v }
}

let cache = Cache()
let v = await cache.get("k1")     // actor calls are async from outside
```

`actor`s serialize all access automatically. No locks, no `with self._lock:` boilerplate.

### `async`/`await`

Python had to bolt `asyncio` on. Swift has it baked in:

```swift
func loadHomeScreen() async throws -> HomeData {
    async let user = api.fetchUser()
    async let articles = api.fetchArticles()
    return try await HomeData(user: user, articles: articles)
}
```

The `async let` syntax launches both calls concurrently; `await` joins them at the end. There's no `asyncio.gather`, no event loop to manage explicitly.

For the full concurrency picture (`Sendable`, `@MainActor`, `Task`, `TaskGroup`), see [Concurrency & Sendable](concurrency-and-sendable.md).

---

## Decorators → Property Wrappers + Result Builders

Python decorators serve many roles. In Swift, the use cases split:

| Python | Swift |
|---|---|
| `@property` | Computed property: `var x: Int { ... }` |
| `@dataclass` | `struct` + `Equatable`/`Hashable`/`Codable` conformance (synthesized) |
| `@cached_property` | `lazy var x = ...` (lazy stored property) |
| `@staticmethod` | `static func ...` |
| `@classmethod` | `static func ...` (Swift doesn't separate — `Self` is the type) |
| Custom `@authorize` decorator | Function wrapping or a property wrapper, depending on shape |
| `@app.route("/")` (Flask) | Result builders (e.g., the `@ViewBuilder` macro in SwiftUI) |

### Property wrappers

```swift
@propertyWrapper
struct Clamped<Value: Comparable> {
    var value: Value
    let range: ClosedRange<Value>
    init(wrappedValue: Value, _ range: ClosedRange<Value>) {
        self.range = range
        self.value = min(max(wrappedValue, range.lowerBound), range.upperBound)
    }
    var wrappedValue: Value {
        get { value }
        set { value = min(max(newValue, range.lowerBound), range.upperBound) }
    }
}

struct Volume {
    @Clamped(0...100) var level: Int = 50
}

var v = Volume()
v.level = 200          // automatically clamped to 100
```

You'll see them constantly in SwiftUI: `@State`, `@Binding`, `@StateObject`, `@ObservedObject`, `@EnvironmentObject`, `@AppStorage`, `@FocusState`.

---

## Memory: Refcount + Cycle Collector → Refcount Only

Python uses reference counting **plus** a cycle collector. Swift uses reference counting **only** — there is no cycle collector. Cycles between two `class` instances will leak unless you explicitly use `weak` or `unowned`.

```swift
class Author { var book: Book? }
class Book { weak var author: Author? }    // weak — breaks the cycle
```

For closures stored on a class instance that capture `self`:

```swift
class ViewModel {
    var onComplete: (() -> Void)?
    func start() {
        onComplete = { [weak self] in       // capture list breaks the cycle
            guard let self else { return }
            self.process()
        }
    }
}
```

This is the single most-recurring gotcha for Python developers. See [ARC, Captures & Lifetimes](arc-and-lifetimes.md) for the full discipline.

---

## Modules, Imports, Packages

| Python | Swift |
|---|---|
| `import foo` | `import Foo` (module) |
| `from foo import bar` | No equivalent — you import the module, then use `Foo.bar`. |
| `pip install`, `requirements.txt` | Swift Package Manager via `Package.swift` |
| `pyproject.toml` | `Package.swift` |
| `__init__.py` | No equivalent — modules are SPM packages or Xcode targets |
| Virtual env (`venv`) | Per-project SPM resolution; no global env to manage |

There's no per-symbol `from foo import bar`. You import the whole module and qualify or rely on inference:

```swift
import Foundation
let url = URL(string: "https://example.com")    // URL is from Foundation
```

---

## Testing Idioms

| Python | Swift |
|---|---|
| `pytest` | XCTest (built-in), Swift Testing (newer) |
| `def test_foo():` | `func testFoo()` (XCTest) or `@Test func foo()` (Swift Testing) |
| `assert x == y` | `XCTAssertEqual(x, y)` or `#expect(x == y)` |
| `pytest.raises(ValueError)` | `XCTAssertThrowsError(...)` or `#expect(throws: MyError.self)` |
| `unittest.mock` | No mainstream library — protocols + small fake structs are idiomatic |
| `pytest.fixture` | XCTest `setUp`/`tearDown` or just a helper function |
| Parameterized: `@pytest.mark.parametrize` | `@Test(arguments: [...])` (Swift Testing) |

The protocol-driven dependency injection style is universal: declare a protocol for the dependency, write a fake conforming struct in tests, inject via initializer.

---

## PythonKit — When You Genuinely Need Python

If you're porting a project that depends heavily on Python ML libraries (NumPy, PyTorch, etc.), [PythonKit](https://github.com/pvieito/PythonKit) lets Swift call into a Python interpreter. It's not what you want for a real iOS app (Apple won't ship a CPython interpreter), but it's useful for macOS tools or one-shot data wrangling.

For iOS production use, the right answer is to port the model to Core ML (Apple's ML framework) — which understands ONNX/PyTorch via [`coremltools`](https://github.com/apple/coremltools). The model becomes a `.mlmodel` file the Swift compiler generates a typed wrapper for.

---

## The Five Most Surprising Things

1. **No truthiness.** Every `if` needs an explicit comparison. After a week of compile errors, you'll write better Python too.
2. **No GIL means real concurrency, and the compiler enforces it.** You can't share mutable state across `Task`s without an `actor` or proven safety. Swift 6 strict concurrency catches what Python's GIL hides.
3. **Default to `struct`.** Most "classes" you'd write in Python are better as Swift structs. Reach for `class` deliberately, not by reflex.
4. **Optionals are types, not values.** You can't pass `nil` where `T` is expected. The annoyance vanishes within a week; you'll never miss `AttributeError: NoneType has no attribute 'foo'` again.
5. **Reference cycles leak.** Swift has no cycle collector. Closures that capture `self` and live longer than the function call need `[weak self]`. Pay attention to `Task`s stored on `self`.

---

## Mapping Cheat Sheet

| Python | Swift |
|---|---|
| `x = 1` | `let x = 1` (or `var x = 1` if mutating) |
| `x: int = 1` | `let x: Int = 1` |
| `None` | `nil` (only valid for `T?`) |
| `Optional[T]` | `T?` |
| `x or default` | `x ?? default` (only for optionals — Swift has no truthy fallback) |
| `if x is None:` | `if x == nil:` (or `guard let x else { ... }`) |
| `def foo(a, b):` | `func foo(_ a: Int, _ b: Int) { ... }` |
| `def foo(a: int = 1):` | `func foo(a: Int = 1) { ... }` |
| `class Foo:` | `struct Foo { ... }` (default) or `class Foo { ... }` |
| `@dataclass class User:` | `struct User: Equatable, Hashable, Codable { ... }` |
| Multiple inheritance | Single class inheritance + multiple protocol conformance |
| Duck typing | Generics with protocol constraints (`<T: Foo>`) |
| `[x*2 for x in xs]` | `xs.map { $0 * 2 }` |
| `{k:v for k,v in ...}` | `Dictionary(uniqueKeysWithValues: ...)` |
| `lambda x: x*2` | `{ $0 * 2 }` |
| `try: ... except: ...` | `do { try ... } catch { ... }` |
| `raise ValueError("...")` | `throw MyError.invalid("...")` |
| `with open(...) as f:` | `defer { try? f.close() }` (or use a class with `deinit`) |
| `asyncio.run(main())` | Top-level `await` in `@main` Swift entry, or `Task { await main() }` |
| `async def`, `await` | `async func`, `await` (same keywords) |
| `asyncio.gather` | `async let` or `withTaskGroup` |
| `threading.Lock` | `actor` |
| `ThreadLocal` | `@TaskLocal` |
| `print(f"...")` | `print("...")` (Swift string interpolation: `"\(value)"`) |
| `len(s)` | `s.count` |
| `range(10)` | `0..<10` |
| `enumerate(xs)` | `xs.enumerated()` |
| `sorted(xs)` | `xs.sorted()` |
| `isinstance(x, Foo)` | `x is Foo` |
| `cast(x, Foo)` (typing) | `x as! Foo` (force) or `x as? Foo` (safe) |
| `json.loads(data)` | `try JSONDecoder().decode(T.self, from: data)` |
| `json.dumps(obj)` | `try JSONEncoder().encode(obj)` |
| `pip install foo` | Add `foo` to `Package.swift` `dependencies` and import |

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — `actor`/`@MainActor`/`Sendable`.
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — refcount-without-cycle-collector model.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — duck-typing replaced.

**Next:** Pick from any chapter in [02-swift-fundamentals/](.).

*Last updated: 2026-05-04*
