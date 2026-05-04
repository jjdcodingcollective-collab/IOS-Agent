# C++ and Objective-C++ Interop

> Swift 5.9+ has first-class C++ interop — you can call C++ classes, namespaces, and (some) templates directly from Swift, no header-bridging dance through ObjC. The catch: ownership, exceptions, and template instantiation still need careful boundary design. This chapter covers what works, what's still rough, and when to drop down to Objective-C++ as a thin facade layer.

> **Audience:** Game engines, audio/video pipelines, cryptography or ML SDKs that ship C++ headers and need to be consumed cleanly from a Swift/iOS app. Also relevant if you're maintaining a long-lived Objective-C++ codebase that's transitioning to Swift.

---

## What "first-class C++ interop" actually means

Swift 5.9 (Xcode 15) introduced direct C++ interoperability behind a build flag. With it enabled:

- C++ classes appear in Swift as Swift types
- C++ member functions appear as Swift methods
- C++ namespaces appear as Swift enum-style namespaces
- Some C++ templates can be specialised and used from Swift
- `std::string` ↔ Swift `String` bridges automatically (with copies)
- `std::vector<T>` is iterable from Swift via a generated `Sequence` conformance

The interop is **not symmetric in maturity**: calling C++ from Swift is much further along than calling Swift from C++. For most app-level integrations this is fine — your C++ is the lower layer, your Swift is the consumer.

---

## Enabling interop

In a Swift Package:

```swift
// Package.swift
let package = Package(
    name: "MyApp",
    targets: [
        .target(
            name: "AudioCore",
            dependencies: [],
            cxxSettings: [
                .headerSearchPath("include"),
            ],
            swiftSettings: [
                .interoperabilityMode(.Cxx),
            ]
        ),
    ],
    cxxLanguageStandard: .cxx20
)
```

In an Xcode target: set **Build Settings → Swift Compiler — Language → C++ and Objective-C Interoperability** to `C++/Objective-C++`.

The flag must be set on **both** the Swift target consuming C++ and any module map that exposes the headers.

---

## Module setup

Swift sees C++ through a module — usually a clang `module.modulemap` file alongside the headers:

```
// module.modulemap
module AudioCore {
    header "AudioCore.hpp"
    requires cplusplus
    export *
}
```

In a Swift package, place this under `Sources/AudioCore/include/module.modulemap`, with headers in `Sources/AudioCore/include/`.

```cpp
// AudioCore.hpp
#pragma once

#include <string>
#include <vector>

namespace audio {

class Codec {
public:
    Codec(std::string name);
    std::vector<float> decode(const std::vector<uint8_t>& bytes) const;

private:
    std::string name_;
};

}  // namespace audio
```

```swift
// Use it from Swift
import AudioCore

let codec = audio.Codec(std.string("opus"))
let samples: std.vector<Float> = codec.decode(rawBytes)
```

Two things to notice:

1. The C++ namespace `audio` becomes a Swift namespace via the import — `audio.Codec`.
2. `std::string` and `std::vector<T>` are exposed as Swift-visible types, but **using them directly is awkward**. The cleaner pattern is to wrap with a Swift facade — see below.

---

## What works well

### Classes and member functions

Plain old C++ classes — constructors, destructors, member functions, static members — all just work. Reference semantics on the Swift side: C++ classes are imported as Swift classes (not structs) by default, so they're heap-allocated and passed by reference.

```cpp
class Synth {
public:
    Synth(double sampleRate);
    void noteOn(int midi);
    void noteOff(int midi);
    float renderSample();
};
```

```swift
let synth = Synth(44100.0)
synth.noteOn(60)
let sample = synth.renderSample()
```

The Swift compiler reads the C++ destructor and inserts ARC-style cleanup calls when the Swift reference goes out of scope. This works because C++ destructors are deterministic — same model as Swift's `deinit`.

### Namespaces

C++ namespaces map directly. `nested::namespace::Class` becomes `nested.namespace.Class` in Swift.

### Enums

C++ `enum class` types come across as Swift enums:

```cpp
enum class Channel : uint8_t { Left = 0, Right = 1, Mono = 2 };
```

```swift
let ch: Channel = .left
```

### Simple value types

C++ classes that are trivially copyable (POD-style — no virtual functions, no complex destructors, no pointer members) can be imported as Swift structs with the `SWIFT_NONCOPYABLE` / `SWIFT_COPYABLE` annotations or default copy semantics. The compiler generally figures this out.

### `std::string` ↔ `String`

`std::string` bridges to Swift's `String`, with copies in both directions. The conversion is:

```swift
import std

let cppName = std.string("hello")        // Swift String → std::string
let swiftName = String(cppName)          // std::string → Swift String
```

The copy cost is real for hot paths but negligible for app-level boundary crossings.

### `std::vector<T>`

`std::vector<T>` for trivial element types (numerics, simple structs) appears as a Swift sequence:

```swift
let samples: std.vector<Float> = codec.decode(bytes)
for s in samples {
    process(s)
}
let array: [Float] = Array(samples)   // copy into a Swift array if you want value semantics
```

---

## What's still rough

