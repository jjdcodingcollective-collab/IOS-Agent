# IOS-Agent Coding Guide — Language Transposition Gap Analysis

**Subject of review:** `docs/` (12 markdown files, 3,852 lines) plus `README.md`
**Review date:** 2026-05-04
**Lens:** How well does the guide cover transposing from popular coding languages to Swift for iOS?
**Verdict (one sentence):** The guide is a competent but narrow JavaScript/TypeScript-to-Swift bridge that misrepresents itself as a general "coding to Swift" resource, and even within its declared scope the depth is uneven.

---

## 1. Headline Finding

The guide is **monolingual on the source side**. The README (line 5) states the scope plainly:

> "Web developers who build with modern frameworks (React, Next.js, Vite), deploy on Vercel..."

A grep across the entire `docs/` tree returns **zero** matches for Python, Kotlin, Java (as a language), C#, C++, Objective-C, Flutter, Dart, Rust, or Go as source-language framings. The only matches that do appear (`ruby` in a Fastfile snippet, `PHPhotoLibrary` for the Photos framework) are coincidental Swift/iOS API names, not migration content.

JavaScript/TypeScript references appear **101 times across 10 files**. That is the entire transposition surface area.

If the project intends to be "a guide to transposing from popular coding languages to Swift," it is currently fulfilling roughly **one tile out of the matrix** — and arguably the easiest tile, since JS/TS-to-Swift is the smallest semantic jump for most concepts (closures, async/await, generics, optionals, structural typing).

---

## 2. Gap Analysis

### 2.1 Source-language coverage (the biggest gap)

| Source language | Coverage in guide | Realistic audience size for iOS migration | Gap severity |
|---|---|---|---|
| JavaScript / TypeScript | **Primary focus** (entire guide) | Large (web teams porting) | — covered |
| **Kotlin** | **None** | Very large — closest cousin language, every Android dev who picks up iOS | **Critical** |
| **Objective-C** | **None** (zero `@objc`, zero "bridging header", zero ObjC interop) | Universal — every non-greenfield iOS codebase has ObjC somewhere | **Critical** |
| **Java** | **None** | Large — Android (pre-Kotlin), enterprise backends building first iOS client | High |
| **Python** | **None** | Large — data scientists, ML engineers, backend devs building first mobile client | High |
| **C#** | **None** | Large — Xamarin/MAUI sunset migrations, Unity gameplay devs | High |
| **Dart / Flutter** | **None** | Growing — cross-platform refugees re-platforming to native | Medium |
| **C++ / Objective-C++** | **None** | Niche but high-value — game devs, ML/CV SDK authors | Medium |
| **Go** | **None** | Niche — backend devs writing first iOS app | Low |
| **Rust** | **None** | Niche, but Swift/Rust interop is increasingly relevant (Rust frameworks via FFI) | Low |
| **Ruby** | **None** | Niche (Rails devs) | Low |

**Why the Kotlin omission is the worst.** Kotlin and Swift are near-twins by design: nullable types, value/data classes, sealed classes vs. enums-with-payloads, structured concurrency (coroutines vs. async/await + Tasks), extension functions, trailing lambdas, property delegation. A well-written Kotlin→Swift section would be the highest-leverage chapter in the entire guide — most concepts translate 1:1 with footnotes, and the differences (actor isolation, Sendable, value-type-by-default, ARC vs JVM GC, no companion objects) are exactly the things that trip Kotlin devs up. Skipping this is a major missed opportunity.

**Why the Objective-C omission is operationally serious.** The guide markets itself partly as a tool for shipping real iOS apps (the converter, the Apple-ecosystem integration). Real iOS apps inevitably touch Objective-C — third-party SDKs, legacy code, framework headers, runtime introspection (`#selector`, `NSObject` inheritance, KVC/KVO, dynamic dispatch). The absence of any `@objc`, `@objcMembers`, `dynamic`, bridging-header, or `Selector` material is a material defect, not just a missing chapter.

### 2.2 Depth of coverage *within* the JS/TS lane

Even where the guide commits to its declared audience, the depth is shallow and inconsistent:

