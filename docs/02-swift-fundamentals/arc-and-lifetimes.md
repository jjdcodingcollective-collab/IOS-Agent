# ARC, Captures & Lifetimes

> Swift uses **Automatic Reference Counting** (ARC) for memory management of class instances. ARC is deterministic and fast, but it's not garbage collection — and the differences matter. This chapter covers the model, the failure modes, and the capture-list discipline that prevents leaks.

---

## The Model in One Picture

```
class Account { var balance: Int = 0 }

let a = Account()    // refcount: 1
let b = a            // refcount: 2  (b points to the same instance)
b.balance = 100      // a.balance is also 100 — same object
// at end of scope:
//   b goes out of scope → refcount: 1
//   a goes out of scope → refcount: 0 → deinit runs, memory freed
```

Compare with:

| System | Frees memory when... |
|---|---|
| Java/Kotlin (JVM GC) | The GC runs, eventually, after no references remain. Non-deterministic. |
| Python (CPython) | Refcount drops to zero (mostly deterministic) **plus** a cycle collector. |
| JavaScript | The engine's mark-and-sweep GC runs. Non-deterministic. |
| Go | The GC runs. Non-deterministic. |
| **Swift (ARC)** | **Refcount drops to zero. Deterministic.** No cycle collector — you must avoid cycles yourself. |

The "no cycle collector" part is what bites people. Two objects pointing at each other will leak unless one of those pointers is `weak` or `unowned`.

---

## Value Types Don't Need ARC

Structs, enums, and tuples are **value types** — they're copied, not reference-counted. ARC only applies to:

- `class` instances
- closures (which are reference types under the hood)
- `actor` instances
- a few standard library types like `String`, `Array`, `Dictionary`, `Set`, which use copy-on-write internally (more on this below)

```swift
struct Settings { var darkMode = false }     // value type — no ARC

class AppState { var isLoggedIn = false }    // reference type — ARC applies
```

If your design avoids classes wherever possible, you avoid most ARC issues by construction. SwiftUI's `View` types are all structs precisely so this isn't a concern.

---

## Copy-on-Write: The Half-Truth

`Array`, `Dictionary`, `Set`, `String`, and `Data` are structs with **copy-on-write (COW)** internal storage. Operationally they behave like value types — assignments look like copies — but the actual underlying buffer is reference-counted and only duplicated when you mutate.

```swift
var a = [1, 2, 3]
var b = a                        // no copy yet — both share the buffer
b.append(4)                      // now b's buffer is copied (CoW kicks in)
print(a)                         // [1, 2, 3] — a is unchanged
```

This matters for two reasons:
1. **Performance:** large array assignments are O(1), not O(n).
2. **Profiling:** when you see refcount activity on an `Array` in Instruments, that's normal — it's the COW machinery, not a leak.

---

## Strong Reference Cycles

The classic ARC bug: two objects each hold a strong reference to the other.

```swift
class Author {
    var book: Book?
}
class Book {
    var author: Author?
}

let a = Author()
let b = Book()
a.book = b
b.author = a
// Both refcounts are 2.
// Even when a and b leave scope, refcounts only drop to 1 — neither hits 0.
// Memory leak.
```

### Fix: `weak` for one side

A `weak` reference does **not** increment the refcount, and is automatically set to `nil` when the referent is deallocated. `weak` references are always optionals.

```swift
class Author {
    var book: Book?           // strong — Author owns Book
}
class Book {
    weak var author: Author?  // weak — breaks the cycle
}
```

### `unowned`: same idea, no optional

