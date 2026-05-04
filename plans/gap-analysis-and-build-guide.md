# iOS Code Converter — Comprehensive Gap Analysis & Build Guide

> **Date:** 2026-04-25
> **Scope:** Full assessment of the 4-phase converter pipeline, learning system, and project assembly
> **Objective:** Identify every gap preventing production-grade iOS readiness, explain *why* each matters, and provide a structured remediation path

---

## Executive Summary

The iOS Code Converter is a well-architected 4-phase pipeline (Analyzer → Reviewer → Rewriter → Assembler) that converts TypeScript/React web apps into Swift/SwiftUI projects with educational annotations. It currently handles ~83% of a sample app automatically, covers 10 pattern detectors, 70+ type mappings, 85+ npm→SPM mappings, and generates a companion learning guide.

However, significant gaps remain across **five dimensions**:

| Dimension | Gaps Found | Severity Breakdown |
|---|---|---|
| **Parsing & Code Generation** | 9 gaps | 3 critical, 4 major, 2 minor |
| **iOS Platform Coverage** | 8 gaps | 2 critical, 4 major, 2 minor |
| **Educational System** | 6 gaps | 1 critical, 3 major, 2 minor |
| **Tooling & Validation** | 5 gaps | 2 critical, 2 major, 1 minor |
| **Framework & Language Support** | 4 gaps | 1 critical, 2 major, 1 minor |

**Total: 32 gaps** — 9 critical, 15 major, 8 minor.

The 12 bugs documented in `converter-bug-fixes.md` have been addressed in recent commits. This analysis goes beyond those fixes to identify systemic and architectural gaps.

---

## Part 1: Gap Analysis

Each gap is classified by:
- **Severity:** Critical (blocks usable output), Major (output compiles but is wrong/incomplete), Minor (style/polish)
- **Phase:** Which converter phase is affected
- **Impact:** What breaks without the fix

---

### 1. Parsing & Code Generation Gaps

#### GAP-P1: No AST Parsing — Regex-Only Approach Hits a Ceiling
- **Severity:** Critical
- **Phase:** All (especially Phase 3)
- **Current State:** Every converter uses regex pattern matching against raw source strings. This works for simple patterns but fails on:
  - Nested generics: `Record<string, Array<Partial<User>>>`
  - Multi-line destructuring: `const { a, b, ...rest } = useCustomHook()`
  - Template literal expressions in JSX: `` className={`flex ${isActive ? 'bg-blue' : 'bg-gray'}`} ``
  - Deeply nested JSX with mixed expressions and components
- **Impact:** The converter silently produces wrong output or falls back to `EmptyView()` / `Any` for any moderately complex real-world file. The 12 bug fixes already committed are symptoms of this ceiling — each fix adds more regex special cases rather than solving the root cause.
- **Why This Matters for iOS:** Xcode's compiler is strict. A single wrong type or missing property makes the entire project fail to build. Web tools can be approximate; iOS output must be syntactically correct or it's useless.

#### GAP-P2: No Import Graph — Files Converted in Isolation
- **Severity:** Critical
- **Phase:** Phase 3 (Rewriter)
- **Current State:** Each file is converted independently. The engine reads source files from the manifest but does not build a dependency graph from `import` statements. This means:
  - When `UserCard.tsx` imports `User` from `../types/user.ts`, the component converter doesn't know the shape of `User`
  - Custom component references (Fix #3) are resolved by naming convention only — no verification that the referenced view actually exists or has matching props
  - Shared types used across files may be generated multiple times or inconsistently
- **Impact:** Cross-file type references produce `Any` fallbacks. Component composition breaks when prop types don't match between generated files.
- **Why This Matters for iOS:** Swift's type system is strict and nominal — `UserCardView(user: someValue)` won't compile if the initializer expects a different type than what's passed. The web's structural typing is forgiving; Swift's nominal typing is not.

#### GAP-P3: No Generic/Complex Type Resolution
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) — `swift_helpers.py:96-178`
- **Current State:** `map_type()` handles simple generics (`Array<T>`, `Record<K,V>`) but fails on:
  - Nested generics: `Promise<Array<User>>` — the inner `Array<User>` is passed as a raw string
  - Intersection types: `User & { role: string }` — no handling at all
  - Mapped types: `{ [K in keyof T]: boolean }` — falls through to `Any`
  - Conditional types: `T extends string ? A : B` — falls through to `Any`
  - Index access types: `User['address']` — falls through to `Any`
  - Template literal types: `` `${string}-${number}` `` — falls through to `Any`
- **Impact:** Complex TypeScript codebases (which are most production codebases) produce excessive `Any` types, defeating Swift's type safety advantage.

#### GAP-P4: Incomplete JSX-to-SwiftUI Element Coverage
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) — `component_converter.py:467-738`
- **Current State:** `process_jsx_element()` handles 15 HTML elements explicitly. Missing:
  - `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<td>`, `<th>` — extremely common, no mapping
  - `<nav>`, `<header>`, `<footer>`, `<aside>` — semantic HTML → should map to layout containers
  - `<video>`, `<audio>` — media elements → `VideoPlayer` / `AVPlayer`
  - `<canvas>` → `Canvas` view
  - `<svg>` → Shape/Path constructs
  - `<progress>`, `<meter>` → `ProgressView`, `Gauge`
  - `<dialog>`, `<details>` → `.sheet()`, `DisclosureGroup`
- **Impact:** Any component using tables, media, or semantic HTML produces `EmptyView()` stubs.

#### GAP-P5: No Handling of React Fragments and Portals
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter)
- **Current State:** `<> ... </>` (React fragments) and `<React.Fragment>` are not detected. `ReactDOM.createPortal()` is not handled.
  - Fragments should map to `Group { }` in SwiftUI
  - Portals have no direct SwiftUI equivalent but need a documented pattern (e.g., `.sheet()`, `.overlay()`, or `@Environment` injection)
- **Impact:** Components using fragments (very common) fail to extract children correctly.

#### GAP-P6: useEffect Conversion is Oversimplified
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) — `component_converter.py`
- **Current State:** `useEffect` is detected by the analyzer but the rewriter only generates `.task { }` stubs. No handling for:
  - Empty dependency array `[]` → `.task { }` (correct, but body not converted)
  - Specific dependencies `[userId]` → `.task(id: userId) { }` or `.onChange(of: userId) { }`
  - Cleanup function → `.onDisappear { }` or structured concurrency cancellation
  - Multiple `useEffect` calls → multiple `.task` or `.onChange` modifiers
  - `useLayoutEffect` → needs synchronous execution context
- **Impact:** Any component with side effects produces a skeleton that requires 100% manual rewriting.
- **Why This Matters for iOS:** `.task` vs `.onAppear` vs `.onChange` have different lifecycle semantics. Choosing wrong causes bugs: `.onAppear` fires on every tab switch, `.task` only on first appearance, `.onChange` on value changes. The educational gap is significant — developers need to understand *which* modifier maps to *which* `useEffect` pattern.

#### GAP-P7: State Setter Patterns Beyond Simple Assignment
- **Severity:** Minor
- **Phase:** Phase 3 (Rewriter) — `component_converter.py:963-1012`
- **Current State:** `convert_handler()` detects `setX(value)` and `setX(!x)` but misses:
  - Functional updates: `setCount(prev => prev + 1)` → `count += 1`
  - Object spread: `setUser({...user, name: 'new'})` → `user.name = "new"` (or struct copy)
  - Array mutations: `setItems([...items, newItem])` → `items.append(newItem)`
  - Filtered updates: `setItems(items.filter(i => i.id !== id))` → `items.removeAll { $0.id == id }`
- **Impact:** Most real handler functions produce only `// TODO: Port handler logic`.

#### GAP-P8: No Support for Higher-Order Components (HOCs) or Render Props
- **Severity:** Minor
- **Phase:** Phase 3 (Rewriter)
- **Current State:** The component extractor looks for function/arrow components only. HOC patterns like `export default withAuth(MyComponent)` or render prop patterns like `<DataProvider render={(data) => ...}/>` are not detected.
- **Impact:** HOC-wrapped exports fail to extract. The component appears to have no source.

