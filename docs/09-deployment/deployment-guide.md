# Deployment & Distribution

> On the web, you `git push` and Vercel deploys. On iOS, the path is: build → archive → upload → TestFlight (beta) → App Store review → release. This guide maps your Vercel workflow to the iOS equivalent.

---

## Vercel vs. iOS Deployment Pipeline

```
Web (Vercel)                         iOS (App Store)
────────────                         ───────────────
git push                             git push
  │                                    │
  ▼                                    ▼
Vercel builds automatically          Xcode Cloud / GitHub Actions builds
  │                                    │
  ▼                                    ▼
Preview deployment (per PR)          TestFlight build (per branch/tag)
  │                                    │
  ▼                                    ▼
Team reviews preview URL             Team installs via TestFlight app
  │                                    │
  ▼                                    ▼
Merge to main → production           Submit to App Store Review (1-3 days)
  │                                    │
  ▼                                    ▼
Live instantly                       Approved → release to App Store
                                       │
                                       ▼
                                     Users update (auto or manual)
```

The critical difference: **you can't roll back an iOS release**. Once users have a version, you can only push a new version forward. This means you need feature flags and careful testing before submission.

---

## TestFlight (Your Staging Environment)

TestFlight is Apple's beta testing platform. It's the closest equivalent to Vercel preview deployments.

| Vercel Previews | TestFlight |
|---|---|
| Auto-deployed per PR | Upload builds manually or via CI |
| Shareable URL | Invite testers by email or public link |
| Instant updates | Users must install update from TestFlight app |
| Unlimited viewers | Up to 10,000 external testers |
| No review needed | External testers require beta review (~24h) |
| Expires never | Builds expire after 90 days |

### TestFlight Workflow

1. **Archive your app** in Xcode (Product → Archive) or via CI
2. **Upload to App Store Connect** (from Xcode Organizer or `xcodebuild`)
3. **Add testers** — internal (your team, up to 100) or external (up to 10,000)
4. **Internal testers** get the build immediately — no review needed
5. **External testers** require a beta app review (usually < 24 hours)

### Internal vs. External Testing

| | Internal | External |
|---|---|---|
| Who | Your Apple Developer team members | Anyone with an email |
| Limit | 100 testers | 10,000 testers |
| Review | None — available immediately | Beta review required |
| Use for | Daily development, QA | Beta programs, stakeholder demos |

---

## The Build Process

### From Xcode (Manual)

```
1. Product → Archive (creates a signed .xcarchive)
2. Window → Organizer → select archive → Distribute App
3. Choose "App Store Connect" → Upload
4. Wait for processing (5-30 min) → appears in App Store Connect
```

### From Command Line (CI/CD)

```bash
# Build archive
xcodebuild archive \
    -scheme MyApp \
    -archivePath ./build/MyApp.xcarchive \
    -destination 'generic/platform=iOS'

# Export IPA
xcodebuild -exportArchive \
    -archivePath ./build/MyApp.xcarchive \
    -exportOptionsPlist ExportOptions.plist \
    -exportPath ./build/output

# Upload to App Store Connect
xcrun altool --upload-app \
    -f ./build/output/MyApp.ipa \
    -t ios \
    -u your@email.com \
    -p @keychain:AC_PASSWORD
```

---

## CI/CD Options

### Xcode Cloud (Apple's Built-in CI)

The easiest option. Configured directly in Xcode, runs on Apple's infrastructure.

```
Xcode → Product → Xcode Cloud → Create Workflow

Workflow:
- Trigger: Push to main branch
- Actions: Build, Test, Archive
- Post-Actions: Upload to TestFlight
```

**Pros:** No setup, no macOS runners to manage, free tier available
**Cons:** Less flexible than GitHub Actions, Apple-only

### GitHub Actions with macOS Runner

If you already use GitHub Actions for your web CI/CD:

```yaml
# .github/workflows/ios.yml
name: iOS Build & Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: macos-14
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Select Xcode
        run: sudo xcode-select -s /Applications/Xcode_16.app
      
      - name: Resolve packages
        run: xcodebuild -resolvePackageDependencies -scheme MyApp
      
      - name: Run tests
        run: |
          xcodebuild test \
            -scheme MyApp \
            -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
            -resultBundlePath TestResults
      
      - name: Archive (main only)
        if: github.ref == 'refs/heads/main'
        run: |
          xcodebuild archive \
            -scheme MyApp \
            -archivePath build/MyApp.xcarchive \
            -destination 'generic/platform=iOS'
      
      - name: Upload to TestFlight (main only)
        if: github.ref == 'refs/heads/main'
        run: |
          xcodebuild -exportArchive \
            -archivePath build/MyApp.xcarchive \
            -exportOptionsPlist ExportOptions.plist \
            -exportPath build/output
          
          xcrun altool --upload-app \
            -f build/output/MyApp.ipa \
            -t ios \
            -u ${{ secrets.APPLE_ID }} \
            -p ${{ secrets.APP_SPECIFIC_PASSWORD }}
```

### Fastlane (Community Standard)

Fastlane automates the most painful parts of iOS deployment — code signing, screenshots, and uploads.

```ruby
# Fastfile
default_platform(:ios)

platform :ios do
  desc "Push a new beta build to TestFlight"
  lane :beta do
    increment_build_number
    build_app(scheme: "MyApp")
    upload_to_testflight
  end

  desc "Push a new release to the App Store"
  lane :release do
    increment_build_number
    build_app(scheme: "MyApp")
    upload_to_app_store(
      submit_for_review: true,
      automatic_release: true
    )
  end
end
```

```bash
# Run locally or in CI
fastlane beta      # Build and upload to TestFlight
fastlane release   # Build and submit to App Store
```

---

## App Store Submission

### Before Your First Submission

1. **App Store Connect** — Create your app listing at [appstoreconnect.apple.com](https://appstoreconnect.apple.com)
2. **App Information** — Name, category, description, keywords, support URL
3. **Screenshots** — Required for each device size you support (iPhone, iPad)
4. **App Icon** — 1024x1024px (Xcode generates all sizes from this)
5. **Privacy Policy URL** — Required for all apps
6. **Age Rating** — Complete the questionnaire

### App Store Review Guidelines (Key Points)

These are the most common rejection reasons for web-to-iOS transitions:

| Rejection Reason | How to Avoid |
|---|---|
| "App is a repackaged website" | Add meaningful native features (push, offline, native UI) |
| Missing privacy policy | Add a privacy policy URL in App Store Connect |
| Crashes on launch | Test on real devices, not just Simulator |
| Incomplete metadata | Fill out all required fields, provide demo credentials if login required |
| Missing purpose strings | Add all `NS*UsageDescription` entries in Info.plist |
| "Guideline 4.2 — Minimum functionality" | Your app must do more than a website. Add native value |

### Review Timelines

- **First submission:** 1-3 days (sometimes longer)
- **Updates:** Usually 24 hours
- **Expedited review:** Available for critical bug fixes (request via App Store Connect)
- **Rejection response:** You can reply and resubmit without going to the back of the queue

---

## Version Management

### Semantic Versioning

iOS uses two version numbers:
- **Marketing version** (`CFBundleShortVersionString`): What users see — `1.0.0`, `1.1.0`, `2.0.0`
- **Build number** (`CFBundleVersion`): Internal build identifier — must be unique per upload, typically incremented automatically

```swift
// Access in code
let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String  // "1.2.0"
let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String               // "42"
```

### Feature Flags (Critical for iOS)

Since you can't roll back releases, feature flags are essential:

```swift
struct FeatureFlags {
    // Remote config (fetch from your API)
    static var newProfileEnabled = false
    static var experimentalSearch = false
    
    static func refresh() async {
        do {
            let flags: FlagResponse = try await APIClient.shared.get("/config/flags")
            newProfileEnabled = flags.newProfile
            experimentalSearch = flags.experimentalSearch
        } catch {
            // Use defaults on failure
        }
    }
}

// Usage in views
if FeatureFlags.newProfileEnabled {
    NewProfileView()
} else {
    LegacyProfileView()
}
```

---

## Phased Rollout

Like Vercel's percentage-based rollouts, Apple offers phased release:

- Release to 1%, 2%, 5%, 10%, 20%, 50%, 100% over 7 days
- You can pause, resume, or immediately release to everyone
- Only applies to automatic updates — users who manually check can always get it

---

**Next:** [Maintenance & Dependencies](../10-maintenance/maintenance-guide.md) — Keeping your iOS project healthy.

*Last updated: 2026-04-25*
