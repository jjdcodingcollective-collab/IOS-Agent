# Rust → Swift FFI

> Rust's appeal in iOS apps is narrow but real: cryptography, parsers, sync engines, ML model code, anything where Rust's safety + performance characteristics beat what you'd write in Swift. The bridge is a C ABI — `extern "C"` on the Rust side, a generated header on the Swift side. There are higher-level tools (`uniffi`, `cargo-swift`) but understanding the hand-rolled FFI is the foundation under all of them.

> **Audience:** Teams shipping Rust crates inside an iOS app — usually security-sensitive code where the Rust crate has a strong existing audit trail, or shared engines (think 1Password, Signal, Discord) running across desktop, web, and mobile.

---

## The 60-second mental model

1. **The bridge is a C ABI, not a Rust↔Swift bridge.** Both languages talk to C; you build the FFI on top of that lowest common denominator.
2. **Memory ownership crosses the boundary explicitly.** Who allocates, who frees — you decide and document. Get it wrong and you get use-after-free or double-free.
3. **Strings are `*const c_char`. UTF-8 invariants must be maintained.** Swift's `String` is UTF-8, Rust's `String` is UTF-8 — but `*const c_char` is just bytes.
4. **`Result<T, E>` doesn't cross FFI directly.** Encode it as a tagged C struct or use an out-parameter for the error.
5. **`panic!` across FFI is undefined behaviour.** Wrap every `extern "C"` body in `catch_unwind` or guarantee it can't panic.
6. **There is no async ↔ async magic.** Rust async and Swift async are different schedulers. Bridge with callbacks, completion functions, or polling.

---

## The FFI surface

### Rust side

```rust
// src/lib.rs

#[no_mangle]
pub extern "C" fn rs_parser_new() -> *mut Parser {
    Box::into_raw(Box::new(Parser::new()))
}

#[no_mangle]
pub extern "C" fn rs_parser_free(parser: *mut Parser) {
    if parser.is_null() { return; }
    unsafe { drop(Box::from_raw(parser)); }
}

#[no_mangle]
pub extern "C" fn rs_parser_parse(
    parser: *mut Parser,
    input: *const c_char,
    out_len: *mut usize,
) -> *mut c_char {
    let result = std::panic::catch_unwind(|| {
        let parser = unsafe { &mut *parser };
        let input = unsafe { CStr::from_ptr(input) }.to_str().ok()?;
        let parsed = parser.parse(input).ok()?;
        let bytes = parsed.into_bytes();
        unsafe { *out_len = bytes.len(); }
        Some(CString::new(bytes).ok()?.into_raw())
    });
    match result {
        Ok(Some(ptr)) => ptr,
        _ => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "C" fn rs_string_free(s: *mut c_char) {
    if s.is_null() { return; }
    unsafe { drop(CString::from_raw(s)); }
}
```

A few things every line is doing:

- `#[no_mangle]` keeps the symbol name stable so Swift can find it.
- `extern "C"` enforces the C calling convention — registers, stack layout, struct passing all match what the linker expects.
- `Box::into_raw` and `Box::from_raw` are the **ownership transfer primitives** — `into_raw` says "I'm handing this pointer to someone else, stop tracking it"; `from_raw` says "I'm taking this pointer back, resume tracking."
- `catch_unwind` catches a `panic!` and lets you return a sentinel (null pointer, error code) instead of unwinding through the FFI boundary, which is undefined behaviour.

### Generated header

`cbindgen` reads the Rust source and generates a C header automatically:

```toml
# cbindgen.toml
language = "C"
include_guard = "PARSER_FFI_H"
[export]
prefix = "rs_"
```

```bash
cbindgen --config cbindgen.toml --crate parser-ffi --output include/parser_ffi.h
```

```c
// include/parser_ffi.h (generated)
#ifndef PARSER_FFI_H
#define PARSER_FFI_H

#include <stddef.h>

typedef struct Parser Parser;

Parser *rs_parser_new(void);
void rs_parser_free(Parser *parser);
char *rs_parser_parse(Parser *parser, const char *input, size_t *out_len);
void rs_string_free(char *s);

#endif
```

The opaque struct (`typedef struct Parser Parser;`) hides the Rust type from the C side — Swift only sees a pointer.

### Swift side

Wrap the raw C API in a Swift class that owns the Rust object via ARC:

```swift
import ParserFFI

public final class Parser {
    private let inner: OpaquePointer

    public init() {
        guard let p = rs_parser_new() else {
            preconditionFailure("rs_parser_new returned nil")
        }
        self.inner = OpaquePointer(p)
    }

    deinit {
        rs_parser_free(UnsafeMutablePointer(inner))
    }

    public func parse(_ input: String) -> String? {
        var outLen: size_t = 0
        guard let cstr = input.withCString({ inputPtr in
            rs_parser_parse(UnsafeMutablePointer(inner), inputPtr, &outLen)
        }) else {
            return nil
        }
        defer { rs_string_free(cstr) }
        return String(cString: cstr)
    }
}
```