#### GAP-P9: String Template Literal Conversion
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) — `component_converter.py:1466-1493`
- **Current State:** `convert_text_expression()` handles `{variable}` interpolation but not:
  - Template literals: `` `Hello ${user.name}` `` → `"Hello \(user.name)"`
  - Tagged templates: `` css`color: red` `` — no handling
  - Multi-line templates with embedded expressions
  - Conditional expressions inside templates: `` `${count > 0 ? 'items' : 'empty'}` ``
- **Impact:** Template literals in JSX text content are passed through as raw JS, producing invalid Swift strings.

---

### 2. iOS Platform Coverage Gaps

#### GAP-I1: No Xcode Project File Generation (.xcodeproj / .xcworkspace)
- **Severity:** Critical
- **Phase:** Phase 4 (Assembler)
- **Current State:** The assembler generates a directory of Swift files, `Package.swift`, and `xcconfig` files — but no `.xcodeproj` or `.xcworkspace`. The developer must manually:
  1. Open Xcode → File → New → Project
  2. Choose iOS App template
  3. Drag in all generated files
  4. Configure build settings to reference xcconfig files
  5. Add SPM dependencies manually
- **Impact:** The "open in Xcode and build" experience is broken. This is the single biggest friction point for a web developer trying the tool for the first time.
- **Why This Matters for iOS:** Unlike web development where you `npm install && npm run dev`, iOS projects require Xcode project configuration. Without a `.xcodeproj`, the generated code is just files on disk — not a buildable project. Apple introduced `Package.swift`-based apps in Xcode 15, but the tool doesn't generate the required structure for that either.

#### GAP-I2: No Info.plist Generation
- **Severity:** Critical
- **Phase:** Phase 4 (Assembler)
- **Current State:** No `Info.plist` is generated. This file is required for:
  - App display name, bundle ID, version number
  - Privacy permission descriptions (camera, location, notifications — Apple rejects apps without these)
  - App Transport Security exceptions for HTTP URLs
  - URL schemes for deep linking
  - Supported orientations and device families
- **Impact:** Even if the developer creates an Xcode project manually, it won't pass App Store review without proper `Info.plist` entries, especially privacy descriptions.
- **Why This Matters for iOS:** Apple's App Review is strict. If the app requests location permission but the `Info.plist` lacks `NSLocationWhenInUseUsageDescription`, the app is rejected immediately. Web developers don't deal with this — the browser handles permissions prompts. This is a critical educational gap.

#### GAP-I3: No Accessibility Support in Generated Views
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter)
- **Current State:** Generated SwiftUI views have no accessibility modifiers:
  - No `.accessibilityLabel()` on images or icons
  - No `.accessibilityHint()` on interactive elements
  - No `.accessibilityValue()` on dynamic content
  - No `.accessibilityElement(children:)` for grouped content
  - ARIA attributes in the source (`aria-label`, `aria-hidden`, `role`) are silently dropped
- **Impact:** Generated apps fail Apple's accessibility audit. Apps without accessibility can be rejected from the App Store and expose legal liability (ADA compliance).
- **Why This Matters for iOS:** Apple takes accessibility seriously — it's a first-class framework feature, not an afterthought. Web developers accustomed to optional ARIA compliance need to understand that iOS accessibility is both a technical requirement and a quality bar Apple enforces.

#### GAP-I4: No Error Handling Patterns for Network Code
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) — `service_converter.py`
- **Current State:** Generated service code uses `async throws` but doesn't generate:
  - `do/catch` blocks at call sites
  - Typed error enums (`enum APIError: Error { case unauthorized, notFound, ... }`)
  - Retry logic for transient failures
  - Network reachability checks (`NWPathMonitor`)
  - Loading/error state in ViewModels (`enum LoadState<T> { case idle, loading, loaded(T), error(Error) }`)
- **Impact:** Service code compiles but crashes on first network error. Web developers used to `.catch()` chains don't see the equivalent Swift pattern.
- **Why This Matters for iOS:** Swift's error handling is explicit — `try/catch` is enforced by the compiler, unlike JavaScript's optional `.catch()`. This is actually an advantage, but the generated code doesn't demonstrate the pattern.

