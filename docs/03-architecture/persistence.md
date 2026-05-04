# Persistence: From ORMs to Core Data and SwiftData

> If you're coming from Prisma, Drizzle, ActiveRecord, SQLAlchemy, Hibernate, or Room, iOS persistence will feel unfamiliar. This chapter maps your existing ORM mental model onto Apple's two managed-object frameworks (Core Data and SwiftData) and gives you a decision tree for the storage tier.

---

## Decision Tree: Pick Your Storage

Not every app needs an ORM. Use this ladder, lightest first:

```
┌─────────────────────────────────────────────────────────────┐
│ Q: How much data and how structured is it?                  │
└─────────────────────────────────────────────────────────────┘
       │
       ├── A few flags, settings, last-used values
       │     → UserDefaults                (key/value, plist-backed)
       │
       ├── Sensitive secrets (tokens, passwords)
       │     → Keychain                    (encrypted, OS-managed)
       │
       ├── Files: images, video, downloaded payloads
       │     → FileManager + Data          (just write bytes)
       │
       ├── Structured data, < ~100 entities, simple queries
       │     → SwiftData                   (modern, codegen-free)
       │
       ├── Structured data, complex queries, migrations, CloudKit sync
       │     → Core Data                   (battle-tested, more API)
       │
       └── You'd reach for SQLite directly on Android/web
             → SQLite.swift / GRDB         (if you really want raw SQL)
```

A common mistake is reaching for a relational store for what's really key/value (a settings panel) or a file (a downloaded image). Match the tool to the shape of the data.

---

## UserDefaults — The Quick Tier

`UserDefaults` is a key/value store, plist-backed, automatically persisted. Use it for: theme preference, last-opened tab, "have we shown this onboarding screen" booleans.

```swift
// Write
UserDefaults.standard.set(true, forKey: "has_seen_onboarding")
UserDefaults.standard.set(Date(), forKey: "last_sync_date")

// Read
let seen = UserDefaults.standard.bool(forKey: "has_seen_onboarding")
let last = UserDefaults.standard.object(forKey: "last_sync_date") as? Date
```

Modern `@AppStorage` wraps it for SwiftUI:

```swift
struct SettingsView: View {
    @AppStorage("dark_mode") private var darkMode = false
    @AppStorage("font_size") private var fontSize = 16

    var body: some View {
        Toggle("Dark mode", isOn: $darkMode)
        Stepper("Font size: \(fontSize)", value: $fontSize, in: 12...24)
    }
}
```

**Don't store secrets in UserDefaults.** It's a plain plist file. Use Keychain.

**Don't put large blobs in UserDefaults.** It loads the whole plist into memory on first read. Use files.

---

## Keychain — The Secret Tier

The Keychain is OS-managed encrypted storage, designed for tokens, passwords, and sensitive identifiers. The native API is C-based and verbose; most apps use a wrapper like [KeychainAccess](https://github.com/kishikawakatsumi/KeychainAccess).

```swift
import KeychainAccess
let keychain = Keychain(service: "com.myapp.tokens")
keychain["api_token"] = "sk_live_..."
let token = keychain["api_token"]
```

For deeper integration (biometrics, sync, access groups across app extensions), consult Apple's `Security` framework documentation directly.

---

## Files — The Bytes Tier

For images, video, downloaded JSON blobs, and anything you'd put in `/var/lib/...` on a server, just write files:

```swift
let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)
    .first!
    .appendingPathComponent("article-42.json")

try data.write(to: url)
let loaded = try Data(contentsOf: url)
```

Two directories matter for app data:

| Directory | Backed up? | Survives iCloud restore? | Use for |
|---|---|---|---|
| `Documents/` | Yes | Yes | User-generated content |
| `Library/Application Support/` | Yes | Yes | App-managed databases, caches that should persist |
| `Library/Caches/` | No | Sometimes purged | Re-downloadable cached data |
| `tmp/` | No | Cleared at OS whim | Truly disposable |

Choosing the wrong directory either floods the user's iCloud backup or has the OS delete your data unexpectedly.

---

## SwiftData: The Modern Object Store (iOS 17+)

SwiftData is Apple's modern persistence framework — built on top of Core Data but with a much smaller API surface. Models are plain `@Model`-annotated classes; no `.xcdatamodeld` GUI editor required.

```swift
import SwiftData

@Model
final class Article {
    var id: UUID
    var title: String
    var body: String
    var publishedAt: Date
    @Relationship(deleteRule: .cascade) var comments: [Comment] = []

    init(title: String, body: String) {
        self.id = UUID()
        self.title = title
        self.body = body
        self.publishedAt = Date()
    }
}

@Model
final class Comment {
    var text: String
    var createdAt: Date
    var article: Article?

    init(text: String) {
        self.text = text
        self.createdAt = Date()
    }
}
```

### Setting up the container

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
            .modelContainer(for: [Article.self, Comment.self])
    }
}
```

That's it. Schema, migrations, Core Data stack — all generated.

### Querying with `@Query`

```swift
struct ArticleListView: View {
    @Query(sort: \Article.publishedAt, order: .reverse) private var articles: [Article]
    @Environment(\.modelContext) private var modelContext