**Things only mentioned in passing or missing entirely from `swift-for-web-devs.md`:**
- **Generics & associated types.** No discussion. SwiftUI's `some View` is used dozens of times across other files but never explained as opaque return types. TypeScript devs ask exactly this question.
- **Protocol-oriented programming.** Protocols are introduced as "like interfaces" and the discussion stops there — no PAT (protocol with associated type) constraints, no existentials (`any P` vs. `some P`), no type erasure (`AnyView`, `AnyPublisher`), no `where` clauses. Swift 5.7+ existential syntax (`any`) is invisible.
- **Strict concurrency / Sendable / actors.** `actor` and `MainActor` appear in two snippets without conceptual treatment. The Swift 6 strict-concurrency model — the single biggest porting headache for any developer in 2025+ — is unaddressed. `Sendable` is never named.
- **ARC and retain cycles.** A single 20-line section in `web-dev-gotchas.md` (#6). No coverage of `weak` vs. `unowned`, capture lists beyond `[weak self]`, Combine subscription lifetime, `Task` cancellation and retention, or escaping vs. non-escaping closures.
- **Combine.** Zero references. Combine is still in production iOS codebases everywhere; web devs fluent in RxJS specifically need this.
- **Codable customization.** Networking chapter shows `JSONDecoder().decode(...)` but no `CodingKeys`, no custom `init(from:)`, no key-decoding strategies, no nested-key flattening. Real-world APIs require all of this.
- **Result builders / DSL mechanics.** SwiftUI is a result-builder DSL; the guide uses it extensively but never explains the `@ViewBuilder` / `@resultBuilder` mechanism. JS/TS devs from React backgrounds ask this on day three.
- **Property wrappers as a language feature.** Mentioned only as a SwiftUI cheat sheet. The mechanism (`@propertyWrapper`, `wrappedValue`, `projectedValue`, `$` projection) is not explained — so when devs see `$binding` in code, they have no model for it.
- **KeyPath.** Used implicitly (`@Environment(\.colorScheme)`) but never introduced.
- **Copy-on-write semantics for collections.** The struct-vs-class section claims structs are "copied on assignment" without nuance. For `Array`, `Dictionary`, `String`, this is *operationally* true but *implementationally* COW. Devs profiling memory will be confused.
- **Implicitly Unwrapped Optionals (`String!`).** Never mentioned. They appear in Apple framework signatures and surprise everyone.
- **Module / access control.** `import ModuleName` is in the cheat sheet, but `internal`, `fileprivate`, `private`, `public`, `open` are not. Web devs from `export`-everywhere conventions hit this hard.

### 2.3 iOS-environment specifics — uneven

- **App lifecycle (gotcha #5):** Adequate.
- **Main thread / main actor (gotcha #3):** Adequate but not deep.
- **UIKit:** Mentioned only in passing. The guide is heavily SwiftUI-first, which is reasonable for greenfield work, but ignores that **most real iOS jobs require UIKit competence** for legacy screens, custom controls, gesture systems, and `UIViewRepresentable` bridging. There is no UIKit-from-web-perspective material at all.
- **Xcode toolchain:** `01-getting-started/environment-setup.md` covers it, but signing/provisioning is glossed at the conceptual level only.
- **Apple ecosystem constraints (App Review, IDFA, ATT, privacy manifests):** Security guide and pitfalls touch on this but the privacy manifest (mandatory since May 2024) gets light treatment relative to its operational importance.
- **Core Data / SwiftData:** Not covered as language transposition. Web devs from ORMs (Prisma, Drizzle, ActiveRecord, SQLAlchemy) need this and don't get it.

### 2.4 Structural quality

The 12 chapters are well organized at the outline level, consistent in tone, cross-linked, and dated. Within-chapter consistency is the issue:

- **`swift-for-web-devs.md`** is a cheat-sheet (~400 lines covering 13 topics in average ~25 lines each). Each topic gets a code pair and a one-line takeaway. That is appropriate for a *quick reference* but is being asked to do the work of a *language guide* — which it cannot at that depth.
- **Inconsistency between docs:** `web-dev-gotchas.md` correctly forbids `try!`/`as!` (gotchas #2). But the same file's gotcha #3 example uses `try! Data(contentsOf: hugeFileURL)`, and `api-integration.md` line 22 uses `response as! HTTPURLResponse`. Force-unwrap discipline is preached but not enforced in the example code.
- **Inaccuracy — `@ObservedObject` ≠ `useContext`** (`swift-for-web-devs.md:362`). `useContext` is closer to `@EnvironmentObject` / `@Environment`. `@ObservedObject` is more analogous to a Zustand/MobX store passed in as a prop. This will mislead React devs.
- **Oversimplification — "interface → protocol"** (cheat sheet line 386). Accurate as a starting point, but Swift protocols with associated types, conditional conformance, and existentials behave differently enough from TS interfaces that the cheat-sheet line creates a false sense of equivalence.
- **No mention of TypeScript inference vs. Swift inference performance.** Swift's whole-expression type inference is famously slow on large literal expressions (`["a": 1, "b": 2.0, ...]`). Web devs hit this when migrating large config dictionaries. Worth a callout.

### 2.5 Out-of-scope but worth flagging

The converter (`converter/`, `wrapper/`) is **TypeScript-source only**. So the guide and the tool both encode the same scope. If the project's brand is "transposing popular coding languages to Swift," the operational tool also needs a roadmap for additional source languages — but that is a tool gap, not a documentation gap.

---

## 3. Future Build Plan (Prioritized)

Priority is based on (a) realistic migration audience size to iOS, (b) the linguistic distance from Swift (closer = more leverage per page), and (c) operational necessity for shipping real iOS apps.

### Tier 0 — Ship-blocking gaps (do before adding more languages)

| # | Item | Where it lives | Why now |
|---|---|---|---|
| 0.1 | **Objective-C interop chapter** | new `docs/02-swift-fundamentals/swift-objc-interop.md` | Every non-toy iOS codebase touches ObjC. `@objc`, bridging headers, `NSObject` subclassing, `Selector`, `dynamic`, KVO, framework header consumption. This is operational table stakes. |
| 0.2 | **Strict concurrency & Sendable** | extend `02-swift-fundamentals/` + new section in `03-architecture/` | Swift 6 strict concurrency is the #1 porting headache as of 2025. Every async chapter that doesn't address Sendable/actor isolation is incomplete. |
| 0.3 | **Generics, opaque types, existentials** | new section in `02-swift-fundamentals/` | Required to read SwiftUI signatures honestly. `some View` / `any P` distinction. |
| 0.4 | **ARC, capture lists, escaping closures, Task lifetime** | expand `web-dev-gotchas.md#6` into a full chapter | Currently 20 lines for the single biggest correctness hazard in Swift. Underweighted. |
| 0.5 | **Fix internal inconsistencies** | `web-dev-gotchas.md`, `api-integration.md`, `swift-for-web-devs.md` | Remove `try!`/`as!` from sample code, correct the `@ObservedObject` ↔ `useContext` mapping, add IUO note, add inference-perf note. |

### Tier 1 — Highest-leverage new source languages

| # | Item | Audience justification |
|---|---|---|
| 1.1 | **Kotlin → Swift** | Highest leverage per page. Almost every concept maps with footnotes. Audience: every Android dev considering iOS, every KMP team, every cross-platform refugee. Cover: nullable types, sealed class ↔ enum-with-payload, data class ↔ struct, coroutines ↔ async/await + Tasks, `suspend` ↔ `async`, `Flow` ↔ `AsyncSequence`, structured concurrency differences, `companion object` (no Swift equivalent — explain the migration), property delegates ↔ property wrappers, scope functions (`let`/`run`/`apply`/`also`/`with` — no direct Swift idiom). |
| 1.2 | **Java → Swift** | Audience: pre-Kotlin Android, enterprise Java backends building their first iOS client. Cover: classes-everywhere → struct-default, checked exceptions → typed throws (and untyped), interfaces → protocols (with the PAT caveat), POJOs → Codable structs, Streams → Sequence/lazy, Optionals (Java's vs Swift's), null → nil, JVM GC → ARC, package visibility → access modifiers. |
| 1.3 | **Python → Swift** | Audience: data/ML engineers building iOS clients, scientific Python devs onto Apple Silicon, Django/Flask backend devs. Cover: dynamic typing → static + inference, duck typing → protocols, list/dict comprehensions → map/filter/reduce, `__init__` → init, multiple inheritance → protocol composition, GIL → main actor & cooperative concurrency, exceptions → typed throws, decorators → property wrappers/result builders, virtualenv → SPM. Special: PythonKit if devs want to call back. |

### Tier 2 — Substantial audience, more linguistic distance

| # | Item | Audience justification |
|---|---|---|
| 2.1 | **C# → Swift** | Audience: Xamarin/MAUI sunset, Unity gameplay devs adopting Swift for iOS-side native plugins, .NET enterprise. Cover: classes vs structs (C# has both — semantic differences), properties (C# auto-properties vs Swift computed properties), LINQ → Sequence operations, `async/await` (similar but `Task` semantics differ), nullable references → optionals, generics constraints, events/delegates → Combine/closures. |
| 2.2 | **Dart / Flutter → Swift** | Audience: Flutter teams replatforming to native (real and increasing in 2025-26). Cover: widgets → SwiftUI views (composition model is similar), `setState` → `@State`, `Provider`/`Riverpod` → `@Observable`/`@Environment`, mixins → protocol extensions, sound null safety (similar mental model — easy section), Streams → AsyncSequence. |
| 2.3 | **Deepen JS/TS chapter** | Even within the declared audience, fill: Combine, Codable customization, KeyPath, property-wrapper authoring, result builders, UIKit-from-React perspective, Core Data / SwiftData mapped from ORM concepts. |

### Tier 3 — Specialist audiences, high value to the right reader

| # | Item | Audience justification |
|---|---|---|
| 3.1 | **C++ / Objective-C++ interop** | Game devs, ML/CV SDK authors, Metal shader interop. Cover: `extern "C"`, module maps, `@_cdecl`, header bridging, ARC bridging across languages, lifetime hazards across the boundary. C++ interop in Swift 5.9+ is increasingly first-class; this is the moment to document it. |
| 3.2 | **Rust → Swift FFI** | Increasingly relevant for Rust crates with iOS use cases (crypto, audio, parsing). Cover: `cbindgen`, Swift package wrapping a Rust static lib, ownership across the boundary, `Sendable` for FFI types. |

### Tier 4 — Smaller audiences, document when capacity allows

- Go → Swift (small but non-zero — backend devs)
- Ruby → Swift (Rails devs)
- PHP → Swift (uncommon path; lowest priority)

### Tier 5 — Cross-cutting additions (regardless of source language)

- **UIKit chapter mapped from each source language's imperative UI tradition** (Android Views, WinForms/WPF, UIKit's own history with ObjC). Skipping UIKit because "we recommend SwiftUI" is unrealistic for production work.
- **Privacy manifests + ATT + IDFA** (operational, mandatory) — should be elevated, not buried in security chapter.
- **Core Data / SwiftData mapped from ORMs** (Prisma, Hibernate, SQLAlchemy, Room).
- **Background modes, push, BGTaskScheduler** — not covered, frequently asked.
- **Apple-platform-specific concepts each language community lacks:** code signing, entitlements, capabilities, App Groups, sandbox.

---

## 4. Concrete Recommendations to the Author

1. **Either rebrand or expand.** If the project is "Web (JS/TS) → iOS," update the README to make that the primary identity and stop describing it as a general coding-to-Swift guide. If the project is genuinely "popular languages → Swift," the JS/TS-only scope is a serious shortfall and the build plan above is the path forward.
2. **Treat Tier 0 as bug fixes, not enhancements.** Strict concurrency, ObjC interop, ARC depth, and the few inconsistencies in sample code (force-unwraps in pages that forbid force-unwraps) are correctness issues, not nice-to-haves.
3. **Adopt a per-language template** before writing more languages. The template should force coverage of: variables/types, null model, error model, value vs reference, concurrency model, generics & polymorphism, memory model, module/visibility, testing idioms, and a "5 most surprising things" callout. Without this, the next chapters will drift in depth like the existing ones do.
4. **Don't grow `swift-for-web-devs.md` further — split it.** The cheat-sheet format is valuable; keep it. But the conceptual content (generics, concurrency, ARC, protocols-deep) belongs in dedicated companion files.
5. **Have the converter and the docs grow together.** Each new source language in the docs implies pressure on the converter. Decide explicitly which docs are converter-aligned and which are reference-only, so readers know where they are.

---

*Prepared by review of `docs/` at commit-state of branch `main` on 2026-05-04. All file references and line numbers reflect that snapshot.*
