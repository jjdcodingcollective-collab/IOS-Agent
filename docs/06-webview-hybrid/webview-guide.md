# WebView & Hybrid Integration

> This is the most directly relevant guide for your transition. You have a working web app on Vercel — this section covers how to embed it in a native iOS shell, bridge JavaScript and Swift, and progressively migrate to native screens.

---

## Strategy Overview

```
Your Vercel App (web)
        │
        ▼
┌───────────────────────┐
│   iOS Native Shell    │
│  ┌─────────────────┐  │
│  │   WKWebView     │  │  ← Your web app runs here
│  │  (your web app) │  │
│  └────────┬────────┘  │
│           │            │
│  Native Features:      │
│  • Push notifications  │
│  • Camera access       │
│  • Biometrics          │
│  • App Store presence  │
└───────────────────────┘
```

---

## Basic WKWebView Setup

This loads your Vercel-deployed web app inside a native iOS shell — the foundation of Wrap mode.

```swift
import SwiftUI
import WebKit

struct WebAppView: UIViewRepresentable {
    let url: URL
    
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        
        // Enable JavaScript
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        
        // Allow inline media playback (important for video)
        config.allowsInlineMediaPlayback = true
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.load(URLRequest(url: url))
        
        return webView
    }
    
    func updateUIView(_ webView: WKWebView, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("Navigation failed: \(error.localizedDescription)")
        }
    }
}

// Usage in your app
struct ContentView: View {
    var body: some View {
        WebAppView(url: URL(string: "https://your-app.vercel.app")!)
            .ignoresSafeArea()
    }
}
```

---

## JavaScript ↔ Swift Bridge

The most powerful feature of WKWebView — you can call Swift from JavaScript and JavaScript from Swift.

### Swift → JavaScript

```swift
// Execute any JS in the web view
func evaluateJS(_ webView: WKWebView) async {
    do {
        let result = try await webView.evaluateJavaScript("document.title")
        print("Page title: \(result)")
    } catch {
        print("JS evaluation failed: \(error)")
    }
    
    // Call a function in your web app
    try await webView.evaluateJavaScript("""
        window.nativeBridge.onTokenReceived('\(pushToken)')
    """)
}
```

### JavaScript → Swift (Message Handlers)

This is how your web app sends data to the native layer.

```swift
// 1. Set up the message handler in Swift
class WebBridgeHandler: NSObject, WKScriptMessageHandler {
    var onMessage: ((String, Any) -> Void)?
    
    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        onMessage?(message.name, message.body)
    }
}

// 2. Register handlers when creating the WebView
func makeUIView(context: Context) -> WKWebView {
    let config = WKWebViewConfiguration()
    let handler = WebBridgeHandler()
    
    handler.onMessage = { name, body in
        switch name {
        case "shareContent":
            // Handle share from web
            if let data = body as? [String: String] {
                NativeFeatures.share(text: data["text"] ?? "")
            }
        case "hapticFeedback":
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        case "openCamera":
            // Trigger native camera
            break
        default:
            break
        }
    }
    
    config.userContentController.add(handler, name: "shareContent")
    config.userContentController.add(handler, name: "hapticFeedback")
    config.userContentController.add(handler, name: "openCamera")
    
    // ...
}
```

```javascript
// 3. In your web app (React/Next.js), call the native handler
// utils/native-bridge.js

export function isRunningInNativeApp() {
  return window.webkit?.messageHandlers !== undefined;
}

export function shareContent(text) {
  if (isRunningInNativeApp()) {
    window.webkit.messageHandlers.shareContent.postMessage({ text });
  } else {
    // Fallback: use Web Share API or clipboard
    navigator.share?.({ text }) || navigator.clipboard.writeText(text);
  }
}

export function triggerHaptic() {
  if (isRunningInNativeApp()) {
    window.webkit.messageHandlers.hapticFeedback.postMessage({});
  }
}

export function openCamera() {
  if (isRunningInNativeApp()) {
    window.webkit.messageHandlers.openCamera.postMessage({});
  }
}
```

---

## Injecting Native Context into Your Web App

Pass information from the native layer into your web app on load.

```swift
// Inject a script before pages load
let userScript = WKUserScript(
    source: """
        window.__NATIVE_CONTEXT__ = {
            platform: 'ios',
            appVersion: '\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] ?? "")',
            deviceModel: '\(UIDevice.current.model)',
            pushToken: '\(pushToken ?? "")',
            userId: '\(currentUserId ?? "")'
        };
    """,
    injectionTime: .atDocumentStart,
    forMainFrameOnly: true
)
config.userContentController.addUserScript(userScript)
```

