#!/usr/bin/env python3
"""The product demo animation and README media (phase 3A G5; dark technical redesign in phase 4B).

Source of truth: design/animation/storyboard.json (scenes, timing, captions, commands, status lines),
design/animation/demo-data.json (real values from the order-service deviation run and its model-revision evidence) and
design/tokens.json (the product's dark theme). Every visual component is generic and reads only those files — nothing
is drawn that the data does not contain.
Outputs (docs/assets/):
  demo.svg          animated SVG (CSS keyframes on one shared loop; prefers-reduced-motion → static poster)
  demo-cover.svg    static poster                                     demo-cover.png  (rsvg-convert or Chromium)
  demo.html         web preview (play / pause, scrub, reduced-motion aware)
  demo.mp4          video export: every frame rendered from demo.svg in Chromium, encoded with ffmpeg
  architecture.svg  architecture and the per-step run flow, same visual language

    python3 scripts/render_demo.py svg                     # stdlib only: demo.svg, demo-cover.svg, demo.html, architecture.svg
    scripts/in-vm.sh 'uv run --frozen python scripts/render_demo.py frames'   # Chromium frames → var/demo-frames
    python3 scripts/render_demo.py encode                  # ffmpeg (host): demo.mp4 + demo-cover.png
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design"
ASSETS = ROOT / "docs" / "assets"
FRAMES = ROOT / "var" / "demo-frames"
W, H = 1280, 720
FPS = 30

TOKENS = json.loads((DESIGN / "tokens.json").read_text())
STORY = json.loads((DESIGN / "animation" / "storyboard.json").read_text())
DATA = json.loads((DESIGN / "animation" / "demo-data.json").read_text())
VERSION = json.loads((ROOT / "web" / "package.json").read_text())["version"]
D = TOKENS["color"]["dark"]
EVD = {k: v["dark"] for k, v in TOKENS["evidence"].items() if isinstance(v, dict)}
TOTAL = STORY["duration_s"]
EASE = TOKENS["motion"]["easing"]["standard"]
FONT = TOKENS["font"]["sans"].replace('"', "'")
MONO = TOKENS["font"]["mono"].replace('"', "'")

# the media palette: the product's dark theme on a deeper canvas
BG, GRID, PANEL, EDGE = "#0b0f15", "#141b26", "#10151e", "#222b38"
TXT, TXT2, MUTED, DIM = D["text"], D["text-secondary"], D["text-muted"], "#5d6779"
BRAND, OK, ERR, WARN, INFO = D["brand"], D["success"], D["danger"], D["warning"], D["info"]
PRED, OBS = EVD["predicted"], EVD["observed"]
SOFT = {BRAND: D["brand-soft"], OK: D["success-soft"], ERR: D["danger-soft"], WARN: D["warning-soft"],
        INFO: D["info-soft"], MUTED: D["neutral-soft"], PRED: "#2a2342"}
STAGE_X0, STAGE_X1 = 470, 1240  # the right-hand stage of every scene


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


class Anim:
    """CSS keyframe animations that all share the loop length, so every element stays in sync."""

    def __init__(self) -> None:
        self.rules: list[str] = []
        self.n = 0

    def pct(self, t: float) -> str:
        return f"{max(0.0, min(100.0, t / TOTAL * 100)):.3f}%"

    def _add(self, frames: list[tuple[float, str]], extra: str = "", timing: str = EASE) -> str:
        self.n += 1
        name = f"k{self.n}"
        frames = sorted(frames, key=lambda f: f[0])
        body = " ".join(f"{self.pct(t)} {{ {css} }}" for t, css in frames)
        self.rules.append(f"@keyframes {name} {{ {body} }}")
        self.rules.append(f".{name} {{ animation: {name} {TOTAL}s {timing} infinite both; {extra} }}")
        return name

    def show(self, t_in: float, t_out: float, dy: float = 8, fade: float = 0.4) -> str:
        off, on = f"opacity: 0; transform: translate(0px, {dy}px);", "opacity: 1; transform: translate(0px, 0px);"
        return self._add([(0, off), (t_in, off), (t_in + fade, on), (t_out - 0.3, on), (t_out, "opacity: 0;"),
                          (TOTAL, "opacity: 0;")])

    def draw(self, t0: float, t1: float, t_out: float, length: float) -> str:
        return self._add([(0, f"stroke-dashoffset: {length}; opacity: 1;"), (t0, f"stroke-dashoffset: {length}; opacity: 1;"),
                          (t1, "stroke-dashoffset: 0; opacity: 1;"), (t_out - 0.3, "stroke-dashoffset: 0; opacity: 1;"),
                          (t_out, "stroke-dashoffset: 0; opacity: 0;"), (TOTAL, f"stroke-dashoffset: {length}; opacity: 0;")],
                         f"stroke-dasharray: {length};")

    def grow_x(self, t0: float, t1: float, t_out: float, timing: str = EASE) -> str:
        """Scale from 0 to 1 along x (transform-origin set by the caller) between t0 and t1."""
        return self._add([(0, "transform: scaleX(0); opacity: 1;"), (t0, "transform: scaleX(0); opacity: 1;"),
                          (t1, "transform: scaleX(1); opacity: 1;"), (t_out - 0.3, "transform: scaleX(1); opacity: 1;"),
                          (t_out, "transform: scaleX(1); opacity: 0;"), (TOTAL, "transform: scaleX(0); opacity: 0;")],
                         "transform-box: fill-box; transform-origin: left center;", timing=timing)

    def fill_at(self, t: float, before: str, after: str, t_out: float) -> str:
        return self._add([(0, f"fill: {before};"), (t, f"fill: {before};"), (t + 0.2, f"fill: {after};"),
                          (t_out, f"fill: {after};"), (min(TOTAL, t_out + 0.01), f"fill: {before};"), (TOTAL, f"fill: {before};")])

    def steps_x(self, stops: list[tuple[float, float]]) -> str:
        """Jump between x offsets at the given times (eased), e.g. the active-stage marker."""
        frames = [(0, f"transform: translate({stops[0][1]}px, 0px);")]
        for i, (t, x) in enumerate(stops[1:], 1):
            frames.append((t, f"transform: translate({stops[i - 1][1]}px, 0px);"))
            frames.append((t + 0.35, f"transform: translate({x}px, 0px);"))
        frames.append((TOTAL, f"transform: translate({stops[-1][1]}px, 0px);"))
        return self._add(frames)

    def travel(self, t0: float, t1: float, dx: float, t_out: float) -> str:
        """Move linearly by dx between t0 and t1 (a pulse along a pipeline)."""
        return self._add([(0, "transform: translate(0px, 0px); opacity: 0;"), (t0 - 0.01, "transform: translate(0px, 0px); opacity: 0;"),
                          (t0, "transform: translate(0px, 0px); opacity: 1;"),
                          (t1, f"transform: translate({dx}px, 0px); opacity: 1;"), (t1 + 0.01, "opacity: 0;"),
                          (t_out, "opacity: 0;"), (TOTAL, "opacity: 0;")], timing="linear")

    def linear_x(self, dx: float) -> str:
        return self._add([(0, "transform: translate(0px, 0px);"), (TOTAL, f"transform: translate({dx}px, 0px);")],
                         timing="linear")


def show(A: Anim | None, t_in: float, t_out: float, **kw) -> str:
    return A.show(t_in, t_out, **kw) if A else ""


def g(cls: str, body: str) -> str:
    return f'<g class="{cls}">{body}</g>' if cls else f"<g>{body}</g>"


def text(x, y, s, *, size=13, weight=400, fill=TXT, anchor="start", family=FONT, extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def mono(x, y, s, *, size=11.5, weight=400, fill=TXT, anchor="start", extra=""):
    return text(x, y, s, size=size, weight=weight, fill=fill, anchor=anchor, family=MONO, extra=extra)


def rect(x, y, w, h, *, fill=PANEL, stroke=EDGE, r=8, sw=1, dash=None, extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d} {extra}/>')


def text_width(s: str, size: float, mono_font: bool = False) -> float:
    if mono_font:
        return sum(1.0 if ord(ch) > 0x2e80 else 0.6 for ch in s) * size
    w = 0.0
    for ch in s:
        if ord(ch) > 0x2e80:
            w += 1.0
        elif ch.isupper() or ch in "@%&MW":
            w += 0.68
        elif ch.isdigit():
            w += 0.58
        elif ch in " .,:;'|!il[]()·":
            w += 0.3
        else:
            w += 0.54
    return w * size


def chip(x, y, label, color, *, size=11, glyph="", filled=True, dash=None) -> tuple[str, float]:
    """A mono status chip (soft background, coloured text)."""
    full = f"{glyph} {label}" if glyph else label
    w = text_width(full, size, mono_font=True) + 18
    body = rect(x, y, w, size + 11, fill=SOFT.get(color, PANEL) if filled else "none", stroke=color if not filled else
                SOFT.get(color, EDGE), r=(size + 11) / 2, dash=dash)
    body += mono(x + 9, y + size + 4.5, full, size=size, weight=600, fill=color)
    return body, w


def arrow(x1, y1, x2, y2, color=DIM, sw=1.3):
    head = f'<path d="M{x2 - 6} {y2 - 4} L{x2} {y2} L{x2 - 6} {y2 + 4}" fill="none" stroke="{color}" stroke-width="{sw}" ' \
           'stroke-linecap="round" stroke-linejoin="round"/>' if y1 == y2 else \
           f'<path d="M{x2 - 4} {y2 - 6} L{x2} {y2} L{x2 + 4} {y2 - 6}" fill="none" stroke="{color}" stroke-width="{sw}" ' \
           'stroke-linecap="round" stroke-linejoin="round"/>'
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{sw}" fill="none"/>' + head


def mark(x, y, s=1.0):
    return (f'<g transform="translate({x} {y}) scale({s})"><rect width="28" height="28" rx="7" fill="{D["brand-soft"]}" '
            f'stroke="{BRAND}" stroke-opacity="0.55"/>'
            f'<path d="M6.5 19.5 11.5 10.5 16.5 16" stroke="{BRAND}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M16.5 16 21.5 8" stroke="{BRAND}" stroke-width="2" fill="none" stroke-linecap="round" stroke-dasharray="2 2.6"/>'
            f'<circle cx="6.5" cy="19.5" r="2.2" fill="{BRAND}"/><circle cx="11.5" cy="10.5" r="2.2" fill="{BRAND}"/>'
            f'<circle cx="16.5" cy="16" r="2.2" fill="{BRAND}"/><circle cx="21.5" cy="8" r="2.2" fill="none" stroke="{BRAND}" stroke-width="1.6"/></g>')


def defs() -> str:
    return (f'<defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">'
            f'<path d="M32 0H0V32" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>'
            f'<radialGradient id="halo" cx="0.68" cy="0.46" r="0.62"><stop offset="0" stop-color="{BRAND}" stop-opacity="0.10"/>'
            f'<stop offset="1" stop-color="{BRAND}" stop-opacity="0"/></radialGradient>'
            '<filter id="glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')


def canvas() -> str:
    return (defs() + f'<rect width="{W}" height="{H}" fill="{BG}"/><rect width="{W}" height="{H}" fill="url(#grid)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#halo)"/>')


def act(a: dict) -> str:
    p = a.get("params") or {}
    return f'{a["action"]}({", ".join(str(v) for v in p.values())})'


# ------------------------------------------------------------------ chrome
def chrome(A: Anim | None) -> str:
    out = [mark(36, 18), text(76, 38, "formal-agent-lab", size=17, weight=650)]
    vw = text_width(f"v{VERSION}", 10.5, True) + 14
    out.append(rect(232, 22, vw, 20, fill="none", stroke=EDGE, r=10) + mono(239, 36, f"v{VERSION}", size=10.5, fill=MUTED))
    scenes = STORY["scenes"]
    x0, step = 560, 114
    for i, s in enumerate(scenes):
        x = x0 + i * step
        label = f"{i + 1:02d} {s['kicker']}"
        cls = A.fill_at(s["start"], DIM, TXT, s["end"]) if A else ""
        out.append(mono(x, 37, label, size=10.5, weight=600, fill=DIM if A else MUTED,
                        extra=f'class="{cls}" letter-spacing="0.6"' if cls else 'letter-spacing="0.6"'))
    if A:
        bar = f'<rect x="{x0}" y="46" width="{step - 30}" height="2" rx="1" fill="{BRAND}" filter="url(#glow)"/>'
        out.append(g(A.steps_x([(s["start"], i * step) for i, s in enumerate(scenes)]), bar))
    out.append(f'<line x1="36" y1="62" x2="{W - 36}" y2="62" stroke="{EDGE}"/>')
    return "".join(out)


def trace_bar(A: Anim | None) -> str:
    """Bottom: a timeline of the six stages with a playhead, the status line and the data provenance."""
    x0, x1, y = 36, W - 36, 650
    out = [f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{EDGE}" stroke-width="2"/>']
    for s in STORY["scenes"]:
        xs = x0 + (x1 - x0) * s["start"] / TOTAL
        out.append(f'<line x1="{xs}" y1="{y - 5}" x2="{xs}" y2="{y + 5}" stroke="{EDGE}" stroke-width="1.5"/>')
        out.append(mono(xs + 6, y - 9, s["kicker"].lower(), size=9.5, fill=DIM))
    if A:
        out.append(g(A.grow_x(0, TOTAL - 0.01, TOTAL + 0.3, timing="linear"),
                     f'<rect x="{x0}" y="{y - 1}" width="{x1 - x0}" height="2" fill="{BRAND}" opacity="0.8"/>'))
        out.append(g(A.linear_x(x1 - x0), f'<circle cx="{x0}" cy="{y}" r="4" fill="{BRAND}" filter="url(#glow)"/>'))
        for s in STORY["scenes"]:
            out.append(g(A.show(s["start"] + 0.2, s["end"], dy=0),
                         mono(x0, 684, "› " + s["status"], size=11, fill=TXT2)))
    src = DATA["source"]
    out.append(mono(x1, 704, f"真实数据 · design/animation/demo-data.json · 订单服务示例（deviation）· 提交 {src['captured_at_commit']}",
                    size=9.5, fill=DIM, anchor="end"))
    return "".join(out)


def left_panel(A: Anim, s: dict, i: int) -> str:
    t0, t1 = s["start"], s["end"]
    head = mono(40, 132, f"{i + 1:02d}", size=44, weight=700, fill=BRAND, extra='opacity="0.9"')
    head += mono(110, 106, s["kicker"], size=11, weight=600, fill=MUTED, extra='letter-spacing="2"')
    head += text(110, 132, s["title"], size=24, weight=700)
    for k, line in enumerate(s["caption"]):
        head += text(40, 178 + k * 23, line, size=14, fill=TXT2)
    out = [g(A.show(t0 + 0.05, t1, dy=6), head)]
    cy = 178 + len(s["caption"]) * 23 + 22
    lines = s["command"]
    box = rect(40, cy, 400, 22 + len(lines) * 19, fill="#0d1219", stroke=EDGE, r=8)
    box += f'<circle cx="54" cy="{cy + 11}" r="2.5" fill="{DIM}"/><circle cx="63" cy="{cy + 11}" r="2.5" fill="{DIM}"/>' \
           f'<circle cx="72" cy="{cy + 11}" r="2.5" fill="{DIM}"/>'
    for k, line in enumerate(lines):
        prompt, rest = (line[:2], line[2:]) if line.startswith("$ ") else ("", line)
        y = cy + 30 + k * 19
        if prompt:
            box += mono(52, y, "$", size=11, fill=OK) + mono(64, y, rest, size=11, fill=TXT, extra='xml:space="preserve"')
        else:
            box += mono(52, y, rest, size=11, fill=TXT2, extra='xml:space="preserve"')
    out.append(g(A.show(t0 + 0.45, t1, dy=6), box))
    return "".join(out)


# ------------------------------------------------------------------ scenes (generic components, data from DATA)
STATES = ["status[orders]", "stock[skus]", "remaining[orders]", "on[orders, stations]", "clock"]
ACTIONS = ["reserve(o)", "enqueue(o)", "start(o, st)", "tick()", "restock(s)"]
WRITES = [(0, 0), (0, 1), (1, 0), (2, 3), (2, 2), (3, 2), (3, 4), (4, 1)]   # action → state it writes
READS = [(0, 0), (1, 4), (2, 3)]                                          # property → state it reads


def scene_model(A: Anim | None, t0: float, t1: float) -> str:
    """A schema graph: entities and properties (left) · state (middle) · actions (right); actions write state from the
    right, properties read it from the left, so no edge crosses a column."""
    m = DATA["model"]
    c0, c1, c2 = STAGE_X0, STAGE_X0 + 300, STAGE_X0 + 590
    w0, w1, w2, bh = 236, 214, 180, 34
    groups = [(c0, 104, "ENTITIES", [f'{n.split()[-1]} ×{k}' for n, k in m["entities"]], MUTED, w0, 0),
              (c0, 290, "PROPERTIES", [f"{n} · {'goal' if k == '目标' else 'invariant'}" for n, k in m["properties"]], OK, w0, 1),
              (c1, 104, "STATE", STATES, INFO, w1, 2),
              (c2, 104, "ACTIONS", ACTIONS, PRED, w2, 3)]
    pos: dict[tuple[str, int], tuple[float, float, float]] = {}
    nodes, edges = [], []
    for x, hy, head, items, accent, bw, order in groups:
        nodes.append(g(show(A, t0 + 0.2 + order * 0.18, t1), mono(x, hy, head, size=10, weight=600, fill=DIM,
                                                                     extra='letter-spacing="1.5"')))
        gap = 50 if head in ("ENTITIES", "PROPERTIES") else 58
        for i, label in enumerate(items):
            y = hy + 16 + i * gap
            pos[(head, i)] = (x, y, bw)
            body = rect(x, y, bw, bh, r=7) + f'<rect x="{x}" y="{y + 9}" width="2" height="{bh - 18}" rx="1" fill="{accent}"/>'
            body += mono(x + 12, y + 21.5, label, size=11, fill=TXT)
            nodes.append(g(show(A, t0 + 0.3 + order * 0.18 + i * 0.06, t1), body))
    links = [("ACTIONS", a, s_, ERR, "w") for a, s_ in WRITES] + [("PROPERTIES", a, s_, BRAND, "r") for a, s_ in READS]
    for k, (src, a, st, color, kind) in enumerate(links):
        xa, ya, wa = pos[(src, a)]
        xs, ys, ws = pos[("STATE", st)]
        if kind == "w":  # from the action's left edge to the state's right edge
            x1, y1, x2, y2 = xa, ya + bh / 2, xs + ws, ys + bh / 2
        else:            # from the property's right edge to the state's left edge
            x1, y1, x2, y2 = xa + wa, ya + bh / 2, xs, ys + bh / 2
        mid = (x1 + x2) / 2
        length = int(abs(x2 - x1) + abs(y2 - y1) + 60)
        cls = A.draw(t0 + 1.1 + k * 0.06, t0 + 1.9 + k * 0.06, t1, length) if A else ""
        edges.append(f'<path d="M{x1} {y1} C{mid} {y1} {mid} {y2} {x2} {y2}" fill="none" stroke="{color}" '
                     f'stroke-opacity="0.6" stroke-width="1.4" class="{cls}"/>')
        edges.append(f'<circle cx="{x2}" cy="{y2}" r="2.2" fill="{color}" class="{cls and A.show(t0 + 1.9 + k * 0.06, t1, dy=0)}"/>')
    ly = 470
    legend = (f'<line x1="{c0}" y1="{ly}" x2="{c0 + 22}" y2="{ly}" stroke="{ERR}" stroke-opacity="0.8" stroke-width="1.6"/>'
              + mono(c0 + 30, ly + 4, "action writes state", size=10.5, fill=MUTED)
              + f'<line x1="{c0 + 190}" y1="{ly}" x2="{c0 + 212}" y2="{ly}" stroke="{BRAND}" stroke-opacity="0.8" stroke-width="1.6"/>'
              + mono(c0 + 220, ly + 4, "property reads state", size=10.5, fill=MUTED))
    chips, x = [], c0
    for label, color, glyph in [("type check PASS", OK, "✓"), (f'{m["state_locations"]} state locations', INFO, ""),
                                (f'{m["ground_actions"]} ground actions', PRED, ""), ("immutable version v1", MUTED, "")]:
        body, w = chip(x, 500, label, color, glyph=glyph)
        chips.append(g(show(A, t0 + 2.2 + len(chips) * 0.18, t1), body))
        x += w + 10
    return "".join(edges) + "".join(nodes) + g(show(A, t0 + 1.9, t1), legend) + "".join(chips)


def scene_check(A: Anim | None, t0: float, t1: float) -> str:
    """A horizon ruler: the bounded check covers ≤ bound steps; nothing is claimed beyond it; the run's length shown."""
    chk = DATA["model"]["initial_check"]
    bound, run_len = 12, DATA["run"]["steps"]
    x0, x1, y = STAGE_X0 + 10, STAGE_X1 - 30, 330
    sx = lambda k: x0 + (x1 - x0) * k / run_len  # noqa: E731
    q = rect(STAGE_X0, 92, 470, 104, fill="#0d1219", r=10)
    for k, (key, val, col) in enumerate([("query ", "GOAL_REACHABILITY(all_completed)", TXT),
                                         ("bound ", f"max_steps = {bound}", TXT),
                                         ("engine", "Z3 bounded model checking", TXT2),
                                         ("model ", "local-order-service@1", TXT2)]):
        q += mono(STAGE_X0 + 18, 118 + k * 21, key, size=11, fill=DIM) + mono(STAGE_X0 + 82, 118 + k * 21, val, size=11.5, fill=col)
    out = [g(show(A, t0 + 0.3, t1), q)]
    ruler = [f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{EDGE}" stroke-width="2"/>']
    for k in range(run_len + 1):
        tall = k % 4 == 0 or k in (bound, run_len)
        ruler.append(f'<line x1="{sx(k)}" y1="{y - (7 if tall else 4)}" x2="{sx(k)}" y2="{y + (7 if tall else 4)}" stroke="{DIM}" stroke-width="1"/>')
        if tall:
            ruler.append(mono(sx(k), y + 38, str(k), size=10, fill=MUTED, anchor="middle"))
    ruler.append(mono(x0, y + 58, "steps", size=10, fill=DIM))
    out.append(g(show(A, t0 + 0.6, t1), "".join(ruler)))
    swept = f'<rect x="{x0}" y="{y - 20}" width="{sx(bound) - x0}" height="40" rx="4" fill="{INFO}" fill-opacity="0.16" stroke="{INFO}" stroke-opacity="0.5"/>'
    out.append(g(A.grow_x(t0 + 0.9, t0 + 2.0, t1) if A else "", swept))
    beyond = (f'<rect x="{sx(bound)}" y="{y - 20}" width="{x1 - sx(bound)}" height="40" rx="4" fill="none" stroke="{DIM}" '
              f'stroke-dasharray="4 4"/>' + mono((sx(bound) + x1) / 2, y - 32, "beyond the bound: no claim", size=10.5,
                                                 fill=MUTED, anchor="middle"))
    out.append(g(show(A, t0 + 2.0, t1), beyond))
    bmark = (f'<line x1="{sx(bound)}" y1="{y - 56}" x2="{sx(bound)}" y2="{y + 30}" stroke="{INFO}" stroke-width="1.5"/>'
             + mono(sx(bound), y - 62, f"bound = {bound}", size=10.5, weight=600, fill=INFO, anchor="middle"))
    out.append(g(show(A, t0 + 1.9, t1), bmark))
    verdict, w = chip(STAGE_X0, 448, chk["verdict"], INFO, glyph="◆", size=12)
    verdict += text(STAGE_X0 + w + 14, 465, f"≤ {bound} 步内没有到达 all_completed 的路径 —— 有界结论", size=13, fill=TXT2)
    out.append(g(show(A, t0 + 2.3, t1), verdict))
    goal = (f'<circle cx="{sx(run_len)}" cy="{y}" r="6" fill="{OK}" filter="url(#glow)"/>'
            + mono(sx(run_len), y + 58, f"the run reached the goal at step {run_len}", size=10.5, fill=OK, anchor="end"))
    out.append(g(show(A, t0 + 2.9, t1), goal))
    return "".join(out)


PIPE = ["OBSERVE", "CANDIDATES", "CHECK", "PROPOSE"]


def header_row(cols: list[tuple[str, float]], y: float = 166) -> str:
    return "".join(mono(STAGE_X0 + dx, y, label, size=10, fill=DIM, extra='letter-spacing="1"') for label, dx in cols)


def pipeline(A: Anim | None, x: float, y: float, labels: list[str], t0: float, t1: float, color=BRAND, w=150, gap=36,
             pulse: tuple[float, float] | None = None) -> str:
    out = []
    for i, label in enumerate(labels):
        bx = x + i * (w + gap)
        body = rect(bx, y, w, 34, fill="#0d1219", stroke=color, r=17, extra='stroke-opacity="0.55"')
        body += mono(bx + w / 2, y + 21.5, label, size=11, weight=650, fill=color, anchor="middle", extra='letter-spacing="1"')
        if i < len(labels) - 1:
            body += arrow(bx + w + 6, y + 17, bx + w + gap - 6, y + 17, color=DIM)
        out.append(g(show(A, t0 + 0.2 + i * 0.12, t1), body))
    if A and pulse:
        total = (len(labels) - 1) * (w + gap) + w - 20
        for k in range(3):
            a, b = pulse[0] + k * 0.95, pulse[0] + k * 0.95 + 0.9
            if b < pulse[1]:
                out.append(g(A.travel(a, b, total, t1), f'<circle cx="{x + 10}" cy="{y + 17}" r="3.5" fill="{color}" filter="url(#glow)"/>'))
    return "".join(out)


def scene_plan(A: Anim | None, t0: float, t1: float) -> str:
    out = [pipeline(A, STAGE_X0, 96, PIPE, t0, t1, pulse=(t0 + 0.8, t1 - 0.2))]
    out.append(g(show(A, t0 + 0.5, t1), header_row([("STEP", 0), ("ACTION", 52), ("PRECONDITION", 268), ("EFFECT", 410)])))
    for i, s in enumerate(DATA["run"]["first_steps"][:9]):
        y = 190 + i * 41
        diff = s["verdict"] != "MATCH"
        row = rect(STAGE_X0 - 10, y - 6, 540, 32, fill=SOFT[ERR] if diff else "none", stroke=ERR if diff else "none", r=7,
                   extra='stroke-opacity="0.5"')
        row += mono(STAGE_X0, y + 14, f"{s['step']:>4}", size=11.5, fill=MUTED, extra='xml:space="preserve"')
        row += mono(STAGE_X0 + 52, y + 14, act(s), size=12, fill=TXT)
        c1, _ = chip(STAGE_X0 + 268, y - 1, "✓ APPLICABLE", OK, size=10)
        c2, _ = chip(STAGE_X0 + 410, y - 1, s["verdict"], ERR if diff else OK, size=10)
        out.append(g(show(A, t0 + 0.6 + i * 0.22, t1, dy=4), row + c1 + c2))
    return "".join(out)


def scene_execute(A: Anim | None, t0: float, t1: float) -> str:
    out = [pipeline(A, STAGE_X0, 96, ["INTENT", "GATES", "SEND", "RECONCILE"], t0, t1, color=INFO, pulse=(t0 + 0.8, t1 - 0.2))]
    out.append(g(show(A, t0 + 0.5, t1), header_row([("STEP", 0), ("ACTION", 52), ("PREPARED", 222), ("DISPATCHED", 346),
                                                    ("COMPLETED", 470)])))
    for i, s in enumerate(DATA["run"]["first_steps"][:6]):
        y = 194 + i * 50
        row = mono(STAGE_X0, y + 14, f"{s['step']:>4}", size=11.5, fill=MUTED, extra='xml:space="preserve"')
        row += mono(STAGE_X0 + 52, y + 14, act(s), size=12, fill=TXT)
        out.append(g(show(A, t0 + 0.7 + i * 0.12, t1, dy=4), row))
        for k, state in enumerate(s["ops"]):
            x = STAGE_X0 + 222 + k * 124
            t = t0 + 0.9 + i * 0.3 + k * 0.12
            cell = rect(x, y - 2, 108, 24, fill=SOFT[INFO] if k < 2 else SOFT[OK], stroke="none", r=12)
            cell += mono(x + 54, y + 14, state, size=10, weight=650, fill=INFO if k < 2 else OK, anchor="middle")
            out.append(g(show(A, t, t1, dy=0, fade=0.2), cell))
    stats, x = [], STAGE_X0
    r = DATA["run"]
    for label, color in [(f'{r["steps"]} steps', TXT2), (f'{r["events"]} events', TXT2),
                         (f'rejected {int(r["metrics"]["rejected_actions"])}', OK), ("no blind re-send", INFO)]:
        body, w = chip(x, 506, label, color if color != TXT2 else MUTED)
        stats.append(g(show(A, t0 + 2.3 + len(stats) * 0.15, t1), body))
        x += w + 10
    return "".join(out) + "".join(stats)


def scene_deviate(A: Anim | None, t0: float, t1: float) -> str:
    fd = DATA["run"]["first_difference"]
    d = fd["diffs"][0]
    rv = DATA["revision"]
    card = rect(STAGE_X0, 92, 390, 252, fill="#0d1219", r=12)
    card += mono(STAGE_X0 + 20, 122, f"step {fd['step']} · tick()", size=12, weight=650, fill=TXT)
    card += mono(STAGE_X0 + 20, 142, d["path"], size=11, fill=MUTED)
    out = [g(show(A, t0 + 0.2, t1), card)]
    pred = (f'<circle cx="{STAGE_X0 + 105}" cy="230" r="46" fill="none" stroke="{PRED}" stroke-width="2" stroke-dasharray="5 5"/>'
            + mono(STAGE_X0 + 105, 246, d["expected"], size=44, weight=700, fill=PRED, anchor="middle")
            + mono(STAGE_X0 + 105, 304, "◌ predicted", size=11, fill=PRED, anchor="middle"))
    obs = (f'<circle cx="{STAGE_X0 + 285}" cy="230" r="46" fill="none" stroke="{OBS}" stroke-width="2"/>'
           + mono(STAGE_X0 + 285, 246, d["observed"], size=44, weight=700, fill=OBS, anchor="middle")
           + mono(STAGE_X0 + 285, 304, "● observed", size=11, fill=TXT2, anchor="middle"))
    neq = mono(STAGE_X0 + 195, 244, "≠", size=34, weight=700, fill=ERR, anchor="middle", extra='filter="url(#glow)"')
    out += [g(show(A, t0 + 0.5, t1), pred), g(show(A, t0 + 0.9, t1), obs), g(show(A, t0 + 1.2, t1), neq)]
    v, _ = chip(STAGE_X0 + 20, 318, d["status"], ERR, size=10.5)
    out.append(g(show(A, t0 + 1.3, t1), v + mono(STAGE_X0 + 130, 332, f"expected by {fd['expected_by'].split(' on ')[0]}", size=10, fill=DIM)))
    flow = [(f'{rv["different"]} / {rv["comparisons"]}', "comparisons DIFFERENT", ERR),
            (f'{rv["suggestion"]["action"]["action_type"]}()', f'reads {", ".join(rv["suggestion"]["constants_read"])} · '
             f'writes {", ".join(rv["suggestion"]["state_families"])}', WARN),
            (f'{rv["regression_cases"]} cases', "minimal regression cases", BRAND)]
    for i, (big, small, col) in enumerate(flow):
        y = 92 + i * 92
        x = STAGE_X0 + 430
        body = rect(x, y, 330, 72, fill="#0d1219", stroke=col, r=10, extra='stroke-opacity="0.45"')
        body += mono(x + 18, y + 32, big, size=17, weight=700, fill=col)
        body += text(x + 18, y + 55, small, size=12, fill=TXT2) if i != 1 else mono(x + 18, y + 55, small, size=10.5, fill=TXT2)
        label = ["", "revision suggestion", ""][i]
        if label:
            body += mono(x + 312, y + 32, label, size=9.5, fill=MUTED, anchor="end")
        if i:
            body += arrow(x + 165, y - 18, x + 165, y - 4, color=DIM)
        out.append(g(show(A, t0 + 1.7 + i * 0.4, t1), body))
    return "".join(out)


def release_card(x, y, title, sub, cases, status, color, extra="", width=360) -> str:
    body = rect(x, y, width, 150, fill="#0d1219", stroke=color, r=12, extra='stroke-opacity="0.5"')
    step = min(78, (width - 40) / max(1, len(cases)))
    body += mono(x + 20, y + 30, title, size=12.5, weight=650, fill=TXT) + mono(x + 20, y + 50, sub, size=10.5, fill=MUTED)
    for k, c in enumerate(cases):
        cc, _ = chip(x + 20 + k * step, y + 66, c, OK if c == "PASS" else ERR, size=10)
        body += cc
    st, _ = chip(x + 20, y + 106, status, color, size=12, glyph="✓" if color == OK else "✕")
    body += st
    if extra:
        body += mono(x + width - 20, y + 124, extra, size=10.5, fill=MUTED, anchor="end")
    return body


def scene_release(A: Anim | None, t0: float, t1: float) -> str:
    rv = DATA["revision"]
    v1 = release_card(STAGE_X0, 92, "v1 · local-order-service@1", "regression replay", rv["old_release"]["cases"],
                      rv["old_release"]["status"], ERR)
    v2 = release_card(STAGE_X0 + 390, 92, f'v2 · {rv["revised_release"]["change"]}', "regression replay",
                      rv["revised_release"]["cases"], rv["revised_release"]["status"], OK,
                      extra=f'{rv["after_different"]} differences')
    out = [g(show(A, t0 + 0.2, t1), v1), g(show(A, t0 + 0.8, t1), arrow(STAGE_X0 + 364, 167, STAGE_X0 + 386, 167, color=DIM)),
           g(show(A, t0 + 0.9, t1), v2)]
    r = DATA["run"]
    bundle = rect(STAGE_X0, 276, 750, 110, fill="#0d1219", r=12)
    bundle += (f'<g transform="translate({STAGE_X0 + 22} 298)"><rect width="44" height="56" rx="6" fill="{SOFT[BRAND]}" stroke="{BRAND}" '
               f'stroke-opacity="0.6"/><path d="M14 10h16M14 18h16M14 26h10" stroke="{BRAND}" stroke-width="2" stroke-linecap="round"/>'
               f'<path d="M14 38h16v10h-16z" fill="none" stroke="{BRAND}" stroke-width="1.6"/></g>')
    bundle += mono(STAGE_X0 + 86, 312, "run.replay.zip", size=14, weight=650, fill=TXT)
    bundle += mono(STAGE_X0 + 86, 334, f"formal-lab/replay-bundle@2 · {r['events']} events · {r['steps']} steps · causal parents",
                   size=11, fill=TXT2)
    bundle += mono(STAGE_X0 + 86, 356, "manifest · model package · snapshots · operations — readable with no server", size=10.5,
                   fill=MUTED)
    out.append(g(show(A, t0 + 1.5, t1), bundle))
    legend, x = [], STAGE_X0
    for label, col in [("● observed", OBS), ("◆ verified in scope", INFO), ("◌ predicted", PRED), ("○ unknown", EVD["unknown"])]:
        body, w = chip(x, 412, label, col, size=10.5, filled=False)
        legend.append(g(show(A, t0 + 2.1 + len(legend) * 0.12, t1), body))
        x += w + 10
    return "".join(out) + "".join(legend)


SCENES = {"model": scene_model, "check": scene_check, "plan": scene_plan, "execute": scene_execute,
          "deviate": scene_deviate, "release": scene_release}


# ------------------------------------------------------------------ outputs
def story_svg() -> str:
    A = Anim()
    body = [canvas(), chrome(A)]
    for i, s in enumerate(STORY["scenes"]):
        body.append(left_panel(A, s, i))
        body.append(SCENES[s["id"]](A, s["start"], s["end"]))
    body.append(trace_bar(A))
    css = "\n".join(A.rules)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-labelledby="t d"><title id="t">formal-agent-lab：模型 → 有界检查 → 计划 → 执行 → 偏差 → 发布与回放</title>'
            f'<desc id="d">{esc(STORY["description"])}</desc>'
            f'<style>\n{css}\n.summary {{ display: none; }}\n'
            "@media (prefers-reduced-motion: reduce) { .story { display: none; } .summary { display: inline; } }\n"
            f'</style><g class="story">{"".join(body)}</g><g class="summary">{cover_body()}</g></svg>\n')


