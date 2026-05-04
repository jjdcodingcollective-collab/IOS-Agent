# Combine, AsyncSequence & Reactive Patterns

> Combine is Apple's reactive framework — `Publisher`, `Subscriber`, `.map`, `.filter`, `.sink` — close enough to RxJS that an experienced JS reactive developer can read it on day one. AsyncSequence is the newer, language-built-in alternative that pairs with `async`/`await`. This chapter covers when to use which, the pitfalls, and the patterns SwiftUI codebases lean on.

---

## The 60-Second Mental Model

Three reactive primitives coexist in a modern Swift codebase:

1. **Combine** — Apple's `Publisher`/`Subscriber` framework. Mature, integrates with `@Published`, lots of operators. Ages well in pre-`async/await` view models.
2. **`AsyncSequence`** (and its concrete cousins `AsyncStream`, `AsyncThrowingStream`) — language-level, lazy, `for await x in stream`. Newer; preferred for greenfield code that's `async`-native.
3. **The `Observable` macro** (Swift 5.9+, iOS 17+) — supersedes `ObservableObject`/`@Published` for SwiftUI state. Not reactive in the streams sense, but worth knowing because it changes the SwiftUI integration story.

If you came from RxJS / RxJava: Combine is your familiar tool. AsyncSequence is the more idiomatic choice in 2026 Swift, but Combine isn't going anywhere — there's still a lot of UI plumbing where it shines.

---

## Combine in 90 Seconds

```swift
import Combine

let publisher = [1, 2, 3, 4, 5].publisher        // sync sequence as a publisher

let subscription = publisher
    .filter { $0.isMultiple(of: 2) }
    .map { $0 * 10 }
    .sink(
        receiveCompletion: { completion in print("done: \(completion)") },
        receiveValue: { value in print("got: \(value)") }
    )
// got: 20
// got: 40
// done: finished
```

`subscription` is an `AnyCancellable`. The pipeline runs as long as the cancellable is alive. Drop it (or call `.cancel()`) and the chain tears down.

### Mapping from RxJS

| RxJS | Combine |
|---|---|
| `Observable` | `Publisher` (a protocol, not a concrete type) |
| `Subject` | `PassthroughSubject<Output, Failure>` |
| `BehaviorSubject` | `CurrentValueSubject<Output, Failure>` |
| `ReplaySubject` | No direct analogue — use `.share()` + buffer or build with subjects. |
| `subject.next(x)` | `subject.send(x)` |
| `subject.complete()` | `subject.send(completion: .finished)` |
| `.subscribe(observer)` | `.sink(receiveValue:)` (and `.assign(to:on:)` for property-binding) |
| `Subscription` | `AnyCancellable` |
| `pipe(map(...), filter(...))` | `.map(...).filter(...)` (chained directly) |
| `combineLatest` | `.combineLatest` (and `.combineLatest3`/`4`) |
| `switchMap` | `.switchToLatest()` (after `.map { ... .publisher }`) |
| `mergeMap`/`flatMap` | `.flatMap { ... }` |
| `debounceTime(300)` | `.debounce(for: .milliseconds(300), scheduler: RunLoop.main)` |
| `throttleTime` | `.throttle(for:scheduler:latest:)` |
| `distinctUntilChanged` | `.removeDuplicates()` |
| `share()` | `.share()` |
| `catchError` | `.catch { ... }` |
| `retry(n)` | `.retry(n)` |
| `Observable.timer(...)` | `Timer.publish(every:on:in:)` |
| `take(n)` | `.prefix(n)` |
| `takeUntil(other)` | `.prefix(untilOutputFrom: other)` |

The biggest API shape difference: Combine publishers carry a typed `Failure` (or `Never`). RxJS errors are untyped. So a Combine pipeline either declares the error type or is converted with `.mapError`/`.replaceError(with:)` to match.

---

## `@Published` and `ObservableObject`

Pre-Observable-macro SwiftUI uses `@Published`:

```swift
final class SearchViewModel: ObservableObject {
    @Published var query: String = ""
    @Published var results: [Result] = []
    private var cancellables: Set<AnyCancellable> = []

    init(api: SearchAPI) {
        $query                                        // Publisher<String, Never>
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .filter { $0.count >= 2 }
            .map { q in
                api.search(q)                         // returns AnyPublisher<[Result], Error>
                    .replaceError(with: [])
            }
            .switchToLatest()
            .receive(on: RunLoop.main)
            .assign(to: &$results)                    // bind directly to @Published
            // — or store via:
            //   .sink { [weak self] r in self?.results = r }
            //   .store(in: &cancellables)
    }
}
```

