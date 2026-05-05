# ADR 0001: Tooling Stack

- **Status:** Accepted
- **Date:** 2026-05-05
- **Deciders:** Product / Tech Lead
- **Supersedes:** —
- **Superseded by:** —

---

## Context

The MVP scope is web codebase → Wrap mode (Capacitor-based WKWebView host) per `docs/mvp-scope.md`. Phase 2+ extends to logic-only transpilation of Kotlin/Java, then Bridge, Port, and TS/Python.

Multiple layers of the build need third-party tooling: source-side AST parsing, Swift-side AST manipulation, Xcode project generation, the WebView host itself, static analysis, and (deferred) JVM-language transpilation. Without a binding decision, contributors will reinvent components that mature open-source projects already solve, and reviewers cannot consistently reject reinvention PRs.

The gap analysis (§6.1) calls out the cost of reinvention: parsers, transpilers, and project generators are large, well-trodden domains where in-house implementations will lose to existing tooling on correctness, edge-case coverage, and maintenance burden.

This ADR fixes the tooling stack for the MVP and the named subsequent phases. Contributors must build on these tools. In-house reimplementation of any layer below is forbidden without a superseding ADR.

---

## Decision

The following tooling is mandated. Each row lists the layer it covers, the chosen tool, the version policy, and the phase at which the dependency becomes load-bearing.

| Layer                         | Tool                              | Version policy                              | Load-bearing from |
|-------------------------------|-----------------------------------|---------------------------------------------|-------------------|
| Web wrapper (host)            | Capacitor (Ionic)                 | Pin to a specific minor on first install    | Phase 1 (MVP)     |
| Source AST (multi-language)   | tree-sitter + per-language grammars | Pin tree-sitter and each grammar          | Phase 1 for web; Phase 2 for Java/Kotlin |
| Swift AST + formatting        | swift-syntax + swift-format       | Track stable Apple releases; pin per Xcode  | Phase 1           |
| Xcode project generation      | XcodeGen (default) or Tuist       | Pin generator version                       | Phase 1           |
| Swift static analysis         | SwiftLint, SwiftFormat, periphery | Pin major; allow patch updates              | Phase 1           |
| Java → iOS transpilation      | J2ObjC                            | Pin release version                         | Phase 2           |
| Kotlin ↔ Swift transpilation  | Skip (skip.tools), KMM where complementary | Pin Skip release; KMM Gradle plugin pin | Phase 2           |
| LLM-assisted idiom translation| Anthropic Claude / OpenAI GPT via captured prompts + seeds | Snapshot model IDs; reproducibility per Tier 1 Step 7 schema | Phase 1 (limited) |

### Defaults and selection rules

- **Project generator:** XcodeGen is the default. Tuist is acceptable as an opt-in for repos that already use it. Hand-writing `project.pbxproj` is forbidden.
- **Dependency manager (Swift side):** Swift Package Manager is the default. CocoaPods support is permitted as a fallback when an upstream Capacitor plugin requires it. Carthage is not supported.
- **Source parser (web archetype):** Use tree-sitter grammars for HTML, CSS, JavaScript, and TypeScript. Reuse upstream grammars; do not author new grammars.
- **Swift code generation:** Emit Swift via swift-syntax. Run swift-format on every emitted file before writing to disk. Do not emit Swift via string templates.
- **Static analysis:** SwiftLint and SwiftFormat run on generated output before the conversion is marked complete. periphery runs in the report-generation step to flag unused emitted symbols.

### Version pinning

- Every tool must have an exact pinned version recorded in the appropriate manifest file (`Package.swift`, `package.json`, `project.yml`, `Brewfile`, or a dedicated `versions.toml` if no natural manifest exists).
- CI must validate the build against the pinned versions on every PR.
- Each tool is tested against the **latest two** Xcode releases on the same CI cadence. Failures on either Xcode release block the PR.

### Update cadence

- Pinned versions are reviewed quarterly. The tech lead opens a PR per tool to bump it, with CI evidence that the build remains green.
- Apple-side tools (swift-syntax, swift-format) are reviewed within 30 days of a new Xcode major release.
- A tool is replaced (not just upgraded) only via a superseding ADR.