### Templates beyond simple specialisations

Swift can use *specialised* template types — `std::vector<int>`, `std::optional<float>`, `std::pair<std::string, int>` — when those specialisations are instantiated in a header Swift can see. **Generic template definitions don't survive** the import — Swift can't synthesise template instantiations on demand.

The pragmatic pattern: instantiate the templates you need in a header, give them concrete typedefs, and Swift sees those.

```cpp
// In a header
using FloatBuffer = std::vector<float>;
using ResultMap = std::map<std::string, double>;
```

### Exceptions

**Swift cannot catch C++ exceptions.** A thrown exception that propagates across the C++/Swift boundary is undefined behaviour and will crash. You have two options:

**Option 1: `noexcept` everywhere on the boundary.** Mark every C++ function exposed to Swift as `noexcept`. If something needs to throw, translate to a `Result`-style return at the C++ side:

```cpp
struct DecodeResult {
    bool ok;
    std::string error;
    std::vector<float> samples;
};

DecodeResult decode(const std::vector<uint8_t>& bytes) noexcept;
```

**Option 2: Wrap exception-throwing C++ in a `try`/`catch` shim.** A C-style or Objective-C++ shim catches and translates the exception into either a `Result` struct or an `NSError*` out parameter:

```objc
// .mm file
- (NSData *)decodeData:(NSData *)input error:(NSError **)error {
    try {
        auto result = decoder_->decode(...);
        return [NSData dataWithBytes:result.data() length:result.size()];
    } catch (const std::exception& e) {
        if (error) {
            *error = [NSError errorWithDomain:@"AudioCore"
                                         code:1
                                     userInfo:@{NSLocalizedDescriptionKey: @(e.what())}];
        }
        return nil;
    }
}
```

This is the most common pattern for production codebases — a thin ObjC++ facade with exception translation. Swift sees the throwing ObjC method via `try`.

### Iterators

C++ iterators are not directly callable from Swift in a clean way. `std::vector<T>::begin()/end()` are exposed but the idiomatic pattern is to use the auto-bridged `Sequence` conformance instead of trying to manipulate iterators by hand.

For STL containers without a good Sequence bridge (`std::map`, `std::set`), wrap the iteration in a C++ helper that pushes results into a `std::vector` and let Swift consume that.

### Ownership when crossing the boundary

C++ has multiple ownership models — raw pointers, `unique_ptr`, `shared_ptr`, references — and the "right" Swift mapping depends on which one. The default Swift import treats:

- A C++ class as Swift class (reference, ARC-managed, destructor on release)
- `std::shared_ptr<T>` as Swift class (reference, refcount stays in sync via ARC + shared_ptr bridge)
- `std::unique_ptr<T>` is awkward — generally wrap with a function that returns the underlying object directly, since `unique_ptr` semantics ("only one owner") clash with Swift's class reference model

A useful rule of thumb: **at the boundary, prefer either pure value semantics (POD structs) or shared ownership (`shared_ptr`/Swift class) — not unique ownership.**

### `std::string_view` and lifetime hazards