#### GAP-I5: No Image Asset Pipeline
- **Severity:** Major
- **Phase:** Phase 4 (Assembler)
- **Current State:** The assembler generates an empty `Assets.xcassets` with placeholder AppIcon and AccentColor entries. No handling for:
  - Detecting image imports in source code (`import logo from './logo.png'`)
  - Copying referenced images into `Assets.xcassets`
  - Generating `@1x`, `@2x`, `@3x` variants (or at minimum noting they're needed)
  - SF Symbols mapping for common icon libraries (Heroicons, Lucide, FontAwesome → SF Symbols equivalents)
  - Color asset generation from Tailwind/CSS color palettes
- **Impact:** All image references in generated code point to assets that don't exist.

#### GAP-I6: No Data Persistence Layer Beyond UserDefaults
- **Severity:** Major
- **Phase:** Phase 2 (Reviewer) + Phase 3 (Rewriter)
- **Current State:** `localStorage` maps to `UserDefaults`, `sessionStorage` maps to `@State`. But no coverage for:
  - IndexedDB → SwiftData / Core Data
  - Web SQL → SQLite via SwiftData
  - Complex client-side caching (Apollo cache, React Query cache) → SwiftData or URLCache
  - File storage (Blob URLs, downloads) → FileManager
- **Impact:** Any app with meaningful client-side data storage gets no conversion guidance.
- **Why This Matters for iOS:** SwiftData (introduced iOS 17) is Apple's modern persistence framework. It's the closest equivalent to IndexedDB + an ORM, but uses Swift macros and model declarations that are fundamentally different from web storage APIs. This is a major educational opportunity.

#### GAP-I7: No Concurrency Safety Annotations
- **Severity:** Minor
- **Phase:** Phase 3 (Rewriter)
- **Current State:** Generated code uses `async/await` and the `APIClient` is an `actor`, but:
  - No `@Sendable` annotations on closures passed across concurrency domains
  - No `@MainActor` annotations on ViewModel classes (required for UI state updates)
  - No `nonisolated` markers on computed properties that don't need actor isolation
  - Generated `Task { }` blocks inside views don't specify `@MainActor` context
- **Impact:** Swift 6 strict concurrency mode produces dozens of warnings/errors on generated code. These are currently warnings (Swift 5.x) but will be errors in Swift 6.
- **Why This Matters for iOS:** Swift's concurrency model is one of its biggest differentiators from JavaScript. Web developers don't think about thread safety at all. The generated code should model correct concurrency patterns, and the learning notes should explain why.

#### GAP-I8: No Deep Link / URL Scheme Handling
- **Severity:** Minor
- **Phase:** Phase 2 (Reviewer) + Phase 4 (Assembler)
- **Current State:** React Router routes are detected but no guidance on:
  - Universal Links configuration (for `https://` links opening the app)
  - Custom URL schemes (for `myapp://` deep links)
  - `onOpenURL` modifier in SwiftUI for handling incoming URLs
  - App Clip support for lightweight entry points
- **Impact:** Apps that rely on URL-based navigation (common in web apps) lose that functionality entirely on iOS.

---

### 3. Educational System Gaps

#### GAP-E1: No Interactive or Progressive Learning Path
- **Severity:** Critical
- **Phase:** Learning system (`converter/learning/`)
- **Current State:** The learning system is passive — it generates a static `learning-notes.md` file and inline comments. There is no:
  - Difficulty progression (beginner → intermediate → advanced concepts)
  - Interactive exercises or challenges ("Try modifying this view to add a tap gesture")
  - Before/after comparison views showing the TypeScript and Swift side by side
  - Concept dependency graph (you need to understand `@State` before `@Observable`)
  - Knowledge assessment or self-check questions
- **Impact:** Developers read the notes once and forget them. The educational value decays rapidly because there's no reinforcement or structured progression.
- **Why This Matters for iOS:** The web→iOS transition involves learning a new language (Swift), a new UI framework (SwiftUI), a new IDE (Xcode), a new build system, and a new deployment model simultaneously. A static document can't teach all of this effectively. The learning system should guide developers through this transition in a structured way.

#### GAP-E2: No "Why This Won't Work" Annotations for Anti-Patterns
- **Severity:** Major
- **Phase:** Learning system (`converter/learning/annotations.py`)
- **Current State:** Annotations explain *why Apple's way is better* but don't warn about common mistakes web developers make:
  - Using `ObservableObject` (old) instead of `@Observable` (new) — many tutorials are outdated
  - Putting heavy logic in `var body` (causes re-computation every render)
  - Using `AnyView` everywhere instead of `@ViewBuilder` or generics (destroys SwiftUI's diffing)
  - Force-unwrapping optionals (`!`) instead of using `if let` / `guard let`
  - Making network calls in `init()` instead of `.task { }`
  - Using `@State` for shared data instead of `@Observable` ViewModel
  - Storing sensitive data in `UserDefaults` instead of `Keychain`
- **Impact:** Developers learn what to do but not what to avoid. The most common web-to-iOS mistakes aren't covered.

#### GAP-E3: Missing Annotations for Key iOS Concepts
- **Severity:** Major
- **Phase:** Learning system (`converter/learning/annotations.py`)
- **Current State:** The annotation database covers 18 concepts. Missing critical topics:
  - **App lifecycle** — `scenePhase`, background/foreground transitions, app states
  - **Memory management** — ARC, retain cycles, `weak`/`unowned` references
  - **SwiftUI layout system** — how `frame`, `padding`, `GeometryReader` work (very different from CSS box model)
  - **Animations** — `withAnimation`, implicit vs explicit animations, `matchedGeometryEffect`
  - **Gestures** — `TapGesture`, `DragGesture`, `LongPressGesture` composition
  - **Lists and performance** — `List` vs `LazyVStack`, cell reuse, `@FetchRequest`
  - **Sheet/alert/confirmation dialog** — modal presentation patterns
  - **Property wrappers beyond @State** — `@Binding`, `@StateObject`, `@AppStorage`, `@SceneStorage`
  - **Protocol-oriented design** — why Swift favors protocols over class inheritance
  - **Generics** — why Swift generics are more powerful than TypeScript generics
- **Impact:** The learning guide covers ~60% of what a web developer needs to know. Major gaps in layout, lifecycle, and memory management.

#### GAP-E4: No Platform-Specific Guidance (iPad, watchOS, macOS)
- **Severity:** Major
- **Phase:** Phase 4 (Assembler) + Learning system
- **Current State:** All generated code targets iPhone only. No guidance on:
  - iPad split-view / multi-column navigation (`NavigationSplitView`)
  - macOS catalyst or native macOS builds
  - watchOS complications and widget extensions
  - iOS widgets (WidgetKit)
  - Adaptive layouts that work across screen sizes
- **Impact:** Web developers building responsive web apps need to understand how iOS handles multiple form factors — it's fundamentally different from CSS media queries.

#### GAP-E5: No Comparison of Web vs iOS Development Workflows
- **Severity:** Minor
- **Phase:** Documentation (`docs/`)
- **Current State:** The docs explain iOS concepts but don't directly compare developer workflows:
  - Hot reload (web) vs Xcode Previews (iOS) — similar intent, very different mechanics
  - `npm run dev` (web) vs Cmd+R in Xcode (iOS) — build → run → test cycle differences
  - Browser DevTools (web) vs Xcode Instruments (iOS) — debugging and profiling
  - CI/CD with Vercel/Netlify (web) vs Xcode Cloud/Fastlane (iOS)
  - Version control + deployment (web: push → deploy) vs (iOS: push → build → TestFlight → review → release)
- **Impact:** Developers understand the code differences but not the workflow differences, which are equally disorienting.

#### GAP-E6: Learning Notes Don't Reference Generated Code Locations
- **Severity:** Minor
- **Phase:** Learning system (`converter/learning/notes_generator.py`)
- **Current State:** Learning notes explain concepts generically but don't point to specific lines in the generated Swift files where those concepts appear.
  - "Why @State Instead of useState()" explains the concept but doesn't say "See `UserCardView.swift:12` where `@State private var user` was generated from your `useState<User>`"
- **Impact:** Developers can't easily connect the explanation to the actual generated code they need to modify.

---

### 4. Tooling & Validation Gaps

#### GAP-T1: No Output Validation / Compilation Check
- **Severity:** Critical
- **Phase:** Post-Phase 4
- **Current State:** The converter generates Swift files but never validates that they compile. There is no:
  - Swift syntax checking (`swiftc -typecheck`)
  - Import resolution verification (does `import SwiftUI` resolve?)
  - Cross-file reference validation (does `UserCardView` actually exist when referenced?)
  - Build simulation with Xcode's command-line tools (`xcodebuild`)
- **Impact:** The converter can produce invalid Swift and report success. The developer only discovers problems when they open Xcode, which may be their first experience with the IDE — a terrible first impression.
- **Why This Matters for iOS:** `tsc --noEmit` checks TypeScript without building. `swiftc -typecheck` does the same for Swift. Adding this step would catch many of the gaps listed above before the developer sees them.

#### GAP-T2: No Test Generation
- **Severity:** Critical
- **Phase:** Phase 4 (Assembler)
- **Current State:** The assembler generates no test files at all. Missing:
  - `XCTest` unit test stubs for ViewModels and Services
  - SwiftUI preview tests
  - Snapshot tests for views
  - A test target in the project configuration
- **Impact:** The generated project has zero test infrastructure. Web developers accustomed to Jest/Vitest have no testing entry point.
- **Why This Matters for iOS:** Apple's testing framework (`XCTest`) is integrated into Xcode. Test stubs for generated ViewModels would give developers a starting point for validation and help them learn the iOS testing approach.

#### GAP-T3: No Incremental / Watch Mode Conversion
- **Severity:** Major
- **Phase:** CLI (`converter/run.py`)
- **Current State:** The converter runs as a one-shot batch process. Every run re-analyzes and re-generates everything. No support for:
  - Watching source files for changes and re-converting only modified files
  - Incremental conversion (only process files that changed since last run)
  - Diff output showing what changed between conversion runs
- **Impact:** Iteration is slow — the developer must re-run the full pipeline after every source change.

#### GAP-T4: No Conversion Confidence Scoring in Output
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter) + Phase 4 (Assembler)
- **Current State:** The migration plan assigns difficulty levels (auto/assisted/manual) per pattern, but the generated Swift files don't include a per-file confidence score. The developer can't easily see:
  - Which files are high-confidence (safe to use as-is)
  - Which files need moderate review
  - Which files are essentially stubs requiring manual rewriting
- **Impact:** Developers spend equal time reviewing high-confidence and low-confidence files. A scoring system would help them prioritize.

#### GAP-T5: No Self-Tests for the Converter Itself
- **Severity:** Minor
- **Phase:** Development tooling
- **Current State:** The converter has no unit tests, no integration tests, and no regression tests. The test fixture (`test-fixtures/sample-app/`) is manually inspected. This means:
  - Bug fixes can introduce regressions without detection
  - New pattern detectors can't be validated against known inputs
  - Refactoring is risky without a safety net

---

### 5. Framework & Language Support Gaps

#### GAP-F1: No Next.js-Specific Handling
- **Severity:** Critical
- **Phase:** Phase 1 (Analyzer) + Phase 3 (Rewriter)
- **Current State:** Next.js is the most popular React framework, but the converter doesn't handle:
  - `getServerSideProps` / `getStaticProps` → should map to `.task { }` data fetching
  - `getStaticPaths` → should generate data provider patterns
  - API routes (`pages/api/` or `app/api/`) → should be flagged as server-only (no iOS equivalent)
  - `next/image` → should map to `AsyncImage`
  - `next/link` → should map to `NavigationLink`
  - `next/router` → should map to `NavigationPath`
  - Server Components vs Client Components → the `'use client'` directive should inform conversion strategy
  - Middleware → should be flagged as server-only
  - `next/head` → should map to `Info.plist` or `.navigationTitle()`
- **Impact:** Next.js projects are the most common input, but Next.js-specific patterns produce the worst output.

#### GAP-F2: No State Management Library Conversion
- **Severity:** Major
- **Phase:** Phase 3 (Rewriter)
- **Current State:** Zustand, Redux, Jotai, and Recoil are detected in Phase 1 but not converted in Phase 3. No converter exists for:
  - Zustand stores → `@Observable` classes
  - Redux slices → `@Observable` ViewModel with action methods
  - Jotai atoms → `@State` or `@AppStorage`
  - React Context providers → `@Environment` with custom keys
- **Impact:** Any app using external state management (most production apps) gets zero conversion for its state layer.

#### GAP-F3: No Form Library Handling
- **Severity:** Major
- **Phase:** Phase 1 (Analyzer) + Phase 3 (Rewriter)
- **Current State:** No detection or conversion for:
  - React Hook Form → SwiftUI `Form` + `@State` bindings
  - Formik → same mapping
  - Yup/Zod validation schemas → Swift validation logic
  - `<select>` already maps to `EmptyView()` (acknowledged in the code)
  - Date/time pickers → `DatePicker`
  - Toggle/switch → `Toggle`
  - Slider/range → `Slider`
- **Impact:** Form-heavy apps (admin panels, settings screens, data entry) get minimal conversion.

#### GAP-F4: No CSS-in-JS Library Support
- **Severity:** Minor
- **Phase:** Phase 1 (Analyzer) + Phase 3 (Rewriter)
- **Current State:** Tailwind is well-supported (50+ mappings). styled-components and CSS Modules are detected but not converted. Missing:
  - Emotion → SwiftUI modifiers
  - Chakra UI / Material UI component → SwiftUI equivalent component mapping
  - Sass/LESS variables → Color/Font constants
  - CSS custom properties (`var(--x)`) → SwiftUI `@Environment` or named colors
  - Media queries → `@Environment(\.horizontalSizeClass)` or GeometryReader

---

## Part 2: Build Guide

Remediation steps ordered by impact. Each section includes the root cause, implementation approach, technical considerations, and the educational rationale.

---

### BUILD-1: Add Lightweight AST Support (Addresses GAP-P1)

**Root Cause:** Regex cannot handle recursive structures (nested brackets, nested JSX, scope-aware variable resolution). Every new edge case requires a new regex special case, creating a maintenance burden.

**Implementation Approach:**

1. **Add `tree-sitter` Python bindings** as a dependency:
   ```bash
   pip install tree-sitter tree-sitter-typescript tree-sitter-tsx
   ```

2. **Create `converter/parser/ts_parser.py`** wrapping tree-sitter:
   ```python
   from tree_sitter import Language, Parser
   
   class TSParser:
       """Lightweight TypeScript/TSX AST parser using tree-sitter."""
       
       def __init__(self):
           self.parser = Parser()
           # Load TypeScript and TSX grammars
           
       def parse(self, source: str) -> 'Tree':
           return self.parser.parse(source.encode())
       
       def extract_components(self, tree) -> list[dict]:
           """Walk AST to find function/arrow components."""
           
       def extract_jsx_tree(self, node) -> dict:
           """Convert JSX AST subtree to structured dict."""
           
       def extract_type_annotations(self, node) -> dict:
           """Extract full type information from AST nodes."""
   ```

3. **Gradually migrate converters** from regex to AST queries:
   - Start with `component_converter.py` — it has the most regex complexity
   - Keep regex-based detectors in `patterns.py` as a fast-path fallback
   - Use AST for structural extraction (component bodies, JSX trees), regex for simple pattern matching (hook names, import paths)

4. **Keep the fallback chain:** AST parse → regex fallback → manifest stub. Never break existing functionality.

**Technical Considerations:**
- `tree-sitter` is a C library with Python bindings — fast and mature
- It handles JSX, TypeScript, and TSX natively
- AST nodes include line/column info for accurate source mapping
- The grammar files are ~200KB each — minimal size overhead

**Educational Value:** Understanding *why* the tool uses AST parsing teaches developers about the difference between textual transformation and structural transformation — the same principle that separates template-string HTML from React's virtual DOM.

---

### BUILD-2: Build Import Dependency Graph (Addresses GAP-P2)

**Root Cause:** Files are processed in isolation without knowledge of what types, components, or utilities they import from other files in the project.

**Implementation Approach:**

1. **Add `converter/analyzer/dependency_graph.py`:**
   ```python
   @dataclass
   class ImportEdge:
       source_file: str       # importing file
       target_file: str       # imported file (resolved path)
       imported_names: list[str]  # what's imported
   
   class DependencyGraph:
       def __init__(self, manifest: dict, source_files: dict[str, str]):
           self.edges: list[ImportEdge] = []
           self.type_registry: dict[str, dict] = {}  # name -> {file, shape}
           self._build(manifest, source_files)
       
       def _build(self, manifest, source_files):
           # 1. Collect all exports from each file
           # 2. Resolve import paths to actual files
           # 3. Build edges
           # 4. Populate type_registry with interface shapes
       
       def get_type_shape(self, name: str) -> dict | None:
           """Look up a type's fields by name."""
       
       def get_conversion_order(self) -> list[str]:
           """Topological sort — types first, then services, then views."""
       
       def get_imports_for(self, file_path: str) -> list[ImportEdge]:
           """What does this file import?"""
   ```

2. **Integrate with Phase 3 engine** — pass the dependency graph to each converter so it can resolve cross-file types.

3. **Use conversion order** from topological sort in `rewrite_project()` instead of manifest iteration order. Types first, then services, then hooks/ViewModels, then components.

**Technical Considerations:**
- Path resolution needs to handle: relative paths (`./types`), barrel imports (`/index`), alias paths (`@/components`), and extension inference (`.ts`, `.tsx`, `.js`)
- For monorepos, resolution must respect `tsconfig.json` paths if present
- The graph enables future optimizations: parallel conversion of independent subgraphs

**Educational Value:** The learning notes should explain Swift's module system and access control (`public`, `internal`, `private`, `fileprivate`) — the iOS equivalent of ES module exports. This is a natural place to teach developers about Swift's stricter visibility model.

---

### BUILD-3: Generate Xcode Project or SPM Executable Package (Addresses GAP-I1)

**Root Cause:** Generated files are not organized into a buildable project. The developer must manually create the Xcode project.

**Implementation Approach:**

The simplest approach is generating a **Swift Package Manager executable** — this requires no `.xcodeproj` and Xcode can open `Package.swift` directly.

1. **Modify `config_generator.py`** to generate `Package.swift` as an executable target:
   ```swift
   // Package.swift
   // swift-tools-version: 5.9
   import PackageDescription
   
   let package = Package(
       name: "MyApp",
       platforms: [.iOS(.v17)],
       products: [
           .library(name: "MyApp", targets: ["MyApp"]),
       ],
       dependencies: [
           // SPM dependencies from npm mapping
       ],
       targets: [
           .target(
               name: "MyApp",
               dependencies: [...],
               path: "Sources"
           ),
           .testTarget(
               name: "MyAppTests",
               dependencies: ["MyApp"],
               path: "Tests"
           ),
       ]
   )
   ```

2. **Restructure output directory** to match SPM layout:
   ```
   MyApp/
   ├── Package.swift
   ├── Sources/
   │   └── MyApp/
   │       ├── App/
   │       ├── Views/
   │       ├── ViewModels/
   │       ├── Models/
   │       ├── Services/
   │       └── Resources/
   └── Tests/
       └── MyAppTests/
   ```

3. **Generate an `.xcodeproj`** as a secondary option using `xcodegen` (YAML-based Xcode project generator):
   - Add `project.yml` generation to the assembler
   - Run `xcodegen generate` if available on the system

**Technical Considerations:**
- SPM executable packages are the simplest path — `Package.swift` is already being generated
- The current output structure needs `Sources/` wrapping
- Xcode opens `Package.swift` directly via File → Open
- Resource files need `Bundle.module` access pattern in SPM

**Educational Value:** Explain *why* iOS projects need build configuration that web projects don't: code signing, provisioning profiles, entitlements, and device targeting are all concepts that don't exist on the web. The learning notes should include a "Your First Build" walkthrough.

---

### BUILD-4: Generate Info.plist from Detected Patterns (Addresses GAP-I2)

**Root Cause:** iOS apps require `Info.plist` for system integration. The assembler has the information to generate it (detected Web APIs, env vars) but doesn't.

**Implementation Approach:**

1. **Add `converter/assembler/plist_generator.py`:**
   ```python
   def generate_info_plist(app_name: str, manifest: dict, env_vars: list) -> str:
       """Generate Info.plist from detected patterns."""
       plist = {
           "CFBundleName": app_name,
           "CFBundleIdentifier": f"com.example.{app_name.lower()}",
           "CFBundleVersion": "1.0",
           "CFBundleShortVersionString": "1.0.0",
           "UILaunchScreen": {},
       }
       
       # Detect required privacy descriptions from patterns
       patterns = collect_all_patterns(manifest)
       
       if has_pattern(patterns, "Geolocation"):
           plist["NSLocationWhenInUseUsageDescription"] = \
               "This app needs your location to provide nearby results."
       
       if has_pattern(patterns, "MediaDevices"):
           plist["NSCameraUsageDescription"] = \
               "This app needs camera access for photos."
           plist["NSMicrophoneUsageDescription"] = \
               "This app needs microphone access for audio."
       
       if has_pattern(patterns, "Web Notifications"):
           # No plist key needed — handled via UNUserNotificationCenter
           pass
       
       # ... more pattern-to-plist mappings
       
       return serialize_plist(plist)
   ```

2. **Map detected Web APIs to required permissions:**

   | Web API | Info.plist Key | Description Template |
   |---|---|---|
   | `navigator.geolocation` | `NSLocationWhenInUseUsageDescription` | Location access for nearby features |
   | `navigator.mediaDevices` | `NSCameraUsageDescription` + `NSMicrophoneUsageDescription` | Camera/mic for media capture |
   | `navigator.clipboard` | — (no plist needed) | UIPasteboard is unrestricted |
   | `navigator.share` | — (no plist needed) | UIActivityViewController is unrestricted |
   | `Notification.requestPermission` | — (runtime permission) | UNUserNotificationCenter handles this |

3. **Generate ATS exceptions** if HTTP (non-HTTPS) URLs are detected in API call patterns.

**Educational Value:** Add a learning annotation explaining iOS's permission model — why apps must declare permissions in advance, why the description strings matter (they're shown to the user), and how this differs from the web's just-in-time permission prompts.

