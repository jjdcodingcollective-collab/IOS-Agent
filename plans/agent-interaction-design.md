# Plan: Agent Interaction Design

> **Status (2026-05-04):** Surface 1 (CLI) and Surface 2 Phase 1+2 (wrapper)
> are now operational. Surface 3 (Claude Code) is the active development
> driver. Phase 3 of the wrapper (push) is next.

## Summary

This project has three distinct "agent" surfaces that each interact with users
differently. Today only one exists (the converter CLI); the other two are
implicit or absent. This plan defines each surface, its primary user, the
interaction patterns it should support, and how the three connect.

The design optimises for **you-now** (solo builder iterating fast) while
keeping the door open for **external devs later** (web developers running
their own conversions, learning iOS as they go).

The three surfaces:

1. **Converter CLI** — the one-shot Python program (`python -m converter.run`)
2. **Conversational wrapper** — a future chat agent that orchestrates the CLI
3. **Claude Code (this session)** — how I collaborate with you while building

---

## Surface 1: Converter CLI

**What it is today:** a one-shot CLI that takes a TS source dir, emits a Swift
project plus several markdown reports (analysis, migration plan, generation
summary, validation report, learning notes).

**Primary user (now):** you, debugging the pipeline against fixtures.
**Primary user (later):** external web devs converting their own apps.

### Current pain points

- All output dumped at once — no triage signal beyond confidence scores
- No way to re-run a single phase or single file
- Errors during conversion produce a stub Swift file with notes — but the
  user has to grep `notes` fields to find them
- No interactive recovery: if the analyzer mis-classifies a file, the user
  can't say "treat this as a hook, not a component"
- `--quiet` is binary; there's no log-level dial

### Interaction principles

1. **Triage by default.** The summary at the end of a run should tell the
   user the three things to look at first, not list every file.
2. **One-shot stays one-shot.** Don't add interactive prompts to the CLI —
   that's the conversational wrapper's job. The CLI should be scriptable.
3. **Exit codes carry meaning.** `0` = clean, `1` = converted with warnings,
   `2` = validation errors, `3` = pipeline failure. Lets the wrapper (and
   CI) react without parsing markdown.
4. **Every report is addressable.** Each TODO, low-confidence file, and
   validation error gets a stable identifier (e.g. `LOW-CONF:UserCardView`)
   so the conversational wrapper can refer back to it.

### Concrete next steps for this surface

- [ ] **Top-of-summary triage block** — top 3 lowest-confidence files, top 3
      validation errors, total TODO count, with file:line refs
- [ ] **`--phase {analyze,rewrite,assemble,validate}`** flag to run a single
      phase against existing intermediate state in the output dir
- [ ] **`--only <relpath>`** to re-run conversion for a single source file
      (re-uses existing manifest)
- [ ] **Stable issue IDs** in generation-summary and validation-report
      (`<KIND>:<file-stem>:<n>`)
- [ ] **Exit codes** as defined above

---

## Surface 2: Conversational Wrapper (Future)

**What it is:** a chat agent that wraps the CLI, holds project state across
turns, asks clarifying questions, and explains output in context. Probably
implemented as a Claude Code skill or a standalone agent backed by the
Anthropic SDK with prompt caching.

**Primary user (now):** you, when you don't want to remember CLI flags.
**Primary user (later):** external web devs who want guidance, not tooling.

### Why a conversational layer is the right shape

The CLI's output is dense and the right next action depends on what the user
cares about. A chat agent can:

- Read the analysis manifest and ask: "I see 3 Zustand stores and 1 Redux
  slice — convert all four, or skip Redux for now?"
- Read the validation report and offer: "5 files have type errors. Want me
  to fix them one at a time, or batch the easy ones first?"
- Read learning-notes.md and answer: "Why did UserCardView use `.task(id:)`
  instead of `.onAppear`?" — pulling from the annotations database directly.
- Re-run conversion with different flags based on user feedback.

### Interaction principles

1. **State lives on disk, not in the agent.** The CLI emits markdown +
   JSON; the agent reads them. This means a conversation can pick up
   mid-project on a different day or machine.
2. **Ask before acting on irreversible work.** Re-running conversion
   overwrites generated Swift — confirm if there are uncommitted edits to
   generated files. Same rule as CLAUDE.md's "executing actions with care".
3. **Prefer pointing over pasting.** When explaining a generated file, link
   to `Sources/MyApp/Views/UserCardView.swift:42` rather than pasting code
   blocks. Keeps the chat scannable.
4. **Three response modes:**
   - **Triage** — "what should I look at first?"
   - **Explain** — "why did the converter do X?"
   - **Iterate** — "fix this file / re-run with these settings"
   The agent picks the mode from the user's intent; the user can override.
5. **Educational by default for external devs, terse by default for you.**
   Detect via a project-level setting or inferred from message style.

