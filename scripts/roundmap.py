#!/usr/bin/env python3
"""Next round on the map: a Reel every Monday 09:00 Athens before a round, without approval (the owner's decision,
2026-11-23), on both Instagram accounts (grid too) and X. Every game of the round in tip-off order: a flight arc from
the away team's city to the venue, the home crest and city lighting up there, a fixture card (day and time in Athens,
both crests, arena and city); when the next flight takes off, the venue keeps both clubs' crests side by side. Then
"From <westernmost city> to <easternmost city>." and the brand outro. With our own synthesized sound (sfx.py). All of
it is data: .github/workflows/roundmap.yml runs `pick`, which writes map.json, the captions and the queue entry; the
Reel is rendered at publish time (render_reel.py).

  python3 scripts/roundmap.py pick [--season E2026]                       # Monday (roundmap.yml): the round starting this week
  python3 scripts/roundmap.py get <folder> [--round N] [--season E2026]   # any round, into any folder (a preview)
  python3 scripts/render_reel.py <folder> <lang>                          # cards/<lang>/reel.mp4
"""
import argparse
import collections
import datetime as dt
import html
import json
import pathlib
import urllib.request
import zoneinfo

from brand_mark import centre_disc
from lineup import mark
from race import rich
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS, ROOT
from round_digest import get

ATHENS = zoneinfo.ZoneInfo("Europe/Athens")
POST_AT = "09:00"                       # Athens, Monday
KICKER = {"en": "Next round", "el": "Επόμενη αγωνιστική"}
HEAD = {"en": "Round {n}\non the map", "el": "Η {n}η αγωνιστική\nστον χάρτη"}
DAYS = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "el": ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]}
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
INTRO, STEP, HOLD = 1.6, 1.5, 2.8      # seconds: before the first flight; per game; the end held
FLY = .75                               # seconds a flight takes
PAIR = 52                               # px: each crest of a past game's pair on the map
# Venue -> (city en, city el, lat, lon): city-level points, enough for a map this size. A venue missing here stops
# `pick` with an error: add it.
VENUES = {
    "PALAU BLAUGRANA": ("Barcelona", "Βαρκελώνη", 41.38, 2.12),
    "PEACE AND FRIENDSHIP STADIUM": ("Piraeus", "Πειραιάς", 37.94, 23.67),
    "SUNEL ARENA": ("Athens", "Αθήνα", 38.08, 23.70),
    "TELEKOM CENTER ATHENS": ("Athens", "Αθήνα", 38.04, 23.79),
    "TURKCELL BASKETBALL DEVELOPMENT CENTER": ("Istanbul", "Κωνσταντινούπολη", 40.99, 28.91),
    "ULKER SPORTS AND EVENT HALL": ("Istanbul", "Κωνσταντινούπολη", 40.99, 29.11),
    "COCA-COLA ARENA": ("Dubai", "Ντουμπάι", 25.20, 55.27),
    "ADIDAS ARENA": ("Paris", "Παρίσι", 48.90, 2.36),
    "ACCOR ARENA": ("Paris", "Παρίσι", 48.84, 2.38),
    "SPYROS KYPRIANOU ATHLETIC CENTER": ("Limassol", "Λεμεσός", 34.69, 33.04),
    "BELGRADE ARENA": ("Belgrade", "Βελιγράδι", 44.81, 20.42),
    "ALEKSANDAR NIKOLIC HALL": ("Belgrade", "Βελιγράδι", 44.80, 20.47),
    "ZALGIRIO ARENA": ("Kaunas", "Κάουνας", 54.89, 23.91),
    "ROIG ARENA": ("Valencia", "Βαλένθια", 39.46, -0.36),
    "UNIPOL FORUM": ("Milan", "Μιλάνο", 45.41, 9.14),
    "SAP GARDEN": ("Munich", "Μόναχο", 48.18, 11.55),
    "BMW PARK": ("Munich", "Μόναχο", 48.12, 11.53),
    "LDLC ARENA": ("Lyon", "Λυών", 45.76, 4.98),
    "ASTROBALLE": ("Lyon", "Λυών", 45.77, 4.88),
    "ARENA 8888 SOFIA": ("Sofia", "Σόφια", 42.68, 23.34),
    "ARENA BOTEVGRAD": ("Botevgrad", "Μπότεβγκραντ", 42.90, 23.79),
    "MOVISTAR ARENA": ("Madrid", "Μαδρίτη", 40.42, -3.67),
    "VIRTUS ARENA": ("Bologna", "Μπολόνια", 44.52, 11.36),
    "PALADOZZA": ("Bologna", "Μπολόνια", 44.49, 11.33),
    "BUESA ARENA": ("Vitoria", "Βιτόρια", 42.86, -2.66),
}
# The city in Greek after "από" / "ως" (accusative, with its article), for the end line.
CITY_EL_ACC = {
    "Barcelona": "τη Βαρκελώνη",
    "Piraeus": "τον Πειραιά",
    "Athens": "την Αθήνα",
    "Istanbul": "την Κωνσταντινούπολη",
    "Dubai": "το Ντουμπάι",
    "Paris": "το Παρίσι",
    "Limassol": "τη Λεμεσό",
    "Belgrade": "το Βελιγράδι",
    "Kaunas": "το Κάουνας",
    "Valencia": "τη Βαλένθια",
    "Milan": "το Μιλάνο",
    "Munich": "το Μόναχο",
    "Lyon": "τη Λυών",
    "Sofia": "τη Σόφια",
    "Botevgrad": "το Μπότεβγκραντ",
    "Madrid": "τη Μαδρίτη",
    "Bologna": "την Μπολόνια",
    "Vitoria": "τη Βιτόρια",
}
ACRONYMS = {"Ldlc": "LDLC", "Sap": "SAP", "Bmw": "BMW"}
LIBS = {  # map geometry (Natural Earth via world-atlas, public domain) and the code to draw it, cached in .cache/
    "d3.js": "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js",
    "topojson.js": "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js",
    "countries-50m.json": "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json",
}