`std::string_view` is a non-owning reference to character data. If the underlying buffer is freed before the view is used, you get a dangling reference. Swift doesn't track this. **Don't expose `std::string_view` (or any `T*`/reference type whose backing buffer Swift doesn't own) at the boundary.** Take or return `std::string` (owning) instead, and accept the copy.

### ABI breakage on toolchain upgrades

C++ has no stable ABI on Apple platforms (libc++ has its own, but it's not a Swift ABI promise). Bumping the Xcode major version may rebuild C++ standard library types in ways that aren't binary-compatible with prebuilt `.a`/`.dylib` artefacts. **Treat vendored C++ static libs as toolchain-coupled** — either rebuild them with each Xcode upgrade or ship them as a `xcframework` with carefully matched build settings.

---

## Objective-C++ as a fallback layer

When direct C++ interop hits a wall — exceptions, templates that won't import, ownership patterns that don't translate — a `.mm` file is the escape hatch. ObjC++ files are compiled in a mode that understands both languages, and the resulting Objective-C class is fully Swift-friendly.

```objc
// CodecFacade.h — pure Objective-C interface
@interface CodecFacade : NSObject
- (instancetype)initWithName:(NSString *)name;
- (NSArray<NSNumber *> *)decode:(NSData *)bytes error:(NSError **)error;
@end
```

```objc
// CodecFacade.mm — C++ inside
#import "CodecFacade.h"
#include "audio/Codec.hpp"

@implementation CodecFacade {
    std::unique_ptr<audio::Codec> _codec;
}

- (instancetype)initWithName:(NSString *)name {
    if ((self = [super init])) {
        _codec = std::make_unique<audio::Codec>(name.UTF8String);
    }
    return self;
}

- (NSArray<NSNumber *> *)decode:(NSData *)bytes error:(NSError **)error {
    try {
        std::vector<uint8_t> input(
            (uint8_t *)bytes.bytes,
            (uint8_t *)bytes.bytes + bytes.length
        );
        auto samples = _codec->decode(input);

        NSMutableArray<NSNumber *> *result = [NSMutableArray arrayWithCapacity:samples.size()];
        for (float s : samples) {
            [result addObject:@(s)];
        }
        return result;
    } catch (const std::exception &e) {
        if (error) {
            *error = [NSError errorWithDomain:@"AudioCore"
                                         code:1
                                     userInfo:@{NSLocalizedDescriptionKey: @(e.what())}];
        }
        return nil;
    }
}

@end
```

```swift
// Swift sees the clean ObjC interface
let codec = CodecFacade(name: "opus")
do {
    let samples = try codec.decode(bytes)
    // ...
} catch {
    // exception translated through NSError
}
```

The win: Swift never sees C++. The cost: an extra layer of NSArray boxing for collections, manual translation of types. For most boundaries this is acceptable — the boundary isn't on the hot path.

See [Objective-C Interop](swift-objc-interop.md) for the full ObjC ↔ Swift bridging story.

---

## Linking strategies

| Strategy | When to use |
|---|---|
| **Source in a Swift package target** | You own the C++ source; cleanest setup |
| **Vendored static lib (`.a`) in a binary target** | Pre-built C++; package the `xcframework` |
| **CocoaPods** with a `vendored_frameworks` entry | Legacy or vendor-distributed binaries |
| **Pre-built dynamic lib (`.dylib`)** | Rare on iOS; App Store rejects most non-system dylibs |

For most modern projects, the answer is one of:

1. **Source-in-package**: simplest if you control the source. Swift Package Manager builds it with your app.
2. **`.xcframework` of `.a`s**: when the C++ comes from a different team or a third party, ship a multi-architecture xcframework with module map and headers.

Avoid CocoaPods unless you're already in a CocoaPods project — the integration overhead isn't worth it for new work.

---

## Pitfalls

1. **Forgetting the interop flag on the consuming target.** Symptom: C++ types are invisible from Swift. Fix: `swiftSettings: [.interoperabilityMode(.Cxx)]` on every target that imports the C++ module.

2. **Template instantiations missing from the imported header.** If you don't `using` (or otherwise instantiate) the specialisations Swift needs, Swift can't see them. Add typedefs at the boundary.

3. **C++ exceptions crossing into Swift.** Always undefined behaviour. Use `noexcept` or shim with try/catch in `.mm`.

4. **`std::string_view` or non-owning references at the boundary.** Lifetime guarantees don't translate. Pass `std::string` (owning) or copy into Swift `String`.

5. **`std::vector<T>` for a non-trivial `T`.** If `T` has a complex copy/move constructor or virtual functions, the bridge gets messy. Either flatten to POD types at the boundary or wrap each element in a class.

6. **Toolchain coupling on prebuilt libs.** Always rebuild C++ static libs against the Xcode you're shipping with. Don't ship a static lib built with Xcode 15 inside an Xcode 16 app without re-linking.

7. **Sendable warnings.** C++ types are not auto-`Sendable`. If you cross actor boundaries with C++ types, you'll need to either confine them to one actor or unsafe-cast at the boundary. See [Strict Concurrency & Sendable](concurrency-and-sendable.md).

---

## Real-world: wrapping a C++ codec into a Swift package

Project layout:

```
AudioCore/
├── Package.swift
└── Sources/
    └── AudioCore/
        ├── AudioCore.swift       (Swift facade)
        ├── CCodec/
        │   ├── include/
        │   │   ├── module.modulemap
        │   │   └── codec.hpp
        │   └── codec.cpp
```

```swift
// Package.swift
let package = Package(
    name: "AudioCore",
    products: [.library(name: "AudioCore", targets: ["AudioCore"])],
    targets: [
        .target(
            name: "AudioCore",
            dependencies: ["CCodec"],
            swiftSettings: [.interoperabilityMode(.Cxx)]
        ),
        .target(
            name: "CCodec",
            publicHeadersPath: "include",
            cxxSettings: [.headerSearchPath(".")]
        ),
    ],
    cxxLanguageStandard: .cxx20
)
```

```swift
// AudioCore.swift — the public Swift API
import CCodec

public struct Codec: ~Copyable {
    private var inner: audio.Codec

    public init(name: String) {
        self.inner = audio.Codec(std.string(name))
    }

    public func decode(_ bytes: Data) -> [Float] {
        let buffer = std.vector<UInt8>(bytes)
        let samples = inner.decode(buffer)
        return Array(samples)
    }
}
```

The Swift facade hides the C++ types entirely. Consumers see `Codec(name:)` and `Float` arrays — no `std::string`, no `std::vector<UInt8>`. This is the pattern to aim for: **C++ at the bottom, ObjC++ or direct interop in the middle, Swift facade at the top, app code on top of the facade.**

---

## Where this fits with the rest of the guide

- [Objective-C Interop](swift-objc-interop.md) — the bridging-header story; ObjC++ shims live here
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — C++ types are not auto-Sendable
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — Swift ARC vs C++ RAII; both deterministic, different mechanics
- [The Swift Toolkit](swift-toolkit-for-web-devs.md) — for the Swift facade patterns

---

*Last updated: 2026-05-04 — BUILD-27.*
