#!/usr/bin/env python3
"""Shot chart Reel: every shot of one player's night, in game order, on a half court. Makes land as lime bursts with
"+2" / "+3", misses as a faint cross, free throws bump the points counter; the game clock runs along. Then a line on
what the chart shows and his shooting numbers; then the brand outro. With sound (sfx.py): a swish for every make, a
rim clank for every miss, an arena murmur that swells at the end. Used for the MVP of the round, Sunday 18:00.

  python3 scripts/shotchart.py mvp mvps/E2026/round-NN                                     # the MVP's night -> <mvp folder>/shots/
  python3 scripts/shotchart.py get <folder> --game 101 --player 014124 [--season E2026]   # any player -> <folder>/shots.json
  python3 scripts/render_reel.py <folder> <lang>                                           # cards/<lang>/reel.mp4

Shots come from the EuroLeague live API (live.euroleague.net/api/Points: x/y in cm from the basket, made or missed,
clock); the shooting line from the box score. The drafting routine adds, per language, "first"/"last", "title" (what
the chart says, no numbers; `*accent*` allowed) and "stats" (up to 3 [value, label] pairs from "line").
"""
import argparse
import html
import json
import pathlib
import re
import sys
import urllib.request

from brand_mark import centre_disc
from lineup import display_name, mark
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS, ROOT
from round_digest import get

LIVE = "https://live.euroleague.net/api"
KICKER = {"en": "Every shot of his night", "el": "Κάθε σουτ της βραδιάς του"}
POINTS = {"en": "points", "el": "πόντοι"}
FT = {"en": "free throws", "el": "βολές"}
OT = {"en": " (OT)", "el": " (παρ.)"}
PERIOD = {"en": ["Q1", "Q2", "Q3", "Q4", "OT", "2OT", "3OT"], "el": ["1η", "2η", "3η", "4η", "Παρ.", "2η παρ.", "3η παρ."]}
S = .66                      # px per cm: the court's 15 m width fills 990px
BASELINE, MID = 470, 540     # the baseline's y on screen, the basket's x
FIRST, STEP = .9, .33        # seconds: before the first shot, between events
TITLE_GAP, HOLD = .9, 2.6    # after the last shot, the line rises; the full picture held


def get_shots(folder, season, game, player):
    req = urllib.request.Request(f"{LIVE}/Points?gamecode={game}&seasoncode={season}",
                                 headers={"User-Agent": "Mozilla/5.0 (parquet-hoops)", "Accept": "application/json"})
    rows = json.load(urllib.request.urlopen(req, timeout=30))["Rows"]
    mine = [r for r in rows if r["ID_PLAYER"].strip() == f"P{player}"]
    if not mine:
        sys.exit(f"No shots for player {player} in game {game}")
    box = get(f"/v2/competitions/E/seasons/{season}/games/{game}/stats")
    g = get(f"/v2/competitions/E/seasons/{season}/games/{game}")
    for side in ("local", "road"):
        for p in box[side]["players"]:
            if p["player"]["person"]["code"] == player:
                s, pl, club = p["stats"], p["player"], p["player"]["club"]["code"]
    first, last = display_name(pl["person"])
    events = []
    for r in mine:  # free throws at the same moment become one event
        minute = r["MINUTE"]
        period = (minute - 1) // 10 if minute <= 40 else 4 + (minute - 41) // 5
        ev = {"period": period, "clock": r["CONSOLE"].strip(), "pts": r["POINTS"]}
        if r["ID_ACTION"].startswith("FT"):
            if events and events[-1].get("ft") and events[-1]["clock"] == ev["clock"] and events[-1]["period"] == period:
                events[-1]["pts"] += r["POINTS"]
                continue
            ev["ft"] = True
        else:
            ev.update(x=r["COORD_X"], y=r["COORD_Y"], made=r["ID_ACTION"].endswith("M"), three=r["ID_ACTION"].startswith("3"))
        events.append(ev)
    pair = lambda a, b: f"{s[a]:.0f}/{s[b]:.0f}"
    data = {"season": season, "game": game, "code": player, "first": first, "last": last, "club": club,
            "home": g["local"]["club"]["code"], "away": g["road"]["club"]["code"],
            "home_pts": g["local"]["score"], "away_pts": g["road"]["score"], "overtime": max(r["MINUTE"] for r in rows) > 40,
            "line": {"pts": s["points"], "fg2": pair("fieldGoalsMade2", "fieldGoalsAttempted2"),
                     "fg3": pair("fieldGoalsMade3", "fieldGoalsAttempted3"), "ft": pair("freeThrowsMade", "freeThrowsAttempted"),
                     "fg": f"{s['fieldGoalsMade2'] + s['fieldGoalsMade3']:.0f}/{s['fieldGoalsAttempted2'] + s['fieldGoalsAttempted3']:.0f}"},
            "events": events}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "shots.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"{folder}: {first} {last}, {sum(1 for e in events if 'x' in e)} shots, {data['line']['pts']:.0f} points")
    return folder


