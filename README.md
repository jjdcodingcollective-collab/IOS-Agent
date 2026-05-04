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
```

The converter writes a Swift project (`Package.swift`, `project.yml` for [xcodegen](https://github.com/yonaskolb/XcodeGen), `Sources/`, `Tests/`) plus five reports under `.ios-conversion/` on the conversion branch. Runs that fail validation or score below 60% confidence land on a `Requires-more-review/` prefixed branch so reviewers can spot them at a glance.

Pipeline:

```
TS source → analyzer → reviewer → rewriter → assembler → validator → reports + Swift project
```

Status: all 15 BUILD-* items shipped (see `plans/gap-analysis-and-build-guide.md`); wrapper is at Phase 2 (clone + convert + local commit; push lands in Phase 3).

---

## Table of Contents

### Getting Started
- [Web-to-iOS Transition Overview](docs/01-getting-started/transition-overview.md) — Strategy, timeline, and decision framework
- [Environment Setup](docs/01-getting-started/environment-setup.md) — Xcode, tooling, certificates, and simulators

### Language & Fundamentals
- [Swift for Web Developers](docs/02-swift-fundamentals/swift-for-web-devs.md) — Swift concepts mapped to JavaScript/TypeScript

### Architecture
- [Architecture Patterns](docs/03-architecture/patterns.md) — Translating web architecture to iOS (MVC, MVVM, state management)

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

The `docs/` guide is currently scoped to **JavaScript / TypeScript → Swift** developers. A 2026-05-04 review against the broader brief of "transposing popular coding languages to Swift" identified 9 documentation gaps (GAP-D1…D9), most importantly:

- No source-language coverage for Kotlin, Java, Python, C#, Objective-C, C++, Dart, Rust, Go.
- No Objective-C interop chapter (operationally required for real iOS work).
- Strict Concurrency / `Sendable` / actor-isolation underweighted.
- ARC, capture, closure-lifetime depth thin (one paragraph in pitfalls).
- A few internal inconsistencies in sample code (`try!` / `as!` used in samples that elsewhere forbid them).

These are now tracked as **BUILD-16…22** (specced) and **BUILD-23…30** (backlog) under a new **Phase E** in `plans/gap-analysis-and-build-guide.md`. Phase E is sequenced so correctness fixes (BUILD-20, 17, 19) ship before any new source-language chapters (BUILD-21).

The converter (`converter/`, `wrapper/`) remains TypeScript-source only. Expanding source-language coverage in the docs ahead of the converter is intentional — the docs are the cheaper experiment.

---

## Last Updated

**2026-05-04** *(revised same-day)* — Documentation review against "popular coding languages → Swift" brief. Added dimension 6 (Documentation & Source-Language Coverage) to gap analysis: 9 new gaps, 7 specified BUILD items, 8-item backlog, new Phase E roadmap. Source review at `outputs/Language-Transposition-Gap-Analysis.md`. No code changes.

**2026-05-04** — Added GitHub round-trip wrapper (Phase 1 + 2). Validated end-to-end against `the-survival-bible` monorepo (42 files converted, 50/50 structural validation pass). All 15 original BUILD-* items from the gap analysis are shipped.

**2026-04-25** — Initial release covering the full web-to-iOS transition path and the four-phase converter pipeline.

Maintained by the IOS-Agent team. Review quarterly or after major WWDC announcements.
