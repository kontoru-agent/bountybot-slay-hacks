"""Render the Bountybot demo video + screenshots from the real demo log.

No screen recorder, no TTS on this VM: the video is rendered frame by frame
with PIL from demo/demo_run.log (a real run), with a caption bar carrying the
narration. 1280x720, 24 fps, ~2.5 minutes, silent with captions.

Outputs:
  demo/bountybot-demo.mp4
  demo/screenshots/01-scout.png, 02-hunt.png, 03-verify.png, 04-report.png
  demo/screenshots/05-architecture.png (pipeline diagram)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent  # repo root
DEMO = ROOT / "demo"
LOG = DEMO / "demo_run.log"
OUT = DEMO / "bountybot-demo.mp4"
FRAMES = DEMO / "_frames"

W, H = 1280, 720
TERM_H = 600
CAP_H = H - TERM_H
BG = (13, 17, 23)
TERM_FG = (230, 237, 243)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
YELLOW = (210, 153, 34)
CYAN = (88, 166, 255)
MUTED = (139, 148, 158)
CAP_BG = (22, 27, 34)
CAP_FG = (255, 255, 255)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO_B if bold else MONO, size)


def sans(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(SANS_B if bold else SANS, size)


def color_for(line: str) -> tuple[int, int, int]:
    if line.startswith("$"):
        return GREEN
    if "REENTRANCY" in line and ("Critical" in line or "withdraw" in line):
        return RED
    if line.startswith("[gate] [PASS]"):
        return GREEN
    if line.startswith("[gate] [FAIL]") or "[!!]" in line:
        return RED
    if line.startswith("[verify]"):
        return CYAN
    if line.startswith("[hunt]") and "clean" in line:
        return MUTED
    if line.startswith("[bountybot] DONE"):
        return GREEN
    if line.startswith("[report]"):
        return YELLOW
    return TERM_FG


def wrap(line: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Greedy wrap on spaces; long tokens are hard-split."""
    words = line.split(" ")
    out, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                out.append(cur)
            while font.getlength(w) > max_w:
                cut = max(1, int(len(w) * max_w / max(font.getlength(w), 1)))
                out.append(w[:cut])
                w = w[cut:]
            cur = w
    if cur:
        out.append(cur)
    return out or [""]