Notes:
- `$query` is the **projected value** of `@Published`, which is the publisher.
- `.assign(to: &$results)` is a Combine-built-in shorthand for binding into another `@Published`. It manages the cancellable lifetime for you (via `inout` to the projected value).
- The `[weak self]` discipline applies — see [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — whenever you `.sink` and the closure captures `self`.

### Lifetime discipline (the part most teams get wrong)

```swift
private var cancellables: Set<AnyCancellable> = []
```

Every `.sink` not pinned with `.assign(to: &$x)` must be `.store(in: &cancellables)` on a property held by the view model. When the view model deinits, the `Set` releases all subscriptions and the upstream publishers cancel.

If you `.sink` and don't store the result, **the subscription is torn down immediately** because `AnyCancellable.deinit` cancels. This silent failure surprises everyone once.

---

## `AnyPublisher` — Type Erasure

Combine operators each return a different concrete type (`Publishers.Map<...>`, `Publishers.Filter<...>` …). For function signatures, you almost always want to erase to `AnyPublisher<Output, Failure>`:

```swift
struct UserAPI {
    func fetchProfile(id: String) -> AnyPublisher<Profile, APIError> {
        URLSession.shared.dataTaskPublisher(for: url(id))
            .tryMap { try JSONDecoder().decode(Profile.self, from: $0.data) }
            .mapError { APIError.network($0) }
            .eraseToAnyPublisher()                    // hide the concrete type
    }
}
```

Without `eraseToAnyPublisher()` the return type would be a multi-parameter generic monstrosity. Same idea as TypeScript declaring `Observable<Profile>` instead of the inferred operator chain type.

See [Generics, Opaque Types & Existentials](generics-and-protocols-deep.md) for why both `AnyPublisher` (existential) and `some Publisher` (opaque) exist and when to pick which.

---

## Common Combine Patterns

### 1. Form validation

```swift
final class SignupViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published private(set) var isValid = false

    init() {
        Publishers.CombineLatest($email, $password)
            .map { email, pw in
                email.contains("@") && pw.count >= 8
            }
            .assign(to: &$isValid)
    }
}
```

### 2. Search-as-you-type

Already shown above (`debounce` → `removeDuplicates` → `switchToLatest`).

### 3. Polling

```swift
Timer.publish(every: 30, on: .main, in: .common)
    .autoconnect()
    .flatMap { _ in api.fetchStatus().replaceError(with: .unknown) }
    .receive(on: RunLoop.main)
    .assign(to: &$status)
```

### 4. Bridging callbacks → publishers

```swift
extension CLLocationManager {
    func locationPublisher() -> AnyPublisher<CLLocation, Never> {
        let subject = PassthroughSubject<CLLocation, Never>()
        let delegate = LocationDelegate(subject: subject)
        // store delegate to keep it alive...
        return subject.eraseToAnyPublisher()
    }
}
```

For one-shot callbacks (single value or error), use `Future`:

```swift
func fetchOnce() -> AnyPublisher<Data, Error> {
    Future { promise in
        URLSession.shared.dataTask(with: url) { data, _, error in
            if let data { promise(.success(data)) }
            else if let error { promise(.failure(error)) }
        }.resume()
    }
    .eraseToAnyPublisher()
}
```

`Future` runs eagerly the moment it's created. If you want lazy semantics, wrap it in `Deferred { Future { ... } }`.

---

## AsyncSequence — The Modern Path

`AsyncSequence` is a protocol; you consume any conforming type with `for await`:

```swift
for try await line in url.lines {                    // URL.lines is built-in
    print(line)
}
```

To produce one, use `AsyncStream`:

```swift
func ticker(every: Duration) -> AsyncStream<Int> {
    AsyncStream { continuation in
        let task = Task {
            var i = 0
            while !Task.isCancelled {
                continuation.yield(i)
                i += 1
                try? await Task.sleep(for: every)
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in task.cancel() }
    }
}

for await i in ticker(every: .seconds(1)).prefix(5) {
    print(i)
}
```

The `onTermination` hook is important: if the consumer breaks early or the stream is cancelled, your producer Task should also stop.

### `AsyncStream.makeStream()` — the cleaner shape

```swift
let (stream, continuation) = AsyncStream.makeStream(of: Int.self)
// hand `continuation` to whoever pushes values
// hand `stream` to whoever consumes them
```

This shape is closer to RxJS `Subject` ergonomics — you have the producer end and the consumer end as separate handles.

---

## Combine vs AsyncSequence — Decision Table

| Situation | Combine | AsyncSequence |
|---|---|---|
| Pre-Swift 5.5 codebase, Combine entrenched | ✅ stay | ❌ |
| `@Published` already drives the UI | ✅ | — |
| Fan-out to multiple subscribers | ✅ (`.share()`) | ❌ (one consumer per stream by default) |
| Backpressure / time-based operators | ✅ (debounce, throttle, etc.) | Limited — you build it manually. |
| Reactive form/validation chains | ✅ | Possible but verbose. |
| Single async resource (one event, one error) | overkill | Use `async throws` + `Task` directly. |
| New code, async-native team | ❌ | ✅ |
| Async iteration over a network stream / file lines | ❌ | ✅ |
| Long-lived single-consumer event source | tie | ✅ |

**Pragmatic rule:** if a codebase already uses Combine for view-model glue, keep doing so. For new producers, ask: "is there exactly one consumer and the data is async by nature?" → AsyncStream. "Is there fan-out, time-based operators, or `@Published` integration?" → Combine.

---

## The `Observable` Macro (Swift 5.9+, iOS 17+)

```swift
import Observation

@Observable
final class SearchModel {
    var query = ""
    var results: [Result] = []
}
```

In SwiftUI, you no longer need `@StateObject`/`@ObservedObject`/`@Published`. SwiftUI tracks property reads automatically:

```swift
struct SearchView: View {
    @State private var model = SearchModel()         // @State suffices

    var body: some View {
        TextField("Query", text: $model.query)
        List(model.results, id: \.id) { ... }
    }
}
```

This doesn't *replace* Combine — it replaces `ObservableObject` for SwiftUI integration. If your view model exposes derived publishers (search-as-you-type), keep Combine. If your view model is a plain bag of properties read by views, use `@Observable`.

Apple's guidance: prefer `@Observable` for new SwiftUI work targeting iOS 17+; fall back to `ObservableObject`/`@Published` if you support iOS 16 or earlier, or if you actively use the publisher projection.

---

## Pitfalls

### 1. Forgetting `.store(in: &cancellables)`

```swift
// ❌ leaked → torn down → no events
publisher.sink { ... }

// ✅
publisher.sink { ... }.store(in: &cancellables)

// ✅ (also fine if assigning to a @Published)
publisher.assign(to: &$results)
```

### 2. `[weak self]` inside `.sink`

The `.sink` closure is escaping and stored. Capturing `self` strongly retains the view model for the publisher's lifetime — usually a leak.

```swift
publisher
    .sink { [weak self] value in
        self?.update(with: value)
    }
    .store(in: &cancellables)
```

### 3. Chains that capture publishers strongly

If a publisher holds a closure that captures the view model strongly, even storing the cancellable on the view model creates a cycle: `vm → cancellables → subscription → closure → vm`. The escape hatch is the same — `[weak self]` in operator closures.

### 4. `assign(to:on:)` keeps `on` alive

The two-arg form `.assign(to: \.title, on: self)` retains `self`. Prefer `.assign(to: &$title)` (the `inout` projected-value form) — it manages lifetime via the `@Published` itself.

### 5. `Future` runs eagerly

```swift
let f = Future { ... }     // body runs NOW, even before sink
```

Wrap in `Deferred { Future { ... } }` for lazy semantics, or just use an `async` function and `Task`.

### 6. Threading

Combine doesn't move to the main thread automatically. Insert `.receive(on: RunLoop.main)` before any `.assign` or `.sink` that touches UI state. With strict concurrency and `@MainActor` view models, the compiler will catch most of these — see [Concurrency & Sendable](concurrency-and-sendable.md).

---

## Companion chapters

- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — actor isolation around publishers and closures.
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — the `[weak self]` and `cancellables` lifetime discipline.
- [Architecture Patterns](../03-architecture/patterns.md) — where Combine fits in MVVM.
- [Codable Customization](codable-deep.md) — `dataTaskPublisher` + `.decode(type:decoder:)` patterns.

**Next:** [Codable Customization](codable-deep.md).

*Last updated: 2026-05-04*