def rich(text):
    t = html.escape(text).replace("\n", "<br>")
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def court():
    """A half court, basket at the top: FIBA lines in cm, scaled by S."""
    a, b = BRAND["colors"]["accent"], BASELINE
    X = lambda cm: MID + cm * S
    Y = lambda cm: b + cm * S  # cm from the baseline
    hoop = 157.5
    corner = (675 ** 2 - 660 ** 2) ** .5 + hoop
    return f"""<svg width="1080" height="1920" style="position:absolute;inset:0"><g fill="none" stroke="{a}" stroke-opacity=".38" stroke-width="5">
<rect x="{X(-750)}" y="{Y(0)}" width="{1500 * S}" height="{1400 * S}"/>
<rect x="{X(-245)}" y="{Y(0)}" width="{490 * S}" height="{580 * S}"/>
<path d="M{X(-180)} {Y(580)} A{180 * S} {180 * S} 0 0 0 {X(180)} {Y(580)}"/>
<path d="M{X(-660)} {Y(0)} V{Y(corner)} A{675 * S} {675 * S} 0 0 0 {X(660)} {Y(corner)} V{Y(0)}"/>
<path d="M{X(-125)} {Y(hoop)} A{125 * S} {125 * S} 0 0 0 {X(125)} {Y(hoop)}"/>
<line x1="{X(-90)}" y1="{Y(120)}" x2="{X(90)}" y2="{Y(120)}" stroke-opacity=".7"/>
<circle cx="{X(0)}" cy="{Y(hoop)}" r="{23 * S}" stroke-opacity=".7"/>
<path d="M{X(-180)} {Y(1400)} A{180 * S} {180 * S} 0 0 1 {X(180)} {Y(1400)}"/>
</g></svg>"""


