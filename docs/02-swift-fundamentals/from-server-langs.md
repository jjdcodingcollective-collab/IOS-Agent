# From Server Languages: Go / Ruby / PHP → Swift

> Audience: server-side developers crossing into iOS — either porting shared
> business logic into a mobile target, or picking up Swift after years on a
> request/response runtime. The biggest mental shift isn't syntactic; it's that
> **you no longer return a response and forget**. A view stays on screen,
> retains state, gets re-rendered, and outlives any one function call.

This chapter is intentionally compressed. Each language gets the parts of the
locked Phase E template that actually differ for that audience; shared
material (concurrency, ARC, generics) lives in the dedicated chapters and is
cross-linked at the end.

## The shared mental shift (read this once, applies to all three)

Server code is **request-scoped**: a handler runs, returns, and its memory is
freed. iOS code is **view-scoped**: a `View` or `ViewController` is constructed,
held by a parent, observes state, and is destroyed when navigation pops.

Three consequences for any server-language refugee:

1. **`self` lives longer than you expect.** Closures captured by a long-lived
   object can leak it. Read [`arc-and-lifetimes.md`](./arc-and-lifetimes.md)
   before writing your first `Task { ... }` block — the GC habits you have
   from Go/Ruby/PHP will silently retain things here.
2. **Mutation is observable.** `@State` / `@Observable` re-runs `body` when the
   value changes. There is no equivalent of "render once, return HTML, done."
3. **Threading is structured.** Swift Concurrency's `Task` tree, `actor`
   isolation, and `@MainActor` are not goroutines, threads, or fibers. Read
   [`concurrency-and-sendable.md`](./concurrency-and-sendable.md).

---

## Go → Swift

### 60-second mental model

| Go | Swift |
|---|---|
| `struct` (value), `*struct` (reference) | `struct` (value), `class` (reference) |
| Interface (structural) | Protocol (nominal) |
| Goroutine + channel | `Task` + `AsyncStream` / actor |
| `error` return + `if err != nil` | `throws` + `try` / `do/catch` |
| `nil` (zero value for pointers) | `Optional<T>` (`.none` / `.some`) |
| Slices, maps | `Array`, `Dictionary` |
| Generics (Go 1.18+) | Generics with associated types and protocol constraints |
| `defer` | `defer` (similar — runs at scope exit) |

### Type system

Go's interfaces are **structural** — any type with the right methods satisfies
the interface, no declaration required. Swift's protocols are **nominal** —
conformance is explicit:

```swift
protocol Greeter {
    func greet() -> String
}

struct EnglishGreeter: Greeter {  // explicit conformance
    func greet() -> String { "hello" }
}
```

This is the single biggest "where did my flexibility go" moment for Go
developers. Swift's tradeoff: the compiler can dispatch protocol methods
directly and enforce conformance once, instead of checking at every call.

**Strong caveat — Protocols with Associated Types (PATs):** A protocol with
an `associatedtype` cannot be used as a generic value type at runtime the
way Go's interfaces can. See
[`generics-and-protocols-deep.md`](./generics-and-protocols-deep.md) for
when to reach for `some`, `any`, or generics.

### Idiom translation

**Error handling.** Go returns `(T, error)`; Swift uses `throws`:

```go
// Go
func parse(s string) (int, error) {
    n, err := strconv.Atoi(s)
    if err != nil {
        return 0, fmt.Errorf("parse: %w", err)
    }
    return n, nil
}
```

```swift
// Swift
func parse(_ s: String) throws -> Int {
    guard let n = Int(s) else {
        throw ParseError.notANumber(s)
    }
    return n
}
```

**Goroutines + channels → Tasks + AsyncStream.** Go's
`go func() { ch <- result }()` becomes:

```swift
let stream = AsyncStream<Result> { continuation in
    let task = Task {
        for item in workItems {
            let result = await process(item)
            continuation.yield(result)
        }
        continuation.finish()
    }
    continuation.onTermination = { _ in task.cancel() }
}

for await result in stream {
    print(result)
}
```

Key differences from channels:

- An `AsyncStream` has **one consumer**. For fan-out, you need an actor or
  multiple streams.
- Cancellation is structured — cancelling a parent `Task` cancels children.
  Goroutines have no such tree; cancellation is cooperative via `context.Context`.
- There is no `select` with multiple channel cases. The closest pattern is
  `withTaskGroup` returning whichever child finishes first.

