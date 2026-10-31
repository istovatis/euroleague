#!/usr/bin/env python3
"""Lineup of the week: one page with the round's five best players, PG, SG, SF, PF and C. Names and photos only.

  python3 scripts/lineup.py pick [--round N]     # the latest fully played round -> lineups/<season>/round-NN/lineup.json
  python3 scripts/lineup.py render <folder>      # cards/en/ig-1.png, cards/el/ig-1.png (1080x1350) and cards/en/x.png
  python3 scripts/render_reel.py <folder> <lang> # cards/<lang>/reel.mp4: the players land one by one, PG to C (reel_document)

pick: the round's top PIR among guards (2), forwards (2) and centers (1); the API only knows Guard / Forward / Center,
so the guard with more assists is the PG and the forward with more rebounds the PF. PIR picks them but no number is
shown: the post is names and faces.

Photos: <folder>/photo-<player code>.jpg + .json from commons_photo.py (--get <folder> "File:..." --name
photo-<code>), only when the photo shows the player in his CURRENT club's jersey. Without one, the tile shows our
own drawing of a vest in the club's colours with his name and number (never someone else's photo). Photos are used
only if all five have one; otherwise every tile shows the drawing, so the card stays consistent. In its JSON, "focus" (CSS
background-position) and "zoom" (e.g. 220: the photo's width as % of the tile, for full-length shots) frame the face. Credits go under each photo
and into the caption.
"""
import argparse
import html
import json
import pathlib
import re
import sys

from brand_mark import centre_disc
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS, ROOT, crest_file, shoot
from round_digest import get

SLOTS = ["PG", "SG", "SF", "PF", "C"]
TITLE = {"en": ("Lineup", "of the week"), "el": ("Η πεντάδα", "της αγωνιστικής")}
ROUND = {"en": "Round {n}", "el": "{n}η αγωνιστική"}


def display_name(person):
    """'MARCUS CARR' -> ('Marcus', 'Carr'); 'DE COLO, NANDO' handled via the 'SURNAME, FIRST' name field."""
    last, _, first = person["name"].partition(",")
    fix = lambda t: re.sub(r"\bMc(\w)", lambda m: "Mc" + m.group(1).upper(), t.strip().title())
    return fix(first), fix(last)


def pick(season, rnd):
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    if rnd is None:
        played = {}
        for g in games:
            played.setdefault(g["round"], []).append(g["played"])
        rnd = max(r for r, p in played.items() if all(p))
    rgames = [g for g in games if g["round"] == rnd]
    if not all(g["played"] for g in rgames):
        sys.exit(f"Round {rnd} isn't fully played yet")
    folder = ROOT / "lineups" / season / f"round-{rnd:02d}"
    if (folder / "lineup.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
        return folder
    pool = []
    for g in rgames:
        box = get(f"/v2/competitions/E/seasons/{season}/games/{g['gameCode']}/stats")
        for side in ("local", "road"):
            won = g[side]["score"] > g["road" if side == "local" else "local"]["score"]
            for p in box[side]["players"]:
                s, pl = p["stats"], p["player"]
                if not s.get("timePlayed"):
                    continue
                first, last = display_name(pl["person"])
                pool.append({"code": pl["person"]["code"], "first": first, "last": last, "club": pl["club"]["code"],
                             "dorsal": pl.get("dorsal") or s.get("dorsal"),
                             "position": pl.get("positionName"), "pir": s["valuation"], "pts": s["points"],
                             "ast": s["assistances"], "reb": s["totalRebounds"], "won": won, "game": g["gameCode"]})
    best = lambda pos, n: sorted([p for p in pool if p["position"] == pos], key=lambda p: (-p["pir"], -p["pts"]))[:n]
    guards, forwards, center = best("Guard", 2), best("Forward", 2), best("Center", 1)
    if len(guards) < 2 or len(forwards) < 2 or not center:
        sys.exit("Not enough players with a position in the box scores")
    guards.sort(key=lambda p: -p["ast"])       # PG = more assists
    forwards.sort(key=lambda p: p["reb"])      # SF first, PF = more rebounds
    five = guards + forwards + center
    for slot, p in zip(SLOTS, five):
        p["slot"] = slot
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "lineup.json").write_text(json.dumps({"season": season, "round": rnd, "players": five},
                                                   indent=2, ensure_ascii=False) + "\n")
    print(folder.relative_to(ROOT))
    for p in five:
        print(f"  {p['slot']:<2} {p['first']} {p['last']} ({p['club']}, {p['position']}, PIR {p['pir']})")
    return folder


