# Generics, Opaque Types & Existentials

> Swift's type system gets deep fast. The cheat sheet says "interface → protocol," but Swift protocols can do things TypeScript interfaces, Java interfaces, and Kotlin interfaces all leave to other mechanisms. This chapter builds the mental model for generics, protocols-with-associated-types, opaque return types (`some`), and existentials (`any`) — and explains when to reach for each.

---

## Generics: The Easy Part

Generics in Swift work the way you'd expect from any modern typed language. Type parameters go in angle brackets; constraints go after a colon.

```swift
// A generic function
func first<T>(in array: [T]) -> T? {
    array.first
}

// With a constraint
func first<T: Comparable>(sorted array: [T]) -> T? {
    array.sorted().first
}

// A generic struct
struct Pair<First, Second> {
    let first: First
    let second: Second
}
```

### `where` clauses — extra constraints

When a constraint is more elaborate than `T: Foo`, use `where`:

```swift
func sumValues<T: Sequence>(_ seq: T) -> Int where T.Element == Int {
    seq.reduce(0, +)
}
```

This is identical in spirit to TypeScript's conditional types or Kotlin's `where` clauses. The Swift sugar is roughly:

| Kotlin | Swift |
|---|---|
| `fun <T : Comparable<T>> ...` | `func ...<T: Comparable>` |
| `fun <T> ... where T : A, T : B` | `func <T: A & B>` or `where T: A, T: B` |

---

## Protocols: Where It Gets Interesting

A protocol declares requirements. Conforming types satisfy them. So far, identical to interfaces.

```swift
protocol Identifiable {
    var id: String { get }
}

struct Article: Identifiable {
    let id: String
    let title: String
}
```

### Default implementations via extensions

Swift protocols can ship default implementations on the protocol itself (via an extension). This is the closest thing to a Kotlin abstract class member or a Java interface default method.

```swift
protocol Greetable {
    var name: String { get }
    func greet() -> String
}

extension Greetable {
    func greet() -> String {        // default implementation
        "Hello, \(name)"
    }
}

struct Person: Greetable {
    let name: String                // satisfies the requirement; greet() is free
}
```

### Protocols can require initialisers, types, operators, and statics

```swift
protocol Newable {
    init()                          // required initialiser
    static var defaultName: String { get }
    static func + (lhs: Self, rhs: Self) -> Self
}
```

The `Self` keyword means "the conforming type." This is more powerful than Java/Kotlin/TS interfaces, which can't refer to the conforming type that way.

---

## Protocols with Associated Types (PATs)

This is the first big departure from TypeScript/Java/Kotlin interfaces. A protocol can have **associated types** — type variables that the conforming type fills in.

```swift
protocol Container {
    associatedtype Item
    var count: Int { get }
    mutating func append(_ item: Item)
    subscript(index: Int) -> Item { get }
}

struct IntBox: Container {
    var values: [Int] = []
    var count: Int { values.count }
    mutating func append(_ item: Int) { values.append(item) }
    subscript(index: Int) -> Int { values[index] }
    // The compiler infers Item == Int.
}
```

The standard library is built on PATs: `Sequence` has `associatedtype Element`, `Collection` adds `associatedtype Index`, etc.

### Why this matters for you

A PAT cannot be used as a plain type (you can't write `var x: Container`). It's a constraint, not a type. You have to use it as a generic constraint:

```swift
// ❌ Compile error: protocol can only be used as a generic constraint
// because it has Self or associated type requirements
func describe(c: Container) { /* ... */ }

// ✅ Use it as a generic constraint
func describe<C: Container>(_ c: C) { print(c.count) }
```

This is the single most surprising rule for developers coming from TypeScript or Java. In TypeScript, `interface Container<T>` is just a type. In Swift, a PAT is a constraint, and you reach for `some` or `any` (next two sections) when you need to use it as a type.

---

## Opaque Types: `some Protocol`

`some P` means "exactly one specific type that conforms to P, but I'm not telling you which." The compiler knows; the caller doesn't.

```swift
func makeCounter() -> some Counter {     // returns a specific Counter type
    return IntCounter()                   // ...that the compiler picks
}
```

Two things are true at once:
1. The caller can't see which concrete type it is.
2. There's still **only one** type at runtime — the compiler erases the name, not the identity.

This is what `some View` in SwiftUI means:

```swift
struct ContentView: View {
    var body: some View {                 // one specific composed View type
        VStack {
            Text("Hello")
            Button("Tap", action: {})
        }
    }
}
```

The actual return type might be `VStack<TupleView<(Text, Button<Text>)>>` — that's what the compiler infers. You write `some View` and never have to spell that monstrosity out.

### When to use `some`

- Returning a value with a complex inferred type (SwiftUI bodies, Combine pipelines).
- Hiding implementation details — callers should treat the result polymorphically but you want compile-time specialisation.
- You want **performance**: `some` lets the compiler devirtualize and inline. There's no boxing or runtime dispatch.

### Limits of `some`

- Two functions both returning `some View` return **different** types. You can't put them in a homogeneous array.
- You can't conditionally return different concrete types from the same `some`-returning function (`if cond { Foo() } else { Bar() }` won't compile if `Foo` and `Bar` differ).

