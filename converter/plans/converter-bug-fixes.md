# Plan: Converter Bug Fix Build Guide

## Summary
Fix all 12 open issues found testing against real-world projects. Ordered by priority — critical issues first (output won't compile), then major (compiles but wrong), then minor (style/idiom).

---

## Critical Fixes (Output Won't Compile)

### Fix #1: `.map()/.filter()` -> ForEach Conversion
**File:** `rewriter/component_converter.py` — `process_jsx_element()`
**Problem:** `{items.map(item => <Card .../>)}` produces raw JS in Swift output.
**Solution:** In the `{expression}` handler, detect `.map(` patterns before `&&`/ternary checks. Parse collection, iterator variable, and callback body. Generate `ForEach(collection, id: \.self) { item in ... }`. Also handle `.filter(...).map(...)` chains.
**Impact:** Fixes nearly every list-based screen.

### Fix #2: Complex Nested Conditional Rendering
**File:** `rewriter/component_converter.py` — `process_jsx_element()`
**Problem:** `inner.split("?", 1)` breaks on optional chaining (`user?.name`) and nested ternaries.
**Solution:** Replace naive string splitting with depth-aware ternary parsing that tracks `<>`, `()`, `{}` depth to find the correct `?` and `:` operators.
**Impact:** Fixes multi-branch JSX in complex components.

### Fix #3: Cross-File Component References
**File:** `rewriter/component_converter.py` — `process_jsx_element()` else block
**Problem:** `<CardViewer card={card} />` produces `EmptyView()` instead of `CardViewerView(card: card)`.
**Solution:** When the JSX tag is PascalCase, treat it as a custom component reference. Extract props from attributes, generate proper Swift view initializer call with mapped prop values.
**Impact:** Fixes component composition across all files.

---

## Major Fixes (Compiles But Wrong)

### Fix #4: Inline CSS `style={{}}` Conversion
**File:** `rewriter/component_converter.py` — new `extract_inline_style_modifiers()`
**Problem:** Components using `style={{ color: 'red', padding: 10 }}` get styling dropped.
**Solution:** Add CSS-to-SwiftUI property mapping. Extract `style={{...}}` objects, parse key-value pairs, map common CSS properties (color, padding, margin, fontSize, etc.) to SwiftUI modifiers.
**Impact:** Restores styling for non-Tailwind components.

### Fix #5+7: Reduce `Any` Fallback + Event Handler Types
**File:** `rewriter/swift_helpers.py` — `TS_TO_SWIFT_TYPES`, `map_type()`
**Problem:** Too many types default to `Any`. React event types map to `Any` instead of proper SwiftUI callbacks.
**Solution:** Add mappings for React event types to SwiftUI equivalents. Improve `map_type` to handle camelCase type names, tuple types, and function types. Add type inference from common variable name patterns.
**Impact:** Restores type safety in ~18 instances.

### Fix #6: Optional `?` Suffix on @State
**File:** `rewriter/hook_converter.py` — `convert_state_init()`
**Problem:** Some `@State` properties initialized with `nil` don't get the `?` suffix.
**Solution:** Ensure all code paths that produce `nil` initial values append `?` to the type. Also fix the component_converter's `extract_use_state_from_body()` for consistency.
**Impact:** Fixes compile errors on nil-initialized state.

### Fix #8: Unresolved Variables from Hooks/Computed
**File:** `rewriter/component_converter.py` — `convert_component()`
**Problem:** Variables from `useParams()`, `useLocation()`, and computed `const` values aren't declared in the generated view.
**Solution:** After useState extraction, also extract: useParams → let declarations, useLocation → let declarations, const computations → computed properties or lets.
**Impact:** Fixes undefined variable references in view bodies.

---

## Minor Fixes (Style/Idiom)

### Fix #9: Excessive TODO Density
**File:** `rewriter/component_converter.py` — `_cleanup_swift_output()`
**Problem:** Complex screens generate 20-30+ TODOs creating noise.
**Solution:** Post-process to collapse consecutive TODO comments into grouped summary. Cap at 5 TODOs per section with a "and N more..." note.
**Impact:** Cleaner, more readable output.

### Fix #10: Empty VStack Wrappers
**File:** `rewriter/component_converter.py` — `process_jsx_element()`
**Problem:** `<div>` with only CSS styling (no Tailwind) produces empty `VStack {}`.
**Solution:** After processing children, check if VStack body is empty. If so, only emit modifiers or skip entirely.
**Impact:** Eliminates dead code in output.

### Fix #11: Preview Initializer Mismatches
**File:** `rewriter/component_converter.py` — `generate_preview()`
**Problem:** Preview uses `children` but struct has `content` (from children -> AnyView conversion).
**Solution:** In preview generation, apply the same prop name transformations used in `convert_prop()`. Skip `children`/`content` props (can't easily preview AnyView).
**Impact:** Previews compile and render correctly.

### Fix #12: Monorepo Awareness
**File:** `rewriter/analyzer/scanner.py` — `scan_project()`
**Problem:** Scanner doesn't understand `apps/`, `packages/` monorepo structures.
**Solution:** Add `detect_monorepo()` that checks for common monorepo markers (turbo.json, pnpm-workspace.yaml, lerna.json). When detected, return available subdirectories for user selection. Add auto-detection of the main app directory.
**Impact:** Users don't need to manually find the right subdirectory.
