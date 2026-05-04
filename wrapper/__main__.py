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
import shutil
import sys
from pathlib import Path

from .explainer import format_branch_explainer
from .git_ops import (
    GitError,
    NEEDS_REVIEW_PREFIX,
    clone_repo,
    commit_conversion,
    push_branch,
)
from .orchestrator import run_conversion
from .post_flight import format_post_flight
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


def cmd_convert(args: argparse.Namespace) -> int:
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

    return 0 if result.success else 1


def cmd_convert_from_github(args: argparse.Namespace) -> int:
    """Clone a GitHub repo, convert it, and commit the output to a local branch."""
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
    gh.set_defaults(func=cmd_convert_from_github)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