---

## Existentials: `any Protocol`

`any P` is the "boxed" version. Each value can be any type that conforms to P, and you don't know which. The runtime carries a witness table to dispatch calls.

```swift
let drawables: [any Shape] = [Circle(), Square(), Triangle()]
for d in drawables { d.draw() }            // dispatched dynamically
```

This is the closest analogue to TypeScript's `Shape[]`, Java's `List<Shape>`, or Kotlin's `List<Shape>`.

### When to use `any`

- Heterogeneous collections (different concrete types in the same array).
- API signatures where you genuinely don't care which concrete type — performance is not the concern, flexibility is.
- Storing protocol-typed properties on a class or struct when concrete types vary at runtime.

### Cost of `any`

- **Indirect dispatch** at every method call.
- **Boxing**: each value lives behind a pointer, with a witness table for protocol methods.
- The compiler can't inline calls or reason about the concrete type.

For a hot loop, prefer `some` (or generics) over `any`.

### `any` and PATs

A PAT can be wrapped in `any` (since Swift 5.7+):

```swift
protocol Container {
    associatedtype Item
    var count: Int { get }
}

let containers: [any Container] = [...] // works — but Item is opaque per element
```

You can store such values, but you can't easily get at the `Item` type at compile time. Reach for type erasure (next section) if you need to.

---

## `some` vs `any` — A Decision Table

| Need | Reach for |
|---|---|
| Single specific type, hidden from caller, max performance | `some P` |
| SwiftUI `body` and Combine return types | `some P` (or compiler infers) |
| Heterogeneous collection of conforming types | `[any P]` |
| Callee may return different concrete types depending on input | `any P` |
| Stored property with a varying conforming type | `any P` |
| Generic algorithm with one type parameter | `func f<T: P>(_ x: T)` |
| Constraint on associated type | `where T.Element == Int`, etc. |

A useful rule of thumb: **`some` for return positions, `any` for property/parameter positions when you genuinely need flexibility, generics for everything else.**

---

## Type Erasure: `AnyView`, `AnyPublisher`, `AnyHashable`

Sometimes you need to wrap a `some P` (or a generic) in a uniform type so you can store it in a property, return it from a function with one signature, or push it across an API boundary.

The standard library and Apple frameworks ship "Any" wrappers:

| Wrapper | Wraps | When to use |
|---|---|---|
| `AnyView` | `some View` | SwiftUI views that branch on runtime conditions |
| `AnyPublisher<Output, Failure>` | A Combine publisher chain | API surface for a publisher |
| `AnyHashable` | Any `Hashable` value | Heterogeneous keys |
| `AnySequence<Element>` | Any `Sequence` of `Element` | Hide a sequence's concrete type |

`AnyView` example:

```swift
@ViewBuilder
var body: some View {
    if loading { AnyView(ProgressView()) }
    else { AnyView(ContentList(items)) }
}
// Better in SwiftUI: use a regular if/else inside @ViewBuilder — it handles
// branching without AnyView. AnyView is the escape hatch when you really need
// a single uniform type.
```

### Writing your own type-eraser

Before Swift 5.7's `any`, type-erasers were the only way to put a PAT in a uniform shape. They're still useful:

```swift
struct AnyContainer<Item>: Container {
    private let _count: () -> Int
    private let _append: (Item) -> Void
    private let _get: (Int) -> Item

    init<C: Container>(_ base: C) where C.Item == Item {
        var copy = base                       // captured to allow mutation
        _count = { copy.count }
        _append = { copy.append($0) }
        _get = { copy[$0] }
    }
    var count: Int { _count() }
    mutating func append(_ item: Item) { _append(item) }
    subscript(index: Int) -> Item { _get(index) }
}
```

In modern Swift, `any Container` often replaces this — but writing one yourself is sometimes still the cleanest way to pin down the associated type.

---

## Conditional Conformance

A generic type can conform to a protocol **only when its type parameter does**. This is one of the cleanest features in Swift:

```swift
extension Array: Equatable where Element: Equatable {
    // Array is Equatable only if Element is Equatable
}

extension Optional: Hashable where Wrapped: Hashable { /* ... */ }
```

You'll write conditional conformance constantly when building generic types — it's how you avoid combinatorial extension explosions.

---

## Real Reading Examples

### `some View` in SwiftUI

