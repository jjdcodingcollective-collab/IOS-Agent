"""
Wrapper entry point.

  python -m wrapper convert <local-path>
  python -m wrapper convert-from-github <repo-url>

Phase 1: `convert <local-path>` runs the CLI against a local source dir.
Phase 2: `convert-from-github <url>` clones the repo, converts, and creates
a local `ios-conversion` branch with the generated Swift project. No push
yet — Phase 3 will add that.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .git_ops import (
    GitError,
    NEEDS_REVIEW_PREFIX,
    clone_repo,
    commit_conversion,
)
from .orchestrator import run_conversion
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

    print(f"Repo:       {repo_url}")
    print(f"Clone to:   {clone_dest}")
    if args.source_subdir:
        print(f"Subdir:     {args.source_subdir}")
    print(f"Output:     {output_dir}")
    print(f"App name:   {args.app_name}")
    print(f"Branch:     {args.branch}")
    print(f"Validate:   {'no' if args.no_validate else 'yes'}")
    print(f"Push:       no (Phase 2 — local commit only)")
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

    return 0


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
        help="Skip confirmation prompts.",
    )
    gh.set_defaults(func=cmd_convert_from_github)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
