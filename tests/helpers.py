"""Shared helpers: build a tiny git repository with a known history."""
import os
import subprocess
import tempfile

BASE_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(cwd, *args, env=None):
    full_env = {**os.environ, **BASE_ENV, **(env or {})}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=full_env)


def commit(repo, author, stamp, message):
    git(repo, "add", "-A")
    env = {
        "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author.split()[0].lower()}@example.com",
        "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": f"{author.split()[0].lower()}@example.com", "GIT_COMMITTER_DATE": stamp,
    }
    git(repo, "commit", "-q", "-m", message, env=env)


def write(repo, path, data):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(full, mode) as fh:
        fh.write(data)


def make_repo(parent=None):
    """Create a repo with four commits:

    1. Ada adds src/app.py (3 lines), README.md (1 line), logo.png (binary)
    2. Grace adds src/util.py (2 lines) and edits src/app.py (+2 lines)
    3. Ada deletes README.md and adds package-lock.json
    4. Grace's message contains a script tag and a unicode name
    """
    repo = tempfile.mkdtemp(prefix="replay-test-", dir=parent)
    git(repo, "init", "-q", "-b", "main")
    write(repo, "src/app.py", "a\nb\nc\n")
    write(repo, "README.md", "hello\n")
    write(repo, "logo.png", bytes(range(200)))
    commit(repo, "Ada Lovelace", "2024-01-01T10:00:00+0000", "Initial commit")
    write(repo, "src/util.py", "x\ny\n")
    write(repo, "src/app.py", "a\nb\nc\nd\ne\n")
    commit(repo, "Grace Hopper", "2024-01-02T10:00:00+0000", "Add util, grow app")
    os.remove(os.path.join(repo, "README.md"))
    write(repo, "package-lock.json", "{}\n")
    commit(repo, "Ada Lovelace", "2024-01-03T10:00:00+0000", "Drop readme")
    write(repo, "src/util.py", "x\ny\nz\n")
    commit(repo, "Grace H\u00f6pper", "2024-01-04T10:00:00+0000", "Fix </script><b>bold</b> edge case")
    return repo
