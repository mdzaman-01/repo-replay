# Contributing

Thanks for helping. The project has no runtime dependencies, so setup is short.

```bash
git clone https://github.com/mdzaman-01/repo-replay
cd repo-replay
pip install -e .
python -m unittest discover -s tests -t .
```

## Where things live

- `src/repo_replay/gitlog.py` reads `git log` into commits.
- `src/repo_replay/compact.py` filters, batches long histories and builds the JSON payload.
- `src/repo_replay/assets/player.js` is the whole browser player (layout, animation, camera, recording).
- `scripts/make_demo_repo.py` builds a made-up repository for demos and screenshots.

## Try your change

```bash
python scripts/make_demo_repo.py /tmp/demo-project
python -m repo_replay /tmp/demo-project -o /tmp/demo.html --open
```

Open the page with `#t=0.5` to jump to the middle, `#panel` to show the stats panel, and `#manual` to step time yourself with `__replay.advance(seconds)` from the console.

## Guidelines

- Keep the output a single file that makes no network requests.
- Add a test for parser or payload changes.
- Good first issues: more language colors, a dark/light theme switch, GIF export.