def reel_document(folder, lang):
    """The Reel's page and its length in seconds (render_reel.py records it)."""
    import render_reel
    C = BRAND["colors"]
    d = json.loads((folder / "shots.json").read_text())
    loc = d.get(lang, {})
    first, last = loc.get("first", d["first"]), loc.get("last", d["last"])
    club = CLUBS[d["club"]].get(lang) or CLUBS[d["club"]]["en"]
    events = d["events"]
    name = lambda code: CLUBS[code].get(lang) or CLUBS[code]["en"]
    score = f"{name(d['home'])} {d['home_pts']}-{d['away_pts']} {name(d['away'])}{OT[lang] if d['overtime'] else ''}"
    shots_end = FIRST + STEP * len(events)
    title_at = shots_end + TITLE_GAP
    total = title_at + 1.4 + HOLD + render_reel.OUTRO
    css = f"""
@font-face {{ font-family: F; font-weight: 500; src: url({FONTS}/FiraSansExtraCondensed-Medium.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; }}
body {{ font-family:F, sans-serif; color:{C['fg']}; background:{C['bg']}; position:relative; }}
em {{ font-style:normal; color:{C['accent']}; }}
.abs {{ position:absolute; }}
.shade {{ position:absolute; inset:0; background: radial-gradient(ellipse at 50% 45%, {C['bg']}66 0%, {C['bg']}BB 70%, {C['bg']}F2 100%); }}
.top {{ left:72px; top:110px; font-weight:700; font-size:26px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.kicker {{ left:72px; top:180px; }}
.kicker span {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:36px;
  letter-spacing:.06em; text-transform:uppercase; padding:4px 16px; }}
.who {{ left:72px; right:72px; top:240px; display:flex; align-items:center; gap:24px; }}
.who .n {{ text-transform:uppercase; line-height:.95; }}
.who .first {{ font-weight:700; font-size:34px; color:{C['muted']}; letter-spacing:.05em; }}
.who .last {{ font-weight:900; font-size:100px; white-space:nowrap; margin-top:14px; }}  /* room for Greek capitals' accents and diaereses (ΡΑΪΤ) */
.who .game {{ margin-top:6px; font-weight:700; font-size:26px; color:{C['muted']}; letter-spacing:.08em; }}
.mark {{ flex:none; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.shot {{ width:0; height:0; }}
.ghost i {{ position:absolute; border-radius:50%; transform:translate(-50%, -50%); }}
.ghost i.m {{ width:18px; height:18px; background:{C['accent']}; opacity:.3; }}
.ghost i.o {{ width:12px; height:12px; background:#ffffff2a; }}
.shot .dot {{ position:absolute; left:-17px; top:-17px; width:34px; height:34px; border-radius:50%; background:{C['accent']};
  box-shadow:0 0 0 5px {C['bg']}, 0 0 26px 6px {C['accent']}99; }}
.shot.three .dot {{ left:-21px; top:-21px; width:42px; height:42px; }}
.shot .ring {{ position:absolute; left:-20px; top:-20px; width:40px; height:40px; border-radius:50%; border:6px solid {C['accent']}; }}
.shot .plus {{ position:absolute; left:-60px; width:120px; top:-90px; text-align:center; font-weight:900; font-size:56px; color:{C['accent']};
  text-shadow:0 4px 14px #000; }}
.shot .x {{ position:absolute; left:-18px; top:-26px; width:36px; text-align:center; font-weight:900; font-size:46px; line-height:1;
  color:{C['fg']}; opacity:.45; }}
.board {{ left:72px; right:72px; top:1418px; display:flex; align-items:flex-end; justify-content:space-between; }}
.pts .v {{ font-weight:900; font-size:150px; line-height:.85; color:{C['accent']}; }}
.pts .l {{ font-weight:700; font-size:32px; text-transform:uppercase; letter-spacing:.08em; }}
.clock {{ text-align:right; font-weight:900; font-size:56px; text-transform:uppercase; line-height:1; }}
.clock .l {{ font-weight:700; font-size:26px; color:{C['muted']}; letter-spacing:.08em; }}
.ftpop {{ left:72px; top:1340px; font-weight:900; font-size:44px; color:{C['accent']}; text-transform:uppercase; }}
.veil {{ left:0; right:0; top:900px; height:520px; background:linear-gradient(to bottom, {C['bg']}00, {C['bg']}EE 30%, {C['bg']}EE 80%, {C['bg']}00); }}
.title {{ left:72px; right:72px; top:990px; text-align:center; font-weight:900; font-size:84px; line-height:1; text-transform:uppercase; }}
.title .ln {{ display:block; }}
.stats {{ left:72px; right:72px; top:1418px; display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; }}
.stat {{ background:#ffffff0d; border-top:8px solid {C['accent']}; border-radius:10px; padding:12px 8px 14px; text-align:center; }}
.stat .v {{ font-weight:900; font-size:80px; line-height:.95; color:{C['accent']}; }}
.stat .l {{ font-weight:700; font-size:24px; text-transform:uppercase; letter-spacing:.06em; }}
"""
    X = lambda cm: MID + cm * S
    Y = lambda cm: BASELINE + (157.5 + cm) * S
    dots, ft_pops = [], []
    # The first frame (the preview) already shows where he scored: every shot of the night as a faint ghost dot,
    # lit up one by one as the game clock runs.
    ghost = "".join(f'<i class="{"m" if e["made"] else "o"}" style="left:{X(e["x"]):.0f}px;top:{Y(e["y"]):.0f}px"></i>'
                    for e in events if "x" in e)
    for i, e in enumerate(events):
        if e.get("ft"):
            ft_pops.append(f'<div class="ftpop abs" data-i="{i}">+{e["pts"]} {html.escape(FT[lang])}</div>')
        elif e["made"]:
            dots.append(f'<div class="shot abs{" three" if e["three"] else ""}" data-i="{i}" style="left:{X(e["x"]):.0f}px;top:{Y(e["y"]):.0f}px">'
                        f'<div class="ring"></div><div class="dot"></div><div class="plus">+{3 if e["three"] else 2}</div></div>')
        else:
            dots.append(f'<div class="shot abs miss" data-i="{i}" style="left:{X(e["x"]):.0f}px;top:{Y(e["y"]):.0f}px"><div class="x">✕</div></div>')
    title = loc.get("title", "")
    lines = "".join(f'<span class="ln">{l}</span>' for l in rich(title).split("<br>")) if title else ""
    stats = loc.get("stats") or [[d["line"]["fg"], "FG"]]
    stat_html = "".join(f'<div class="stat"><div class="v">{html.escape(v)}</div><div class="l">{html.escape(l)}</div></div>' for v, l in stats)
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>{court()}
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span></div>
<div class="kicker abs"><span>{html.escape(KICKER[lang])}</span></div>
<div class="who abs">{mark(d['club'], 110)}<div class="n"><div class="first">{html.escape(first)}</div><div class="last">{html.escape(last)}</div>
<div class="game">{html.escape(score)}</div></div></div>
<div class="ghost abs" style="inset:0">{ghost}</div>{''.join(dots)}{''.join(ft_pops)}
<div class="board abs"><div class="pts"><div class="v">0</div><div class="l">{html.escape(POINTS[lang])}</div></div>
<div class="clock"><div class="t">{PERIOD[lang][0]} 10:00</div></div></div>
<div class="veil abs"></div><div class="title abs">{lines}</div><div class="stats abs">{stat_html}</div></div>
<script>for (const el of document.querySelectorAll('.who .last')) {{ let fs = 100;
  while (el.scrollWidth > 760 && fs > 50) {{ fs -= 4; el.style.fontSize = fs + 'px'; }} }}</script>"""
    marks = [{"pts": e["pts"] if (e.get("ft") or e.get("made")) else 0,
              "clock": f'{PERIOD[lang][min(e["period"], 6)]} {e["clock"]}'} for e in events]
    script = """
