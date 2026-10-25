(() => {
"use strict";

/* ------------------------------------------------------------------ data */
const D = JSON.parse(document.getElementById("replay-data").textContent);
const CFG = JSON.parse(document.getElementById("replay-config").textContent);
const N = D.commits.length;
const $ = (id) => document.getElementById(id);
const canvas = $("stage");
const ctx = canvas.getContext("2d");
const FONT = getComputedStyle(document.body).fontFamily;
const TAU = Math.PI * 2;
const GOLDEN = 2.399963229728653;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

const fmtDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const fmtInt = new Intl.NumberFormat("en-US");
const fmtCompact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

/* ------------------------------------------------------------- languages */
const LANGS = [
  ["JavaScript", "#E9B949", ["js", "mjs", "cjs", "jsx"]],
  ["TypeScript", "#4C9BE0", ["ts", "tsx", "mts", "cts"]],
  ["Python", "#58B894", ["py", "pyi", "ipynb"]],
  ["Go", "#5FCFE0", ["go"]],
  ["Rust", "#E2774B", ["rs"]],
  ["Java and Kotlin", "#D9697A", ["java", "kt", "kts", "scala", "groovy"]],
  ["C and C++", "#9C8BE3", ["c", "h", "cc", "cpp", "hpp", "cxx", "hh", "m", "mm"]],
  ["C# and .NET", "#7DB25E", ["cs", "fs", "vb", "csproj"]],
  ["Ruby and PHP", "#DE6B8F", ["rb", "php", "erb", "rake"]],
  ["Swift and Dart", "#F0925A", ["swift", "dart"]],
  ["Shell", "#B3C27E", ["sh", "bash", "zsh", "fish", "ps1", "bat", "cmd"]],
  ["HTML and templates", "#EE8A52", ["html", "htm", "vue", "svelte", "hbs", "ejs", "jinja", "j2", "twig"]],
  ["CSS", "#B57FD6", ["css", "scss", "sass", "less", "styl"]],
  ["Docs", "#8FA5BA", ["md", "mdx", "rst", "txt", "adoc"]],
  ["Config and data", "#CDB88A", ["json", "yml", "yaml", "toml", "ini", "cfg", "xml", "csv", "lock", "env", "conf"]],
  ["Images and media", "#D78CBE", ["png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "mp4", "mp3", "woff", "woff2", "ttf", "pdf"]],
  ["Other", "#6F7F8F", []],
];
const OTHER = LANGS.length - 1;
const LANG_BY_EXT = Object.create(null);
LANGS.forEach((l, i) => l[2].forEach((e) => { LANG_BY_EXT[e] = i; }));
const extOf = (name) => {
  const base = name.slice(name.lastIndexOf("/") + 1).toLowerCase();
  if (base === "dockerfile" || base === "makefile") return "sh";
  const dot = base.lastIndexOf(".");
  return dot > 0 ? base.slice(dot + 1) : "";
};

/* ------------------------------------------------------------------ tree */
const FILE_STEP = 4.4;
const dirs = [];
const newDir = (name, parent) => ({
  name, parent, depth: parent ? parent.depth + 1 : 0, kids: new Map(), kidList: [], files: [],
  total: 0, alive: 0, own: 0, r: 8, x: 0, y: 0, hx: 0, hy: 0, angle: 0,
});
const root = newDir("", null);
const maxDepth = D.maxDepth || 99;

const files = D.files.map((p, i) => {
  const segs = p.split("/");
  const nd = Math.min(segs.length - 1, maxDepth);
  let d = root;
  for (let k = 0; k < nd; k++) {
    let c = d.kids.get(segs[k]);
    if (!c) { c = newDir(segs[k], d); d.kids.set(segs[k], c); }
    d = c;
  }
  const name = segs.slice(nd).join("/");
  const lang = LANG_BY_EXT[extOf(name)] ?? OTHER;
  const f = { i, path: p, name, dir: d, lang, alive: false, heat: 0, pop: 1, born: Infinity, x: 0, y: 0 };
  d.files.push(f);
  return f;
});

D.commits.forEach((c, ci) => {
  for (const ch of c[3]) { const f = files[ch[0]]; if (ci < f.born) f.born = ci; }
});

(function walk(d) {
  dirs.push(d);
  d.files.sort((a, b) => a.born - b.born || a.i - b.i);
  d.total = d.files.length;
  d.r = 8 + FILE_STEP * Math.sqrt(d.files.length);
  d.kidList = [...d.kids.values()].sort((a, b) => (a.name < b.name ? -1 : 1));
  for (const c of d.kidList) { walk(c); d.total += c.total; }
})(root);

function layoutTree() {
  const deepest = dirs.reduce((m, d) => Math.max(m, d.depth), 0);
  const ringMax = new Array(deepest + 1).fill(0);
  let maxRad = 0;
  for (const d of dirs) { ringMax[d.depth] = Math.max(ringMax[d.depth], d.r); maxRad = Math.max(maxRad, d.r); }
  const radii = [0];
  for (let k = 1; k <= deepest; k++) radii[k] = radii[k - 1] + ringMax[k - 1] + ringMax[k] + 46;

  const place = (d, a0, a1) => {
    d.angle = (a0 + a1) / 2;
    const R = radii[d.depth];
    d.hx = d.x = Math.cos(d.angle) * R;
    d.hy = d.y = Math.sin(d.angle) * R;
    const kids = d.kidList;
    if (!kids.length) return;
    const w = kids.map((k) => Math.sqrt(k.total) + 0.8);
    const sum = w.reduce((a, b) => a + b, 0);
    let a = a0;
    kids.forEach((k, i) => { const span = ((a1 - a0) * w[i]) / sum; place(k, a, a + span); a += span; });
  };
  place(root, 0, TAU);

  // Nudge overlapping folders apart; a spring keeps each near its sector.
  const n = dirs.length;
  if (n > 1) {
    const iters = n > 1500 ? 25 : n > 600 ? 50 : 90;
    const pad = 14;
    const cell = 2 * maxRad + pad;
    dirs.forEach((d, i) => { d.id = i; });
    for (let it = 0; it < iters; it++) {
      const grid = new Map();
      for (const d of dirs) {
        const key = Math.floor(d.x / cell) * 100003 + Math.floor(d.y / cell);
        (grid.get(key) || grid.set(key, []).get(key)).push(d);
      }
      for (const d of dirs) {
        const cx = Math.floor(d.x / cell), cy = Math.floor(d.y / cell);
        for (let ox = -1; ox <= 1; ox++) for (let oy = -1; oy <= 1; oy++) {
          const bucket = grid.get((cx + ox) * 100003 + (cy + oy));
          if (!bucket) continue;
          for (const e of bucket) {
            if (e.id <= d.id) continue;
            let dx = e.x - d.x, dy = e.y - d.y;
            let dist = Math.hypot(dx, dy);
            const min = d.r + e.r + pad;
            if (dist >= min) continue;
            if (dist < 1e-6) { dx = Math.cos(d.id); dy = Math.sin(d.id); dist = 1; }
            const push = ((min - dist) / 2) * 0.5;
            const ux = dx / dist, uy = dy / dist;
            d.x -= ux * push; d.y -= uy * push; e.x += ux * push; e.y += uy * push;
          }
        }
      }
      for (const d of dirs) { d.x += (d.hx - d.x) * 0.02; d.y += (d.hy - d.y) * 0.02; }
    }
  }

  for (const d of dirs) {
    d.files.forEach((f, k) => {
      const rr = FILE_STEP * Math.sqrt(k + 0.6);
      const ang = k * GOLDEN + d.angle;
      f.x = d.x + Math.cos(ang) * rr;
      f.y = d.y + Math.sin(ang) * rr;
    });
  }
}
layoutTree();

/* --------------------------------------------------------------- authors */
const initials = (name) => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
};
const authors = D.authors.map((name, i) => ({
  i, name, tag: initials(name), color: `hsl(${Math.round((i * 137.508) % 360)} 68% 68%)`,
  x: 0, y: 0, tx: 0, ty: 0, a: 0, seen: false, last: -1e9, commits: 0,
}));

/* ------------------------------------------------------------ growth data */
const growth = new Float32Array(N + 1);
(function () {
  const alive = new Uint8Array(files.length);
  let count = 0, lines = 0;
  for (let i = 0; i < N; i++) {
    for (const ch of D.commits[i][3]) {
      if (ch[1] === 2) { if (alive[ch[0]]) { alive[ch[0]] = 0; count--; } }
      else if (!alive[ch[0]]) { alive[ch[0]] = 1; count++; }
      lines += ch[2] - ch[3];
    }
    growth[i + 1] = D.hasLines ? Math.max(lines, 0) : count;
  }
})();
const growthMax = growth.reduce((m, v) => Math.max(m, v), 1);

const yearTicks = (function () {
  const out = [];
  let last = -1;
  D.commits.forEach((c, i) => {
    const y = new Date(c[0] * 1000).getUTCFullYear();
    if (y !== last) { out.push({ i, label: String(y) }); last = y; }
  });
  const keep = Math.ceil(out.length / 9);
  return out.filter((_, k) => k % keep === 0);
})();

/* ----------------------------------------------------------------- state */
let idx = 0, acc = 0, playing = false, speedMul = 1;
let showLabels = true, panelOpen = false, recording = null;
let pendingSeek = null, clock = 0, endedAt = 0, lastSpark = -1, lastPanel = -1e9;
let dirty = true;
let commitsDone = 0, aliveCount = 0, linesAdded = 0, linesDeleted = 0;
let current = null;
const langCount = new Array(LANGS.length).fill(0);
const hot = new Set();
const beams = [];
const fx = [];
const rate = clamp(N / 45, 1.5, 60); // whole replay takes about 45 s at 1x

function setAlive(f, v) {
  if (f.alive === v) return;
  f.alive = v;
  const step = v ? 1 : -1;
  aliveCount += step;
  langCount[f.lang] += step;
  for (let d = f.dir; d; d = d.parent) d.alive += step;
  f.dir.own += step;
}

function resetState() {
  for (const f of files) { f.alive = false; f.heat = 0; f.pop = 1; }
  for (const d of dirs) { d.alive = 0; d.own = 0; }
  aliveCount = 0; commitsDone = 0; linesAdded = 0; linesDeleted = 0;
  langCount.fill(0); hot.clear(); beams.length = 0; fx.length = 0; current = null;
  for (const a of authors) { a.commits = 0; a.seen = false; a.a = 0; a.last = -1e9; }
}

function applyCommit(i, silent) {
  dirty = true;
  const c = D.commits[i];
  const au = authors[c[1]];
  const weight = c[4] || 1;
  au.commits += weight;
  commitsDone += weight;
  let sx = 0, sy = 0, n = 0;
  for (const ch of c[3]) {
    const f = files[ch[0]];
    if (ch[1] === 2) {
      if (f.alive) {
        setAlive(f, false);
        if (!silent && fx.length < 300) fx.push({ x: f.x, y: f.y, t: 0, color: LANGS[f.lang][1] });
      }
    } else if (!f.alive) {
      setAlive(f, true);
      if (!silent) { f.pop = 0; f.heat = 1; hot.add(f); }
    } else if (!silent) {
      f.heat = 1; hot.add(f);
    }
    linesAdded += ch[2]; linesDeleted += ch[3];
    if (!silent) { sx += f.x; sy += f.y; n++; }
  }
  current = { msg: c[2], au, ts: c[0] };
  if (silent || !n) return;
  au.tx = sx / n; au.ty = sy / n; au.last = clock;
  if (!au.seen) { au.x = au.tx; au.y = au.ty; au.seen = true; }
  const stride = Math.max(1, Math.ceil(c[3].length / 10));
  for (let k = 0; k < c[3].length; k += stride) {
    beams.push({ au, f: files[c[3][k][0]], t: 1 });
  }
  if (beams.length > 160) beams.splice(0, beams.length - 160);
}

function seek(target) {
  dirty = true;
  target = clamp(Math.round(target), 0, N);
  if (target < idx) { resetState(); idx = 0; }
  while (idx < target) applyCommit(idx++, true);
  acc = 0;
  if (idx === 0) current = null;
  fitCamera(true);
}

/* ---------------------------------------------------------------- camera */
const cam = { x: 0, y: 0, z: 0.6, tx: 0, ty: 0, tz: 0.6, auto: true };
let W = 0, H = 0, dpr = 1, dprCap = 2;
const region = () => {
  const clean = !!recording || document.body.classList.contains("recording"); // controls hidden: use the room
  const right = panelOpen && W > 760 && !clean ? 278 : 24;
  return { l: 24, r: W - right, t: 84, b: Math.max(H - (clean ? 128 : 176), 160) };
};
const toScreen = (x, y) => {
  const r = region();
  return [(x - cam.x) * cam.z + (r.l + r.r) / 2, (y - cam.y) * cam.z + (r.t + r.b) / 2];
};
const toWorld = (sx, sy) => {
  const r = region();
  return [(sx - (r.l + r.r) / 2) / cam.z + cam.x, (sy - (r.t + r.b) / 2) / cam.z + cam.y];
};

function fitCamera(snap) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const d of dirs) {
    if (d.alive <= 0) continue;
    const r = d.own > 0 ? FILE_STEP * Math.sqrt(d.own + 1) + 8 : 6;
    x0 = Math.min(x0, d.x - r); x1 = Math.max(x1, d.x + r);
    y0 = Math.min(y0, d.y - r); y1 = Math.max(y1, d.y + r);
  }
  if (!isFinite(x0)) return;
  const r = region();
  const w = Math.max(x1 - x0, 60) + 80, h = Math.max(y1 - y0, 60) + 80;
  cam.tz = clamp(Math.min((r.r - r.l) / w, (r.b - r.t) / h), 0.03, 1.6);
  cam.tx = (x0 + x1) / 2; cam.ty = (y0 + y1) / 2;
  if (snap) { cam.x = cam.tx; cam.y = cam.ty; cam.z = cam.tz; }
}

/* ------------------------------------------------------------- rendering */
const byLang = LANGS.map(() => []);

function update(dt) {
  if (cam.auto) {
    fitCamera(false);
    const k = 1 - Math.exp(-dt * 1.8);
    cam.x += (cam.tx - cam.x) * k; cam.y += (cam.ty - cam.y) * k;
    cam.z = Math.exp(Math.log(cam.z) + (Math.log(cam.tz) - Math.log(cam.z)) * k);
  }
  for (const f of hot) {
    f.heat = Math.max(0, f.heat - dt * 0.8);
    if (f.pop < 1) f.pop = Math.min(1, f.pop + dt * 3.5);
    if (f.heat <= 0.005 && f.pop >= 1) { f.heat = 0; hot.delete(f); }
  }
  for (let i = beams.length - 1; i >= 0; i--) { beams[i].t -= dt * 1.7; if (beams[i].t <= 0) beams.splice(i, 1); }
  for (let i = fx.length - 1; i >= 0; i--) { fx[i].t += dt * 1.6; if (fx[i].t >= 1) fx.splice(i, 1); }
  const ka = 1 - Math.exp(-dt * 4);
  for (const a of authors) {
    if (!a.seen) continue;
    a.x += (a.tx - a.x) * ka; a.y += (a.ty - a.y) * ka;
    a.a += ((clock - a.last < 3.2 ? 1 : 0) - a.a) * (1 - Math.exp(-dt * 3));
  }
}

function text(str, x, y, size, color, weight, align) {
  ctx.font = `${weight || 400} ${size}px ${FONT}`;
  ctx.textAlign = align || "left";
  ctx.lineWidth = 4; ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(10,17,24,0.85)";
  ctx.strokeText(str, x, y);
  ctx.fillStyle = color;
  ctx.fillText(str, x, y);
}

function fitText(str, maxW, size, weight) {
  ctx.font = `${weight || 400} ${size}px ${FONT}`;
  if (ctx.measureText(str).width <= maxW) return str;
  let s = str;
  while (s.length > 4 && ctx.measureText(s + "\u2026").width > maxW) s = s.slice(0, -1);
  return s + "\u2026";
}

function draw() {
  // background
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  const g = ctx.createRadialGradient(W / 2, H * 0.45, 0, W / 2, H * 0.45, Math.max(W, H) * 0.75);
  g.addColorStop(0, "#14212c"); g.addColorStop(1, "#080d13");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  if (!N) return;

  // world space
  const r = region();
  const cx = (r.l + r.r) / 2, cy = (r.t + r.b) / 2;
  ctx.setTransform(dpr * cam.z, 0, 0, dpr * cam.z, dpr * (cx - cam.x * cam.z), dpr * (cy - cam.y * cam.z));
  const z = cam.z;
  const px = 1 / z;

  ctx.lineWidth = 1.2 * px;
  ctx.strokeStyle = "rgba(150,185,215,0.2)";
  ctx.beginPath();
  for (const d of dirs) {
    if (!d.parent || d.alive <= 0) continue;
    const p = d.parent;
    ctx.moveTo(p.x, p.y);
    ctx.quadraticCurveTo((p.x + d.x) / 2 + (d.y - p.y) * 0.1, (p.y + d.y) / 2 - (d.x - p.x) * 0.1, d.x, d.y);
  }
  ctx.stroke();

  ctx.strokeStyle = "rgba(150,185,215,0.5)";
  ctx.beginPath();
  for (const f of hot) {
    if (!f.alive || f.heat < 0.05) continue;
    ctx.moveTo(f.dir.x, f.dir.y); ctx.lineTo(f.x, f.y);
  }
  ctx.stroke();

  ctx.fillStyle = "rgba(190,215,235,0.55)";
  ctx.beginPath();
  for (const d of dirs) {
    if (d.alive <= 0) continue;
    const rad = Math.max(2.4, 3 * px);
    ctx.moveTo(d.x + rad, d.y); ctx.arc(d.x, d.y, rad, 0, TAU);
  }
  ctx.fill();

  for (const arr of byLang) arr.length = 0;
  for (const f of files) if (f.alive && f.heat === 0) byLang[f.lang].push(f);
  const fr = Math.max(2.1, 1.3 * px);
  ctx.globalAlpha = 0.9;
  for (let L = 0; L < LANGS.length; L++) {
    const arr = byLang[L];
    if (!arr.length) continue;
    ctx.fillStyle = LANGS[L][1];
    ctx.beginPath();
    if (fr * z < 1.1 || (aliveCount > 4000 && fr * z < 2.2)) { // tiny or crowded: squares are far cheaper and read the same
      const side = fr * 2;
      for (const f of arr) ctx.rect(f.x - fr, f.y - fr, side, side);
    } else {
      for (const f of arr) { ctx.moveTo(f.x + fr, f.y); ctx.arc(f.x, f.y, fr, 0, TAU); }
    }
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  ctx.globalCompositeOperation = "lighter";
  for (const f of hot) {
    if (!f.alive) continue;
    const col = LANGS[f.lang][1];
    const grow = f.pop < 1 ? 0.35 + 0.65 * f.pop + Math.sin(f.pop * Math.PI) * 0.5 : 1;
    ctx.globalAlpha = 0.22 * f.heat;
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(f.x, f.y, fr * (3 + 6 * f.heat), 0, TAU); ctx.fill();
    ctx.globalAlpha = 0.95;
    ctx.beginPath(); ctx.arc(f.x, f.y, fr * grow * (1 + f.heat * 0.9), 0, TAU); ctx.fill();
    ctx.globalAlpha = 0.36 * f.heat;
    ctx.fillStyle = "#fff";
    ctx.beginPath(); ctx.arc(f.x, f.y, fr * 0.8 * grow, 0, TAU); ctx.fill();
  }
  ctx.globalAlpha = 1;

  for (const e of fx) {
    ctx.globalAlpha = (1 - e.t) * 0.8;
    ctx.strokeStyle = "#ff8f8f";
    ctx.lineWidth = 1.6 * px;
    ctx.beginPath(); ctx.arc(e.x, e.y, fr * (1.5 + e.t * 7), 0, TAU); ctx.stroke();
  }

  for (const b of beams) {
    if (!b.au.seen || !b.f.alive) continue;
    ctx.globalAlpha = clamp(b.t, 0, 1) * 0.55;
    ctx.strokeStyle = b.au.color;
    ctx.lineWidth = 1.3 * px;
    ctx.beginPath(); ctx.moveTo(b.au.x, b.au.y); ctx.lineTo(b.f.x, b.f.y); ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";

  // screen space
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.textBaseline = "alphabetic";

  if (showLabels) {
    let shown = 0;
    for (const d of dirs) {
      if (!d.parent || d.alive < 2 || shown > 140) continue;
      if (d.depth > 1 && d.r * z < 14) continue;
      const [sx, sy] = toScreen(d.x, d.y);
      if (sx < -80 || sx > W + 80 || sy < -40 || sy > H + 40) continue;
      shown++;
      text(d.name, sx, sy - Math.max(8, d.r * z * 0.55) - 4, 11, "rgba(214,226,238,0.82)", 500, "center");
    }
  }

  for (const a of authors) {
    if (!a.seen || a.a < 0.03) continue;
    const [sx, sy] = toScreen(a.x, a.y);
    ctx.globalAlpha = a.a;
    ctx.fillStyle = "rgba(10,17,24,0.9)";
    ctx.beginPath(); ctx.arc(sx, sy, 12, 0, TAU); ctx.fill();
    ctx.strokeStyle = a.color; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = a.color;
    ctx.font = `600 10px ${FONT}`; ctx.textAlign = "center";
    ctx.fillText(a.tag, sx, sy + 3.5);
    if (showLabels) text(a.name, sx, sy + 26, 11, a.color, 500, "center");
  }
  ctx.globalAlpha = 1;

  drawHud();
}

function drawHud() {
  text(D.repo, 24, 38, 22, "#eef4fa", 600);
  const who = D.authors.length === 1 ? "1 contributor" : `${fmtInt.format(D.authors.length)} contributors`;
  text(`${fmtInt.format(D.totalCommits)} commits by ${who}`, 24, 59, 13, "#8a9bab", 400);
  if (CFG.watermark) text("made with repo-replay", W - 24, 38, 12, "rgba(160,180,200,0.5)", 400, "right");

  const ts = current ? current.ts : D.commits[0][0];
  const baseY = H - 76 - 52;
  text(fmtDate.format(new Date(ts * 1000)), 24, baseY, 38, "#f3ebdd", 300);
  if (current) {
    const line = `${current.au.name}: ${current.msg}`;
    const shownText = fitText(line, Math.min(W * 0.55, 620), 14, 400);
    ctx.fillStyle = current.au.color;
    ctx.beginPath(); ctx.arc(30, baseY + 22, 4, 0, TAU); ctx.fill();
    text(shownText, 42, baseY + 27, 14, "#c3d0dc", 400);
  }

  if (!panelOpen || recording) {
    const rows = [];
    for (let L = 0; L < LANGS.length; L++) if (langCount[L] > 0) rows.push(L);
    rows.sort((a, b) => langCount[b] - langCount[a]);
    const shown = rows.slice(0, 7);
    let y = H - 76 - 26 - (shown.length - 1) * 20; // largest language on top
    ctx.textAlign = "right";
    for (const L of shown) {
      const label = `${LANGS[L][0]}  ${fmtInt.format(langCount[L])}`;
      text(label, W - 24, y, 12, "#b4c3d1", 400, "right");
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = LANGS[L][1];
      ctx.beginPath(); ctx.arc(W - 24 - tw - 12, y - 4, 4.5, 0, TAU); ctx.fill();
      y += 20;
    }
  }
}

/* ------------------------------------------------------------ sparkline */
const spark = $("spark");
const sctx = spark.getContext("2d");

function drawSpark() {
  const w = spark.clientWidth, h = spark.clientHeight;
  if (!w || !h) return;
  if (spark.width !== Math.round(w * dpr) || spark.height !== Math.round(h * dpr)) {
    spark.width = Math.round(w * dpr); spark.height = Math.round(h * dpr);
  }
  sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  sctx.clearRect(0, 0, w, h);
  const top = 6, bottom = h - 14;
  const path = new Path2D();
  path.moveTo(0, bottom);
  for (let i = 0; i <= N; i++) {
    path.lineTo((i / Math.max(N, 1)) * w, bottom - (growth[i] / growthMax) * (bottom - top));
  }
  path.lineTo(w, bottom); path.closePath();
  sctx.fillStyle = "rgba(170,200,225,0.14)";
  sctx.fill(path);
  sctx.save();
  sctx.beginPath(); sctx.rect(0, 0, (idx / Math.max(N, 1)) * w, h); sctx.clip();
  sctx.fillStyle = "rgba(243,235,221,0.42)";
  sctx.fill(path);
  sctx.restore();
  sctx.font = `10px ${FONT}`; sctx.textAlign = "left"; sctx.fillStyle = "#8a9bab";
  for (const t of yearTicks) {
    const x = (t.i / Math.max(N, 1)) * w;
    sctx.fillRect(x, bottom, 1, 4);
    sctx.fillText(t.label, Math.min(x + 3, w - 26), h - 2);
  }
  lastSpark = idx;
}

/* --------------------------------------------------------------- controls */
const ICON = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>',
  prev: '<svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zM9.5 12L18 6v12z"/></svg>',
  next: '<svg viewBox="0 0 24 24"><path d="M16 6h2v12h-2zM6 18V6l8.5 6z"/></svg>',
  full: '<svg viewBox="0 0 24 24"><path d="M5 5h5v2H7v3H5zM14 5h5v5h-2V7h-3zM5 14h2v3h3v2H5zM17 14h2v5h-5v-2h3z"/></svg>',
};
$("prev").innerHTML = ICON.prev;
$("next").innerHTML = ICON.next;
$("btn-full").innerHTML = ICON.full;
$("credit-link").href = CFG.projectUrl;

const seekEl = $("seek");
seekEl.max = String(N);

function setPlaying(v) {
  playing = v;
  const b = $("play");
  b.innerHTML = v ? ICON.pause : ICON.play;
  b.setAttribute("aria-label", v ? "Pause" : "Play");
}
function togglePlay() {
  if (!playing && idx >= N) { seek(0); }
  setPlaying(!playing);
}
function step(delta) {
  setPlaying(false);
  if (delta > 0 && idx < N) applyCommit(idx++, false);
  else if (delta < 0) pendingSeek = Math.max(0, idx - 1);
}
function setSpeed(v) {
  speedMul = v;
  const sel = $("speed");
  sel.value = String(v);
}
function bumpSpeed(dir) {
  const opts = [...$("speed").options].map((o) => +o.value);
  const i = clamp(opts.indexOf(speedMul) + dir, 0, opts.length - 1);
  setSpeed(opts[i]);
}
function setToggle(id, on) {
  dirty = true; $(id).setAttribute("aria-pressed", String(on)); }
function toggleLabels() { showLabels = !showLabels; setToggle("btn-labels", showLabels); }
function toggleFollow() {
  cam.auto = !cam.auto; setToggle("btn-cam", cam.auto);
  if (cam.auto) fitCamera(false);
}
function togglePanel() {
  panelOpen = !panelOpen; setToggle("btn-panel", panelOpen);
  $("panel").hidden = !panelOpen; lastPanel = -1e9;
}
function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
}

let toastTimer = 0;
function toast(msg, ms) {
  const t = $("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), ms || 2400);
}

$("play").addEventListener("click", togglePlay);
$("prev").addEventListener("click", () => step(-1));
$("next").addEventListener("click", () => step(1));
$("speed").addEventListener("change", (e) => setSpeed(+e.target.value));
$("btn-labels").addEventListener("click", toggleLabels);
$("btn-cam").addEventListener("click", toggleFollow);
$("btn-panel").addEventListener("click", togglePanel);
$("btn-rec").addEventListener("click", toggleRecording);
$("btn-full").addEventListener("click", toggleFullscreen);
seekEl.addEventListener("input", () => { pendingSeek = +seekEl.value; });

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = e.target.tagName;
  const onControl = tag === "BUTTON" || tag === "SELECT";
  const k = e.key;
  if (k === "Escape" && recording) { stopRecording(); return; }
  if (k === " " && !onControl) { e.preventDefault(); togglePlay(); }
  else if (k === "ArrowRight" && tag !== "INPUT") step(1);
  else if (k === "ArrowLeft" && tag !== "INPUT") step(-1);
  else if (k === "+" || k === "=") bumpSpeed(1);
  else if (k === "-" || k === "_") bumpSpeed(-1);
  else if (k === "Home") pendingSeek = 0;
  else if (k === "End") pendingSeek = N;
  else if (k === "l" || k === "L") toggleLabels();
  else if (k === "c" || k === "C") toggleFollow();
  else if (k === "s" || k === "S") togglePanel();
  else if (k === "r" || k === "R") toggleRecording();
  else if (k === "f" || k === "F") toggleFullscreen();
});

