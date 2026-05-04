# The Swift Toolkit: KeyPaths, Property Wrappers, Result Builders, IUOs

> Four small but high-leverage Swift idioms that JS/TS developers don't have direct equivalents for. Each is a building block of frameworks (SwiftUI, Combine, SwiftData) you'll meet daily, and authoring them yourself is what unlocks "I can write framework-quality APIs" in Swift.

---

## 1. KeyPaths

A KeyPath is a typed reference to a property — like a "lens" in functional programming, or like JS bracket-access (`obj[key]`) but with the property name *known to the compiler at the call site*.

### The 30-second mental model

| JS/TS | Swift |
|---|---|
| `users.map(u => u.name)` | `users.map(\.name)` |
| `array.sort((a, b) => a.age - b.age)` | `array.sorted(using: KeyPathComparator(\.age))` |
| `_.get(obj, "deeply.nested.path")` (Lodash) | `obj[keyPath: \.deeply.nested.path]` |
| `(a, b) => a.id === b.id` for grouping | `Dictionary(grouping: items, by: \.category)` |

### Reading

The syntax `\TypeName.propertyName` produces a `KeyPath<TypeName, PropertyType>`. Swift can usually infer the root type:

```swift
struct User { let id: String; let name: String; let age: Int }

let users: [User] = [...]

users.map(\.name)                          // [String]
users.sorted(using: KeyPathComparator(\.age))
users.sorted(using: KeyPathComparator(\.age, order: .reverse))

// Multi-criterion:
users.sorted(using: [
    KeyPathComparator(\.age),
    KeyPathComparator(\.name)
])
```

### `KeyPath` vs `WritableKeyPath` vs `ReferenceWritableKeyPath`

- `KeyPath<Root, Value>` — read-only.
- `WritableKeyPath<Root, Value>` — `Root` must be a `var` (or you mutate via `&`). For value types.
- `ReferenceWritableKeyPath<Root, Value>` — `Root` is a class (or actor); the path can mutate the property even if the *binding* to `Root` is `let`.

You'll see all three in framework signatures. SwiftUI's `Binding(projectedValue: \.name)` and Combine's `assign(to: \.x, on: y)` both rely on this distinction.

### Subscripts

```swift
let nameKP: KeyPath<User, String> = \.name
let user = users[0]

let n1 = user.name                  // normal
let n2 = user[keyPath: nameKP]      // via key path
```

The `[keyPath:]` subscript is universal — every type gets it for free.

### Why KeyPaths matter

They're how **type-safe reflection** works in Swift. Where TypeScript would say `keyof User`, Swift gives you a runtime value (the KeyPath) that's guaranteed by the compiler to point at a real property of the right type. SwiftData's `#Predicate { $0.name == "x" }` and Core Data's predicate building both compile down to KeyPath operations.

### Common patterns

```swift
// Group by a property
let byCategory = Dictionary(grouping: items, by: \.category)

// Pluck a single field from a sequence
let titles = articles.map(\.title)

// Bind in SwiftUI
TextField("Name", text: $user.name)            // $user.name uses Bindings under the hood

// Equatable convenience
let allSameAuthor = articles.allSatisfy { $0.author == articles[0].author }
// or via key path:
let allSameAuthor2 = articles.map(\.author).allSatisfy { $0 == articles[0].author }
```

---

## 2. Property Wrappers — Authoring Your Own

You've used `@State`, `@Binding`, `@AppStorage`, `@Published`, `@Query`. The mechanism behind them is `@propertyWrapper` — a struct/class with a specific shape that the compiler rewrites usage into.

### The minimum viable wrapper

```swift
@propertyWrapper
struct Trimmed {
    private var value: String = ""
    var wrappedValue: String {
        get { value }
        set { value = newValue.trimmingCharacters(in: .whitespacesAndNewlines) }
    }
    init(wrappedValue: String) { self.wrappedValue = wrappedValue }
}

struct Form {
    @Trimmed var firstName: String = ""
}

var f = Form()
f.firstName = "  Alice  "
print(f.firstName)              // "Alice"
```

The compiler synthesizes a stored property of type `Trimmed`, and rewrites `f.firstName` reads/writes to go through `wrappedValue`.

### The projected value (`$`)

If you add `var projectedValue: T`, callers can access it with the `$` prefix:

```swift
@propertyWrapper
struct Validated<Value> {
    var wrappedValue: Value
    var projectedValue: ValidationStatus = .untouched
}

struct Form {
    @Validated var email: String = ""
}

var f = Form()
print(f.email)            // wrappedValue
print(f.$email)           // projectedValue (ValidationStatus)
```

This is how `@Published`'s `$x` returns a publisher, and how `@State`'s `$x` returns a `Binding`.

### A useful real wrapper: `@Clamped`

```swift
@propertyWrapper
struct Clamped<Value: Comparable> {
    private var value: Value
    private let range: ClosedRange<Value>

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
v.level = -10          // clamped to 0
```

The init signature `init(wrappedValue:_:)` lets the call site pass extra arguments alongside the initial value, exactly as `@AppStorage("key")` does.

### Where wrappers are appropriate

- Persistent storage (`@AppStorage`, `@SceneStorage`).
- State propagation (`@State`, `@Binding`, `@StateObject`).
- Serialization invariants (`@LooseInt` for Codable — see [Codable Customization](codable-deep.md)).
- Validation/clamping/normalization at the property level.
- Logging / change notification (replacing manual `didSet`).

### Where wrappers are *not* appropriate

- Cross-cutting "decorators" that affect method behavior — Swift macros are the right tool for that now (Swift 5.9+).
- Anything that needs to know about the enclosing type's instance — wrappers are stored on the instance but don't "see" `self` of the enclosing type. (The "enclosing-self subscript" trick exists but is fragile and unsupported.)