---

### BUILD-5: Add Accessibility Modifier Generation (Addresses GAP-I3)

**Root Cause:** The JSX-to-SwiftUI converter strips HTML attributes that aren't recognized, including `aria-*` and `role` attributes.

**Implementation Approach:**

1. **Extend `_extract_component_props()` and `extract_attr()`** to capture accessibility-related attributes:
   ```python
   ARIA_TO_SWIFTUI = {
       "aria-label": lambda v: f'.accessibilityLabel("{v}")',
       "aria-hidden": lambda v: ".accessibilityHidden(true)" if v == "true" else "",
       "aria-describedby": lambda v: f'.accessibilityHint("{v}")',
       "aria-live": lambda v: "",  # No direct equivalent, add TODO
       "role": lambda v: _map_role(v),
       "alt": lambda v: f'.accessibilityLabel("{v}")',
       "title": lambda v: f'.accessibilityLabel("{v}")',
   }
   
   def _map_role(role: str) -> str:
       role_map = {
           "button": '.accessibilityAddTraits(.isButton)',
           "link": '.accessibilityAddTraits(.isLink)',
           "heading": '.accessibilityAddTraits(.isHeader)',
           "img": '.accessibilityAddTraits(.isImage)',
           "tab": '.accessibilityAddTraits(.isSelected)',
       }
       return role_map.get(role, f'// TODO: Map role="{role}" to accessibility trait')
   ```