The pattern:

- The Swift class **owns** the Rust pointer for its lifetime.
- `deinit` calls the Rust deallocator. ARC ensures it runs exactly once, on the last release.
- String results from Rust are copied into Swift `String` immediately, then the Rust allocation is freed. Swift never holds a long-lived Rust-allocated buffer.

---

## Memory ownership patterns

The five rules that prevent the most common FFI bugs:

1. **One side allocates, the same side frees.** If Rust `Box`'s a value and hands it across, Rust must free it. Swift never calls `free()` on a Rust-allocated buffer; it calls back into Rust to free.
2. **Strings copy at every boundary crossing.** Don't try to share a buffer; the lifetime guarantees don't compose. Convert to/from `String` on each call.
3. **Opaque handles for long-lived Rust objects.** A `*mut SomeRustType` becomes a Swift class that holds it; the Swift class's `deinit` releases it.
4. **Slices/arrays are passed as `(pointer, length)` pairs.** Document who owns the buffer. The receiving side either copies immediately or calls back to release.
5. **Never store a Rust pointer in a Swift `struct`.** Structs are copied freely; you'd lose track of how many copies need to release. Use a class (reference type) and let ARC handle the count.

---

## Strings

Strings are the trickiest part of any FFI because of UTF-8 boundaries, ownership, and length conventions. The patterns:

### Swift → Rust (input)

```swift
public func parse(_ input: String) -> String? {
    input.withCString { ptr in
        // ptr is a *const c_char valid for the duration of this closure
        let result = rs_parser_parse(inner, ptr, &outLen)
        // ...
    }
}
```

`withCString` gives you a null-terminated UTF-8 buffer that lives for the duration of the closure. Don't escape the pointer.

### Rust → Swift (output)

```rust
let cstr = CString::new(bytes).ok()?;
cstr.into_raw()  // transfer ownership to caller
```

```swift
defer { rs_string_free(cstr) }
return String(cString: cstr)  // copies into Swift's heap
```

Swift's `String(cString:)` reads bytes until a null terminator. This is a copy — the original Rust buffer is no longer referenced by Swift, and the `defer` calls back to free it.

### Don't pass `&str` or `String` directly

These are Rust types with non-FFI-stable layouts. Always go through `*const c_char` + length, or `CString`/`CStr` at the boundaries.

---

## Result types

`Result<T, E>` doesn't have a stable C representation. Two patterns work:

### Pattern 1: Out-parameter for error

```rust
#[no_mangle]
pub extern "C" fn rs_decode(
    input: *const u8,
    input_len: usize,
    out_data: *mut *mut u8,
    out_len: *mut usize,
    out_error: *mut *mut c_char,
) -> bool {
    let result = std::panic::catch_unwind(|| {
        let bytes = unsafe { std::slice::from_raw_parts(input, input_len) };
        match decode(bytes) {
            Ok(decoded) => {
                let len = decoded.len();
                let ptr = Box::into_raw(decoded.into_boxed_slice()) as *mut u8;
                unsafe {
                    *out_data = ptr;
                    *out_len = len;
                }
                true
            }
            Err(e) => {
                let msg = CString::new(e.to_string()).unwrap_or_default();
                unsafe { *out_error = msg.into_raw(); }
                false
            }
        }
    });
    result.unwrap_or(false)
}
```

### Pattern 2: Tagged result struct

```rust
#[repr(C)]
pub struct DecodeResult {
    pub ok: bool,
    pub data: *mut u8,
    pub data_len: usize,
    pub error: *mut c_char,
}
```

Either pattern works; the out-parameter style scales better as you add more functions.

On the Swift side, wrap as a throwing function:

```swift
public func decode(_ data: Data) throws -> Data {
    var outData: UnsafeMutablePointer<UInt8>? = nil
    var outLen: size_t = 0
    var outError: UnsafeMutablePointer<CChar>? = nil

    let ok = data.withUnsafeBytes { bytes in
        rs_decode(
            bytes.bindMemory(to: UInt8.self).baseAddress,
            bytes.count,
            &outData,
            &outLen,
            &outError
        )
    }

    if !ok {
        let message = outError.map { String(cString: $0) } ?? "unknown error"
        if let outError { rs_string_free(outError) }
        throw ParserError.decodeFailed(message)
    }

    guard let outData else { throw ParserError.decodeFailed("nil output") }
    let result = Data(bytes: outData, count: outLen)
    rs_buffer_free(outData, outLen)  // pair with the Rust allocator
    return result
}
```

---

