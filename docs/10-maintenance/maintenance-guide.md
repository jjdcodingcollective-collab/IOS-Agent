# Maintenance & Dependencies

> Dependency management and project maintenance on iOS. Swift Package Manager is your npm, and WWDC is your "new major framework version" event.

---

## Swift Package Manager (SPM) — Your npm

| npm | Swift Package Manager |
|---|---|
| `package.json` | `Package.swift` (for libraries) or Xcode project settings (for apps) |
| `node_modules/` | `~/Library/Developer/Xcode/DerivedData/` (global cache) |
| `package-lock.json` | `Package.resolved` (commit this) |
| `npm install` | Xcode resolves automatically, or `swift package resolve` |
| `npm update` | File → Packages → Update to Latest Versions |
| `npx` | `swift package plugin` |
| npmjs.com | No central registry — packages are git repos |

### Adding a Dependency in Xcode

```
1. File → Add Package Dependencies
2. Paste the git URL: https://github.com/author/package
3. Choose version rule (Up to Next Major recommended)
4. Select which targets need the package
```

### Adding a Dependency in Package.swift (for libraries)

```swift
// Package.swift
let package = Package(
    name: "MyLibrary",
    platforms: [.iOS(.v17)],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.15.0"),
        .package(url: "https://github.com/onevcat/Kingfisher", from: "7.10.0"),
    ],
    targets: [
        .target(
            name: "MyLibrary",
            dependencies: [
                .product(name: "Kingfisher", package: "Kingfisher"),
            ]
        ),
        .testTarget(
            name: "MyLibraryTests",
            dependencies: [
                "MyLibrary",
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing"),
            ]
        ),
    ]
)
```

### Version Rules

| Rule | Meaning | npm Equivalent |
|---|---|---|
| `from: "1.0.0"` | ≥ 1.0.0, < 2.0.0 | `^1.0.0` |
| `"1.0.0"..<"1.5.0"` | ≥ 1.0.0, < 1.5.0 | `>=1.0.0 <1.5.0` |
| `.exact("1.2.3")` | Exactly 1.2.3 | `1.2.3` |
| `.branch("main")` | Track a branch | `github:user/repo#main` |

**Best practice:** Use `from:` (equivalent to `^` in npm). Pin exact versions only when you have a specific reason.

---

## Recommended Packages

Packages most web-to-iOS teams will need:

| Need | Package | Notes |
|---|---|---|
| Image loading & caching | [Kingfisher](https://github.com/onevcat/Kingfisher) | Like next/image but for native |
| Snapshot testing | [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing) | Like jest-image-snapshot |
| Linting | [SwiftLint](https://github.com/realm/SwiftLint) | Like ESLint |
| Keychain access | [KeychainAccess](https://github.com/kishikawakatsumi/KeychainAccess) | Simpler Keychain API |
| Date handling | Foundation (built-in) | No need for date-fns/dayjs — Swift's Date and Calendar are comprehensive |
| JSON parsing | Foundation Codable (built-in) | No need for external JSON libraries |
| State management | Observation framework (built-in) | No need for external state libraries in most cases |

**Key difference from web:** The Swift standard library and Apple frameworks cover much more ground than Node.js built-ins. You'll need far fewer third-party dependencies.

---

## Xcode Project Maintenance

### Keeping Xcode Updated

Major Xcode versions ship annually after WWDC (June). Each major version adds support for the next iOS version.

```
WWDC (June) → Xcode beta → September → Xcode release + new iOS
```

**Update strategy:**
- Install Xcode betas in parallel (don't replace your stable Xcode during development)
- Test your app on new iOS betas during summer
- Update to the new Xcode release when you're ready to support the new iOS

### Minimum Deployment Target

This is the oldest iOS version your app supports. It's like setting your browsing compatibility target.

```
Current best practice (as of 2026):
- Support current iOS and previous version (iOS 18 + iOS 17)
- This covers ~95% of active devices
- Allows use of modern APIs with iOS 17+ (Observable, NavigationStack, etc.)
```

Set in: **Xcode → Project → General → Minimum Deployments**

### Derived Data

Xcode's build cache (`~/Library/Developer/Xcode/DerivedData/`). Like `node_modules` + build cache combined.

```bash
# Clean derived data when things get weird
rm -rf ~/Library/Developer/Xcode/DerivedData

# Or from Xcode: Product → Clean Build Folder (⌘⇧K)
```

---

## OS Compatibility Matrix

| If you want to use... | Minimum iOS | Notes |
|---|---|---|
| `@Observable` macro | iOS 17 | Replaces older ObservableObject |
| `NavigationStack` | iOS 16 | Replaces NavigationView |
| `async/await` | iOS 15 | (or iOS 13 with backport) |
| SwiftUI (basic) | iOS 13 | But significant improvements in every version |
| `SwiftData` | iOS 17 | Core Data replacement |
| Widgets | iOS 14 | WidgetKit |
| Live Activities | iOS 16.1 | Dynamic Island + Lock Screen |

**Recommendation for new projects:** Target iOS 17+ minimum. This gives you access to all modern APIs and covers the vast majority of active devices.

---

## Code Quality

### SwiftLint (Like ESLint)

```yaml
# .swiftlint.yml
opt_in_rules:
  - empty_count
  - closure_spacing
  - force_unwrapping

disabled_rules:
  - trailing_whitespace

excluded:
  - Pods
  - .build

line_length:
  warning: 120
  error: 150
```

```bash
# Install
brew install swiftlint

# Run
swiftlint

# Auto-fix
swiftlint --fix
```

### Swift Format (Like Prettier)

```bash
# Apple's official formatter
brew install swift-format

# Format a file
swift-format format --in-place Sources/MyFile.swift

# Format entire project
swift-format format --recursive --in-place Sources/
```

---

## Handling Breaking Changes

### WWDC Season (June - September)

Every June, Apple announces new iOS/macOS versions and new APIs. New Xcode drops in September.

**Annual checklist:**
1. Watch WWDC sessions relevant to your app
2. Install Xcode beta (don't replace stable)
3. Build your app with the new SDK — fix warnings and deprecations
4. Test on new OS betas
5. Adopt new features that benefit your users
6. Ship an update before or shortly after the new OS launches

### Deprecation Handling

Apple marks APIs as deprecated with compiler warnings. They rarely remove APIs immediately — you usually have 2-3 years.

```swift
// Xcode shows warning:
// 'NavigationView' was deprecated in iOS 16.0: use NavigationStack or NavigationSplitView instead

// Fix: replace deprecated API
// Before:
NavigationView { ... }
// After:
NavigationStack { ... }
```

**Strategy:** Fix deprecation warnings as part of your annual WWDC update cycle. Don't ignore them — accumulated warnings mask real issues.

---

## Project Health Checklist

Run through this quarterly:

- [ ] All dependencies up to date (`File → Packages → Update to Latest Versions`)
- [ ] No deprecation warnings in build output
- [ ] Tests pass on latest Xcode
- [ ] App runs correctly on latest iOS
- [ ] Minimum deployment target is still appropriate
- [ ] `Package.resolved` is committed and up to date
- [ ] No hardcoded secrets in source code
- [ ] Privacy manifest is current
- [ ] App Store screenshots are current

---

**Next:** [Common Pitfalls](../11-pitfalls/web-dev-gotchas.md) — Mistakes web developers make on iOS.

*Last updated: 2026-04-25*