def lib(name):
    f = ROOT / ".cache" / "roundmap" / name
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(LIBS[name], timeout=60).read())
    return f.read_text()


def arena_name(v):
    return " ".join(ACRONYMS.get(w, w) for w in v.title().split())


def get_round(folder, season, rnd=None, games=None):
    """The round's games in tip-off order (each with where the away team flies from: its usual home venue) and the
    end line per language; writes map.json and returns it."""
    games = games or get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    if rnd is None:
        rnd = min(g["round"] for g in games if not g["played"])
    homes = collections.defaultdict(collections.Counter)  # each club's usual venue: where its flights start
    for g in games:
        homes[g["local"]["club"]["code"]][g["venue"]["name"]] += 1
    out = []
    for g in sorted((g for g in games if g["round"] == rnd), key=lambda g: g["utcDate"]):
        h, a = g["local"]["club"]["code"], g["road"]["club"]["code"]
        out.append({"game": g["gameCode"], "utc": g["utcDate"], "home": h, "away": a, "venue": g["venue"]["name"],
                    "from": homes[a].most_common(1)[0][0]})
    missing = sorted({v for x in out for v in (x["venue"], x["from"]) if v not in VENUES})
    if missing:
        raise SystemExit(f"Add these venues to VENUES in roundmap.py: {', '.join(missing)}")
    cities = sorted({VENUES[x["venue"]] for x in out}, key=lambda v: v[3])  # west to east
    west, east = cities[0], cities[-1]
    d = {"season": season, "round": rnd, "games": out,
         "en": {"title": f"From {west[0]}\n*to {east[0]}.*"},
         "el": {"title": f"Από {CITY_EL_ACC[west[0]]}\n*ως {CITY_EL_ACC[east[0]]}.*"}}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "map.json").write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return d


def tip(x):
    return dt.datetime.fromisoformat(x["utc"].replace("Z", "+00:00")).astimezone(ATHENS)


