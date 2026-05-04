# Swift for Web Developers

> A guide to Swift syntax and concepts, mapped from JavaScript and TypeScript. If you know JS/TS, you already understand most of the concepts — Swift just spells them differently.

---

## Variables and Constants

```javascript
// JavaScript / TypeScript
let count = 0;        // mutable
const name = "Alice"; // immutable
var legacy = true;    // function-scoped (avoid)
```

```swift
// Swift
var count = 0        // mutable (like JS let)
let name = "Alice"   // immutable (like JS const)
// No equivalent to JS var — Swift doesn't have function-scoped variables
```

**Key difference:** Swift's `let` means constant (like JS `const`). Swift's `var` means mutable (like JS `let`). This trips up every web developer on day one.

---

## Type System

Swift is statically typed like TypeScript, but types are enforced at compile time with no `any` escape hatch.

```typescript
// TypeScript
let name: string = "Alice";
let age: number = 30;
let items: string[] = ["a", "b"];
let user: { name: string; age: number } = { name: "Alice", age: 30 };
```

```swift
// Swift
let name: String = "Alice"
let age: Int = 30
let items: [String] = ["a", "b"]
// Structs replace inline object types (see below)

// Type inference works like TS — you can omit types when obvious
let name = "Alice"    // inferred as String
let age = 30          // inferred as Int
```

### Optionals (Swift's null safety)

Swift has no `null` or `undefined`. Instead, it has **optionals** — a type that explicitly says "this value might not exist."

```typescript
// TypeScript
let email: string | null = null;
if (email !== null) {
  console.log(email.toUpperCase());
}
// Or with optional chaining:
console.log(email?.toUpperCase() ?? "no email");
```

```swift
// Swift
var email: String? = nil  // The ? makes it optional
if let email = email {    // "Optional binding" — unwrap safely
    print(email.uppercased())
}
// Or with optional chaining (identical to TS):
print(email?.uppercased() ?? "no email")

// Force unwrap (like TS non-null assertion !)
// DANGER: crashes if nil — avoid in production code
print(email!.uppercased())
```

**Mental model:** `String?` in Swift = `string | null` in TypeScript. The compiler forces you to handle the `nil` case.

#### Implicitly Unwrapped Optionals (`String!`)

You will see `String!` (with `!` instead of `?`) in Apple framework signatures. This is an **Implicitly Unwrapped Optional** — declared as optional but auto-unwrapped at every use site. If the value is `nil` when read, your app crashes.

```swift
// Apple framework property — declared T! because it's set after init.
var label: UILabel!  // crashes if you read it before viewDidLoad fires

// In your own code, prefer T? — IUOs are a legacy convenience for Objective-C
// interop and pre-init UIKit outlets. SwiftUI rarely needs them.
```

**Rule for your own code:** use `T?` and unwrap explicitly. Reach for `T!` only when bridging legacy ObjC headers or `@IBOutlet` properties that the framework guarantees are non-nil after a known lifecycle event.

---

## Functions

```javascript
// JavaScript
function greet(name, greeting = "Hello") {
  return `${greeting}, ${name}!`;
}
greet("Alice");
greet("Bob", "Hey");

// Arrow function
const double = (x) => x * 2;
```

```swift
// Swift
func greet(name: String, greeting: String = "Hello") -> String {
    return "\(greeting), \(name)!"
}
greet(name: "Alice")
greet(name: "Bob", greeting: "Hey")

// Closure (like arrow function)
let double = { (x: Int) -> Int in x * 2 }
// Or with shorthand:
let double: (Int) -> Int = { $0 * 2 }
```

**Key difference:** Swift uses **argument labels** by default. When you call `greet(name: "Alice")`, the `name:` part is required. This makes call sites self-documenting.

```swift
// You can suppress labels with _
func greet(_ name: String) -> String { ... }
greet("Alice")  // No label needed
```

---

## Collections