/* pan, zoom, hover */
const pointers = new Map();
let pinch = 0;
const tip = $("tip");

function manualCamera() {
  dirty = true;
  if (cam.auto) { cam.auto = false; setToggle("btn-cam", false); }
}
function zoomAt(sx, sy, factor) {
  dirty = true;
  manualCamera();
  const [wx, wy] = toWorld(sx, sy);
  cam.z = cam.tz = clamp(cam.z * factor, 0.02, 8);
  const r = region();
  cam.x = cam.tx = wx - (sx - (r.l + r.r) / 2) / cam.z;
  cam.y = cam.ty = wy - (sy - (r.t + r.b) / 2) / cam.z;
}
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015)));
}, { passive: false });

canvas.addEventListener("pointerdown", (e) => {
  canvas.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  canvas.classList.add("dragging");
  tip.hidden = true;
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch = Math.hypot(a.x - b.x, a.y - b.y);
  }
});
canvas.addEventListener("pointermove", (e) => {
  const p = pointers.get(e.pointerId);
  if (!p) { hover(e.clientX, e.clientY); return; }
  const dx = e.clientX - p.x, dy = e.clientY - p.y;
  p.x = e.clientX; p.y = e.clientY;
  if (pointers.size === 1) {
    manualCamera();
    cam.x = cam.tx = cam.x - dx / cam.z;
    cam.y = cam.ty = cam.y - dy / cam.z;
  } else if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const d = Math.hypot(a.x - b.x, a.y - b.y);
    if (pinch > 0) zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, d / pinch);
    pinch = d;
  }
});
const endPointer = (e) => {
  pointers.delete(e.pointerId);
  pinch = 0;
  if (!pointers.size) canvas.classList.remove("dragging");
};
canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);
canvas.addEventListener("pointerleave", () => { tip.hidden = true; });

