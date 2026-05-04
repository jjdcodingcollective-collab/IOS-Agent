# Plan: Phase E Tier 2/3/4 Remaining Backlog

## Summary

After Wrapper Phase 3 (push, shipped `01fd363`) and Phase E Tier 0/1 + BUILD-26/29
(shipped `e3cd4a1`/`6d340ff`), the remaining docs backlog is six chapters:
**BUILD-23, 24, 25, 27, 28, 30**. This plan sequences them by reader leverage,
batches the work into commits that are independently reviewable, and locks in
the per-language template so depth stays consistent.

The work is doc-only — no converter or wrapper code changes — so each batch can
ship as a self-contained PR-style commit and push to `origin/main` per the
project's "Documentation and Housekeeping before pushes" rule.

## Sequencing rationale

Ordered by **how many real-world readers each chapter serves**, biggest first.

| BUILD | Chapter | Audience size | Tier | Order |
|---|---|---|---|---|
| BUILD-23 | UIKit (mapped from imperative-UI traditions) | **All** non-greenfield iOS readers — universal | 2 | 1 |
| BUILD-24 | C# → Swift (Xamarin/MAUI sunset, Unity gameplay) | Large — active migration wave | 2 | 2 |
| BUILD-25 | Dart/Flutter → Swift (cross-platform replatforming) | Medium-large | 2 | 3 |
| BUILD-27 | C++/Objective-C++ interop (Swift 5.9+ first-class) | Narrow but technically deep — game/SDK devs | 3 | 4 |
| BUILD-28 | Rust → Swift FFI (cbindgen, SPM wrapping static lib) | Narrow — security/perf-sensitive crates | 3 | 5 |
| BUILD-30 | Go / Ruby / PHP migration | Smallest — server-language refugees | 4 | 6 |

UIKit goes first because every other chapter benefits from referring to it.
Source-language chapters (BUILD-24/25/30) follow the established Phase E
template (`from-kotlin.md`, `from-java.md`, `from-python.md`).
Interop chapters (BUILD-27/28) live in `02-swift-fundamentals/` next to
`swift-objc-interop.md`.

## Per-language template (locked)

For BUILD-24/25/30 follow the template proven in BUILD-16/17/18:

1. **Type-system mapping table** — source's primitives/collections/optionals/error model → Swift equivalents
2. **Idiom translation** — five to seven side-by-side code blocks for the patterns the source language is known for (e.g. C# LINQ → Swift sequence ops, Flutter widgets → SwiftUI views)
3. **Concurrency model mapping** — source's coroutines/async/threads → Swift Task/actor model
4. **Memory model differences** — GC vs ARC consequences in practice
5. **Where it gets weird** — three to five sharp gotchas that catch this audience specifically
6. **A representative real-world snippet** ported end-to-end
7. **Cross-links** — pointers to the relevant deep chapters (concurrency, ARC, generics, Codable, persistence)

Each chapter ends with a "Last updated" line and contributes one new entry to
the README TOC under "Language & Fundamentals" (or "UI Development" for
BUILD-23).

## Per-chapter deliverables

### BUILD-23 — UIKit chapter (`docs/04-ui-development/uikit-guide.md`)

**Audience:** Anyone joining a non-greenfield iOS codebase. Bridges from
imperative-UI traditions (Android Views, WPF/WinForms, web DOM, ObjC UIKit).

**Sections:**
- Why UIKit is still load-bearing (mixed codebases, SwiftUI-on-UIKit, AppKit parallels)
- The three pillars: `UIView`, `UIViewController`, `UIWindow`/`UIScene`
- View lifecycle (`viewDidLoad` / `viewWillAppear` / `viewDidLayoutSubviews` / `viewWillDisappear`) mapped to React lifecycle hooks and Android `onCreate`/`onResume`
- Auto Layout — the constraint mental model, intrinsic content size, NSLayoutAnchor, programmatic vs Storyboard vs XIB tradeoffs
- Storyboards / XIBs / programmatic UI — when each is appropriate, and why most production teams pick programmatic + child VC composition
- `UITableView` / `UICollectionView` with diffable data sources (the modern replacement for `cellForRowAt` + `reloadData`)
- Navigation: `UINavigationController` push/pop vs `UITabBarController` vs modal presentation
- Gestures, responder chain, and event bubbling — mapped from DOM event delegation and Android `onTouchEvent`
- **Bridging to SwiftUI**: `UIViewRepresentable`, `UIViewControllerRepresentable`, and the reverse `UIHostingController` for embedding SwiftUI in UIKit screens
- **Common pitfalls:** retain cycles in target/action, reusable cells holding stale references, Auto Layout cycle warnings, `viewDidLoad` vs `init` for setup
- Cross-links: ARC chapter (retain cycles in cell reuse), concurrency chapter (`@MainActor` for UI updates), SwiftUI chapter

### BUILD-24 — C# → Swift (`docs/02-swift-fundamentals/from-csharp.md`)

**Audience:** Xamarin/MAUI maintainers shipping cross-platform .NET code that
Microsoft is winding down; Unity gameplay devs porting to native iOS.

**Sections per template**, with these C#-specific emphases:
- **Type system:** value types vs reference types (struct vs class — same nominal split, very different ergonomics), nullable reference types, `record` → struct with synthesised conformances
- **LINQ → Sequence/Collection ops:** `Where` → `filter`, `Select` → `map`, `Aggregate` → `reduce`; lazy vs eager evaluation differences
- **Async model:** `Task<T>` / `async`/`await` → Swift `Task` + `async`/`await`; `IAsyncEnumerable` → `AsyncSequence`; `CancellationToken` → `Task.checkCancellation()`
- **Properties:** auto-properties, `init`-only setters, computed properties — direct map
- **Pattern matching:** switch expressions → Swift switch with `where` clauses; positional patterns
- **Generics:** `where T : class` / `where T : struct` constraints — Swift's `AnyObject` and lack of struct-only constraint
- **Memory:** GC pause-and-mark vs ARC determinism; finalizers vs `deinit`; `IDisposable`/`using` vs `defer` and ARC release timing
- **Where it gets weird:** Swift has no `internal` access to other modules, no `protected`, no static class members on protocols; Swift extensions are closer to C# extension methods but vary; trailing closures
- **Real-world port:** a small MVVM ViewModel exposing an `ObservableProperty<T>` translated to `@Observable` / `@Published`
- **Xamarin/MAUI sunset specifics:** how to incrementally port shared business logic by extracting it to a Swift package

### BUILD-25 — Dart/Flutter → Swift (`docs/02-swift-fundamentals/from-dart-flutter.md`)

**Audience:** Teams replatforming a Flutter app to native iOS, often after
hitting performance ceilings, plugin-ecosystem fragility, or platform-feature
needs that exceed the channel boundary.

**Sections per template**, plus:
- **Widget tree → View tree:** Flutter's everything-is-a-widget vs SwiftUI's struct-of-views; explicit StatefulWidget vs implicit `@State`
- **Layout:** Flutter's intrinsic sizing + flex-based parents → SwiftUI's layout protocol + `frame`/`Spacer`/`alignmentGuide`; equivalent table for `Row`/`Column`/`Expanded` → `HStack`/`VStack`/`Spacer`
- **State management mapping:** `setState` / Provider / Riverpod / BLoC → `@State` / `@ObservedObject` / `@Observable` / TCA-style stores
- **Async:** Dart `Future`/`Stream` → Swift `Task`/`AsyncSequence`
- **Null-safety:** sound null-safety in Dart 3 vs Swift optionals — both forbid implicit unwrapping but with different ergonomics
- **Memory:** Dart's generational GC vs ARC; the "rebuild widget tree on every frame" cost model has no SwiftUI equivalent (SwiftUI diffs)
- **Platform channels gone:** what platform-channel calls map to native APIs directly
- **Real-world port:** a `ChangeNotifier`-based VM ported to `@Observable`
- **Performance note:** SwiftUI's diffing model rewards small bodies; document the equivalent of `const Widget` constructors as `Equatable`-conforming view models

### BUILD-27 — C++ / Objective-C++ interop (`docs/02-swift-fundamentals/cpp-interop.md`)

**Audience:** Game engines, audio/video pipelines, cryptography or ML SDKs
exposing C++ headers to Swift apps.

**Sections:**
- Swift 5.9+ first-class C++ interop: `-cxx-interoperability-mode=default`
- Module setup: modulemap, package targets, header search paths
- What works: classes, namespaces, member functions, simple templates, `std::string` ↔ `String`
- What's still rough: ownership/lifetime when crossing the boundary (Swift expects ARC-style; C++ expects RAII), iterators, exceptions (Swift cannot catch C++ exceptions — wrap in C functions or noexcept)
- `std::vector<T>` and `std::map<K,V>` bridging — copy semantics, no automatic Sendable
- Objective-C++ as a fallback layer — when to use a `.mm` file as a thin facade
- Linking strategies: vendored static libs vs CocoaPods vs SPM binary frameworks
- **Pitfalls:** template instantiation in headers vs swiftmodules, ABI breakage on toolchain upgrades, `std::string_view` lifetime hazards
- Real-world: wrap a small C++ codec into a Swift package with a clean Swift API

### BUILD-28 — Rust → Swift FFI (`docs/02-swift-fundamentals/rust-ffi.md`)

**Audience:** Teams using Rust for security-sensitive code (crypto, parsers,
sync engines) and shipping it inside an iOS app.

**Sections:**
- The FFI surface: `extern "C"`, `#[no_mangle]`, `cbindgen` for header generation
- Memory ownership across the boundary: who allocates, who frees; `Box::into_raw` / `Box::from_raw` patterns
- Strings: `*const c_char` ↔ `String.init(cString:)`; UTF-8 invariants
- Result types: returning `Result<T, E>` requires translation to a tagged C struct or out-parameter
- Async crossing the boundary — there is no "Rust async ↔ Swift async" magic; pump completions through callbacks or a synchronous polling API
- Building a Swift package that wraps a Rust static lib (xcframework + module map)
- `cargo-swift` and `uniffi` as higher-level options; tradeoffs vs hand-written FFI
- **Pitfalls:** `panic!` across FFI is undefined behaviour — wrap with `catch_unwind`; differing thread-safety guarantees
- Real-world: wrap a tiny Rust parser as a Swift package and consume it from a SwiftUI view

### BUILD-30 — Go / Ruby / PHP (`docs/02-swift-fundamentals/from-server-langs.md`)

**Audience:** Server-side developers porting business logic into mobile apps,
or building tools that share logic between server and client.

Single combined chapter (not three separate files — the audiences are small
and the content overlaps heavily on "everything you knew about request/response
is now about views and lifecycle"). Sections per template, but compressed:
- Go: goroutines → Tasks; channels → AsyncStream; interfaces → protocols (with strong caveats around PATs); error returns → `throws`; no generics until recently — Swift's are richer
- Ruby: dynamic dispatch and metaprogramming have **no Swift equivalent**; this section is mostly "stop reaching for `method_missing`, here is the protocol-based replacement"
- PHP: type-juggling vs Swift's strict typing; superglobals → dependency-injected services; minimal coverage — many PHP devs going to iOS skip this and pick up Swift via a different lens

## Implementation order and commits

I recommend **three commits** to keep the diff reviewable:

1. **Commit 1 — BUILD-23 (UIKit):** the universal chapter; ships standalone.
2. **Commit 2 — BUILD-24 + BUILD-25 (C#, Dart/Flutter):** the two largest source-language audiences; pair them since both follow the same template.
3. **Commit 3 — BUILD-27 + BUILD-28 + BUILD-30 (C++ interop, Rust FFI, server langs):** the niche tail; group them since they're the smallest audiences and the per-chapter prose is shorter.

After each commit:

- Update `README.md` TOC and "Last Updated"
- Update `context/ACTIVE.md` (current state) and `context/REFERENCES.md` (chapter index)
- Mark the relevant BUILD items ✅ in `plans/gap-analysis-and-build-guide.md`
- `git push origin main`

## Out of scope

- No converter (`converter/`, `wrapper/`) changes — Phase E is documentation-only
- No new `from-objective-c.md` — ObjC is covered as a target/interop language in `swift-objc-interop.md`, not a source migration audience (different beast)
- No source-language chapters for Scala, Haskell, OCaml, Elixir, etc. — out-of-scope until a real audience surfaces

## Acceptance criteria

- All six chapters exist and follow the per-language template (or the UIKit-specific outline)
- Each chapter has working code samples (compiled mentally; no `try!`/`as!` in happy paths per BUILD-20's correctness rule)
- README TOC, ACTIVE, REFERENCES, and the gap-analysis build guide all reflect ✅ on BUILD-23/24/25/27/28/30
- Three commits pushed to `origin/main`

## Notes

- The "Phase E" name was coined in the 2026-05-04 docs review and is preserved here for continuity with the gap-analysis build guide.
- After this batch ships, the only remaining roadmap work is wrapper Phase 4 (conversational polish) and Phase 5 (`--open-pr`).