```typescript
// TypeScript
const arr: string[] = ["a", "b", "c"];
const dict: Record<string, number> = { x: 1, y: 2 };
const unique: Set<string> = new Set(["a", "b"]);
```

```swift
// Swift
let arr: [String] = ["a", "b", "c"]
let dict: [String: Int] = ["x": 1, "y": 2]
let unique: Set<String> = ["a", "b"]

// Mutable versions — just use var
var mutableArr = ["a", "b"]
mutableArr.append("c")

// Functional operations (identical concepts to JS)
let doubled = [1, 2, 3].map { $0 * 2 }           // [2, 4, 6]
let evens = [1, 2, 3, 4].filter { $0 % 2 == 0 }  // [2, 4]
let sum = [1, 2, 3].reduce(0, +)                   // 6
```

---

## Structs and Classes

In web development, you use objects and classes. Swift has both **structs** and **classes**, and the choice matters.

```typescript
// TypeScript — class
class User {
  constructor(public name: string, public age: number) {}
  greet() { return `Hi, I'm ${this.name}`; }
}
```

```swift
// Swift — struct (preferred for data/models)
struct User {
    let name: String
    let age: Int
    
    func greet() -> String {
        return "Hi, I'm \(name)"
    }
}

let user = User(name: "Alice", age: 30)
print(user.greet())
```

### When to use struct vs. class

| Use a **struct** when... | Use a **class** when... |
|---|---|
| Representing data (models, DTOs) | You need reference semantics (shared mutable state) |
| Value should be copied, not shared | You need inheritance |
| Most of the time (Swift default) | Working with UIKit APIs that require classes |

**Rule of thumb:** Default to structs. Use classes when you specifically need reference semantics. SwiftUI `View` types are always structs.

```swift
// Struct = value type (copied on assignment)
var a = User(name: "Alice", age: 30)
var b = a
b.name = "Bob"
// a.name is still "Alice" — b is a separate copy

// Class = reference type (shared on assignment)
class Account { var balance: Int = 0 }
let a = Account()
let b = a
b.balance = 100
// a.balance is also 100 — same object
```

---

## Enums (Much More Powerful Than JS/TS)

Swift enums can carry associated data — think of them as TypeScript discriminated unions.

```typescript
// TypeScript — discriminated union
type Result = 
  | { type: "success"; data: string }
  | { type: "error"; message: string };
```

```swift
// Swift — enum with associated values
enum Result {
    case success(data: String)
    case error(message: String)
}

let result = Result.success(data: "Hello")

switch result {
case .success(let data):
    print("Got: \(data)")
case .error(let message):
    print("Error: \(message)")
}
```

---

## Error Handling

```javascript
// JavaScript
try {
  const data = await fetchUser();
} catch (error) {
  console.error(error.message);
}
```

```swift
// Swift
// Errors are typed — define what can go wrong
enum NetworkError: Error {
    case notFound
    case serverError(code: Int)
    case noConnection
}

// Functions declare that they can throw
func fetchUser() throws -> User {
    throw NetworkError.notFound
}

// Callers must handle errors
do {
    let user = try fetchUser()
    print(user.name)
} catch NetworkError.notFound {
    print("User not found")
} catch {
    print("Something went wrong: \(error)")
}
```

---

## Async/Await

Swift's async/await works almost identically to JavaScript's.

```javascript
// JavaScript
async function loadUser() {
  const response = await fetch("/api/user");
  const data = await response.json();
  return data;
}
```

```swift
// Swift
func loadUser() async throws -> User {
    let url = URL(string: "https://api.myapp.com/user")!
    let (data, _) = try await URLSession.shared.data(from: url)
    let user = try JSONDecoder().decode(User.self, from: data)
    return user
}

// Call it from an async context
Task {
    do {
        let user = try await loadUser()
        print(user.name)
    } catch {
        print("Failed: \(error)")
    }
}
```

**Key difference:** Swift's `async` functions can also `throw`, and you must handle both. The `Task { }` block is like wrapping a call in an immediately-invoked async function.

---

## Protocols (Like TypeScript Interfaces)

```typescript
// TypeScript
interface Displayable {
  displayName: string;
  describe(): string;
}

