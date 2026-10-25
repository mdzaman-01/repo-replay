#!/usr/bin/env python3
"""Create a realistic-looking git repository with a made-up history.

Used to generate the demo page and README media without exposing anyone's real
code. The result is deterministic for a given --seed.

    python scripts/make_demo_repo.py /tmp/demo-repo --commits 420
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import shutil
import subprocess
import sys

AUTHORS = [  # (name, email, joins at fraction of history, weight)
    ("Maya Chen", "maya@example.com", 0.00, 5),
    ("Tomas Rivera", "tomas@example.com", 0.00, 4),
    ("Priya Natarajan", "priya@example.com", 0.10, 3),
    ("Jonas Weber", "jonas@example.com", 0.30, 3),
    ("Aiko Tanaka", "aiko@example.com", 0.50, 2),
    ("Sam Okafor", "sam@example.com", 0.70, 2),
]

# fraction of history at which each folder starts receiving files, and its file type
FOLDERS = [
    (0.00, "src/core", "py"), (0.00, "tests", "py"), (0.00, "docs", "md"),
    (0.12, "src/api", "py"),
    (0.28, "web/components", "tsx"), (0.28, "web/styles", "css"),
    (0.42, "src/plugins/auth", "py"), (0.46, "src/plugins/billing", "py"),
    (0.50, "src/plugins/search", "py"), (0.54, "src/plugins/export", "py"),
    (0.60, "assets/img", "png"), (0.60, "scripts", "sh"),
    (0.72, "src/ml", "py"), (0.72, "web/pages", "tsx"),
    (0.85, "config", "yml"),
]

WORDS = ["router", "session", "cache", "parser", "schema", "token", "queue", "worker", "index",
         "events", "batch", "logger", "client", "storage", "metrics", "format", "stream",
         "limits", "retry", "config", "render", "layout", "theme", "forms", "table", "chart",
         "export", "import", "filters", "tags", "users", "teams", "invoice", "search", "rank"]
VERBS = ["Add", "Fix", "Refactor", "Speed up", "Simplify", "Document", "Handle errors in",
         "Clean up", "Extend", "Test", "Rename", "Tighten"]


def git(cwd: str, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, **(env or {})})


def body(rng: random.Random, ext: str, name: str, lines: int) -> bytes:
    if ext == "png":
        return bytes(rng.randrange(256) for _ in range(rng.randint(80, 400)))
    out = []
    for i in range(lines):
        n = rng.randint(1, 999)
        if ext == "py":
            out.append(f"def {name}_{n}(value):\n    return value * {n}\n")
        elif ext == "tsx":
            out.append(f"export const {name.title()}{n} = () => <div className=\"{name}-{n}\" />;")
        elif ext == "css":
            out.append(f".{name}-{n} {{ margin: {n % 24}px; padding: {n % 16}px; }}")
        elif ext == "md":
            out.append(f"Notes on {name}, point {n}: keep it simple and test it.")
        elif ext == "sh":
            out.append(f"echo \"step {n}: {name}\"")
        else:
            out.append(f"{name}_{n}: {n}")
    return ("\n".join(out) + "\n").encode()


def build(dest: str, commits: int, seed: int) -> None:
    rng = random.Random(seed)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "config", "commit.gpgsign", "false")

    start = dt.datetime(2023, 1, 9, 10, 0, tzinfo=dt.timezone.utc)
    span_days = 760
    live: list[str] = []  # tracked files
    ext_of: dict[str, str] = {}

    def write(path: str, data: bytes, append: bool = False) -> None:
        full = os.path.join(dest, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "ab" if append else "wb") as fh:
            fh.write(data)

    def create(frac: float) -> str:
        pool = [f for f in FOLDERS if f[0] <= frac]
        _, folder, ext = rng.choice(pool[-8:] if rng.random() < 0.6 else pool)
        name = rng.choice(WORDS)
        path = f"{folder}/{name}_{rng.randint(1, 99)}.{ext}"
        if path in live:
            return create(frac)
        write(path, body(rng, ext, name, rng.randint(6, 60)))
        live.append(path); ext_of[path] = ext
        return path

    def modify() -> str:
        path = rng.choice(live)
        ext = ext_of[path]
        if ext == "png":
            write(path, body(rng, ext, "x", 0))
        else:
            full = os.path.join(dest, path)
            with open(full, "rb") as fh:
                kept = [ln for ln in fh.read().splitlines(True) if rng.random() > 0.15]
            with open(full, "wb") as fh:
                fh.write(b"".join(kept))
            write(path, body(rng, ext, "edit", rng.randint(1, 18)), append=True)
        return path

    for i in range(commits):
        frac = i / max(commits - 1, 1)
        joined = [a for a in AUTHORS if a[2] <= frac]
        name, email, _, _ = rng.choices(joined, weights=[a[3] for a in joined])[0]
        when = start + dt.timedelta(days=span_days * frac + rng.random() * 1.2, hours=rng.randint(0, 9))
        touched: list[str] = []
        roll = rng.random()
        if i == 0 or not live:
            write("README.md", b"# Demo project\n\nA made-up history for repo-replay.\n")
            live.append("README.md"); ext_of["README.md"] = "md"
            for _ in range(3):
                touched.append(create(frac))
            touched.append("README.md")
            msg = "Initial commit"
        else:
            if roll < 0.40:
                touched = [modify() for _ in range(rng.randint(1, 3))]
            elif roll < 0.68:
                touched = [create(frac) for _ in range(rng.randint(1, 3))]
            elif roll < 0.78:
                touched = [create(frac) for _ in range(rng.randint(1, 3))] + [modify() for _ in range(2)]
            elif roll < 0.86:
                n = rng.randint(8, 20)
                touched = [modify() if rng.random() < 0.6 else create(frac) for _ in range(n)]
            elif roll < 0.90 and len(live) > 12:
                for _ in range(rng.randint(1, 2)):
                    victim = live.pop(rng.randrange(len(live)))
                    os.remove(os.path.join(dest, victim))
                    touched.append(victim)
            else:
                touched = [modify()]
            msg = f"{rng.choice(VERBS)} {rng.choice(WORDS)} {rng.choice(['handling', 'logic', 'tests', 'flow', 'docs'])}"
        git(dest, "add", "-A")
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
        env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": stamp,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": stamp}
        try:
            git(dest, "commit", "-q", "-m", msg, env=env)
        except subprocess.CalledProcessError:
            continue  # nothing changed (rare); skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dest", nargs="?", default="/tmp/demo-repo")
    ap.add_argument("--commits", type=int, default=420)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    build(args.dest, args.commits, args.seed)
    print(f"Created {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
