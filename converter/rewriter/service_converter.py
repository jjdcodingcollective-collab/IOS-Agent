"""
Service Converter — Converts TypeScript API services (fetch/axios) to Swift service structs.
Generates async methods using URLSession via a shared APIClient pattern.
"""

import re
from .swift_helpers import (
    map_type, to_pascal_case, to_camel_case, swift_header, swift_mark,
    swift_todo, format_swift,
)


def convert_service_file(source: str, relative_path: str, manifest_entry: dict) -> str:
    """
    Convert a TypeScript service file to a Swift service struct.
    Returns the generated Swift code.
    """
    filename = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    service_name = to_pascal_case(filename)
    if not service_name.endswith("Service"):
        service_name += "Service"
    swift_name = f"{service_name}.swift"

    blocks = []
    blocks.append(swift_header(swift_name))
    blocks.append("import Foundation\n")

    # Check if we need to generate the APIClient (only once per project)
    blocks.append(swift_mark("Service"))
    blocks.append("")

    # Extract methods from source
    methods = extract_service_methods(source)

    if methods:
        blocks.append(f"struct {service_name} {{")
        blocks.append("")
        for method in methods:
            blocks.append(convert_service_method(method))
        blocks.append("}")
    else:
        # Fallback: wrap detected API calls from manifest
        api_patterns = [p for p in manifest_entry.get("patterns", []) if p["pattern_type"] == "api_call"]
        blocks.append(f"struct {service_name} {{")
        blocks.append("")
        for p in api_patterns:
            blocks.append(generate_stub_method(p))
        blocks.append("}")

    blocks.append("")
    return format_swift("\n".join(blocks))


# ---------------------------------------------------------------------------
# Method extraction
# ---------------------------------------------------------------------------

def extract_service_methods(source: str) -> list[dict]:
    """Extract service methods from a TS service file."""
    methods = []

    # Pattern: async methodName(params): Promise<ReturnType> { ... axios/fetch call }
    # Match methods in object literals: async getAll(...) { ... }
    method_pattern = re.compile(
        r"async\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*Promise<([^>]+)>)?\s*\{",
        re.MULTILINE,
    )

    for m in method_pattern.finditer(source):
        name = m.group(1)
        params_str = m.group(2).strip()
        return_type = m.group(3)

        # Find the method body (track braces)
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[start:i - 1]

        # Parse parameters
        params = parse_params(params_str) if params_str else []

        # Detect HTTP method and URL
        http_method, url = detect_http_call(body)

        methods.append({
            "name": name,
            "params": params,
            "return_type": return_type,
            "http_method": http_method,
            "url": url,
            "body": body,
            "has_auth": "Authorization" in body or "token" in params_str.lower(),
        })

    return methods


def parse_params(params_str: str) -> list[dict]:
    """Parse TypeScript function parameters."""
    params = []
    # Split by comma but respect nested generics
    depth = 0
    current = ""
    for ch in params_str:
        if ch in "<({":
            depth += 1
        elif ch in ">)}":
            depth -= 1
        elif ch == "," and depth == 0:
            if current.strip():
                params.append(parse_single_param(current.strip()))
            current = ""
            continue
        current += ch
    if current.strip():
        params.append(parse_single_param(current.strip()))
    return params


def parse_single_param(param_str: str) -> dict:
    """Parse a single TS parameter: name: type = default"""
    # Handle destructured params
    if param_str.startswith("{"):
        return {"name": "params", "type": "Any", "default": None}

    parts = param_str.split("=", 1)
    name_type = parts[0].strip()
    default = parts[1].strip() if len(parts) > 1 else None

    type_parts = name_type.split(":", 1)
    name = type_parts[0].strip()
    ts_type = type_parts[1].strip() if len(type_parts) > 1 else "Any"

    return {"name": name, "type": ts_type, "default": default}


def detect_http_call(body: str) -> tuple[str, str]:
    """Detect the HTTP method and URL from a method body."""
    # axios pattern
    axios_match = re.search(r"axios\.(get|post|put|patch|delete)\s*\(\s*[`'\"]?([^`'\")\s,]+)", body)
    if axios_match:
        return axios_match.group(1).upper(), clean_url(axios_match.group(2))

    # fetch pattern
    fetch_match = re.search(r"fetch\s*\(\s*[`'\"]?([^`'\")\s,]+)", body)
    if fetch_match:
        url = clean_url(fetch_match.group(1))
        method_match = re.search(r"method:\s*['\"](\w+)['\"]", body)
        method = method_match.group(1).upper() if method_match else "GET"
        return method, url

    return "GET", ""


def clean_url(url: str) -> str:
    """Clean a URL template, converting JS interpolation to Swift."""
    # Replace ${VAR} with \(var)
    url = re.sub(r"\$\{(\w+)\}", lambda m: f"\\({to_camel_case(m.group(1))})", url)
    # Replace ${process.env.XXX} or ${API_BASE}
    url = re.sub(r"\\\(processEnvNextPublicApiUrl\)", "\\(baseURL)", url)
    url = re.sub(r"\\\(apiBase\)", "\\(baseURL)", url)
    url = re.sub(r"\\\(APIBASE\)", "\\(baseURL)", url)
    # Remove template literal backticks
    url = url.strip("`'\"")
    return url


