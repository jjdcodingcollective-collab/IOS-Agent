# UI Development with SwiftUI

> Building iOS interfaces mapped from web concepts. If you can build a React component with JSX and CSS, you can build a SwiftUI view — the paradigm is the same, only the syntax changes.

---

## The Core Concept: Views Are Functions of State

React and SwiftUI share the same fundamental model: **UI = f(state)**. You declare what the UI should look like for a given state, and the framework handles updates.

```jsx
// React
function Greeting({ name }) {
  return <h1>Hello, {name}!</h1>;
}
```

```swift
// SwiftUI
struct Greeting: View {
    let name: String
    
    var body: some View {
        Text("Hello, \(name)!")
            .font(.title)
    }
}
```

Every SwiftUI view is a struct with a `body` property. Think of `body` as your `return` statement in a React component.

---

## Layout System: CSS → SwiftUI

There's no CSS in SwiftUI. Layout is done with **stacks**, **modifiers**, and **containers**.

### Flexbox → Stacks

```css
/* CSS Flexbox */
.container { display: flex; flex-direction: row; gap: 8px; }
.container-v { display: flex; flex-direction: column; gap: 8px; }
```

```swift
// SwiftUI equivalent
HStack(spacing: 8) {  // flex-direction: row
    Text("Left")
    Text("Right")
}

VStack(spacing: 8) {  // flex-direction: column
    Text("Top")
    Text("Bottom")
}

ZStack {  // position: absolute (layered on top of each other)
    Image("background")
    Text("Overlay")
}
```

### Common CSS → SwiftUI Modifier Mapping

| CSS | SwiftUI |
|---|---|
| `padding: 16px` | `.padding(16)` |
| `padding: 8px 16px` | `.padding(.horizontal, 16).padding(.vertical, 8)` |
| `background-color: blue` | `.background(.blue)` |
| `border-radius: 8px` | `.clipShape(RoundedRectangle(cornerRadius: 8))` |
| `color: white` | `.foregroundStyle(.white)` |
| `font-size: 24px` | `.font(.title)` or `.font(.system(size: 24))` |
| `font-weight: bold` | `.fontWeight(.bold)` |
| `opacity: 0.5` | `.opacity(0.5)` |
| `width: 100px` | `.frame(width: 100)` |
| `max-width: 400px` | `.frame(maxWidth: 400)` |
| `width: 100%` | `.frame(maxWidth: .infinity)` |
| `gap: 8px` | `VStack(spacing: 8)` or `HStack(spacing: 8)` |
| `overflow: scroll` | `ScrollView { ... }` |
| `display: none` | Conditional rendering (no modifier) |
| `box-shadow` | `.shadow(radius: 4)` |

### Modifier Order Matters

Unlike CSS where property order rarely matters, SwiftUI modifier order **changes the result**:

```swift
// Background THEN padding → background covers the padded area
Text("Hello")
    .padding()
    .background(.blue)

// Padding THEN background → background only covers the text
Text("Hello")
    .background(.blue)
    .padding()
```

Think of modifiers as wrapping your view in layers, from inside out.

---

## Components → Views

### Basic Component with Props

```jsx
// React
function UserCard({ name, role, avatarUrl }) {
  return (
    <div className="card">
      <img src={avatarUrl} alt={name} />
      <h2>{name}</h2>
      <p>{role}</p>
    </div>
  );
}
```

```swift
// SwiftUI
struct UserCard: View {
    let name: String
    let role: String
    let avatarUrl: URL
    
    var body: some View {
        VStack {
            AsyncImage(url: avatarUrl) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                ProgressView()
            }
            .frame(width: 80, height: 80)
            .clipShape(Circle())
            
            Text(name)
                .font(.headline)
            Text(role)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(radius: 2)
    }
}
```

### Conditional Rendering

```jsx
// React
{isLoggedIn ? <Dashboard /> : <Login />}
{showBanner && <Banner />}
```

```swift
// SwiftUI
if isLoggedIn {
    Dashboard()
} else {
    Login()
}

if showBanner {
    Banner()
}
```

### Lists (Like .map())

```jsx
// React
{items.map(item => (
  <ItemRow key={item.id} item={item} />
))}
```

```swift
// SwiftUI
ForEach(items) { item in
    ItemRow(item: item)
}

// Or in a styled list:
List(items) { item in
    ItemRow(item: item)
}
```

`List` gives you native iOS styling (separators, swipe actions, pull-to-refresh). `ForEach` is raw iteration. Items must conform to `Identifiable` (like requiring a `key` prop).

---

## Interactive Elements

### Buttons

```swift
Button("Tap Me") {
    // action
}

// Styled button
Button {
    handleSubmit()
} label: {
    Text("Submit")
        .frame(maxWidth: .infinity)
        .padding()
        .background(.blue)
        .foregroundStyle(.white)
        .clipShape(RoundedRectangle(cornerRadius: 8))
}
```

### Text Input

```jsx
// React
<input value={text} onChange={e => setText(e.target.value)} placeholder="Type here" />
<textarea value={longText} onChange={e => setLongText(e.target.value)} />
```