    var body: some View {
        List(articles) { article in
            VStack(alignment: .leading) {
                Text(article.title).font(.headline)
                Text(article.body).font(.subheadline)
            }
        }
        .toolbar {
            Button("Add") {
                let new = Article(title: "Hello", body: "World")
                modelContext.insert(new)
            }
        }
    }
}
```

`@Query` is reactive — when the underlying store changes, the view updates. No explicit fetch, no observer wiring.

### Predicates (filtering)

```swift
let recent = #Predicate<Article> { $0.publishedAt > Date.now.addingTimeInterval(-86400) }
@Query(filter: recent, sort: \Article.publishedAt) private var articles: [Article]
```

`#Predicate` is a Swift macro that builds a typed query at compile time. No string-based query language.

### Manual fetch (when `@Query` isn't enough)

```swift
let descriptor = FetchDescriptor<Article>(
    predicate: #Predicate { $0.title.contains("Swift") },
    sortBy: [SortDescriptor(\.publishedAt, order: .reverse)]
)
let articles = try modelContext.fetch(descriptor)
```

### Delete and save

```swift
modelContext.delete(article)
try modelContext.save()         // explicit save (auto-saves on background, too)
```

---

## Core Data: The Older, Deeper Framework

Core Data has been Apple's ORM since 2005. It's more capable than SwiftData (richer fetch APIs, more migration tools, deeper CloudKit integration) at the cost of more API surface and a `.xcdatamodeld` schema file.

If you're starting fresh on iOS 17+, **prefer SwiftData**. Reach for Core Data when you need:
- Migration patterns more complex than SwiftData currently supports.
- Fine-grained control over the persistent store coordinator.
- An existing Core Data model you're maintaining.
- iOS 16 or earlier support.

### Core Data sketch (for reference)

```swift
// Entities defined in MyApp.xcdatamodeld GUI editor.
// Generated NSManagedObject subclasses are in DerivedData.

@FetchRequest(
    sortDescriptors: [NSSortDescriptor(keyPath: \Article.publishedAt, ascending: false)],
    animation: .default
) private var articles: FetchedResults<Article>
```

The `@FetchRequest` property wrapper is to Core Data what `@Query` is to SwiftData. Familiar shape; older syntax and slightly more setup.

---

## Migrations

Schema changes happen. Both frameworks support **lightweight migration** automatically when you add a new property or entity. **Heavyweight migrations** (renaming, splitting entities, transforming data) need explicit migration plans.

### SwiftData migration plan

```swift
enum AppMigrationPlan: SchemaMigrationPlan {
    static var schemas: [any VersionedSchema.Type] = [
        SchemaV1.self, SchemaV2.self
    ]
    static var stages: [MigrationStage] = [
        .lightweight(fromVersion: SchemaV1.self, toVersion: SchemaV2.self)
    ]
}

.modelContainer(for: [Article.self, Comment.self], migrationPlan: AppMigrationPlan.self)
```

### Core Data migration

Either configure mapping models in the GUI editor, or write programmatic migration with `NSPersistentStoreCoordinator`. This is the area where Core Data's age is most visible — the API is more verbose, but also more powerful for tricky cases.

**Rule:** every shipped schema is a contract you have to migrate from forever. Bump version numbers early (SchemaV1, SchemaV2) and write migration tests.

---

## CloudKit Sync

Both frameworks integrate with CloudKit for cross-device sync of a user's personal data. Configure in the model setup:

```swift
// SwiftData
.modelContainer(
    for: [Article.self],
    isAutosaveEnabled: true,
    isUndoEnabled: true,
    cloudKitDatabase: .private("iCloud.com.myapp")
)
```

```swift
// Core Data — use NSPersistentCloudKitContainer instead of NSPersistentContainer.
let container = NSPersistentCloudKitContainer(name: "MyApp")
```

Limitations to know going in:
- CloudKit sync is **per-user**, not multi-user — there's no shared editing.
- The user's iCloud account is the database; if they're signed out, sync silently doesn't happen.
- Schemas must be deployed to the CloudKit dashboard before going live.

---

## Mapping From ORMs You Already Know

### Models / Schema

| Your ORM | Maps to |
|---|---|
| Prisma `model Article { ... }` in `schema.prisma` | SwiftData `@Model final class Article` |
| Drizzle `pgTable("articles", { ... })` | SwiftData `@Model` |
| ActiveRecord `class Article < ApplicationRecord` | SwiftData `@Model` |
| SQLAlchemy `class Article(Base): __tablename__ = 'articles'` | SwiftData `@Model` |
| Hibernate `@Entity class Article` | SwiftData `@Model` |
| Room `@Entity data class Article(...)` | SwiftData `@Model` |

### Relationships

