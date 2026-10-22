#!/usr/bin/env python3
"""Render stat cards (PNG) from a cards.<lang>.json spec using headless Chrome.

Usage: python3 scripts/render_cards.py rounds/E2026/round-06/cards.en.json
Outputs next to the spec: cards/<lang>/ig-1.png ... (1080x1350), x.png (1600x900) and, when the spec
has a "story" card, story.png (1080x1920, an Instagram Story). "ig" may be empty.

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
CLUBS = json.loads((ROOT / "assets" / "clubs.json").read_text())
CREST_CACHE = ROOT / ".cache" / "crests"  # gitignored: crests are club trademarks, never committed
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
  background: radial-gradient(circle at 85%% 10%%, %(accent)s22, transparent 45%%); }
.top { display: flex; justify-content: space-between; align-items: center; font-weight: 700;
  font-size: %(small)dpx; letter-spacing: .12em; text-transform: uppercase; color: %(muted)s; position: relative; }
.top b { color: %(fg)s; font-weight: 900; }
.brand { display: inline-flex; align-items: center; gap: .4em; }
.brand svg { width: 1.15em; height: 1.15em; }
.main { flex: 1; display: flex; flex-direction: column; justify-content: center; position: relative; }
.badges { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 26px; }
.badge { display: inline-flex; align-items: center; gap: 12px; padding: 10px 22px 10px 16px; border-radius: 999px;
  font-weight: 900; font-size: %(kick)dpx; letter-spacing: .06em; text-transform: uppercase;
  box-shadow: 0 0 0 2px #ffffff40, 0 2px 10px #0006; }
.badge i { width: .62em; height: .62em; border-radius: 50%%; display: block; box-shadow: 0 0 0 2px #0002; }
.crests { gap: 18px; margin-bottom: 28px; }
.crest { width: 118px; height: 118px; border-radius: 50%%; background: #fff; display: flex; align-items: center;
  justify-content: center; box-shadow: 0 2px 12px #0008; }
.crest img { width: 84px; height: 84px; object-fit: contain; }
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
.photo { position: absolute; inset: 0; background-size: cover; }
.photo::after { content: ""; position: absolute; inset: 0;
  background: linear-gradient(to bottom, %(bg)sd9 0%%, %(bg)s00 16%%, %(bg)s00 34%%, %(bg)se0 58%%, %(bg)s 72%%); }
body.has-photo::before { display: none; }
body.has-photo .main { justify-content: flex-end; padding-bottom: 28px; }
.credit { font-size: %(credit)dpx; letter-spacing: .02em; text-transform: none; opacity: .8; }
.foot { display: flex; justify-content: space-between; font-weight: 500; font-size: %(tiny)dpx; color: %(muted)s;
  letter-spacing: .06em; text-transform: uppercase; position: relative; }
"""

SIZES = {
    "ig": dict(w=1080, h=1350, pad=72, small=26, kick=28, title=150, sub=38, body=56, team=72, pts=120,
               line=44, item=50, tiny=22, credit=17),
    # Instagram Story: the top and bottom ~250px sit under Instagram's own UI, so the padding is taller.
    "story": dict(w=1080, h=1920, pad=72, pad_y=250, small=28, kick=34, title=160, sub=40, body=56, team=84, pts=150,
                  line=44, item=50, tiny=24, credit=17),
    "x": dict(w=1600, h=900, pad=64, small=26, kick=26, title=120, sub=34, body=48, team=64, pts=100,
              line=36, item=44, tiny=22, credit=17),
}


def rich(s):
    """Escape text, then allow *accent* and **bold** markup."""
    s = html.escape(s).replace("\n", "<br>")
    out, parts = "", s.split("**")
    for i, p in enumerate(parts):
        out += f"<strong>{p}</strong>" if i % 2 else p
    parts = out.split("*")
    return "".join(f"<em>{p}</em>" if i % 2 else p for i, p in enumerate(parts))


def crest_file(code):
    """Official club crest from the EuroLeague API, cached locally. None if unavailable."""
    import urllib.request
    f = CREST_CACHE / f"{code}.png"
    if f.exists():
        return f
    try:
        req = urllib.request.Request("https://api-live.euroleague.net/v2/competitions/E/seasons/E2026/games",
                                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            games = json.load(r)["data"]
        urls = {g[s]["club"]["code"]: g[s]["club"]["images"]["crest"] for g in games for s in ("local", "road")}
        req = urllib.request.Request(urls[code], headers={"User-Agent": "Mozilla/5.0"})
        CREST_CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=30) as r:
            f.write_bytes(r.read())
        return f
    except Exception as e:  # network blocked, unknown code, ...
        print(f"warning: no crest for {code} ({e}); using the styled badge", file=sys.stderr)
        return None


def club_marks_html(codes, lang):
    """Crests or styled badges for the given clubs, per brand.json "club_marks"."""
    if BRAND.get("club_marks") == "crests":
        files = [crest_file(c) for c in codes]
        if all(files):
            items = "".join(f'<span class="crest"><img src="{f.as_uri()}"></span>' for f in files)
            return f'<div class="badges crests">{items}</div>'
    return badges_html(codes, lang)


def badges_html(codes, lang):
    """Club badges in our own style (assets/clubs.json): never crests, which are trademarks."""
    out = []
    for code in codes:
        c = CLUBS[code]
        out.append(f'<span class="badge" style="background:{c["bg"]};color:{c["fg"]}">'
                   f'<i style="background:{c["dot"]}"></i>{html.escape(c.get(lang) or c["en"])}</span>')
    return f'<div class="badges">{"".join(out)}</div>'


