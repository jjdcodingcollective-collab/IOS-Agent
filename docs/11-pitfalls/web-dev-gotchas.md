# Common Pitfalls for Web Developers

> The mistakes every web developer makes when starting iOS development — and how to avoid them. These come from real experience transitioning web teams to native iOS.

---

## 1. Confusing `let` and `var`

**The trap:** In JavaScript, `let` is mutable and `const` is immutable. In Swift, it's reversed — `let` is immutable (like `const`) and `var` is mutable.

```swift
// WRONG (thinking in JavaScript)
let count = 0
count += 1  // ❌ Compiler error: cannot assign to 'let'

// RIGHT
var count = 0
count += 1  // ✅
```

**Rule:** Use `let` by default. Xcode will suggest changing to `var` when you need mutability.

---

## 2. Force-Unwrapping Optionals

**The trap:** Using `!` to unwrap optionals because it compiles. This crashes at runtime if the value is `nil`.

```swift
// DANGEROUS
let user = users.first!          // Crashes if array is empty
let name = json["name"] as! String  // Crashes if key missing or wrong type

// SAFE
guard let user = users.first else {
    // Handle empty case
    return
}

if let name = json["name"] as? String {
    // Use name safely
}
```

**Rule:** Never use `!` except in tests or when you have a genuine invariant you want to crash on. Use `if let`, `guard let`, or `??` (nil coalescing) instead.

---

## 3. Blocking the Main Thread

**The trap:** On the web, async operations are always non-blocking because JavaScript is single-threaded with an event loop. On iOS, you can accidentally block the main (UI) thread with synchronous work.

```swift
// WRONG — blocks UI, causes spinning indicator
func loadData() {
    let data = try! Data(contentsOf: hugeFileURL)  // Synchronous file read
    let items = try! JSONDecoder().decode([Item].self, from: data)
    self.items = items
}

// RIGHT — async, off main thread
func loadData() async {
    do {
        let (data, _) = try await URLSession.shared.data(from: url)
        let items = try JSONDecoder().decode([Item].self, from: data)
        await MainActor.run {
            self.items = items
        }
    } catch {
        // Handle error
    }
}
```

**Rule:** Network requests, file I/O, JSON parsing of large payloads, and image processing should always be async. UI updates must happen on `@MainActor`.

---

## 4. Treating Structs Like Objects

**The trap:** Expecting struct instances to behave like JavaScript objects (reference semantics). Swift structs are **value types** — they're copied on assignment.

```swift
struct Settings {
    var darkMode = false
}

var a = Settings()
var b = a          // b is a COPY, not a reference
b.darkMode = true
print(a.darkMode)  // false — a is unchanged

// If you need shared mutable state, use a class or @Observable
@Observable
class Settings {
    var darkMode = false
}
```

**Rule:** Default to structs for data. Use `@Observable` classes when you need shared mutable state across views.

---

## 5. Not Handling the App Lifecycle

**The trap:** On the web, your app runs as long as the tab is open. On iOS, the system can suspend or terminate your app at any time. Background apps get killed to free memory.

```swift
// Things that WILL happen on iOS:
// - User switches apps → your app is suspended
// - System needs memory → your app is terminated (no warning)
// - User gets a phone call → your app goes to background
// - 30 seconds of background → most tasks are killed

// Handle it:
struct MyApp: App {
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: scenePhase) { oldPhase, newPhase in
            switch newPhase {
            case .active:
                // App is in foreground — refresh data
                break
            case .inactive:
                // App is transitioning (e.g., incoming call)
                break
            case .background:
                // App is in background — save state NOW
                saveState()
            @unknown default:
                break
            }
        }
    }
}
```

**Rule:** Save state when going to background. Refresh data when coming to foreground. Never assume your app is still running.

---

## 6. Ignoring Memory Management

**The trap:** On the web, garbage collection handles memory. On iOS, Swift uses **ARC (Automatic Reference Counting)**, which usually works automatically — but can create memory leaks with retain cycles.

```swift
// MEMORY LEAK — class holds a closure that captures self
class ViewModel {
    var onComplete: (() -> Void)?
    
    func start() {
        onComplete = {
            self.finish()  // ❌ Strong reference cycle: self → closure → self
        }
    }
    
    func finish() { }
}

// FIXED — use [weak self]
func start() {
    onComplete = { [weak self] in
        self?.finish()  // ✅ Weak reference — won't prevent deallocation
    }
}
```

**Rule:** Use `[weak self]` in closures stored on classes (completion handlers, callbacks). You don't need it for SwiftUI views (they're structs) or for non-escaping closures (like `map`, `filter`).

---

## 7. Over-Engineering the Architecture

**The trap:** Bringing heavy web architecture patterns (Redux-style stores, complex DI containers, middleware chains) to a simple iOS app.

