# Codable Customization

> The default `Codable` synthesis covers maybe 60% of real-world JSON. The other 40% — snake_case keys, ISO-8601 dates with fractional seconds, polymorphic types, flat-vs-nested mismatches, nullable-as-empty-string — is where you'll spend most of your serialization time. This chapter covers the customization toolkit so you stop reaching for `[String: Any]` workarounds.

---

## What `Codable` Gives You for Free

```swift
struct User: Codable {
    let id: String
    let email: String
    let isActive: Bool
}

let user = try JSONDecoder().decode(User.self, from: data)
let json = try JSONEncoder().encode(user)
```

Synthesis handles:
- Property names exactly matching JSON keys
- Standard primitives (`String`, `Int`, `Double`, `Bool`)
- Nested `Codable` types
- `Array`, `Dictionary` of `Codable`
- `Optional` properties (missing keys → `nil`)

Everything below is what to do when reality doesn't match.

---

## Snake_case ↔ camelCase

The single most common JSON mismatch. Two ways to handle:

### Option A: encoder/decoder strategy (project-wide)

```swift
let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase

let encoder = JSONEncoder()
encoder.keyEncodingStrategy = .convertToSnakeCase

struct User: Codable {
    let id: String
    let displayName: String         // maps to "display_name"
    let isActive: Bool              // maps to "is_active"
}
```

**Caveats:**
- `convertFromSnakeCase` mangles ID-style keys: `"user_id"` → `userId` (fine), `"URL"` → `URL` (fine), `"id"` → `id` (fine). But `"user_ID"` → `userID` and `"userID"` → `"user_id"` round-trip breakage exists for some Apple-style abbreviations.
- A single bad key forces an *override*, not a strategy switch.

### Option B: explicit `CodingKeys`

```swift
struct User: Codable {
    let id: String
    let displayName: String
    let isActive: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case isActive = "is_active"
    }
}
```

More verbose but explicit and robust. **Use this** when:
- Only some keys are mismatched.
- You want one source of truth visible at the type definition.
- You're consuming a third-party API where keys may change and you want a typed compile failure.

**Combined idiom:** project-wide `.convertFromSnakeCase` strategy + `CodingKeys` overrides only on the awkward types.

---

## Dates — The Single Largest Source of Bugs

Apple's defaults rarely match the wire format. Configure explicitly.

```swift
let decoder = JSONDecoder()

// 1. ISO-8601 (most common in modern APIs)
decoder.dateDecodingStrategy = .iso8601

// 2. Unix epoch seconds (Stripe, many JS-default backends)
decoder.dateDecodingStrategy = .secondsSince1970

// 3. Unix epoch milliseconds (Java/Kotlin defaults)
decoder.dateDecodingStrategy = .millisecondsSince1970

// 4. Custom formatter (the painful path)
let formatter = ISO8601DateFormatter()
formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
decoder.dateDecodingStrategy = .custom { decoder in
    let container = try decoder.singleValueContainer()
    let string = try container.decode(String.self)
    guard let date = formatter.date(from: string) else {
        throw DecodingError.dataCorruptedError(
            in: container,
            debugDescription: "Invalid date: \(string)"
        )
    }
    return date
}
```

The `.iso8601` built-in **does not handle fractional seconds**. Backends that emit `2026-05-04T12:34:56.789Z` (the default from many JVM and JS toolchains) fail with `.iso8601`. Use the custom strategy with `.withFractionalSeconds` or normalize at the gateway.

---

## Custom `init(from:)` and `encode(to:)`

When the JSON shape and the Swift shape don't line up, override the synthesized methods.

### Decode-only customization

```swift
struct Article: Codable {
    let id: String
    let title: String
    let publishedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, title
        case publishedAt = "published_timestamp"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try c.decode(String.self, forKey: .id)
        self.title = try c.decode(String.self, forKey: .title)

        // server sends an Int, we want a Date
        let timestamp = try c.decode(Int.self, forKey: .publishedAt)
        self.publishedAt = Date(timeIntervalSince1970: TimeInterval(timestamp))
    }
}
```

When you write a custom `init(from:)`, you **lose the synthesized init** — provide both `init(from:)` and `encode(to:)` if you want symmetric encoding, or accept that encoding will be different from decoding.

### `decodeIfPresent` for missing-key tolerance

```swift
self.subtitle = try c.decodeIfPresent(String.self, forKey: .subtitle) ?? ""
```