| Your ORM | SwiftData |
|---|---|
| `@OneToMany`, `hasMany`, `relations: { many: ... }` | `@Relationship var comments: [Comment]` |
| `@ManyToOne`, `belongsTo` | `@Relationship var article: Article?` |
| Cascading delete | `@Relationship(deleteRule: .cascade)` |

### Queries

| Your ORM | SwiftData |
|---|---|
| `prisma.article.findMany({ where: ... })` | `@Query(filter: #Predicate { ... })` |
| `Article.where(published: true)` | `@Query(filter: #Predicate { $0.published })` |
| `db.query.articles.findFirst({ ... })` | `try modelContext.fetch(FetchDescriptor<Article>(predicate: ..., fetchLimit: 1))` |
| `session.query(Article).filter(...)` | Same as above |
| `Article.findAll({ where, order, limit })` | `FetchDescriptor` |

### Migrations

| Your ORM | iOS |
|---|---|
| `prisma migrate dev` | SwiftData: `MigrationStage`; Core Data: model versioning + mapping models |
| Rails `bin/rails db:migrate` | Same |
| Alembic | Same |
| Flyway / Liquibase | Same |
| Room schema export | Same |

### Transactions

| Your ORM | iOS |
|---|---|
| `prisma.$transaction([...])` | Both frameworks: changes within one `ModelContext` save are atomic |
| ActiveRecord `Article.transaction do ... end` | Same |

### Reactivity

This is where iOS surprises ORM-trained devs: **the queries are reactive by default**.

```swift
@Query private var articles: [Article]    // automatically updates when store changes
```

In Prisma or Hibernate, you fetch and the data is dead. In SwiftData, the property is a live view. UIs built on `@Query` need no explicit refresh logic.

---

## Common Pitfalls

### 1. Querying on the main thread for large datasets

Both frameworks default to running fetches on the main thread. For thousands of records, push to a background context:

```swift
// Core Data
let bgContext = persistentContainer.newBackgroundContext()
bgContext.perform {
    let results = try? bgContext.fetch(request)
    // results live on bgContext only — pass IDs across, not objects
}
```

```swift
// SwiftData — use a ModelActor
@ModelActor
actor BackgroundLoader {
    func load() async throws -> [PersistentIdentifier] { /* ... */ }
}
```

### 2. Passing managed objects across actors

Core Data `NSManagedObject` and SwiftData `@Model` instances are **bound to their context**. Don't pass them across actor boundaries — pass `objectID`/`PersistentIdentifier` and re-fetch on the receiving side.

### 3. Forgetting to `save()`

Both frameworks have autosave but it's not instant. For app-foreground transitions or critical writes, call `try modelContext.save()` explicitly.

### 4. Treating SwiftData as drop-in for SQL

SwiftData hides the SQL. Composable `JOIN`s with arbitrary projections aren't a first-class feature. If your app's value is in complex relational queries (analytics, reporting), evaluate GRDB or SQLite.swift instead.

### 5. CloudKit field-name conflicts

CloudKit has reserved names and limits on field types. Plan your schema with CloudKit's constraints in mind from day one if you'll ever sync.

### 6. Schema versioning paid forward

The first release of your app sets a precedent. Add `VersionedSchema` (SwiftData) or numbered model versions (Core Data) **from day one**, even when the schema is trivial. Adding versioning later is harder than starting with it.

---

## Testing Persistence

```swift
// SwiftData — in-memory store for tests
let config = ModelConfiguration(isStoredInMemoryOnly: true)
let container = try ModelContainer(for: Article.self, configurations: config)
let context = ModelContext(container)
context.insert(Article(title: "Test", body: "..."))
try context.save()
```

```swift
// Core Data — in-memory store for tests
let container = NSPersistentContainer(name: "MyApp")
let description = NSPersistentStoreDescription()
description.type = NSInMemoryStoreType
container.persistentStoreDescriptions = [description]
container.loadPersistentStores { _, _ in }
```

Always test against an in-memory store. File-based test stores leak state between runs.

---

## When to Skip the Frameworks Entirely

Consider raw SQLite (via [GRDB](https://github.com/groue/GRDB.swift) or [SQLite.swift](https://github.com/stephencelis/SQLite.swift)) when:

- You want full SQL control (window functions, CTEs, custom indexing).
- You need cross-platform schema parity with an Android Room database.
- Your data model is read-heavy with complex projections that don't fit `@Query`.
- You're storing thousands of small records per second and need fine-grained transaction control.

GRDB is the most mature option and supports SwiftUI integration via `@FetchRequest`-shaped APIs.

---

**Companion chapters:**
- [Architecture Patterns](patterns.md) — where the persistence layer fits relative to view models.
- [Strict Concurrency & Sendable](../02-swift-fundamentals/concurrency-and-sendable.md) — `@ModelActor` and Core Data's threading model.

**Next:** [UI Development with SwiftUI](../04-ui-development/swiftui-guide.md).

*Last updated: 2026-05-04*
