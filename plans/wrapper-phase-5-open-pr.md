# Plan: Wrapper Phase 5 — `--open-pr` via `gh pr create`

## Summary

Phase 4 left the `gh pr create` command on the user's clipboard. Phase 5
makes the wrapper run it, off by default, with the same safety rails the
rest of the wrapper uses for irreversible actions.

This is **deliberately small.** Phase 4 already built the formatter that
produces the exact `gh pr create` arguments. Phase 5 is mostly: (a)
detect `gh`, (b) authentication-check, (c) confirm with the user, (d)
invoke `gh pr create`, (e) parse the URL out of the output and surface
it.

## Decisions (locked)

| Question | Decision |
|---|---|
| Default behaviour | **Off.** Opening a PR is irreversible — surfaces to teammates, sends notifications, kicks CI. Stays opt-in via `--open-pr`. |
| `gh` not installed | Hard fail with a clear message: "`--open-pr` requires the GitHub CLI. Install: brew install gh, then `gh auth login`. Skipping PR." Do **not** silently degrade — the user explicitly asked to open a PR. |
| `gh` not authenticated | Same — hard fail with `gh auth login` instruction. |
| `--yes` and `--open-pr` together | `--yes` skips the confirmation prompt. Matches the existing `--yes` semantics. |
| `--no-push` and `--open-pr` together | Mutually incompatible — refuse at argparse time with a clear error. You can't open a PR for a branch that wasn't pushed. |
| Re-runs (rev 2+) | If a PR already exists for the head branch, `gh pr create` fails. Surface that error verbatim plus a hint: "An existing PR for `ios-conversion` was found. The wrapper does not update PR descriptions on re-runs — edit it yourself or close+reopen." |
| Repo without push | If push failed (read-only fallback), skip `--open-pr` with a one-line note. Don't try to open a PR for an unpushed branch. |
| Title and body | Title: `iOS conversion (rev N)` — same as the formatted command. Body: `--body-file .ios-conversion/generation-summary.md`, run from the clone working directory. |
| Output | Print whatever URL `gh pr create` returns to stdout, prefixed with "PR opened: ". |

## User flow (delta from Phase 4)

```
$ python -m wrapper convert-from-github https://github.com/acme/web-app --push --open-pr

[ existing pre-flight, clone, convert, commit, push output ]

Pushed: origin/ios-conversion
Remote: https://github.com/acme/web-app.git

Open a PR:
  gh pr create \
    --base main \
    --head ios-conversion \
    --body-file ".ios-conversion/generation-summary.md" \
    --title "iOS conversion (rev 1)"

  …or open in browser:
  https://github.com/acme/web-app/compare/main...ios-conversion?expand=1

Open this PR now? [y/N] y                                                    ← NEW (Phase 5)
Running: gh pr create …                                                      ← NEW
PR opened: https://github.com/acme/web-app/pull/42                           ← NEW
```

With `--yes`, the prompt is skipped. Without `--open-pr`, the command is
printed (as today) and the wrapper exits — Phase 4 behaviour preserved.

## Scope

### In scope

1. **`wrapper/pr_ops.py`** — new module. Three functions:
   - `gh_available() -> bool` — `which gh` plus `gh auth status` check
   - `open_pr(repo_path, base, head, title, body_path) -> PrInfo` —
     subprocess invocation, captures stdout/stderr, parses the PR URL
     out of `gh pr create`'s output (last URL line printed by `gh`)
   - A `PrInfo` dataclass holding `(opened: bool, url: str | None, error: str | None)`
2. **Argparse:** add `--open-pr` to `convert-from-github`. Mark
   `--no-push` and `--open-pr` mutually exclusive.
3. **`wrapper/__main__.py`:** after a successful push, if `--open-pr`
   is set:
   - Check `gh_available()`. Hard-fail with install hint if not.
   - Confirm (skipped by `--yes`).
   - Call `open_pr(...)` from inside the clone working directory.
   - Print the result.
4. **Tests** in `wrapper/tests/test_pr_ops.py`:
   - PR-URL extraction from realistic `gh pr create` output (it usually
     prints the URL on the last line; sometimes prepends "Creating
     pull request for…")
   - Error-path: `gh` exits non-zero with "a pull request for branch
     X already exists" — surface verbatim
   - `gh_available()` mocked via patched `subprocess.run`
5. **Documentation:** update `plans/github-round-trip.md` (Phase 5 ✅),
   `README.md` (Last Updated + scope banner), `context/ACTIVE.md`
   (Phase 5 ✅, "What's Next" — wrapper roadmap complete), and
   `context/REFERENCES.md` (new module + new flag).

### Out of scope

- Updating an existing PR description on rev 2+ (the user owns the PR).
- Auto-merge / auto-close.
- Drafting via `gh pr create --draft` — could be added later behind a
  flag if there's signal for it; not in v1 to keep the surface tight.
- Non-GitHub hosts. `--open-pr` is GitHub-only via `gh`.

## Implementation order

Single commit. The work is small enough that splitting hurts review more
than it helps.

1. Write `wrapper/pr_ops.py` and tests; verify with the suite.
2. Wire into `wrapper/__main__.py`.
3. Update plans/README/ACTIVE/REFERENCES.
4. Commit + push.

## Acceptance criteria

1. `python -m wrapper convert-from-github <url> --push --open-pr` on a
   machine with `gh` authenticated opens a PR and prints the URL.
2. Same command without `gh` installed prints a clear install hint and
   exits non-zero **after** the conversion + push have already
   succeeded — the PR step fails open, the conversion stays.
3. `--no-push --open-pr` is rejected by argparse with a one-line error.
4. Without `--open-pr`, the wrapper behaviour is unchanged (Phase 4
   command-printing path).
5. The new module has unit tests; no test invokes a real `gh` process.
6. One commit pushed to `main` with the project's structured commit
   message format.

## Risks / non-goals

- **Auth flows.** `gh auth status` doesn't prompt. We never run
  `gh auth login` from inside the wrapper — the user does that
  themselves. We only check, then refuse cleanly.
- **PR URL parsing.** `gh pr create` historically prints the URL on the
  last line. We grab the last URL-shaped token in stdout to be robust
  to "Creating pull request…" preambles. Add a regex test for both
  shapes.
- **Read-only fallback.** Phase 3 guaranteed local commits survive a
  failed push. Phase 5 must not regress that — `--open-pr` is checked
  *after* the push branch has already been confirmed.
- **No coupling back to Phase 4.** The `format_pr_command` formatter
  stays — both the printed command and the actual subprocess call use
  the same `(base, head, title, body_path)` tuple, so the user's
  copy-pasteable command and the wrapper's invocation always match.

## Notes

- After Phase 5, the wrapper roadmap is complete. The next investment
  is converter-side (source-language expansion, new `from-*` converters)
  or a hosted/paid-product layer above the wrapper — both are open and
  not on this plan.