`decodeIfPresent` returns `nil` for both missing keys and explicit `null`. `decode(...)` throws for missing keys. Use the former when the field is optional in the wire format but you want a concrete value in Swift.

---

## Flat ↔ Nested Translations

A common need: the API sends a flat object but you want nested types in Swift, or vice versa.

```json
{ "id": "u1", "address_street": "...", "address_city": "...", "address_zip": "..." }
```

```swift
struct Address: Codable {
    let street: String
    let city: String
    let zip: String
}

struct User: Codable {
    let id: String
    let address: Address

    enum CodingKeys: String, CodingKey {
        case id
        case addressStreet = "address_street"
        case addressCity = "address_city"
        case addressZip = "address_zip"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try c.decode(String.self, forKey: .id)
        self.address = Address(
            street: try c.decode(String.self, forKey: .addressStreet),
            city: try c.decode(String.self, forKey: .addressCity),
            zip: try c.decode(String.self, forKey: .addressZip)
        )
    }
}
```

For the inverse (nested JSON → flat Swift), `nestedContainer(keyedBy:forKey:)` reads into a sub-container.

---

## Polymorphism — The "Discriminator" Pattern

Backends often emit a `type` field that tells you which concrete shape to decode:

```json
[
  { "type": "image", "url": "..." },
  { "type": "video", "url": "...", "duration": 12.5 },
  { "type": "text", "body": "..." }
]
```

```swift
enum Media: Codable {
    case image(url: URL)
    case video(url: URL, duration: TimeInterval)
    case text(body: String)

    enum CodingKeys: String, CodingKey { case type, url, duration, body }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let type = try c.decode(String.self, forKey: .type)
        switch type {
        case "image":
            self = .image(url: try c.decode(URL.self, forKey: .url))
        case "video":
            self = .video(
                url: try c.decode(URL.self, forKey: .url),
                duration: try c.decode(TimeInterval.self, forKey: .duration)
            )
        case "text":
            self = .text(body: try c.decode(String.self, forKey: .body))
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .type,
                in: c,
                debugDescription: "Unknown media type: \(type)"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .image(let url):
            try c.encode("image", forKey: .type)
            try c.encode(url, forKey: .url)
        case .video(let url, let duration):
            try c.encode("video", forKey: .type)
            try c.encode(url, forKey: .url)
            try c.encode(duration, forKey: .duration)
        case .text(let body):
            try c.encode("text", forKey: .type)
            try c.encode(body, forKey: .body)
        }
    }
}
```

This is the canonical pattern. It's verbose but robust — every case is exhaustively handled at compile time, and adding a new variant fails to compile until you handle it everywhere.

---

## The "Lossy Array" Pattern

A real headache: an API returns 100 items, one is malformed, and `JSONDecoder` rejects the entire response. Sometimes you want "decode what you can, drop the bad ones."

```swift
struct LossyArray<T: Decodable>: Decodable {
    let elements: [T]
    init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        var results: [T] = []
        while !container.isAtEnd {
            if let element = try? container.decode(T.self) {
                results.append(element)
            } else {
                _ = try? container.decode(AnyDecodable.self)   // skip
            }
        }
        self.elements = results
    }
}

struct AnyDecodable: Decodable {}    // sponge for skipped items
```

Use sparingly — silently dropping malformed data hides backend bugs. Better to log the failure and surface the partial result explicitly.

---

## `JSONDecoder` Configuration Cheat Sheet

```swift
let decoder = JSONDecoder()

// Keys
decoder.keyDecodingStrategy = .convertFromSnakeCase    // or .useDefaultKeys, .custom

// Dates
decoder.dateDecodingStrategy = .iso8601                // or .secondsSince1970, .formatted, .custom

// Data (base64 by default)
decoder.dataDecodingStrategy = .base64                 // or .custom

// Floats — what to do with NaN/Infinity
decoder.nonConformingFloatDecodingStrategy = .convertFromString(
    positiveInfinity: "+Infinity",
    negativeInfinity: "-Infinity",
    nan: "NaN"
)

// Numbers — Allow lossy conversion (e.g., string "42" → Int 42)?
// Not built-in. Override at the property level.
```

`JSONEncoder` has matching settings — `.outputFormatting = [.prettyPrinted, .sortedKeys]` is the formatting most often forgotten.

---

## Property Wrappers for Codable

Repeating "string with int fallback" or "boolean with 0/1 acceptance" decode logic across types is tedious. Property wrappers can centralize:

```swift
@propertyWrapper
struct LooseInt: Codable {
    var wrappedValue: Int

    init(wrappedValue: Int) { self.wrappedValue = wrappedValue }

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let i = try? c.decode(Int.self) { wrappedValue = i; return }
        if let s = try? c.decode(String.self), let i = Int(s) { wrappedValue = i; return }
        throw DecodingError.typeMismatch(
            Int.self,
            .init(codingPath: c.codingPath, debugDescription: "expected int or numeric string")
        )
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        try c.encode(wrappedValue)
    }
}

struct Order: Codable {
    @LooseInt var quantity: Int       // accepts 5, "5"
}
```

Several open-source packages (`BetterCodable`, `CodableWrappers`) ship pre-built wrappers for the common cases. For a couple of awkward fields, write the wrapper yourself; for a project full of them, pull in a package.

---

## Common Pitfalls

### 1. Custom `init(from:)` removes synthesis

Once you write `init(from:)`, the synthesized one is gone. If you rely on the default for some properties, write the custom init carefully and run round-trip tests.

### 2. `decodeIfPresent` vs default values

```swift
struct Settings: Codable {
    var theme: String = "light"     // default doesn't trigger on missing JSON
}
```

The Swift property default does not run during decoding — `theme` will throw if the key is missing. Use `decodeIfPresent` in a custom init, or make it `String?`.

### 3. `[String: Any]` and `Codable`

`Codable` doesn't handle `[String: Any]` because `Any` isn't `Codable`. If you genuinely have heterogeneous JSON, decode into a discriminated enum (the polymorphism pattern above) or use `JSONSerialization` for that subtree.

### 4. `null` vs missing

JSON's `null` decodes into an Optional as `nil`. A *missing key* also decodes into an Optional as `nil` *if and only if* you use `decodeIfPresent`. With plain `decode(...)`, missing throws but explicit `null` round-trips to `nil`. If you need to distinguish them, use a double-optional `T??` and inspect.

### 5. Nested JSON with same-named keys

If the outer and inner JSON have a `type` key that mean different things, `CodingKeys` on the outer struct conflicts. Solution: explicit nested containers via `nestedContainer(keyedBy:forKey:)`.

### 6. Forgetting to encode all cases of an enum

```swift
enum Status: String, Codable { case active, inactive, deleted }
```

The synthesized encoder uses the raw value — but if you write a custom `encode(to:)` for an enum with associated values, **every** case must encode. Compile won't catch missing cases inside `switch self` if you have a `default`.

### 7. `JSONEncoder` produces unsorted keys

Different runs produce JSON in different key orders, breaking snapshot tests. Set `encoder.outputFormatting = [.sortedKeys]` for deterministic output (and consider `.prettyPrinted` for diffability).

---

## Mapping From JSON Libraries Elsewhere

| In your source ecosystem | Closest Swift |
|---|---|
| TypeScript: `interface User`, manual `JSON.parse` cast | `struct User: Codable` + `JSONDecoder` |
| TypeScript: `zod` / `io-ts` validation | Codable + custom `init(from:)` for validation |
| Java: Jackson `@JsonProperty` | `CodingKeys` enum |
| Java: Jackson `@JsonDeserialize(using:)` | Custom `init(from:)` or property-wrapper |
| Java: Jackson polymorphism (`@JsonTypeInfo`) | Discriminator-enum pattern (above) |
| Kotlin: kotlinx.serialization `@Serializable` | `Codable` (synthesized) |
| Kotlin: `@SerialName("...")` | `CodingKeys` enum |
| Python: Pydantic `BaseModel` | `Codable` struct + custom validation in `init(from:)` |
| Python: `dataclasses_json` | `Codable` struct |
| C#: `System.Text.Json` `[JsonPropertyName]` | `CodingKeys` enum |
| C#: `JsonConverter<T>` | Custom `init(from:)`/`encode(to:)` |

---

## Companion chapters

- [Networking & API Integration](../05-networking/api-integration.md) — `JSONDecoder` integration with `URLSession`.
- [Combine & AsyncStream](combine-and-async-streams.md) — `.decode(type:decoder:)` operator usage.
- [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) — generic Codable wrappers.

**Next:** [Swift Toolkit for Web Devs](swift-toolkit-for-web-devs.md) — KeyPaths, property-wrapper authoring, result builders, IUO.

*Last updated: 2026-05-04*
