#!/usr/bin/env python3
"""The specialists of the season, a Reel on both Instagram accounts (grid too) every Monday at 12:00 Athens after a
finished round, without approval (the owner's decision, 2026-11-27): four scorers picked from the EuroLeague API's season totals (players with
100+ points): the sniper (most of his points from threes), the paint (most from twos), the line (most from free
throws) and the all-rounder (the top-10 scorer whose points are split most evenly). Each gets a half court with every
shot of his season from the live API (makes glow lime, so where he shoots lights up; misses are faint dots; the
free-throw line glows for the line specialist), then a bar splitting his points into twos, threes and free throws.
Anyone featured in the last RECENT weeks is left out, so the cast rotates. With our own synthesized sound (sfx.py).
Shots come from shots/<season>/<game>.json, every played game's shots, fetched once (~10 calls a round).

  python3 scripts/specialists.py pick [--season E2026]          # Monday (specialists.yml): cache new games, pick, queue
  python3 scripts/specialists.py get <folder> [--season E2026]  # a preview into any folder
  python3 scripts/specialists.py captions <folder>              # rewrite the captions (after the Greek names are added)
  python3 scripts/render_reel.py <folder> <lang>                # cards/<lang>/reel.mp4
"""
import argparse
import html
import json
import pathlib
import time
import urllib.request

from brand_mark import centre_disc
from lineup import display_name, mark
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS
from round_digest import get

LIVE = "https://live.euroleague.net/api"
KINDS = ["three", "two", "ft", "all"]
LABEL = {"three": {"en": "The sniper", "el": "Ο σκόπευτης"},
         "two": {"en": "The paint", "el": "Ο άρχοντας της ρακέτας"},
         "ft": {"en": "Lives at the line", "el": "Ζει στη γραμμή"},
         "all": {"en": "The all-rounder", "el": "Ο ολοκληρωμένος"}}
LINE = {"three": {"en": "*{p3}%* of his points\nfrom three", "el": "Το *{p3}%* των πόντων του\nαπό το τρίποντο"},
        "two": {"en": "*{p2}%* of his points\ninside the arc", "el": "Το *{p2}%* των πόντων του\nαπό δίποντα"},
        "ft": {"en": "*{pf}%* of his points\nat the line", "el": "Το *{pf}%* των πόντων του\nαπό τις βολές"},
        "all": {"en": "Twos, threes,\nfree throws: *all of it*", "el": "Δίποντα, τρίποντα,\nβολές: *τα κάνει όλα*"}}
PARTS = {"en": ["Twos", "Threes", "Free throws"], "el": ["Δίποντα", "Τρίποντα", "Βολές"]}
KICKER = {"en": "Season so far · Round {n}", "el": "Η σεζόν ως την {n}η"}
HEAD = {"en": "The\nspecialists", "el": "Οι\nειδικοί"}
FACTS = {"en": ("points", "shots", "games"), "el": ("πόντοι", "σουτ", "αγώνες")}
EYEBROW = {"en": "The specialists of the season", "el": "Οι ειδικοί της σεζόν"}
S = .6                          # px per cm
BASELINE, MID = 470, 540        # the baseline's y on screen, the basket's x
POST_AT = {"three": "10:00", "two": "12:00", "ft": "14:00", "all": "16:00"}  # Athens, Monday: one Reel every 2 hours
RECENT = 4                      # weeks: a player featured in the last 4 is left out
INTRO, SCENE = 1.6, 4.6         # seconds: the title card; per player
TWO, THREE, FTC = "#F4F1EA", None, "#FF9F43"   # bar colours: twos, threes (the accent), free throws


