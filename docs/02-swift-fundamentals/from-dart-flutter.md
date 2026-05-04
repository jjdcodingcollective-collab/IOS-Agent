# Swift for Dart / Flutter Developers

> Dart and Swift are closer than you might think — both are statically typed, both have sound null safety, both have async/await, both have value-leaning collections. The real translation cost is the **UI framework**: SwiftUI and Flutter look superficially similar (declarative, composable, reactive) but their lifecycle, layout, and state primitives differ enough that a literal port goes wrong.

> **Audience:** Teams replatforming a Flutter app to native iOS, usually after hitting performance ceilings, plugin-ecosystem fragility, platform-feature needs that exceed the channel boundary, or after Flutter's roadmap diverged from their roadmap.

---

## The 60-second mental model

1. **Widgets → Views, but they're structs, not classes.** SwiftUI views are value types; Flutter widgets are classes (immutable but heap-allocated). The diffing model is similar; the cost model is different.
2. **`StatefulWidget` boilerplate is gone.** Where Flutter splits state into a `State<MyWidget>` class, SwiftUI puts state directly on the view via `@State`. The reduction in ceremony is dramatic.
3. **Async/await maps directly.** Dart's `Future<T>` and `Stream<T>` are Swift's `async` functions and `AsyncSequence`. The keyword spelling is identical.
4. **Sound null safety, different ergonomics.** Dart 3's null safety and Swift's optionals enforce the same guarantee — no implicit nulls — but Swift uses `Optional<T>` (an enum) where Dart uses a nullable-type annotation. Optional chaining (`?.`) and the null-coalescing operator (`??`) work the same way.
5. **No GC.** Dart has a generational GC; Swift uses ARC. Closure capture leaks are a real concern in Swift in a way they aren't in Dart.
6. **No platform channels.** What you used to call across a `MethodChannel` you now call directly — those native APIs *are* your runtime now.

---

## Type-system mapping

| Dart | Swift | Note |
|---|---|---|
| `int`, `double`, `bool` | `Int`, `Double`, `Bool` | `Int` is platform-width on iOS (64-bit). |
| `String` | `String` | Both Unicode-correct value types; both have grapheme-cluster-aware iteration. |
| `List<T>` | `[T]` | Value type with copy-on-write in Swift; Dart's `List` is a class but its idiomatic usage is similar. |
| `Map<K, V>` | `[K: V]` | Keys must be `Hashable` in Swift. |
| `Set<T>` | `Set<T>` | Elements must be `Hashable`. |
| `Iterable<T>` | `some Sequence<T>` | Lazy in Dart; eager by default in Swift unless you prefix `.lazy`. |
| `T?` (nullable) | `T?` (Optional) | Same syntax; Swift's is an enum, Dart's an annotation. |
| `dynamic` | `Any` | Avoid in both. |
| `Object` | `Any` (or `AnyObject` for class-only) | Swift distinguishes value-vs-reference any. |
| `class` | `class` | Reference type. |
| `class` (with no inheritance, used as a value) | `struct` | Default to `struct` for "data" types. |
| `mixin M` | `protocol M { /* default impls in extension */ }` | Swift doesn't have mixins as a keyword; the same effect comes from protocol + extension default implementations. |
| `enum` (with values via Dart 3 enhanced) | `enum` (with associated values) | Swift enums are richer — see below. |
| `Future<T>` | `async` function returning `T` | Async functions are first-class. |
| `Stream<T>` | `some AsyncSequence<T>` | See [Combine & AsyncStream](combine-and-async-streams.md). |
| `Function` / `Function(int)` | `() -> Void` / `(Int) -> Void` | Function types. |
| `Exception` / `Error` | `Error` (a protocol) | Anything `Error`-conforming can be thrown. |

### Enums with values

Dart 3 introduced enhanced enums with constructors and methods. Swift's enums went further years earlier — they're full algebraic data types with associated values per case.

```dart
// Dart 3 enhanced enum
enum LoadState {
  loading,
  loaded(int count),       // not actually possible — Dart enhanced enums don't carry per-case values
  failed(String message);
}
```

