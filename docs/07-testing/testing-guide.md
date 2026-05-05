# Testing & Debugging

> Testing on iOS uses XCTest (built into Xcode) instead of Jest/Vitest. Debugging uses Xcode's debugger and Instruments instead of Chrome DevTools. The concepts are the same — the tools are different.

---

## Test Framework Comparison

| Web (Jest / Vitest) | iOS (XCTest) |
|---|---|
| `describe("Suite", () => {})` | `class MyTests: XCTestCase {}` |
| `it("should do X", () => {})` | `func testShouldDoX() {}` |
| `expect(value).toBe(5)` | `XCTAssertEqual(value, 5)` |
| `expect(value).toBeTruthy()` | `XCTAssertTrue(value)` |
| `expect(fn).toThrow()` | `XCTAssertThrowsError(try fn())` |
| `beforeEach(() => {})` | `override func setUp() {}` |
| `afterEach(() => {})` | `override func tearDown() {}` |
| `jest.fn()` / `vi.fn()` | Protocol-based mocks (no built-in mocking) |

---

## Unit Tests

```swift
import XCTest
@testable import MyApp

final class ArticleTests: XCTestCase {
    
    // setUp runs before each test (like beforeEach)
    override func setUp() {
        super.setUp()
    }
    
    func testArticleDecoding() throws {
        let json = """
        {"id": "1", "title": "Hello", "body": "World", "published_at": "2026-01-01T00:00:00Z"}
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        
        let article = try decoder.decode(Article.self, from: json)
        
        XCTAssertEqual(article.id, "1")
        XCTAssertEqual(article.title, "Hello")
        XCTAssertEqual(article.body, "World")
    }
    
    func testArticleFormattedDate() {
        let article = Article(
            id: "1",
            title: "Test",
            body: "Body",
            publishedAt: Date(timeIntervalSince1970: 0)
        )
        
        XCTAssertFalse(article.formattedDate.isEmpty)
    }
}
```

### Async Tests

```swift
func testFetchArticles() async throws {
    let service = ArticleService(client: MockAPIClient())
    let articles = try await service.fetchAll()
    XCTAssertEqual(articles.count, 3)
    XCTAssertEqual(articles.first?.title, "Mock Article 1")
}
```

### Testing with Mocks (Protocol-Based)

Swift doesn't have built-in mocking like Jest. Instead, you define protocols and create mock implementations.

```swift
// Define the protocol
protocol ArticleServiceProtocol {
    func fetchAll() async throws -> [Article]
}

// Real implementation
struct ArticleService: ArticleServiceProtocol {
    func fetchAll() async throws -> [Article] {
        try await APIClient.shared.get("/articles")
    }
}

// Mock for tests
struct MockArticleService: ArticleServiceProtocol {
    var mockArticles: [Article] = []
    var shouldThrow = false
    
    func fetchAll() async throws -> [Article] {
        if shouldThrow { throw APIError.httpError(status: 500, body: nil) }
        return mockArticles
    }
}

// Test with mock
func testViewModelLoadsArticles() async {
    let mock = MockArticleService(mockArticles: [
        Article(id: "1", title: "Test", body: "Body", publishedAt: .now)
    ])
    let viewModel = ArticleListViewModel(service: mock)
    
    await viewModel.load()
    
    XCTAssertEqual(viewModel.articles.count, 1)
    XCTAssertFalse(viewModel.isLoading)
}
```

---

## UI Tests

UI tests automate tapping, typing, and asserting on the actual app UI. Like Playwright/Cypress but for iOS.

```swift
import XCTest

final class ArticleFlowUITests: XCTestCase {
    let app = XCUIApplication()
    
    override func setUp() {
        continueAfterFailure = false
        app.launch()
    }
    
    func testArticleListShowsArticles() {
        // Wait for content to load
        let firstArticle = app.staticTexts["Hello World"]
        XCTAssertTrue(firstArticle.waitForExistence(timeout: 5))
    }
    
    func testTapArticleShowsDetail() {
        let firstArticle = app.staticTexts["Hello World"]
        XCTAssertTrue(firstArticle.waitForExistence(timeout: 5))
        firstArticle.tap()
        
        // Verify detail screen
        XCTAssertTrue(app.staticTexts["Article Detail"].exists)
        XCTAssertTrue(app.staticTexts["Hello World"].exists)
    }
    
    func testPullToRefresh() {
        let list = app.collectionViews.firstMatch
        XCTAssertTrue(list.waitForExistence(timeout: 5))
        
        list.swipeDown() // Pull to refresh
        
        // Verify loading indicator appeared
        // ...
    }
}
```