**`defer`.** Both languages have it; semantics are nearly identical
(runs at scope exit, last-registered runs first).

### Concurrency model

| Go | Swift |
|---|---|
| Goroutine (M:N scheduled, ~2KB stack) | `Task` (cooperative, on a global pool or actor) |
| Channel (`chan T`) | `AsyncStream<T>` (single consumer) or actor mailbox |
| `sync.Mutex` | `actor` (preferred) or `os_unfair_lock` |
| `context.Context` for cancellation | Implicit `Task` cancellation tree |
| `select { case <-ch1: ... }` | `withTaskGroup` + `for await ... in group` |

The biggest shift: Swift's actors enforce isolation at the **type system**
level. A `Mutex` in Go protects data by convention; an `actor` in Swift makes
unsynchronized access a compile error.

### Memory model

Go: tracing GC, stop-the-world pauses (microseconds in modern Go but real),
escape analysis decides stack vs heap.

Swift: ARC — deterministic, refcount-based, no GC pauses but you pay attention
to retain cycles. Closures capturing `self` inside a `Task` are the #1 source
of leaks for newcomers. See [`arc-and-lifetimes.md`](./arc-and-lifetimes.md).

### Where it gets weird for Go devs

1. **No implicit interface satisfaction.** You must declare conformance.
2. **No `nil` for value types.** `0` is not `nil`-ish — use `Optional<Int>`.
3. **Generics are richer but stricter.** Associated types, protocol constraints,
   `where` clauses — and PATs are not interchangeable with concrete types.
4. **No package-private without modules.** Swift's access levels are `private`,
   `fileprivate`, `internal` (module-scoped), `public`, `open`. There is no
   per-directory visibility — split with `internal` + module boundaries.
5. **`init` is mandatory and order-sensitive.** Go's zero-value initialization
   has no equivalent; every stored property must be initialized before `self`
   is usable.

---

## Ruby → Swift

### 60-second mental model

Ruby is dynamic, message-passing, metaprogrammable. Swift is static,
compile-checked, and treats runtime introspection as an emergency exit. **The
core advice for Ruby developers crossing over: stop reaching for
`method_missing`. Use protocols instead.**

| Ruby | Swift |
|---|---|
| Duck typing (`respond_to?`) | Protocol conformance (compile-checked) |
| `attr_accessor` | Stored property (default behaviour) |
| Mixins (`include Module`) | Protocol + protocol extension (default impl) |
| Blocks / procs / lambdas | Closures (single unified concept) |
| `nil` | `Optional<T>` |
| `method_missing`, `define_method` | **No direct equivalent** — see below |
| ActiveRecord | SwiftData / Core Data — see [`persistence.md`](../03-architecture/persistence.md) |

### Idiom translation

**Mixins → Protocol extensions.** Ruby's `include` is replaced by:

```swift
protocol Greetable {
    var name: String { get }
}

extension Greetable {
    func greet() -> String { "hello, \(name)" }
}

struct User: Greetable {
    let name: String
}

User(name: "Ada").greet()  // "hello, Ada"
```

**Blocks → trailing closures.** Ruby's `each do |x| ... end` becomes:

```swift
items.forEach { item in
    print(item)
}
```

Or, idiomatically:

```swift
for item in items { print(item) }
```

**`nil` checking.** Ruby's `value || default` becomes Swift's `value ?? default`.
Ruby's `value&.method` becomes Swift's `value?.method`. The mechanics are
similar; the difference is that the Swift compiler **forces** you to deal with
the `nil` case before using the value.

### Where it gets weird for Ruby devs

1. **No `method_missing`.** Stop. There is no runtime method synthesis. The
   replacement is a `protocol` plus `protocol extension` for default
   implementations, or — for genuinely dynamic dispatch — `@dynamicMemberLookup`
   and `@dynamicCallable`, which are explicitly typed and far less flexible
   than Ruby's open-world dispatch.
2. **No monkey-patching across modules.** You can extend a type with new
   methods, but you cannot override an existing method's implementation
   without subclassing. This breaks the "open every class and rewrite it"
   muscle Ruby builds.
3. **Compile-time strictness everywhere.** `nil`, types, casts — all
   compile-checked. The TDD-driven discovery loop common in Ruby
   (write a test, it fails, you discover what the type "should" do) is
   replaced by the compiler telling you upfront.