def days(d, lang):
    """The round's game days: "Tue 24 & Wed 25 Nov" / "Τρίτη 24/11 και Τετάρτη 25/11"."""
    ds = sorted({tip(x).date() for x in d["games"]})
    if lang == "el":
        return " και ".join(f"{DAYS['el'][t.weekday()]} {t.day}/{t.month}" for t in ds)
    parts = [f"{DAYS['en'][t.weekday()]} {t.day}" for t in ds]
    return " & ".join(parts) + f" {MONTHS_EN[ds[-1].month - 1]}"


def posts(folder, d):
    """Captions (Instagram EN + EL) and the X post: data only, like the next-game posts."""
    n, k = d["round"], len(d["games"])
    title = {l: d[l]["title"].replace("*", "").replace("\n", " ") for l in ("en", "el")}
    clubs = {c for x in d["games"] for c in (x["home"], x["away"])}
    greek = " ".join(t for c, t in (("OLY", "#Ολυμπιακός"), ("PAN", "#Παναθηναϊκός")) if c in clubs)
    (folder / "post.en.md").write_text(f"""# Round {n} on the map

## X
Round {n} on the map 🗺️

{k} games, {title['en'][0].lower() + title['en'][1:]}
{days(d, 'en')}

#EuroLeague

## Instagram caption
Round {n} on the map. 🗺️

{k} games, {title['en'][0].lower() + title['en'][1:]}
{days(d, 'en')}.

Which trip would you make? 👇

#EuroLeague #EuroLeagueBasketball #Basketball #BasketballEurope #Round{n} #NextRound #Hoops #ParquetHoops
""")
    (folder / "post.el.md").write_text(f"""# Η {n}η αγωνιστική στον χάρτη

## Instagram caption
Η {n}η αγωνιστική στον χάρτη. 🗺️

{k} αγώνες, {title['el'][0].lower() + title['el'][1:]}
{days(d, 'el')}.

Σε ποιο ταξίδι θα πήγαινες; 👇

#EuroLeague #μπάσκετ #basketball {greek + ' ' if greek else ''}#EuroLeagueBasketball #αγωνιστική #ParquetHoops
""")


def pick(season):
    """Monday: the round whose first game is in the next 7 days -> maps/<season>/round-NN/, queued (approved) for
    today at POST_AT with both Reels and X."""
    import subprocess
    import sys
    now = dt.datetime.now(dt.timezone.utc)
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    first = {}
    for g in games:
        t = dt.datetime.fromisoformat(g["utcDate"].replace("Z", "+00:00"))
        first[g["round"]] = min(first.get(g["round"], t), t)
    soon = [r for r, t in first.items() if now < t <= now + dt.timedelta(days=7)]
    if not soon:
        print("No round starts in the next 7 days")
        return
    rnd = min(soon)
    folder = ROOT / "maps" / season / f"round-{rnd:02d}"
    if (folder / "map.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
    else:
        posts(folder, get_round(folder, season, rnd, games))
        print(folder.relative_to(ROOT))
    queue = [sys.executable, str(ROOT / "scripts" / "publish_queue.py")]
    if folder.relative_to(ROOT).as_posix() not in subprocess.run(queue + ["list"], capture_output=True, text=True).stdout:
        today = now.astimezone(ATHENS).strftime("%Y-%m-%d")
        subprocess.run(queue + ["add", str(folder.relative_to(ROOT)), f"{today} {POST_AT}", "--langs", "reel-en,reel-el,x"],
                       check=True)


def when(utc, lang):
    t = dt.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ATHENS)
    if lang == "el":
        return f"{DAYS['el'][t.weekday()]} {t.day}/{t.month} · {t:%H:%M}"
    return f"{DAYS['en'][t.weekday()]} {t.day} {MONTHS_EN[t.month - 1]} · {t:%H:%M}"


def timeline(d):
    import render_reel
    end = INTRO + len(d["games"]) * STEP
    return end, end + HOLD + render_reel.OUTRO


