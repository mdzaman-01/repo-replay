"""Command-line entry point: ``repo-replay [repo] [options]``."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from typing import List, Optional, Tuple

from . import __version__
from .compact import DEFAULT_EXCLUDES, batch_commits, build_payload, filter_commits
from .gitlog import GitError, is_git_repo, read_history, repo_name
from .render import render_html

URL_RE = re.compile(r"^(https?://|git@|ssh://|git://|file://)")
SHORTHAND_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="repo-replay",
        description="Turn a git repository's history into a self-contained, interactive HTML animation.",
        epilog="Examples:\n"
               "  repo-replay                      replay the repo in this folder\n"
               "  repo-replay ~/code/myapp --open  replay and open it in your browser\n"
               "  repo-replay torvalds/linux       clone a public GitHub repo and replay it\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("source", nargs="?", default=".",
                   help="local path, git URL, or GitHub 'owner/name' (default: current folder)")
    p.add_argument("-o", "--output", help="output file (default: <repo>-replay.html)")
    p.add_argument("--open", action="store_true", help="open the result in your default browser")
    p.add_argument("--title", help="title shown in the browser tab")
    p.add_argument("--rev", help="branch, tag or revision to replay (default: HEAD)")
    p.add_argument("--since", help="only commits after this date, e.g. 2024-01-01")
    p.add_argument("--until", help="only commits before this date")
    p.add_argument("--max-commits", type=int, default=3000, metavar="N",
                   help="merge neighbouring commits so the replay has at most N steps (default: 3000, 0 = no limit)")
    p.add_argument("--depth", type=int, default=0, metavar="N",
                   help="fold folders deeper than N levels into their parent (default: 0 = keep all)")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                   help="skip files matching this pattern (repeatable)")
    p.add_argument("--no-default-excludes", action="store_true",
                   help="also include lockfiles, minified files, vendor/ and node_modules/")
    p.add_argument("--no-lines", action="store_true",
                   help="skip line counts (much faster on huge repos; used automatically for URLs)")
    p.add_argument("--lines", action="store_true", help="force line counts when replaying a URL")
    p.add_argument("--anonymize", action="store_true", help="replace author names with Contributor 1, 2, ...")
    p.add_argument("--no-watermark", action="store_true", help="hide the small 'repo-replay' mark in recordings")
    p.add_argument("-q", "--quiet", action="store_true", help="print nothing except errors")
    p.add_argument("-V", "--version", action="version", version=f"repo-replay {__version__}")
    return p


def resolve_source(source: str) -> Tuple[str, bool]:
    """Return ``(location, is_remote)``. Raises ValueError for unusable input."""
    if os.path.isdir(source):
        return source, False
    if URL_RE.match(source):
        return source, True
    if SHORTHAND_RE.match(source):
        return f"https://github.com/{source}.git", True
    raise ValueError(f"'{source}' is not a folder, a git URL, or a GitHub owner/name")


def clone_bare(url: str, dest: str, quiet: bool) -> None:
    """Clone history only (no checkout). Tries a blob-less clone first for speed."""
    base = ["git", "clone", "--bare", "--quiet"]
    attempts = [base + ["--filter=blob:none", url, dest], base + [url, dest]]
    last_error = ""
    for cmd in attempts:
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return
        except FileNotFoundError:
            raise GitError("git is not installed or not on your PATH")
        except subprocess.CalledProcessError as exc:
            last_error = (exc.stderr or "").strip()
    raise GitError(last_error or f"could not clone {url}")


def name_from_url(url: str) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return tail[:-4] if tail.endswith(".git") else tail or "repository"


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    def say(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    try:
        location, remote = resolve_source(args.source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tmp: Optional[str] = None
    try:
        if remote:
            say(f"Cloning {location} (history only)...")
            tmp = tempfile.mkdtemp(prefix="repo-replay-")
            repo_path = os.path.join(tmp, "clone.git")
            clone_bare(location, repo_path, args.quiet)
            name = name_from_url(location)
            with_lines = args.lines and not args.no_lines
        else:
            repo_path = location
            if not is_git_repo(repo_path):
                print(f"error: '{os.path.abspath(repo_path)}' is not a git repository", file=sys.stderr)
                return 2
            name = repo_name(repo_path)
            with_lines = not args.no_lines

        say("Reading history...")
        commits = read_history(repo_path, args.rev, args.since, args.until, with_lines)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    if not commits:
        print("error: no commits found in that range, so there is nothing to replay", file=sys.stderr)
        return 1

    total = len(commits)
    excludes = list(args.exclude) + ([] if args.no_default_excludes else list(DEFAULT_EXCLUDES))
    commits = filter_commits(commits, excludes)
    if not commits:
        print("error: every changed file was excluded; try --no-default-excludes", file=sys.stderr)
        return 1
    steps = batch_commits(commits, args.max_commits)

    payload = build_payload(steps, name, total, with_lines, args.anonymize, max(args.depth, 0))
    page = render_html(payload, args.title or "", watermark=not args.no_watermark)

    out_path = args.output or f"{name}-replay.html"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    authors = len(payload["authors"])
    say(f"Done: {total:,} commits, {authors:,} contributors, {len(payload['files']):,} files "
        f"-> {out_path} ({os.path.getsize(out_path) / 1024:.0f} KB)")
    if len(steps) < len(commits):
        say(f"      (merged into {len(steps):,} steps; raise --max-commits for finer detail)")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
