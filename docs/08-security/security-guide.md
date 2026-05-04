# Security & Privacy

> iOS security is stricter than web security by default. Apple enforces policies at the OS level that you'd normally opt into on the web. This guide covers what's mandatory, what's different, and what you get for free.

---

## Web vs. iOS Security Model

| Web | iOS |
|---|---|
| HTTPS optional (but expected) | HTTPS mandatory (App Transport Security) |
| localStorage / cookies | Keychain (encrypted, hardware-backed) |
| CORS policies | App sandboxing (full filesystem isolation) |
| Content Security Policy | App-level permissions (per API) |
| OAuth in browser | ASWebAuthenticationSession (system-managed) |
| No biometric auth standard | Face ID / Touch ID (LocalAuthentication framework) |

The key shift: on the web, security is largely opt-in. On iOS, it's enforced by the OS and App Store review.

---

## App Transport Security (ATS)

ATS is iOS's built-in HTTPS enforcement. All network requests must use HTTPS by default — no exceptions without explicit configuration.

```xml
<!-- Info.plist — DO NOT add these unless absolutely necessary -->

<!-- Disable ATS entirely (App Store may reject this) -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>

<!-- Allow specific HTTP domains (for legacy APIs only) -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSExceptionDomains</key>
    <dict>
        <key>legacy-api.example.com</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
        </dict>
    </dict>
</dict>
```

**Best practice:** Don't disable ATS. If your API doesn't support HTTPS, fix the API. App Store reviewers will ask why you disabled it.

---

## Keychain (Secure Token Storage)

On the web, you store tokens in localStorage (insecure) or httpOnly cookies (better). On iOS, use the **Keychain** — it's encrypted at the hardware level and survives app reinstalls.

```swift
import Security

enum KeychainHelper {
    
    static func save(_ value: String, forKey key: String) throws {
        guard let data = value.data(using: .utf8) else { return }
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        
        // Delete existing item first
        SecItemDelete(query as CFDictionary)
        
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.unhandled(status: status)
        }
    }
    
    static func read(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    
    static func delete(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

### Keychain Accessibility Levels

| Level | When accessible | Use for |
|---|---|---|
| `kSecAttrAccessibleAfterFirstUnlock` | After first device unlock | Auth tokens, API keys (recommended default) |
| `kSecAttrAccessibleWhenUnlocked` | Only when device is unlocked | Sensitive user data |
| `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` | Only with passcode, this device | Highest security items |

---

## Biometric Authentication (Face ID / Touch ID)

```swift
import LocalAuthentication

func authenticateWithBiometrics() async -> Bool {
    let context = LAContext()
    var error: NSError?
    
    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
        print("Biometrics not available: \(error?.localizedDescription ?? "")")
        return false
    }
    
    do {
        let success = try await context.evaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            localizedReason: "Authenticate to access your account"
        )
        return success
    } catch {
        print("Authentication failed: \(error.localizedDescription)")
        return false
    }
}
```

**Required Info.plist entry:**
```xml
<key>NSFaceIDUsageDescription</key>
<string>We use Face ID to securely authenticate you.</string>
```

---

## App Permissions

Unlike the web (where you can access many APIs without asking), iOS requires explicit user permission for sensitive capabilities.

### Permission Request Pattern

```swift
import PhotosUI
import AVFoundation
import CoreLocation

// Camera
AVCaptureDevice.requestAccess(for: .video) { granted in
    if granted { /* use camera */ }
}

// Photos
PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
    switch status {
    case .authorized: /* full access */
    case .limited:    /* user selected specific photos */
    case .denied:     /* user said no */
    default: break
    }
}

// Location
let manager = CLLocationManager()
manager.requestWhenInUseAuthorization() // or requestAlwaysAuthorization()
```

### Required Info.plist Descriptions

Every permission requires a human-readable description. Apple rejects apps with missing or vague descriptions.

```xml
<key>NSCameraUsageDescription</key>
<string>We need camera access to scan documents.</string>

<key>NSPhotoLibraryUsageDescription</key>
<string>We need photo access to let you upload images.</string>

<key>NSLocationWhenInUseUsageDescription</key>
<string>We use your location to show nearby results.</string>

<key>NSMicrophoneUsageDescription</key>
<string>We need microphone access for voice messages.</string>
```

**Be specific.** "We need access to your photos" will get rejected. "We need photo access to let you set a profile picture" will pass.

---

## Privacy Manifest (Required Since 2024)

> **Operational reference:** [App Store Operations](../09-deployment/app-store-operations.md) covers the full privacy-manifest workflow (required-reason API categories, reason codes, App Store Connect survey reconciliation, third-party SDK aggregation). This section is the quick orientation; the operational chapter is what you reach for when preparing a submission.

Apple now requires apps to declare what data they collect and what APIs they use. This is a `PrivacyInfo.xcprivacy` file in your app bundle.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
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
    </array>
</dict>
</plist>
```

---

## OAuth / Sign in with Apple

For third-party authentication, use `ASWebAuthenticationSession` (system-managed browser) instead of embedding login pages in a WebView.

```swift
import AuthenticationServices

func signInWithOAuth() async throws -> String {
    let authURL = URL(string: "https://auth.provider.com/authorize?client_id=xxx&redirect_uri=myapp://callback")!
    let callbackScheme = "myapp"
    
    return try await withCheckedThrowingContinuation { continuation in
        let session = ASWebAuthenticationSession(
            url: authURL,
            callbackURLScheme: callbackScheme
        ) { callbackURL, error in
            if let error {
                continuation.resume(throwing: error)
                return
            }
            guard let token = callbackURL?.queryItems?["token"] else {
                continuation.resume(throwing: AuthError.noToken)
                return
            }
            continuation.resume(returning: token)
        }
        session.prefersEphemeralWebBrowserSession = true
        session.start()
    }
}
```

### Sign in with Apple (Required If You Support Social Login)

If your app offers any third-party sign-in (Google, Facebook, etc.), Apple **requires** you to also offer Sign in with Apple.

```swift
import AuthenticationServices

struct SignInWithAppleButton: View {
    var body: some View {
        SignInWithAppleButton(.signIn) { request in
            request.requestedScopes = [.email, .fullName]
        } onCompletion: { result in
            switch result {
            case .success(let auth):
                if let credential = auth.credential as? ASAuthorizationAppleIDCredential {
                    let userId = credential.user
                    let email = credential.email
                    let identityToken = credential.identityToken
                    // Send to your backend
                }
            case .failure(let error):
                print("Sign in failed: \(error)")
            }
        }
        .frame(height: 50)
        .padding()
    }
}
```

---

## Data Protection Best Practices

1. **Never store secrets in code** — Use xcconfig files or the Keychain. Strings in your binary can be extracted.
2. **Don't log sensitive data** — `print()` statements with tokens or PII will appear in device logs.
3. **Use HTTPS everywhere** — ATS enforces this, but also validate certificates in production.
4. **Clear sensitive data on logout** — Delete Keychain entries, clear in-memory caches.
5. **Encrypt local databases** — If using SQLite directly, enable encryption. Core Data encryption requires manual setup.

---

**Next:** [Deployment & Distribution](../09-deployment/deployment-guide.md) — Getting your app to users.

*Last updated: 2026-04-25*