class User implements Displayable {
  displayName: string;
  constructor(name: string) { this.displayName = name; }
  describe() { return `User: ${this.displayName}`; }
}
```

```swift
// Swift
protocol Displayable {
    var displayName: String { get }
    func describe() -> String
}

struct User: Displayable {
    let displayName: String
    func describe() -> String {
        return "User: \(displayName)"
    }
}
```

Protocols can also provide default implementations (like TypeScript mixin patterns):

```swift
extension Displayable {
    func describe() -> String {
        return displayName  // Default implementation
    }
}
```

---

## Property Wrappers (No JS Equivalent — iOS-Specific)

SwiftUI uses property wrappers extensively for state management. No direct JS equivalent exists, but think of them as decorators that add reactive behavior.

```swift
// @State — local component state (like useState)
@State private var count = 0

// @Binding — two-way binding to parent state (like React props + callback)
@Binding var isOn: Bool

// @ObservedObject — subscribe to an observable passed in by a parent
// (like a Zustand/MobX store handed down as a prop — NOT useContext).
// Use this when a parent View owns the object and passes it down.
@ObservedObject var viewModel: MyViewModel

// @StateObject — own the lifecycle of an observable in this View
// (initialise once, survives redraws). Pair with @ObservedObject in children.
@StateObject private var viewModel = MyViewModel()

// @EnvironmentObject — receive an observable injected from anywhere up the
// View tree (this is the real React Context analogue).
@EnvironmentObject var session: SessionStore

// @Environment — read framework- or app-provided environment values
// (color scheme, locale, scenePhase, etc.). Also Context-like, but for
// values you don't own.
@Environment(\.colorScheme) var colorScheme
```

> **Common mismap:** Earlier drafts of this guide called `@ObservedObject` "like `useContext`." That's wrong. `useContext` reads a value provided somewhere up the tree without props — that's `@EnvironmentObject` (or `@Environment` for framework values). `@ObservedObject` is for objects passed in explicitly, much closer to a store-as-prop than to context.

See [SwiftUI Guide](../04-ui-development/swiftui-guide.md) for detailed usage.

---

## Quick Reference Cheat Sheet

| JavaScript / TypeScript | Swift |
|---|---|
| `let` (mutable) | `var` |
| `const` (immutable) | `let` |
| `null` / `undefined` | `nil` (with optionals `?`) |
| `string \| null` | `String?` |
| `obj?.prop ?? default` | `obj?.prop ?? default` (identical) |
| `===` | `==` (Swift `==` is always strict) |
| `typeof x === "string"` | `x is String` |
| `x as string` | `x as! String` (force) or `x as? String` (safe) |
| Template literals `` `${x}` `` | String interpolation `"\(x)"` |
| `console.log()` | `print()` |
| `interface` | `protocol` *(starting point only — see footnote)* |
| `class` | `class` (reference) or `struct` (value) |
| `enum` | `enum` (much more powerful) |
| `async/await` | `async/await` (nearly identical) |
| `try/catch` | `do/try/catch` |
| `() => {}` | `{ }` (closures) |
| `[].map(x => ...)` | `[].map { ... }` |
| `export / import` | `import ModuleName` (module-level, not file-level) |

> **Footnote — `interface` vs `protocol`:** Swift protocols look like TypeScript interfaces at first glance, but they diverge sharply. Protocols can have **associated types** (PATs), which behave more like generic constraints than interface members. They can also be used as **existentials** (`any P`) or **opaque types** (`some P`), and the choice changes the runtime semantics. See the dedicated [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) chapter before treating "interface = protocol" as 1:1.

---

**Next:** [Architecture Patterns](../03-architecture/patterns.md) — How web architecture concepts map to iOS.

*Last updated: 2026-05-04*