### Accessibility Identifiers (Like data-testid)

```swift
// In your SwiftUI view (like adding data-testid)
Text("Hello World")
    .accessibilityIdentifier("article-title")

// In your UI test
let title = app.staticTexts["article-title"]
XCTAssertTrue(title.exists)
```

---

## Snapshot / Preview Tests

SwiftUI previews serve as visual regression tests. For automated snapshot testing, use the **swift-snapshot-testing** library:

```swift
import SnapshotTesting
import XCTest
@testable import MyApp

final class ViewSnapshotTests: XCTestCase {
    func testArticleRow() {
        let view = ArticleRow(article: .sample)
        assertSnapshot(of: view, as: .image(layout: .fixed(width: 375, height: 100)))
    }
    
    func testArticleRowDarkMode() {
        let view = ArticleRow(article: .sample)
            .preferredColorScheme(.dark)
        assertSnapshot(of: view, as: .image(layout: .fixed(width: 375, height: 100)))
    }
}
```

---

## Running Tests

```bash
# From Xcode
# ⌘U — Run all tests
# Click the diamond next to a test function — Run single test

# From command line
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
    | xcpretty  # Optional: pretty-print output (install via gem)
```

---

## Debugging

### Xcode Debugger (Like Chrome DevTools)

| Chrome DevTools | Xcode Equivalent |
|---|---|
| `console.log()` | `print()` (appears in Xcode console) |
| Breakpoints panel | Click line gutter to set breakpoints |
| Watch expressions | Variables view (bottom left in debug) |
| Network tab | Use `URLSession` logging or Instruments |
| Elements inspector | Xcode View Hierarchy Debugger (Debug → View Debugging → Capture View Hierarchy) |
| Performance tab | Instruments (see below) |

### LLDB Debugger Commands

When paused at a breakpoint, use the debug console:

```
(lldb) po myVariable              // Print object (like console.log)
(lldb) p myVariable               // Print with type info
(lldb) expression myVar = 42      // Change a value at runtime
(lldb) bt                         // Backtrace (stack trace)
```

### View Hierarchy Debugger

Xcode can show a 3D exploded view of your UI hierarchy — like the Elements inspector in Chrome DevTools but in 3D. Access via **Debug → View Debugging → Capture View Hierarchy** or the button in the debug toolbar.

---

## Instruments (Performance Profiling)

Instruments is Xcode's profiling suite — like Chrome's Performance tab but much more detailed.

| What to measure | Instrument | Web equivalent |
|---|---|---|
| CPU usage | Time Profiler | Performance tab flame chart |
| Memory leaks | Leaks / Allocations | Memory tab |
| Network requests | Network | Network tab |
| UI rendering | Core Animation | Paint flashing |
| Energy impact | Energy Log | Lighthouse |
| Disk I/O | File Activity | — |

```bash
# Open Instruments
open -a Instruments

# Or from Xcode: Product → Profile (⌘I)
```

### Common Performance Issues

1. **Doing work on the main thread** — Network calls, JSON parsing, or heavy computation blocks the UI. Use `Task` or `Task.detached` for background work.
2. **Excessive view redraws** — SwiftUI redraws views when state changes. Use `@Observable` (not `@Published`) and keep state granular.
3. **Large image loading** — Decode images off the main thread. Use `AsyncImage` or a caching library.
4. **Memory leaks from closures** — Capture `[weak self]` in closures that reference `self` in classes.

---

## Debugging WebView Content

If you're shipping a Wrap or Bridge app, you can debug your web content inside WKWebView using Safari:

1. On your Mac: **Safari → Settings → Advanced → Show Develop menu**
2. On Simulator/device: **Settings → Safari → Advanced → Web Inspector** (ON)
3. Run your app, then in Safari: **Develop → Simulator → your page**
4. Full Safari DevTools appear — console, network, elements, everything

This is critical for debugging the JavaScript bridge between your web app and native code.

---

**Next:** [Security & Privacy](../08-security/security-guide.md) — iOS security requirements.

*Last updated: 2026-04-25*
