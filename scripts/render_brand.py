#!/usr/bin/env python3
"""Render brand assets (court mark, avatar, wordmarks, X headers) into assets/brand/.

Usage: python3 scripts/render_brand.py
Uses the palette in brand.json and the same headless Chrome as render_cards.py.
"""
import pathlib
import subprocess
import tempfile

from render_cards import BRAND, CHROME, FONTS, ROOT

C = BRAND["colors"]
OUT = ROOT / "assets" / "brand"

LANGS = {
    "en": {"name": "PARQUET", "tagline": "One story per round"},
    "el": {"name": "ΠΑΡΚΕ", "tagline": "Μία ιστορία κάθε αγωνιστική"},
}


def court(color, size=None, stroke=4):
    """Minimal half court, top view, in real FIBA proportions (15 x 14 m): sidelines,
    halfway line with the centre circle, the paint with the free-throw circle and the
    three-point line. Pure geometry, so it is also exported as a real SVG."""
    s, x0, top = 5.2, 11, 11                       # metres -> viewBox units
    base, cx = top + 14 * s, 50
    basket = base - 1.575 * s
    key_w, key_top, r_ft, r_3 = 4.9 * s, base - 5.8 * s, 1.8 * s, 6.75 * s
    c1, c2 = x0 + 0.9 * s, x0 + 15 * s - 0.9 * s  # three-point corner lines
    c_y = basket - ((r_3 ** 2 - (cx - c1) ** 2) ** 0.5)
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    pad = stroke / 2
    vb = f"{f(x0 - pad)} {f(top - pad)} {f(15 * s + stroke)} {f(14 * s + stroke)}"
    dim = f' width="{size}" height="{f(size * 14 / 15)}"' if size else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"{dim}>
  <g fill="none" stroke="{color}" stroke-width="{stroke}">
    <rect x="{x0}" y="{top}" width="{f(15 * s)}" height="{f(14 * s)}"/>
    <path d="M{f(cx - r_ft)},{top} A{f(r_ft)},{f(r_ft)} 0 0 0 {f(cx + r_ft)},{top}"/>
    <rect x="{f(cx - key_w / 2)}" y="{f(key_top)}" width="{f(key_w)}" height="{f(base - key_top)}"/>
    <path d="M{f(cx - r_ft)},{f(key_top)} A{f(r_ft)},{f(r_ft)} 0 0 1 {f(cx + r_ft)},{f(key_top)}"/>
    <path d="M{f(c1)},{f(base)} V{f(c_y)} A{f(r_3)},{f(r_3)} 0 0 1 {f(c2)},{f(c_y)} V{f(base)}"/>
  </g>
</svg>"""


CSS = f"""
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: %(w)dpx; height: %(h)dpx; overflow: hidden; }}
body {{ font-family: F, sans-serif; color: {C['fg']}; display: flex; align-items: center; justify-content: center; }}
.ink {{ background: {C['bg']}; position: relative; }}
.ink::before {{ content: ""; position: absolute; inset: 0;
  background: radial-gradient(circle at 80%% 15%%, {C['accent']}26, transparent 50%%),
              repeating-linear-gradient(135deg, #ffffff08 0 3px, transparent 3px 34px); }}
.lockup {{ display: flex; align-items: center; position: relative; }}
.word {{ font-weight: 900; letter-spacing: -0.01em; line-height: 1; }}
svg {{ display: block; position: relative; }}
"""


def lockup(lang, font_px, color, mark_color):
    # Court mark ~ cap height wide, with a heavier stroke so it holds up next to Black type.
    return f"""<div class="lockup" style="gap:{round(font_px * 0.18)}px">{court(mark_color, round(font_px * 0.8), 6)}
<div class="word" style="font-size:{font_px}px; color:{color}">{LANGS[lang]['name']}</div></div>"""


def avatar():
    # One avatar for every language. The court's corners stay well inside the circle crop.
    return CSS % dict(w=1080, h=1080), court(C["accent"], 600), 1080, 1080, True


def wordmark(lang, mode):
    """mode: "ink" (on the dark brand background), "light-text" (transparent, for dark
    backgrounds) or "mono" (transparent, all ink: for white or light backgrounds)."""
    text, markc = (C["bg"], C["bg"]) if mode == "mono" else (C["fg"], C["accent"])
    return CSS % dict(w=2000, h=640), lockup(lang, 340, text, markc), 2000, 640, mode == "ink"


def header(lang):
    # X overlays the avatar bottom-left, so the lockup sits right of centre.
    body = f"""<div style="position:absolute; right:110px; top:50%; transform:translateY(-50%);
  display:flex; flex-direction:column; align-items:flex-end; gap:20px">
{lockup(lang, 180, C['fg'], C['accent'])}
<span style="font-weight:700; font-size:40px; letter-spacing:.08em; text-transform:uppercase; color:{C['muted']}">{LANGS[lang]['tagline']}</span>
</div>"""
    return CSS % dict(w=1500, h=500), body, 1500, 500, True


def shoot(css, body, w, h, on_ink, out, lang="en"):
    doc = f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}</style></head>' \
          f'<body class="{"ink" if on_ink else ""}">{body}</body></html>'
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--allow-file-access-from-files", "--virtual-time-budget=3000",
           f"--window-size={w},{h}", f"--screenshot={out}", pathlib.Path(f.name).as_uri()]
    if not on_ink:
        cmd.insert(1, "--default-background-color=00000000")
    subprocess.run(cmd, check=True, capture_output=True)
    pathlib.Path(f.name).unlink()
    print(out.relative_to(ROOT))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "court.svg").write_text(court(C["accent"]))
    (OUT / "court-mono.svg").write_text(court(C["bg"]))
    print("assets/brand/court.svg\nassets/brand/court-mono.svg")
    shoot(*avatar(), OUT / "avatar.png")
    for lang in LANGS:
        shoot(*wordmark(lang, "ink"), OUT / f"wordmark-{lang}.png", lang)
        shoot(*wordmark(lang, "light-text"), OUT / f"wordmark-{lang}-transparent.png", lang)
        shoot(*wordmark(lang, "mono"), OUT / f"wordmark-{lang}-mono.png", lang)
        shoot(*header(lang), OUT / f"header-x-{lang}.png", lang)


if __name__ == "__main__":
    main()