const ease = 'cubic-bezier(.2,.8,.2,1)', pop = 'cubic-bezier(.3,1.6,.5,1)';
const marks = %(marks)s, F = %(first)d, STEP = %(step)d, T = %(title_at)d;
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
function setup() {
  $$('.shot').forEach(el => {
    const t = F + (+el.dataset.i) * STEP;
    if (el.classList.contains('miss')) {
      anim(el.querySelector('.x'), [{opacity: 0, transform: 'scale(2)'}, {opacity: .45, transform: 'none'}], t, 260);
      return;
    }
    anim(el.querySelector('.dot'), [{transform: 'scale(0)'}, {transform: 'scale(1.5)', offset: .6}, {transform: 'none'}], t, 320, pop);
    anim(el.querySelector('.ring'), [{opacity: 0, transform: 'none'}, {opacity: 1, transform: 'none', offset: .1},
                                     {opacity: 0, transform: 'scale(3.2)'}], t, 520, ease);
    anim(el.querySelector('.plus'), [{opacity: 0, transform: 'translateY(20px) scale(.6)'}, {opacity: 1, transform: 'none', offset: .25},
                                     {opacity: 1, transform: 'translateY(-30px)', offset: .75}, {opacity: 0, transform: 'translateY(-50px)'}], t, 800, 'linear');
  });
  $$('.ftpop').forEach(el => {
    const t = F + (+el.dataset.i) * STEP;
    anim(el, [{opacity: 0, transform: 'translateY(20px)'}, {opacity: 1, transform: 'none', offset: .2},
              {opacity: 1, offset: .8}, {opacity: 0, transform: 'translateY(-20px)'}], t, 700, 'linear');
  });
  anim($('.pts .v'), [{transform: 'none'}, {transform: 'none'}], 0, 1);
  // The end: the clock makes way for the numbers, the line rises over the chart.
  anim($('.clock'), [{opacity: 1}, {opacity: 0}], T - 300, 300, 'linear', 'forwards');
  anim($('.pts'), [{opacity: 1}, {opacity: 0}], T - 300, 300, 'linear', 'forwards');
  anim($('.veil'), [{opacity: 0}, {opacity: 1}], T - 200, 400, 'linear');
  $$('.title .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], T + i * 220, 420));
  $$('.stat').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], T + 900 + i * 180, 380));
  const end = %(outro_at)d, outro = $('.outro');
  anim($('.stage'), [{opacity: 1}, {opacity: 0}], end - 180, 180, 'linear', 'forwards');
  anim(outro, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], end, 260);
  const parts = [...outro.children];
  anim(parts[0], [{opacity: 0, transform: 'scale(.6) rotate(-90deg)'}, {opacity: 1, transform: 'none'}], end + 100, 600);
  parts.slice(1).forEach((el, k) => anim(el, [{opacity: 0, transform: 'translateY(70px)'}, {opacity: 1, transform: 'none'}],
                                         end + 350 + k * 120, 420));
}
function seek(ms) {
  document.getAnimations().forEach(a => { a.currentTime = ms; });
  // The points counter and the game clock follow the shots: each event's points tick up as it lands.
  let pts = 0, clock = null, bump = 0;
  marks.forEach((m, i) => {
    const t = F + i * STEP;
    if (ms >= t) { pts += m.pts; clock = m.clock; if (m.pts) bump = ms - t; }
  });
  $('.pts .v').textContent = pts;
  if (clock) $('.clock .t').textContent = clock;
  const k = bump < 250 && pts ? 1 + .18 * Math.sin(Math.PI * bump / 250) : 1;
  $('.pts .v').style.transform = `scale(${k})`;
}
""" % dict(marks=json.dumps(marks, ensure_ascii=False), first=FIRST * 1000, step=STEP * 1000, title_at=title_at * 1000,
           outro_at=(total - render_reel.OUTRO) * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def from_mvp(mvp_folder):
    """The MVP's night: <mvp folder>/shots/, with his names from mvp.json (the routine adds title and stats)."""
    m = json.loads((mvp_folder / "mvp.json").read_text())
    folder = get_shots(mvp_folder / "shots", m["season"], m["game"], m["code"])
    d = json.loads((folder / "shots.json").read_text())
    for lang in ("en", "el"):
        names = {k: m[lang][k] for k in ("first", "last") if k in m.get(lang, {})}
        if names:
            d[lang] = {**d.get(lang, {}), **names}
    (folder / "shots.json").write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return folder