def card_html(card, lang="en"):
    t = card["type"]
    k = f'<div class="kicker">{rich(card["kicker"])}</div>' if card.get("kicker") else ""
    if t == "hook":
        inner = (club_marks_html(card["badges"], lang) if card.get("badges") else "") + f'{k}<div class="title">{rich(card["title"])}</div>' + (
            f'<div class="sub">{rich(card["subtitle"])}</div>' if card.get("subtitle") else "")
    elif t == "score":
        rows = "".join(
            f'<div class="team {"" if s["won"] else "lose"}">{rich(s["team"])}</div>'
            f'<div class="pts {"" if s["won"] else "lose"}">{s["score"]}</div>' for s in card["sides"])
        note = f'<div class="note">{rich(card["note"])}</div>' if card.get("note") else ""
        lines = "".join(f'<div class="line"><span>{rich(a)}</span><span>{rich(b)}</span></div>'
                        for a, b in card.get("lines", []))
        marks = club_marks_html(card["badges"], lang) if card.get("badges") else ""
        inner = f'{marks}{k}<div class="score">{rows}</div>{note}<div class="lines">{lines}</div>'
    elif t == "text":
        inner = k + '<div class="body">' + "".join(f"<p>{rich(p)}</p>" for p in card["paragraphs"]) + "</div>"
    elif t == "list":
        inner = k + '<div class="items">' + "".join(
            f'<div class="item"><div class="tag">{rich(i["tag"])}</div><div class="txt">{rich(i["text"])}</div></div>'
            for i in card["items"]) + "</div>"
    else:
        raise ValueError(f"unknown card type {t}")
    return inner


def page(spec, card, fmt, n, total, photo=None):
    """photo: {"uri", "credit", "focus"} puts a full-bleed photo behind this card (Instagram slide 1)."""
    size = SIZES[fmt]
    css = CSS % dict(size, f=FONTS, **BRAND["colors"])
    if size.get("pad_y"):
        css += f"body {{ padding-top: {size['pad_y']}px; padding-bottom: {size['pad_y']}px; }}"
    page_no = f"{n}/{total}" if total > 1 else ""
    bg = credit = ""
    if photo:
        bg = f'<div class="photo" style="background-image:url({photo["uri"]}); background-position:{photo["focus"]}"></div>'
        credit = f'<span class="credit">{html.escape(photo["credit"])}</span>'
    return f"""<!doctype html><html lang="{spec['lang']}"><head><meta charset="utf-8"><style>{css}</style></head><body class="{"has-photo" if photo else ""}">{bg}
<div class="top"><span class="brand">{centre_disc(BRAND['colors']['accent'])}<b>{html.escape(BRAND['name'][spec['lang']])}</b> · {html.escape(spec['round_label'])}</span><span>{page_no}</span></div>
<div class="main">{card_html(card, spec["lang"])}</div>
<div class="foot"><span>{html.escape(BRAND['handle']["ig" if fmt == "story" else fmt][spec['lang']])}</span>{credit}</div>
<script>
// Long words (e.g. Greek) must never run off the card: shrink a headline until it fits its box.
for (const el of document.querySelectorAll('.title, .team')) {{
  let fs = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollWidth > el.clientWidth + 1 && fs > 40) {{ fs -= 4; el.style.fontSize = fs + 'px'; }}
}}
</script>
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
    x_only = "--x-only" in sys.argv[2:]  # re-render just the X cards (e.g. of a post already on Instagram)
    jobs = [] if x_only else [("ig", c, i + 1, len(spec["ig"]), out_dir / f"ig-{i + 1}.png") for i, c in enumerate(spec["ig"])]
    if spec["lang"] in BRAND["handle"]["x"] and "x" in spec:  # some languages are Instagram-only
        # "x" is one card, or a list of up to 4 (X's image limit): x.png, x-2.png, ...
        xs = spec["x"] if isinstance(spec["x"], list) else [spec["x"]]
        if len(xs) > 4:
            sys.exit("X allows at most 4 images per post")
        jobs += [("x", c, i + 1, len(xs), out_dir / ("x.png" if i == 0 else f"x-{i + 1}.png")) for i, c in enumerate(xs)]
    if "story" in spec and not x_only:
        jobs.append(("story", spec["story"], 1, 1, out_dir / "story.png"))
    # Photos come from scripts/commons_photo.py: <name>.jpg plus <name>.json (credit, optional focus).
    # A card names its photo with "photo": "<name>"; otherwise a story's photo.jpg goes behind slide 1.
    def load_photo(name):
        jpg, meta = spec_path.parent / f"{name}.jpg", spec_path.parent / f"{name}.json"
        if not jpg.exists():
            sys.exit(f"Missing photo {jpg}")
        m = json.loads(meta.read_text())
        return {"uri": jpg.as_uri(), "credit": m["credit"], "focus": m.get("focus", "50% 20%")}

    for fmt, card, n, total, out in jobs:
        if card.get("photo"):
            slide_photo = load_photo(card["photo"])
        elif fmt == "ig" and n == 1 and (spec_path.parent / "photo.jpg").exists():
            slide_photo = load_photo("photo")
        else:
            slide_photo = None
        shoot(page(spec, card, fmt, n, total, slide_photo), SIZES[fmt]["w"], SIZES[fmt]["h"], out)
        print(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out)


if __name__ == "__main__":
    main()