Dart enums *can't* carry case-specific associated values like that. You'd reach for a sealed class hierarchy:

```dart
sealed class LoadState {}
final class Loading extends LoadState {}
final class Loaded extends LoadState { final int count; Loaded(this.count); }
final class Failed extends LoadState { final String message; Failed(this.message); }
```

Swift collapses the same pattern into the type system natively:

```swift
enum LoadState {
    case loading
    case loaded(count: Int)
    case failed(message: String)
}
```

This is the single biggest stylistic shift for Dart developers — you'll find yourself reaching for enums where you used to reach for sealed classes.

---

## Idiom translation

### Widget tree → View tree

The core mental model — UI is a tree of declarative descriptions, the framework diffs and updates — is **identical**. The mechanics differ.

```dart
// Flutter
class Greeting extends StatelessWidget {
  final String name;
  const Greeting({super.key, required this.name});

  @override
  Widget build(BuildContext context) =>
    Text('Hello, $name', style: Theme.of(context).textTheme.headlineLarge);
}
```

```swift
// SwiftUI
struct Greeting: View {
    let name: String

    var body: some View {
        Text("Hello, \(name)")
            .font(.largeTitle)
    }
}
```

The differences:

- `View` is a **struct**, not a class. No heap allocation per build, no reference identity.
- No `BuildContext` parameter. SwiftUI threads context through the environment (`@Environment`), implicit on the view.
- No `key`. SwiftUI's identity comes from the `id(_:)` modifier or stable `Identifiable` ids in collections; you only set it explicitly for collection items where natural identity is ambiguous.
- `body` is a computed property, not a method.

### `StatefulWidget` → `@State`

The Flutter pattern most worth unlearning: the two-class split.

```dart
// Flutter — the standard StatefulWidget shape
class Counter extends StatefulWidget {
  const Counter({super.key});
  @override State<Counter> createState() => _CounterState();
}

class _CounterState extends State<Counter> {
  int _count = 0;

  @override
  Widget build(BuildContext context) =>
    GestureDetector(
      onTap: () => setState(() => _count++),
      child: Text('Count: $_count'),
    );
}
```

```swift
// SwiftUI
struct Counter: View {
    @State private var count = 0

    var body: some View {
        Text("Count: \(count)")
            .onTapGesture { count += 1 }
    }
}
```

The two-class split is gone. `@State` makes a stored property on a struct view function as if the view were stateful — SwiftUI manages the actual storage out-of-band, keyed by view identity. There is no `setState` because direct mutation of an `@State` property is the trigger.

### Layout

The mental model:

| Flutter | SwiftUI | Note |
|---|---|---|
| `Row` | `HStack` | Horizontal stack. |
| `Column` | `VStack` | Vertical stack. |
| `Stack` | `ZStack` | Z-axis overlay. |
| `Expanded(child: …)` | `.frame(maxWidth: .infinity, maxHeight: .infinity)` or implicit `Spacer` | "Take available space." |
| `Flexible(flex: 2, …)` | `.frame(maxWidth: .infinity)` with `.layoutPriority(2)` | Proportional growth. |
| `SizedBox(width: 16)` | `Spacer().frame(width: 16)` or `.padding(.leading, 16)` | Fixed gap. |
| `Padding(padding: …)` | `.padding(…)` modifier | Modifier on the child. |
| `Container(decoration: …)` | `.background(…)`, `.cornerRadius(…)`, `.border(…)` modifiers | No single Container. |
| `ListView.builder` | `List` or `LazyVStack` inside `ScrollView` | Lazy by default in `List`. |
| `GridView` | `Grid` (iOS 16+) or `LazyVGrid` | `LazyVGrid` for performance. |
| `Align(alignment: …)` | `.frame(maxWidth: .infinity, alignment: .center)` | Alignment via frame. |

```dart
// Flutter
Row(
  children: [
    Icon(Icons.star),
    SizedBox(width: 8),
    Expanded(child: Text(title)),
    Text('$count'),
  ],
)
```