## Async crossing the boundary

There is no shortcut for "Rust async ↔ Swift async." Rust's executors (Tokio, async-std) and Swift's runtime are different worlds. Three workable patterns:

### Pattern 1: Synchronous Rust, called from Swift `Task.detached`

If the Rust work is CPU-bound (parsing, crypto, decompression), expose it as a synchronous C function. Call it from Swift inside a `Task.detached` to keep it off the main thread:

```swift
public func parse(_ input: String) async throws -> ParsedResult {
    try await Task.detached(priority: .userInitiated) {
        try parserSync(input)
    }.value
}
```

### Pattern 2: Callback-based Rust, bridged with `withCheckedContinuation`

For genuinely async Rust (network, IO) with a callback API:

```rust
#[no_mangle]
pub extern "C" fn rs_fetch(
    url: *const c_char,
    callback: extern "C" fn(*mut c_void, *mut Response),
    context: *mut c_void,
) {
    // Spawn a Tokio task; on completion, call back
}
```

```swift
public func fetch(_ url: String) async throws -> Response {
    try await withCheckedThrowingContinuation { continuation in
        url.withCString { urlPtr in
            let context = Unmanaged.passRetained(
                ContinuationBox(continuation)
            ).toOpaque()
            rs_fetch(urlPtr, fetchCallback, context)
        }
    }
}

// C function pointer — extern "C" on the Swift side
private func fetchCallback(context: UnsafeMutableRawPointer?, response: UnsafeMutablePointer<Response>?) {
    guard let context else { return }
    let box = Unmanaged<ContinuationBox>.fromOpaque(context).takeRetainedValue()
    if let response {
        box.continuation.resume(returning: Response(response.pointee))
    } else {
        box.continuation.resume(throwing: FetchError.unknown)
    }
}
```

The `Unmanaged.passRetained` / `takeRetainedValue` dance is how you move a Swift continuation across the C boundary safely — you retain on send, release on receive, and ARC stays balanced.

### Pattern 3: Polling

For long-running Rust work where you want incremental progress, expose a polling function that returns "in progress" / "done" / "error" each call. Swift drives the loop with `Task.sleep` between polls. Crude but reliable.

---

## Higher-level options

Hand-rolled FFI is the foundation. For most projects you'll reach for one of:

### `uniffi-rs`

Defines the FFI surface in a UDL (interface definition) file or via Rust attribute macros and generates language bindings — Swift, Kotlin, Python — automatically. Includes a runtime that handles strings, errors, async (with caveats), and basic collections.

**Pros:** much less hand-written FFI; multi-language out of the box; battle-tested by Mozilla.
**Cons:** the runtime is a hard dependency; the generated Swift is sometimes verbose; debugging across the generated layer adds friction.

### `cargo-swift`

A cargo subcommand that scaffolds a Swift package wrapping a Rust crate. Built on top of uniffi.

**Pros:** zero-config setup for the common cases.
**Cons:** opinionated; harder to escape if you outgrow it.

### Recommendation

- For a small, stable FFI surface (single crate, < 20 functions): hand-rolled is simpler.
- For a large or evolving surface: use uniffi.
- Never use FFI without `cbindgen` or equivalent — keeping the C header in sync by hand is a recipe for crashes.

---

## Building a Swift package wrapping a Rust static lib

The shape:

```
ParserKit/
├── Package.swift
├── Sources/
│   └── Parser/
│       └── Parser.swift            (Swift facade)
└── parser-rust/
    ├── Cargo.toml
    ├── cbindgen.toml
    ├── src/lib.rs
    └── target/
        ├── aarch64-apple-ios/
        │   └── release/libparser.a
        └── aarch64-apple-ios-sim/
            └── release/libparser.a
```

You build the `.a` files for each target (device + simulator + Mac Catalyst as needed) with cargo, then bundle them into an `.xcframework`:

```bash
cargo build --release --target aarch64-apple-ios
cargo build --release --target aarch64-apple-ios-sim
cargo build --release --target x86_64-apple-ios     # if you still ship Intel sim

xcodebuild -create-xcframework \
    -library target/aarch64-apple-ios/release/libparser.a \
    -headers include \
    -library target/aarch64-apple-ios-sim/release/libparser.a \
    -headers include \
    -output ParserFFI.xcframework
```

Then in `Package.swift`:

```swift
let package = Package(
    name: "ParserKit",
    products: [.library(name: "Parser", targets: ["Parser"])],
    targets: [
        .target(name: "Parser", dependencies: ["ParserFFI"]),
        .binaryTarget(name: "ParserFFI", path: "ParserFFI.xcframework"),
    ]
)
```

The Swift target depends on the binary target; consumers see the clean `Parser` API and never know there's Rust under the hood.

