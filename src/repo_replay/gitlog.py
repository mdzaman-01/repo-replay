"""Read a repository's history from ``git log`` into plain Python objects.

Only the standard library and the ``git`` executable are used. Nothing is
sent anywhere: the history is read from the local repository.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

COMMIT_MARK = "\x01"
FIELD_SEP = "\x02"
LOG_FORMAT = "%x01%H%x02%an%x02%at%x02%P%x02%s"


class GitError(RuntimeError):
    """Raised when git cannot read the repository."""


@dataclass
class FileChange:
    path: str
    op: str  # "A" added, "M" modified, "D" deleted
    added: int = 0
    deleted: int = 0


@dataclass
class Commit:
    sha: str
    author: str
    ts: int
    message: str
    parents: int = 1
    changes: List[FileChange] = field(default_factory=list)
    weight: int = 1  # how many original commits this step stands for


def parse_log(lines: Iterable[str]) -> Iterator[Commit]:
    """Parse the output of ``git log --raw --numstat`` (or ``--name-status``).

    Accepts any iterable of lines. Commits are yielded in the order given.
    """
    cur: Optional[Commit] = None
    by_path: dict = {}
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line.startswith(COMMIT_MARK):
            if cur is not None:
                yield cur
            sha, author, ts, parents, subject = (line[1:].split(FIELD_SEP, 4) + [""] * 5)[:5]
            try:
                stamp = int(ts)
            except ValueError:
                stamp = 0
            cur = Commit(sha, author, stamp, subject, len(parents.split()))
            by_path = {}
            continue
        if cur is None or not line:
            continue

        if line.startswith(":"):  # --raw: ":100644 100644 abc def M\tpath"
            meta, _, path = line.partition("\t")
            status = meta.split()[-1][:1] if meta.split() else "M"
            _add_change(cur, by_path, path, "A" if status == "A" else "D" if status == "D" else "M")
            continue

        parts = line.split("\t", 2)
        if len(parts) == 2 and parts[0] in ("A", "M", "D", "T"):  # --name-status
            op = parts[0] if parts[0] in ("A", "D") else "M"
            _add_change(cur, by_path, parts[1], op)
        elif len(parts) == 3 and (parts[0].isdigit() or parts[0] == "-"):  # --numstat
            added = int(parts[0]) if parts[0].isdigit() else 0
            deleted = int(parts[1]) if parts[1].isdigit() else 0
            change = by_path.get(parts[2])
            if change is None:
                change = _add_change(cur, by_path, parts[2], "M")
            change.added, change.deleted = added, deleted
    if cur is not None:
        yield cur


def _add_change(commit: Commit, by_path: dict, path: str, op: str) -> FileChange:
    change = FileChange(path, op)
    commit.changes.append(change)
    by_path[path] = change
    return change


def run_git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on your PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError((exc.stderr or "").strip() or "git command failed") from exc
    return out.stdout


def is_git_repo(path: str) -> bool:
    try:
        run_git(path, "rev-parse", "--git-dir")
        return True
    except GitError:
        return False


def repo_name(path: str) -> str:
    try:
        top = run_git(path, "rev-parse", "--show-toplevel").strip()
    except GitError:
        top = os.path.abspath(path)
    name = os.path.basename(top.rstrip("/\\"))
    # Bare clones end in ".git"
    return name[:-4] if name.endswith(".git") else name or "repository"


def read_history(
    repo: str,
    rev: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    with_lines: bool = True,
) -> List[Commit]:
    """Return every commit oldest-first, with the files each one touched."""
    cmd = [
        "git", "-C", repo, "-c", "core.quotepath=off", "log",
        "--reverse", "--no-renames", "--date=unix", f"--format={LOG_FORMAT}",
    ]
    cmd += ["--raw", "--numstat"] if with_lines else ["--name-status"]
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    cmd.append(rev or "HEAD")
    cmd.append("--")

    # stderr goes to a temp file so a chatty git can never fill a pipe and deadlock us.
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as err:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err,
                                    text=True, encoding="utf-8", errors="replace")
        except FileNotFoundError as exc:
            raise GitError("git is not installed or not on your PATH") from exc
        with proc:
            assert proc.stdout is not None
            commits = list(parse_log(proc.stdout))
        err.seek(0)
        message = err.read().strip()
    if proc.returncode != 0:
        if "does not have any commits" in message or "unknown revision" in message:
            return []
        raise GitError(message or "git log failed")
    return commits