```swift
// OVER-ENGINEERED for most iOS apps
// Custom middleware, action dispatchers, reducers, side effects...
// Unless you're building a very complex app, this is overkill

// RIGHT — SwiftUI's built-in tools handle most cases
@Observable
class ArticleViewModel {
    var articles: [Article] = []
    var isLoading = false
    
    func load() async {
        isLoading = true
        defer { isLoading = false }
        articles = (try? await ArticleService.fetchAll()) ?? []
    }
}
```

**Rule:** Start with `@Observable` + simple service layer. Add complexity only when you have a specific problem to solve. SwiftUI's built-in state management is more capable than it looks.

---

## 8. Not Testing on Real Devices

**The trap:** Developing entirely on the Simulator and assuming the app works on real hardware.

**Things that differ on real devices:**
- Performance (Simulator runs on your Mac's CPU — much faster)
- Camera, Bluetooth, NFC, GPS — not available in Simulator
- Memory pressure — real devices have less RAM
- Thermal throttling — sustained workloads slow down real devices
- Push notifications — different setup required
- Code signing — must be correctly configured

**Rule:** Test on a real device before every TestFlight upload. Always test performance-sensitive features on the oldest device you support.

---

## 9. Putting Everything in One File

**The trap:** Writing an entire screen in one massive file like a complex React component.

```swift
// WRONG — 500-line view file
struct HomeView: View {
    // ... 20 @State variables
    // ... 15 computed properties
    // ... 10 methods
    
    var body: some View {
        // ... 300 lines of nested views
    }
}

// RIGHT — break it down
struct HomeView: View {
    @State private var viewModel = HomeViewModel()
    
    var body: some View {
        VStack {
            HeaderSection(user: viewModel.user)
            ArticleList(articles: viewModel.articles)
            QuickActions(onAction: viewModel.handleAction)
        }
        .task { await viewModel.load() }
    }
}
```

**Rule:** Extract subviews early. A SwiftUI view's `body` should ideally be under 30-40 lines. Xcode previews work best with small, focused views.

---

## 10. Ignoring Accessibility

**The trap:** Web developers sometimes add ARIA labels as an afterthought. On iOS, accessibility is deeply integrated and Apple's review team may flag issues.

```swift
// SwiftUI has excellent accessibility built in
// Most standard controls are accessible by default

// Add labels to custom views
Image(systemName: "heart.fill")
    .accessibilityLabel("Favorite")

// Group related elements
VStack {
    Text("John Doe")
    Text("Software Engineer")
}
.accessibilityElement(children: .combine) // VoiceOver reads as one element

// Support Dynamic Type (users who increase text size)
// Use system fonts — they scale automatically
Text("Title")
    .font(.headline)  // ✅ Scales with user settings

Text("Title")
    .font(.system(size: 18))  // ⚠️ Doesn't scale — use sparingly
```

**Rule:** Use semantic fonts (`.headline`, `.body`, `.caption`), add accessibility labels to images and icons, and test with VoiceOver at least once before shipping.

---

## 11. Treating Network as Always Available

**The trap:** On the web, you often assume connectivity. On mobile, users go through tunnels, have spotty cell service, and switch between Wi-Fi and cellular.

```swift
import Network

// Monitor connectivity
let monitor = NWPathMonitor()
monitor.pathUpdateHandler = { path in
    if path.status == .satisfied {
        print("Connected")
    } else {
        print("No connection")
    }
}
monitor.start(queue: DispatchQueue.global())

// In your views — show offline state
struct ContentView: View {
    @State private var isOffline = false
    
    var body: some View {
        if isOffline {
            ContentUnavailableView(
                "You're Offline",
                systemImage: "wifi.slash",
                description: Text("Check your connection and try again")
            )
        } else {
            MainContent()
        }
    }
}
```

**Rule:** Always handle the offline case. Cache critical data locally. Show meaningful offline states, not blank screens.

---

## 12. Not Understanding App Store Rejection Reasons

**The trap:** Submitting an app without understanding Apple's guidelines, then being surprised by rejection.

**Top rejection reasons for web-to-iOS apps:**
1. App is just a website wrapper with no native value
2. Crashes on specific devices or iOS versions
3. Missing privacy policy or usage descriptions
4. Login required but no demo credentials provided for reviewers
5. Broken links or placeholder content
6. Performance issues (slow loading, unresponsive UI)

**Rule:** Read the [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) at least once. Provide App Review notes with test credentials. Test on multiple device sizes.

---

## Quick Recovery Guide

| Problem | Quick Fix |
|---|---|
| "Build failed" with no clear error | Clean Build Folder (⌘⇧K), restart Xcode |
| Simulator won't start | `xcrun simctl shutdown all`, then restart |
| Packages won't resolve | File → Packages → Reset Package Caches |
| Signing error | Xcode → Settings → Accounts → re-download profiles |
| Preview won't render | Clean build, restart Xcode, check for compilation errors |
| "No such module" error | Clean, resolve packages, ensure target membership is correct |
| App crashes on launch with no log | Check device console in Xcode → Devices for crash log |

---

**Back to:** [README](../../README.md)

*Last updated: 2026-04-25*