### Concrete next steps for this surface

- [ ] Decide implementation: Claude Code skill (lower lift) vs standalone
      agent SDK app (more control, can be deployed)
- [ ] Define the conversation state contract: what does the agent read on
      each turn? (`analysis.json`, `generation-summary.md`,
      `validation-report.md`, `learning-notes.md`, project git status)
- [ ] Build a thin command surface: `triage`, `explain <file|symbol>`,
      `fix <issue-id>`, `rerun [--only <path>] [--phase ...]`
- [ ] Implement the educational/terse mode toggle
- [ ] Wire prompt caching against the on-disk reports (large, stable
      content — prime cache target)

---

## Surface 3: Claude Code Session (This Chat)

**What it is:** how I, Claude Code, work with you in this project. Distinct
from the future conversational wrapper because I have repo write access and
a different tool surface (Edit, Bash, TodoWrite, Plan, etc.).

**Primary user:** you, today.
**Primary user (later):** other contributors using Claude Code on this repo.

### Interaction principles (current behaviour to keep)

- **Plan before non-trivial implementation work.** Big features get a plan
  file in `plans/` first; small fixes do not.
- **Use TodoWrite for multi-step work, mark complete eagerly.** Already
  doing this — keep doing it.
- **One in_progress task at a time.** No batching completion.
- **Verify before claiming done.** Smoke-test new code, run end-to-end
  against the sample fixture before saying it works.
- **Commit only when asked.** Never auto-commit.
- **Terse updates between tool calls.** No narration, no summaries when the
  diff already says what changed.

### Patterns to formalise

- **When the user says "let's start," interpret as "implement now."** Skip
  re-confirmation, dive in, surface decisions only when they're real
  forks. (Already working well — worth stating so it sticks.)
- **When the user asks an exploratory question ("what's next?", "how
  should we approach X?"), answer in 2-3 sentences with a recommendation
  and tradeoff.** Don't draft a plan unless asked.
- **Phase-style work plans.** The build guide established that work flows
  in phases (A→B→C→D). Continue that pattern: when starting a phase,
  enumerate the BUILDs in a TodoWrite list and proceed in roadmap order.
- **End-of-task summary discipline.** A small table of what changed and
  one recommendation for what's next. No celebration, no recap of obvious
  steps.

### Open questions for this surface

- Should I auto-commit after each completed BUILD, or batch into phases?
  (Current default: never auto-commit, ask first.)
- Should I run the full E2E pipeline after every BUILD, or only at phase
  boundaries? (Current: phase boundaries — fast enough, catches integration
  issues without slowing iteration.)
- Memory usage: should I save build-guide phase progress to memory so
  future sessions know where you left off? (Probably yes — propose this
  separately.)

---

## How the three surfaces connect

```
┌──────────────────────────────────────────────────────────┐
│  Claude Code (Surface 3) — builds the converter          │
│  ───────────────────────────────────────────────         │
│                       │                                   │
│                       ▼                                   │
│  Converter CLI (Surface 1) — runs against TS source       │
│  emits: analysis.json, *.md reports, Swift project        │
│                       │                                   │
│                       ▼                                   │
│  Conversational wrapper (Surface 2) — reads CLI output    │
│  triages, explains, iterates with the end user            │
└──────────────────────────────────────────────────────────┘
```

Surface 1 is the contract between Surface 3 (build-time) and Surface 2
(use-time). Stable issue IDs, structured exit codes, and machine-readable
manifests keep the wrapper decoupled from CLI internals.

---

## Phasing recommendation

**Phase 1 — Tighten Surface 1** (1–2 BUILDs)
- Triage block in generation-summary
- Stable issue IDs
- Exit codes
- `--only <path>` flag

These unlock the wrapper without committing to its design yet.

**Phase 2 — Prototype Surface 2 as a Claude Code skill**
- Skills are cheap to ship and live in this repo
- Validate the interaction patterns against your real workflow
- Iterate before committing to a standalone agent

**Phase 3 — Promote Surface 2 to standalone agent (optional)**
- Only if external-dev demand materialises
- At that point, prompt caching, account-scoped state, and a deployable
  surface become worth the cost

**Surface 3** evolves continuously through CLAUDE.md and project memory —
no formal phase needed.

---

## Notes

- This plan deliberately doesn't pick an LLM, framework, or hosting target
  for Surface 2 — those are downstream of validating the interaction shape.
- The build guide (`gap-analysis-and-build-guide.md`) covers Surface 1
  feature gaps. Phase 1 of this plan extends that with UX-focused BUILDs;
  add them as BUILD-16+ when the time comes.
- Surface 3 principles overlap with CLAUDE.md guidance — if any of the
  patterns in this plan diverge from CLAUDE.md, CLAUDE.md wins.
