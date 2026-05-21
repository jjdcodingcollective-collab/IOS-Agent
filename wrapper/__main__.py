"""
Wrapper entry point.

  python -m wrapper convert <local-path>
  python -m wrapper convert-from-github <repo-url>

Phase 1: `convert <local-path>` runs the CLI against a local source dir.
Phase 2: `convert-from-github <url>` clones the repo, converts, and creates
a local conversion branch with the generated Swift project.
Phase 3: `convert-from-github <url> --push` (or interactive prompt) pushes
that branch to origin. The local commit is always created first so a
push failure is never destructive.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from converter.report import (
    ReportBuilder,
    ReportError,
    Source,
    render_json,
    render_markdown,
)

from .compatibility import UnsupportedCombination, assert_supported
from .compliance_step import run_compliance_step
from .disclaimer import show_and_confirm as _show_disclaimer
from .explainer import format_branch_explainer
from .preflight import format_preflight_report, run_preflight
from .xcode_step import run_xcode_step
from .git_ops import (
    GitError,
    NEEDS_REVIEW_PREFIX,
    clone_repo,
    commit_conversion,
    push_branch,
)
from .orchestrator import run_conversion
from .post_flight import default_base_branch, format_post_flight
from .pr_ops import gh_available, open_pr
from .repo_metadata import (
    RepoMetadata,
    fetch_repo_metadata,
    format_metadata_banner,
    parse_github_url,
)
from .triage import format_triage


def _confirm(prompt: str, assume_yes: bool) -> bool:
    """Prompt the user for confirmation, or auto-yes in non-interactive mode."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        # Refuse non-interactive runs unless they pass --yes — matches
        # CLAUDE.md's "ask before acting on irreversible work" rule. Phase 1
        # writes to a local output dir so it's actually reversible, but the
        # habit is worth establishing now.
        print("error: stdin is not a TTY; pass --yes to proceed non-interactively",
              file=sys.stderr)
        return False
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


TOOL_VERSION = "ios-agent 0.1.0"
REPORT_FILENAME_MD = "report.md"
REPORT_FILENAME_JSON = "report.json"

PLACEHOLDER_BUNDLE_ID_PREFIX = "com.example."
PLACEHOLDER_TEAM_ID = "TODO_TEAMID"

_BUNDLE_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _default_bundle_id(app_name: str) -> str:
    """Derive a placeholder reverse-DNS bundle id from the app name.

    The com.example.* prefix is reserved by Apple; the emitter emits a
    Layer-A blocker for any bundle id under that prefix so the developer
    must replace it before submission. We use the app slug (lowercased,
    non-alphanumerics collapsed) as the suffix so multi-app workspaces
    don't collide on the default.
    """
    slug = _BUNDLE_SLUG_RE.sub("", app_name.lower())
    if not slug:
        slug = "myapp"
    return f"{PLACEHOLDER_BUNDLE_ID_PREFIX}{slug}"