def season_rows(season):
    """Every player with 100+ points this season: totals and the split of his points (twos, threes, free throws)."""
    q = f"seasonMode=Single&seasonCode={season}&limit=1000&statisticMode=Accumulated"
    rows = []
    for p in get(f"/v3/competitions/E/statistics/players/traditional?{q}")["players"]:
        pts = p["pointsScored"]
        if pts < 100:
            continue
        s2, s3, sf = 2 * p["twoPointersMade"] / pts, 3 * p["threePointersMade"] / pts, p["freeThrowsMade"] / pts
        rows.append({"code": p["player"]["code"], "name": p["player"]["name"], "club": p["player"]["team"]["code"],
                     "pts": pts, "games": p["gamesPlayed"], "split": [s2, s3, sf],
                     "fg2": f"{p['twoPointersMade']:.0f}/{p['twoPointersAttempted']:.0f}",
                     "fg3": f"{p['threePointersMade']:.0f}/{p['threePointersAttempted']:.0f}",
                     "ft": f"{p['freeThrowsMade']:.0f}/{p['freeThrowsAttempted']:.0f}"})
    return rows


def choose(rows, skip=()):
    """The four specialists, leaving out players featured recently (`skip`) so the cast rotates week to week."""
    pool = [r for r in rows if r["code"] not in skip] or rows
    chosen = {"three": max(pool, key=lambda r: r["split"][1])}
    pool = [r for r in pool if r is not chosen["three"]]
    chosen["two"] = max(pool, key=lambda r: r["split"][0])
    pool = [r for r in pool if r is not chosen["two"]]
    chosen["ft"] = max(pool, key=lambda r: r["split"][2])
    pool = [r for r in pool if r is not chosen["ft"]]
    top10 = sorted(pool, key=lambda r: -r["pts"])[:10]
    chosen["all"] = min(top10, key=lambda r: max(r["split"]) - min(r["split"]))
    return chosen


def cache(season, games):
    """Every played game's located shots, saved once in shots/<season>/<game>.json (a played game's shots never
    change): each week reads only the new games, ~10 calls a round. Returns how many were fetched."""
    from render_cards import ROOT
    folder = ROOT / "shots" / season
    folder.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for g in games:
        f = folder / f"{g['gameCode']}.json"
        if not g["played"] or f.exists():
            continue
        time.sleep(1)
        req = urllib.request.Request(f"{LIVE}/Points?gamecode={g['gameCode']}&seasoncode={season}",
                                     headers={"User-Agent": "Mozilla/5.0 (parquet-hoops)", "Accept": "application/json"})
        rows = json.load(urllib.request.urlopen(req, timeout=30))["Rows"]
        if not rows:  # not out yet: try again next run
            continue
        shots = [[r["ID_PLAYER"].strip().lstrip("P"), r["COORD_X"], r["COORD_Y"], int(r["ID_ACTION"].endswith("M")),
                  int(r["ID_ACTION"][0])] for r in rows if r["ID_ACTION"][:1] in "23"]
        f.write_text(json.dumps({"game": g["gameCode"], "round": g["round"], "home": g["local"]["club"]["code"],
                                 "away": g["road"]["club"]["code"], "shots": shots}, separators=(",", ":")) + "\n")
        fetched += 1
    return fetched


def shots(season, codes):
    """Every cached shot of these players: {code: [[x, y, made], ...]}."""
    from render_cards import ROOT
    out = {c: [] for c in codes}
    for f in sorted((ROOT / "shots" / season).glob("*.json")):
        for code, x, y, made, _ in json.loads(f.read_text())["shots"]:
            if code in out:
                out[code].append([x, y, made])
    return out


