# Strict Concurrency & Sendable

> Swift 6's strict concurrency model is the single biggest porting headache for any developer adopting Swift in 2025+. This chapter explains the model, then shows you how to satisfy the compiler without papering over real bugs.

---

## The One-Sentence Mental Model

Swift's concurrency goal is **data-race freedom by construction**. The compiler refuses to let you share mutable state across concurrent contexts unless you've proven it's safe. Every warning under strict concurrency is the compiler asking, "how do I know this access is safe?"

If you're coming from JavaScript: there's no event-loop guarantee anymore. If you're coming from Java/Kotlin: it's stricter than `synchronized`/coroutines — the compiler enforces what those languages leave to discipline. If you're coming from Python: there's no GIL — multiple threads run in parallel, for real.

---

## The Three Pillars

```
┌─────────────────┐    ┌────────────────┐    ┌──────────────────┐
│   Sendable      │    │   Actor         │    │  @MainActor      │
│   (the data)    │    │   (the boxed    │    │  (the main-thread │
│   "safe to send"│    │    state)       │    │   actor)          │
└─────────────────┘    └────────────────┘    └──────────────────┘
        │                      │                       │
        ▼                      ▼                       ▼
   value types,          mutually-exclusive       UI must touch
   immutable refs,       access to its state      this actor only
   or explicitly         from one task at a       ─────────────────
   marked safe           time                     equivalent in JS:
                                                   "must run on the
                                                   UI thread"
```

---

## `Sendable`: Data That Crosses Boundaries

`Sendable` is a marker protocol meaning **"safe to pass between concurrency domains."** Crossing an `await` or sending a value into a `Task` requires the value to be `Sendable`.

### Auto-conformance

Swift gives you `Sendable` for free when:

- The type is a **struct or enum** with all-`Sendable` stored properties.
- The type is **`final class`** with all-immutable (`let`) `Sendable` stored properties.
- The type is a **function value** that doesn't capture non-`Sendable` state (annotate with `@Sendable`).

```swift
struct Article: Sendable {           // auto — all stored props are Sendable
    let id: String
    let title: String
}

enum LoadState: Sendable {           // auto
    case idle, loading, loaded(Article), failed(Error)
}
// (Error is implicitly Sendable; concrete error types you write should be too.)
```

### Explicit conformance

For final classes that hold immutable state, you state it:

```swift
final class Configuration: Sendable {
    let apiHost: String
    let maxRetries: Int

    init(apiHost: String, maxRetries: Int) {
        self.apiHost = apiHost
        self.maxRetries = maxRetries
    }
}
```

### `@unchecked Sendable` — the escape hatch

If you can prove safety yourself (e.g., a class with internal locking), use `@unchecked Sendable`:

```swift
final class ThreadSafeCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var value = 0
    func increment() { lock.lock(); defer { lock.unlock() }; value += 1 }
    func read() -> Int { lock.lock(); defer { lock.unlock() }; return value }
}
```

`@unchecked` turns off the compiler's verification — so use it only when you've genuinely thought through the synchronization.

---

## Actors: Mutable State, Made Safe

An `actor` is a class-like reference type whose state is accessible only one task at a time. From outside the actor, every access is `await`ed.

```swift
actor SessionCache {
    private var entries: [String: Session] = [:]

    func session(for id: String) -> Session? {
        entries[id]                  // synchronous inside the actor
    }

    func store(_ session: Session, for id: String) {
        entries[id] = session
    }
}

// Outside the actor:
let cache = SessionCache()
let s = await cache.session(for: "abc")     // must await — actor-isolated
await cache.store(newSession, for: "abc")
```

**When to use an actor instead of a class:**
- You have shared mutable state that multiple tasks read/write.
- You'd otherwise be reaching for a lock or a serial dispatch queue.

**When NOT to use an actor:**
- The state is immutable — use a `Sendable` struct or `final class`.
- The "state" is just a one-shot computation — use a plain `async` function.
- The data is UI — use `@MainActor` (below) instead.

---

## `@MainActor`: The UI Thread, Spelled Differently

