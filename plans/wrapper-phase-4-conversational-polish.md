# Plan: Wrapper Phase 4 — Conversational Polish

## Summary

Phase 3 made `python -m wrapper convert-from-github <url> --push` functionally
complete. Phase 4 makes it **usable by humans** without changing what the git
plumbing does. It adds three things on top of the existing commit/push
machinery:

1. **Pre-flight repo metadata** — before cloning, fetch what GitHub already
   knows (default branch, last push, primary language, visibility) and
   surface it in the confirmation prompt so the user can catch a wrong-repo
   typo before the clone runs.
2. **Post-flight PR-ready next steps** — after a successful push, print the
   exact `gh pr create` command (or the GitHub web URL) the user needs, so
   they don't have to remember the syntax or hunt down the URL.
3. **Educational mode** — first-time users see a short "what just landed
   on this branch and how to review it" summary explaining the
   `Requires-more-review/` prefix, the `.ios-conversion/` reports
   directory, and the per-file confidence scores.

This is **wrapper-only** — `converter/` and the existing `git_ops.py`
push semantics are untouched.

## Decisions (locked)

| Question | Decision |
|---|---|
| GitHub API auth | Use `gh auth token` if `gh` is installed and authenticated; else fall back to `GITHUB_TOKEN` env var; else fall back to **anonymous** API calls (works for public repos, rate-limited but adequate for the pre-flight summary). |
| Network failures | Soft-fail. Skip the metadata block, log one line, continue. The metadata is decorative; the conversion is the product. |
| `gh` dependency | Optional. We **detect** `gh` on PATH and prefer it for the post-flight URL/command, but fall back to constructing the URL by hand from the remote URL if `gh` is missing. |
| Educational mode trigger | Implicit on every run, but **gated** by a one-line `--brief` flag for power users. No persistent "first-time user" state on disk — that would be flaky and surprise CI. |
| Pre-flight order | Metadata fetch happens **before** the existing confirmation prompt. The prompt now includes the metadata in its banner. |
| Test surface | Unit tests for the URL parser and metadata formatter. The HTTP-fetch path is mocked in tests; we do **not** hit GitHub from CI. |

## Why these choices

- **Soft-fail metadata:** the worst pre-flight bug would be one that blocks
  conversion when GitHub is having an outage. The conversion has no
  technical dependency on the metadata — it only improves the prompt.
- **`gh` optional:** users who don't have `gh` installed should still
  benefit from Phase 4. The fallback is a `https://github.com/<owner>/<repo>/pull/new/<branch>`
  URL constructed from the remote, which is what `gh pr create` shows you
  anyway.
- **No first-time-user state file:** introducing a `~/.ios-agent/state.json`
  for "have we shown the educational message?" creates a sync problem
  across machines, breaks CI determinism, and gives us nothing in return.
  `--brief` covers the power-user case in one flag.

## User flow (delta from Phase 3)

```
$ python -m wrapper convert-from-github https://github.com/acme/web-app

Repo:       https://github.com/acme/web-app
About:      acme/web-app · public · TypeScript · default branch 'main'
            last push 2 days ago · 142 stars · 31 open PRs                  ← NEW (Phase 4)

Clone to:   …/workspace/github-clones/web-app
Output:     …/workspace/web-app-ios-output
App name:   MyApp
Branch:     ios-conversion
Validate:   yes
Push:       ask after commit

Clone, convert, and commit to local branch? [y/N] y

Cloning…
Running converter…
[triage summary]

Committing conversion to branch…
Branch:    ios-conversion
Revision:  rev 1
Commit:    a1b2c3d4e5f6

What's on this branch:                                                       ← NEW (Phase 4)
  • Sources/MyApp/         the generated Swift app
  • Tests/MyAppTests/      one stub per converted screen
  • .ios-conversion/       five reports, including generation-summary.md
                           with per-file confidence scores
  • Branch is unprefixed because validation passed (50/50). A
    'Requires-more-review/' prefix would have meant "look here first."

Push branch 'ios-conversion' to origin? [y/N] y
Pushing…
Pushed: origin/ios-conversion

Open a PR:                                                                   ← NEW (Phase 4)
  gh pr create --base main --head ios-conversion \
    --title "iOS conversion (rev 1)" \
    --body-file ".ios-conversion/generation-summary.md"

  …or open in browser:
  https://github.com/acme/web-app/compare/main...ios-conversion?expand=1
```

## Scope

### In scope

1. **`wrapper/repo_metadata.py`** — new module. Fetches repo metadata from
   GitHub's REST API (`GET /repos/{owner}/{repo}`). Auth via `gh auth token`
   subprocess or `GITHUB_TOKEN`. Returns a `RepoMetadata` dataclass with the
   fields used in the banner. Soft-fails on network errors, returns `None`.
2. **URL parsing** — extract `(owner, repo)` from any of: `https://github.com/owner/repo`,
   `https://github.com/owner/repo.git`, `git@github.com:owner/repo.git`,
   `github.com/owner/repo` (no scheme). Refuses non-GitHub hosts cleanly
   (Phase 4 doesn't add support for GitLab/Bitbucket; the metadata block
   simply skips for non-GitHub URLs).
3. **`wrapper/post_flight.py`** — new module. Builds the post-push next-steps
   text given a `CommitInfo` + `PushInfo` + repo URL. Two outputs: the
   `gh pr create` command and the compare URL fallback.
4. **Educational mode** — a small `wrapper/explainer.py` with one function
   `format_branch_explainer(commit: CommitInfo) -> str`. Branched on
   `commit.needs_review` (different message for prefixed vs unprefixed
   branches). Suppressed by `--brief`.
