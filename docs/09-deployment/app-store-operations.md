# App Store Operations: Privacy, Tracking, Background Work, Push, App Groups

> The "ship to App Store" surface is its own competency. Privacy manifests, App Tracking Transparency, IDFA, background tasks, push notifications, App Groups, entitlements — none of these are language-design topics, but every one of them is a *required* moving part for a real production app. This chapter consolidates them in one operational reference.

---

## Why this chapter exists

In other guides this material is scattered across security, deployment, and "common pitfalls" pages. In practice you reach for it as a single problem space:

- The privacy manifest, the Info.plist usage descriptions, the entitlements file, and App Store Connect's data-collection survey **must agree**. A mismatch is the most common reason for App Store Review rejection.
- The set of "background things you can do" — silent push, background fetch, BGTaskScheduler, location updates, audio — interacts with capabilities in Xcode, entries in `Info.plist`, and approval criteria in App Review.
- The set of "things you can store cross-process" — App Groups, Keychain access groups, shared `UserDefaults`, shared file containers — uses overlapping but distinct entitlements.

Treat this as a checklist before shipping, not a casual read.

---

## 1. Privacy Manifest (`PrivacyInfo.xcprivacy`)

**Required since Spring 2024 for new and updated apps**, and **strictly enforced since November 2024**. Apple will reject builds whose privacy manifest doesn't account for required-reason API usage.

### What it declares

A `PrivacyInfo.xcprivacy` file (Property List XML) in your app bundle answers four questions:

1. **Does the app track users across apps/websites?** (`NSPrivacyTracking`)
2. **What domains does it use for tracking?** (`NSPrivacyTrackingDomains`)
3. **What data does it collect?** (`NSPrivacyCollectedDataTypes`)
4. **Which "required reason" APIs does it use, and why?** (`NSPrivacyAccessedAPITypes`)

### Required-reason APIs (the part that gets you rejected)

Apple maintains a list of APIs whose use requires a declared reason. The major categories:

| Category | Examples | Common reason codes |
|---|---|---|
| `NSPrivacyAccessedAPICategoryFileTimestamp` | `creationDate`, `modificationDate` on files | `C617.1`, `0A2A.1` |
| `NSPrivacyAccessedAPICategoryUserDefaults` | `UserDefaults` reads/writes | `CA92.1`, `1C8F.1` |
| `NSPrivacyAccessedAPICategorySystemBootTime` | `mach_absolute_time`, `systemUptime` | `35F9.1`, `8FFB.1` |
| `NSPrivacyAccessedAPICategoryDiskSpace` | `volumeAvailableCapacityKey` | `E174.1`, `85F4.1` |
| `NSPrivacyAccessedAPICategoryActiveKeyboards` | `UITextInputMode.activeInputModes` | `54BD.1`, `3EC4.1` |

Reason codes are matched literally — `"CA92.1"` not `"CA92"`. The full official list lives at <https://developer.apple.com/documentation/bundleresources/privacy_manifest_files/describing_use_of_required_reason_api>.

### Where it goes

- **App target:** `<AppTarget>/PrivacyInfo.xcprivacy` — at the root of your app's bundle.
- **SDK targets:** every framework or SwiftPM library you ship that uses required-reason APIs needs its **own** privacy manifest. Apple aggregates them at submission.
- Third-party SDKs you depend on (Firebase, Sentry, etc.) ship their own manifests now. Check that your version of each SDK is up to date — older versions without manifests will cause submission warnings or rejections.

### Minimal example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
                      "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSPrivacyTracking</key>
    <false/>
    <key>NSPrivacyTrackingDomains</key>
    <array/>
    <key>NSPrivacyCollectedDataTypes</key>
    <array>
        <dict>
            <key>NSPrivacyCollectedDataType</key>
            <string>NSPrivacyCollectedDataTypeEmailAddress</string>
            <key>NSPrivacyCollectedDataTypeLinked</key>
            <true/>
            <key>NSPrivacyCollectedDataTypeTracking</key>
            <false/>
            <key>NSPrivacyCollectedDataTypePurposes</key>
            <array>
                <string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string>
                <string>NSPrivacyCollectedDataTypePurposeAnalytics</string>
            </array>
        </dict>
    </array>
    <key>NSPrivacyAccessedAPITypes</key>
    <array>
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>CA92.1</string>
            </array>
        </dict>
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryFileTimestamp</string>
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>C617.1</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
```

### Validation before submission

```bash
# Inside your built .app bundle:
plutil -lint PrivacyInfo.xcprivacy