```swift
// SwiftUI
HStack(spacing: 8) {
    Image(systemName: "star.fill")
    Text(title)
        .frame(maxWidth: .infinity, alignment: .leading)
    Text("\(count)")
}
```

`HStack` takes a `spacing` parameter, removing the `SizedBox` ceremony. `frame(maxWidth:.infinity)` is the SwiftUI idiom for "take the available space."

### State management mapping

```dart
// Flutter — with Provider
class CounterModel extends ChangeNotifier {
  int _count = 0;
  int get count => _count;
  void increment() { _count++; notifyListeners(); }
}

ChangeNotifierProvider(
  create: (_) => CounterModel(),
  child: Consumer<CounterModel>(
    builder: (context, model, _) => Text('${model.count}'),
  ),
)
```

```swift
// SwiftUI with @Observable (iOS 17+)
import Observation

@Observable
final class CounterModel {
    var count = 0
    func increment() { count += 1 }
}

// in a parent
@State private var model = CounterModel()
// pass via init or @Environment

// in a child
let model: CounterModel
var body: some View { Text("\(model.count)") }
```

Mapping table:

| Flutter | SwiftUI | Note |
|---|---|---|
| `setState` (StatefulWidget) | `@State` | View-local mutable state. |
| `ChangeNotifier` + Provider | `@Observable` | iOS 17+; replaces `ObservableObject`. |
| `ChangeNotifier` + `Consumer` | `@Observable` ref + plain property read | The view rebuild is automatic. |
| `Provider.of<T>(context, listen: false)` | `@Environment(T.self)` | Read from environment without observing. |
| Riverpod `StateProvider` | `@State` for transient UI; `@Observable` ref for shared | No 1:1 — Riverpod's "global" feel maps to environment-injected models. |
| Riverpod `FutureProvider` | `Task` in `.task { }` modifier | Async side effects scoped to view lifetime. |
| BLoC | `@Observable` model with `AsyncStream` of state | The pattern works; the framework support is lighter. |

### Async

```dart
// Dart
Future<List<User>> fetchUsers() async {
  final resp = await http.get(Uri.parse('https://example.com/users'));
  if (resp.statusCode != 200) throw HttpException('bad status');
  return (jsonDecode(resp.body) as List)
      .map((j) => User.fromJson(j))
      .toList();
}
```

```swift
// Swift
func fetchUsers() async throws -> [User] {
    let url = URL(string: "https://example.com/users")!
    let (data, response) = try await URLSession.shared.data(from: url)
    guard (response as? HTTPURLResponse)?.statusCode == 200 else {
        throw URLError(.badServerResponse)
    }
    return try JSONDecoder().decode([User].self, from: data)
}
```

The shape is identical; the differences are framework conventions (`URLSession`, `JSONDecoder`) and Swift's typed `throws`.

`Stream<T>` → `AsyncSequence`:

```dart
Stream<int> ticks() async* {
  while (true) {
    await Future.delayed(Duration(seconds: 1));
    yield DateTime.now().second;
  }
}
```

```swift
func ticks() -> AsyncStream<Int> {
    AsyncStream { continuation in
        let task = Task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                continuation.yield(Calendar.current.component(.second, from: .now))
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in task.cancel() }
    }
}
```

See [Combine & AsyncStream](combine-and-async-streams.md) for the deep dive.

### Null safety

Dart and Swift agree on the principle: nullability is in the type system, not a runtime annotation. The ergonomics align:

| Dart | Swift |
|---|---|
| `String?` | `String?` |
| `s?.length` | `s?.count` |
| `s ?? 'default'` | `s ?? "default"` |
| `s!` (force unwrap) | `s!` (force unwrap) |
| `late String x` | `var x: String!` (rare) or `var x: String?` |
| `if (s != null) s.length` (with promotion) | `if let s { s.count }` |

Swift's `if let` is the idiomatic "promote optional to non-optional in this scope" — equivalent to Dart's null-promotion in `if` checks.

---

## Concurrency model

