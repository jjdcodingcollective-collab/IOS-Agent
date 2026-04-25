# Plan: iOS Code Converter — Review & Rewrite Pipeline

## Vision

An internal AI-powered tool that takes TypeScript web code and:
1. **Reviews** it — identifies components, patterns, and iOS translation complexity
2. **Rewrites** it — generates equivalent Swift/SwiftUI code with correct architecture
3. **Reports** — produces a migration summary with manual intervention notes

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   iOS Code Converter                 │
│                                                      │
│  Input: TypeScript source files / repo path          │
│                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────┐│
│  │  1. ANALYZER  │──▶│  2. REVIEWER  │──▶│3. WRITER ││
│  │              │   │              │   │          ││
│  │ Parse TS/TSX │   │ Map patterns │   │ Generate ││
│  │ Identify:    │   │ to iOS equiv │   │ Swift    ││
│  │ - Components │   │ Flag:        │   │ code per ││
│  │ - Routes     │   │ - Auto-conv  │   │ file     ││
│  │ - State mgmt │   │ - Needs work │   │          ││
│  │ - API calls  │   │ - No equiv   │   │          ││
│  │ - Styles     │   │              │   │          ││
│  └──────────────┘   └──────────────┘   └──────────┘│
│                                                      │
│  Output: Swift project + migration report            │
└─────────────────────────────────────────────────────┘
```

## Phased Approach

### Phase 1: Code Analyzer (Foundation)
**Goal:** Parse a TypeScript project and produce a structured manifest of what's in it.

**What it does:**
- Scans a directory of TS/TSX files
- Identifies: React components, hooks, routes, API calls, state stores, styles
- Classifies each element by conversion complexity (auto, assisted, manual)
- Outputs a JSON manifest + human-readable report

**Implementation:**
- Build as a **platform workflow** (multi-step, reusable)
- Step 1: File discovery — glob for `.ts`, `.tsx`, scan imports
- Step 2: Pattern detection — identify React patterns via heuristic analysis
- Step 3: Manifest generation — structured output of all detected elements

**Deliverable:** Given a repo path, produces `analysis.json` + `analysis-report.md`

---

### Phase 2: Code Reviewer (Intelligence Layer)
**Goal:** Take the manifest from Phase 1 and map each element to its iOS equivalent, using our reference guides as the knowledge base.

**What it does:**
- For each component/pattern found, looks up the iOS equivalent from `docs/`
- Scores conversion confidence (high/medium/low)
- Flags patterns with no clean iOS mapping (e.g., SSR, middleware)
- Produces a migration plan with prioritized file list

**Implementation:**
- Agent preset with our `docs/` as attached context
- Input: manifest from Phase 1
- Output: `migration-plan.md` with per-file conversion strategy

**Deliverable:** A detailed, file-by-file migration plan that a developer can execute or hand to Phase 3.

---

### Phase 3: Code Rewriter (Generation)
**Goal:** Actually generate Swift/SwiftUI code from TypeScript source, guided by the migration plan.

**What it does:**
- Takes a single TS/TSX file + its migration plan entry
- Generates the equivalent Swift file(s)
- Maps: JSX → SwiftUI Views, hooks → @State/@Observable, fetch → URLSession, CSS → modifiers
- Includes inline comments for anything that needs manual review

**Core conversion mappings:**

| TypeScript / React | Swift / SwiftUI |
|---|---|
| `.tsx` component | `View` struct |
| `useState` | `@State` |
| `useEffect` | `.task` / `.onAppear` |
| `useContext` | `@Environment` |
| Custom hook | `@Observable` ViewModel |
| `fetch()` / axios | `URLSession` + `Codable` |
| React Router routes | `NavigationStack` destinations |
| CSS / Tailwind classes | SwiftUI modifiers |
| `interface` / `type` | `struct: Codable` |
| `.env` vars | xcconfig values |
| `localStorage` | `UserDefaults` / Keychain |

**Deliverable:** Per-file Swift output + conversion notes.

---

### Phase 4: Project Assembler (Polish)
**Goal:** Assemble individual converted files into a buildable Xcode project structure.

**What it does:**
- Creates the standard iOS project layout (App/, Views/, Models/, ViewModels/, Services/)
- Generates the entry point (`MyAppApp.swift`)
- Maps route config to NavigationStack setup
- Generates `Package.swift` with required dependencies
- Creates xcconfig files from `.env` patterns

**Deliverable:** A complete, organized Swift project directory ready for Xcode.

---

## Technology Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Runtime | Platform workflows + agent presets | Internal tool, everything stays in-platform |
| TS parsing | Heuristic analysis + LLM | Lighter than full AST parser, good enough for pattern detection |
| Knowledge base | `docs/` folder in this repo | Already written, maintained alongside the tool |
| File processing | Per-file agents (parallelizable) | Avoids context window limits, allows concurrent conversion |
| Output format | Raw Swift files + markdown reports | Developers review and integrate, not blind copy-paste |
| Expansion | Plugin-based pattern matchers | Add new input languages by adding new analyzer patterns |

## Expansion Path (Beyond TypeScript)

The architecture is designed so the **Analyzer** is the only language-specific part:
- Phase 1 Analyzer = pluggable per input language
- Phases 2-4 work on the abstract manifest, not raw source

To support Python/Django, Vue, Angular, etc. later → write a new Analyzer plugin, reuse everything else.

---

## MVP Scope (Recommended Starting Point)

**Build Phase 1 + Phase 2 first** — the Analyzer and Reviewer.

Why: 
- Immediately useful without code generation — produces a migration plan your team can follow manually
- Validates the pattern-detection approach before investing in generation
- Lower-risk (reading code, not writing it)
- The migration plan output works with the reference guides already in `docs/`

**MVP input:** A single TS/TSX file or small component directory
**MVP output:** Analysis manifest + migration plan with iOS equivalents

---

## Implementation Steps

1. Create the **Analyzer workflow** — file scanner + pattern detector
2. Create a **Reviewer agent preset** — with `docs/` as knowledge base
3. **Test on a real component** from one of your Vercel projects
4. Iterate on detection accuracy before building the Rewriter
5. Build **Phase 3 (Rewriter)** once Phase 1+2 are reliable
6. Build **Phase 4 (Assembler)** when you have enough converted files to need it
