# Web-to-iOS Transition Overview

> Your team ships web apps via containers and Vercel. This guide maps that world to iOS native development — what changes, what carries over, and how to plan the transition.

---

## The Mental Shift

| Web World | iOS World |
|---|---|
| Browser is your runtime | iOS is your runtime (no browser sandbox) |
| Deploy anytime, instant rollout | App Store review (1-3 days), phased rollouts |
| Responsive layouts via CSS | Adaptive layouts via SwiftUI/Auto Layout |
| npm / yarn / pnpm | Swift Package Manager (SPM) |
| Vercel / Netlify / Docker | Xcode Cloud / TestFlight / App Store Connect |
| `localhost:3000` | iOS Simulator or physical device |
| JavaScript/TypeScript | Swift (strongly typed, compiled) |
| React/Vue/Svelte components | SwiftUI Views or UIKit ViewControllers |
| REST/GraphQL via fetch | URLSession with async/await |
| `.env` files | Xcode schemes, Info.plist, xcconfig files |
| CI/CD via GitHub Actions | Xcode Cloud, Fastlane, or GitHub Actions with macOS runners |

The biggest shift isn't the language — it's the **deployment model**. On the web, you push and it's live. On iOS, you submit a build, wait for review, and users update on their own schedule. This fundamentally changes how you think about releases, feature flags, and backwards compatibility.

---

## Transition Strategies

There are three paths from web to iOS. Choose based on your timeline, team skills, and product requirements.

### Strategy 1: Wrap (Fastest)

Wrap mode embeds your existing web app in a native iOS shell using `WKWebView` (the converter targets a Capacitor host project). Your web app runs inside a native container that can access some device features via JavaScript bridges.

**When to choose this:**
- You need an App Store presence quickly
- Your web app works well on mobile Safari already
- You don't need deep hardware integration (camera, AR, Bluetooth)
- Your team doesn't have Swift experience yet

**Trade-offs:**
- Performance limited by WebView rendering
- Limited access to native APIs without bridging
- App Store reviewers may reject "thin" Wrap apps that add no native value (Guideline 4.2)
- Users may notice it's not a "real" native app

**Timeline:** 2-4 weeks for a basic Wrap app with basic native features.

See: [WebView & Hybrid Integration Guide](../06-webview-hybrid/webview-guide.md)

### Strategy 2: Bridge (Progressive Migration)

Bridge mode starts as a Wrap app, then incrementally replaces web screens with native SwiftUI views. Your web app and native code coexist, and you migrate screen by screen.

**When to choose this:**
- You want to ship something soon but go fully native (Port) eventually
- Different parts of your app have different performance requirements
- You want to train your team on Swift while still shipping features

**Trade-offs:**
- Two codebases to maintain during transition
- Complexity in routing between web and native screens
- Need a clear migration plan to avoid "permanent Bridge" limbo

**Timeline:** 1-2 months for initial Bridge, 3-6 months for significant native coverage.

### Strategy 3: Port (Best Long-Term)

Port mode rebuilds the iOS app from scratch in SwiftUI. Reuse your API layer and business logic concepts, but rewrite the UI and client-side logic in Swift.

**When to choose this:**
- You need the best possible performance and UX
- You need deep platform integration (widgets, Watch app, Shortcuts, Live Activities)
- Your team has time to invest in learning Swift/SwiftUI
- You're building a product where the mobile experience is primary

**Trade-offs:**
- Longest timeline to first ship
- Parallel feature development across web and iOS
- Need to keep API contracts stable across both clients

**Timeline:** 3-6 months for a full-featured v1.

---

## What Carries Over From Web

Not everything changes. You keep:

- **Your API layer** — Your backend REST/GraphQL APIs work identically from Swift. URLSession replaces `fetch`, but the HTTP semantics are the same.
- **Your data models** — JSON structures map directly to Swift `Codable` structs. If you have TypeScript interfaces, they translate almost 1:1.
- **Your state management concepts** — React state/context maps to SwiftUI's `@State`, `@ObservableObject`, and `@Environment`. The patterns are different, the thinking is the same.
- **Your CI/CD mindset** — Automated builds, tests, and deploys exist on iOS too. TestFlight is your staging environment, just like Vercel preview deployments.
- **Your git workflow** — Nothing changes here. Same branching, same PRs, same code review.

---

## What's Genuinely New

- **Xcode** — You can't avoid it. It's your IDE, build system, debugger, simulator manager, and provisioning tool all in one. See [Environment Setup](environment-setup.md).
- **Code Signing & Provisioning** — The most confusing part of iOS development. Every build must be cryptographically signed. Apple manages the trust chain. See [Deployment Guide](../09-deployment/deployment-guide.md).
- **The App Store Review Process** — A human reviews your app before each release. They check for guideline compliance, performance, and content policy. Budget 1-3 days per submission.
- **Memory & Resource Constraints** — iOS aggressively kills background apps. You can't assume your app stays running. You need to handle state preservation and restoration.
- **Offline-First Expectations** — Mobile users expect apps to work without connectivity. Core Data or SwiftData provide local persistence. This is less common in web development.

---

## Recommended Learning Path

1. **Week 1:** [Environment Setup](environment-setup.md) → Get Xcode running, build a Hello World app, run it on Simulator
2. **Week 1-2:** [Swift for Web Developers](../02-swift-fundamentals/swift-for-web-devs.md) → Learn Swift syntax mapped from JS/TS concepts
3. **Week 2-3:** [Architecture Patterns](../03-architecture/patterns.md) → Understand how web patterns map to iOS
4. **Week 3-4:** [SwiftUI Guide](../04-ui-development/swiftui-guide.md) → Build real UI, learn the layout system
5. **Week 4+:** Pick your transition strategy and start building

---

## Decision Framework: Wrap vs. Bridge vs. Port

```
Do you need App Store presence in < 1 month?
├── Yes → Do you need native features (camera, AR, push)?
│   ├── Yes → Bridge (WebView + targeted native screens)
│   └── No  → Wrap (WKWebView host)
└── No  → Is mobile your primary platform?
    ├── Yes → Port (full native rebuild)
    └── No  → Bridge (progressive migration)
```

> **Mode names:** Wrap / Bridge / Port are the canonical names per `docs/mvp-scope.md`. The older terms "wrapper," "hybrid," and "fully native" are deprecated when used as mode labels — they may still appear historically in the codebase but should not be introduced in new content.

---

**Next:** [Environment Setup](environment-setup.md) — Get your development environment ready.

*Last updated: 2026-04-25*