---

## 3. Result Builders

Result builders are the magic behind SwiftUI's body syntax:

```swift
var body: some View {
    VStack {
        Text("Hello")
        Text("World")
        if isVisible { Text("Maybe") }
        ForEach(items) { Text($0.name) }
    }
}
```

This isn't normal Swift. Inside `VStack { ... }`, multiple expressions are valid (a statement-level builder), and `if`/`ForEach` produce values. That's a result builder rewriting the closure body.

### How they work

A result builder is a struct/enum/class annotated `@resultBuilder` that provides static methods like `buildBlock`, `buildOptional`, `buildEither`, `buildArray`, `buildExpression`. The compiler rewrites a closure annotated with that builder by calling these methods to combine the expressions.

```swift
@resultBuilder
enum StringBuilder {
    static func buildBlock(_ parts: String...) -> String {
        parts.joined(separator: " ")
    }

    static func buildOptional(_ part: String?) -> String { part ?? "" }
    static func buildEither(first: String) -> String { first }
    static func buildEither(second: String) -> String { second }
}

func sentence(@StringBuilder _ build: () -> String) -> String { build() }

let s = sentence {
    "Hello"
    "World"
    if Bool.random() { "(maybe)" } else { "(no)" }
}
print(s)        // "Hello World (maybe)" or "Hello World (no)"
```

### When to author one yourself

Honestly: rarely. Result builders are the right tool for **declarative DSLs** that need control flow (`if`, `for`, optional) inside a builder closure. SwiftUI's `@ViewBuilder`, RegexBuilder's `@RegexComponentBuilder`, Combine doesn't use one (it's plain method chains).

Cases where authoring one is the right call:
- Internal DSL for HTML/XML/email templates.
- A query builder where the resulting type is a composition of clauses.
- A test-fixture or stub-construction DSL.

For everything else, plain functions or arrays are simpler.

### Reading SwiftUI signatures

```swift
func VStack<Content: View>(
    alignment: HorizontalAlignment = .center,
    spacing: CGFloat? = nil,
    @ViewBuilder content: () -> Content
) -> VStack<Content>
```

The `@ViewBuilder` on the closure is what lets multiple-statement bodies and `if`/`ForEach` work inside `VStack { ... }`. If you write your own SwiftUI helper functions that take "a chunk of view content," put `@ViewBuilder` on the closure parameter:

```swift
func Card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
    VStack { content() }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
}
```

---

## 4. Implicitly Unwrapped Optionals (`String!`)

You'll see types like `String!` or `UIView!` in Apple framework headers and — historically — Interface Builder outlets. They are **Optionals that auto-unwrap on use**.

```swift
var label: String! = "Hello"
print(label.count)          // 5 — no `?` or `!` needed at the call site
label = nil                 // legal
print(label.count)          // 💥 fatal error: unexpectedly found nil
```

### Mental model

`String!` is a `String?` that the compiler will silently unwrap (with a runtime trap on nil) every time you use it. It's the language's apology for two specific situations:

1. **Two-phase initialization:** the property is initially `nil` but is guaranteed to be set before any use (classic UIKit `@IBOutlet` from Interface Builder).
2. **Bridged Objective-C APIs** that have no nullability annotations — Swift defaults them to IUO because it can't prove either way.

### Why you should almost never write IUOs in new code

- `String?` + `guard let` is safer.
- Two-phase init with IUOs is a code smell — initialize in `init` instead, or use `lazy var` for late-but-safe properties.
- Modern Apple APIs are nullability-audited; you'll see `String?` or `String`, almost never `String!`.

### Where you legitimately encounter them

```swift
class ProfileViewController: UIViewController {
    @IBOutlet weak var nameLabel: UILabel!     // wired up by Interface Builder before viewDidLoad
}
```

Or in older bridged headers like `Foundation`'s pre-audit C APIs. Treat them as "Optional with a runtime promise" — and if the promise breaks, you get a `unexpectedly found nil while unwrapping an Optional value` crash.

### Decision tree

| Situation | Type to use |
|---|---|
| Property always non-nil, you can initialize in `init` | `let` or non-optional `var` |
| Property is computed but expensive to compute eagerly | `lazy var` |
| Property is genuinely optional in your domain | `T?` |
| Property is nil at first but guaranteed set before use | `T?` (use `guard let`) — only IUO if a framework forces it |
| Bridged Objective-C type with no audit | Accept IUO; convert to `T?` at your boundary if you control it |

---

## How These Four Connect

A working iOS engineer reaches for all four in a single afternoon:

```swift
// KeyPath drives reactive binding:
@StateObject private var vm = SearchViewModel()
TextField("Query", text: $vm.query)         // KeyPath \SearchViewModel.query under the hood

// Property wrapper drives storage:
@AppStorage("preferredTheme") var theme = "light"

// Result builder drives view declaration:
var body: some View {
    VStack {
        TextField("Name", text: $name)
        if showHelp { Text("Help text") }
    }
}

// IUO appears at framework boundary:
@IBOutlet weak var titleLabel: UILabel!
```

Understanding each individually demystifies the SwiftUI/Combine/UIKit code you read, and authoring them yourself is what unlocks framework-quality APIs.

---

## Companion chapters

- [Combine & AsyncStream](combine-and-async-streams.md) — `@Published`'s projected value uses the property-wrapper pattern.
- [Codable Customization](codable-deep.md) — `@LooseInt` and friends as a real-world property-wrapper use case.
- [SwiftUI Guide](../04-ui-development/swiftui-guide.md) — `@ViewBuilder` and `@State` in their natural habitat.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — `KeyPathComparator<Root, Value>` and writing generic over key paths.

**Next:** Pick from any chapter in [02-swift-fundamentals/](.).

*Last updated: 2026-05-04*