UIKit and SwiftUI require UI updates to happen on the main thread. `@MainActor` is the actor that owns the main thread.

```swift
@MainActor
final class HomeViewModel: ObservableObject {
    @Published var articles: [Article] = []

    func load() async {
        // We're on the main actor here. Hop off for the network call:
        let fetched = try? await ArticleService.fetchAll()
        // After the await we're back on the main actor — safe to touch @Published.
        articles = fetched ?? []
    }
}
```

Key rules:
- A view model that drives SwiftUI views typically wants `@MainActor`.
- Marking the **whole class** is usually cleaner than marking individual methods.
- Inside a `@MainActor` context, calling a non-isolated `async` function suspends, runs that function off the main actor, and resumes on the main actor when it returns.

### `MainActor.run`

When you're inside a non-isolated context but need to touch UI:

```swift
func processInBackground() async {
    let result = expensiveComputation()
    await MainActor.run {
        self.label.text = result      // hop to main actor
    }
}
```

Avoid this if you can — annotate the surrounding type/method `@MainActor` instead. `MainActor.run` is for one-off hops.

---

## `nonisolated`: Opting Out

Sometimes a method on an actor (or `@MainActor`-isolated type) genuinely doesn't touch isolated state — pure computation, or reading immutable `let`s. Mark it `nonisolated`:

```swift
@MainActor
final class TodoStore {
    @Published var items: [Todo] = []

    nonisolated let storeID: String       // immutable — safe everywhere
    nonisolated init(storeID: String) { self.storeID = storeID }

    nonisolated func describe() -> String {
        "TodoStore(\(storeID))"           // doesn't touch items
    }
}
```

Use `nonisolated` to relax the default so callers don't have to `await` purely for compiler appeasement.

---

## Reading the Common Warnings

Under Swift 6 strict concurrency, these are the warnings you'll see most often:

### "Type 'X' does not conform to the 'Sendable' protocol"

You're passing a value across an actor boundary (or into a `Task`) but the compiler can't prove it's safe.

**Fix path:**
1. Can the type *be* `Sendable`? Make all properties `Sendable`, mark the class `final`, declare conformance.
2. If it can't (it has mutable shared state), wrap it in an `actor` instead.
3. If you've handled synchronization yourself, use `@unchecked Sendable` — and write a comment explaining the invariant.

### "Capture of 'self' with non-sendable type 'X' in a `@Sendable` closure"

You're passing a closure into something that runs concurrently (e.g., `Task.detached`, a `Sendable`-typed callback) and the closure captures `self` from a non-`Sendable` context.

**Fix path:**
1. Can the surrounding type be `Sendable`? See above.
2. Capture only the values you need: `[name = self.name] in ...`.
3. Switch to a `Task { ... }` (non-detached) if you actually want to inherit the current actor.

### "Non-sendable type 'X' returned by call from main actor-isolated context"

You're calling an `async` function that returns a non-`Sendable` value, and the call crosses the `@MainActor` boundary.

**Fix path:** make the returned type `Sendable`, or copy the data you need into a `Sendable` value at the boundary.

### "Main actor-isolated property 'foo' can not be referenced from a non-isolated context"

You're touching UI/`@MainActor` state from a background context.

**Fix path:** await the property, or hop to `MainActor.run`, or mark the surrounding context `@MainActor`.

---

## Structured Concurrency: `Task` and `TaskGroup`

A `Task` is a unit of asynchronous work. Tasks can be cancelled, awaited, and grouped.

```swift
// Run something concurrently, await later:
let task = Task {
    try await ArticleService.fetchAll()
}
let articles = try await task.value

// Cancel:
task.cancel()
```

### Task inheritance