```swift
// SwiftUI
TextField("Type here", text: $text)      // Single line
TextEditor(text: $longText)               // Multi-line

// Secure input (like <input type="password">)
SecureField("Password", text: $password)
```

The `$` prefix creates a **binding** — a two-way connection to the state variable. It's like passing both the value and the setter in React.

### Toggle / Switch

```swift
Toggle("Dark Mode", isOn: $isDarkMode)
```

### Picker / Select

```swift
Picker("Category", selection: $selectedCategory) {
    Text("All").tag(Category.all)
    Text("News").tag(Category.news)
    Text("Tech").tag(Category.tech)
}
.pickerStyle(.segmented) // or .menu, .wheel, .inline
```

---

## Responsive Layout

Web developers use media queries. SwiftUI uses **size classes** and **adaptive layouts**.

```swift
struct AdaptiveView: View {
    @Environment(\.horizontalSizeClass) var sizeClass
    
    var body: some View {
        if sizeClass == .compact {
            // Phone layout (single column)
            VStack { content }
        } else {
            // Tablet/landscape layout (two columns)
            HStack { sidebar; content }
        }
    }
}

// GeometryReader for exact dimensions (like useRef + getBoundingClientRect)
GeometryReader { geometry in
    Text("Width: \(geometry.size.width)")
}

// ViewThatFits — automatically picks the layout that fits
ViewThatFits {
    HStack { labels }  // Try horizontal first
    VStack { labels }  // Fall back to vertical
}
```

---

## Navigation

```swift
// Tab bar (like bottom nav)
TabView {
    Tab("Home", systemImage: "house") {
        HomeView()
    }
    Tab("Search", systemImage: "magnifyingglass") {
        SearchView()
    }
    Tab("Profile", systemImage: "person") {
        ProfileView()
    }
}

// Push navigation (like clicking a link)
NavigationStack {
    List(articles) { article in
        NavigationLink(value: article) {
            ArticleRow(article: article)
        }
    }
    .navigationTitle("Articles")
    .navigationDestination(for: Article.self) { article in
        ArticleDetailView(article: article)
    }
}

// Modal / Sheet (like a dialog/modal)
.sheet(isPresented: $showSettings) {
    SettingsView()
}

// Full screen cover
.fullScreenCover(isPresented: $showOnboarding) {
    OnboardingView()
}
```

---

## Animations

```swift
// Implicit animation (like CSS transition)
Text("Hello")
    .scaleEffect(isExpanded ? 1.5 : 1.0)
    .animation(.spring, value: isExpanded)

// Explicit animation (like requestAnimationFrame)
withAnimation(.easeInOut(duration: 0.3)) {
    showDetail = true
}

// Transition (like CSS enter/exit animations)
if showBanner {
    BannerView()
        .transition(.move(edge: .top).combined(with: .opacity))
}
```

---

## Images and Assets

```swift
// Local images (from Assets.xcassets)
Image("myPhoto")
    .resizable()
    .scaledToFit()
    .frame(height: 200)

// SF Symbols (Apple's built-in icon library — like Lucide/Heroicons)
Image(systemName: "heart.fill")
    .foregroundStyle(.red)

// Remote images (like <img src={url}>)
AsyncImage(url: URL(string: "https://example.com/photo.jpg")) { phase in
    switch phase {
    case .success(let image):
        image.resizable().scaledToFill()
    case .failure:
        Image(systemName: "photo")
    case .empty:
        ProgressView()
    @unknown default:
        EmptyView()
    }
}
.frame(width: 200, height: 200)
.clipShape(RoundedRectangle(cornerRadius: 8))
```

**SF Symbols** are a huge advantage over web development — Apple provides 5,000+ vector icons that automatically adapt to text size, weight, and accessibility settings. Browse them at [developer.apple.com/sf-symbols](https://developer.apple.com/sf-symbols/) or download the SF Symbols app.

---

## Dark Mode

SwiftUI handles dark mode automatically if you use semantic colors:

```swift
// These adapt to light/dark mode automatically
Text("Title").foregroundStyle(.primary)    // Black in light, white in dark
Text("Subtitle").foregroundStyle(.secondary)
VStack { }.background(.background)          // White in light, dark gray in dark

// Custom colors that adapt
// Define in Assets.xcassets with "Any Appearance" and "Dark Appearance" variants

// Check current scheme
@Environment(\.colorScheme) var colorScheme
if colorScheme == .dark { /* ... */ }
```

---

## SwiftUI Previews (Like Storybook)

SwiftUI includes live previews directly in Xcode. No separate tool needed.

```swift
#Preview {
    UserCard(name: "Alice", role: "Developer", avatarUrl: URL(string: "https://example.com")!)
}

#Preview("Dark Mode") {
    UserCard(name: "Alice", role: "Developer", avatarUrl: URL(string: "https://example.com")!)
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    UserCard(name: "Alice", role: "Developer", avatarUrl: URL(string: "https://example.com")!)
        .environment(\.dynamicTypeSize, .xxxLarge)
}
```

---

**Next:** [Networking & API Integration](../05-networking/api-integration.md) — Calling your APIs from Swift.

*Last updated: 2026-04-25*
