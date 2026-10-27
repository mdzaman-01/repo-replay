<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/mdzaman-01/repo-replay/main/docs/logo-dark.png">
    <img src="https://raw.githubusercontent.com/mdzaman-01/repo-replay/main/docs/logo.png" alt="repo replay" width="260">
  </picture>
</p>

# repo-replay

Watch your repository grow. One command turns any git history into an interactive animation: folders branch out, files appear and glow when they change, and contributors fly in to edit them.

![repo-replay animation of a project growing over two years](https://raw.githubusercontent.com/mdzaman-01/repo-replay/main/docs/demo.gif)

**[Try the live demo](https://mdzaman-01.github.io/repo-replay/demo.html)**

- **One file out.** The result is a single HTML page. Email it, host it anywhere, or open it offline.
- **Zero dependencies.** Python 3.9+ and git. Nothing to install beyond the tool itself.
- **Private by design.** Your history is read locally and never leaves your machine. The page makes no network requests.
- **Record a video.** Press `R` in the page to save the replay as a WebM file for social posts.
- **Handles big repos.** Long histories are merged into steps you can tune, and the player stays smooth with thousands of files.

## Quick start

```bash
pip install git+https://github.com/mdzaman-01/repo-replay

cd your-project
repo-replay --open               # writes your-project-replay.html and opens it
```

Replay any public GitHub repository without cloning it yourself:

```bash
repo-replay torvalds/linux --since 2024-01-01 --open
```

## Controls

| Key | Action |
| --- | --- |
| `Space` | Play or pause |
| `Left` / `Right` | Step one commit |
| `+` / `-` | Change speed |
| `L` | Toggle folder labels |
| `C` | Camera follows the action |
| `S` | Show statistics |
| `R` | Record a video |
| `F` | Fullscreen |

Drag to pan, scroll or pinch to zoom, and hover a dot to see its file path. Drag the timeline to jump anywhere.

## Options

```
repo-replay [source] [options]

  -o, --output FILE        output file (default: <repo>-replay.html)
  --open                   open the result in your browser
  --since DATE             only commits after this date
  --until DATE             only commits before this date
  --rev REV                branch, tag or revision to replay
  --max-commits N          merge neighbouring commits into at most N steps (default 3000)
  --depth N                fold folders deeper than N levels into their parent
  --exclude GLOB           skip files matching a pattern (repeatable)
  --no-default-excludes    include lockfiles, minified files, vendor/ and node_modules/
  --anonymize              show Contributor 1, 2, ... instead of names
  --no-lines               skip line counts (faster on huge repos)
  --no-watermark           hide the small "made with repo-replay" mark in recordings
```

## How it works

1. `git log --raw --numstat` is read once and parsed into commits, files and line counts.
2. Long histories are batched, with each file's operations collapsed correctly (a file created and deleted inside one batch never appears).
3. The data is embedded in one HTML file together with a small canvas player.
4. In the browser, folders are laid out as a radial tree, and each file is placed in its folder by the order it first appeared.

## Develop

```bash
pip install -e .
python -m unittest discover -s tests -t .
python scripts/make_demo_repo.py /tmp/demo-project
python -m repo_replay /tmp/demo-project --open
```

See [CONTRIBUTING.md](https://github.com/mdzaman-01/repo-replay/blob/main/CONTRIBUTING.md). Ideas that would make good first issues: a light theme, GIF export, more language colors, a `--follow-author` mode.

## License

MIT