`Task { ... }` inherits the current actor (if you're on `@MainActor`, the task starts on `@MainActor`). `Task.detached { ... }` doesn't inherit — use it sparingly, only when you genuinely want a fresh context.

### TaskGroup — fan out, fan in

```swift
func loadAllArticles(ids: [String]) async throws -> [Article] {
    try await withThrowingTaskGroup(of: Article.self) { group in
        for id in ids {
            group.addTask { try await ArticleService.fetch(id: id) }
        }
        var results: [Article] = []
        for try await article in group {
            results.append(article)
        }
        return results
    }
}
```

**Cancellation propagates:** if one task in the group throws, the group cancels the rest. The compiler enforces structured lifetime — no orphaned tasks.

### `async let`

For a small fixed fan-out, `async let` is the lighter sibling of `TaskGroup`:

```swift
func loadHomeScreen() async throws -> HomeData {
    async let user = UserService.fetchCurrent()
    async let articles = ArticleService.fetchTrending()
    async let notifications = NotificationService.unreadCount()
    return try await HomeData(user: user, articles: articles, notifications: notifications)
}
```

All three calls run concurrently; the `await` at the end joins them.

---

## Mapping From Other Languages

| Concept in your source language | Swift equivalent |
|---|---|
| **JavaScript** event loop / microtasks | No equivalent — work runs on actors, not a single loop. `await` suspends; the resume can happen on a different thread. |
| **JavaScript** `Promise` | `Task` (cancellable) or just `async` function. |
| **Kotlin** `suspend fun` | `async` function. |
| **Kotlin** `CoroutineScope` | `Task` (inherits actor) or `TaskGroup`. |
| **Kotlin** `Mutex` over a class | `actor` — usually you don't need a mutex. |
| **Kotlin** `Dispatchers.Main` | `@MainActor`. |
| **Java** `synchronized` block | `actor`. |
| **Java** `ExecutorService.submit` | `Task { ... }`. |
| **Java** `ThreadLocal` | Task-local values (`@TaskLocal`). |
| **Python** `asyncio` event loop | No analogue. Tasks are scheduled on cooperative pools. |
| **Python** `threading.Lock` | `actor`. |
| **Python** GIL | None — Swift parallelism is real. |
| **C#** `async/await` | Nearly identical syntax; `Task` is similar but Swift `Task` is value-typed and lighter. |
| **C#** `lock` keyword | `actor`. |

---

## A Practical Adoption Checklist

When enabling strict concurrency on an existing Swift codebase:

1. **Turn on the warnings, don't fix them yet.** In Xcode build settings: *Strict Concurrency Checking → Complete*. Compile. Read the diagnostic count.
2. **Make obvious value types `Sendable`.** Most of your `struct` models will conform automatically — declare it explicitly so the next reader doesn't wonder.
3. **Annotate your view models `@MainActor`.** This is the single highest-leverage change for SwiftUI codebases.
4. **Convert shared mutable singletons to actors.** Caches, in-memory stores, anything previously protected by a lock or serial queue.
5. **Stop using `Task.detached` reflexively.** Most `Task { ... }` work should inherit the surrounding actor. `detached` is for genuinely independent work.
6. **Resist `@unchecked Sendable` until you've tried the alternatives.** It's a real tool, but the diagnostics are usually telling you about a real problem.

---

## What Not to Do

- **Don't sprinkle `await MainActor.run { ... }` everywhere.** If you're hopping back to main repeatedly inside one method, the surrounding type/method probably wants to be `@MainActor` itself.
- **Don't make every type `@unchecked Sendable` to silence warnings.** That's how you ship races. Each `@unchecked` is an unverified claim — write a comment explaining why it's actually safe.
- **Don't fight the compiler on `nonisolated`.** If the compiler insists a property is `@MainActor`-isolated, it usually means SwiftUI is observing it and you can't change that.
- **Don't reach for a `DispatchQueue` to "fix" a concurrency warning.** Modern Swift uses actors and `Task` for almost everything you used to use GCD for. GCD still exists, but it doesn't participate in the strict-concurrency proof.

---

**Companion chapters:**
- [ARC, Capture & Lifetimes](arc-and-lifetimes.md) — Closure captures and `Task` retention.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — `Sendable` is itself a protocol with these properties.

**Next:** [Architecture Patterns](../03-architecture/patterns.md) — How concurrency interacts with MVVM in SwiftUI.

*Last updated: 2026-05-04*
