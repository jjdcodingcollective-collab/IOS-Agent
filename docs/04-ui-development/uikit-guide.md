# UIKit for Web & Imperative-UI Developers

> SwiftUI is the headline. UIKit is the codebase. Most production iOS apps you'll join are 60-100% UIKit, with SwiftUI bolted on for newer screens. This chapter is the bridge from imperative-UI traditions (DOM, Android Views, WPF/WinForms, ObjC UIKit) into the modern UIKit you'll actually need to read, modify, and embed SwiftUI inside.

> **Pair with [SwiftUI Guide](swiftui-guide.md)** for the declarative side, and the **[ARC chapter](../02-swift-fundamentals/arc-and-lifetimes.md)** for the retain-cycle traps that bite UIKit harder than SwiftUI.

---

## Why UIKit is still load-bearing

SwiftUI shipped in 2019. Most iOS apps shipping today are at least five years older than that, written entirely against UIKit. Even greenfield apps usually drop into UIKit when they need:

- A truly custom layout (SwiftUI's layout protocol is improving but still not a replacement for `intrinsicContentSize` + Auto Layout)
- A `UICollectionView` with compositional layout (the SwiftUI equivalent is much newer and still gappy)
- Anything requiring fine-grained control over `UIScrollView` behaviour
- `WKWebView` integration (you can wrap it in SwiftUI but the API surface is UIKit)
- `AVPlayerViewController`, `MFMailComposeViewController`, `UIDocumentPickerViewController` and friends — all UIKit
- Existing third-party SDKs that ship UIKit views (`UIView` subclasses, not `View` structs)

**The pragmatic truth:** know SwiftUI for new screens, know UIKit for everything else. Both will coexist for years.

---

## The three pillars

UIKit has three primary classes you build everything on top of:

| Class | Web analogue | Android analogue | What it owns |
|---|---|---|---|
| `UIView` | A DOM element (`<div>`, `<img>`) | `View` (the Android one) | Drawing, layout, gestures |
| `UIViewController` | A "page" or "screen" component | `Activity` / `Fragment` | A view tree + its lifecycle |
| `UIWindow` / `UIWindowScene` | The browser tab | The window/Activity host | The root container, presentation context |

A typical screen is **one `UIViewController`** that owns **one root `UIView`** with a tree of subviews under it. The window is created once at app launch and you rarely touch it directly.

```swift
// The skeleton every UIKit screen starts from
final class ProfileViewController: UIViewController {
    private let nameLabel = UILabel()
    private let avatarView = UIImageView()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        setupSubviews()
        setupConstraints()
    }
}
```

The `view` property is implicitly there — every `UIViewController` has a root `UIView` it owns.

---

## View controller lifecycle

The closest mental model from other ecosystems:

| UIKit method | React (class component) | Android `Activity` | When it fires |
|---|---|---|---|
| `init(coder:)` / `init(nibName:bundle:)` | `constructor` | `onCreate` (early) | Once, when the VC is constructed |
| `viewDidLoad` | `componentDidMount` (sort of) | `onCreate` (after `setContentView`) | Once, after the view tree is loaded |
| `viewWillAppear` | (no direct equivalent) | `onStart` | Every time the view is about to be shown |
| `viewDidAppear` | `componentDidMount` (more accurately) | `onResume` | Every time the view has been shown |
| `viewWillDisappear` | `componentWillUnmount` (sort of) | `onPause` | Every time the view is about to leave |
| `viewDidDisappear` | (no direct equivalent) | `onStop` | Every time the view has left |
| `viewDidLayoutSubviews` | (no equivalent — CSS handles this) | `onLayout` | After Auto Layout has positioned the subviews |
| `deinit` | `componentWillUnmount` (real one) | `onDestroy` | When the VC is deallocated |

**The single most common mistake from web devs:** putting setup code in `init` instead of `viewDidLoad`. The view tree doesn't exist yet in `init` — `self.view` will lazily load on first access, which is rarely what you want.

```swift
// WRONG — view tree may not be set up yet, you'll trigger an unintended load
init() {
    super.init(nibName: nil, bundle: nil)
    view.backgroundColor = .red  // forces view to load before viewDidLoad
}

// RIGHT
override func viewDidLoad() {
    super.viewDidLoad()
    view.backgroundColor = .red
}
```

**The most common mistake from Android devs:** assuming `viewWillAppear` is "the new `onResume`." It is, in spirit, but it fires for *every* presentation including returning from a pushed VC. Don't put expensive one-time setup there — that goes in `viewDidLoad`.

---

## Auto Layout (the constraint mental model)

Web layout is two systems duct-taped together: the document flow (block/inline) and the override systems (flexbox, grid, absolute). UIKit has one system: **constraints**. Every view's frame is the solution to a constraint solver, not a value you set directly.

A constraint says "this view's `leadingAnchor` equals that view's `trailingAnchor` plus 16 points." You declare enough of these to make the layout uniquely solvable, and Auto Layout computes positions.

### The CSS → Auto Layout mental flip

| CSS | Auto Layout | Notes |
|---|---|---|
| `margin-left: 16px` | `view.leadingAnchor.constraint(equalTo: parent.leadingAnchor, constant: 16)` | Margins live on the constraint, not the view |
| `width: 100px` | `view.widthAnchor.constraint(equalToConstant: 100)` | Explicit width constraint |
| `width: 100%` | `view.widthAnchor.constraint(equalTo: parent.widthAnchor)` | Match parent |
| `display: flex` | `UIStackView` | The closest single-construct equivalent |
| `position: absolute` | (default — set leading/top constraints to parent) | UIKit has no normal flow |
| `min-width: 200px` | `view.widthAnchor.constraint(greaterThanOrEqualToConstant: 200)` | Inequality constraints exist |
| `aspect-ratio: 16/9` | `view.heightAnchor.constraint(equalTo: view.widthAnchor, multiplier: 9.0/16.0)` | Same anchor, different multiplier |

### Programmatic Auto Layout in practice

```swift
private func setupConstraints() {
    // CRITICAL: this disables the implicit "I'll generate constraints from
    // your frame" behaviour. Without it, your constraints will conflict
    // with auto-generated ones and you'll get cryptic console warnings.
    avatarView.translatesAutoresizingMaskIntoConstraints = false
    nameLabel.translatesAutoresizingMaskIntoConstraints = false

    NSLayoutConstraint.activate([
        avatarView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16),
        avatarView.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
        avatarView.widthAnchor.constraint(equalToConstant: 64),
        avatarView.heightAnchor.constraint(equalTo: avatarView.widthAnchor),

        nameLabel.centerYAnchor.constraint(equalTo: avatarView.centerYAnchor),
        nameLabel.leadingAnchor.constraint(equalTo: avatarView.trailingAnchor, constant: 12),
        nameLabel.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -16),
    ])
}
```

The `translatesAutoresizingMaskIntoConstraints = false` line is the most-forgotten step in all of UIKit. If your constraints "do nothing" or you see `Unable to simultaneously satisfy constraints` errors, this is the first thing to check.

### Intrinsic content size

A `UILabel` with text already knows how big it wants to be. So does a `UIButton`, a `UIImageView` with an image, a `UISwitch`. You don't need to give them explicit width/height constraints — Auto Layout asks them via `intrinsicContentSize`.

This is the mental flip web devs miss: **most leaf views size themselves**. You only constrain the things they don't know — usually their position, and sometimes a `lessThanOrEqualTo` on width to allow truncation.

### Stack views (the flexbox of UIKit)

`UIStackView` is the closest thing to flexbox UIKit has. Use it generously — most rows of buttons, vertical lists of labels, and form layouts are simpler with stacks than with raw constraints.

```swift
let row = UIStackView(arrangedSubviews: [avatarView, nameLabel])
row.axis = .horizontal     // .vertical for column
row.spacing = 12
row.alignment = .center    // cross-axis (CSS align-items)
row.distribution = .fill   // main-axis (loose mapping to CSS justify-content)
```

---

## Storyboards, XIBs, programmatic — what to pick

Apple's tutorials lean on Storyboards. Production teams overwhelmingly do not. Three options:

| Option | Description | When to use |
|---|---|---|
| **Storyboards** | One `.storyboard` file holds many VCs and segues between them | Almost never on a real team — merge conflicts are brutal, refactoring is painful, performance suffers as files grow |
| **XIBs** | One `.xib` file per view or VC, no segues | Acceptable for static views or designer-driven layouts |
| **Programmatic** | All UI in Swift code | The de facto standard for production UIKit. Refactor-friendly, code-review-friendly, mergeable |

**Recommendation:** programmatic for new code. Don't migrate existing Storyboards — the cost rarely pays off. Just add new screens programmatically and let the Storyboard set shrink over time.

---

## `UITableView` and `UICollectionView` (modern style)

Lists were UIKit's most legacy-laden API for a decade — `numberOfRowsInSection`, `cellForRowAt`, manual `reloadData`/`insertRows` ceremony. Diffable data sources (iOS 13+) replaced almost all of that.

```swift
// Modern: UICollectionView with diffable data source
enum Section { case main }

private lazy var dataSource = UICollectionViewDiffableDataSource<Section, User.ID>(
    collectionView: collectionView
) { [weak self] collectionView, indexPath, userID in
    let cell = collectionView.dequeueReusableCell(
        withReuseIdentifier: "UserCell",
        for: indexPath
    )
    if let userCell = cell as? UserCell, let user = self?.userByID[userID] {
        userCell.configure(with: user)
    }
    return cell
}

func update(with users: [User]) {
    var snapshot = NSDiffableDataSourceSnapshot<Section, User.ID>()
    snapshot.appendSections([.main])
    snapshot.appendItems(users.map(\.id))
    dataSource.apply(snapshot, animatingDifferences: true)
}
```

The diffable API takes a snapshot of the desired state and computes inserts/deletes/moves itself. You don't tell it "row 3 was inserted at index 5"; you give it the new array and it figures it out. This is conceptually identical to React's reconciliation or Android's `DiffUtil` — and it removes the entire class of "I forgot to reload that section" bugs.

### Cell reuse — the trap

The view does not stay attached to its data. The collection view recycles cells: a cell that just showed user A may, two scrolls later, show user Z. **Always reset state in `prepareForReuse`** or in your `configure` method:

```swift
final class UserCell: UICollectionViewCell {
    private let avatarView = UIImageView()
    private var imageTask: Task<Void, Never>?

    override func prepareForReuse() {
        super.prepareForReuse()
        imageTask?.cancel()      // cancel pending image load
        avatarView.image = nil   // clear stale image
    }

    func configure(with user: User) {
        imageTask = Task { [weak avatarView] in
            let image = try? await ImageLoader.shared.image(for: user.avatarURL)
            avatarView?.image = image
        }
    }
}
```

The `[weak avatarView]` capture is essential. Without it, a slow image load can hold the cell alive across reuses, and you'll see flashing wrong avatars.

---

## Navigation

Three primary patterns; you'll see them mixed in any real app.

```swift
// 1. Push onto a navigation stack (the "drill in" pattern)
navigationController?.pushViewController(detailVC, animated: true)
navigationController?.popViewController(animated: true)

// 2. Modal presentation (the "this blocks the world until dismissed" pattern)
present(modalVC, animated: true)
modalVC.dismiss(animated: true)

// 3. Tab bar (top-level switching)
// Configured at app launch, not navigated to imperatively
let tabBar = UITabBarController()
tabBar.viewControllers = [feedNav, searchNav, profileNav]
```

Mental model: a `UINavigationController` is a stack of VCs (push/pop), a `UITabBarController` is a switcher (no stack — each tab keeps its own state), and modals overlay the current VC.

The web analogue isn't a perfect fit. Navigation pushes feel like routing, but each pushed VC keeps full state — closer to keeping React Router history with all the prior pages still mounted in memory.

---

## Gestures, the responder chain, and event bubbling

UIKit events bubble up the **responder chain**: from the touched view, to its superview, to the view controller, eventually to the window and the app delegate. This is the same shape as DOM event bubbling, with a few twists.

```swift
// The web way: addEventListener('tap', handler)
// The UIKit way: a gesture recognizer attached to the view

let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap))
view.addGestureRecognizer(tap)

@objc private func handleTap() {
    // ...
}
```

The `#selector` and `@objc` ceremony comes from UIKit's Objective-C heritage — `UIGestureRecognizer` was designed before Swift existed and uses ObjC dispatch. See the [ObjC Interop chapter](../02-swift-fundamentals/swift-objc-interop.md) for the full picture.

### Target-action and retain cycles

`addTarget(_:action:for:)` and `UIGestureRecognizer(target:action:)` use **unowned-style references** to the target — they will not retain `self`. This is why you almost never need `[weak self]` for these specifically. But beware the inverse: if your closure-based callbacks (e.g. `UIAction`) capture `self`, retain cycles do happen.

```swift
// Closure-based — capture rules apply
let action = UIAction { [weak self] _ in
    self?.didTapButton()
}
button.addAction(action, for: .touchUpInside)
```

---

## Bridging to and from SwiftUI

Modern apps mix freely. The two adapters you need:

### SwiftUI inside a UIKit screen — `UIHostingController`

```swift
final class FeedViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        let swiftUIView = NewItemBanner(onTap: { [weak self] in
            self?.openComposer()
        })

        let host = UIHostingController(rootView: swiftUIView)
        addChild(host)
        view.addSubview(host.view)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            host.view.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])
        host.didMove(toParent: self)
    }
}
```

`UIHostingController` is a `UIViewController` whose root view is SwiftUI. Add it as a child VC — that's standard child VC composition.

### UIKit inside a SwiftUI screen — `UIViewRepresentable`

```swift
struct ActivityIndicator: UIViewRepresentable {
    let isAnimating: Bool

    func makeUIView(context: Context) -> UIActivityIndicatorView {
        UIActivityIndicatorView(style: .medium)
    }

    func updateUIView(_ view: UIActivityIndicatorView, context: Context) {
        if isAnimating { view.startAnimating() } else { view.stopAnimating() }
    }
}
```

`UIViewRepresentable` for a `UIView` subclass; `UIViewControllerRepresentable` for a whole `UIViewController` (e.g. a `UIImagePickerController` or a third-party SDK's VC). For two-way state flow, use a `Coordinator` — the SwiftUI docs cover this in detail.

---

## Common pitfalls

1. **Forgetting `translatesAutoresizingMaskIntoConstraints = false`.** Symptom: constraints "do nothing," view appears full-frame or zero-size. Fix: set it to `false` on every view you constrain manually.

2. **Doing UI work off the main thread.** UIKit is `@MainActor`-style by convention (and increasingly by Swift 6 strict concurrency). Touching `.text` on a label from a background queue causes undefined behaviour, including delayed crashes. See the [concurrency chapter](../02-swift-fundamentals/concurrency-and-sendable.md).

3. **Storing strong references to `UIViewController` from a singleton or model.** The view controller has its own lifetime managed by `UINavigationController` or its presenter. If you hold it strongly, you'll either leak it or fight the navigation stack. Use `weak` for these references.

4. **Using `viewDidLoad` for "every-time-shown" setup.** It only fires once. If a navigation push and pop returns to the same VC, `viewDidLoad` won't fire again — `viewWillAppear` will. Pick the right hook.

5. **Cell reuse showing stale data.** Always reset image, text, and any cancellable work in `prepareForReuse`. Cancel async tasks; don't let them complete and write into a recycled cell.

6. **Auto Layout cycle warnings spamming the console.** "Unable to simultaneously satisfy constraints" — read the logs. Apple's diagnostic format is verbose but the broken constraint is named. The single most common cause: two width constraints on the same view (one from `intrinsicContentSize`, one from your code).

7. **Treating `UITableView`/`UICollectionView` like a `<ul>`.** It is not a list of nodes you append to. It is a windowing component that asks the data source what to show for visible index paths. Always think "data → snapshot → diff," not "DOM mutation."

---

## Where this fits with the rest of the guide

- [SwiftUI Guide](swiftui-guide.md) — the declarative side; bridge between the two via `UIHostingController` / `UIViewRepresentable`.
- [ARC, Captures & Lifetimes](../02-swift-fundamentals/arc-and-lifetimes.md) — UIKit's target-action history makes retain cycles more likely than in pure SwiftUI.
- [Strict Concurrency & Sendable](../02-swift-fundamentals/concurrency-and-sendable.md) — `@MainActor` is the right tool for UI updates from async code.
- [Swift / ObjC Interop](../02-swift-fundamentals/swift-objc-interop.md) — almost every UIKit API has an ObjC ancestry; useful when reading the framework headers.

---

*Last updated: 2026-05-04 — BUILD-23.*