2. **Add accessibility modifiers to generated views** — append them to the modifier chain after visual modifiers.

3. **Add `alt` text extraction from `<img>` tags** → `.accessibilityLabel()` on `AsyncImage` / `Image`.

**Educational Value:** Add a learning annotation on iOS accessibility — explain VoiceOver, Dynamic Type, and why Apple treats accessibility as a core feature rather than an add-on. Include Apple's Accessibility Programming Guide link.

---

### BUILD-6: Expand useEffect Conversion Logic (Addresses GAP-P6)

**Root Cause:** `useEffect` is one of the most complex React patterns to convert because its behavior depends on the dependency array, and SwiftUI has three different modifiers (`.task`, `.onAppear`, `.onChange`) that each cover a subset of `useEffect` use cases.

**Implementation Approach:**

1. **Add `useEffect` body extraction** to `component_converter.py`:
   ```python
   def extract_use_effects(body: str) -> list[dict]:
       """Extract useEffect calls with their bodies and dependencies."""
       effects = []
       # Find useEffect( with balanced paren tracking
       # Extract:
       #   - callback body
       #   - cleanup function (return () => { ... })
       #   - dependency array contents
       
       # Classify each effect:
       # - [] deps → .task { } (run once on appear)
       # - [dep1, dep2] → .onChange(of: dep1) { } + .onChange(of: dep2) { }
       # - no deps → .onAppear { } (run every render — rare, usually a mistake)
       # - cleanup → .onDisappear { } or Task cancellation
       
       return effects
   ```

2. **Generate the appropriate SwiftUI modifier:**
   ```swift
   // useEffect(() => { fetchUser(id) }, [id])
   // →
   .task(id: id) {
       await fetchUser(id: id)
   }
   
   // useEffect(() => { ... return () => cleanup() }, [])
   // →
   .task {
       // ... effect body
   }
   .onDisappear {
       // cleanup()
   }
   ```

3. **Add to the learning annotations** a detailed comparison table:

   | useEffect Pattern | SwiftUI Equivalent | When to Use |
   |---|---|---|
   | `useEffect(() => {}, [])` | `.task { }` | One-time async work on appear |
   | `useEffect(() => {}, [dep])` | `.task(id: dep) { }` or `.onChange(of: dep) { }` | React to value changes |
   | `useEffect(() => { return cleanup })` | `.onDisappear { }` + Task cancellation | Cleanup resources |
   | No dependency array | `.onAppear { }` (caution) | Every appearance — usually wrong |

**Educational Value:** This is one of the highest-value learning moments. `useEffect` is notoriously confusing even in React. Showing developers that SwiftUI splits it into three purpose-specific modifiers — each with clear semantics — demonstrates Apple's "explicit over implicit" philosophy.

---

### BUILD-7: Add Next.js-Specific Analyzer and Converter (Addresses GAP-F1)

**Root Cause:** Next.js is the most common React framework but its patterns (SSR, API routes, file-based routing, server components) don't map 1:1 to any existing converter.

**Implementation Approach:**