# ---------------------------------------------------------------------------
# Swift code generation
# ---------------------------------------------------------------------------

def convert_service_method(method: dict) -> str:
    """Convert a single service method to Swift."""
    name = to_camel_case(method["name"])
    http = method["http_method"]
    lines = []

    # Build Swift parameter list
    swift_params = []
    for p in method["params"]:
        if p["name"] in ("token",):
            continue  # Auth handled by APIClient
        swift_type = map_type(p["type"])
        if p["default"] is not None:
            swift_default = convert_default_value(p["default"])
            swift_params.append(f"{p['name']}: {swift_type} = {swift_default}")
        else:
            swift_params.append(f"{p['name']}: {swift_type}")

    # Build return type
    if method["return_type"]:
        ret_type = map_type(method["return_type"])
        if ret_type == "Void":
            return_clause = ""
            decode_line = None
        else:
            return_clause = f" -> {ret_type}"
            decode_line = ret_type
    else:
        return_clause = ""
        decode_line = None

    params_str = ", ".join(swift_params)
    lines.append(f"    static func {name}({params_str}) async throws{return_clause} {{")

    # Build URL
    url = method["url"]
    if url:
        # Check if URL has interpolation
        if "\\(" in url:
            lines.append(f'        let url = "\\(APIClient.shared.baseURL){url}"')
        else:
            lines.append(f'        let url = "\\(APIClient.shared.baseURL){url}"')
    else:
        lines.append(f"        {swift_todo('Set the correct endpoint URL')}")
        lines.append(f'        let url = "\\(APIClient.shared.baseURL)/endpoint"')

    # Generate the API call
    if http == "GET":
        if decode_line:
            lines.append(f"        return try await APIClient.shared.get(url)")
        else:
            lines.append(f"        try await APIClient.shared.get(url)")
    elif http == "POST":
        body_param = next((p["name"] for p in method["params"] if p["type"] not in ("string", "String") and p["name"] != "token"), None)
        if body_param:
            if decode_line:
                lines.append(f"        return try await APIClient.shared.post(url, body: {body_param})")
            else:
                lines.append(f"        try await APIClient.shared.post(url, body: {body_param})")
        else:
            lines.append(f"        {swift_todo('Add request body')}")
            if decode_line:
                lines.append(f"        return try await APIClient.shared.post(url, body: EmptyBody())")
            else:
                lines.append(f"        try await APIClient.shared.post(url, body: EmptyBody())")
    elif http in ("PUT", "PATCH"):
        body_param = next((p["name"] for p in method["params"] if p["type"] not in ("string", "String") and p["name"] not in ("token", "id")), None)
        if body_param:
            if decode_line:
                lines.append(f"        return try await APIClient.shared.put(url, body: {body_param})")
            else:
                lines.append(f"        try await APIClient.shared.put(url, body: {body_param})")
        else:
            if decode_line:
                lines.append(f"        return try await APIClient.shared.put(url, body: EmptyBody())")
            else:
                lines.append(f"        try await APIClient.shared.put(url, body: EmptyBody())")
    elif http == "DELETE":
        lines.append(f"        try await APIClient.shared.delete(url)")

    lines.append("    }")
    lines.append("")

    return "\n".join(lines)


def convert_default_value(default: str) -> str:
    """Convert a TypeScript default value to Swift."""
    default = default.strip().strip("'\"")
    if default == "true":
        return "true"
    if default == "false":
        return "false"
    if default.isdigit():
        return default
    # String value
    return f'"{default}"'


def generate_stub_method(pattern: dict) -> str:
    """Generate a stub method from a manifest pattern entry."""
    method = pattern.get("details", {}).get("method", "get").lower()
    url = pattern.get("details", {}).get("url", "/endpoint")
    name = f"{method}Data"

    return f"""    {swift_todo(f'Implement: {method.upper()} {url}')}
    static func {name}() async throws -> Data {{
        return try await APIClient.shared.get("\\(APIClient.shared.baseURL){url}")
    }}
"""