`unowned` also doesn't bump the refcount, but doesn't become `nil` — accessing an `unowned` reference after deallocation crashes. Use it when the lifetimes are guaranteed to be related (e.g., a child object's pointer back to a parent that lives at least as long).

```swift
class Customer {
    var card: CreditCard?
}
class CreditCard {
    unowned let customer: Customer    // a card always has a customer
    init(customer: Customer) { self.customer = customer }
}
```

**Rule of thumb:** if there's any chance the referent could be `nil`, use `weak`. Use `unowned` only when you're certain about the lifetime relationship — and when the cost of the `nil` check matters (rare).

---

## Closures: The Most Common Source of Cycles

A closure captures the variables it references. If a closure is stored on an instance and the closure captures `self`, you have a cycle:

```swift
class ViewModel {
    var onComplete: (() -> Void)?
    var name = "Alice"

    func start() {
        onComplete = {
            print(self.name)        // ❌ closure → self → onComplete → closure
        }
    }
}
```

`self` retains the closure (via `onComplete`), and the closure retains `self` (via the capture). Cycle.

### Fix: capture lists

```swift
func start() {
    onComplete = { [weak self] in
        guard let self else { return }
        print(self.name)
    }
}
```

`[weak self]` makes the capture a weak reference. Inside the closure, `self` is now `Self?`.

### When you need `[weak self]` and when you don't

You need it when:
- The closure is **stored** on a class instance (`self.someClosure = { ... }`).
- The closure is **escaping** and outlives the current call (e.g., delivered to a callback queue, completion handler, Combine sink, `Task` retained on `self`).

You don't need it when:
- The closure is **non-escaping** — it's called and discarded before the function returns. `Sequence.map`, `filter`, `reduce`, `forEach` all take non-escaping closures.
- Working with **value types**. Structs don't have `self` retain semantics — capturing `self` in a struct closure copies the struct, no cycle possible. (SwiftUI `View` bodies are structs — you do not need `[weak self]` inside a SwiftUI view body.)

```swift
// No [weak self] needed — non-escaping
let doubled = numbers.map { $0 * 2 }

// No [weak self] needed — struct
struct ContentView: View {
    @State private var count = 0
    var body: some View {
        Button("Tap") { count += 1 }    // closure captures self (struct copy) — fine
    }
}

// [weak self] required — escaping, on a class
class ImageLoader {
    var onLoaded: ((UIImage) -> Void)?

    func load() {
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let self, let data, let image = UIImage(data: data) else { return }
            self.onLoaded?(image)
        }.resume()
    }
}
```

### `[weak self]` vs `[unowned self]` in closures

- `[weak self]` — `self` is `Self?` inside the closure. Safest default.
- `[unowned self]` — `self` is `Self`, but crashes if accessed after deallocation. Use only when the closure cannot outlive `self` (e.g., you guarantee cancellation in `deinit`).

---

## `Task` Retention

`Task { ... }` is a reference-typed handle. If you store the task on `self`, and the task body captures `self`, you have a cycle until the task completes.

```swift
final class FeedViewModel {
    var refreshTask: Task<Void, Never>?

    func refresh() {
        refreshTask = Task { [weak self] in
            await self?.fetchAndApply()
        }
    }

    deinit {
        refreshTask?.cancel()      // important — let the task drop self
    }
}
```

Two rules:
1. If a `Task` is stored on `self`, capture `self` weakly.
2. Cancel stored tasks in `deinit` — the task otherwise keeps the closure (and any captures) alive until it finishes.

---

## Combine: `AnyCancellable` Lifetime

Combine subscriptions are managed by `AnyCancellable`. The subscription is alive as long as the cancellable is retained; when it's released, the subscription is torn down.

```swift
final class SearchViewModel: ObservableObject {
    @Published var query = ""
    @Published var results: [Result] = []
    private var cancellables: Set<AnyCancellable> = []

    init() {
        $query
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { [weak self] q in
                self?.search(q)
            }
            .store(in: &cancellables)
    }
}
```

Patterns to know:
- **`.store(in: &cancellables)`** is the canonical way to retain a subscription on the view model. When the view model deinits, the set is released, and all subscriptions are torn down.
- **Always `[weak self]` inside `.sink`** if `self` is a class — the subscription closure is escaping and stored.
- **Don't keep a long-lived publisher chain that captures `self` strongly.** That's a leak waiting to happen, especially if the publisher is upstream of `self`'s view.

---

## Escaping vs Non-Escaping Closures

A closure parameter is **non-escaping** by default — meaning the function promises to call it and discard it before returning. An **`@escaping`** closure may be stored or run later.

```swift
// Non-escaping — no [weak self] needed at the call site
func transform(_ block: (Int) -> Int) -> Int { block(42) }

// Escaping — call site usually wants [weak self] if `self` is a class
func onComplete(_ block: @escaping () -> Void) {
    DispatchQueue.main.asyncAfter(deadline: .now() + 1) { block() }
}
```

The `@escaping` annotation in Apple framework signatures is a tell that you might need a capture list at the call site.

---

## Deinitialization: What Runs When Refcount Hits Zero

```swift
final class FileHandle {
    let fd: Int32
    init(path: String) throws { /* open */ }
    deinit { close(fd) }
}
```

Use `deinit` for **deterministic cleanup**: closing files, cancelling tasks, removing observers. Don't rely on it for things that absolutely must happen at a specific moment — use explicit lifetimes (`defer`, `try/finally` analogues, or the `~Copyable` types in newer Swift) for those.

---

## Diagnosing Leaks in Practice

### 1. Xcode Memory Graph Debugger

In Xcode while the app is running: Debug → View Memory Graph. Filter to your view-model classes — purple `!` triangles flag retain cycles automatically.

### 2. Instruments → Leaks template

Run a representative user flow. Stop. The Leaks instrument shows leaked allocations and their backtraces. Reproducible leaks under Instruments are nearly always real.

### 3. `print` in `deinit`

Cheap and effective. Add `deinit { print("ViewModel deinit") }` and exercise the screen flow. If you don't see the message, you have a retain.

### 4. Watch for these smells

- A view-model class with stored closures that don't use `[weak self]`.
- A `Task` stored on `self` that captures `self` strongly.
- A Combine subscription not stored in a `cancellables` set, or stored but capturing `self` strongly.
- A `delegate` property that is *not* `weak`. (`weak var delegate: SomeDelegate?` is the correct shape.)

---

## Mapping From Other Languages

| Concept in your source language | Swift equivalent / difference |
|---|---|
| **Java/Kotlin** GC handles cycles | Swift does **not** — you must break cycles with `weak`/`unowned`. |
| **Java** `WeakReference<T>` | `weak var x: T?` (built into the language). |
| **Kotlin** `lateinit var` | Closer to Implicitly Unwrapped Optionals (`T!`) — but in Swift this is rare; prefer `T?`. |
| **JavaScript** GC + closures | JS GC handles closure cycles automatically. Swift does not. Translation devs will leak by default until they internalise capture lists. |
| **Python** refcount + cycle collector | Swift has the refcount, **not** the cycle collector. |
| **C++** `shared_ptr`/`weak_ptr` | Direct analogue — strong reference is `shared_ptr`, `weak` is `weak_ptr`, `unowned` is closer to a raw pointer with lifetime guarantees. |
| **Rust** ownership | Swift is much looser — but the discipline of "who owns whom" is exactly what `weak`/`unowned` choices encode. |
| **Objective-C** `__weak`/`__strong` | Same machinery, same tradeoffs — Swift's `weak`/`unowned`/strong are the modern spelling. |

---

## Quick Decision Table

| Situation | Capture |
|---|---|
| Closure inside a struct (e.g., SwiftUI `View` body) | None — structs don't cycle. |
| Non-escaping closure (`map`, `filter`, `forEach`) | None. |
| Escaping closure stored on a class instance | `[weak self]` (then `guard let self` inside). |
| Closure stored on a `Task` retained by `self` | `[weak self]`; cancel the task in `deinit`. |
| Combine `.sink` on a class view model | `[weak self]`; store cancellable in a set on `self`. |
| Delegate property | `weak var delegate: SomeDelegateProtocol?` |
| Parent → child → parent reference | Weak on the back-pointer side. |
| Cache or pool referenced from multiple owners | `class` with explicit ownership rules; consider `actor` if shared mutably. |

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — how `Task` and actors interact with ARC.
- [Common Pitfalls #6](../11-pitfalls/web-dev-gotchas.md#6-ignoring-memory-management) — quick-glance reminder.

**Next:** [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md).

*Last updated: 2026-05-04*