def cover_body() -> str:
    """The static poster: what the product is, the six stages with their real numbers, the deviation and the release."""
    m, r, rv = DATA["model"], DATA["run"], DATA["revision"]
    d = r["first_difference"]["diffs"][0]
    out = [canvas(), mark(40, 40, 1.3), mono(86, 62, f"v{VERSION}", size=12, fill=MUTED)]
    out.append(text(40, 140, "formal-agent-lab", size=52, weight=750, extra='letter-spacing="-1"'))
    out.append(text(40, 184, "从形式模型出发，让智能体的每一步", size=24, weight=650, fill=TXT2))
    out.append(text(40, 218, "都可检查、可比较、可回放。", size=24, weight=650, fill=TXT2))
    out.append(mono(40, 252, "local-first · Z3 bounded checks · Temporal durable runs", size=11.5, fill=MUTED))
    out.append(mono(40, 272, "field-level effect diffs · revision with regression cases · offline replay", size=11.5, fill=MUTED))
    rows = [("01", "MODEL", f'{m["state_locations"]} state locations · {m["ground_actions"]} ground actions · type check PASS', INFO),
            ("02", "CHECK", f'≤ 12 steps → {m["initial_check"]["verdict"]}', INFO),
            ("03", "PLAN", "proposals only from model candidates · precondition first", PRED),
            ("04", "EXECUTE", f'{r["steps"]} steps · {r["events"]} events · intent logged before send', INFO),
            ("05", "DEVIATE", f'{d["path"]}: predicted {d["expected"]} · observed {d["observed"]} → DIFFERENT', ERR),
            ("06", "RELEASE", f'v1 {rv["old_release"]["status"]} · v2 {rv["revised_release"]["change"]} {rv["revised_release"]["status"]}', OK)]
    for i, (n, k, line, col) in enumerate(rows):
        y = 330 + i * 46
        out.append(f'<line x1="40" y1="{y - 22}" x2="640" y2="{y - 22}" stroke="{EDGE}"/>')
        out.append(mono(40, y + 2, n, size=13, weight=700, fill=BRAND) + mono(72, y + 2, k, size=11, weight=650, fill=MUTED,
                                                                             extra='letter-spacing="1.5"'))
        out.append(f'<circle cx="168" cy="{y - 3}" r="3" fill="{col}"/>' + mono(182, y + 2, line, size=11.5, fill=TXT))
    # right: the deviation and the release, as on screen
    x = 700
    card = rect(x, 92, 540, 220, fill="#0d1219", r=14)
    card += mono(x + 22, 124, f"step {r['first_difference']['step']} · tick()  —  {d['path']}", size=12, fill=TXT2)
    card += (f'<circle cx="{x + 150}" cy="214" r="54" fill="none" stroke="{PRED}" stroke-width="2" stroke-dasharray="6 6"/>'
             + mono(x + 150, 232, d["expected"], size=52, weight=700, fill=PRED, anchor="middle")
             + mono(x + 150, 290, "◌ predicted", size=11, fill=PRED, anchor="middle")
             + mono(x + 270, 230, "≠", size=40, weight=700, fill=ERR, anchor="middle", extra='filter="url(#glow)"')
             + f'<circle cx="{x + 390}" cy="214" r="54" fill="none" stroke="{OBS}" stroke-width="2"/>'
             + mono(x + 390, 232, d["observed"], size=52, weight=700, fill=OBS, anchor="middle")
             + mono(x + 390, 290, "● observed", size=11, fill=TXT2, anchor="middle"))
    out.append(card)
    out.append(release_card(x, 336, "v1 · local-order-service@1", "regression replay", rv["old_release"]["cases"],
                            rv["old_release"]["status"], ERR, width=262))
    out.append(release_card(x + 278, 336, f'v2 · {rv["revised_release"]["change"]}', "regression replay",
                            rv["revised_release"]["cases"], rv["revised_release"]["status"], OK, width=262))
    out.append(mono(x, 520, f'run.replay.zip · formal-lab/replay-bundle@2 · {r["events"]} events · readable offline', size=11,
                    fill=MUTED))
    out.append(mono(W - 40, 690, f"真实数据：订单服务示例（工位 p2 半速，模型按正常速度预测）· design/animation/demo-data.json · 提交 "
                    f"{DATA['source']['captured_at_commit']}", size=10, fill=DIM, anchor="end"))
    return "".join(out)