4. **No `&:method` symbol-to-proc.** Use a key-path or a closure:
   `users.map(\.name)` instead of `users.map(&:name)`.
5. **Eager/lazy is opt-in.** Ruby's `Enumerable` is mostly eager; Swift
   sequences are eager unless you call `.lazy`. See
   [`combine-and-async-streams.md`](./combine-and-async-streams.md) for the
   async/lazy variants.

### Real-world port

A typical Ruby `Service` class:

```ruby
class UserService
  def initialize(repo)
    @repo = repo
  end

  def find_active(since:)
    @repo.where(active: true).where('updated_at > ?', since)
  end
end
```

Swift equivalent:

```swift
final class UserService {
    private let repo: UserRepository
    init(repo: UserRepository) { self.repo = repo }

    func findActive(since: Date) async throws -> [User] {
        try await repo.fetch(predicate: #Predicate {
            $0.active && $0.updatedAt > since
        })
    }
}
```

The shape is preserved; what changes is that `repo.where(...)` becomes a
typed predicate (`#Predicate` is SwiftData's macro), and the call is
`async throws` because iOS APIs are typically async.

---

## PHP → Swift

PHP-to-iOS is the smallest of the three audiences. Most PHP developers who
move to mobile end up picking up Swift through a different lens (a JS/TS
chapter, or directly from SwiftUI tutorials). This section covers only the
conceptual gaps that bite PHP developers specifically.

### 60-second mental model

| PHP | Swift |
|---|---|
| Type juggling (`'1' == 1` is true) | Strict typing — no implicit coercion |
| `null` | `Optional<T>` |
| Superglobals (`$_POST`, `$_SESSION`) | Dependency injection — there are no globals |
| `array` (mixed list/map) | `Array<T>` and `Dictionary<K,V>` are distinct |
| Class autoload + require | Module system with `import` — no per-file requires |
| `try { } catch (Exception $e) { }` | `do { try ... } catch { }` |
| Composer | Swift Package Manager |

### The two shifts that matter most

**1. No type juggling.** This is the single biggest source of PHP bugs that
disappear in Swift, and it's also the biggest "why does this not compile"
moment. `"1" == 1` is a type error. Concatenation requires explicit string
conversion: `"\(count) items"`.

**2. No superglobals.** PHP's `$_POST` / `$_GET` / `$_SESSION` / `$_ENV` are
all global, request-scoped, and writable. iOS has nothing like this. The
nearest equivalent is `UserDefaults` (key-value storage, persisted across
launches — not request-scoped) or a singleton service injected via
constructor or `@Environment`. The mental model is "everything is passed in
explicitly," even shared services.

### Where it gets weird for PHP devs

1. **Arrays are not associative arrays.** `Array<T>` is ordered and indexed
   by integer; `Dictionary<K,V>` is unordered and keyed. PHP's
   one-data-structure-fits-all habit produces awkward Swift if you keep it.
2. **No `null` in non-optional types.** Every type either explicitly opts
   into nullability (`Int?`) or is guaranteed non-null. This catches
   uninitialized fields at compile time.
3. **No request-scoped state.** A view persists across user interactions;
   you cannot reset everything by reloading the page. Plan your state
   ownership upfront — read [`persistence.md`](../03-architecture/persistence.md).
4. **Strong concurrency model.** PHP is request-per-process by default;
   shared state across requests is rare. iOS apps run a single long-lived
   process with many concurrent tasks — `actor` isolation is the design tool.

---

## Cross-links

- [`arc-and-lifetimes.md`](./arc-and-lifetimes.md) — the GC → ARC transition
  is the most consequential shift for all three audiences
- [`concurrency-and-sendable.md`](./concurrency-and-sendable.md) — `Task`,
  actors, `@MainActor`, `Sendable`
- [`generics-and-protocols-deep.md`](./generics-and-protocols-deep.md) —
  `some` vs `any`, PATs, type erasure (especially for Go interface refugees)
- [`codable-deep.md`](./codable-deep.md) — JSON encoding/decoding, the
  closest thing to "request body parsing" in mobile
- [`../03-architecture/persistence.md`](../03-architecture/persistence.md) —
  the iOS replacements for ActiveRecord / Eloquent / database/sql
- [`combine-and-async-streams.md`](./combine-and-async-streams.md) —
  reactive streams, the closest mental model for channel-based code

---

Last updated: 2026-05-04 (Phase E Tier 4 — BUILD-30).