```javascript
// In your web app, check for native context
if (window.__NATIVE_CONTEXT__?.platform === "ios") {
  console.log("Running in native app, version:", window.__NATIVE_CONTEXT__.appVersion);
  // Enable native-only features
  enableHaptics();
  enableNativeShare();
}
```

---

## Handling Navigation

Control which URLs open in the WebView vs. external browser.

```swift
class Coordinator: NSObject, WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        
        // Keep your app's URLs in the WebView
        if url.host == "your-app.vercel.app" || url.host == "your-production-domain.com" {
            decisionHandler(.allow)
            return
        }
        
        // Open external links in Safari
        UIApplication.shared.open(url)
        decisionHandler(.cancel)
    }
}
```

---

## Bridge Architecture: Web + Native Screens

This is the Bridge-mode pattern — a progressive migration approach where some screens are web (loaded in WKWebView) and some are native SwiftUI. New code should call this pattern "Bridge" rather than the older "hybrid" label.

```swift
struct HybridApp: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Native screen (already migrated)
            Tab("Home", systemImage: "house", value: 0) {
                NativeHomeView()
            }
            
            // Tab 2: Still web
            Tab("Explore", systemImage: "safari", value: 1) {
                WebAppView(url: URL(string: "https://your-app.vercel.app/explore")!)
            }
            
            // Tab 3: Native screen
            Tab("Profile", systemImage: "person", value: 2) {
                NativeProfileView()
            }
        }
    }
}
```

### Screen-Level Routing

Route between web and native at the screen level:

```swift
enum Screen {
    case nativeHome
    case nativeProfile(userId: String)
    case webScreen(path: String)  // Everything else loads in WebView
}

struct AppRouter: View {
    let screen: Screen
    
    var body: some View {
        switch screen {
        case .nativeHome:
            NativeHomeView()
        case .nativeProfile(let userId):
            NativeProfileView(userId: userId)
        case .webScreen(let path):
            WebAppView(url: URL(string: "https://your-app.vercel.app\(path)")!)
        }
    }
}
```

---

## Handling Offline / Loading States

WebViews fail silently when offline. Add native error handling.

```swift
class Coordinator: NSObject, WKNavigationDelegate {
    @Binding var isLoading: Bool
    @Binding var loadError: Error?
    
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        isLoading = true
        loadError = nil
    }
    
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        isLoading = false
    }
    
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        isLoading = false
        loadError = error
    }
}

// In your view
struct RobustWebView: View {
    @State private var isLoading = true
    @State private var loadError: Error?
    
    var body: some View {
        ZStack {
            WebAppView(url: appURL, isLoading: $isLoading, loadError: $loadError)
            
            if isLoading {
                ProgressView("Loading...")
            }
            
            if let error = loadError {
                ContentUnavailableView(
                    "Can't Load Page",
                    systemImage: "wifi.slash",
                    description: Text("Check your connection and try again")
                )
            }
        }
    }
}
```

---

## Cookie and Session Sharing

If your web app uses cookies for auth, WKWebView manages its own cookie store.

```swift
// Copy cookies from your auth flow into WKWebView
let cookie = HTTPCookie(properties: [
    .domain: "your-app.vercel.app",
    .path: "/",
    .name: "session",
    .value: sessionToken,
    .secure: true,
    .expires: Date().addingTimeInterval(86400 * 30)
])!

let config = WKWebViewConfiguration()
config.websiteDataStore.httpCookieStore.setCookie(cookie)
```

---

## App Store Review Considerations

Apple may reject apps that are "just a website in a wrapper." To pass review:

1. **Add native value** — Push notifications, offline caching, native share sheets, biometric auth
2. **Don't load a generic website** — The content should be specific to your app
3. **Handle offline gracefully** — Show a native error screen, not a blank WebView
4. **Use native navigation** — At minimum, a native tab bar or navigation structure
5. **Respect platform conventions** — Back swipe gesture, safe area insets, dynamic type

---

## Performance Tips

- **Cache web assets locally** — Bundle critical HTML/CSS/JS in the app for instant loading, then sync updates
- **Preload the WebView** — Initialize it before the user navigates to the web screen
- **Minimize bridge calls** — Batch messages between JS and Swift
- **Use `WKWebView`, never `UIWebView`** — UIWebView is deprecated and will be rejected by App Store

---

**Next:** [Testing & Debugging](../07-testing/testing-guide.md) — Testing your iOS app.

*Last updated: 2026-04-25*