function hover(mx, my) {
  let best = null, bestD = 100;
  for (const f of files) {
    if (!f.alive) continue;
    const [sx, sy] = toScreen(f.x, f.y);
    const d = (sx - mx) * (sx - mx) + (sy - my) * (sy - my);
    if (d < bestD) { bestD = d; best = f; }
  }
  if (!best) { tip.hidden = true; return; }
  tip.textContent = `${best.path} (${LANGS[best.lang][0]})`;
  tip.hidden = false;
  tip.style.left = Math.min(mx + 14, W - 240) + "px";
  tip.style.top = my + 16 + "px";
}

/* -------------------------------------------------------------- recording */
function toggleRecording() { recording ? stopRecording() : startRecording(); }

function startRecording() {
  if (!canvas.captureStream || typeof MediaRecorder === "undefined") {
    toast("Recording is not supported in this browser. Try Chrome, Edge or Firefox.", 4000);
    return;
  }
  const mime = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"].find((t) => MediaRecorder.isTypeSupported(t));
  if (!mime) { toast("This browser cannot record WebM video.", 4000); return; }
  dprCap = 1; resize();
  seek(0);
  const stream = canvas.captureStream(30);
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6000000 });
  const chunks = [];
  rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  rec.onstop = () => {
    const blob = new Blob(chunks, { type: "video/webm" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${D.repo}-replay.webm`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast(`Saved ${a.download}`, 4000);
  };
  recording = { rec, mime };
  document.body.classList.add("recording");
  $("btn-rec").classList.add("recording");
  setPlaying(true);
  rec.start(250);
  toast("Recording. Press Esc to stop early.", 3500);
}

function stopRecording() {
  if (!recording) return;
  const { rec } = recording;
  recording = null;
  if (rec.state !== "inactive") rec.stop();
  document.body.classList.remove("recording");
  $("btn-rec").classList.remove("recording");
  dprCap = 2; resize();
  setPlaying(false);
}

/* -------------------------------------------------------------- side panel */
function updatePanel() {
  $("s-commits").textContent = fmtInt.format(commitsDone);
  $("s-files").textContent = fmtInt.format(aliveCount);
  const linesRow = $("s-lines").parentElement;
  linesRow.hidden = !D.hasLines;
  $("s-lines-label").textContent = "Lines";
  $("s-lines").textContent = `+${fmtCompact.format(linesAdded)} / -${fmtCompact.format(linesDeleted)}`;

  const fill = (el, rows) => {
    el.replaceChildren(...rows.map(([color, name, count]) => {
      const li = document.createElement("li");
      const dot = document.createElement("i"); dot.style.background = color;
      const nm = document.createElement("span"); nm.textContent = name; nm.title = name;
      const ct = document.createElement("b"); ct.textContent = fmtInt.format(count);
      li.append(dot, nm, ct);
      return li;
    }));
  };
  fill($("s-authors"), authors.filter((a) => a.commits > 0).sort((a, b) => b.commits - a.commits).slice(0, 8)
    .map((a) => [a.color, a.name, a.commits]));
  fill($("s-langs"), LANGS.map((l, i) => [l[1], l[0], langCount[i]]).filter((r) => r[2] > 0)
    .sort((a, b) => b[2] - a[2]).slice(0, 8));
}

/* -------------------------------------------------------------- main loop */
function resize() {
  dirty = true;
  dpr = Math.min(window.devicePixelRatio || 1, dprCap);
  W = window.innerWidth; H = window.innerHeight;
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
  lastSpark = -1;
}
window.addEventListener("resize", () => { resize(); if (cam.auto) fitCamera(true); });

let lastT = performance.now();
let manual = false; // set by #manual so tools can step time deterministically (used for README media)

function tick(dt) {
  clock += dt;
  if (pendingSeek !== null) { seek(pendingSeek); pendingSeek = null; }
  if (playing) {
    acc += dt * rate * speedMul;
    let guard = 0;
    while (acc >= 1 && idx < N && guard++ < 200) { applyCommit(idx++, false); acc -= 1; }
    if (idx >= N) {
      if (!endedAt) endedAt = clock;
      if (!recording) { setPlaying(false); endedAt = 0; }
      else if (clock - endedAt > 2.4) { endedAt = 0; stopRecording(); }
    }
  }
  update(dt);
  const moving = cam.auto && (Math.abs(cam.tx - cam.x) * cam.z > 0.25 || Math.abs(cam.ty - cam.y) * cam.z > 0.25
    || Math.abs(Math.log(cam.tz / cam.z)) > 0.002);
  const animating = playing || recording || hot.size || beams.length || fx.length || moving
    || authors.some((a) => a.seen && (a.a > 0.03 || clock - a.last < 3.4));
  if (dirty || animating) { draw(); dirty = false; }

  if (seekEl.value !== String(idx)) seekEl.value = String(idx);
  if (idx !== lastSpark) drawSpark();
  if (panelOpen && clock - lastPanel > 0.25) { updatePanel(); lastPanel = clock; }
}

function frame(t) {
  const dt = Math.min(0.05, (t - lastT) / 1000);
  lastT = t;
  if (!manual) tick(dt);
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ start */
resize();
setPlaying(false);
if (!N) {
  $("empty").hidden = false;
} else {
  const hash = new URLSearchParams(location.hash.slice(1));
  const startAt = parseFloat(hash.get("t"));
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  manual = hash.has("manual");
  if (hash.has("panel")) togglePanel();
  if (hash.get("labels") === "0") toggleLabels();
  if (isFinite(startAt)) {
    seek(clamp(startAt, 0, 1) * N);
  } else if (!reduced) {
    setTimeout(() => setPlaying(true), 500);
  }
}
window.__replay = { N, get idx() { return idx; }, files, dirs, authors, cam, seek: (n) => { pendingSeek = n; }, play: () => setPlaying(true), advance: (dt) => { dirty = true; tick(dt); } };
requestAnimationFrame(frame);
})();
