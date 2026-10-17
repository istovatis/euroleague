#!/usr/bin/env python3
"""Render stat cards (PNG) from a cards.<lang>.json spec using headless Chrome.

Usage: python3 scripts/render_cards.py rounds/E2026/round-06/cards.en.json
Outputs next to the spec: cards/<lang>/ig-1.png ... (1080x1350) and x.png (1600x900).

Card types: hook, score, text, list (see any cards.*.json for the fields).
"""
import html
import os
import shutil
import json
import pathlib
import subprocess
import sys
import tempfile

from brand_mark import centre_disc

ROOT = pathlib.Path(__file__).resolve().parent.parent


def find_chrome():
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for c in (os.environ.get("CHROME"), mac):
        if c and os.path.exists(c):
            return c
    # Cloud (Linux): prefer Playwright's headless_shell. The full Chromium build there
    # crops ~88px off the bottom of --window-size screenshots, clipping the footer.
    pw_dirs = [pathlib.Path("/opt/pw-browsers"), pathlib.Path.home() / ".cache/ms-playwright"]
    for d in pw_dirs:
        hits = sorted(d.glob("chromium_headless_shell-*/chrome-linux*/headless_shell"))
        if hits:
            return str(hits[-1])
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(c):
            return c
    for d in pw_dirs:
        hits = sorted(d.glob("chromium-*/chrome-linux*/chrome"))
        if hits:
            return str(hits[-1])
    sys.exit("No Chrome found: run `npx -y playwright install chromium-headless-shell` or set CHROME=/path/to/chrome")


CHROME = find_chrome()
BRAND = json.loads((ROOT / "brand.json").read_text())
FONTS = (ROOT / "assets" / "fonts").as_uri()

CSS = """
@font-face { font-family: F; font-weight: 500; src: url(%(f)s/FiraSansExtraCondensed-Medium.ttf); }
@font-face { font-family: F; font-weight: 700; src: url(%(f)s/FiraSansExtraCondensed-Bold.ttf); }
@font-face { font-family: F; font-weight: 900; src: url(%(f)s/FiraSansExtraCondensed-Black.ttf); }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: %(w)dpx; height: %(h)dpx; overflow: hidden; }
body { font-family: F, sans-serif; background: %(bg)s; color: %(fg)s; position: relative;
  padding: %(pad)dpx; display: flex; flex-direction: column; }
body::before { content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(circle at 85%% 10%%, %(accent)s22, transparent 45%%),
              repeating-linear-gradient(135deg, #ffffff06 0 2px, transparent 2px 22px); }
.top { display: flex; justify-content: space-between; align-items: center; font-weight: 700;
  font-size: %(small)dpx; letter-spacing: .12em; text-transform: uppercase; color: %(muted)s; position: relative; }
.top b { color: %(fg)s; font-weight: 900; }
.brand { display: inline-flex; align-items: center; gap: .4em; }
.brand svg { width: 1.15em; height: 1.15em; }
.main { flex: 1; display: flex; flex-direction: column; justify-content: center; position: relative; }
.kicker { display: inline-block; align-self: flex-start; background: %(accent)s; color: %(bg)s; font-weight: 900;
  font-size: %(kick)dpx; letter-spacing: .08em; text-transform: uppercase; padding: 6px 16px; margin-bottom: 28px; }
.title { font-weight: 900; font-size: %(title)dpx; line-height: .92; text-transform: uppercase; }
.title em { font-style: normal; color: %(accent)s; }
.sub { font-weight: 700; font-size: %(sub)dpx; color: %(muted)s; margin-top: 28px; text-transform: uppercase; letter-spacing: .04em; }
.body { font-weight: 500; font-size: %(body)dpx; line-height: 1.25; }
.body p + p { margin-top: 28px; }
.body strong { font-weight: 900; color: %(accent)s; }
.score { display: grid; grid-template-columns: 1fr auto; row-gap: 6px; align-items: baseline; }
.score .team { font-weight: 900; font-size: %(team)dpx; text-transform: uppercase; line-height: 1; }
.score .pts { font-weight: 900; font-size: %(pts)dpx; line-height: 1; text-align: right; }
.score .lose { color: %(muted)s; }
.note { margin-top: 24px; font-weight: 700; font-size: %(sub)dpx; color: %(accent)s; text-transform: uppercase; }
.lines { margin-top: 36px; border-top: 3px solid %(accent)s; }
.line { display: flex; justify-content: space-between; align-items: baseline; padding: 16px 0;
  border-bottom: 1px solid #ffffff22; font-size: %(line)dpx; }
.line span:first-child { font-weight: 900; text-transform: uppercase; }
.line span:last-child { font-weight: 700; color: %(muted)s; }
.items { display: flex; flex-direction: column; gap: 34px; }
.item .tag { font-weight: 900; color: %(accent)s; font-size: %(kick)dpx; letter-spacing: .1em; text-transform: uppercase; }
.item .txt { font-weight: 700; font-size: %(item)dpx; line-height: 1.12; margin-top: 4px; }
.foot { display: flex; justify-content: space-between; font-weight: 500; font-size: %(tiny)dpx; color: %(muted)s;
  letter-spacing: .06em; text-transform: uppercase; position: relative; }
"""