1. **Add `converter/analyzer/nextjs_detector.py`:**
   ```python
   def detect_nextjs_patterns(content: str, file_path: str) -> list[DetectedPattern]:
       """Detect Next.js-specific patterns."""
       patterns = []
       
       # Server-side data fetching
       if "getServerSideProps" in content:
           patterns.append(DetectedPattern(
               pattern_type="nextjs_ssr",
               name="getServerSideProps",
               line=...,
               details={"ios_equivalent": ".task { } with API call"},
               conversion_difficulty="assisted",
           ))
       
       # API routes (server-only — flag, don't convert)
       if "/api/" in file_path and ("NextApiRequest" in content or "NextResponse" in content):
           patterns.append(DetectedPattern(
               pattern_type="nextjs_api_route",
               name="API Route",
               line=1,
               details={"ios_equivalent": "Server-only — no iOS equivalent. Keep as backend."},
               conversion_difficulty="manual",
           ))
       
       # Server Components ('use client' directive)
       if "'use client'" in content or '"use client"' in content:
           patterns.append(DetectedPattern(
               pattern_type="nextjs_client_component",
               name="Client Component",
               line=1,
               details={"ios_equivalent": "All SwiftUI views are client-side."},
               conversion_difficulty="auto",
           ))
       
       # next/image, next/link, next/router mappings
       # ...
       
       return patterns
   ```

2. **Add Next.js import remapping** in the rewriter:
   - `import Image from 'next/image'` → use `AsyncImage` in generated code
   - `import Link from 'next/link'` → use `NavigationLink`
   - `import { useRouter } from 'next/navigation'` → use `NavigationPath`

3. **Flag server-only code** clearly in the migration plan — these files shouldn't be converted, they should remain as the backend API.

**Educational Value:** Add a learning section explaining the client-server split in iOS development: "Unlike Next.js where your app spans client and server, an iOS app is purely client-side. Your Next.js API routes stay on the server — the iOS app calls them via URLSession, just like your Next.js client components call them via fetch()."

---

### BUILD-8: Add State Management Library Converters (Addresses GAP-F2)

**Root Cause:** Zustand, Redux, and Jotai are detected by the analyzer but no rewriter exists for them.

**Implementation Approach:**

1. **Add `converter/rewriter/state_converter.py`:**

   ```python
   def convert_zustand_store(source: str, store_name: str) -> str:
       """Convert a Zustand store to @Observable class."""
       # Zustand: create((set) => ({ count: 0, increment: () => set(s => ({count: s.count + 1})) }))
       # → @Observable class CountStore { var count = 0; func increment() { count += 1 } }
       
   def convert_redux_slice(source: str, slice_name: str) -> str:
       """Convert a Redux Toolkit slice to @Observable class."""
       # createSlice({ name, initialState, reducers })
       # → @Observable class with state properties and action methods
       
   def convert_context_provider(source: str, context_name: str) -> str:
       """Convert React Context to SwiftUI @Environment."""
       # createContext → EnvironmentKey + EnvironmentValues extension
   ```

2. **Register in engine.py** — add `"state"` to `FILE_TYPE_TO_DIR` and route state files to `state_converter`.

**Educational Value:** Add annotations explaining why SwiftUI doesn't need external state management libraries: `@Observable` + `@Environment` cover most use cases because they're framework-level primitives, not community packages. This is the "batteries included" philosophy in action.

---

### BUILD-9: Add Compilation Validation Step (Addresses GAP-T1)

**Root Cause:** The converter reports success based on whether Python code ran without exceptions, not whether the generated Swift is valid.

**Implementation Approach:**

1. **Add `converter/validator/swift_checker.py`:**
   ```python
   import subprocess
   
   def validate_swift_syntax(file_path: str) -> tuple[bool, list[str]]:
       """Check if a Swift file has valid syntax using swiftc."""
       result = subprocess.run(
           ["swiftc", "-parse", file_path],
           capture_output=True, text=True
       )
       errors = []
       if result.returncode != 0:
           for line in result.stderr.splitlines():
               if "error:" in line:
                   errors.append(line)
       return result.returncode == 0, errors
   
   def validate_project(output_dir: str) -> dict:
       """Validate all generated Swift files."""
       results = {}
       for swift_file in Path(output_dir).rglob("*.swift"):
           valid, errors = validate_swift_syntax(str(swift_file))
           results[str(swift_file)] = {"valid": valid, "errors": errors}
       return results
   ```

2. **Add `--validate` flag** to `run.py` that runs validation after Phase 4.

3. **Generate a validation report** showing which files pass/fail syntax check.

**Technical Considerations:**
- `swiftc` must be available (macOS with Xcode, or Swift toolchain on Linux)
- On Linux (where this tool may run), use the Swift Docker image for validation
- For cross-platform support, make validation optional — skip if `swiftc` is not found
- Even syntax-only checking (`-parse`) catches many issues

**Educational Value:** Explain the difference between Swift's ahead-of-time compilation and TypeScript's type erasure — Swift errors are compile errors that must be fixed before the app can run, unlike TypeScript where you can run despite type errors.

---

### BUILD-10: Generate Test Stubs (Addresses GAP-T2)

**Root Cause:** The assembler generates no test files, leaving developers with no testing entry point.

**Implementation Approach:**

1. **Add `converter/assembler/test_generator.py`:**
   ```python
   def generate_viewmodel_tests(view_models: list[dict]) -> dict[str, str]:
       """Generate XCTest stubs for each ViewModel."""
       tests = {}
       for vm in view_models:
           name = vm["name"]
           test_code = f'''
   import XCTest
   @testable import MyApp
   
   final class {name}Tests: XCTestCase {{
       
       var sut: {name}!  // System Under Test
       
       override func setUp() {{
           super.setUp()
           sut = {name}()
       }}
       
       override func tearDown() {{
           sut = nil
           super.tearDown()
       }}
       
       func testInitialState() {{
           // TODO: Verify initial state matches expectations
           // Example: XCTAssertNil(sut.user)
           // Example: XCTAssertFalse(sut.isLoading)
       }}
       
       func testAsyncDataLoading() async {{
           // TODO: Test async data fetching
           // await sut.fetchData()
           // XCTAssertNotNil(sut.data)
       }}
   }}
   '''
           tests[f"Tests/{name}Tests.swift"] = test_code
       return tests
   ```

2. **Generate service tests** with mock URL protocols for network testing.

3. **Add test target** to `Package.swift` generation.

**Educational Value:** Add a learning annotation on iOS testing — explain `XCTest` vs Jest, `@testable import` vs module boundaries, and why iOS testing emphasizes async testing patterns more than web testing does.

---

### BUILD-11: Expand JSX Element Coverage (Addresses GAP-P4)

**Root Cause:** `process_jsx_element()` handles 15 elements. Real-world apps use 30+.

**Implementation Approach:**

Add handlers to `process_jsx_element()` for the missing elements:

```python
# Tables
elif jsx.startswith("<table"):
    children = extract_jsx_children(jsx)
    lines.append(f"{ind}// TODO: Consider using List or Grid for table data")
    lines.append(f"{ind}VStack(alignment: .leading, spacing: 0) {{")
    for child in children:
        child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
        if child_result.strip():
            lines.append(child_result)
    lines.append(f"{ind}}}")

elif jsx.startswith("<tr"):
    children = extract_jsx_children(jsx)
    lines.append(f"{ind}HStack(spacing: 16) {{")
    for child in children:
        child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
        if child_result.strip():
            lines.append(child_result)
    lines.append(f"{ind}}}")
    lines.append(f"{ind}Divider()")

elif jsx.startswith("<td") or jsx.startswith("<th"):
    text_content = extract_text_content(jsx)
    text_expr = convert_text_expression(text_content, state_names)
    font_mod = ".fontWeight(.bold)" if jsx.startswith("<th") else ""
    lines.append(f"{ind}Text({text_expr})")
    if font_mod:
        lines.append(f"{ind}    {font_mod}")
    lines.append(f"{ind}    .frame(maxWidth: .infinity, alignment: .leading)")

# Semantic HTML
elif jsx.startswith("<nav") or jsx.startswith("<header") or jsx.startswith("<footer"):
    container = "VStack" 
    children = extract_jsx_children(jsx)
    lines.append(f"{ind}{container} {{")
    for child in children:
        child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
        if child_result.strip():
            lines.append(child_result)
    lines.append(f"{ind}}}")

# Media
elif jsx.startswith("<video"):
    src = extract_attr(jsx, "src")
    lines.append(f"{ind}// TODO: Import AVKit")
    lines.append(f'{ind}VideoPlayer(player: AVPlayer(url: URL(string: "{src or ""}")!))')
    lines.append(f"{ind}    .frame(height: 300)")

# Progress
elif jsx.startswith("<progress"):
    value = extract_attr(jsx, "value") or "0.5"
    lines.append(f"{ind}ProgressView(value: {value})")

# Dialog / Modal
elif jsx.startswith("<dialog"):
    children = extract_jsx_children(jsx)
    lines.append(f"{ind}// TODO: Present as .sheet() or .alert()")
    lines.append(f"{ind}{swift_todo('Convert <dialog> to .sheet() modifier')}")
```