---

## Consequences

### Positive

- Reinvention of mature components is closed off. Code review can reject any PR that introduces an in-house parser, transpiler, project generator, or formatter.
- Versioning discipline gives reproducible builds across contributor environments and CI.
- Quarterly review prevents drift while keeping pace with Apple's release cadence.
- LLM provenance hooks into the Tier 1 report schema, so non-deterministic translations remain auditable.

### Negative

- The stack carries the union of every chosen tool's bug surface and release cadence. A regression in any one tool becomes a project regression.
- XcodeGen and Tuist diverge in capability over time; supporting both as opt-in adds maintenance overhead. The cost is bounded by keeping XcodeGen as default and limiting Tuist to opt-in.
- Capacitor introduces a JavaScript-side runtime dependency in every Wrap-mode build. Apple guideline drift around runtime JS (Guideline 4.7 / 2.5.2) could affect us — mitigated by the pre-flight scanner (Tier 1 Step 7).
- LLM dependency on third-party APIs creates a vendor risk. Mitigated by capturing prompts/seeds so a swap to a different model snapshot is reproducible.

### Forbidden without superseding ADR

- Hand-writing `.xcodeproj` files.
- Authoring an in-house source-language parser when tree-sitter has a grammar.
- Authoring an in-house Swift AST representation.
- Reimplementing J2ObjC, Skip, or KMM functionality in-house.
- Generating Swift via string concatenation or template strings without going through swift-syntax + swift-format.

---

## Alternatives Considered

### Alternative A: In-house parser + emitter, no tree-sitter / swift-syntax

- **Why considered:** Removes external dependencies; lets us control the AST shape exactly.
- **Why rejected:** Authoring and maintaining multi-language parsers is a multi-year engineering effort with no upside relative to tree-sitter. Apple's swift-syntax is the canonical Swift AST and is what every credible Swift code generator uses; rolling our own would diverge with every Swift release.

### Alternative B: React Native or Flutter as the Wrap-mode host

- **Why considered:** Both have stronger native-feature stories than a bare WKWebView.
- **Why rejected:** Both are JS-driven UI frameworks, not WebView hosts. Adopting either would change the product from "your web app inside a native shell" to "rebuild your UI in our framework," which is out of MVP scope per `docs/mvp-scope.md` §1. Capacitor is the right abstraction for the Wrap mode the MVP is targeting.

### Alternative C: Cordova instead of Capacitor

- **Why considered:** Cordova predates Capacitor and has broader plugin coverage in legacy ecosystems.
- **Why rejected:** Cordova is in maintenance mode; Capacitor is its de facto successor with active maintenance, modern Xcode integration, and a Swift-friendly plugin model. Adopting Cordova would saddle the MVP with deprecation risk on day one.

### Alternative D: Pure-LLM translation, no AST tooling

- **Why considered:** LLM-only pipelines have caught up quickly on simple translations and avoid the upfront cost of AST integration.
- **Why rejected:** LLM-only output is non-deterministic and difficult to validate. The Tier 1 report (Step 7) needs structured findings tied to source locations, which requires an AST. The chosen approach is hybrid: AST scaffolding for structure + LLM for idiom translation in narrow, captured-prompt contexts.

---

## References

- `docs/mvp-scope.md` — MVP scope and Definition of Done
- `MVP-Gap-Analysis.md` §6.1 — original mandate to fix the tooling stack
- `plans/mvp-tier-0-tier-1.md` Step 4 — plan entry that produced this ADR
- `config/compatibility-matrix.yaml` — gates which (source, target) combinations consume this stack
- Capacitor: https://capacitorjs.com/
- tree-sitter: https://tree-sitter.github.io/tree-sitter/
- swift-syntax: https://github.com/swiftlang/swift-syntax
- XcodeGen: https://github.com/yonaskolb/XcodeGen
- Tuist: https://tuist.dev/
- J2ObjC: https://j2objc.org/
- Skip: https://skip.tools/
