# Environment Setup

> Everything you need to go from zero to building and running an iOS app. If you've set up a Node.js project with Docker, this is the equivalent — but Apple-flavored.

---

## Prerequisites

- **A Mac** — iOS development requires macOS. There's no Windows or Linux alternative for building and signing iOS apps. If your team develops on non-Mac hardware, you'll need macOS CI runners (GitHub Actions, Xcode Cloud) for builds.
- **An Apple ID** — Free for development and simulator testing. You need a paid Apple Developer Program membership ($99/year) for device testing and App Store distribution.

---

## Install Xcode

Xcode is your entire toolchain: IDE, compiler, simulator, debugger, Interface Builder, and provisioning manager.

```bash
# Install via Mac App Store (recommended — handles updates automatically)
# Or install via command line:
xcode-select --install   # Command line tools only (for CI)

# For full Xcode, download from:
# https://developer.apple.com/xcode/
```

After installation, open Xcode once to accept the license and install additional components.

**Web equivalent:** Xcode is VS Code + Docker + Chrome DevTools + your build system, all bundled together.

### Xcode Components That Matter

| Component | What it does | Web equivalent |
|---|---|---|
| **Editor** | Write code, SwiftUI previews | VS Code |
| **Simulator** | Run iOS/iPadOS/watchOS apps | Browser DevTools device mode (but a real OS) |
| **Instruments** | Performance profiling | Chrome Performance tab / Lighthouse |
| **Interface Builder** | Visual UI design (mostly legacy) | No direct equivalent — SwiftUI previews replace this |
| **Organizer** | Manage builds, crash logs, archives | Vercel dashboard |

---

## Xcode Project vs. Web Project Structure

```
Web Project                     iOS Project
├── package.json                ├── MyApp.xcodeproj (or .xcworkspace)
├── src/                        ├── MyApp/
│   ├── components/             │   ├── Views/
│   ├── pages/                  │   ├── Models/
│   ├── hooks/                  │   ├── ViewModels/
│   ├── utils/                  │   ├── Services/
│   └── App.tsx                 │   └── MyAppApp.swift (entry point)
├── public/                     ├── Assets.xcassets (images, colors)
├── .env                        ├── Info.plist (app metadata)
├── tsconfig.json               ├── Package.swift (SPM dependencies)
├── next.config.js              └── MyApp.entitlements (permissions)
├── vercel.json
└── Dockerfile
```

Key differences:
- No `node_modules` — SPM packages are resolved by Xcode and cached globally
- No `.env` — use Xcode schemes and xcconfig files for environment-specific config
- `Info.plist` is your app's manifest — it declares permissions, supported orientations, URL schemes, etc.
- `Assets.xcassets` is a structured asset catalog, not a `public/` folder

---

## The iOS Simulator

The Simulator runs a real iOS operating system (not emulation — it's simulation on your Mac's CPU). It's fast and covers most development needs.

```bash
# Open Simulator from command line
open -a Simulator

# List available simulators
xcrun simctl list devices

# Boot a specific simulator
xcrun simctl boot "iPhone 16 Pro"

# Install and launch an app
xcrun simctl install booted MyApp.app
xcrun simctl launch booted com.myteam.myapp
```

**Limitations vs. real devices:**
- No camera, Bluetooth, NFC, or accelerometer
- Performance characteristics differ from real hardware
- Push notifications require extra setup
- Metal (GPU) rendering can differ

**Rule of thumb:** Develop on Simulator, test on device before every release.

---

## Apple Developer Program

| Tier | Cost | What you get |
|---|---|---|
| **Free Apple ID** | $0 | Xcode, Simulator, build to personal device (7-day cert), documentation |
| **Individual** | $99/year | TestFlight, App Store distribution, provisioning profiles, 100 test devices |
| **Organization** | $99/year | Everything above + team management, requires D-U-N-S number |
| **Enterprise** | $299/year | Internal distribution without App Store (large companies only) |

**For your transition:** Start with the $99 Individual or Organization program. You need it for TestFlight beta testing (your Vercel preview equivalent).

---

## Code Signing (The Part That Confuses Everyone)

Code signing proves your app comes from you and hasn't been tampered with. Every iOS app must be signed.

### How it works (simplified):

1. **Apple issues you a certificate** — this is your identity as a developer
2. **You create an App ID** — a unique identifier for your app (like `com.myteam.myapp`)
3. **You create a provisioning profile** — links your certificate + App ID + authorized devices
4. **Xcode signs your build** — embeds the profile in the `.ipa` file

### Automatic vs. Manual Signing

```
Automatic (recommended for most teams):
Xcode → Signing & Capabilities → Check "Automatically manage signing"
→ Xcode handles certificates, profiles, and device registration

Manual (for complex CI/CD setups):
You manage certificates and profiles in Apple Developer portal
→ More control, more complexity, needed for advanced Fastlane workflows
```

**Web equivalent:** There is none. The closest analogy is SSL certificates, but code signing is mandatory for every build, not just production.

---

## Essential CLI Tools

```bash
# Swift compiler and REPL
swift --version
swift repl              # Interactive Swift (like Node REPL)

# Swift Package Manager (your npm equivalent)
swift package init      # Create a new package
swift build             # Build
swift test              # Run tests

# Xcode command line tools
xcodebuild -list                    # List targets and schemes
xcodebuild -scheme MyApp build      # Build from CLI
xcodebuild test -scheme MyApp       # Run tests from CLI

# Simulator management
xcrun simctl list                   # List simulators
xcrun simctl boot <device-id>       # Start a simulator
xcrun simctl shutdown all           # Stop all simulators
```

---

## Recommended Xcode Settings

After installing Xcode, configure these:

1. **Xcode → Settings → Accounts** — Add your Apple ID
2. **Xcode → Settings → Locations → Command Line Tools** — Select your Xcode version
3. **Xcode → Settings → Text Editing → Indentation** — Set to 4 spaces (Swift convention)
4. **Enable SwiftUI Previews** — Editor → Canvas (⌥⌘↩) to toggle the live preview pane

---

## Environment Configuration (Replacing .env)

On the web, you use `.env` files and `process.env`. On iOS, configuration is handled differently:

### xcconfig files (recommended)

```
// Debug.xcconfig
API_BASE_URL = https://api-staging.myapp.com
ENABLE_LOGGING = YES

// Release.xcconfig  
API_BASE_URL = https://api.myapp.com
ENABLE_LOGGING = NO
```

Reference in code:
```swift
// Info.plist: Add a key "API_BASE_URL" with value $(API_BASE_URL)
// Then access in Swift:
let apiURL = Bundle.main.infoDictionary?["API_BASE_URL"] as? String
```

### Xcode Schemes

Schemes define how your app builds and runs for different configurations (Debug, Release, Staging). Think of them as your Vercel environment presets.

```
Scheme: MyApp-Dev     → Debug config   → points to staging API
Scheme: MyApp-Staging → Release config → points to staging API  
Scheme: MyApp-Prod    → Release config → points to production API
```

---

## Quick Verification Checklist

After setup, verify everything works:

- [ ] `swift --version` prints a version
- [ ] Xcode opens without errors
- [ ] You can create a new iOS App project (File → New → Project → iOS → App)
- [ ] The SwiftUI preview renders in the canvas
- [ ] The app builds and runs in Simulator (⌘R)
- [ ] Your Apple Developer account appears in Xcode → Settings → Accounts

---

**Next:** [Swift for Web Developers](../02-swift-fundamentals/swift-for-web-devs.md) — Learn Swift with your JavaScript/TypeScript knowledge as a foundation.

*Last updated: 2026-04-25*