def _run_post_conversion_steps(
    *,
    source_dir: Path,
    output_dir: Path,
    app_name: str,
    bundle_id: str,
    team_id: str,
    brief: bool,
) -> None:
    """Run compliance + Xcode emit, accumulate findings, write report.md/json.

    Failure to render or write the report surfaces as a wrapper-level
    warning — the conversion + manifest + project.yml already landed; the
    report writer is not the ship-gate. Step 7's pre-flight scanner is.
    """
    builder = ReportBuilder(
        source=Source(
            archetype="web",
            target_mode="wrap",
            root=str(source_dir),
            rev=1,
        ),
        tool_version=TOOL_VERSION,
    )
    run_compliance_step(
        source_dir=source_dir,
        output_dir=output_dir,
        brief=brief,
        report_builder=builder,
    )
    run_xcode_step(
        source_dir=source_dir,
        output_dir=output_dir,
        app_name=app_name,
        bundle_id=bundle_id,
        team_id=team_id,
        brief=brief,
        report_builder=builder,
    )

    try:
        report = builder.build()
    except ReportError as exc:
        print(f"warning: report build failed: {exc}", file=sys.stderr)
        return

    md_path = output_dir / REPORT_FILENAME_MD
    json_path = output_dir / REPORT_FILENAME_JSON
    try:
        md_path.write_text(render_markdown(report), encoding="utf-8")
        json_path.write_text(render_json(report), encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not write report: {exc}", file=sys.stderr)
        return

    n_a = len(report.layer_a_blockers)
    n_b = len(report.layer_b_manual_review)
    n_c = len(report.layer_c_learnings)
    print(
        f"report: A={n_a} B={n_b} C={n_c} "
        f"→ {REPORT_FILENAME_MD}, {REPORT_FILENAME_JSON}"
    )


def _gate_combination(source: str, target: str, *, allow_unsupported: bool) -> int | None:
    """Check the compatibility matrix. Returns None to proceed, or an exit code."""
    try:
        assert_supported(source, target)
    except UnsupportedCombination as exc:
        if allow_unsupported:
            print(f"warning: --allow-unsupported set; proceeding despite: {exc}",
                  file=sys.stderr)
            return None
        print(f"error: {exc}", file=sys.stderr)
        print("Pass --allow-unsupported to override during development.",
              file=sys.stderr)
        return 2
    return None


def cmd_convert(args: argparse.Namespace) -> int:
    gate = _gate_combination("web", "wrap", allow_unsupported=args.allow_unsupported)
    if gate is not None:
        return gate

    if not _show_disclaimer(assume_yes=args.yes):
        return 1

    source = Path(args.source).resolve()
    if not source.is_dir():
        print(f"error: '{source}' is not a directory", file=sys.stderr)
        return 2

    output = Path(args.output).resolve() if args.output else (
        Path.cwd() / "workspace" / f"{source.name}-ios"
    )

    print(f"Source:  {source}")
    print(f"Output:  {output}")
    print(f"App:     {args.app_name}")
    print(f"Validate: {'no' if args.no_validate else 'yes'}")
    print()

    if not _confirm("Run conversion?", args.yes):
        print("Aborted.")
        return 1

    result = run_conversion(
        source_dir=source,
        output_dir=output,
        app_name=args.app_name,
        validate=not args.no_validate,
        quiet=True,
    )

    print()
    print(format_triage(result))

    if result.success:
        print()
        _run_post_conversion_steps(
            source_dir=source,
            output_dir=output,
            app_name=args.app_name,
            bundle_id=args.bundle_id or _default_bundle_id(args.app_name),
            team_id=args.team_id,
            brief=getattr(args, "brief", False),
        )

    return 0 if result.success else 1


def _do_open_pr(
    *,
    commit,
    meta: RepoMetadata | None,
    clone_dest: Path,
    summary_path: str,
    assume_yes: bool,
) -> int:
    """Phase 5: invoke `gh pr create` after a successful push.

    Returns the exit code for the wrapper. On any failure of the PR step
    we return 1 — the conversion + push already succeeded, but the user
    asked for the PR to be opened, so silently exiting 0 would mislead.
    """
    ok, hint = gh_available()
    if not ok:
        print()
        print(f"Cannot open PR: {hint}", file=sys.stderr)
        return 1

    print()
    if not _confirm(
        f"Open this PR now (gh pr create from {clone_dest})?",
        assume_yes=assume_yes,
    ):
        print("Skipping PR. The branch is pushed; open the PR manually when ready.")
        return 0

    base = default_base_branch(meta)
    title = f"iOS conversion (rev {commit.revision})"
    print(f"Running: gh pr create --base {base} --head {commit.branch} ...")
    info = open_pr(
        clone_dest,
        base=base,
        head=commit.branch,
        title=title,
        body_path=summary_path,
    )
    if info.opened and info.url:
        print(f"PR opened: {info.url}")
        return 0

    print("Could not open PR.", file=sys.stderr)
    if info.error:
        print(info.error, file=sys.stderr)
    if "already exists" in (info.error or "").lower():
        print(
            "Hint: the wrapper does not update PR descriptions on re-runs — "
            "edit the existing PR yourself or close+reopen.",
            file=sys.stderr,
        )
    return 1


def cmd_convert_from_github(args: argparse.Namespace) -> int:
    """Clone a GitHub repo, convert it, and commit the output to a local branch."""
    gate = _gate_combination("web", "wrap", allow_unsupported=args.allow_unsupported)
    if gate is not None:
        return gate

    if not _show_disclaimer(assume_yes=args.yes):
        return 1

    repo_url = args.repo_url
    # --yes implies --push (auto-yes on every prompt), unless the user
    # explicitly asked for --no-push.
    if args.yes and args.push is None:
        args.push = True
    workdir = Path(args.workdir).resolve() if args.workdir else (
        Path.cwd() / "workspace" / "github-clones"
    )
    workdir.mkdir(parents=True, exist_ok=True)

    # Derive a clone directory name from the URL.
    clone_name = repo_url.rstrip("/").split("/")[-1]
    if clone_name.endswith(".git"):
        clone_name = clone_name[:-4]
    clone_dest = workdir / clone_name

    output_dir = Path(args.output).resolve() if args.output else (
        Path.cwd() / "workspace" / f"{clone_name}-ios-output"
    )

    # Phase 4 pre-flight: fetch metadata once and reuse for both the banner
    # and the post-flight PR command (which needs the default branch).
    # Soft-fails on no network / no auth / non-GitHub URL.
    meta: RepoMetadata | None = None
    parsed = parse_github_url(repo_url)
    if parsed:
        try:
            meta = fetch_repo_metadata(parsed[0], parsed[1])
        except Exception:
            meta = None

    print(f"Repo:       {repo_url}")
    if meta and not args.brief:
        print(f"About:      {format_metadata_banner(meta)}")
    elif parsed and not args.brief:
        print("About:      (github metadata unavailable)")
    print(f"Clone to:   {clone_dest}")
    if args.source_subdir:
        print(f"Subdir:     {args.source_subdir}")
    print(f"Output:     {output_dir}")
    print(f"App name:   {args.app_name}")
    print(f"Branch:     {args.branch}")
    print(f"Validate:   {'no' if args.no_validate else 'yes'}")
    if args.push is True:
        push_banner = "yes (--push)"
    elif args.push is False:
        push_banner = "no (--no-push)"
    else:
        push_banner = "ask after commit"
    print(f"Push:       {push_banner}")
    print()

    if not _confirm("Clone, convert, and commit to local branch?", args.yes):
        print("Aborted.")
        return 1

    # If a previous clone exists at the destination, we need to clear it
    # before clone_repo will accept it (it refuses to overwrite).
    if clone_dest.exists():
        if not args.reuse_clone:
            print(f"Clone destination exists: {clone_dest}")
            if not _confirm("Remove and re-clone?", args.yes):
                print("Aborted.")
                return 1
            shutil.rmtree(clone_dest)
        else:
            print(f"Reusing existing clone at {clone_dest}")

    if not clone_dest.exists():
        print(f"Cloning {repo_url}...")
        try:
            clone_repo(repo_url, clone_dest, depth=args.depth)
        except GitError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    # Output dir is wiped per-run so stale reports don't survive into the commit.
    if output_dir.exists():
        shutil.rmtree(output_dir)

    convert_source = clone_dest
    if args.source_subdir:
        convert_source = (clone_dest / args.source_subdir).resolve()
        if not convert_source.is_dir():
            print(
                f"error: --source-subdir '{args.source_subdir}' does not exist "
                f"in the clone ({convert_source})",
                file=sys.stderr,
            )
            return 1

    print("Running converter...")
    result = run_conversion(
        source_dir=convert_source,
        output_dir=output_dir,
        app_name=args.app_name,
        validate=not args.no_validate,
        quiet=True,
    )

    print()
    print(format_triage(result))

    if not result.success:
        print()
        print("Converter failed; skipping commit.", file=sys.stderr)
        return 1

    print()
    _run_post_conversion_steps(
        source_dir=convert_source,
        output_dir=output_dir,
        app_name=args.app_name,
        bundle_id=args.bundle_id or _default_bundle_id(args.app_name),
        team_id=args.team_id,
        brief=args.brief,
    )

    print()
    print("Committing conversion to branch...")
    try:
        commit = commit_conversion(
            repo_path=clone_dest,
            conversion=result,
            branch_name=args.branch,
        )
    except GitError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print()
    print(f"Branch:    {commit.branch}")
    print(f"Revision:  rev {commit.revision}")
    print(f"Commit:    {commit.sha[:12]}")
    if commit.needs_review:
        print(
            f"Note:      branch is prefixed with '{NEEDS_REVIEW_PREFIX}' "
            f"because the run has validation errors or low confidence."
        )
    print()
    print(f"Inspect locally:")
    print(f"  cd {clone_dest}")
    print(f"  git log --oneline {commit.branch}")
    print(f"  git diff main..{commit.branch}")

    # Phase 4: educational mode — explain what's on the branch and how to
    # review it. Suppressed by --brief for power users.
    if not args.brief:
        print()
        print(format_branch_explainer(commit))

    # Phase 3: push. Three states for args.push:
    #   True  → push without asking (--push, also implied by --yes)
    #   False → never push (--no-push)
    #   None  → prompt the user (default)
    if args.push is False:
        print()
        print("Skipping push (--no-push). Run `git push -u origin "
              f"{commit.branch}` from {clone_dest} to publish.")
        return 0

    if args.push is None:
        print()
        if not _confirm(
            f"Push branch '{commit.branch}' to origin?",
            assume_yes=False,
        ):
            print(f"Skipping push. Run `git push -u origin {commit.branch}` "
                  f"from {clone_dest} to publish.")
            return 0

    print()
    print(f"Pushing {commit.branch} to origin...")
    try:
        push = push_branch(clone_dest, commit.branch)
    except GitError as e:
        # Hard refusal (e.g. protected branch). Local commit stays put.
        print(f"error: {e}", file=sys.stderr)
        print(f"Local branch is intact at {clone_dest}.", file=sys.stderr)
        return 1

    if push.pushed:
        print(f"Pushed: {push.remote}/{push.branch}")
        if push.remote_url:
            print(f"Remote: {push.remote_url}")

        # Phase 4 post-flight: tell the user exactly how to open the PR.
        # The summary lives at <output_dir>/.ios-conversion/generation-summary.md
        # but we reference it by its in-repo path so the gh command works
        # from inside the clone, where the user will run it.
        summary_in_repo = ".ios-conversion/generation-summary.md"
        print()
        print(format_post_flight(commit, push, meta=meta, summary_path=summary_in_repo))

        # Phase 5: optionally invoke `gh pr create` directly. Off by default;
        # opt in with --open-pr. The Phase 4 command stays printed above so
        # the manual path always works.
        if args.open_pr:
            return _do_open_pr(commit=commit, meta=meta, clone_dest=clone_dest,
                               summary_path=summary_in_repo, assume_yes=args.yes)
        return 0

    # Push failed — read-only fallback per the plan. Don't fail the run;
    # the user can fix credentials and retry the push themselves.
    print(f"Push failed — local commit is intact.", file=sys.stderr)
    print(f"  remote: {push.remote}", file=sys.stderr)
    if push.remote_url:
        print(f"  url:    {push.remote_url}", file=sys.stderr)
    print(f"  error:  {push.error}", file=sys.stderr)
    print(f"Retry with: cd {clone_dest} && git push -u origin {commit.branch}",
          file=sys.stderr)
    return 1


def cmd_preflight(args: argparse.Namespace) -> int:
    """Scan a source tree for App Store compliance issues without converting it."""
    source = Path(args.source).resolve()
    if not source.is_dir():
        print(f"error: '{source}' is not a directory", file=sys.stderr)
        return 2

    result = run_preflight(source)
    print(format_preflight_report(result, source, brief=getattr(args, "brief", False)))
    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wrapper",
        description="ios-agent wrapper — orchestrate the converter CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser(
        "convert",
        help="Convert a local TypeScript project to a Swift project.",
    )
    convert.add_argument("source", help="Path to the TypeScript source directory.")
    convert.add_argument(
        "--output", "-o",
        help="Output directory (default: workspace/<source-name>-ios).",
    )
    convert.add_argument(
        "--app-name",
        default="MyApp",
        help="Name for the generated iOS app (default: MyApp).",
    )
    convert.add_argument(
        "--bundle-id",
        default=None,
        help="Reverse-DNS bundle id for the generated iOS app "
             "(default: com.example.<slug>; the placeholder prefix triggers "
             "a Layer-A finding).",
    )
    convert.add_argument(
        "--team-id",
        default=PLACEHOLDER_TEAM_ID,
        help="10-character Apple Developer Team ID "
             "(default: TODO_TEAMID; the placeholder triggers a Layer-A finding).",
    )
    convert.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip swiftc validation (faster).",
    )
    convert.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts.",
    )
    convert.add_argument(
        "--brief",
        action="store_true",
        help="Suppress the metadata banner and educational mode "
             "(power-user output; the actionable lines remain).",
    )
    convert.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="Bypass the compatibility-matrix gate. Development override only; "
             "see docs/mvp-scope.md and config/compatibility-matrix.yaml.",
    )
    convert.set_defaults(func=cmd_convert)

    gh = sub.add_parser(
        "convert-from-github",
        help="Clone a GitHub repo, convert it, and commit to a local branch.",
    )
    gh.add_argument("repo_url", help="GitHub repository URL (HTTPS or SSH).")
    gh.add_argument(
        "--branch",
        default="ios-conversion",
        help="Branch name for the conversion (default: ios-conversion). "
             "Will be prefixed with 'Requires more review/' if the run has "
             "validation errors or low confidence.",
    )
    gh.add_argument(
        "--workdir",
        help="Directory where the repo will be cloned (default: workspace/github-clones).",
    )
    gh.add_argument(
        "--source-subdir",
        default=None,
        help="Convert only this subdirectory of the cloned repo "
             "(e.g. 'apps/mobile' for a monorepo).",
    )
    gh.add_argument(
        "--output", "-o",
        help="Converter output directory (default: workspace/<name>-ios-output).",
    )
    gh.add_argument(
        "--app-name",
        default="MyApp",
        help="Name for the generated iOS app (default: MyApp).",
    )
    gh.add_argument(
        "--bundle-id",
        default=None,
        help="Reverse-DNS bundle id for the generated iOS app "
             "(default: com.example.<slug>; the placeholder prefix triggers "
             "a Layer-A finding).",
    )
    gh.add_argument(
        "--team-id",
        default=PLACEHOLDER_TEAM_ID,
        help="10-character Apple Developer Team ID "
             "(default: TODO_TEAMID; the placeholder triggers a Layer-A finding).",
    )
    gh.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Shallow-clone depth (default: full clone).",
    )
    gh.add_argument(
        "--reuse-clone",
        action="store_true",
        help="If a clone already exists at the destination, use it as-is instead of re-cloning.",
    )
    gh.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip swiftc validation (faster).",
    )
    gh.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts. Implies --push unless --no-push is set.",
    )
    gh.add_argument(
        "--brief",
        action="store_true",
        help="Suppress the metadata banner and educational mode "
             "(power-user output; the PR command still appears).",
    )
    push_group = gh.add_mutually_exclusive_group()
    push_group.add_argument(
        "--push",
        dest="push",
        action="store_const",
        const=True,
        default=None,
        help="Push the conversion branch to origin without prompting.",
    )
    push_group.add_argument(
        "--no-push",
        dest="push",
        action="store_const",
        const=False,
        help="Commit locally only; do not push.",
    )
    gh.add_argument(
        "--open-pr",
        dest="open_pr",
        action="store_true",
        help="Phase 5: after a successful push, invoke `gh pr create` "
             "to open the pull request. Off by default. Requires the GitHub "
             "CLI (`gh`) to be installed and authenticated. Cannot be "
             "combined with --no-push.",
    )
    gh.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="Bypass the compatibility-matrix gate. Development override only; "
             "see docs/mvp-scope.md and config/compatibility-matrix.yaml.",
    )
    gh.set_defaults(func=cmd_convert_from_github, open_pr=False)

    pf = sub.add_parser(
        "preflight",
        help="Scan a source tree for App Store compliance issues without converting.",
    )
    pf.add_argument("source", help="Path to the TypeScript/JavaScript source directory.")
    pf.add_argument(
        "--brief",
        action="store_true",
        help="Print only the verdict and counts; suppress per-finding detail.",
    )
    pf.set_defaults(func=cmd_preflight)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # `--no-push` + `--open-pr` is incoherent — you can't open a PR for a
    # branch that wasn't pushed. argparse can't express this naturally
    # (different groups), so check here.
    if getattr(args, "open_pr", False) and getattr(args, "push", None) is False:
        parser.error("--open-pr cannot be combined with --no-push")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