def cover_svg() -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>formal-agent-lab</title>{cover_body()}</svg>\n')


def preview_html() -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>formal-agent-lab · 产品演示</title>
<style>
body {{ margin: 0; background: {BG}; font-family: {FONT}; color: {TXT}; display: grid; place-items: center; min-height: 100vh; }}
main {{ width: min(1280px, 100% - 32px); display: grid; gap: 12px; padding: 16px 0; }}
object {{ width: 100%; aspect-ratio: 16 / 9; border: 1px solid {EDGE}; border-radius: 12px; background: {BG}; }}
.bar {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
button {{ font: inherit; padding: 6px 12px; border-radius: 6px; border: 1px solid {EDGE}; background: {PANEL}; color: {TXT}; cursor: pointer; }}
input[type=range] {{ flex: 1; min-width: 200px; accent-color: {BRAND}; }}
small, span {{ color: {MUTED}; font-family: {MONO}; font-size: 12px; }}
</style></head><body><main>
<object id="demo" data="demo.svg" type="image/svg+xml" aria-label="产品演示动画"></object>
<div class="bar"><button id="toggle">暂停</button><input id="scrub" type="range" min="0" max="{TOTAL}" step="0.05" value="0" aria-label="时间">
<span id="time">0.0 s</span><small>{TOTAL} s loop · reduced motion → static poster</small></div>
<small>source: docs/assets/demo.svg · generator: scripts/render_demo.py · video: demo.mp4</small>
</main><script>
const obj = document.getElementById('demo'), btn = document.getElementById('toggle'), scrub = document.getElementById('scrub'), label = document.getElementById('time');
let playing = true;
const anims = () => obj.contentDocument ? obj.contentDocument.getAnimations() : [];
function show(t) {{ label.textContent = (t % {TOTAL}).toFixed(1) + ' s'; scrub.value = t % {TOTAL}; }}
btn.onclick = () => {{ playing = !playing; anims().forEach(a => playing ? a.play() : a.pause()); btn.textContent = playing ? '暂停' : '播放'; }};
scrub.oninput = () => {{ playing = false; btn.textContent = '播放'; anims().forEach(a => {{ a.pause(); a.currentTime = scrub.value * 1000; }}); show(+scrub.value); }};
setInterval(() => {{ const a = anims()[0]; if (a && playing) show((a.currentTime || 0) / 1000); }}, 100);
</script></body></html>
"""


def architecture_svg() -> str:
    """Architecture and the per-step run flow (README), in the same dark technical language."""
    w, h = 1280, 760
    out = [defs(), f'<rect width="{w}" height="{h}" fill="{BG}"/><rect width="{w}" height="{h}" fill="url(#grid)"/>']

    def box(x, y, bw, bh, title, lines=(), accent=BRAND, ident=""):
        b = rect(x, y, bw, bh, fill="#0d1219", r=10)
        b += f'<rect x="{x}" y="{y + 12}" width="2" height="{bh - 24}" rx="1" fill="{accent}"/>'
        b += text(x + 16, y + 27, title, size=14.5, weight=650)
        if ident:
            b += mono(x + bw - 14, y + 27, ident, size=10, fill=DIM, anchor="end")
        for i, line in enumerate(lines):
            b += mono(x + 16, y + 49 + i * 18, line, size=10.5, fill=TXT2)
        return b

    def label(x, y, s):
        return mono(x, y, s, size=10, weight=600, fill=DIM, extra='letter-spacing="2"')

    out.append(mark(40, 32) + text(80, 52, "架构与运行流程", size=20, weight=700))
    out.append(mono(240, 52, "contracts: formal-lab-contracts/v2 · plugins: entry point formal_lab.plugins", size=11, fill=MUTED))
    out.append(label(40, 96, "ENTRIES"))
    for i, (t, lines) in enumerate([("Web · React", ["六个功能区 · SSE 实时事件"]), ("fal CLI", ["运行 · 查询 · 导出 · 离线回放"]),
                                    ("Python SDK", ["Client · 插件测试工具"])]):
        out.append(box(40 + i * 246, 106, 230, 66, t, lines))
    out.append(arrow(780, 139, 812, 139))
    out.append(box(820, 106, 420, 66, "FastAPI  /api/v1", ["REST + SSE · 场景 · 运行 · 操作 · 矩阵 · 发布 · 参与者令牌"]))
    out.append(label(40, 206, "STATE & ORCHESTRATION"))
    out.append(box(40, 216, 380, 84, "PostgreSQL", ["模型版本 · 场景 · 运行与事件", "操作账本 · 规则 · 发布 · 矩阵单元"], accent=MUTED))
    out.append(box(440, 216, 380, 84, "Temporal", ["ExperimentWorkflow · MatrixWorkflow", "暂停 / 取消 / Worker 重启后按步恢复"], accent=MUTED))
    out.append(box(840, 216, 400, 84, "Artifact store · local / S3", ["快照 · 模型调用 · 查询包", "回放包（自包含，离线可读）"], accent=MUTED))
    out.append(arrow(1030, 174, 1030, 210) + arrow(630, 174, 630, 210))
    out.append(label(40, 336, "TURN KERNEL · runtime (local runner and worker share it)"))
    k = rect(40, 346, 1200, 186, fill="#0d1219", stroke=BRAND, r=14, extra='stroke-opacity="0.45"')
    stages = ["TURN", "OBSERVE", "PROPOSE", "CHECK", "GATE", "EXECUTE", "COMPARE", "TERMINATE"]
    k += f'<line x1="120" y1="392" x2="1160" y2="392" stroke="{BRAND}" stroke-opacity="0.35" stroke-width="2"/>'
    for i, st in enumerate(stages):
        x = 64 + i * 146
        k += rect(x, 374, 128, 36, fill=BG, stroke=BRAND, r=18, extra='stroke-opacity="0.8"')
        k += mono(x + 64, 397, st, size=11.5, weight=700, fill=BRAND, anchor="middle", extra='letter-spacing="1"')
    for i, line in enumerate(["plan_step：观测 → 候选（在参与者视图下的信念上计算）→ 前提检查 → 提案（可能调用模型，先持久化）",
                              "apply_step：意图先记账 → 执行门控在发送前决定 → 发送 → 应答丢失时按操作 id 查询对账 → 逐字段效果比较",
                              "轮流 / 固定轮次表 / 同步批次 · 证据等级：观测 ● / 范围内核实 ◆ / 预测 ◌ / 未知 ○"]):
        k += text(64, 444 + i * 24, line, size=12.5, fill=TXT2)
    k += mono(64, 516, "packages/runtime/src/formal_lab_runtime/{engine,coordination,participants,turns}.py", size=10.5, fill=DIM)
    out.append(g("", k) + arrow(640, 302, 640, 340))
    out.append(label(40, 568, "PLUGINS"))
    plugins = [("模型前端", ["IR JSON", "MAL 攻击图"]), ("语义驱动", ["有限状态 IR", "仓储分配"]),
               ("环境", ["ir-world · 订单服务", "CAGE 4"]), ("策略", ["规则 · Z3 · 任务计划", "LLM（真实 / 替身）"]),
               ("验证器", ["Z3 有界检查", "PRISM-games（可选）"]), ("执行门控", ["库存安全线 · 装载率", "准入 Broker"]),
               ("评分与探针", ["确定性评分器", "独立探针"])]
    colors = TOKENS["participant"]["dark"]
    for i, (t, lines) in enumerate(plugins):
        out.append(box(40 + i * 172, 578, 160, 92, t, lines, accent=colors[i % len(colors)]))
    out.append(mono(40, 702, "每个插件声明接口、能力与配置 schema；内核只经公开接口调用它们（docs/architecture/plugin-integration.md）",
                    size=10.5, fill=MUTED))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
            f'<title>formal-agent-lab 架构</title>{"".join(out)}</svg>\n')


def cmd_svg() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "demo.svg").write_text(story_svg())
    (ASSETS / "demo-cover.svg").write_text(cover_svg())
    (ASSETS / "demo.html").write_text(preview_html())
    (ASSETS / "architecture.svg").write_text(architecture_svg())
    print(f"wrote demo.svg ({(ASSETS / 'demo.svg').stat().st_size} B), demo-cover.svg, demo.html, architecture.svg")


def cmd_frames() -> None:
    """Render every frame of demo.svg in Chromium (Web Animations API: pause + seek), for the video export."""
    from playwright.sync_api import sync_playwright

    shutil.rmtree(FRAMES, ignore_errors=True)
    FRAMES.mkdir(parents=True)
    only = [float(t) for t in sys.argv[2].split(",")] if len(sys.argv) > 2 else None  # preview: a few times only
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        page.goto((ASSETS / "demo.svg").as_uri())
        page.evaluate("document.getAnimations().forEach(a => a.pause())")
        times = only if only is not None else [i / FPS for i in range(int(TOTAL * FPS))]
        for i, t in enumerate(times):
            page.evaluate(f"document.getAnimations().forEach(a => a.currentTime = {t * 1000})")
            page.screenshot(path=str(FRAMES / (f"t{t:05.2f}.png" if only is not None else f"f{i:05d}.png")))
        if only is None:
            page.evaluate(f"document.getAnimations().forEach(a => a.currentTime = {STORY['cover_time_s'] * 1000})")
            page.screenshot(path=str(FRAMES / "still.png"))
        cover = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        cover.goto((ASSETS / "demo-cover.svg").as_uri())
        cover.screenshot(path=str(FRAMES / "cover.png"))
        arch = b.new_page(viewport={"width": 1280, "height": 760}, device_scale_factor=1.25)
        arch.goto((ASSETS / "architecture.svg").as_uri())
        arch.screenshot(path=str(FRAMES / "architecture.png"))
        b.close()
    print(f"{len(times)} frames in {FRAMES.relative_to(ROOT)}")


def cmd_encode() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FRAMES / "f%05d.png"),
                    "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "20", "-movflags", "+faststart", str(ASSETS / "demo.mp4")], check=True)
    cover = FRAMES / "cover.png"
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "1920", "-o", str(ASSETS / "demo-cover.png"), str(ASSETS / "demo-cover.svg")],
                       check=True)
    elif cover.exists():
        shutil.copyfile(cover, ASSETS / "demo-cover.png")
    print(f"wrote demo.mp4 ({(ASSETS / 'demo.mp4').stat().st_size} B), demo-cover.png")


if __name__ == "__main__":
    {"svg": cmd_svg, "frames": cmd_frames, "encode": cmd_encode}[sys.argv[1] if len(sys.argv) > 1 else "svg"]()