def get_data(folder, season, skip=(), games=None):
    games = games or get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    print(f"{cache(season, games)} new games' shots cached")
    chosen = choose(season_rows(season), skip)
    sh = shots(season, [c["code"] for c in chosen.values()])
    rnd = max(r for r in {g["round"] for g in games} if all(g["played"] for g in games if g["round"] == r))
    players = []
    for k in KINDS:
        c = chosen[k]
        first, last = display_name({"name": c["name"]})
        players.append({**c, "kind": k, "first": first, "last": last, "shots": sh[c["code"]]})
    for p in players:  # one Reel per specialist (the owner's choice, 2026-11-27): <folder>/<kind>/
        sub = folder / p["kind"]
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "specialists.json").write_text(json.dumps({"season": season, "round": rnd, "players": [p]}, ensure_ascii=False) + "\n")
        captions(sub)
    print(f"{folder}:", ", ".join(f"{p['kind']} {p['last']} ({len(p['shots'])} shots)" for p in players))
    return players


def captions(folder):
    """The captions, data only; the Greek one uses the Greek surnames once the Monday routine has added them."""
    import unicodedata
    d = json.loads((folder / "specialists.json").read_text())
    names = d.get("el", {}).get("names", {})
    def tag(code):
        c = CLUBS[code]
        plain = unicodedata.normalize("NFKD", c["en"]).encode("ascii", "ignore").decode()
        return c.get("hashtag") or "#" + "".join(ch for ch in plain if ch.isalnum())
    p = d["players"][0]
    s2, s3, sf = (round(v * 100) for v in p["split"])
    el_last = names.get(p["code"], p["last"])
    what = {"en": {"three": f"{s3}% of his points this season come from three ({p['fg3']}).",
                   "two": f"{s2}% of his points this season come from inside the arc ({p['fg2']})"
                          + (", without a single three attempted." if p["fg3"].endswith("/0") else "."),
                   "ft": f"{sf}% of his points this season come from the free-throw line ({p['ft']}).",
                   "all": f"Twos {s2}%, threes {s3}%, free throws {sf}%: he scores every way ({p['pts']:.0f} points)."},
            "el": {"three": f"Το {s3}% των πόντων του φέτος είναι από το τρίποντο ({p['fg3']}).",
                   "two": f"Το {s2}% των πόντων του φέτος είναι από δίποντα ({p['fg2']})"
                          + (", χωρίς ούτε ένα τρίποντο." if p["fg3"].endswith("/0") else "."),
                   "ft": f"Το {sf}% των πόντων του φέτος είναι από τις βολές ({p['ft']}).",
                   "all": f"Δίποντα {s2}%, τρίποντα {s3}%, βολές {sf}%: σκοράρει με κάθε τρόπο ({p['pts']:.0f} πόντοι)."}}
    ask = {"en": {"three": "Who's the best shooter in the EuroLeague? 👇", "two": "Who rules the paint? 👇",
                  "ft": "Who do you want at the line with the game on it? 👇", "all": "Who's the most complete scorer? 👇"},
           "el": {"three": "Ποιος είναι ο καλύτερος σουτέρ της EuroLeague; 👇", "two": "Ποιος κυριαρχεί στη ρακέτα; 👇",
                  "ft": "Ποιον θέλεις στη γραμμή στο τελευταίο δευτερόλεπτο; 👇", "all": "Ποιος είναι ο πιο ολοκληρωμένος σκόρερ; 👇"}}
    n, club = d["round"], tag(p["club"])
    (folder / "post.en.md").write_text(f"""# The specialists, Round {n}: {LABEL[p['kind']]['en']}, {p['first']} {p['last']}

## Instagram caption
{LABEL[p['kind']]['en']}: {p['first']} {p['last']} ({CLUBS[p['club']]['en']}). 🎯

{what['en'][p['kind']]}
Every shot of his season, on one court.

{ask['en'][p['kind']]}

#EuroLeague {club} #Basketball #EuroLeagueBasketball #ShotChart #Specialists #ParquetHoops
""")
    (folder / "post.el.md").write_text(f"""# Οι ειδικοί, {n}η αγωνιστική: {LABEL[p['kind']]['el']}, {el_last}

## Instagram caption
{LABEL[p['kind']]['el']}: ο {el_last} ({CLUBS[p['club']]['el']}). 🎯

{what['el'][p['kind']]}
Κάθε σουτ της σεζόν του, σε ένα γήπεδο.

{ask['el'][p['kind']]}

#EuroLeague #μπάσκετ #basketball {club} #ParquetHoops
""")