def reel_document(folder, lang):
    import render_reel
    C = BRAND["colors"]
    d = json.loads((folder / "map.json").read_text())
    loc = d.get(lang, {})
    end, total = timeline(d)
    ci = 0 if lang == "en" else 1
    games, cards, pins = [], [], []
    for k, g in enumerate(d["games"]):
        v, f = VENUES[g["venue"]], VENUES[g["from"]]
        games.append({"to": [v[3], v[2]], "from": [f[3], f[2]], "color": CLUBS[g["away"]]["bg"]})
        name = lambda c: html.escape(CLUBS[c][lang])
        cards.append(f'<div class="card abs"><div class="when"><span>{html.escape(when(g["utc"], lang))}</span>'
                     f'<b>{k + 1}/{len(d["games"])}</b></div>'
                     f'<div class="teams">{mark(g["home"], 170)}<i>vs</i>{mark(g["away"], 170)}</div>'
                     f'<div class="names">{name(g["home"])} – {name(g["away"])}</div>'
                     f'<div class="where">{html.escape(arena_name(g["venue"]))} · {html.escape(v[ci])}</div></div>')
        pins.append(f'<div class="pin abs">{mark(g["home"], 64)}<span>{html.escape(v[ci])}</span></div>'
                    f'<div class="pair abs">{mark(g["home"], PAIR)}{mark(g["away"], PAIR)}</div>')
    css = f"""
@font-face {{ font-family: F; font-weight: 500; src: url({FONTS}/FiraSansExtraCondensed-Medium.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; }}
body {{ font-family:F, sans-serif; color:{C['fg']}; background:{C['bg']}; position:relative; }}
em {{ font-style:normal; color:{C['accent']}; }}
.abs {{ position:absolute; }}
.shade {{ position:absolute; inset:0; background: radial-gradient(ellipse at 50% 45%, {C['bg']}AA 0%, {C['bg']}DD 70%, {C['bg']}F6 100%); }}
.top {{ left:72px; top:110px; font-weight:700; font-size:26px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.kicker {{ left:72px; top:180px; }}
.kicker span {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:36px;
  letter-spacing:.06em; text-transform:uppercase; padding:4px 16px; }}
.head {{ left:72px; top:240px; font-weight:900; font-size:104px; line-height:.95; text-transform:uppercase; }}
.head .ln {{ display:block; }}
svg.map {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
.land {{ fill:#26303c; stroke:#3a4757; stroke-width:1.2; }}
.arc {{ fill:none; stroke-width:5; stroke-linecap:round; }}
.dot {{ fill:{C['accent']}; }}
.ring {{ fill:none; stroke:{C['accent']}; stroke-width:4; }}
.plane {{ fill:#fff; }}
.pair {{ display:flex; gap:4px; }}
.pin {{ display:flex; align-items:center; gap:12px; transform-origin:32px 32px; }}
.pin span {{ font-weight:900; font-size:40px; text-transform:uppercase; text-shadow:0 2px 12px #000, 0 0 4px #000; }}
.mark {{ flex:none; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.card {{ left:72px; right:72px; top:1300px; }}
.when {{ display:flex; justify-content:space-between; align-items:baseline; font-weight:900; font-size:44px; text-transform:uppercase; }}
.when span {{ color:{C['accent']}; }} .when b {{ color:{C['muted']}; font-size:36px; }}
.teams {{ display:flex; align-items:center; gap:36px; margin-top:28px; }}
.teams i {{ font-style:normal; font-weight:900; font-size:52px; color:{C['muted']}; text-transform:uppercase; }}
.names {{ margin-top:30px; font-weight:900; font-size:64px; line-height:1; text-transform:uppercase; white-space:nowrap; }}
.where {{ margin-top:16px; font-weight:700; font-size:38px; color:{C['muted']}; text-transform:uppercase; letter-spacing:.02em; }}
.line {{ left:72px; right:72px; top:1330px; font-weight:900; font-size:92px; line-height:1; text-transform:uppercase; }}
.line .ln {{ display:block; }}
"""
    head = "".join(f'<span class="ln">{html.escape(l)}</span>' for l in HEAD[lang].format(n=d["round"]).split("\n"))
    title = loc.get("title", "")
    lines = "".join(f'<span class="ln">{l}</span>' for l in rich(title).split("<br>")) if title else ""
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>
<svg class="map"><g class="lands"></g><g class="arcs"></g><g class="dots"></g></svg>
{''.join(pins)}
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span></div>
<div class="kicker abs"><span>{html.escape(KICKER[lang])}</span></div>
<div class="head abs">{head}</div>
{''.join(cards)}<div class="line abs">{lines}</div></div>"""
    script = """