For CI: a `Makefile` or `build.sh` that runs the `cargo build`s and the `xcodebuild -create-xcframework` is the standard pattern. Don't try to drive cargo from inside Xcode build phases — it works for one developer and breaks on CI.

---

## Pitfalls

1. **`panic!` across FFI.** Always undefined behaviour. Wrap every `extern "C"` body in `catch_unwind`.

2. **Forgetting `#[no_mangle]`.** The function won't be findable from C. Cargo won't warn — the linker will, eventually.

3. **Allocating in Rust, freeing in Swift (or vice versa).** Different allocators. Use is undefined behaviour. Always pair allocate/free on the same side.

4. **Storing Rust pointers in Swift structs.** Structs are copied; you lose track of ownership. Use classes.

5. **Treating `*const c_char` as borrowed across calls.** The lifetime guarantees are weak. Copy at the boundary.

6. **Linking architecture mismatch.** A Mac-native `.a` won't link into an iOS app. Always rebuild for `aarch64-apple-ios` (device) and `aarch64-apple-ios-sim` (simulator) separately.

7. **`bitcode` mismatch.** iOS still sometimes asks for bitcode-embedded artefacts. Rust's nightly supports it via `RUSTFLAGS="-C embed-bitcode=yes -C lto"`, but configuration is fiddly. Check the current Apple guidance before assuming.

8. **Threading.** Rust types are `Send`/`Sync` or not. If a Rust handle is `!Send` (most of `RefCell`-based types), confine it to one thread/actor on the Swift side. See [Strict Concurrency & Sendable](concurrency-and-sendable.md).

---

## Real-world: a parser as a Swift package

A complete shape:

```rust
// parser-rust/src/lib.rs
use std::ffi::{CStr, CString};
use std::os::raw::c_char;

pub struct Parser { /* internals */ }

impl Parser {
    pub fn new() -> Self { Self { /* ... */ } }
    pub fn parse(&self, input: &str) -> Result<String, String> {
        // ... real work
        Ok(format!("parsed: {}", input))
    }
}

#[no_mangle]
pub extern "C" fn parser_new() -> *mut Parser {
    Box::into_raw(Box::new(Parser::new()))
}

#[no_mangle]
pub extern "C" fn parser_free(p: *mut Parser) {
    if !p.is_null() { unsafe { drop(Box::from_raw(p)); } }
}

#[no_mangle]
pub extern "C" fn parser_parse(
    p: *const Parser,
    input: *const c_char,
    out_error: *mut *mut c_char,
) -> *mut c_char {
    std::panic::catch_unwind(|| {
        let parser = unsafe { &*p };
        let input = unsafe { CStr::from_ptr(input) }.to_str().ok()?;
        match parser.parse(input) {
            Ok(s) => CString::new(s).ok().map(|c| c.into_raw()),
            Err(e) => {
                let msg = CString::new(e).unwrap_or_default();
                unsafe { *out_error = msg.into_raw(); }
                None
            }
        }
    }).ok().flatten().unwrap_or(std::ptr::null_mut())
}

#[no_mangle]
pub extern "C" fn parser_string_free(s: *mut c_char) {
    if !s.is_null() { unsafe { drop(CString::from_raw(s)); } }
}
```

```swift
// Sources/Parser/Parser.swift
import ParserFFI

public final class Parser: @unchecked Sendable {
    private let inner: OpaquePointer

    public init() {
        guard let p = parser_new() else {
            preconditionFailure("parser_new returned nil")
        }
        self.inner = OpaquePointer(p)
    }

    deinit {
        parser_free(UnsafeMutablePointer(inner))
    }

    public func parse(_ input: String) throws -> String {
        var errorPtr: UnsafeMutablePointer<CChar>? = nil
        let result = input.withCString { inputPtr in
            parser_parse(UnsafePointer(inner), inputPtr, &errorPtr)
        }

        if let result {
            defer { parser_string_free(result) }
            return String(cString: result)
        }

        if let errorPtr {
            defer { parser_string_free(errorPtr) }
            throw ParserError.parseFailed(String(cString: errorPtr))
        }

        throw ParserError.parseFailed("unknown error")
    }
}

public enum ParserError: Error {
    case parseFailed(String)
}
```

The Swift class is `@unchecked Sendable` with the assumption that the underlying Rust `Parser` is thread-safe. If it isn't, drop the `Sendable` and confine to a specific actor.

---

## Where this fits with the rest of the guide

- [Objective-C Interop](swift-objc-interop.md) — bridging headers and module maps; the same plumbing applies
- [C++ Interop](cpp-interop.md) — adjacent FFI story; many of the same patterns
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — `@unchecked Sendable` on Rust-backed types
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — manual `deinit` for resource cleanup

---

*Last updated: 2026-05-04 — BUILD-28.*