| Dart | Swift |
|---|---|
| `Future<T>` | `async` function returning `T` |
| `Stream<T>` | `AsyncSequence` / `AsyncStream` |
| `await` | `await` |
| `async`/`async*` (generator) | `async` function / `AsyncStream { … }` |
| `Isolate.spawn` | Dispatch to a `Task` (different model — see below) |
| `compute<Q, R>(…)` | `await Task.detached { … }.value` (with Sendable arguments) |
| Cancellation: `CancelToken` libraries | `Task.isCancelled` / `Task.checkCancellation()` (built in) |

**The biggest model difference: isolates vs actors.** Dart's `Isolate` is a separate heap with no shared memory — communication goes through ports, like Web Workers. Swift's `Task` and `actor` share the heap; isolation is enforced by the type system (`Sendable`, actor isolation), not by physical separation.

For most Flutter apps the practical consequence is: the `compute` function used for one-off heavy work becomes a `Task.detached` block. Long-lived isolates with port-based messaging become actors with method calls.

```dart
// Dart
final users = await compute(parseUsers, jsonString);
```

```swift
// Swift — same intent, much lighter ceremony
let users = try await Task.detached(priority: .userInitiated) {
    try JSONDecoder().decode([User].self, from: jsonData)
}.value
```

See [Strict Concurrency & Sendable](concurrency-and-sendable.md) for actors and the `Sendable` checking that catches data-race bugs at compile time.

---

## Memory model

Dart's GC pauses (mostly imperceptibly) to collect garbage. Swift's ARC counts references at compile-time-inserted retain/release pairs, with no pauses but a different failure mode: **retain cycles do not get collected**.

| Dart | Swift |
|---|---|
| GC handles cycles automatically | You break cycles manually with `weak` / `unowned` |
| Closures retain captured state | Closures retain captured state; **manual `[weak self]` discipline required** |
| `WeakReference<T>` | `weak var x: Foo?` |
| Finalizer (`Finalizer<T>`, rare) | `deinit` |

The Flutter widget rebuild model masks this: widgets are recreated each build, and old widgets become garbage. In SwiftUI, *views* are recreated each build but **state references** (`@State`, `@Observable` instances, `@StateObject`) live across builds. A retain cycle there is permanent.

The most common trap:

```swift
// In a Combine subscription stored on the view model:
service.events
    .sink { event in
        self.handle(event)        // captures self strongly
    }
    .store(in: &cancellables)     // cancellables stored on self
// self ↔ cancellables ↔ closure ↔ self — leak
```

Fix:

```swift
service.events
    .sink { [weak self] event in
        self?.handle(event)
    }
    .store(in: &cancellables)
```

See [ARC, Captures & Lifetimes](arc-and-lifetimes.md) for a complete treatment.

---

## Where it gets weird

1. **No `BuildContext`. The environment replaces it.** SwiftUI's `@Environment(\.dismiss)`, `@Environment(\.colorScheme)`, etc. take the place of `Theme.of(context)` and friends. Custom environment values are a few lines of boilerplate.

2. **Modifiers compose — they don't wrap.** Where Flutter wraps with `Padding(padding: …, child: Container(decoration: …, child: Text(…)))`, SwiftUI chains: `Text(…).padding(…).background(…)`. This produces a different code shape and is easier on the eyes — but the order matters, sometimes subtly. `.frame(width: 100).background(.red)` and `.background(.red).frame(width: 100)` produce different visual results.

