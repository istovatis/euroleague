#!/usr/bin/env python3
"""Render brand assets (avatars, wordmarks, X headers) into assets/brand/.

Usage: python3 scripts/render_brand.py
Uses the palette in brand.json and the same headless Chrome as render_cards.py.
"""
import json
import pathlib
import subprocess
import tempfile

from render_cards import BRAND, CHROME, FONTS, ROOT

C = BRAND["colors"]
OUT = ROOT / "assets" / "brand"

# name: the wordmark split as (before, accent letter, after); mark: avatar letter;
# nudge: optical centring of the mark in px (P's heavy stem makes it look left of centre).
LANGS = {
    "en": {"name": ("PAR", "Q", "UET"), "mark": "P", "nudge": 36, "tagline": "One story per round"},
    "el": {"name": ("ΠΑΡ", "Κ", "Ε"), "mark": "Π", "nudge": 0, "tagline": "Μία ιστορία κάθε αγωνιστική"},
}

BASE = f"""
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: %(w)dpx; height: %(h)dpx; overflow: hidden; }}
body {{ font-family: F, sans-serif; color: {C['fg']}; display: flex; align-items: center; justify-content: center; }}
.ink {{ background: {C['bg']}; position: relative; }}
.ink::before {{ content: ""; position: absolute; inset: 0;
  background: radial-gradient(circle at 80%% 15%%, {C['accent']}26, transparent 50%%),
              repeating-linear-gradient(135deg, #ffffff08 0 3px, transparent 3px 34px); }}
.acc {{ color: {C['accent']}; }}
.word {{ font-weight: 900; letter-spacing: -0.01em; line-height: 1; position: relative; }}
.planks {{ display: flex; gap: %(gap)dpx; position: relative; }}
.planks i {{ display: block; width: %(pw)dpx; height: %(ph)dpx; background: {C['accent']}; transform: skewX(-45deg); }}
"""


def planks(n, pw, ph, gap):
    return f'<div class="planks" style="--n:{n}">' + "<i></i>" * n + "</div>"


def avatar(lang):
    m = LANGS[lang]["mark"]
    css = BASE % dict(w=1080, h=1080, gap=18, pw=56, ph=26)
    # Glyph sits inside the centre ~65% so the Instagram/X circle crop never clips it.
    body = f"""<div class="word acc" style="font-size:760px; margin-top:-40px; margin-left:{LANGS[lang]['nudge']}px">{m}</div>
<div style="position:absolute; bottom:250px; left:50%; transform:translateX(-50%)">{planks(4, 56, 26, 18)}</div>"""
    return css, body, 1080, 1080, True


def wordmark(lang, mode):
    """mode: "ink" (on the dark brand background), "light-text" (transparent, for dark
    backgrounds) or "mono" (transparent, all ink: for white or light backgrounds)."""
    a, q, b = LANGS[lang]["name"]
    css = BASE % dict(w=2000, h=640, gap=28, pw=90, ph=40)
    if mode == "mono":
        css += f".word, .acc {{ color: {C['bg']}; }} .planks i {{ background: {C['bg']}; }}"
    body = f"""<div style="display:flex; flex-direction:column; align-items:flex-start; gap:40px">
<div class="word" style="font-size:380px">{a}<span class="acc">{q}</span>{b}</div>
{planks(5, 90, 40, 28)}</div>"""
    return css, body, 2000, 640, mode == "ink"


def header(lang):
    a, q, b = LANGS[lang]["name"]
    css = BASE % dict(w=1500, h=500, gap=16, pw=50, ph=22)
    # X overlays the avatar bottom-left, so the wordmark sits right of centre.
    body = f"""<div style="position:absolute; right:110px; top:50%; transform:translateY(-50%);
  display:flex; flex-direction:column; align-items:flex-end; gap:22px">
<div class="word" style="font-size:200px">{a}<span class="acc">{q}</span>{b}</div>
<div style="display:flex; align-items:center; gap:24px">
<span style="font-weight:700; font-size:40px; letter-spacing:.08em; text-transform:uppercase; color:{C['muted']}">{LANGS[lang]['tagline']}</span>
{planks(3, 50, 22, 16)}</div></div>"""
    return css, body, 1500, 500, True


def shoot(css, body, w, h, on_ink, out, lang):
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
    for lang in LANGS:
        shoot(*avatar(lang), OUT / f"avatar-{lang}.png", lang)
        shoot(*wordmark(lang, "ink"), OUT / f"wordmark-{lang}.png", lang)
        shoot(*wordmark(lang, "light-text"), OUT / f"wordmark-{lang}-transparent.png", lang)
        shoot(*wordmark(lang, "mono"), OUT / f"wordmark-{lang}-mono.png", lang)
        shoot(*header(lang), OUT / f"header-x-{lang}.png", lang)


if __name__ == "__main__":
    main()
