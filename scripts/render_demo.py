#!/usr/bin/env python3
"""The product demo animation (phase 3A, G5): model → plan → run → deviation → evidence, 20 s loop.

Source of truth: design/animation/storyboard.json (scenes, timing, captions), design/animation/demo-data.json (real
values from the order-service deviation run and scripts/model_revision_evidence.py) and design/tokens.json (colours).
Outputs (docs/assets/):
  demo.svg        editable, animated SVG (CSS keyframes, one shared loop; prefers-reduced-motion → static summary)
  demo-cover.svg  static cover (the five stages side by side)          demo-cover.png  (rsvg-convert or Chromium)
  demo.html       web preview (play / pause, scrub, reduced-motion aware)
  demo.mp4        video export: every frame rendered from demo.svg in Chromium, encoded with ffmpeg

    python3 scripts/render_demo.py svg                     # stdlib only: demo.svg, demo-cover.svg, demo.html
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
C = TOKENS["color"]["light"]
P = TOKENS["participant"]["light"]
EV = {k: v["light"] for k, v in TOKENS["evidence"].items() if isinstance(v, dict)}
TOTAL = STORY["duration_s"]
EASE = TOKENS["motion"]["easing"]["standard"]
FONT = "Inter, 'PingFang SC', 'Hiragino Sans GB', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, monospace"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


class Anim:
    """CSS keyframe animations that all share the loop length, so every element stays in sync."""

    def __init__(self) -> None:
        self.rules: list[str] = []
        self.n = 0

    def pct(self, t: float) -> str:
        return f"{max(0.0, min(100.0, t / TOTAL * 100)):.3f}%"

    def _add(self, frames: list[tuple[float, str]], extra: str = "") -> str:
        self.n += 1
        name = f"k{self.n}"
        frames = sorted(frames, key=lambda f: f[0])
        body = " ".join(f"{self.pct(t)} {{ {css} }}" for t, css in frames)
        self.rules.append(f"@keyframes {name} {{ {body} }}")
        self.rules.append(f".{name} {{ animation: {name} {TOTAL}s {EASE} infinite both; {extra} }}")
        return name

    def show(self, t_in: float, t_out: float, dy: float = 10, fade: float = 0.45) -> str:
        """Visible (and in place) between t_in and t_out; slides up by dy while fading in."""
        off, on = f"opacity: 0; transform: translate(0px, {dy}px);", "opacity: 1; transform: translate(0px, 0px);"
        return self._add([(0, off), (t_in, off), (t_in + fade, on), (t_out - 0.3, on), (t_out, "opacity: 0;"),
                          (TOTAL, "opacity: 0;")])

    def draw(self, t0: float, t1: float, t_out: float, length: float) -> str:
        """A stroke that draws itself between t0 and t1 and fades at t_out."""
        return self._add([(0, f"stroke-dashoffset: {length}; opacity: 1;"), (t0, f"stroke-dashoffset: {length}; opacity: 1;"),
                          (t1, "stroke-dashoffset: 0; opacity: 1;"), (t_out - 0.3, "stroke-dashoffset: 0; opacity: 1;"),
                          (t_out, "stroke-dashoffset: 0; opacity: 0;"), (TOTAL, f"stroke-dashoffset: {length}; opacity: 0;")],
                         f"stroke-dasharray: {length};")

    def fill_at(self, t: float, before: str, after: str, t_out: float) -> str:
        return self._add([(0, f"fill: {before};"), (t, f"fill: {before};"), (t + 0.25, f"fill: {after};"),
                          (t_out, f"fill: {after};"), (min(TOTAL, t_out + 0.01), f"fill: {before};"), (TOTAL, f"fill: {before};")])

    def move_x(self, stops: list[tuple[float, float]]) -> str:
        frames = []
        for i, (t, x) in enumerate(stops):
            if i:
                frames.append((t - 0.001, f"transform: translate({stops[i - 1][1]}px, 0px);"))
                frames.append((t + 0.35, f"transform: translate({x}px, 0px);"))
            else:
                frames.append((t, f"transform: translate({x}px, 0px);"))
        frames.append((TOTAL, f"transform: translate({stops[-1][1]}px, 0px);"))
        return self._add(frames)


def text(x, y, s, *, size=14, weight=400, fill=None, anchor="start", family=FONT, cls="", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill or C["text"]}" text-anchor="{anchor}" class="{cls}" {extra}>{esc(s)}</text>')


def rect(x, y, w, h, *, fill=None, stroke=None, r=10, sw=1, dash=None, cls="", extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or C["surface"]}" '
            f'stroke="{stroke or C["border"]}" stroke-width="{sw}"{d} class="{cls}" {extra}/>')


def text_width(s: str, size: float, weight: int = 600) -> float:
    """Approximate advance width of `s` (CJK full width, Latin by class), enough to size pills and boxes."""
    w = 0.0
    for ch in s:
        if ord(ch) > 0x2e80:
            w += 1.0
        elif ch.isupper() or ch in "@%&MW":
            w += 0.70
        elif ch.isdigit():
            w += 0.60
        elif ch in " .,:;'|!il[]()":
            w += 0.32
        else:
            w += 0.56
    return w * size * (1.04 if weight >= 600 else 1.0)


def tag(x, y, label, *, fg, bg=None, border=None, dash=None, size=12, pad=9, glyph=""):
    w = int(text_width(label, size) + (size if glyph else 0) + 2 * pad)
    parts = [rect(x, y, w, size + 10, fill=bg or "none", stroke=border or (bg or fg), r=(size + 10) / 2, dash=dash)]
    tx = x + pad
    if glyph:
        parts.append(text(tx, y + size + 3, glyph, size=size - 2, fill=fg))
        tx += size
    parts.append(text(tx, y + size + 3, label, size=size, weight=600, fill=fg))
    return "".join(parts), w


def mark(x, y, s=1.0):
    return (f'<g transform="translate({x} {y}) scale({s})"><rect width="28" height="28" rx="7" fill="{C["brand"]}"/>'
            '<path d="M6.5 19.5 11.5 10.5 16.5 16" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M16.5 16 21.5 8" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-dasharray="2 2.6"/>'
            '<circle cx="6.5" cy="19.5" r="2.2" fill="#fff"/><circle cx="11.5" cy="10.5" r="2.2" fill="#fff"/>'
            '<circle cx="16.5" cy="16" r="2.2" fill="#fff"/><circle cx="21.5" cy="8" r="2.2" fill="none" stroke="#fff" stroke-width="1.6"/></g>')


def act(a: dict) -> str:
    p = a.get("params") or {}
    return f'{a["action"]}({", ".join(str(v) for v in p.values())})'


# ------------------------------------------------------------------ scenes
def scene_model(A: Anim, t0: float, t1: float) -> str:
    m = DATA["model"]
    out, lines = [], []
    cols = [(80, "领域（实体）", [f"{n}  ×{k}" for n, k in m["entities"]]),
            (370, "状态", ["订单状态 status[orders]", "可用库存 stock[skus]", "剩余处理时间 remaining[orders]",
                           "所在工位 on[orders, stations]", "逻辑时间 clock"]),
            (660, "动作", ["预约库存 reserve(o)", "加入队列 enqueue(o)", "开始处理 start(o, st)", "推进时间 tick()",
                           "补货 restock(s)"]),
            (950, "性质", [f"{n}（{k}）" for n, k in m["properties"]])]
    pos = {}
    for ci, (x, head, items) in enumerate(cols):
        out.append(f'<g class="{A.show(t0 + 0.2 + ci * 0.25, t1)}">' + text(x, 196, head, size=12, weight=600, fill=C["text-muted"]) + "</g>")
        for i, label in enumerate(items):
            y = 212 + i * 58
            pos[(ci, i)] = (x, y)
            accent = [C["neutral"], C["info"], P[0], C["success"]][ci]
            g = rect(x, y, 250, 42, r=8) + f'<rect x="{x}" y="{y + 8}" width="3" height="26" rx="1.5" fill="{accent}"/>'
            g += text(x + 14, y + 26, label, size=13, weight=600)
            out.append(f'<g class="{A.show(t0 + 0.35 + ci * 0.25 + i * 0.08, t1)}">{g}</g>')
    edges = [((2, 0), (1, 0), "w"), ((2, 0), (1, 1), "w"), ((2, 1), (1, 0), "w"), ((2, 2), (1, 3), "w"),
             ((2, 2), (1, 2), "w"), ((2, 3), (1, 2), "w"), ((2, 3), (1, 4), "w"), ((2, 4), (1, 1), "w"),
             ((1, 0), (3, 0), "r"), ((1, 4), (3, 1), "r"), ((1, 3), (3, 2), "r")]
    for k, ((ca, ia), (cb, ib), kind) in enumerate(edges):
        xa, ya = pos[(ca, ia)]
        xb, yb = pos[(cb, ib)]
        if kind == "w":  # action (col 2) writes a state (col 1): from the action's left edge to the state's right edge
            x1, y1, x2, y2 = xa, ya + 21, xb + 250, yb + 21
        else:            # a property (col 3) reads a state
            x1, y1, x2, y2 = xa + 250, ya + 21, xb, yb + 21
        mid = (x1 + x2) / 2
        length = abs(x2 - x1) + abs(y2 - y1) + 40
        color = C["danger"] if kind == "w" else C["brand"]
        lines.append(f'<path d="M{x1} {y1} C{mid} {y1} {mid} {y2} {x2} {y2}" fill="none" stroke="{color}" stroke-opacity="0.55" '
                     f'stroke-width="1.6" class="{A.draw(t0 + 1.3 + k * 0.07, t0 + 2.2 + k * 0.07, t1, int(length))}"/>')
    lg = (f'<line x1="80" y1="535" x2="104" y2="535" stroke="{C["danger"]}" stroke-width="2" stroke-opacity="0.6"/>'
          + text(110, 539, "动作写入", size=12, fill=C["text-secondary"])
          + f'<line x1="186" y1="535" x2="210" y2="535" stroke="{C["brand"]}" stroke-width="2" stroke-opacity="0.6"/>'
          + text(216, 539, "性质读取", size=12, fill=C["text-secondary"]))
    out = lines + out  # edges under the boxes
    out.append(f'<g class="{A.show(t0 + 2.0, t1)}">{lg}</g>')
    chips = [("类型检查通过", C["success"], C["success-soft"], "✓"),
             (f'{m["state_locations"]} 个状态位置 · {m["ground_actions"]} 个基础动作', C["text-secondary"], C["neutral-soft"], ""),
             ("有界检查：≤12 步内无见证（有界结论）", C["info"], C["info-soft"], "◆")]
    x = 80
    for i, (label, fg, bg, glyph) in enumerate(chips):
        g, w = tag(x, 566, label, fg=fg, bg=bg, glyph=glyph, size=13)
        out.append(f'<g class="{A.show(t0 + 2.4 + i * 0.25, t1)}">{g}</g>')
        x += w + 12
    return "".join(out)


def scene_plan(A: Anim, t0: float, t1: float) -> str:
    out = []
    stages = ["观测", "信念", "候选（模型给出）", "策略选择", "前提检查", "提案"]
    x = 80
    for i, s in enumerate(stages):
        w = 150 if len(s) > 4 else 104
        g = rect(x, 200, w, 48, r=10, fill=C["surface"]) + text(x + w / 2, 230, s, size=14, weight=600, anchor="middle")
        hl = rect(x, 200, w, 48, r=10, fill=C["brand-soft"], stroke=C["brand"], sw=1.5)
        out.append(f'<g class="{A.show(t0 + 0.2 + i * 0.12, t1)}">{g}</g>')
        out.append(f'<g class="{A.show(t0 + 0.8 + i * 0.28, t0 + 0.8 + i * 0.28 + 0.6, dy=0, fade=0.12)}">{hl}'
                   + text(x + w / 2, 230, s, size=14, weight=700, anchor="middle", fill=C["brand"]) + "</g>")
        if i < len(stages) - 1:
            out.append(f'<g class="{A.show(t0 + 0.3 + i * 0.12, t1)}"><path d="M{x + w + 6} 224 h18 m-6 -5 l6 5 l-6 5" '
                       f'stroke="{C["text-muted"]}" stroke-width="1.6" fill="none" stroke-linecap="round"/></g>')
        x += w + 30
    out.append(f'<g class="{A.show(t0 + 0.5, t1)}">' + text(80, 300, "策略：订单处理规则（RULE）· 逐步提案，只从模型给出的候选中选择", size=13,
                                                        fill=C["text-secondary"]) + "</g>")
    for i, s in enumerate(DATA["run"]["first_steps"][:8]):
        col, row = i % 4, i // 4
        x, y = 80 + col * 285, 330 + row * 92
        g = rect(x, y, 265, 72, r=10)
        g += text(x + 16, y + 26, f"步 {s['step']}", size=12, weight=600, fill=C["text-muted"])
        g += text(x + 16, y + 52, act(s), size=16, weight=650, family=MONO)
        t, _ = tag(x + 170, y + 12, "提案", fg=EV["predicted"], dash="3 3", size=11)
        g += t
        out.append(f'<g class="{A.show(t0 + 1.4 + i * 0.28, t1)}">{g}</g>')
    return "".join(out)


def scene_run(A: Anim, t0: float, t1: float) -> str:
    out = []
    n = DATA["run"]["steps"]
    out.append(f'<g class="{A.show(t0 + 0.1, t1)}">' + text(80, 200, f"运行：{n} 个逻辑步 · 订单服务进程（FastAPI + SQLite）是环境", size=13,
                                                        weight=600, fill=C["text-secondary"]) + "</g>")
    for i in range(n):
        x = 80 + i * 42
        tt = t0 + 0.3 + i * 0.1
        cls = A.fill_at(tt, C["surface-sunken"], "#cfe8da", t1)
        out.append(f'<g class="{A.show(t0 + 0.15, t1, dy=0)}"><rect x="{x}" y="216" width="34" height="34" rx="6" '
                   f'stroke="{C["border"]}" class="{cls}"/>' + text(x + 17, 238, i + 1, size=11, anchor="middle",
                                                                       fill=C["text-secondary"]) + "</g>")
    s6 = DATA["run"]["first_steps"][5]
    card = rect(80, 290, 690, 250, r=12)
    card += text(104, 324, "环境操作 · 意图先记账，再发送", size=15, weight=650)
    card += text(104, 350, f"run_demo:s{s6['step']}:handler:apply   {act(s6)}", size=13, family=MONO, fill=C["text-secondary"])
    out.append(f'<g class="{A.show(t0 + 0.6, t1)}">{card}</g>')
    states = [("PREPARED", "意图已记录", C["neutral"]), ("DISPATCHED", "已发送（带操作 id）", C["info"]),
              ("COMPLETED", "服务应答 APPLIED", C["success"])]
    for i, (st, note, col) in enumerate(states):
        x = 104 + i * 220
        g = rect(x, 376, 196, 70, r=10, fill=C["surface-sunken"])
        g += f'<circle cx="{x + 20}" cy="{400}" r="6" fill="{col}"/>' + text(x + 34, 405, st, size=13, weight=700, family=MONO, fill=col)
        g += text(x + 16, 432, note, size=12, fill=C["text-secondary"])
        out.append(f'<g class="{A.show(t0 + 1.2 + i * 0.55, t1)}">{g}</g>')
        if i < 2:
            out.append(f'<g class="{A.show(t0 + 1.45 + i * 0.55, t1)}"><path d="M{x + 200} 411 h16 m-6 -5 l6 5 l-6 5" '
                       f'stroke="{C["text-muted"]}" stroke-width="1.6" fill="none"/></g>')
    note = text(104, 486, "应答丢失时按 id 查询对账（OUTCOME_UNKNOWN → RECONCILED），", size=12, fill=C["text-secondary"])
    note += text(104, 506, "服务无记录且不能幂等重发时标记人工复核，从不猜测。", size=12, fill=C["text-secondary"])
    out.append(f'<g class="{A.show(t0 + 2.6, t1)}">{note}</g>')
    env = rect(810, 290, 390, 250, r=12, fill=C["surface"])
    env += text(834, 324, "订单服务（真实进程）", size=15, weight=650)
    for i, (k, v) in enumerate([("环境", "formal-lab.env.order-service"), ("去重", "按 operation id"),
                                ("查询", "GET /operations/{id}"), ("完成订单", f'{int(DATA["run"]["metrics"]["orders_completed"])} 个'),
                                ("事件", f'{DATA["run"]["events"]} 条（因果链）')]):
        env += text(834, 360 + i * 32, k, size=12, fill=C["text-muted"]) + text(914, 360 + i * 32, v, size=13, family=MONO if i < 3 else FONT)
    out.append(f'<g class="{A.show(t0 + 0.9, t1)}">{env}</g>')
    return "".join(out)


def scene_deviation(A: Anim, t0: float, t1: float) -> str:
    out = []
    diff = DATA["run"]["first_difference"]
    d0 = diff["diffs"][0]
    rv = DATA["revision"]
    n = DATA["run"]["steps"]
    for i in range(n):
        x = 80 + i * 42
        fill = C["danger-soft"] if i + 1 == diff["step"] else "#cfe8da"
        stroke = C["danger"] if i + 1 == diff["step"] else C["border"]
        out.append(f'<g class="{A.show(t0 + 0.1, t1, dy=0)}"><rect x="{x}" y="216" width="34" height="34" rx="6" fill="{fill}" '
                   f'stroke="{stroke}" stroke-width="{2 if i + 1 == diff["step"] else 1}"/>'
                   + text(x + 17, 238, i + 1, size=11, anchor="middle", fill=C["danger"] if i + 1 == diff["step"] else C["text-secondary"]) + "</g>")
    card = rect(80, 280, 700, 196, r=12)
    card += text(104, 314, f"步 {diff['step']} · tick() · 效果比较（逐字段）", size=15, weight=650)
    card += text(104, 338, f"预期来源：{diff['expected_by']}", size=12, fill=C["text-muted"], family=MONO)
    card += text(104, 378, "位置", size=12, fill=C["text-muted"]) + text(330, 378, "预测", size=12, fill=C["text-muted"])
    card += text(470, 378, "观测", size=12, fill=C["text-muted"]) + text(610, 378, "结论", size=12, fill=C["text-muted"])
    card += f'<line x1="104" y1="390" x2="756" y2="390" stroke="{C["border"]}"/>'
    card += text(104, 424, d0["path"], size=15, weight=650, family=MONO)
    out.append(f'<g class="{A.show(t0 + 0.4, t1)}">{card}</g>')
    tp, _ = tag(330, 405, f"◌ 预测 {d0['expected']}", fg=EV["predicted"], dash="3 3", size=13)
    to, _ = tag(470, 405, f"● 观测 {d0['observed']}", fg=EV["observed"], size=13)
    td, _ = tag(610, 405, "DIFFERENT", fg=C["danger"], bg=C["danger-soft"], size=13)
    out.append(f'<g class="{A.show(t0 + 0.9, t1)}">{tp}</g><g class="{A.show(t0 + 1.3, t1)}">{to}</g>'
               f'<g class="{A.show(t0 + 1.8, t1)}">{td}</g>')
    truth = rect(810, 280, 390, 196, r=12, fill=C["warning-soft"], stroke=C["warning-soft"])
    truth += text(834, 314, "真实服务的运行条件", size=15, weight=650, fill=C["warning"])
    truth += text(834, 346, "工位 p2 以半速处理订单，", size=14, fill=C["text"])
    truth += text(834, 370, "模型按正常速度预测。", size=14, fill=C["text"])
    truth += text(834, 410, f"本次运行 {rv['comparisons']} 次比较，{rv['different']} 处差异", size=13, fill=C["text-secondary"])
    truth += text(834, 434, "都在 tick 的效果上", size=13, fill=C["text-secondary"])
    out.append(f'<g class="{A.show(t0 + 2.1, t1)}">{truth}</g>')
    sug = rect(80, 500, 1120, 96, r=12, fill=C["brand-soft"], stroke=C["brand-soft"])
    sug += text(104, 534, "模型修订建议", size=15, weight=650, fill=C["brand"])
    consts = "、".join(rv["suggestion"]["constants_read"])
    sug += text(104, 564, f"tick 的效果读取常量 {consts}：预测值与服务不符，修改模型后重新检查并在新运行中比较", size=13, fill=C["text"])
    sug += text(104, 586, f"同时生成 {rv['regression_cases']} 个最小回归案例（初始状态 + 动作 + 预期 / 观测）", size=13, fill=C["text-secondary"])
    out.append(f'<g class="{A.show(t0 + 2.5, t1)}">{sug}</g>')
    return "".join(out)


def scene_evidence(A: Anim, t0: float, t1: float) -> str:
    out = []
    rv = DATA["revision"]
    for i, (title, cases, status, change) in enumerate([
            ("模型 v1（按正常速度预测）", rv["old_release"]["cases"], rv["old_release"]["status"], "原始模型"),
            ("模型 v2", rv["revised_release"]["cases"], rv["revised_release"]["status"], rv["revised_release"]["change"])]):
        x = 80 + i * 380
        ok = status == "RELEASED"
        g = rect(x, 200, 356, 220, r=12)
        g += text(x + 24, 236, title, size=15, weight=650)
        g += text(x + 24, 262, change, size=13, family=MONO, fill=C["text-secondary"])
        g += text(x + 24, 302, f"回归案例 {len(cases)} 个", size=12, fill=C["text-muted"])
        for k, c in enumerate(cases):
            passed = c == "PASS"
            g += (f'<rect x="{x + 24 + k * 56}" y="316" width="46" height="34" rx="8" fill="{C["success-soft"] if passed else C["danger-soft"]}"/>'
                  + text(x + 47 + k * 56, 339, "✓" if passed else "✕", size=16, weight=700, anchor="middle",
                         fill=C["success"] if passed else C["danger"]))
        t, _ = tag(x + 24, 368, status, fg=C["success"] if ok else C["danger"], bg=C["success-soft"] if ok else C["danger-soft"], size=14)
        g += t
        out.append(f'<g class="{A.show(t0 + 0.3 + i * 0.9, t1)}">{g}</g>')
    after = rect(80, 444, 736, 64, r=12, fill=C["success-soft"], stroke=C["success-soft"])
    after += text(104, 482, f"修订后对同一服务的新运行：{rv['after_different']} 处模型差异", size=15, weight=650, fill=C["success"])
    out.append(f'<g class="{A.show(t0 + 2.0, t1)}">{after}</g>')
    b = rect(840, 200, 360, 308, r=12)
    b += text(864, 236, "回放包（离线可读）", size=15, weight=650)
    for i, (k, v) in enumerate([("事件", f'{DATA["run"]["events"]} 条，因果父事件可追溯'), ("证据等级", "观测 · 范围内核实 · 预测 · 未知"),
                                ("操作", "每个操作的状态路径"), ("模型", "包内含所用模型版本"), ("读取", "fal replay view / verify")]):
        b += text(864, 276 + i * 44, k, size=12, fill=C["text-muted"]) + text(864, 296 + i * 44, v, size=13,
                                                                              family=MONO if i == 4 else FONT)
    out.append(f'<g class="{A.show(t0 + 1.2, t1)}">{b}</g>')
    legend = ""
    x = 80
    for key in ("observed", "verified", "predicted", "unknown"):
        e = TOKENS["evidence"][key]
        t, w = tag(x, 540, f'{e["glyph"]} {e["label"]}', fg=e["light"], dash="3 3" if e["stroke"] != "solid" else None, size=13)
        legend += t
        x += w + 10
    out.append(f'<g class="{A.show(t0 + 2.4, t1)}">{legend}</g>')
    return "".join(out)


SCENES = {"model": scene_model, "plan": scene_plan, "run": scene_run, "deviation": scene_deviation, "evidence": scene_evidence}


def chrome(A: Anim | None) -> str:
    """Header with the brand and the five-stage progress; footer with the data source."""
    out = [f'<rect width="{W}" height="{H}" fill="{C["canvas"]}"/>', mark(40, 26),
           text(80, 46, "formal-agent-lab", size=18, weight=700),
           text(236, 46, "形式模型 · 智能体实验台", size=13, fill=C["text-muted"])]
    x0, cw = 660, 116
    if A is not None:
        stops = [(s["start"], i * cw) for i, s in enumerate(STORY["scenes"])]
        out.append(f'<g class="{A.move_x(stops)}">' + rect(x0, 22, cw - 8, 36, fill=C["brand-soft"], stroke=C["brand"], r=18) + "</g>")
    for i, s in enumerate(STORY["scenes"]):
        out.append(text(x0 + i * cw + (cw - 8) / 2, 45, f'{i + 1}  {s["label"]}', size=14, weight=650, anchor="middle",
                        fill=C["text"]))
    out.append(f'<line x1="40" y1="84" x2="{W - 40}" y2="84" stroke="{C["border"]}"/>')
    src = DATA["source"]
    out.append(text(40, H - 28, f'真实数据 · 订单服务示例 deviation 案例 · 提交 {src["captured_at_commit"]} · '
                                "docs/execution/evidence/phase3/g3-release.json", size=12, fill=C["text-muted"]))
    return "".join(out)


def story_svg() -> str:
    A = Anim()
    body = [chrome(A)]
    for s in STORY["scenes"]:
        t0, t1 = s["start"], s["end"]
        head = (text(80, 132, s["title"], size=30, weight=700) + text(80, 162, s["caption"], size=15, fill=C["text-secondary"]))
        body.append(f'<g class="{A.show(t0 + 0.05, t1, dy=6)}">{head}</g>')
        body.append(SCENES[s["id"]](A, t0, t1))
    summary = cover_body(offset_y=0)
    css = "\n".join(A.rules)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-labelledby="t d"><title id="t">formal-agent-lab：模型 → 计划 → 运行 → 偏差 → 证据</title>'
            f'<desc id="d">{esc(STORY["description"])}</desc>'
            f'<style>\n{css}\n.summary {{ display: none; }}\n'
            "@media (prefers-reduced-motion: reduce) { .story { display: none; } .summary { display: inline; } }\n"
            f'</style><g class="story">{"".join(body)}</g><g class="summary">{summary}</g></svg>\n')


def cover_body(offset_y: int = 0) -> str:
    """Static composition: the five stages side by side, with the real result of each."""
    rv = DATA["revision"]
    d0 = DATA["run"]["first_difference"]["diffs"][0]
    out = [chrome(None)]
    out.append(text(80, 150, "从形式模型出发，让智能体的每一步都可检查、可比较、可回放", size=28, weight=700))
    out.append(text(80, 184, "本地运行的研究工作台：模型与有界检查、规划策略、持久运行、效果比较、离线证据。", size=15,
                    fill=C["text-secondary"]))
    cards = [("1  模型", [f'{DATA["model"]["state_locations"]} 个状态位置', f'{DATA["model"]["ground_actions"]} 个基础动作', "类型检查通过"], C["neutral"]),
             ("2  计划", [act(DATA["run"]["first_steps"][0]), act(DATA["run"]["first_steps"][1]), act(DATA["run"]["first_steps"][2])], EV["predicted"]),
             ("3  运行", [f'{DATA["run"]["steps"]} 个逻辑步', "意图先记账再发送", "按 id 对账"], C["info"]),
             ("4  偏差", [f'{d0["path"]}', f'预测 {d0["expected"]} · 观测 {d0["observed"]}', f'{rv["different"]} 处差异 → 修订建议'], C["danger"]),
             ("5  证据", [f'v1 回归 {rv["old_release"]["status"]}', f'v2 {rv["revised_release"]["change"]}', f'{rv["revised_release"]["status"]} · 0 处差异'], C["success"])]
    for i, (title, lines, col) in enumerate(cards):
        x = 80 + i * 228
        y = 240 + offset_y
        g = rect(x, y, 208, 236, r=14)
        g += f'<rect x="{x}" y="{y}" width="208" height="6" rx="3" fill="{col}"/>'
        g += text(x + 20, y + 48, title, size=20, weight=700)
        for k, line in enumerate(lines):
            code = i == 1 or (i == 3 and k == 0) or (i == 4 and k == 1)
            g += text(x + 20, y + 100 + k * 40, line, size=14, family=MONO if code else FONT,
                      fill=C["text"] if k == 0 else C["text-secondary"])
        out.append(g)
        if i < 4:
            out.append(f'<path d="M{x + 212} {y + 118} h12 m-5 -5 l5 5 l-5 5" stroke="{C["text-muted"]}" stroke-width="1.6" fill="none"/>')
    out.append(text(80, 528, "所有数字来自已跑通的订单服务示例（工位 p2 半速，模型按正常速度预测）及其模型修订证据。", size=13,
                    fill=C["text-muted"]))
    return "".join(out)


def cover_svg() -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>formal-agent-lab</title>{cover_body()}</svg>\n')


def preview_html() -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>formal-agent-lab · 产品演示</title>
<style>
body {{ margin: 0; background: {C["canvas"]}; font-family: {FONT}; color: {C["text"]}; display: grid; place-items: center; min-height: 100vh; }}
main {{ width: min(1280px, 100% - 32px); display: grid; gap: 12px; padding: 16px 0; }}
object {{ width: 100%; aspect-ratio: 16 / 9; border: 1px solid {C["border"]}; border-radius: 12px; background: #fff; }}
.bar {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
button {{ font: inherit; padding: 6px 12px; border-radius: 6px; border: 1px solid {C["border-strong"]}; background: #fff; cursor: pointer; }}
input[type=range] {{ flex: 1; min-width: 200px; accent-color: {C["brand"]}; }}
small {{ color: {C["text-muted"]}; }}
</style></head><body><main>
<object id="demo" data="demo.svg" type="image/svg+xml" aria-label="产品演示动画"></object>
<div class="bar"><button id="toggle">暂停</button><input id="scrub" type="range" min="0" max="{TOTAL}" step="0.05" value="0" aria-label="时间">
<span id="time">0.0 s</span><small>{TOTAL} 秒循环 · 系统设置“减少动态效果”时显示静态总结</small></div>
<small>源文件：docs/assets/demo.svg（可编辑）· 生成：scripts/render_demo.py · 视频：demo.mp4</small>
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
    """Architecture and the per-step run flow, in the same visual language (README)."""
    w, h = 1280, 700
    out = [f'<rect width="{w}" height="{h}" fill="{C["canvas"]}"/>']

    def box(x, y, bw, bh, title, sub="", *, fill=None, stroke=None, accent=None, title_color=None):
        g = rect(x, y, bw, bh, r=10, fill=fill or C["surface"], stroke=stroke or C["border"])
        if accent:
            g += f'<rect x="{x}" y="{y + 10}" width="3" height="{bh - 20}" rx="1.5" fill="{accent}"/>'
        g += text(x + 16, y + 26, title, size=15, weight=650, fill=title_color or C["text"])
        for i, line in enumerate(sub.split("\n") if sub else []):
            g += text(x + 16, y + 48 + i * 19, line, size=12.5, fill=C["text-secondary"])
        return g

    def arrow(x1, y1, x2, y2):
        return (f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{C["text-muted"]}" stroke-width="1.5" fill="none"/>'
                f'<path d="M{x2 - 5} {y2 - 7} L{x2} {y2} L{x2 + 5} {y2 - 7}" stroke="{C["text-muted"]}" stroke-width="1.5" fill="none" '
                'stroke-linecap="round" stroke-linejoin="round"/>')

    out.append(mark(40, 28) + text(80, 48, "架构与运行流程", size=20, weight=700))
    out.append(text(250, 48, "所有层共用契约 formal-lab-contracts/v2；插件经 entry point 注册，内核只经公开接口调用它们", size=13,
                    fill=C["text-muted"]))
    for i, (t, sub) in enumerate([("Web（React）", "六个功能区 · SSE 实时事件"), ("fal CLI", "运行 · 查询 · 导出 · 离线回放"),
                                  ("Python SDK", "Client · 插件测试工具")]):
        out.append(box(40 + i * 250, 88, 230, 74, t, sub, accent=C["brand"]))
    out.append(box(820, 88, 420, 74, "FastAPI /api/v1", "REST + SSE · 场景、运行、操作、批次、矩阵、发布", accent=C["brand"]))
    out.append(arrow(774, 125, 814, 125))
    out.append(box(40, 200, 360, 110, "PostgreSQL", "模型版本 · 场景 · 运行与事件\n操作账本 · 规则 · 发布 · 矩阵单元", accent=C["neutral"]))
    out.append(box(420, 200, 360, 110, "Temporal", "ExperimentWorkflow / MatrixWorkflow\n暂停 · 取消 · Worker 重启后按步恢复", accent=C["neutral"]))
    out.append(box(800, 200, 440, 110, "产物存储（本地 / S3 兼容）", "快照 · 模型调用 · 查询包 · 回放包（离线可读）", accent=C["neutral"]))
    out.append(arrow(1030, 162, 1030, 194) + arrow(600, 162, 600, 194))
    kernel = rect(40, 340, 1200, 190, r=12, fill=C["brand-soft"], stroke=C["brand-soft"])
    kernel += text(64, 372, "轮次内核（runtime，本地运行器与 Worker 共用）", size=15, weight=700, fill=C["brand"])
    stages = ["TURN", "OBSERVE", "PROPOSE", "CHECK", "EXECUTE", "RECONCILE", "COMPARE", "TERMINATE"]
    for i, st in enumerate(stages):
        x = 64 + i * 144
        kernel += rect(x, 390, 128, 36, r=18, fill=C["surface"], stroke=C["brand"])
        kernel += text(x + 64, 413, st, size=12.5, weight=700, anchor="middle", family=MONO, fill=C["brand"])
        if i < len(stages) - 1:
            kernel += f'<path d="M{x + 130} 408 h12" stroke="{C["brand"]}" stroke-width="1.5"/>'
    kernel += text(64, 456, "plan_step（可能调用模型，先持久化）→ apply_step（经协调器执行：意图先记账、门控决定、按 id 对账）→ 逐字段比较 → 规则与终止", size=12.5,
                   fill=C["text-secondary"])
    kernel += text(64, 480, "轮流 / 固定轮次表 / 同步批次（JOINT_BATCH：每轮一个环境步）· 参与者视图过滤规划器输入 · 证据等级：观测 / 范围内核实 / 预测 / 未知", size=12.5,
                   fill=C["text-secondary"])
    kernel += text(64, 504, "代码：packages/runtime/src/formal_lab_runtime/{engine,coordination,participants,turns}.py", size=12, family=MONO, fill=C["text-muted"])
    out.append(kernel + arrow(600, 310, 600, 334))
    plugins = [("语义驱动", "IR 有限状态 · 仓储分配\n协议示例：计数器"), ("环境", "IR / 驱动世界（纯数据）\n订单服务（HTTP 进程）"),
               ("策略", "规则 · Z3 · 任务计划\nLLM（真实 / 替身）"), ("验证器", "Z3 有界检查\nPRISM-games（可选扩展）"),
               ("执行门控", "库存安全线\n库区装载率"), ("评分与探针", "确定性评分器\n独立探针")]
    for i, (t, sub) in enumerate(plugins):
        out.append(box(40 + i * 202, 556, 186, 96, t, sub, accent=P[i % len(P)]))
    out.append(text(40, 684, "插件（entry point：formal_lab.plugins）", size=12, fill=C["text-muted"]))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img"><title>formal-agent-lab 架构</title>{"".join(out)}</svg>\n'


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
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        page.goto((ASSETS / "demo.svg").as_uri())
        page.evaluate("document.getAnimations().forEach(a => a.pause())")
        n = int(TOTAL * FPS)
        for i in range(n):
            page.evaluate(f"document.getAnimations().forEach(a => a.currentTime = {i * 1000 / FPS})")
            page.screenshot(path=str(FRAMES / f"f{i:05d}.png"))
        page.evaluate(f"document.getAnimations().forEach(a => a.currentTime = {STORY['cover_time_s'] * 1000})")
        page.screenshot(path=str(FRAMES / "still.png"))
        b.close()
    print(f"{n} frames in {FRAMES.relative_to(ROOT)}")


def cmd_encode() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FRAMES / "f%05d.png"),
                    "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "20", "-movflags", "+faststart", str(ASSETS / "demo.mp4")], check=True)
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "1920", "-o", str(ASSETS / "demo-cover.png"), str(ASSETS / "demo-cover.svg")],
                       check=True)
    print(f"wrote demo.mp4 ({(ASSETS / 'demo.mp4').stat().st_size} B), demo-cover.png")


if __name__ == "__main__":
    {"svg": cmd_svg, "frames": cmd_frames, "encode": cmd_encode}[sys.argv[1] if len(sys.argv) > 1 else "svg"]()
