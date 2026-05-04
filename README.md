# IOS-Agent

> A reference guide **and** an automated converter for teams transitioning from web development (containerized builds, Vercel deployments) to the iOS and Apple ecosystem.

**Who this is for:** Web developers who build with modern frameworks (React, Next.js, Vite), deploy on Vercel, and are now bringing their products to native iOS.

**What this covers:** The full journey from web to native — environment setup, Swift fundamentals mapped to web concepts, architecture translation, hybrid approaches with WebViews, App Store deployment, and everything in between. Plus a working pipeline that takes your TypeScript codebase and produces a buildable Swift/SwiftUI project.

---

## The Converter (operational)

Two ways to use it:

**1. Local conversion** — point it at a TS project on disk:
```
python -m wrapper convert path/to/typescript-app --app-name MyApp
```

**2. GitHub round-trip** — clone a repo, convert, and create an `ios-conversion` branch:
```
python -m wrapper convert-from-github https://github.com/you/your-app --app-name MyApp
# Monorepo? scope to a subdirectory:
python -m wrapper convert-from-github https://github.com/you/your-app \
    --source-subdir apps/mobile --app-name MyApp
# Push the branch to origin (default is to prompt after the local commit):
python -m wrapper convert-from-github https://github.com/you/your-app --push
# Or commit locally only:
python -m wrapper convert-from-github https://github.com/you/your-app --no-push
```