**Educational Value:** Each new element mapping is an opportunity to explain the SwiftUI equivalent. Tables → List/Grid teaches data display patterns. Dialog → sheet teaches modal presentation. Video → AVKit teaches the media framework.

---

### BUILD-12: Add Error Handling Patterns (Addresses GAP-I4)

**Root Cause:** Generated async code uses `throws` but never generates the error handling infrastructure.

**Implementation Approach:**

1. **Generate `APIError.swift`** as a scaffold:
   ```swift
   enum APIError: LocalizedError {
       case invalidURL
       case unauthorized
       case notFound
       case serverError(statusCode: Int)
       case decodingFailed(Error)
       case networkUnavailable
       
       var errorDescription: String? {
           switch self {
           case .invalidURL: return "Invalid URL"
           case .unauthorized: return "Please sign in again"
           case .notFound: return "The requested resource was not found"
           case .serverError(let code): return "Server error (\(code))"
           case .decodingFailed: return "Failed to process server response"
           case .networkUnavailable: return "No internet connection"
           }
       }
   }
   ```

2. **Generate `LoadState<T>` enum** for ViewModel state:
   ```swift
   enum LoadState<T> {
       case idle
       case loading
       case loaded(T)
       case error(Error)
       
       var isLoading: Bool { if case .loading = self { return true }; return false }
       var value: T? { if case .loaded(let v) = self { return v }; return nil }
       var error: Error? { if case .error(let e) = self { return e }; return nil }
   }
   ```

3. **Modify `hook_converter.py`** to wrap async operations in do/catch:
   ```swift
   func fetchUser() async {
       state = .loading
       do {
           let user = try await APIClient.shared.request(...)
           state = .loaded(user)
       } catch {
           state = .error(error)
       }
   }
   ```

**Educational Value:** Add a learning annotation on Swift's error handling — explain `throws`/`try`/`catch` vs JavaScript's `try`/`catch`/`.catch()`, and why Swift makes error handling explicit and exhaustive.

---

### BUILD-13: Expand Learning Annotations Database (Addresses GAP-E2 + GAP-E3)

**Root Cause:** The annotation database covers 18 concepts but misses anti-patterns and several critical iOS topics.

**Implementation Approach:**

Add these annotations to `converter/learning/annotations.py`:

```python
# Anti-patterns (GAP-E2)
"antipattern_any_view": {
    "title": "Don't Use AnyView Everywhere",
    "short": "AnyView erases type information SwiftUI needs for efficient diffing.",
    "detail": "Web developers sometimes wrap views in AnyView to 'make types work.' "
              "This is like wrapping everything in React.Fragment — it works but kills "
              "performance. SwiftUI uses view types for its diffing algorithm. AnyView "
              "forces runtime type checks instead of compile-time optimization. Use "
              "@ViewBuilder or generic constraints instead.",
    "web_analogy": "Like using 'any' type in TypeScript — it compiles but defeats the purpose.",
},

"antipattern_force_unwrap": {
    "title": "Never Force-Unwrap in Production Code",
    "short": "The ! operator crashes your app if the value is nil — use if let or guard.",
    ...
},

"antipattern_body_logic": {
    "title": "Keep var body Simple — No Heavy Logic",
    "short": "body is called on every state change. Move logic to methods or computed props.",
    ...
},

# Missing concepts (GAP-E3)
"app_lifecycle": {
    "title": "Why App Lifecycle Matters More on Mobile",
    "short": "iOS can suspend or terminate your app at any time — save state proactively.",
    "detail": "Web apps run until the user closes the tab. iOS apps move through states: "
              "active → inactive → background → suspended → terminated. The OS can kill "
              "your app in the background to reclaim memory — without warning. You must "
              "save state in .onChange(of: scenePhase) and restore it on launch.",
    "web_analogy": "Like the Page Visibility API, but the OS can kill your 'tab' entirely.",
},

"memory_management_arc": {
    "title": "Why Swift Uses ARC Instead of Garbage Collection",
    "short": "ARC is deterministic — objects are freed immediately when no longer referenced.",
    ...
},

"swiftui_layout_system": {
    "title": "How SwiftUI Layout Differs from CSS",
    "short": "SwiftUI negotiates size between parent and child — no box model, no flow.",
    "detail": "CSS uses a box model with flow, flexbox, and grid. SwiftUI uses a "
              "three-step negotiation: parent proposes a size, child chooses its size, "
              "parent places the child. There's no margin (use padding on parent), no "
              "float, no position:absolute. GeometryReader gives you the parent's size "
              "but should be used sparingly.",
    "web_analogy": "Like flexbox where every child tells its parent exactly how big it wants to be.",
},

"binding_property_wrapper": {
    "title": "Why @Binding for Two-Way Data Flow",
    "short": "@Binding creates a reference to a parent's @State — the child can read AND write.",
    ...
},

"sheet_presentation": {
    "title": "Why .sheet() Instead of Modal Components",
    "short": "iOS manages modal presentation at the system level — sheets, alerts, popovers.",
    ...
},
```

**Educational Value:** Anti-pattern annotations directly prevent the most common mistakes web developers make when writing their first iOS code. These are more valuable than concept explanations because they prevent wasted debugging time.

---

### BUILD-14: Add Per-File Confidence Score (Addresses GAP-T4)

**Root Cause:** Developers can't quickly assess which generated files are ready to use vs which need significant manual work.

**Implementation Approach:**

1. **Add scoring to `RewriteResult`:**
   ```python
   @dataclass
   class RewriteResult:
       # ... existing fields
       confidence_score: float = 0.0  # 0.0 to 1.0
       confidence_breakdown: dict = field(default_factory=dict)
   ```

2. **Calculate score based on:**
   - Number of TODO comments in output (each reduces score by 0.05)
   - Number of `EmptyView()` fallbacks (each reduces by 0.1)
   - Number of `Any` type fallbacks (each reduces by 0.03)
   - Whether the file uses AST (if available) vs regex fallback
   - Pattern conversion_difficulty distribution (auto=+, assisted=0, manual=-)

3. **Include in generation summary:**
   ```markdown
   ## Conversion Confidence
   
   | File | Confidence | Issues |
   |---|---|---|
   | Views/UserCardView.swift | 🟢 87% | 2 TODOs, 1 type inference |
   | ViewModels/AuthViewModel.swift | 🟡 62% | 5 TODOs, manual handler ports |
   | Views/DashboardView.swift | 🔴 31% | 12 TODOs, 3 EmptyView stubs |
   ```

---

### BUILD-15: Add React Fragment and Portal Handling (Addresses GAP-P5)

**Implementation Approach:**

Add to `process_jsx_element()`:

```python
# React Fragment: <> ... </> or <React.Fragment>
elif jsx.startswith("<>") or jsx.startswith("<React.Fragment"):
    children = extract_jsx_children(jsx)
    if len(children) == 1:
        # Single child — unwrap the fragment
        lines.append(process_jsx_element(children[0], state_names, setters, indent_level))
    else:
        lines.append(f"{ind}Group {{")
        for child in children:
            child_result = process_jsx_element(child, state_names, setters, indent_level + 1)
            if child_result.strip():
                lines.append(child_result)
        lines.append(f"{ind}}}")
```