3. **No `const` constructors. `Equatable` view models do similar work.** Flutter's `const` widgets are skipped during rebuild. SwiftUI's equivalent is structural equality: if two views compare equal (and they're value types so this is cheap), the framework skips re-rendering. Conform your view models to `Equatable` and `Hashable` for the same effect.

4. **No global navigator. Navigation is data.** Flutter's `Navigator.push(…)` is imperative. SwiftUI 16+ uses `NavigationStack(path:)` with a binding to a path collection — navigation is observable state. This is a real reshape, especially if your Flutter app leans heavily on `Navigator` keys and named routes.

5. **No `setState` — direct mutation is the trigger.** This is liberating but trips up muscle memory for the first week.

6. **Hot reload is gone.** Xcode has SwiftUI Previews — closer to Storybook than to Flutter hot reload. Most teams rebuild the simulator (~5-15 seconds incrementally) for full app testing and rely on Previews for component-level iteration.

---

## Real-world port: a `ChangeNotifier`-based VM

```dart
// Flutter
class FeedViewModel extends ChangeNotifier {
  final FeedService _service;
  FeedViewModel(this._service);

  bool _isLoading = false;
  List<Post> _posts = [];

  bool get isLoading => _isLoading;
  List<Post> get posts => _posts;

  Future<void> load() async {
    _isLoading = true; notifyListeners();
    try {
      _posts = await _service.fetchPosts();
    } finally {
      _isLoading = false; notifyListeners();
    }
  }
}
```

```swift
// SwiftUI / iOS 17+
import Observation

@Observable
@MainActor
final class FeedViewModel {
    private(set) var isLoading = false
    private(set) var posts: [Post] = []

    private let service: FeedService

    init(service: FeedService) {
        self.service = service
    }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            posts = try await service.fetchPosts()
        } catch {
            // surface error state — omitted for brevity
        }
    }
}
```

```swift
// The view
struct FeedView: View {
    @State private var model = FeedViewModel(service: .shared)

    var body: some View {
        Group {
            if model.isLoading {
                ProgressView()
            } else {
                List(model.posts) { post in PostRow(post: post) }
            }
        }
        .task { await model.load() }
    }
}
```

What disappeared:

- `notifyListeners()` calls. `@Observable` synthesises change tracking at compile time.
- `Consumer<FeedViewModel>` wrappers. The view reads the property; SwiftUI tracks the dependency automatically.
- The `try/finally`. `defer` is the Swift idiom.
- Manual `dispose()` of the VM. SwiftUI's `@State` owns the lifecycle.

What appeared:

- `@MainActor`. The VM is touched from views and bindings; main-actor isolation is enforced at compile time.
- `.task { await model.load() }`. View-lifetime-scoped async work — cancelled automatically when the view goes away.

---

## Performance: the rebuild cost model

This is the area where Flutter and SwiftUI diverge most:

- **Flutter rebuilds the widget tree, then diffs against the element tree to decide what RenderObjects to update.** Cheap widgets (`const Widget(…)`) are skipped. Heavy `build` methods are a real cost.
- **SwiftUI rebuilds the body computation, then uses structural equality on its value-type views to decide whether to re-render.** Make your view bodies small and your dependency graph clean and the framework prunes most work.

The practical advice that maps across:

- **Flutter's `const Widget` constructors → SwiftUI's `Equatable` conformance on view models.** Both let the framework skip work when nothing relevant has changed.
- **Flutter's `RepaintBoundary` → SwiftUI's `.drawingGroup()` / `.compositingGroup()`.** Use sparingly; useful for heavy custom drawing.
- **Flutter's `ListView.builder` lazy construction → SwiftUI's `List` (lazy by default) or `LazyVStack` inside `ScrollView`.** Avoid `VStack(ForEach(…))` for long lists — that's eagerly built.

---

## Where this fits with the rest of the guide

- [UI Development with SwiftUI](../04-ui-development/swiftui-guide.md) — the SwiftUI deep dive
- [Strict Concurrency & Sendable](concurrency-and-sendable.md) — actors, `@MainActor`, `Sendable`
- [ARC, Captures & Lifetimes](arc-and-lifetimes.md) — closures, retain cycles, `[weak self]`
- [Combine & AsyncStream](combine-and-async-streams.md) — Rx-shaped streams
- [Codable Customization](codable-deep.md) — JSON encoding/decoding
- [Persistence](../03-architecture/persistence.md) — Hive / Drift / Isar mappings
- [UIKit Guide](../04-ui-development/uikit-guide.md) — useful for Flutter teams that need a native shell to host a remaining hybrid screen

---

*Last updated: 2026-05-04 — BUILD-25.*
