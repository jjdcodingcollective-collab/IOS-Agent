# Objective-C Interop

> Even pure-Swift apps consume Apple frameworks whose roots are Objective-C. Real iOS jobs touch ObjC code directly: legacy modules, third-party SDKs, runtime-driven APIs (KVO, target-action, NSCoding). This chapter gives you the mental model and the recipes — without making you learn Objective-C.

---

## When Will You Hit This?

You'll need this chapter when:

- You see `@objc` in a stack trace, autocomplete, or someone else's code.
- You add a third-party SDK that ships as an `.xcframework` with ObjC headers.
- You inherit a project with a `*-Bridging-Header.h` file at the root.
- You're using KVO (`observe(\.path)`), target-action (`#selector(...)`), or `NSNotificationCenter`.
- You see a method signature like `class func methodName(_:with:and:) -> Bool`.
- You see `String!` or `UIView!` in framework headers (the `!` is an ObjC bridge artefact — see [IUOs](swift-for-web-devs.md#implicitly-unwrapped-optionals-string)).

You won't need this chapter when:
- You're building a brand-new SwiftUI-only app with only Swift packages — until your first dependency drags ObjC in, which it eventually will.

---

## The One-Sentence Mental Model

The Objective-C runtime is a **dynamic, message-passing system** built on a layer of C. Every method call is `objc_msgSend(receiver, selector, args...)` at runtime. Swift's calling convention is **static and compiled** by default — it doesn't go through the runtime at all. Marking something `@objc` opts that one declaration back into the dynamic runtime so ObjC code (and ObjC-style APIs like KVO and target-action) can find it.

---

## Calling ObjC From Swift

If a Swift package or framework imports an ObjC module, the Swift compiler auto-generates a Swift-shaped interface:

```swift
import Foundation
import UIKit

let label = UILabel()                  // UIKit is ObjC under the hood
label.text = "Hello"                   // setter call → objc_msgSend
label.textColor = .systemBlue          // same
```

You don't have to do anything special. The Swift compiler reads the framework's headers, generates Swift signatures, and the calls are dispatched dynamically.

### Naming-convention translations

ObjC's `withFoo:withBar:` style becomes Swift argument labels:

```objc
// Objective-C
[manager loadResourceWithIdentifier:@"abc" priority:5];
```

```swift
// Swift — labels mirror the ObjC selector parts
manager.loadResource(withIdentifier: "abc", priority: 5)
```

The first argument label is usually dropped if the method name already implies it. Apple's Swift API translation rules are documented but in practice you can rely on autocomplete.

### `NSError ** ` becomes `throws`

ObjC error-pointer-out-parameters become Swift throwing functions:

```objc
// Objective-C
NSError *err = nil;
BOOL ok = [item saveTo:url error:&err];
```

```swift
// Swift
do {
    try item.save(to: url)
} catch {
    print(error)
}
```

### Optional vs Implicitly Unwrapped

ObjC types are nullable-by-default at the runtime level. Modern ObjC headers use `nullable`/`nonnull` annotations to give Swift better signatures:

| ObjC declaration | Swift sees |
|---|---|
| `(nullable NSString *)` | `String?` |
| `(nonnull NSString *)` | `String` |
| `NSString *` (unannotated, legacy) | `String!` (Implicitly Unwrapped) |

When you encounter `String!`, the framework header was written before audit-for-nullability — read the docs to decide whether to treat it as `String?` or `String`.

---

## Calling Swift From ObjC: `@objc`

To make a Swift declaration visible to the ObjC runtime, mark it `@objc`:

```swift
class AnalyticsLogger: NSObject {       // must inherit NSObject
    @objc func logEvent(_ name: String) {
        // ObjC code can now call [self.logger logEvent:@"open"]
    }
}
```

Three rules:

1. **The class must inherit from `NSObject`** (or an NSObject subclass like `UIView`, `UIViewController`).
2. **The signature must be ObjC-representable.** No Swift-only types: no enums-with-payloads, no generics on classes, no `Result<T, E>`, no tuples (other than `Void`).
3. **`@objc` per-declaration, or `@objcMembers` on the class** to expose all eligible members.

```swift
@objcMembers
class LegacyBridge: NSObject {
    var name: String = ""               // exposed to ObjC
    func reload() { /* ... */ }         // exposed to ObjC
    func swiftOnly(_ x: any Hashable) {} // skipped — not ObjC-representable
}
```

### `@objc(name)` — overriding the exposed name

Use this when an ObjC consumer expects a specific selector or class name (e.g., when bridging to a `Storyboard`/`xib` that references a class by string):

```swift
@objc(LegacyBridge)
class NewSwiftBridge: NSObject { /* ... */ }
```

---

## `dynamic`: Forcing Dynamic Dispatch

`@objc` exposes a method to ObjC. `dynamic` goes further — it forces Swift to dispatch every call through the runtime. Required for:

- **KVO observation** (the observed property must be `dynamic`).
- **Method swizzling** (advanced; mostly libraries).
- **Some `@NSManaged` Core Data properties** (the framework does the swizzling).

```swift
class User: NSObject {
    @objc dynamic var name: String = ""    // observable via KVO
}
```

Don't use `dynamic` unless you actually need it — it costs you compile-time devirtualization and inlining.

---

## Selectors and `#selector`

Target-action (`UIControl.addTarget(_:action:for:)`), `NSTimer`, `Selector(":")` strings, and a few others still work via selectors. Swift uses `#selector` to construct them safely:

```swift
class ControllerThing: NSObject {
    let button = UIButton()

    func wireUp() {
        button.addTarget(self, action: #selector(buttonTapped), for: .touchUpInside)
    }

    @objc func buttonTapped() {
        // Must be @objc — UIControl looks it up via the runtime.
    }
}
```

Two rules:

1. The target method must be `@objc`.
2. `#selector` is checked at compile time — typos become compiler errors.

For methods with arguments, name the selector with colons:

```swift
button.addTarget(self, action: #selector(handleTap(_:)), for: .touchUpInside)

@objc func handleTap(_ sender: UIButton) { /* ... */ }
```

---

## Bridging Headers (Mixing Swift and ObjC in One Target)

If a single app/framework target contains **both Swift and ObjC source files**, you need a bridging header so the Swift code can `#include` ObjC headers.

The first time you add a `.m` file to a Swift target (or vice versa), Xcode prompts: "Would you like to configure an Objective-C bridging header?" Say yes. Xcode creates `<TargetName>-Bridging-Header.h`.

```objc
// MyApp-Bridging-Header.h
// Anything imported here becomes visible to all Swift files in this target.
#import "LegacyAuth.h"
#import "AnalyticsKit.h"
```

The reverse (ObjC consuming Swift) is automatic: every Swift target generates a `<TargetName>-Swift.h` umbrella header that ObjC files can `#import`. Only `@objc`-exposed Swift declarations show up there.

> **Frameworks vs apps:** Bridging headers are for **app targets only**. Framework targets use `module.modulemap` files instead.

---

## KVO: `observe(\.keyPath)`

Key-Value Observing is an ObjC-runtime feature that lets you watch a property for changes. In modern Swift, `NSObject.observe(_:options:changeHandler:)` is the type-safe entry point:

```swift
class User: NSObject {
    @objc dynamic var name = ""           // both annotations required for KVO
}

let user = User()
let token = user.observe(\.name, options: [.new]) { observed, change in
    print("name changed to \(change.newValue ?? "?")")
}

user.name = "Alice"   // observer fires
```

Two requirements:
1. The class inherits from `NSObject`.
2. The property is `@objc dynamic`.

The `token` is an `NSKeyValueObservation`. Hold on to it (typically as a stored property) — when it deallocates, the observation is removed.

> **For new code, prefer Combine's `@Published`/`@Observable`** over KVO. KVO is mainly for observing properties of frameworks you don't control.

---

## NotificationCenter: Posting and Observing

Apple frameworks use `NotificationCenter` heavily (keyboard notifications, app lifecycle events, scene changes). The names are `Notification.Name` constants, but old code may post raw strings.

```swift
// Modern API
let token = NotificationCenter.default.addObserver(
    forName: UIApplication.didEnterBackgroundNotification,
    object: nil,
    queue: .main
) { _ in
    saveState()
}
// Cancel:
NotificationCenter.default.removeObserver(token)
```

Notes:
- Hold the returned token. When it deallocates, the observer is removed.
- `queue: .main` ensures the closure runs on the main queue.
- `@Sendable` warnings can surface here under strict concurrency — see the [Concurrency chapter](concurrency-and-sendable.md).

---

## Calling C Directly: `@_cdecl`

Sometimes you need to expose a Swift function to C (for callbacks into a C library or SDK). Swift offers `@_cdecl`:

```swift
@_cdecl("my_swift_callback")
func mySwiftCallback(_ value: Int32) -> Int32 {
    return value * 2
}
```

C code can now call `extern int my_swift_callback(int);`. This is rare in app code; common in framework code that wraps a C library.

---

## C Pointers: The Five Variants

When ObjC/C APIs hand you pointers, Swift wraps them:

| C type | Swift type |
|---|---|
| `const T *` | `UnsafePointer<T>` |
| `T *` | `UnsafeMutablePointer<T>` |
| `const void *` | `UnsafeRawPointer` |
| `void *` | `UnsafeMutableRawPointer` |
| `T * _Nullable` | optional version of the above |

Use `withUnsafePointer(to:)`, `withUnsafeBytes`, etc., to safely produce a pointer when needed:

```swift
var x: Int32 = 42
withUnsafePointer(to: &x) { ptr in
    some_c_function(ptr)
}
```

These APIs are fenced for a reason — once a pointer escapes the closure, you're in undefined-behavior territory.

---

## Common Stack-Trace Symbols, Decoded

When you read a crash log, ObjC frames look like this:

```
-[UIView setText:]                  // instance method on UIView
+[NSURL URLWithString:]             // class method on NSURL
___24-[Foo bar]_block_invoke        // a block (closure) inside [Foo bar]
objc_msgSend                        // the runtime dispatching a message
```

If you see `objc_msgSend` deep in your stack with a Swift method just above, the Swift method is `@objc dynamic` and was invoked through the runtime.

---

## A Quick Recipe Cheat Sheet

| You want to... | Swift recipe |
|---|---|
| Call ObjC framework code | Just import — Apple frameworks are pre-bridged. |
| Expose Swift method to ObjC | `class X: NSObject { @objc func ... }`. |
| Expose Swift property to KVO | `class X: NSObject { @objc dynamic var ... }`. |
| Use a Swift method as a target-action | Mark it `@objc`; build the selector with `#selector(...)`. |
| Mix Swift + ObjC in one app target | Create a bridging header; let Xcode generate `<Target>-Swift.h` for ObjC. |
| Call a C function | Just call it — C functions are auto-imported as Swift functions. |
| Pass a Swift function to C | Mark the function `@_cdecl("name")`. |
| Get a `void *` to a Swift value | `withUnsafePointer(to: &value) { ... }`. |
| Override a class name for ObjC consumers | `@objc(LegacyName)` on the class. |
| Generate a Swift-shaped name for an ObjC API | Apple does it automatically — read the framework's "Swift Reference" page. |

---

## What Not to Do

- **Don't subclass `NSObject` reflexively.** `NSObject` is mandatory only when you need `@objc` exposure (KVO, target-action, NSCoding). Otherwise, plain Swift classes (or, ideally, structs) are leaner.
- **Don't sprinkle `@objc` on every method.** Each one disables compiler optimizations (devirtualization, inlining) for that call site. Use it where required, not as a default.
- **Don't manually retain/release.** ARC handles ObjC objects too. The old `retain`/`release`/`autorelease` machinery is gone from app code.
- **Don't write new code that depends on KVO or NotificationCenter when Combine or `@Observable` would work.** Use ObjC-runtime features for **observing things you don't control**, not for designing new event flows.
- **Don't fight the compiler when it says a signature isn't ObjC-representable.** It's right. Either add a Swift-side overload that *is* representable, or don't expose the ObjC entry point.

---

## Mapping From Other Languages

If you've worked with bridges between languages before, here are the closest analogues:

| You know... | ObjC interop maps to... |
|---|---|
| **Java/Kotlin** JNI | The same problem — bridging static-typed code to dynamic foreign code — but ObjC is a much closer cousin to Swift than C is to Java. |
| **Kotlin/Native** `@ObjCName`, `@CName` | Direct analogues to `@objc(name)` and `@_cdecl`. The whole concept transfers. |
| **Python** ctypes / cffi | Closer to Swift's C-pointer interop than to ObjC interop. |
| **C#** P/Invoke | The same role as `@_cdecl` for C; ObjC interop is much richer because the runtimes are more similar. |
| **Rust** FFI / `#[no_mangle]` | `@_cdecl` is the Swift equivalent for exporting to C. |
| **JavaScript** Node N-API or browser binding | No close analogue — JS doesn't have a static-typed foreign call surface like Swift's. |

---

**Companion chapters:**
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — `@objc` callbacks need careful Sendable analysis.
- [ARC, Capture & Lifetimes](arc-and-lifetimes.md) — ObjC objects participate in ARC; observation tokens need correct retention.

**Next:** [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md).

*Last updated: 2026-05-04*