const G = %(games)s, INTRO = %(intro)d, STEP = %(step)d, FLY = %(fly)d, END = %(end)d;
const ease = 'cubic-bezier(.2,.8,.2,1)';
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); parent.appendChild(e); return e; };
const world = %(world)s;
const pts = {type: 'MultiPoint', coordinates: G.flatMap(g => [g.to, g.from])};
const proj = d3.geoMercator().fitExtent([[70, 500], [1010, 1220]], pts);
const path = d3.geoPath(proj);
let arcs = [];
function setup() {
  svg('path', {class: 'land', d: path(topojson.feature(world, world.objects.countries))}, $('.lands'));
  const pins = $$('.pin'), cards = $$('.card'), pairs = $$('.pair'), spots = [];
  G.forEach((g, k) => {
    const [x1, y1] = proj(g.from), [x2, y2] = proj(g.to);
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
    const lift = Math.min(160, Math.hypot(dx, dy) * .3);
    const n = Math.hypot(dx, dy) || 1, cx = mx + dy / n * lift * (dx > 0 ? -1 : 1), cy = my - Math.abs(dx / n) * lift;
    const p = svg('path', {class: 'arc', d: `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`, stroke: '#ffffff'}, $('.arcs'));
    const L = p.getTotalLength();
    p.style.strokeDasharray = `${L} ${L}`;
    const plane = svg('circle', {class: 'plane', r: 9}, $('.arcs'));
    const ring = svg('circle', {class: 'ring', cx: x2, cy: y2, r: 12}, $('.dots'));
    const dot = svg('circle', {class: 'dot', cx: x2, cy: y2, r: 11}, $('.dots'));
    arcs.push({p, L, plane, start: INTRO + k * STEP});
    const t0 = INTRO + k * STEP, land = t0 + FLY;
    anim(dot, [{opacity: 0}, {opacity: 1}], land, 120);
    anim(ring, [{opacity: 0, r: 12}, {opacity: 1, r: 12, offset: .01}, {opacity: 0, r: 80}], land, 800, 'ease-out');
    const pin = pins[k], right = x2 > 760;
    pin.style.left = (right ? x2 - 32 : x2 - 32) + 'px'; pin.style.top = (y2 - 32) + 'px';
    if (right) { pin.style.flexDirection = 'row-reverse'; pin.style.left = 'auto'; pin.style.right = (1080 - x2 - 32) + 'px'; pin.style.transformOrigin = 'calc(100%% - 32px) 32px'; }
    anim(pin, [{opacity: 0, transform: 'scale(.3)'}, {opacity: 1, transform: 'none'}], land, 360);
    // When the next flight takes off (or the round is done), the venue keeps both clubs' crests, side by side.
    const off = k < G.length - 1 ? t0 + STEP : END + 300;
    anim(pin, [{opacity: 1}, {opacity: 0}], off, 200, 'linear', 'forwards');
    anim(dot, [{opacity: 1}, {opacity: 0}], off, 200, 'linear', 'forwards');
    anim(pairs[k], [{opacity: 0, transform: 'scale(.4)'}, {opacity: 1, transform: 'none'}], off, 320);
    spots.push({x: x2 - %(pair)d - 2, y: y2 - %(pair)d / 2});
    const c = cards[k];
    anim(c, [{opacity: 0, transform: 'translateX(90px)'}, {opacity: 1, transform: 'none'}], t0 + 80, 380);
    anim(c, [{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'translateX(-90px)'}], (k < G.length - 1 ? t0 + STEP - 160 : END + 200), 220, 'ease-in', 'forwards');
  });
  const PW = 2 * %(pair)d + 4, PH = %(pair)d;
  for (let it = 0; it < 60; it++) for (const p of spots) for (const q of spots) {
    if (p === q) continue;
    const ox = PW + 6 - Math.abs(p.x - q.x), oy = PH + 6 - Math.abs(p.y - q.y);
    if (ox > 0 && oy > 0) { const s = (p.y < q.y || p.y === q.y && p.x < q.x) ? -1 : 1; p.y += s * oy / 2; }
  }
  spots.forEach((p, k) => { p.x = Math.max(24, Math.min(1080 - 24 - PW, p.x)); pairs[k].style.left = p.x + 'px'; pairs[k].style.top = p.y + 'px'; });
  $$('.head .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(50px)'}, {opacity: 1, transform: 'none'}], 150 + i * 200, 420));
  anim($('.kicker'), [{opacity: 0}, {opacity: 1}], 0, 300);
  $$('.line .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(50px)'}, {opacity: 1, transform: 'none'}], END + 600 + i * 220, 420));
  const end = %(outro_at)d, outro = $('.outro');
  anim($('.stage'), [{opacity: 1}, {opacity: 0}], end - 180, 180, 'linear', 'forwards');
  anim(outro, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], end, 260);
  const parts = [...outro.children];
  anim(parts[0], [{opacity: 0, transform: 'scale(.6) rotate(-90deg)'}, {opacity: 1, transform: 'none'}], end + 100, 600);
  parts.slice(1).forEach((el, k) => anim(el, [{opacity: 0, transform: 'translateY(70px)'}, {opacity: 1, transform: 'none'}],
                                         end + 350 + k * 120, 420));
}
const smooth = f => f * f * (3 - 2 * f);
function seek(ms) {
  document.getAnimations().forEach(a => { a.currentTime = ms; });
  const done = ms > END + 300;
  arcs.forEach((a, k) => {
    const f = Math.max(0, Math.min(1, (ms - a.start) / FLY)), g = smooth(f);
    a.p.style.strokeDashoffset = a.L * (1 - g);
    const active = ms < a.start + STEP || k === arcs.length - 1 && !done;
    a.p.style.opacity = f === 0 ? 0 : done ? .55 : active ? 1 : .28;
    a.p.setAttribute('stroke', active && !done ? '#ffffff' : '%(accent)s');
    const q = a.p.getPointAtLength(a.L * g);
    a.plane.setAttribute('cx', q.x); a.plane.setAttribute('cy', q.y);
    a.plane.style.opacity = f > 0 && f < 1 ? 1 : 0;
  });
}
""" % dict(games=json.dumps(games), intro=INTRO * 1000, step=STEP * 1000, fly=FLY * 1000, end=end * 1000,
           world=lib("countries-50m.json"), pair=PAIR, accent=C["accent"], outro_at=(total - render_reel.OUTRO) * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style>'
           f'<script>{lib("d3.js")}</script><script>{lib("topojson.js")}</script></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def soundtrack(folder, lang, total, out):
    """A low hum under the map, a whoosh per flight, a ping when it lands, a hit and the chord at the end."""
    import numpy as np
    import render_reel
    from sfx import Mix, RATE
    d = json.loads((folder / "map.json").read_text())
    end, _ = timeline(d)
    m = Mix(total)
    n = int((end + HOLD) * RATE)
    m.put(.05 * np.sin(2 * np.pi * 55 * m.t(n)) * np.minimum(1, m.t(n) / .8) * np.minimum(1, (end + HOLD - m.t(n)) / 1.2), 0)
    for k in range(len(d["games"])):
        t0 = INTRO + k * STEP
        m.swoosh(t0, gain=.16, dur=FLY)
        m.put(.22 * m.tone(1320, 1320, .5, .12), t0 + FLY)
        m.put(.1 * m.tone(1980, 1980, .4, .08), t0 + FLY)
    m.put(.5 * m.tone(110, 50, .6, .2), end + .3)
    for i in range(2):
        m.swoosh(end + .6 + i * .22, gain=.12, dur=.25)
    m.chord(total - render_reel.OUTRO + .1)
    return m.write(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick"); p.add_argument("--season", default="E2026")
    g = sub.add_parser("get"); g.add_argument("folder", type=pathlib.Path); g.add_argument("--round", type=int)
    g.add_argument("--season", default="E2026")
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.season)
    else:
        posts(a.folder, get_round(a.folder, a.season, a.round))
        print(a.folder / "map.json")


if __name__ == "__main__":
    main()