def pick(season):
    """Monday: the four specialists after the latest fully played round -> specialists/<season>/round-NN/<kind>/, leaving
    out anyone featured in the last RECENT weeks; each queued (approved) for today at its POST_AT, Reels on both accounts."""
    import datetime as dt
    import subprocess
    import sys
    import zoneinfo
    from render_cards import ROOT
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    done = [r for r in {g["round"] for g in games} if all(g["played"] for g in games if g["round"] == r)]
    if not done:
        print("No fully played round yet")
        return
    base = ROOT / "specialists" / season
    folder = base / f"round-{max(done):02d}"
    if (folder / KINDS[0] / "specialists.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
    else:
        weeks = sorted(d for d in base.glob("round-*") if d.is_dir())[-RECENT:]
        skip = {p["code"] for w in weeks for f in w.glob("*/specialists.json") for p in json.loads(f.read_text())["players"]}
        get_data(folder, season, skip, games)
    queue = [sys.executable, str(ROOT / "scripts" / "publish_queue.py")]
    listed = subprocess.run(queue + ["list"], capture_output=True, text=True).stdout
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Athens")).strftime("%Y-%m-%d")
    for k in KINDS:
        story = (folder / k).relative_to(ROOT).as_posix()
        if story not in listed:
            subprocess.run(queue + ["add", story, f"{today} {POST_AT[k]}", "--langs", "reel-en,reel-el"], check=True)


def court(i, glow_ft):
    a, b = BRAND["colors"]["accent"], BASELINE
    X = lambda cm: MID + cm * S
    Y = lambda cm: b + cm * S
    hoop = 157.5
    corner = (675 ** 2 - 660 ** 2) ** .5 + hoop
    ft = (f'<line class="ftline" x1="{X(-245)}" y1="{Y(580)}" x2="{X(245)}" y2="{Y(580)}" stroke="#FF9F43" stroke-width="14" '
          f'stroke-linecap="round"/>' if glow_ft else "")
    return f"""<svg class="court" width="1080" height="1920" style="position:absolute;inset:0"><g fill="none" stroke="{a}" stroke-opacity=".32" stroke-width="5">
<rect x="{X(-750)}" y="{Y(0)}" width="{1500 * S}" height="{1400 * S}"/>
<rect x="{X(-245)}" y="{Y(0)}" width="{490 * S}" height="{580 * S}"/>
<path d="M{X(-180)} {Y(580)} A{180 * S} {180 * S} 0 0 0 {X(180)} {Y(580)}"/>
<path d="M{X(-660)} {Y(0)} V{Y(corner)} A{675 * S} {675 * S} 0 0 0 {X(660)} {Y(corner)} V{Y(0)}"/>
<line x1="{X(-90)}" y1="{Y(120)}" x2="{X(90)}" y2="{Y(120)}" stroke-opacity=".7"/>
<circle cx="{X(0)}" cy="{Y(hoop)}" r="{23 * S}" stroke-opacity=".7"/></g>{ft}</svg>"""


def rich(text):
    import re
    t = html.escape(text).replace("\n", "<br>")
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def intro(d):
    """A title card only when one Reel holds several specialists; a single one opens straight on his court."""
    return INTRO if len(d["players"]) > 1 else 0


def timeline(d):
    import render_reel
    end = intro(d) + len(d["players"]) * SCENE
    return end, end + render_reel.OUTRO


def reel_document(folder, lang):
    import render_reel
    C = BRAND["colors"]
    d = json.loads((folder / "specialists.json").read_text())
    loc = d.get(lang, {})
    end, total = timeline(d)
    X = lambda cm: MID + cm * S
    Y = lambda cm: BASELINE + (157.5 + cm) * S
    scenes = []
    for i, p in enumerate(d["players"]):
        s2, s3, sf = p["split"]
        pc = {"p2": round(s2 * 100), "p3": round(s3 * 100), "pf": round(sf * 100)}
        last = loc.get("names", {}).get(p["code"], p["last"])
        dots = "".join(f'<i class="{"m" if m else "o"}" style="left:{X(x):.0f}px;top:{Y(y):.0f}px"></i>'
                       for x, y, m in p["shots"] if -760 < x < 760 and -170 < y < 1250)
        bar = "".join(f'<div class="seg" style="flex:{v:.4f};background:{col}"><span>{round(v * 100)}%</span></div>'
                      for v, col in zip(p["split"], (TWO, C["accent"], FTC)) if v > 0)
        keys = "".join(f'<span><i style="background:{col}"></i>{html.escape(t)}</span>'
                       for t, col in zip(PARTS[lang], (TWO, C["accent"], FTC)))
        foot = {"three": p["fg3"] + (" 3P" if lang == "en" else " τρίποντα"),
                "two": p["fg2"] + (" 2P" if lang == "en" else " δίποντα") + (
                    " · 0 3PA" if lang == "en" and p["fg3"].endswith("/0") else " · κανένα τρίποντο" if p["fg3"].endswith("/0") else ""),
                "ft": p["ft"] + (" FT" if lang == "en" else " βολές"),
                "all": f"{p['pts']:.0f} " + ("points" if lang == "en" else "πόντοι")}[p["kind"]]
        title = "".join(f'<span class="ln">{l}</span>' for l in rich(LINE[p["kind"]][lang].format(**pc)).split("<br>"))
        # The first frame (the preview) already says who and how much: his season's points, shots and games, and his
        # shots as faint ghost dots, so his hot zones show before they light up.
        facts = " · ".join(x for x in (f"{p['pts']:.0f} {FACTS[lang][0]}", f"{len(p['shots'])} {FACTS[lang][1]}",
                                       f"{p['games']:.0f} {FACTS[lang][2]}" if p.get("games") else "") if x)
        scenes.append(f"""<section class="spec abs" style="inset:0">{court(i, p['kind'] == 'ft')}
<div class="kicker abs"><span>{html.escape(LABEL[p['kind']][lang])}</span></div>
<div class="who abs">{mark(p['club'], 96)}<div><small>{html.escape(p['first'])}</small><b>{html.escape(last)}</b>
<span class="facts">{html.escape(facts)}</span></div></div>
<div class="ghost abs" style="inset:0">{dots}</div><div class="dots abs" style="inset:0">{dots}</div>
<div class="say abs">{title}</div>
<div class="bar abs">{bar}</div><div class="keys abs">{keys}</div><div class="foot abs">{html.escape(foot)}</div></section>""")
    css = f"""
@font-face {{ font-family: F; font-weight: 500; src: url({FONTS}/FiraSansExtraCondensed-Medium.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; }}
body {{ font-family:F, sans-serif; color:{C['fg']}; background:{C['bg']}; position:relative; }}
em {{ font-style:normal; color:{C['accent']}; }}
.abs {{ position:absolute; }}
.shade {{ position:absolute; inset:0; background: radial-gradient(ellipse at 50% 45%, {C['bg']}88 0%, {C['bg']}CC 70%, {C['bg']}F4 100%); }}
.top {{ left:72px; top:110px; font-weight:700; font-size:26px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; z-index:5; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.intro {{ inset:0; display:flex; flex-direction:column; justify-content:center; padding:0 72px; }}
.intro .k span, .kicker span {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:36px;
  letter-spacing:.06em; text-transform:uppercase; padding:4px 16px; }}
.intro h1 {{ margin-top:20px; font-weight:900; font-size:190px; line-height:.9; text-transform:uppercase; }}
.intro h1 .ln {{ display:block; }}
.kicker {{ left:72px; top:180px; }}
.who {{ left:72px; top:250px; display:flex; align-items:center; gap:24px; }}
.who small {{ display:block; font-weight:700; font-size:40px; color:{C['muted']}; text-transform:uppercase; line-height:1; }}
.who b {{ display:block; font-weight:900; font-size:96px; line-height:.95; text-transform:uppercase; }}
.mark {{ flex:none; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.dots i {{ position:absolute; border-radius:50%; transform:translate(-50%, -50%); }}
.dots i.m {{ width:56px; height:56px; background:radial-gradient(circle, {C['accent']}cc 0 18%, {C['accent']}33 40%, transparent 70%);
  mix-blend-mode:screen; }}
.dots i.o {{ width:14px; height:14px; background:#ffffff40; }}
.ghost i {{ position:absolute; border-radius:50%; transform:translate(-50%, -50%); }}
.ghost i.m {{ width:16px; height:16px; background:{C['accent']}; opacity:.3; }}
.ghost i.o {{ width:10px; height:10px; background:#ffffff26; }}
.who .facts {{ display:block; margin-top:8px; font-weight:700; font-size:30px; color:{C['muted']}; text-transform:uppercase; letter-spacing:.04em; }}
.top .eyebrow {{ color:{C['muted']}; }}
.say {{ left:72px; right:72px; top:1350px; font-weight:900; font-size:76px; line-height:1; text-transform:uppercase; }}
.say .ln {{ display:block; }}
.bar {{ left:72px; right:72px; top:1540px; height:84px; display:flex; border-radius:12px; overflow:hidden; gap:4px; }}
.seg {{ display:flex; align-items:center; justify-content:center; min-width:0; transform-origin:left; }}
.seg span {{ font-weight:900; font-size:40px; color:{C['bg']}; white-space:nowrap; }}
.keys {{ left:72px; right:72px; top:1642px; display:flex; gap:34px; font-weight:700; font-size:28px; text-transform:uppercase; color:{C['muted']}; }}
.keys i {{ display:inline-block; width:22px; height:22px; border-radius:5px; margin-right:10px; vertical-align:-3px; }}
.foot {{ left:72px; right:72px; top:1700px; font-weight:700; font-size:30px; color:{C['muted']}; text-transform:uppercase; }}
"""
    intro_html = "" if not intro(d) else (f'<div class="intro abs"><div class="k"><span>{html.escape(KICKER[lang].format(n=d["round"]))}</span></div>'
             f'<h1>{"".join(f"<span class=ln>{html.escape(l)}</span>" for l in HEAD[lang].split(chr(10)))}</h1></div>')
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span><span class="eyebrow"> · {html.escape(EYEBROW[lang])}</span></div>
{intro_html}{''.join(scenes)}</div>"""
    script = """
const INTRO = %(intro)d, SCENE = %(scene)d;
const ease = 'cubic-bezier(.2,.8,.2,1)';
const $ = s => document.querySelector(s), $$ = (s, r) => [...(r || document).querySelectorAll(s)];
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const rise = [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}];
function setup() {
  $$('.intro .k, .intro h1 .ln').forEach((el, i) => anim(el, rise, 100 + i * 160, 420));
  if ($('.intro')) anim($('.intro'), [{opacity: 1}, {opacity: 0}], INTRO - 200, 200, 'linear', 'forwards');
  $$('.spec').forEach((sc, i) => {
    const s = INTRO + i * SCENE;
    // A Reel with one specialist is complete from its first frame (court, label, name); the shots then land.
    const opener = i === 0 && INTRO === 0;
    if (!opener) {
      anim(sc, [{opacity: 0}, {opacity: 1}], s, 220);
      anim(sc.querySelector('.court'), [{opacity: 0, transform: 'scale(.94)'}, {opacity: 1, transform: 'none'}], s, 500);
      anim(sc.querySelector('.kicker'), [{opacity: 0, transform: 'translateX(-80px)'}, {opacity: 1, transform: 'none'}], s + 80, 380);
      anim(sc.querySelector('.who'), [{opacity: 0, transform: 'translateX(-80px)'}, {opacity: 1, transform: 'none'}], s + 180, 420);
    }
    anim(sc, [{opacity: 1}, {opacity: 0}], s + SCENE - 220, 220, 'linear', 'forwards');
    // Every shot of his season lands within ~1.4 s, in random order: the hot zones fill up and glow.
    const dots = $$('.dots i', sc);
    dots.forEach((el, k) => anim(el, [{opacity: 0, transform: 'translate(-50%%, -50%%) scale(2.4)'},
                                      {opacity: 1, transform: 'translate(-50%%, -50%%) scale(1)'}],
                                 s + 450 + ((k * 7919) %% dots.length) / Math.max(1, dots.length) * 1400, 260));
    const ft = sc.querySelector('.ftline');
    if (ft) anim(ft, [{opacity: 0}, {opacity: 1}, {opacity: .35}, {opacity: 1}, {opacity: .35}, {opacity: 1}], s + 600, 1600, 'linear');
    $$('.say .ln', sc).forEach((el, k) => anim(el, rise, s + 1900 + k * 160, 420));
    $$('.seg', sc).forEach((el, k) => anim(el, [{transform: 'scaleX(0)'}, {transform: 'none'}], s + 2300 + k * 180, 500));
    anim(sc.querySelector('.keys'), [{opacity: 0}, {opacity: 1}], s + 2700, 300);
    anim(sc.querySelector('.foot'), [{opacity: 0}, {opacity: 1}], s + 2800, 300);
  });
  const end = %(outro_at)d, outro = $('.outro');
  anim($('.stage'), [{opacity: 1}, {opacity: 0}], end - 180, 180, 'linear', 'forwards');
  anim(outro, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], end, 260);
  const parts = [...outro.children];
  anim(parts[0], [{opacity: 0, transform: 'scale(.6) rotate(-90deg)'}, {opacity: 1, transform: 'none'}], end + 100, 600);
  parts.slice(1).forEach((el, k) => anim(el, rise, end + 350 + k * 120, 420));
}
function seek(ms) { document.getAnimations().forEach(a => { a.currentTime = ms; }); }
""" % dict(intro=intro(d) * 1000, scene=SCENE * 1000, outro_at=end * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def soundtrack(folder, lang, total, out):
    """A swoosh into each player, a patter of soft ticks as his shots land (more makes, brighter), a thump as the bar
    fills, the outro chord."""
    import numpy as np
    import render_reel
    from sfx import Mix
    d = json.loads((folder / "specialists.json").read_text())
    end, _ = timeline(d)
    m = Mix(total)
    for i, p in enumerate(d["players"]):
        s = intro(d) + i * SCENE
        if s:
            m.swoosh(s, gain=.16, dur=.35)
        n = len(p["shots"])
        for k, (_, _, made) in enumerate(p["shots"][:120]):
            t = s + .45 + ((k * 7919) % n) / max(1, n) * 1.4
            m.put((.07 if made else .035) * m.tone(1800 if made else 900, 1800 if made else 900, .06, .02), t)
        m.put(.5 * m.tone(120, 60, .35, .12), s + 2.3)
        m.swoosh(s + 1.9, gain=.1, dur=.25)
    m.chord(end + .1)
    return m.write(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick"); p.add_argument("--season", default="E2026")
    g = sub.add_parser("get"); g.add_argument("folder", type=pathlib.Path); g.add_argument("--season", default="E2026")
    c = sub.add_parser("captions"); c.add_argument("folder", type=pathlib.Path)
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.season)
    elif a.cmd == "captions":
        captions(a.folder)
    else:
        get_data(a.folder, a.season)


if __name__ == "__main__":
    main()
