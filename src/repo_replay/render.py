"""Build the self-contained HTML file."""
from __future__ import annotations

import html
import json
import re
from importlib import resources

from . import PROJECT_URL, __version__


def _asset(name: str) -> str:
    return resources.files("repo_replay").joinpath("assets", name).read_text(encoding="utf-8")


def render_html(payload: dict, title: str = "", watermark: bool = True) -> str:
    """Return one HTML document with data, styles and script inlined."""
    config = {"watermark": watermark, "projectUrl": PROJECT_URL, "version": __version__}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    cfg = json.dumps(config, separators=(",", ":"))
    # Keep the JSON from ever closing the surrounding <script> tag.
    data = data.replace("</", "<\\/").replace("<!--", "<\\u0021--").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    page_title = title or f"{payload['repo']} - history replay"
    values = {
        "/*__CSS__*/": _asset("player.css"),
        "/*__JS__*/": _asset("player.js"),
        "__TITLE__": html.escape(page_title),
        "__CONFIG__": cfg,
        "__DATA__": data,
    }
    # One pass, so substituted content is never scanned for placeholders again.
    pattern = re.compile("|".join(re.escape(k) for k in values))
    out = pattern.sub(lambda m: values[m.group(0)], _asset("template.html"))
    return out