5. **`wrapper/__main__.py`** — wire all three into `cmd_convert_from_github`.
   Add `--brief` flag (suppresses pre-flight metadata + educational mode;
   post-flight PR command stays — that's the actionable output).
6. **Tests** — `wrapper/tests/test_repo_metadata.py` (URL parsing, response
   parsing, soft-fail behaviour); `wrapper/tests/test_post_flight.py`
   (`gh pr create` formatter, compare-URL fallback for missing `gh`,
   handling of SSH vs HTTPS remote URLs).

### Out of scope (Phase 5 or later)

- `--open-pr` flag and `gh pr create` invocation (Phase 5; Phase 4 only
  *prints* the command, doesn't run it).
- Webhook-driven re-conversion.
- Non-GitHub hosts (GitLab/Bitbucket) — metadata simply degrades to "unknown".
- A persistent first-time-user state file.
- `gh issue` / project-board automation.
- Updating an existing PR description on rev 2+ (the user owns the PR; the
  wrapper only tells them the command).

## Implementation order

Three commits. Each is independently reviewable and ships behind no flag —
on first run the user just sees the new output blocks.

### Commit 1 — Pre-flight metadata

- `wrapper/repo_metadata.py` (new)
  - `parse_github_url(url: str) -> tuple[str, str] | None`
  - `fetch_repo_metadata(owner: str, repo: str, token: str | None) -> RepoMetadata | None`
  - `_resolve_token() -> str | None` — tries `gh auth token` (subprocess),
    then `GITHUB_TOKEN`, then `None` (anonymous)
  - `format_metadata_banner(meta: RepoMetadata) -> str` — single-line
    summary used in the pre-flight banner
- `wrapper/__main__.py` — call into the metadata module, surface the
  result above the existing prompt. Soft-fails to a single-line "(github
  metadata unavailable)" if the fetch returns `None`.
- Tests for URL parsing (six URL shapes) and banner formatting (with all
  fields, with missing fields, with `None`).
- No network calls in tests — `fetch_repo_metadata` is monkey-patched.

### Commit 2 — Post-flight PR-ready next steps + educational mode

- `wrapper/post_flight.py` (new)
  - `format_pr_command(commit: CommitInfo, push: PushInfo, base_branch: str) -> str`
  - `format_compare_url(remote_url: str, base_branch: str, head_branch: str) -> str | None`
  - `_default_base_branch_from_metadata(meta: RepoMetadata | None) -> str` —
    uses the metadata `default_branch` if available, falls back to `"main"`
- `wrapper/explainer.py` (new)
  - `format_branch_explainer(commit: CommitInfo, validation_pass: int, validation_total: int) -> str`
  - Branches on `commit.needs_review` for the prefixed-vs-unprefixed prose
- `wrapper/__main__.py` — wire both, add `--brief` flag (suppresses the
  branch-explainer block and the metadata banner; PR command always shown).
- Tests:
  - `gh pr create` formatter: HTTPS remote, SSH remote, with `--body-file`
    pointing at the existing summary path
  - Compare URL builder: SSH-to-HTTPS conversion (`git@github.com:foo/bar.git`
    → `https://github.com/foo/bar/compare/main...ios-conversion?expand=1`)
  - Explainer text varies by `needs_review` flag

### Commit 3 — Documentation + plan-status sync

- Update `plans/github-round-trip.md`: mark Phase 4 ✅, list the three
  modules and the `--brief` flag.
- Update `README.md`:
  - Add `--brief` to the wrapper command surface.
  - Add a "Last Updated" entry covering the Phase 4 polish.
- Update `context/ACTIVE.md`: roadmap line is now "wrapper Phase 5 only".
- Update `context/REFERENCES.md`: list `wrapper/repo_metadata.py`,
  `wrapper/post_flight.py`, `wrapper/explainer.py` under the wrapper
  command surface section.

## Acceptance criteria

1. `python -m wrapper convert-from-github https://github.com/<public-repo>`
   on a connected machine prints the metadata banner before the prompt.
2. The same command on an offline machine still completes the conversion;
   the banner shows `(github metadata unavailable)` and nothing fails.
3. After a successful push, the output ends with a copy-pasteable
   `gh pr create` command and a fallback compare URL.
4. `--brief` suppresses the metadata banner and the branch-explainer
   block; the PR command still appears.
5. The three new modules each have unit tests; no test makes a real HTTP
   request.
6. `git_ops.py` is unchanged. The push semantics from Phase 3 are
   preserved exactly.
7. Three commits land on `main`, each with the project's structured
   commit-message format.

## Risks / non-goals

- **Auth pop-ups.** Calling `gh auth token` in a subprocess never prompts
  — `gh` either has a token cached or returns an error to stderr, in which
  case we fall back to anonymous. No interactive auth flow is added.
- **API rate limits.** Anonymous calls are rate-limited to 60/hour per IP.
  This is fine for one-off conversions but would matter for CI loops; CI
  runs should set `GITHUB_TOKEN`. Document this in the new module's
  docstring.
- **Surfacing too much.** The banner stays a **single line** — anything
  longer competes with the existing run banner for attention.
- **No coupling to Phase 5.** The post-flight code prints a `gh pr create`
  command but does not invoke it. Phase 5 will add `--open-pr`, which
  reuses the same formatter.

## Notes

- The `--brief` flag is intentionally not a config option in `~/.ios-agent`.
  Persistent config would make CI runs surprising; a single repeat-typed
  flag is fine.
- We could later promote the metadata banner into a richer multi-line
  "About this repo" block. Held off until there's signal that users want
  it; today's single line is information-dense enough to catch wrong-repo
  typos without slowing down power users.