def generate_api_client_scaffold() -> str:
    """Generate the shared APIClient that all services use."""
    return format_swift('''\
//
//  APIClient.swift
//  MyApp
//
//  Auto-generated by iOS Code Converter
//

import Foundation

// 💡 Learn: `actor` ensures thread-safe access to mutable state.
//    Unlike JavaScript (single-threaded), Swift can run code on multiple
//    threads. The actor keyword prevents data races automatically.
actor APIClient {
    static let shared = APIClient()

    let baseURL: String

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

    private init() {
        // TODO: Load from xcconfig / Info.plist
        self.baseURL = Bundle.main.infoDictionary?["API_BASE_URL"] as? String
            ?? "https://api.example.com"
    }

    func setAuthToken(_ token: String?) {
        authToken = token
    }

    // MARK: - HTTP Methods

    func get<T: Decodable>(_ urlString: String) async throws -> T {
        let data = try await performRequest(urlString, method: "GET")
        return try decoder.decode(T.self, from: data)
    }

    func post<T: Decodable>(_ urlString: String, body: any Encodable) async throws -> T {
        let data = try await performRequest(urlString, method: "POST", body: body)
        return try decoder.decode(T.self, from: data)
    }

    func put<T: Decodable>(_ urlString: String, body: any Encodable) async throws -> T {
        let data = try await performRequest(urlString, method: "PUT", body: body)
        return try decoder.decode(T.self, from: data)
    }

    func delete(_ urlString: String) async throws {
        _ = try await performRequest(urlString, method: "DELETE")
    }

    // MARK: - Internal

    private func performRequest(
        _ urlString: String,
        method: String,
        body: (any Encodable)? = nil
    ) async throws -> Data {
        guard let url = URL(string: urlString) else {
            throw APIError.invalidURL(urlString)
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let token = authToken {
            request.setValue("Bearer \\(token)", forHTTPHeaderField: "Authorization")
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

        return data
    }
}

// MARK: - Error Types

// 💡 Learn: Swift's error handling is explicit — `throws` in a function
//    signature means the caller MUST handle errors with `do { try } catch`.
//    This is unlike JavaScript where .catch() is optional and easily forgotten.
//    LocalizedError provides user-facing messages via errorDescription.

enum APIError: LocalizedError {
    case invalidURL(String)
    case invalidResponse
    case unauthorized
    case notFound
    case serverError(statusCode: Int)
    case decodingFailed(Error)
    case networkUnavailable
    case httpError(status: Int, body: String?)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let url):
            return "Invalid URL: \\(url)"
        case .invalidResponse:
            return "Invalid response from server"
        case .unauthorized:
            return "Please sign in again"
        case .notFound:
            return "The requested resource was not found"
        case .serverError(let code):
            return "Server error (\\(code))"
        case .decodingFailed(let error):
            return "Failed to process response: \\(error.localizedDescription)"
        case .networkUnavailable:
            return "No internet connection — check your network settings"
        case .httpError(let status, let body):
            return "HTTP \\(status): \\(body ?? "No details")"
        }
    }
}

struct EmptyBody: Encodable {}
''')


def generate_load_state_scaffold() -> str:
    """Generate the LoadState<T> enum for ViewModel state management.

    Phase B: BUILD-12 (GAP-I4)

    This enum replaces the common pattern of separate isLoading/error/data
    properties with a single, type-safe state machine.
    """
    return format_swift('''\
//
//  LoadState.swift
//  MyApp
//
//  Auto-generated by iOS Code Converter
//

import Foundation

// 💡 Learn: LoadState replaces the web pattern of { isLoading, error, data }.
//    In React you might write:
//      const [data, setData] = useState(null)
//      const [isLoading, setIsLoading] = useState(false)
//      const [error, setError] = useState(null)
//
//    In Swift, an enum with associated values guarantees you can't have
//    contradictory states (e.g., isLoading=true AND error!=null).
//    This is called "making illegal states unrepresentable."

enum LoadState<T> {
    case idle
    case loading
    case loaded(T)
    case error(Error)

    // MARK: - Convenience accessors

    /// True when data is being fetched
    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }

    /// The loaded value, or nil if not yet loaded
    var value: T? {
        if case .loaded(let v) = self { return v }
        return nil
    }

    /// The error, or nil if no error occurred
    var error: Error? {
        if case .error(let e) = self { return e }
        return nil
    }

    /// True when data has been successfully loaded
    var isLoaded: Bool {
        if case .loaded = self { return true }
        return false
    }

    /// User-facing error message, or nil
    var errorMessage: String? {
        error?.localizedDescription
    }
}

// MARK: - SwiftUI Integration

// 💡 Learn: This extension lets you use LoadState directly in SwiftUI views:
//
//    switch state {
//    case .idle:
//        EmptyView()
//    case .loading:
//        ProgressView()
//    case .loaded(let items):
//        List(items) { ... }
//    case .error(let error):
//        ErrorView(error: error, retry: { Task { await vm.load() } })
//    }

import SwiftUI

/// A reusable view that renders loading/error/content states.
struct LoadStateView<T, Content: View>: View {
    let state: LoadState<T>
    let retry: (() -> Void)?
    @ViewBuilder let content: (T) -> Content

    init(
        _ state: LoadState<T>,
        retry: (() -> Void)? = nil,
        @ViewBuilder content: @escaping (T) -> Content
    ) {
        self.state = state
        self.retry = retry
        self.content = content
    }

    var body: some View {
        switch state {
        case .idle:
            Color.clear
        case .loading:
            ProgressView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .loaded(let value):
            content(value)
        case .error(let error):
            VStack(spacing: 16) {
                Image(systemName: "exclamationmark.triangle")
                    .font(.largeTitle)
                    .foregroundStyle(.secondary)
                Text(error.localizedDescription)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                if let retry {
                    Button("Try Again", action: retry)
                        .buttonStyle(.borderedProminent)
                }
            }
            .padding()
        }
    }
}
''')

