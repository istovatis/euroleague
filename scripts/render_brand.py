#!/usr/bin/env python3
"""Render brand assets (ball mark, avatar, wordmarks, X headers) into assets/brand/.

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


def ball(color, size=None, uid="b"):
    """Minimal basketball: a solid disc with the seams cut out (transparent), so it
    sits on any background. Pure geometry, so it is also exported as a real SVG."""
    dim = f' width="{size}" height="{size}"' if size else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"{dim}>
  <mask id="{uid}"><rect width="100" height="100" fill="#fff"/>
    <g fill="none" stroke="#000" stroke-width="5" stroke-linecap="round">
      <line x1="50" y1="0" x2="50" y2="100"/><line x1="0" y1="50" x2="100" y2="50"/>
      <path d="M20,15 C38,32 38,68 20,85"/><path d="M80,15 C62,32 62,68 80,85"/>
    </g></mask>
  <circle cx="50" cy="50" r="46" fill="{color}" mask="url(#{uid})"/>
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


def lockup(lang, font_px, color, ball_color):
    # Ball ~ cap height plus a little, so it reads as an equal partner to the name.
    b = round(font_px * 0.78)
    return f"""<div class="lockup" style="gap:{round(font_px * 0.16)}px">{ball(ball_color, b, "w")}
<div class="word" style="font-size:{font_px}px; color:{color}">{LANGS[lang]['name']}</div></div>"""


def avatar():
    # One avatar for every language. The ball fills ~60% so the circle crop never touches it.
    return CSS % dict(w=1080, h=1080), ball(C["accent"], 640), 1080, 1080, True


def wordmark(lang, mode):
    """mode: "ink" (on the dark brand background), "light-text" (transparent, for dark
    backgrounds) or "mono" (transparent, all ink: for white or light backgrounds)."""
    text, ballc = (C["bg"], C["bg"]) if mode == "mono" else (C["fg"], C["accent"])
    return CSS % dict(w=2000, h=640), lockup(lang, 340, text, ballc), 2000, 640, mode == "ink"


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
    for old in OUT.glob("avatar-*.png"):  # per-language letter avatars are replaced by the ball
        old.unlink()
    (OUT / "ball.svg").write_text(ball(C["accent"]))
    (OUT / "ball-mono.svg").write_text(ball(C["bg"]))
    print("assets/brand/ball.svg\nassets/brand/ball-mono.svg")
    shoot(*avatar(), OUT / "avatar.png")
    for lang in LANGS:
        shoot(*wordmark(lang, "ink"), OUT / f"wordmark-{lang}.png", lang)
        shoot(*wordmark(lang, "light-text"), OUT / f"wordmark-{lang}-transparent.png", lang)
        shoot(*wordmark(lang, "mono"), OUT / f"wordmark-{lang}-mono.png", lang)
        shoot(*header(lang), OUT / f"header-x-{lang}.png", lang)


if __name__ == "__main__":
    main()
