"""Turn a list of commits into the compact payload the browser player reads."""
from __future__ import annotations

import fnmatch
import math
import time
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence

from .gitlog import Commit, FileChange

# Files that dominate line counts without telling you anything about a project.
DEFAULT_EXCLUDES = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock",
    "Pipfile.lock", "composer.lock", "Gemfile.lock", "go.sum", "*.min.js", "*.min.css",
    "*.map", "node_modules/*", "*/node_modules/*", "vendor/*", "*/vendor/*",
)

OP_CODES = {"A": 0, "M": 1, "D": 2}
MAX_SUBJECT = 120


def is_excluded(path: str, patterns: Sequence[str]) -> bool:
    base = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(base, p) for p in patterns)


def filter_commits(commits: Iterable[Commit], excludes: Sequence[str]) -> List[Commit]:
    """Drop excluded paths, then drop commits that no longer touch any file."""
    kept: List[Commit] = []
    for c in commits:
        changes = [ch for ch in c.changes if not is_excluded(ch.path, excludes)] if excludes else c.changes
        if changes:
            kept.append(Commit(c.sha, c.author, c.ts, c.message, c.parents, list(changes), c.weight))
    return kept


def _merge_ops(first: str, last: str) -> Optional[str]:
    """Collapse the first and last operation on a file within a batch."""
    if first == "A" and last == "D":
        return None  # created and removed inside one batch: never visible
    if first == "A":
        return "A"
    if last == "D":
        return "D"
    return "M"


def merge_commits(group: Sequence[Commit]) -> Commit:
    """Combine consecutive commits into a single synthetic commit."""
    if len(group) == 1:
        return group[0]
    state: Dict[str, List] = {}
    for c in group:
        for ch in c.changes:
            entry = state.get(ch.path)
            if entry is None:
                state[ch.path] = [ch.op, ch.op, ch.added, ch.deleted]
            else:
                entry[1] = ch.op
                entry[2] += ch.added
                entry[3] += ch.deleted
    changes = []
    for path, (first, last, added, deleted) in state.items():
        op = _merge_ops(first, last)
        if op is not None:
            changes.append(FileChange(path, op, added, deleted))
    authors = Counter(c.author for c in group)
    top_author = authors.most_common(1)[0][0]
    last = group[-1]
    total = sum(c.weight for c in group)
    message = f"{total} commits, latest: {last.message}"
    return Commit(last.sha, top_author, last.ts, message, 1, changes, total)


def batch_commits(commits: Sequence[Commit], max_commits: int) -> List[Commit]:
    """Shrink a long history to at most ``max_commits`` steps by merging neighbours."""
    if max_commits <= 0 or len(commits) <= max_commits:
        return list(commits)
    size = math.ceil(len(commits) / max_commits)
    out = []
    for start in range(0, len(commits), size):
        merged = merge_commits(commits[start:start + size])
        if merged.changes:
            out.append(merged)
    return out


def build_payload(
    commits: Sequence[Commit],
    repo: str,
    total_commits: int,
    with_lines: bool = True,
    anonymize: bool = False,
    max_depth: int = 0,
) -> dict:
    """Build the JSON-serialisable structure embedded in the HTML file."""
    author_index: Dict[str, int] = {}
    author_names: List[str] = []
    file_index: Dict[str, int] = {}
    file_paths: List[str] = []
    rows = []

    for c in commits:
        if c.author not in author_index:
            author_index[c.author] = len(author_names)
            author_names.append(f"Contributor {len(author_names) + 1}" if anonymize else c.author)
        changes = []
        for ch in c.changes:
            fi = file_index.get(ch.path)
            if fi is None:
                fi = file_index[ch.path] = len(file_paths)
                file_paths.append(ch.path)
            changes.append([fi, OP_CODES.get(ch.op, 1), ch.added, ch.deleted])
        subject = c.message if len(c.message) <= MAX_SUBJECT else c.message[: MAX_SUBJECT - 1] + "\u2026"
        row = [c.ts, author_index[c.author], subject, changes]
        if c.weight > 1:
            row.append(c.weight)
        rows.append(row)

    return {
        "v": 1,
        "repo": repo,
        "generated": int(time.time()),
        "totalCommits": total_commits,
        "hasLines": with_lines,
        "maxDepth": max_depth,
        "authors": author_names,
        "files": file_paths,
        "commits": rows,
    }