The converter writes a Swift project (`Package.swift`, `project.yml` for [xcodegen](https://github.com/yonaskolb/XcodeGen), `Sources/`, `Tests/`) plus five reports under `.ios-conversion/` on the conversion branch. Runs that fail validation or score below 60% confidence land on a `Requires-more-review/` prefixed branch so reviewers can spot them at a glance.

Pipeline:

```
TS source → analyzer → reviewer → rewriter → assembler → validator → reports + Swift project
```

Status: all 15 BUILD-* items shipped (see `plans/gap-analysis-and-build-guide.md`); wrapper is at Phase 3 (clone + convert + local commit + opt-in push). Push refuses protected branches (`main`/`master`/`develop`/`trunk`/`release`), never force-pushes, and falls back read-only if credentials are missing.

---

## Table of Contents

### Getting Started
- [Web-to-iOS Transition Overview](docs/01-getting-started/transition-overview.md) — Strategy, timeline, and decision framework
- [Environment Setup](docs/01-getting-started/environment-setup.md) — Xcode, tooling, certificates, and simulators

### Language & Fundamentals
- [Swift for Web Developers](docs/02-swift-fundamentals/swift-for-web-devs.md) — Swift concepts mapped to JavaScript/TypeScript
- [Swift for Kotlin Developers](docs/02-swift-fundamentals/from-kotlin.md) — Near-twin language transposition (coroutines, sealed classes, data classes)
- [Swift for Java Developers](docs/02-swift-fundamentals/from-java.md) — POJOs → structs, checked exceptions → typed throws, GC → ARC
- [Swift for Python Developers](docs/02-swift-fundamentals/from-python.md) — Static typing, no truthiness, no GIL, optionals as types
- [Strict Concurrency & Sendable](docs/02-swift-fundamentals/concurrency-and-sendable.md) — Actors, `@MainActor`, `Sendable`, Swift 6 strict mode
- [ARC, Captures & Lifetimes](docs/02-swift-fundamentals/arc-and-lifetimes.md) — Reference counting, retain cycles, `[weak self]`, `Task` retention
- [Generics, Opaque Types & Existentials](docs/02-swift-fundamentals/generics-and-protocols-deep.md) — `some` vs `any`, PATs, type erasure
- [Objective-C Interop](docs/02-swift-fundamentals/swift-objc-interop.md) — `@objc`, bridging headers, `#selector`, KVO, framework header reading
- [Combine & AsyncStream](docs/02-swift-fundamentals/combine-and-async-streams.md) — Combine for RxJS readers, AsyncSequence, when to pick which
- [Codable Customization](docs/02-swift-fundamentals/codable-deep.md) — CodingKeys, dates, polymorphism, lossy arrays, property-wrapper decoders
- [The Swift Toolkit](docs/02-swift-fundamentals/swift-toolkit-for-web-devs.md) — KeyPaths, property-wrapper authoring, result builders, IUOs

### Architecture
- [Architecture Patterns](docs/03-architecture/patterns.md) — Translating web architecture to iOS (MVC, MVVM, state management)
- [Persistence](docs/03-architecture/persistence.md) — UserDefaults, Keychain, FileManager, SwiftData, Core Data, CloudKit (mapped from ORMs)

### UI Development
- [UI Development with SwiftUI](docs/04-ui-development/swiftui-guide.md) — Building interfaces, mapped from web components and CSS

### Networking & APIs
- [Networking & API Integration](docs/05-networking/api-integration.md) — URLSession, async/await, REST/GraphQL from Swift

### Hybrid & WebView
- [WebView & Hybrid Integration](docs/06-webview-hybrid/webview-guide.md) — Embedding web content, JS-Swift bridging, progressive migration

### Testing & Debugging
- [Testing & Debugging](docs/07-testing/testing-guide.md) — XCTest, UI testing, Instruments, debugging workflows

### Security & Privacy
- [Security & Privacy](docs/08-security/security-guide.md) — App Transport Security, Keychain, privacy manifests, App Store requirements

### Deployment & Distribution
- [Deployment & Distribution](docs/09-deployment/deployment-guide.md) — TestFlight, App Store Connect, CI/CD (mapped from Vercel workflows)
- [App Store Operations](docs/09-deployment/app-store-operations.md) — Privacy manifest, ATT, IDFA, BGTaskScheduler, push, App Groups, entitlements, pre-submission checklist

### Maintenance
- [Maintenance & Dependencies](docs/10-maintenance/maintenance-guide.md) — Swift Package Manager, versioning, OS compatibility

### Common Pitfalls
- [Common Pitfalls for Web Developers](docs/11-pitfalls/web-dev-gotchas.md) — Mistakes web developers make on iOS and how to avoid them

---

## How to Use This Guide

**New to iOS?** Start with the [Transition Overview](docs/01-getting-started/transition-overview.md), then work through the [Environment Setup](docs/01-getting-started/environment-setup.md) and [Swift for Web Developers](docs/02-swift-fundamentals/swift-for-web-devs.md).

**Building a hybrid app?** Jump to [WebView & Hybrid Integration](docs/06-webview-hybrid/webview-guide.md) for strategies on wrapping your existing web app in a native shell.

**Ready to ship?** The [Deployment Guide](docs/09-deployment/deployment-guide.md) maps your Vercel workflow to TestFlight and App Store Connect.

**Hit a wall?** Check [Common Pitfalls](docs/11-pitfalls/web-dev-gotchas.md) first — it covers the most frequent issues web developers encounter.

---

## Contributing

This is a living reference. To contribute:

1. Create a branch from `main`
2. Add or edit markdown files in the relevant `docs/` subfolder
3. Update the Table of Contents in this README if adding new sections
4. Open a PR with a clear description of what changed and why

**Style guidelines:**
- Write for developers who know web but not iOS — explain the *why*, not just the *how*
- Include code examples for every concept
- Link to official Apple documentation where applicable
- Mark deprecated patterns clearly with `> **Deprecated:**` callouts

---

## Scope (Current)

The `docs/` guide now covers **JavaScript / TypeScript, Kotlin, Java, and Python → Swift** developers, plus operational depth on Objective-C interop, strict concurrency, ARC, generics, and persistence.

**Phase E Tier 0 + Tier 1 shipped 2026-05-04** (BUILD-16 through BUILD-22): seven new chapters, three correctness fixes, and a per-language template established for future source-language additions.

**BUILD-26 + BUILD-29 also shipped 2026-05-04** out of the Tier 2/3 backlog (highest reader-leverage among the non-language items): three new companion chapters under `02-swift-fundamentals/` deepening the JS/TS material (Combine, Codable customization, and the KeyPaths/property-wrappers/result-builders/IUO toolkit), and a dedicated `09-deployment/app-store-operations.md` chapter consolidating privacy manifest, ATT, BGTaskScheduler, push, App Groups, and entitlements as a pre-submission checklist.

Remaining backlog under Phase E: BUILD-23 (UIKit), BUILD-24 (C# / Xamarin/MAUI sunset), BUILD-25 (Dart/Flutter), BUILD-27 (C++ interop), BUILD-28 (Rust FFI), BUILD-30 (Go/Ruby/PHP). See `plans/gap-analysis-and-build-guide.md` for full specs.

The converter (`converter/`, `wrapper/`) remains TypeScript-source only. Expanding source-language coverage in the docs ahead of the converter is intentional — the docs are the cheaper experiment.

---

## Last Updated

**2026-05-04** *(Wrapper Phase 3 shipped — opt-in push)* — `convert-from-github` gains `--push` / `--no-push` flags (default: prompt after the local commit lands). `wrapper/git_ops.py` adds `push_branch()` + `PushInfo`: plain `git push --set-upstream`, never `--force`, hard refusal on the protected-branch list, and a read-only fallback when credentials are missing or the push otherwise fails. `--yes` implies `--push` unless overridden. Phase 3 marked ✅ in `plans/github-round-trip.md`; the previously-open re-run-on-stale-base question is resolved as "leave alone."

**2026-05-04** *(BUILD-26 + BUILD-29 shipped from Tier 2/3 backlog)* — Four new chapters: `combine-and-async-streams.md`, `codable-deep.md`, `swift-toolkit-for-web-devs.md` (under `02-swift-fundamentals/`), and `app-store-operations.md` (under `09-deployment/`). The intro `swift-for-web-devs.md` got a "Going Deeper" pointer block linking the eight companion chapters. Cross-links added from `security-guide.md` and `deployment-guide.md` into the new operations chapter. BUILD-26 and BUILD-29 marked ✅ in the gap-analysis build guide. No converter code changes.

**2026-05-04** *(Phase E Tier 0 + Tier 1 shipped, evening)* — Authored seven new chapters: `swift-objc-interop.md`, `concurrency-and-sendable.md`, `arc-and-lifetimes.md`, `generics-and-protocols-deep.md`, `from-kotlin.md`, `from-java.md`, `from-python.md`, plus `03-architecture/persistence.md`. Fixed internal inconsistencies in `web-dev-gotchas.md`, `api-integration.md`, and `swift-for-web-devs.md` (eliminated `try!`/`as!` from happy-path samples; corrected `@EnvironmentObject ↔ useContext` mapping; added IUO callout). BUILD-16…22 marked ✅ in the gap-analysis build guide. No converter code changes.

**2026-05-04** *(revised same-day)* — Documentation review against "popular coding languages → Swift" brief. Added dimension 6 (Documentation & Source-Language Coverage) to gap analysis: 9 new gaps, 7 specified BUILD items, 8-item backlog, new Phase E roadmap. Source review at `outputs/Language-Transposition-Gap-Analysis.md`. No code changes.

**2026-05-04** — Added GitHub round-trip wrapper (Phase 1 + 2). Validated end-to-end against `the-survival-bible` monorepo (42 files converted, 50/50 structural validation pass). All 15 original BUILD-* items from the gap analysis are shipped.

**2026-04-25** — Initial release covering the full web-to-iOS transition path and the four-phase converter pipeline.

Maintained by the IOS-Agent team. Review quarterly or after major WWDC announcements.