# To validate aggregation across SDKs (Xcode 15.3+):
xcrun privacy-checker --target MyApp.app
```

The Xcode 15+ Organizer shows aggregated privacy info before upload — review it there.

### App Store Connect data-collection survey

**Must match the manifest.** When you file a new release in App Store Connect → App Privacy, the data types you select must be a superset of (and ideally identical to) what's in `NSPrivacyCollectedDataTypes`. If you collect "device ID" in code but didn't declare it on either side, the app gets rejected.

---

## 2. App Tracking Transparency (ATT)

ATT is the runtime permission that lets you call `ASIdentifierManager.advertisingIdentifier` (the IDFA) and use any data for **cross-app/cross-website tracking**.

### When you need it

You need ATT if and only if:

- You read the IDFA, OR
- You correlate first-party data with data from **other companies' apps or websites** for advertising or share with data brokers.

You **don't** need ATT for analytics that stay first-party and don't tie to other sources, or for crash reporting.

### Implementation

```swift
import AppTrackingTransparency
import AdSupport

@MainActor
func requestTrackingAuthorization() async -> ATTrackingManager.AuthorizationStatus {
    await ATTrackingManager.requestTrackingAuthorization()
}

func currentIDFA() -> String? {
    guard ATTrackingManager.trackingAuthorizationStatus == .authorized else {
        return nil
    }
    return ASIdentifierManager.shared.advertisingIdentifier.uuidString
}
```

Add to `Info.plist`:

```xml
<key>NSUserTrackingUsageDescription</key>
<string>We use this to deliver relevant ads. You can change this anytime in Settings.</string>
```

Apple rejects vague strings. Be specific about *what* you track and *what value* the user gets.

### Compliance gotchas

- **Don't gate non-tracking features** behind ATT acceptance. Apple rejects apps that withhold core functionality from users who decline.
- **Don't repeatedly re-prompt** after a `.denied` result. The dialog can only be shown once until the user manually re-enables in Settings.
- **Don't call `requestTrackingAuthorization()` cold.** Show a pre-prompt explaining the value, then trigger the system prompt. Conversion is dramatically higher.
- **Don't use IDFV (`identifierForVendor`) as a tracking proxy.** That's an explicit policy violation even though the API itself isn't gated.

### IDFV — the underused alternative

```swift
let idfv = UIDevice.current.identifierForVendor?.uuidString
```

`identifierForVendor` is per-vendor (your team) and persistent within installs of *your* apps. No ATT prompt required. Use it for first-party analytics correlation — that's what it's for.

---

## 3. Background Work

Background execution on iOS is heavily constrained. The big buckets:

| Mode | What it does | Capability key | Approval bar |
|---|---|---|---|
| Background fetch (legacy) | Wake periodically to fetch | `fetch` | Easy — but heavily throttled now, prefer BGAppRefreshTask |
| BGAppRefreshTask | Short refresh task | `processing` (in Info.plist's `BGTaskSchedulerPermittedIdentifiers`) | Easy |
| BGProcessingTask | Long-running maintenance (cleanup, ML training) | `processing` | Easy |
| Silent push (`content-available: 1`) | Wake via push to do quick work | `remote-notification` | Easy if used sparingly |
| Voice over IP | Maintain VoIP socket | `voip` | Heavy review |
| Audio | Background audio playback | `audio` | Easy if app is genuinely audio-first |
| Location | Background location updates | `location` | Heavy review for "always" |

### BGTaskScheduler — the modern way

Register identifiers in `Info.plist`:

```xml
<key>BGTaskSchedulerPermittedIdentifiers</key>
<array>
    <string>com.example.myapp.refresh</string>
    <string>com.example.myapp.cleanup</string>
</array>
```

Register handlers at app launch (early — must be in `application(_:didFinishLaunchingWithOptions:)` or your `App` init):

```swift
import BackgroundTasks

@main
struct MyApp: App {
    init() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.example.myapp.refresh",
            using: nil                                  // run on a background queue
        ) { task in
            handleAppRefresh(task: task as! BGAppRefreshTask)
        }
    }
    var body: some Scene { WindowGroup { ContentView() } }
}

func handleAppRefresh(task: BGAppRefreshTask) {
    scheduleNextRefresh()                               // chain immediately

    let work = Task {
        do {
            try await refreshFeed()
            task.setTaskCompleted(success: true)
        } catch {
            task.setTaskCompleted(success: false)
        }
    }

    task.expirationHandler = { work.cancel() }
}

func scheduleNextRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: "com.example.myapp.refresh")
    request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)    // 15 minutes
    try? BGTaskScheduler.shared.submit(request)
}
```

Critical operational notes:

- **You don't choose when it runs.** iOS picks the moment based on user behavior, battery, network, etc. `earliestBeginDate` is a *lower bound*.
- **Each task has ~30 seconds** before iOS expects `setTaskCompleted` (BGAppRefreshTask) or up to a few minutes for BGProcessingTask.
- **Set the expiration handler.** If you don't, iOS will kill your process and possibly mark your app as misbehaving (less frequent scheduling).
- **Always re-schedule from inside the handler.** Otherwise the task only ever runs once.
- **Test from Xcode**: pause the debugger, then run in lldb:
  ```
  e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.example.myapp.refresh"]
  ```
  This is the only realistic way to verify the handler runs.

### Silent push for "wake me when something happens"

```json
{
  "aps": { "content-available": 1 },
  "payload": "..."
}
```

Server sends a push with `content-available: 1` and **no alert, sound, or badge**. iOS wakes your app in the background. Implement:

```swift
import UIKit

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable : Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        Task {
            let result = await fetchUpdates()
            completionHandler(result ? .newData : .noData)
        }
    }
}
```

Required capability in `Info.plist`:

```xml
<key>UIBackgroundModes</key>
<array>
    <string>remote-notification</string>
</array>
```

iOS rate-limits silent push aggressively (no more than ~2-3 per hour for most apps). Don't design around delivery guarantees.

---

## 4. Push Notifications (Visible)

For user-visible notifications:

```swift
import UserNotifications

@MainActor
final class PushManager: NSObject, UNUserNotificationCenterDelegate {
    func register() async throws {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
        guard granted else { return }
        await UIApplication.shared.registerForRemoteNotifications()
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .badge]                      // show in-foreground too
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        // user tapped — handle deep link
    }
}
```

The device token comes from your `AppDelegate`:

```swift
func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
) {
    let token = deviceToken.map { String(format: "%02x", $0) }.joined()
    Task { try await api.registerPushToken(token) }
}

func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
) {
    // Common cause in dev: Push capability not enabled, or APNs sandbox vs prod mismatch.
}
```

### Provisioning gotchas

- **Push needs the "Push Notifications" capability** turned on in Xcode → Signing & Capabilities. This adds an entitlement and APNs key requirements.
- **Sandbox vs production APNs.** Builds installed via Xcode use sandbox APNs; TestFlight/App Store builds use production APNs. Tokens from the two environments are not interchangeable. Your server must talk to the right environment per build flavor.
- **Token rotation.** Tokens can change after iOS upgrades, restoring from backup, etc. Re-register on every cold launch.

---

## 5. App Groups & Shared State

App Groups let your app share state with **app extensions** (Share Extension, Today widgets, WidgetKit widgets, Notification Service Extensions, etc.) and with **other apps from the same team ID**.

### Setup

1. Apple Developer Portal → Certificates → Identifiers → App IDs → Edit each App ID → enable **App Groups**.
2. Create a group: typically `group.com.yourteam.yourapp`.
3. Xcode → Signing & Capabilities → **App Groups** → check the new group on every target that needs it.
4. The entitlement `com.apple.security.application-groups` gets added automatically.

### Shared `UserDefaults`

```swift
let shared = UserDefaults(suiteName: "group.com.yourteam.yourapp")!
shared.set("dark", forKey: "theme")
let theme = shared.string(forKey: "theme")
```

**Pitfalls:**
- This is *not* the same as `UserDefaults.standard`. Code that reads `.standard` won't see `.suiteName(...)` writes. Use one consistently per data domain.
- Concurrent writes from app + extension can race. Treat shared `UserDefaults` as eventually-consistent, not transactional.

### Shared file container

```swift
let container = FileManager.default.containerURL(
    forSecurityApplicationGroupIdentifier: "group.com.yourteam.yourapp"
)!
let logURL = container.appendingPathComponent("shared.log")
try data.write(to: logURL)
```

### Shared Keychain (`kSecAttrAccessGroup`)

```swift
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "MyService",
    kSecAttrAccessGroup as String: "TEAMID.com.yourteam.shared",   // ← team-prefixed
    kSecValueData as String: secret.data(using: .utf8)!,
]
SecItemAdd(query as CFDictionary, nil)
```

Add the keychain access group to `<AppTarget>.entitlements`:

```xml
<key>keychain-access-groups</key>
<array>
    <string>$(AppIdentifierPrefix)com.yourteam.shared</string>