def render_terminal(lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f = mono(19)
    lh = 25
    max_rows = (TERM_H - 24) // lh
    # Wrap first, then keep the last rows so the newest line is never clipped.
    rows: list[tuple[str, tuple[int, int, int]]] = []
    for line in lines:
        for wl in wrap(line, f, W - 48):
            rows.append((wl, color_for(line)))
    rows = rows[-max_rows:]
    y = 12
    for text, color in rows:
        d.text((24, y), text, font=f, fill=color)
        y += lh
    return img


def render_caption(img: Image.Image, caption: str, sub: str = "") -> Image.Image:
    d = ImageDraw.Draw(img)
    d.rectangle([0, TERM_H, W, H], fill=CAP_BG)
    d.rectangle([0, TERM_H, W, TERM_H + 2], fill=(48, 54, 61))
    d.text((24, TERM_H + 18), caption, font=sans(26, bold=True), fill=CAP_FG)
    if sub:
        d.text((24, TERM_H + 58), sub, font=sans(20), fill=MUTED)
    return img


def render_title_card(title: str, lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((64, 170), title, font=mono(64, bold=True), fill=GREEN)
    y = 280
    for line in lines:
        d.text((64, y), line, font=sans(28), fill=TERM_FG)
        y += 48
    d.text((64, 620), "SLAY HACKS 2026  ·  Devpost  ·  github.com/kontoru-agent/bountybot-slay-hacks",
           font=mono(20), fill=MUTED)
    return img


def render_field_card() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((64, 60), "The same pipeline, on real programs", font=sans(34, bold=True), fill=TERM_FG)
    rows = [
        ("XE Network", "39 reports filed · XE-18940 (High) NEW, filed 19 Nov 2026"),
        ("Merkl", "full contract audit · 5/5 Foundry PoCs pass · Critical candidate"),
        ("Meta Muse", "C1 / C2 / P2 submitted 16 Nov 2026"),
        ("BNB Chain", "BountybotRegistry deployed · Sourcify exact match"),
    ]
    y = 150
    for name, desc in rows:
        d.text((64, y), name, font=sans(26, bold=True), fill=CYAN)
        d.text((64, y + 38), desc, font=sans(22), fill=TERM_FG)
        y += 104
    d.text((64, 600), "Bountybot — no runnable PoC means no report.",
           font=mono(22, bold=True), fill=GREEN)
    return img


def render_architecture() -> Image.Image:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((64, 50), "Bountybot — how the agent works", font=sans(34, bold=True), fill=(17, 17, 17))
    boxes = ["SCOUT\nscope", "HUNT\n10 bug classes", "GATE\n7 questions", "VERIFY\nFoundry PoC", "REPORT\ndraft"]
    bw, bh, gap = 200, 120, 22
    x = 64
    y = 200
    for i, b in enumerate(boxes):
        fill = (13, 17, 23) if i != 3 else (10, 122, 47)
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=10, fill=fill)
        lines = b.split("\n")
        d.text((x + 16, y + 28), lines[0], font=sans(24, bold=True), fill=(255, 255, 255))
        d.text((x + 16, y + 66), lines[1], font=sans(18), fill=(200, 200, 200))
        if i < len(boxes) - 1:
            ax = x + bw + 2
            d.line([ax, y + bh // 2, ax + gap - 4, y + bh // 2], fill=(17, 17, 17), width=3)
            d.polygon([(ax + gap - 4, y + bh // 2 - 7), (ax + gap - 4, y + bh // 2 + 7),
                       (ax + gap + 4, y + bh // 2)], fill=(17, 17, 17))
        x += bw + gap
    d.rounded_rectangle([64, 420, 1216, 520], radius=10, outline=(10, 122, 47), width=3)
    d.text((84, 445), "Identity — every submission is gated on a Binance Agent ID (on-chain registry, BNB Chain).",
           font=sans(20), fill=(17, 17, 17))
    d.text((84, 480), "No Agent ID = no registration, no submission, no payout.",
           font=sans(20), fill=(100, 100, 100))
    d.text((64, 600), "Rule: no runnable PoC means no report.  ·  bountybot-slay-hacks",
           font=mono(20), fill=(100, 100, 100))
    return img


def split_log() -> dict[str, list[str]]:
    lines = LOG.read_text().splitlines()
    beats: dict[str, list[str]] = {"scout": [], "hunt": [], "verify": [], "gate": [], "report": []}
    cur = None
    for line in lines:
        if line.startswith("[scout]"):
            cur = "scout"
        elif line.startswith("[hunt]"):
            cur = "hunt"
        elif line.startswith("[verify]"):
            cur = "verify"
        elif line.startswith("[gate]"):
            cur = "gate"
        elif line.startswith("[report]") or line.startswith("[bountybot] DONE"):
            cur = "report"
        if cur and line.strip():
            beats[cur].append(line)
    return beats


def main() -> int:
    beats = split_log()
    for k, v in beats.items():
        print(f"beat {k}: {len(v)} lines")
    FRAMES.mkdir(exist_ok=True)
    for p in FRAMES.glob("*.png"):
        p.unlink()

    steps: list[tuple[Image.Image, float]] = []  # (image, seconds)

    # Title card — 8s
    steps.append((render_title_card("BOUNTYBOT", [
        "An AI agent that hunts Web3 bug bounties end to end.",
        "Scout → hunt → gate → verify with a runnable PoC → report.",
        "No runnable PoC means no report.",
    ]), 8.0))

    shown: list[str] = []
    cmd = "$ python3 -m bountybot hunt --target targets/demo-vault"
    shown.append(cmd)
    steps.append((render_caption(render_terminal(shown),
                                 "The demo — one command, the whole loop",
                                 "Python 3.12, stdlib only · no API keys · fully offline"), 5.0))

    plan = [
        ("scout", "1 · SCOUT — read the program scope first",
         "In scope, known issues, reward tiers. Out-of-scope is not a finding.", 12.0, "01-scout.png"),
        ("hunt", "2 · HUNT — 10 bug classes scanned, one pattern fires",
         "REENTRANCY (Critical): withdraw() sends ETH before updating state.", 18.0, "02-hunt.png"),
        ("verify", "3 · VERIFY — the PoC must reproduce the impact",
         "forge test 2/2 PASS · vault 100 ETH → 0 · attacker drains 101 ETH.", 16.0, "03-verify.png"),
        ("gate", "4 · GATE — 7 questions, the first wrong answer kills it",
         "Real harm? In scope? Not a duplicate? PoC reproducible? 7/7 PASS.", 18.0, "04-report.png"),
        ("report", "5 · REPORT — one finding, one root cause, exact numbers",
         "Submission-grade draft written in 6.0 seconds, end to end.", 12.0, None),
    ]
    for key, caption, sub, hold, shot in plan:
        for line in beats[key]:
            shown.append(line)
            steps.append((render_caption(render_terminal(shown), caption, sub), 0.45))
        if shot:
            render_caption(render_terminal(shown), caption, sub).save(DEMO / "screenshots" / shot)
            print(f"screenshot {shot}")
        steps.append((render_caption(render_terminal(shown), caption, sub), hold))

    # Field results card — 20s
    steps.append((render_field_card(), 20.0))

    # Architecture diagram screenshot
    render_architecture().save(DEMO / "screenshots" / "05-architecture.png")
    print("screenshot 05-architecture.png")

    # Write frames + concat list (each step held for its duration at 24fps)
    concat = FRAMES / "concat.txt"
    with concat.open("w") as f:
        for i, (img, dur) in enumerate(steps):
            path = FRAMES / f"f{i:03d}.png"
            img.save(path)
            f.write(f"file '{path}'\n")
            f.write(f"duration {dur:.2f}\n")
        f.write(f"file '{FRAMES / f'f{len(steps) - 1:03d}.png'}'\n")
    total = sum(d for _, d in steps)
    print(f"{len(steps)} steps, total {total:.0f}s")

    proc = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "fps=24", "-pix_fmt", "yuv420p", str(OUT),
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        return 1
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