SIZES = {
    "ig": dict(w=1080, h=1350, pad=72, small=26, kick=28, title=150, sub=38, body=56, team=72, pts=120,
               line=44, item=50, tiny=22),
    "x": dict(w=1600, h=900, pad=64, small=26, kick=26, title=120, sub=34, body=48, team=64, pts=100,
              line=36, item=44, tiny=22),
}


def rich(s):
    """Escape text, then allow *accent* and **bold** markup."""
    s = html.escape(s).replace("\n", "<br>")
    out, parts = "", s.split("**")
    for i, p in enumerate(parts):
        out += f"<strong>{p}</strong>" if i % 2 else p
    parts = out.split("*")
    return "".join(f"<em>{p}</em>" if i % 2 else p for i, p in enumerate(parts))


def card_html(card):
    t = card["type"]
    k = f'<div class="kicker">{rich(card["kicker"])}</div>' if card.get("kicker") else ""
    if t == "hook":
        inner = f'{k}<div class="title">{rich(card["title"])}</div>' + (
            f'<div class="sub">{rich(card["subtitle"])}</div>' if card.get("subtitle") else "")
    elif t == "score":
        rows = "".join(
            f'<div class="team {"" if s["won"] else "lose"}">{rich(s["team"])}</div>'
            f'<div class="pts {"" if s["won"] else "lose"}">{s["score"]}</div>' for s in card["sides"])
        note = f'<div class="note">{rich(card["note"])}</div>' if card.get("note") else ""
        lines = "".join(f'<div class="line"><span>{rich(a)}</span><span>{rich(b)}</span></div>'
                        for a, b in card.get("lines", []))
        inner = f'{k}<div class="score">{rows}</div>{note}<div class="lines">{lines}</div>'
    elif t == "text":
        inner = k + '<div class="body">' + "".join(f"<p>{rich(p)}</p>" for p in card["paragraphs"]) + "</div>"
    elif t == "list":
        inner = k + '<div class="items">' + "".join(
            f'<div class="item"><div class="tag">{rich(i["tag"])}</div><div class="txt">{rich(i["text"])}</div></div>'
            for i in card["items"]) + "</div>"
    else:
        raise ValueError(f"unknown card type {t}")
    return inner


def page(spec, card, fmt, n, total):
    size = SIZES[fmt]
    css = CSS % dict(size, f=FONTS, **BRAND["colors"])
    page_no = f"{n}/{total}" if total > 1 else ""
    return f"""<!doctype html><html lang="{spec['lang']}"><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="top"><span class="brand">{centre_disc(BRAND['colors']['accent'])}<b>{html.escape(BRAND['name'][spec['lang']])}</b> · {html.escape(spec['round_label'])}</span><span>{page_no}</span></div>
<div class="main">{card_html(card)}</div>
<div class="foot"><span>{html.escape(BRAND['handle'][fmt][spec['lang']])}</span><span>{html.escape(BRAND['disclaimer'][spec['lang']])}</span></div>
</body></html>"""


def shoot(doc, w, h, out):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=3000",
                    f"--window-size={w},{h}", f"--screenshot={out}", pathlib.Path(f.name).as_uri()],
                   check=True, capture_output=True)
    pathlib.Path(f.name).unlink()


def main():
    spec_path = pathlib.Path(sys.argv[1]).resolve()
    spec = json.loads(spec_path.read_text())
    out_dir = spec_path.parent / "cards" / spec["lang"]
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [("ig", c, i + 1, len(spec["ig"]), out_dir / f"ig-{i + 1}.png") for i, c in enumerate(spec["ig"])]
    jobs.append(("x", spec["x"], 1, 1, out_dir / "x.png"))
    for fmt, card, n, total, out in jobs:
        shoot(page(spec, card, fmt, n, total), SIZES[fmt]["w"], SIZES[fmt]["h"], out)
        print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