def mark(club, size):
    """The club's crest on a white disc, or our styled badge (club colours + short name) if there's no crest."""
    f = crest_file(club) if BRAND.get("club_marks") == "crests" else None
    if f:
        return f'<div class="mark" style="width:{size}px;height:{size}px"><img src="{f.as_uri()}"></div>'
    c = CLUBS[club]
    return (f'<div class="mark" style="width:{size}px;height:{size}px;background:{c["bg"]};color:{c["fg"]};'
            f'box-shadow:inset 0 0 0 {size // 18}px {c["dot"]}"><span>{html.escape(c["en"][:3].upper())}</span></div>')


def jersey(p, size):
    """Our own drawing when there's no usable photo: a vest in the club's colours with the player's name and number."""
    c = CLUBS[p["club"]]
    num, name = html.escape(str(p.get("dorsal") or "")), html.escape(p["last"].upper())
    fs = 18 if len(name) <= 9 else max(11, 18 * 9 // len(name))
    return f"""<svg viewBox="0 0 200 220" width="{size}" height="{size * 1.1:.0f}" style="filter:drop-shadow(0 10px 18px #000a)">
<path d="M62 12 Q100 46 138 12 L162 20 Q164 62 186 78 L186 208 Q100 220 14 208 L14 78 Q36 62 38 20 Z" fill="{c['bg']}"/>
<path d="M62 12 Q100 46 138 12 M162 20 Q164 62 186 78 M38 20 Q36 62 14 78" fill="none" stroke="{c['dot']}" stroke-width="7" stroke-linecap="round"/>
<text x="100" y="92" text-anchor="middle" font-family="F" font-weight="900" font-size="{fs}" letter-spacing="1" fill="{c['fg']}">{name}</text>
<text x="100" y="178" text-anchor="middle" font-family="F" font-weight="900" font-size="84" fill="{c['fg']}">{num}</text></svg>"""


def all_photos(folder, data):
    """Photos are used only when every player has one (the owner's rule): a mixed card looks inconsistent."""
    return all((folder / f"photo-{p['code']}.jpg").exists() for p in data["players"])


def tile(folder, p, lang, w, h, photos=True):
    photo = folder / f"photo-{p['code']}.jpg"
    club = CLUBS[p["club"]].get(lang) or CLUBS[p["club"]]["en"]
    if photos and photo.exists():
        meta = json.loads((folder / f"photo-{p['code']}.json").read_text())
        face = (f'<div class="face" style="background-image:url({photo.as_uri()});'
                f'background-position:{meta.get("focus", "50% 20%")};'
                f'{"background-size:" + str(meta["zoom"]) + "% auto;" if meta.get("zoom") else ""}">{mark(p["club"], 64)}</div>'
                f'<div class="credit">{html.escape(meta["credit"])}</div>')
    else:
        face = (f'<div class="face none">{jersey(p, round(w * .58)) if p.get("dorsal") else mark(p["club"], round(w * .5))}'
                f'{mark(p["club"], 64) if p.get("dorsal") else ""}</div><div class="credit"></div>')
    return (f'<div class="tile" style="width:{w}px"><div style="height:{h}px;position:relative">{face}</div>'
            f'<div class="plate"><b>{p["slot"]}</b><div class="first">{html.escape(p["first"])}</div>'
            f'<div class="last">{html.escape(p["last"])}</div><div class="club">{html.escape(club)}</div></div></div>')


def court(w, h, cx, base_y, scale):
    """Half court in brand lime, baseline at base_y: paint, free-throw circle, three-point arc, hoop."""
    s = scale
    a = BRAND["colors"]["accent"]
    return f"""<svg width="{w}" height="{h}" style="position:absolute;inset:0"><g fill="none" stroke="{a}" stroke-opacity=".32" stroke-width="5">
<rect x="{cx - 245 * s}" y="{base_y - 580 * s}" width="{490 * s}" height="{580 * s}"/>
<circle cx="{cx}" cy="{base_y - 580 * s}" r="{180 * s}"/>
<path d="M{cx - 660 * s} {base_y} V{base_y - 300 * s} A{675 * s} {675 * s} 0 0 1 {cx + 660 * s} {base_y - 300 * s} V{base_y}"/>
<circle cx="{cx}" cy="{base_y - 157 * s}" r="{23 * s}"/><line x1="{cx - 90 * s}" y1="{base_y - 120 * s}" x2="{cx + 90 * s}" y2="{base_y - 120 * s}"/>
</g></svg>"""


def page(folder, data, lang, fmt):
    C = BRAND["colors"]
    w, h = {"ig": (1080, 1350), "reel": (1080, 1920), "x": (1600, 900)}[fmt]
    players = {p["slot"]: p for p in data["players"]}
    t1, t2 = TITLE[lang]
    if fmt == "ig":   # two rows: the backcourt and wing (SG, PG, SF), then the bigs (PF, C) nearer the basket
        tw, th = 290, 270
        spots = {"SG": (200, 330), "PG": (540, 330), "SF": (880, 330), "PF": (360, 805), "C": (720, 805)}
        floor = court(w, h, 540, 1350, 1.0)
        title_css = "left:72px; top:126px; font-size:88px"
    elif fmt == "reel":  # the same two rows at Reel size, a little larger
        tw, th = 300, 290
        spots = {"SG": (195, 520), "PG": (540, 520), "SF": (885, 520), "PF": (365, 1110), "C": (715, 1110)}
        floor = court(w, h, 540, 1920, 1.15)
        title_css = "left:72px; top:190px; font-size:108px"
    else:             # one row
        tw, th = 270, 300
        spots = {s: (180 + i * 310, 300) for i, s in enumerate(SLOTS)}
        floor = court(w, h, 800, 960, .75)
        title_css = "left:64px; top:118px; font-size:84px"
    photos = all_photos(folder, data)
    tiles = "".join(f'<div class="spot" data-slot="{s}" style="position:absolute;left:{x - tw // 2}px;top:{y}px">{tile(folder, players[s], lang, tw, th, photos)}</div>'
                    for s, (x, y) in spots.items())
    css = f"""
@font-face {{ font-family: F; font-weight: 500; src: url({FONTS}/FiraSansExtraCondensed-Medium.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{w}px; height:{h}px; overflow:hidden; }}
body {{ font-family:F, sans-serif; color:{C['fg']}; background:{C['bg']}; position:relative; }}
.shade {{ position:absolute; inset:0; background: radial-gradient(ellipse at 50% 45%, {C['bg']}55 0%, {C['bg']}AA 70%, {C['bg']}EE 100%); }}
.top {{ position:absolute; left:{64 if fmt == 'x' else 72}px; right:{64 if fmt == 'x' else 72}px; top:{50 if fmt == 'x' else 60 if fmt == 'ig' else 110}px;
  display:flex; justify-content:space-between; font-weight:700; font-size:26px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.title {{ position:absolute; {title_css}; font-weight:900; line-height:.9; text-transform:uppercase; }}
.title em {{ font-style:normal; color:{C['accent']}; }}
.face {{ position:absolute; inset:0; border-radius:22px; background-size:cover; background-color:#1b222c;
  box-shadow:0 0 0 4px {C['accent']}, 0 14px 30px #000a; overflow:hidden; }}
.face.none {{ display:flex; align-items:center; justify-content:center;
  background:linear-gradient(160deg, #222b37, #12171f); }}
.face .mark {{ position:absolute; right:10px; bottom:10px; }}
.face.none > .mark:only-child {{ position:static; }}
.mark {{ border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.face.none .mark span {{ font-size:34px; }}
.credit {{ position:absolute; left:0; right:0; bottom:-22px; font-size:12px; color:{C['muted']}; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.plate {{ margin-top:30px; text-align:center; }}
.plate b {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:24px; letter-spacing:.08em; padding:2px 12px; }}
.first {{ margin-top:8px; font-weight:700; font-size:24px; color:{C['muted']}; text-transform:uppercase; letter-spacing:.04em; line-height:1; }}
.last {{ font-weight:900; font-size:44px; text-transform:uppercase; line-height:1; white-space:nowrap; }}
.club {{ margin-top:4px; font-weight:700; font-size:20px; color:{C['muted']}; text-transform:uppercase; letter-spacing:.06em; }}
.foot {{ position:absolute; left:{64 if fmt == 'x' else 72}px; bottom:{36 if fmt == 'x' else 44}px; font-weight:500; font-size:22px;
  letter-spacing:.06em; text-transform:uppercase; color:{C['muted']}; }}
"""
    body = f"""<div class="stage" style="position:absolute;inset:0">{parquet(w, h)}{floor}<div class="shade"></div>
<div class="top"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b> · {ROUND[lang].format(n=data['round'])}</span></div>
<div class="title">{html.escape(t1)}<br><em>{html.escape(t2)}</em></div>
{tiles}</div>
<script>for (const el of document.querySelectorAll('.last')) {{ let fs = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollWidth > el.parentElement.clientWidth + 1 && fs > 20) {{ fs -= 2; el.style.fontSize = fs + 'px'; }} }}</script>"""
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>', w, h


def reel_document(folder, lang):
    """The Reel (render_reel.py records it): court and title on screen from the first frame, then the players slam
    down one by one, PG to C (shake, flash, shockwave, sparks), then the brand outro. Returns (html, seconds)."""
    import render_reel
    data = json.loads((folder / "lineup.json").read_text())
    doc, _, _ = page(folder, data, lang, "reel")
    first, step, hold = 0.4, 1.0, 2.4   # seconds: before the PG lands, between players, full five on screen
    total = first + step * len(SLOTS) + hold + render_reel.OUTRO
    script = """
const ease = 'cubic-bezier(.2,.8,.2,1)', pop = 'cubic-bezier(.3,1.5,.5,1)', fall = 'cubic-bezier(.55,0,1,.45)';
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
function add(parent, css) {
  const el = document.createElement('div');
  el.style.cssText = 'position:absolute;pointer-events:none;' + css;
  parent.appendChild(el);
  return el;
}
function setup() {
  const stage = document.querySelector('.stage'), outro = document.querySelector('.outro');
  const flash = add(stage, 'inset:0;background:%(accent)s;opacity:0');
  anim(document.querySelector('.title'), [{transform: 'scale(1.05)'}, {transform: 'none'}], 0, 700);
  %(slots)s.forEach((slot, k) => {
    const spot = document.querySelector(`.spot[data-slot="${slot}"]`), t = %(first)d + k * %(step)d;
    const box = spot.querySelector('.tile > div'), hit = t + 390;  // the moment the tile hits the floor
    // The tile falls from above the screen, tilted, slams onto the court and settles with a bounce.
    // Hidden until its turn: before its drop, a tile would otherwise wait in plain view above the screen edge.
    anim(box, [{opacity: 0}, {opacity: 1}], t, 1, 'linear');
    anim(box, [{transform: 'translateY(-1300px) scale(1.7) rotate(-12deg)', easing: fall},
               {offset: .7, transform: 'translateY(0) scale(.9) rotate(0)', easing: ease},
               {offset: .86, transform: 'scale(1.05)'}, {transform: 'none'}], t, 560, 'linear');
    // Impact: the screen shakes, a lime flash, a shockwave ring and sparks fly out of the tile.
    anim(stage, [{transform: 'none'}, {transform: 'translate(0, 16px)'}, {transform: 'translate(-9px, -7px)'},
                 {transform: 'translate(6px, 4px)'}, {transform: 'none'}], hit, 280, 'linear');
    anim(flash, [{opacity: 0}, {opacity: .2}, {opacity: 0}], hit, 300, 'linear');
    const ring = add(box, 'inset:-6px;border:8px solid %(accent)s;border-radius:28px');
    anim(ring, [{opacity: 0, transform: 'none'}, {opacity: .95, transform: 'none'}, {opacity: 0, transform: 'scale(1.8)'}], hit, 520, ease);
    for (let i = 0; i < 10; i++) {
      const a = i / 10 * 2 * Math.PI + .3, d = 230 + (i %% 3) * 60;
      const spark = add(box, 'left:50%%;top:50%%;width:16px;height:16px;margin:-8px;background:%(accent)s;border-radius:3px');
      anim(spark, [{opacity: 0, transform: 'none'}, {opacity: 1, transform: 'none', offset: .05},
                   {opacity: 0, transform: `translate(${Math.cos(a) * d}px, ${Math.sin(a) * d}px) rotate(${180 + i * 40}deg) scale(.4)`}],
           hit, 560, ease);
    }
    anim(spot.querySelector('.face'), [{boxShadow: '0 0 0 4px %(accent)s, 0 0 80px 26px %(accent)s'},
         {boxShadow: '0 0 0 4px %(accent)s, 0 14px 30px #000a'}], hit, 800, ease, 'forwards');
    // Then the position tag is stamped on, and the name wipes in.
    anim(spot.querySelector('.plate b'), [{opacity: 0, transform: 'scale(3) rotate(-14deg)'}, {opacity: 1, transform: 'none'}],
         hit + 60, 260, pop);
    for (const [i, el] of [...spot.querySelectorAll('.first, .last, .club')].entries())
      anim(el, [{opacity: 0, clipPath: 'inset(0 100%% 0 0)'}, {opacity: 1, clipPath: 'inset(0 0 0 0)'}], hit + 150 + i * 80, 300);
  });
  const end = %(outro_at)d;
  anim(stage, [{opacity: 1}, {opacity: 0}], end - 180, 180, 'linear', 'forwards');
  anim(outro, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], end, 260);
  const parts = [...outro.children];
  anim(parts[0], [{opacity: 0, transform: 'scale(.6) rotate(-90deg)'}, {opacity: 1, transform: 'none'}], end + 100, 600);
  parts.slice(1).forEach((el, k) => anim(el, [{opacity: 0, transform: 'translateY(70px)'}, {opacity: 1, transform: 'none'}],
                                         end + 350 + k * 120, 420));
}
function seek(ms) { document.getAnimations().forEach(a => { a.currentTime = ms; }); }
""" % dict(slots=json.dumps(SLOTS), first=first * 1000, step=step * 1000, outro_at=(total - render_reel.OUTRO) * 1000,
           accent=BRAND["colors"]["accent"])
    extra = f"<style>{render_reel.outro_css()}</style>{render_reel.outro_html(lang)}<script>{script}</script>"
    return doc.replace("</body>", extra + "</body>"), total


def render(folder):
    folder = (ROOT / folder).resolve()
    data = json.loads((folder / "lineup.json").read_text())
    for lang, fmt, name in (("en", "ig", "ig-1.png"), ("el", "ig", "ig-1.png"), ("en", "x", "x.png")):
        out = folder / "cards" / lang / name
        out.parent.mkdir(parents=True, exist_ok=True)
        doc, w, h = page(folder, data, lang, fmt)
        shoot(doc, w, h, out)
        print(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out)
    if not all_photos(folder, data):
        print("Not every player has a photo: all five tiles show the jersey drawing, and the caption credits no photo.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--season", default="E2026")
    p.add_argument("--round", type=int)
    r = sub.add_parser("render")
    r.add_argument("folder")
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.season, a.round)
    else:
        render(a.folder)


if __name__ == "__main__":
    main()