```swift
struct HomeView: View {
    var body: some View {
        VStack { Text("Hi"); Button("Go") {} }
    }
}
```

`some View` = "exactly one View type, inferred by the compiler from this body, but the caller doesn't get to know which." That hidden concrete type is what enables SwiftUI's diffing.

### `Sequence` in the standard library

```swift
public protocol Sequence {
    associatedtype Element
    associatedtype Iterator: IteratorProtocol where Iterator.Element == Element
    __consuming func makeIterator() -> Iterator
}
```

This is a full PAT-based protocol — `Element` is the associated type, and `Iterator` is also associated, with a `where` constraint linking them. You can't use `Sequence` as a plain type without `any Sequence<...>` or a generic constraint.

### `AnyPublisher` in Combine

```swift
extension Publisher {
    func eraseToAnyPublisher() -> AnyPublisher<Output, Failure> { /* ... */ }
}
```

Combine pipelines accumulate generic types fast (`Map<Filter<Throttle<...>>>`). `eraseToAnyPublisher()` collapses that monster into a uniform `AnyPublisher<Output, Failure>` for API stability.

---

## Mapping From Other Languages

| Concept | Swift equivalent |
|---|---|
| **TS** `interface Foo<T>` (used as a type) | `protocol Foo` (with `associatedtype`) — but it's a *constraint*, not a type. Use `any Foo` or `some Foo` to use as a type. |
| **TS** `type Foo<T> = ...` | Swift `typealias Foo<T> = ...` |
| **TS** generic constraints `<T extends Bar>` | `<T: Bar>` |
| **TS** conditional types `T extends X ? A : B` | No direct equivalent — usually replaced by overloads or `where` clauses. |
| **Kotlin** `interface Container<T>` | `protocol Container` with `associatedtype Item`. Note: Swift's PAT is *not* a generic protocol. (There is no `protocol Container<Item>` per se — though `Container` can be parameterised on use as `any Container<Int>` since Swift 5.7.) |
| **Kotlin** sealed class with type parameter | Generic enum with associated values. |
| **Java** `interface Container<T>` | `protocol Container` + PAT. |
| **Java** `List<? extends Number>` (wildcard) | `some Numeric`-typed collection elements (closest spirit). |
| **C#** `where T : IFoo, new()` | `<T: Foo>` plus an `init()` requirement on the protocol. |
| **C++** templates / concepts | Swift generics with `where` clauses. Swift forces explicit constraints; C++ historically didn't. |
| **Rust** trait + impl + bound | Almost identical: `protocol = trait`, `extension = impl`, `<T: Trait>` is the same. Rust's `dyn Trait` ≈ Swift's `any Protocol`; Rust's `impl Trait` ≈ Swift's `some Protocol`. |

The Rust ↔ Swift mapping is uncannily close. If you've worked with Rust traits, Swift's `some`/`any` distinction will feel familiar — same concept, different keyword.

---

## A Reading Checklist for Confused Signatures

When you see a Swift signature you can't parse, ask in this order:

1. **Are there `<T, U>` brackets?** — generics.
2. **Is there `: P` after a type parameter?** — a constraint.
3. **Is there a `where` clause?** — extra constraints, often on associated types.
4. **Is the return type `some P`?** — opaque return; compiler-known specific type.
5. **Is a parameter or property typed `any P`?** — existential; runtime polymorphism.
6. **Is `Self` used?** — refers to the conforming type, not the protocol.
7. **Is `associatedtype` declared?** — protocol with PAT, only usable as a constraint or behind `any`/`some`.

Run that checklist on `func first<S: Sequence>(_ s: S) -> S.Element? where S.Element: Comparable` and the signature decomposes cleanly:

- Generic over `S`.
- `S` must conform to `Sequence`.
- Returns the optional element type of `S`.
- Element must be `Comparable`.

---

## What Not to Do

- **Don't reach for `any` first.** It's flexible but slow. Try a generic with `some` or `<T: P>` first; fall back to `any` when you genuinely need heterogeneity.
- **Don't write a custom type-eraser for every PAT.** `any P` (Swift 5.7+) is usually enough.
- **Don't use `AnyView` to dodge the type checker.** Most "branch on condition" cases are handled by `@ViewBuilder` automatically.
- **Don't panic at long inferred types in error messages.** Read the topmost few generic parameters; the rest is usually noise.
- **Don't constrain protocols with `: AnyObject` reflexively.** That makes them class-only — sometimes correct (delegates) but often overconstraining.

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — `Sendable` is itself a PAT-free marker protocol.
- [ARC, Capture & Lifetimes](arc-and-lifetimes.md) — class protocols (`AnyObject`-bound) follow ARC rules.

**Next:** [Architecture Patterns](../03-architecture/patterns.md).

*Last updated: 2026-05-04*
