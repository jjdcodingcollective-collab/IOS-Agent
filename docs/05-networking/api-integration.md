# Networking & API Integration

> Your backend APIs don't change. This guide covers how to call them from Swift instead of JavaScript — URLSession replaces `fetch`, `Codable` replaces manual JSON parsing, and Swift's type system catches API mismatches at compile time.

---

## Basic HTTP Requests

### fetch → URLSession

```javascript
// JavaScript
const response = await fetch("https://api.myapp.com/articles");
const articles = await response.json();
```

```swift
// Swift
guard let url = URL(string: "https://api.myapp.com/articles") else {
    throw APIError.invalidURL
}
let (data, response) = try await URLSession.shared.data(from: url)

guard let httpResponse = response as? HTTPURLResponse else {
    throw APIError.invalidResponse
}
guard httpResponse.statusCode == 200 else {
    throw APIError.badStatus(httpResponse.statusCode)
}

let articles = try JSONDecoder().decode([Article].self, from: data)
```

> **Note:** This guide deliberately avoids `try!` and `as!` in sample code (see [Common Pitfalls #2](../11-pitfalls/web-dev-gotchas.md)). The few `URL(...)!` force-unwraps that remain are clearly-marked compile-time-known literals — never trust user input or remote data the same way.

### POST with JSON Body

```javascript
// JavaScript
const response = await fetch("/api/articles", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Hello", body: "World" }),
});
```

```swift
// Swift
var request = URLRequest(url: URL(string: "https://api.myapp.com/articles")!)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.httpBody = try JSONEncoder().encode(CreateArticle(title: "Hello", body: "World"))

let (data, response) = try await URLSession.shared.data(for: request)
```

---

## JSON Decoding with Codable

TypeScript parses JSON into `any` and you assert the type. Swift decodes JSON directly into typed structs — mismatches are caught immediately.

```typescript
// TypeScript
interface Article {
  id: string;
  title: string;
  body: string;
  published_at: string;
  author: { name: string; avatar_url: string };
}
const article: Article = await response.json();
```

```swift
// Swift
struct Article: Codable, Identifiable {
    let id: String
    let title: String
    let body: String
    let publishedAt: Date       // Decoded from "published_at" (see below)
    let author: Author
    
    struct Author: Codable {
        let name: String
        let avatarUrl: URL      // Decoded from "avatar_url"
    }
}

// Configure decoder to handle snake_case → camelCase
let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase
decoder.dateDecodingStrategy = .iso8601

let article = try decoder.decode(Article.self, from: jsonData)
```

**Key advantage:** If the API changes a field name or type, your app won't compile. On the web, you'd get a runtime error (or worse, silent `undefined`).

---

## Building an API Client

A structured API client replaces your web app's `fetch` wrapper or axios instance.

```swift
actor APIClient {
    static let shared = APIClient()
    
    private let baseURL = URL(string: "https://api.myapp.com")!
    private let session = URLSession.shared
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .iso8601
        return d
    }()
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()
    
    private var authToken: String?
    
    func setAuthToken(_ token: String?) {
        authToken = token
    }
    
    // Generic request method
    func request<T: Decodable>(
        _ method: String,
        path: String,
        body: (any Encodable)? = nil,
        queryItems: [URLQueryItem]? = nil
    ) async throws -> T {
        var url = baseURL.appending(path: path)
        if let queryItems {
            url.append(queryItems: queryItems)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body {
            request.httpBody = try encoder.encode(body)
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.httpError(
                status: httpResponse.statusCode,
                body: String(data: data, encoding: .utf8)
            )
        }
        
        return try decoder.decode(T.self, from: data)
    }
    
    // Convenience methods
    func get<T: Decodable>(_ path: String, query: [URLQueryItem]? = nil) async throws -> T {
        try await request("GET", path: path, queryItems: query)
    }
    
    func post<T: Decodable>(_ path: String, body: any Encodable) async throws -> T {
        try await request("POST", path: path, body: body)
    }
    
    func put<T: Decodable>(_ path: String, body: any Encodable) async throws -> T {
        try await request("PUT", path: path, body: body)
    }
    
    func delete(_ path: String) async throws {
        let _: EmptyResponse = try await request("DELETE", path: path)
    }
}

struct EmptyResponse: Decodable {}

enum APIError: Error, LocalizedError {
    case invalidResponse
    case httpError(status: Int, body: String?)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let status, let body):
            return "HTTP \(status): \(body ?? "No details")"
        }
    }
}
```

### Using the API Client in Services

```swift
// Service layer (like your web API modules)
struct ArticleService {
    static func fetchAll() async throws -> [Article] {
        try await APIClient.shared.get("/articles")
    }
    
    static func fetch(id: String) async throws -> Article {
        try await APIClient.shared.get("/articles/\(id)")
    }
    
    static func create(_ article: CreateArticle) async throws -> Article {
        try await APIClient.shared.post("/articles", body: article)
    }
}

// In a ViewModel
@Observable
class ArticleListViewModel {
    var articles: [Article] = []
    var isLoading = false
    
    func load() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            articles = try await ArticleService.fetchAll()
        } catch {
            // handle error
        }
    }
}
```

---

## Authentication Patterns

### Token Storage

On the web, you store tokens in localStorage or httpOnly cookies. On iOS, use the **Keychain** — it's encrypted and persists across app launches.

```swift
import Security

struct KeychainHelper {
    static func save(key: String, value: String) throws {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        SecItemDelete(query as CFDictionary) // Remove existing
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }
    
    static func read(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        SecItemCopyMatching(query as CFDictionary, &result)
        guard let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
```

### Auth Flow in Your API Client

```swift
// On login
let tokens: AuthTokens = try await APIClient.shared.post("/auth/login", body: credentials)
try KeychainHelper.save(key: "access_token", value: tokens.accessToken)
await APIClient.shared.setAuthToken(tokens.accessToken)

// On app launch — restore session
if let token = KeychainHelper.read(key: "access_token") {
    await APIClient.shared.setAuthToken(token)
}
```

---

## Handling Loading and Error States

```swift
struct ArticleListView: View {
    @State private var viewModel = ArticleListViewModel()
    
    var body: some View {
        Group {
            switch (viewModel.isLoading, viewModel.articles.isEmpty, viewModel.error) {
            case (true, true, _):
                ProgressView("Loading articles...")
            case (_, _, let error?):
                ContentUnavailableView(
                    "Something went wrong",
                    systemImage: "exclamationmark.triangle",
                    description: Text(error.localizedDescription)
                )
            case (_, true, nil):
                ContentUnavailableView.search // Empty state
            default:
                List(viewModel.articles) { article in
                    ArticleRow(article: article)
                }
                .refreshable {
                    await viewModel.load()
                }
            }
        }
        .task {
            await viewModel.load()
        }
    }
}
```

---

## Image Loading

On the web you use `<img src={url}>`. SwiftUI has `AsyncImage` built in, but for production apps with caching, consider a library.

```swift
// Built-in (no caching between sessions)
AsyncImage(url: article.imageURL) { image in
    image.resizable().scaledToFill()
} placeholder: {
    Rectangle().fill(.gray.opacity(0.2))
}
.frame(height: 200)
.clipped()
```

For production image loading with disk caching, look at **Kingfisher** or **Nuke** (Swift packages — see [Maintenance Guide](../10-maintenance/maintenance-guide.md)).

---

## WebSocket Connections

```swift
// Like new WebSocket() in JavaScript
let task = URLSession.shared.webSocketTask(with: URL(string: "wss://api.myapp.com/ws")!)
task.resume()

// Receive messages
func receiveMessages() async {
    do {
        while true {
            let message = try await task.receive()
            switch message {
            case .string(let text):
                let update = try JSONDecoder().decode(Update.self, from: Data(text.utf8))
                // Handle update
            case .data(let data):
                // Handle binary data
            @unknown default:
                break
            }
        }
    } catch {
        // Connection closed or error
    }
}

// Send messages
try await task.send(.string("{\"type\":\"subscribe\",\"channel\":\"updates\"}"))
```

---

**Next:** [WebView & Hybrid Integration](../06-webview-hybrid/webview-guide.md) — Embedding your existing web app in a native iOS shell.

*Last updated: 2026-04-25*