def soundtrack(folder, lang, total, out):
    """Write the Reel's sound to `out` (WAV), timed to reel_document's animation (effects from sfx.py)."""
    import numpy as np
    import render_reel
    from sfx import Mix
    d = json.loads((folder / "shots.json").read_text())
    loc = d.get(lang, {})
    events = d["events"]
    title_at = FIRST + STEP * len(events) + TITLE_GAP
    n_lines = len(loc.get("title", "").split("\n")) if loc.get("title") else 0
    n_stats = len(loc.get("stats") or [1])
    m = Mix(total, seed=11)
    put, tone, noise, lowpass = m.put, m.tone, m.noise, m.lowpass

    def swish(gain):  # the ball through the net: a short, airy hiss
        w = noise(.28)
        return gain * (w - lowpass(w, 3)) * np.sin(np.linspace(0, np.pi, len(w))) ** 1.5 * m.decay(len(w), .12)

    def clank(gain):  # off the rim: inharmonic metal ringing
        return gain * sum(a * tone(f, f * .99, .5, .12) for f, a in ((690, 1), (1170, .7), (1830, .5), (2560, .35)))

    # An arena murmur under the shots, swelling as the chart completes.
    bed = noise(title_at + .8)
    bed = lowpass(bed, 10) - lowpass(bed, 60)
    k = np.linspace(0, 1, len(bed))
    put(.25 * bed * (.35 + .65 * k ** 2), 0)
    for i, e in enumerate(events):
        t = FIRST + i * STEP
        if e.get("ft"):
            for j in range(e["pts"]):
                put(swish(.35), t + j * .12)
        elif e["made"]:
            put(swish(.7 if not e["three"] else .85), t)
            put(.25 * tone(880 if not e["three"] else 1320, 880 if not e["three"] else 1320, .25, .08), t + .03)
        else:
            put(clank(.32), t)
            put(.4 * m.knock(1), t)  # and the thud of the ball on the rim
    put(.5 * tone(120, 45, .8, .3), title_at - .2)  # the chart is complete: a low hit
    for i in range(n_lines):
        m.swoosh(title_at + i * .22)
    for i in range(n_stats):
        put(.35 * tone(520, 980, .12, .04), title_at + .9 + i * .18)
    m.chord(total - render_reel.OUTRO + .1)
    return m.write(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    mv = sub.add_parser("mvp")
    mv.add_argument("folder", help="the MVP of the round's folder, e.g. mvps/E2026/round-12")
    g = sub.add_parser("get")
    g.add_argument("folder")
    g.add_argument("--game", type=int, required=True)
    g.add_argument("--player", required=True, help="the player's person code, e.g. 014124")
    g.add_argument("--season", default="E2026")
    a = ap.parse_args()
    if a.cmd == "mvp":
        from_mvp((ROOT / a.folder).resolve())
    else:
        get_shots(pathlib.Path(a.folder).resolve(), a.season, a.game, a.player)


if __name__ == "__main__":
    main()