Update `extract_jsx_children()` to handle fragment closing tags (`</>`, `</React.Fragment>`).

---

## Part 3: Priority Roadmap

Based on impact, difficulty, and dependency ordering. **All 15 BUILD-* items
shipped 2026-04-25 → 2026-05-04**; the active roadmap is now the GitHub
round-trip wrapper (see `plans/github-round-trip.md`).

### Phase A — Foundation (Unblocks Everything Else) — ✅ delivered
1. ✅ **BUILD-2** — Import dependency graph (enables cross-file type resolution)
2. ✅ **BUILD-1** — Lightweight AST support (fixes the regex ceiling)
3. ✅ **BUILD-9** — Compilation validation (catches issues early)

### Phase B — iOS Project Viability — ✅ delivered
4. ✅ **BUILD-3** — Xcode project / SPM package generation
5. ✅ **BUILD-4** — Info.plist generation
6. ✅ **BUILD-12** — Error handling patterns

### Phase C — Real-World App Support — ✅ delivered
7. ✅ **BUILD-7** — Next.js-specific handling
8. ✅ **BUILD-6** — useEffect conversion expansion
9. ✅ **BUILD-8** — State management library converters
10. ✅ **BUILD-11** — Expanded JSX element coverage

### Phase D — Quality & Education — ✅ delivered
11. ✅ **BUILD-13** — Expanded learning annotations + anti-patterns
12. ✅ **BUILD-5** — Accessibility modifiers
13. ✅ **BUILD-10** — Test stub generation
14. ✅ **BUILD-14** — Per-file confidence scoring
15. ✅ **BUILD-15** — React fragments and portals

### Next: Wrapper / GitHub round-trip
- ✅ Phase 1 — local convert (`python -m wrapper convert <path>`)
- ✅ Phase 2 — clone + convert + local branch with `Requires-more-review/`
  prefix, revision counter, and update-notes diff
- ⏳ Phase 3 — push the conversion branch to GitHub
- ⏳ Phase 4 — first-class monorepo discovery (auto-detect `apps/mobile` etc.)
- ⏳ Phase 5 — hosted service wrapping the CLI (paid product)

---

## Appendix A: Current Capability Matrix

> **Last refreshed:** 2026-05-04 — after Phase A–D BUILD-1…15 delivery and the
> first GitHub round-trip integration test against `the-survival-bible`.

| Capability | Status | Coverage | Notes |
|---|---|---|---|
| Component detection | ✅ Working | ~90% | Misses HOCs, forwardRef |
| Hook detection | ✅ Working | ~85% | All built-in + custom hooks |
| State management detection | ✅ Working | ~75% | Detects + basic Redux/Zustand converters (BUILD-8) |
| API call detection | ✅ Working | ~80% | fetch, axios, generic patterns |
| Routing detection | ✅ Working | ~75% | React Router, Next.js |
| Style detection | ✅ Working | ~70% | Tailwind, CSS Modules, styled |
| Type conversion | ✅ Working | ~80% | Simple types, basic generics |
| Component → View | ✅ Working | ~80% | 30+ elements covered (BUILD-11), fragments/portals (BUILD-15) |
| Hook → ViewModel | ⚠️ Partial | ~70% | useEffect/useMemo/useRef expanded (BUILD-6); logic still stubbed |
| Service → Service | ✅ Working | ~80% | Async + structured error handling (BUILD-12) |
| Project assembly | ✅ Working | ~85% | SPM `Package.swift` + xcodegen `project.yml` + `Info.plist` (BUILD-3, BUILD-4) |
| Learning system | ✅ Working | ~85% | 34 annotations incl. anti-patterns (BUILD-13) |
| Validation | ✅ Working | ~75% | Pattern lint + per-file confidence; swiftc-parse when toolchain present (BUILD-9, BUILD-14) |
| Testing | ✅ Working | ~70% | Per-ViewModel + per-service XCTest stubs with MockURLProtocol (BUILD-10) |
| Next.js support | ⚠️ Partial | ~50% | Detector + image/head/lazy/styling translators (BUILD-7); SSR still flagged manual |
| Accessibility | ✅ Working | ~75% | ARIA → SwiftUI a11y modifiers (BUILD-5) |
| GitHub round-trip wrapper | ✅ Working (Phase 2) | clone + convert + local branch with revisions and update-notes; push pending Phase 3 |

### Real-world validation (2026-05-04)

Pointed the wrapper at [`the-survival-bible`](https://github.com/jjdcodingcollective-collab/the-survival-bible)
monorepo via `--source-subdir apps/mobile`. Result:

| Metric | Value |
|---|---|
| Files converted | 42 |
| Files passing structural validation | 50 / 50 |
| Validation errors | 0 |
| Average confidence | 52% (run-level) / 66% (validator-level) |
| Confidence bands | 13 HIGH / 13 MEDIUM / 16 LOW |

Bug fixes that emerged from this run:

- Arrow-function leak (3 paths in `component_converter.py`): JSX prop callbacks
  like `style={({pressed}) => [...]}` and `renderItem={({item}) => ...}` no
  longer leak `=>` into Swift output. The `&&` and Text-content branches now
  reject `=>` early, and the post-processor's leaked-callback detector accepts
  any param shape (not just `() =>`).

## Appendix B: File Reference

| Gap ID | Primary Files Affected |
|---|---|
| GAP-P1 | `converter/rewriter/component_converter.py`, `converter/analyzer/patterns.py` |
| GAP-P2 | `converter/rewriter/engine.py:49-105` |
| GAP-P3 | `converter/rewriter/swift_helpers.py:96-178` |
| GAP-P4 | `converter/rewriter/component_converter.py:467-738` |
| GAP-P5 | `converter/rewriter/component_converter.py:467-478` |
| GAP-P6 | `converter/rewriter/component_converter.py:207-241` |
| GAP-P7 | `converter/rewriter/component_converter.py:963-1012` |
| GAP-P8 | `converter/rewriter/component_converter.py:61-107` |
| GAP-P9 | `converter/rewriter/component_converter.py:1466-1493` |
| GAP-I1 | `converter/assembler/project_assembler.py`, `converter/assembler/config_generator.py` |
| GAP-I2 | `converter/assembler/project_assembler.py` (new file needed) |
| GAP-I3 | `converter/rewriter/component_converter.py:467-738` |
| GAP-I4 | `converter/rewriter/service_converter.py`, `converter/rewriter/hook_converter.py` |
| GAP-I5 | `converter/assembler/project_assembler.py:137-152` |
| GAP-I6 | `converter/reviewer/migration_planner.py:41-148` |
| GAP-I7 | `converter/rewriter/hook_converter.py`, `converter/rewriter/service_converter.py` |
| GAP-I8 | `converter/reviewer/migration_planner.py`, `converter/assembler/entry_point.py` |
| GAP-E1 | `converter/learning/notes_generator.py` |
| GAP-E2 | `converter/learning/annotations.py` |
| GAP-E3 | `converter/learning/annotations.py:15-322` |
| GAP-E4 | `converter/assembler/project_assembler.py`, `docs/` |
| GAP-E5 | `docs/` |
| GAP-E6 | `converter/learning/notes_generator.py:16-120` |
| GAP-T1 | New: `converter/validator/swift_checker.py` |
| GAP-T2 | New: `converter/assembler/test_generator.py` |
| GAP-T3 | `converter/run.py` |
| GAP-T4 | `converter/rewriter/engine.py` |
| GAP-T5 | New: `tests/` directory |
| GAP-F1 | `converter/analyzer/patterns.py`, new: `converter/analyzer/nextjs_detector.py` |
| GAP-F2 | New: `converter/rewriter/state_converter.py` |
| GAP-F3 | `converter/analyzer/patterns.py`, `converter/rewriter/component_converter.py` |
| GAP-F4 | `converter/rewriter/component_converter.py:1218-1256` |

---

*Generated by iOS Agent Gap Analysis — 2026-04-25*