</array>
```

`$(AppIdentifierPrefix)` resolves to your team ID + `.` at build time.

---

## 6. Entitlements: Mental Model

Entitlements are runtime permissions baked into your code-signed app. They live in `<AppTarget>.entitlements` (an XML plist) and Xcode adds them automatically when you toggle capabilities.

| Entitlement | What it unlocks |
|---|---|
| `com.apple.developer.applesignin` | Sign in with Apple |
| `com.apple.developer.associated-domains` | Universal Links, Web Credentials |
| `com.apple.developer.healthkit` | HealthKit |
| `com.apple.developer.in-app-payments` | Apple Pay |
| `com.apple.developer.networking.wifi-info` | Read SSID |
| `com.apple.developer.usernotifications.communication` | Communication Notifications API |
| `aps-environment` | Push notifications (`development` or `production`) |
| `com.apple.security.application-groups` | App Groups |
| `keychain-access-groups` | Shared Keychain |
| `com.apple.developer.icloud-services` | iCloud Documents / Key-Value / CloudKit |

**Common rejection cause:** an entitlement in your built app that isn't enabled on the App ID in the developer portal. The build signs but provisioning fails at install or first launch.

**Diagnostic:** run `codesign -d --entitlements - /path/to/.app` on a built app to see exactly which entitlements are baked in.

---

## 7. The Pre-Submission Checklist

Treat this as a hard gate before each App Store submission:

### Privacy

- [ ] `PrivacyInfo.xcprivacy` exists in app target.
- [ ] All required-reason API categories your app uses are declared with valid reason codes.
- [ ] Each third-party SDK you bundle has its own up-to-date manifest.
- [ ] App Store Connect → App Privacy data-collection survey matches the manifest.
- [ ] All `NS*UsageDescription` strings in `Info.plist` are specific and user-friendly.

### Tracking

- [ ] If you use IDFA, you call `ATTrackingManager.requestTrackingAuthorization()` at the right moment, **not** at first launch.
- [ ] `NSUserTrackingUsageDescription` is set and explains the value.
- [ ] No core feature is gated behind ATT acceptance.

### Background

- [ ] Every BGTaskScheduler identifier in code is listed in `Info.plist`'s `BGTaskSchedulerPermittedIdentifiers`.
- [ ] Every handler sets `task.expirationHandler` and re-schedules itself.
- [ ] Background modes in `Info.plist` (audio, location, etc.) match what the App Review team would expect from your app's user-facing features.

### Push

- [ ] Push capability enabled in Xcode and on the App ID.
- [ ] APNs key (or cert) configured in your push server, **per-environment** (sandbox + production).
- [ ] Server tolerates `BadDeviceToken` and re-prompts re-registration when needed.
- [ ] `aps-environment` entitlement is `production` for App Store builds (Xcode does this automatically with proper provisioning).

### App Groups & Sharing

- [ ] Each target that needs shared data has the group entitlement.
- [ ] Code uses `UserDefaults(suiteName:)` not `.standard` for shared keys.
- [ ] Shared Keychain access group string matches across app and extensions.

### Code-signing & entitlements

- [ ] `codesign -d --entitlements - MyApp.app` shows only entitlements you've enabled on the App ID.
- [ ] Build configuration is **Release**, **not** Debug, for archive uploads.

### Symbolication / debugging

- [ ] dSYMs uploaded to your crash-reporter (Sentry, Firebase Crashlytics, App Store Connect).
- [ ] BitCode is *not* enabled (deprecated since Xcode 14; should be off).

---

## 8. Common Rejection Patterns

From years of App Review feedback aggregated across the developer community:

| Rejection reason | Root cause | Fix |
|---|---|---|
| "Privacy manifest doesn't account for X API usage" | Required-reason category or reason code missing | Add the relevant category + valid reason code |
| "App Privacy section doesn't match disclosed data collection" | Manifest and App Store Connect disagree | Reconcile both; manifest is source of truth |
| "ATT permission requested without sufficient context" | Cold prompt, vague description | Pre-prompt with value-prop screen first |
| "Background modes used without justification" | "location" capability with no obvious user need | Disable, or rewrite app description to explain |
| "Token / push abuse" | Sending non-user-facing pushes too frequently | Move to BGAppRefreshTask or silent push w/ rate awareness |
| "Encryption export compliance" | First app with strong crypto, no `ITSAppUsesNonExemptEncryption` | Add the key + answer survey at submission |
| "Sign in with Apple required but not present" | Offering a 3rd-party social login w/o SiwA | Add SiwA as an option |

---

## Companion chapters

- [Security & Privacy](../08-security/security-guide.md) — Keychain, ATS, Sign in with Apple in code.
- [Deployment & Distribution](deployment-guide.md) — TestFlight, App Store Connect, CI/CD.
- [Maintenance & Dependencies](../10-maintenance/maintenance-guide.md) — third-party SDK privacy-manifest auditing during dependency updates.
- [Persistence](../03-architecture/persistence.md) — App Group containers as a SwiftData / Core Data store backing.

**Next:** [Maintenance & Dependencies](../10-maintenance/maintenance-guide.md).

*Last updated: 2026-05-04*
