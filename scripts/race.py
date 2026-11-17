#!/usr/bin/env python3
"""Season leaders race, after every round: a bar race of the season total (points by default) over the latest
WINDOW rounds (all of them while the season has fewer). The top 8 grow and overtake each other, a big round counter
ticks along, then the leader lights up and a line says what the race shows; then the brand outro. With sound
(sfx.py): a tick per round, a whoosh when the order changes.

  python3 scripts/race.py pick [--stat pts] [--season E2026]           # after the latest round -> races/<season>/round-NN/
  python3 scripts/race.py get <folder> [--upto N] [--window 6]         # any folder; --upto replays an earlier round
  python3 scripts/render_reel.py <folder> <lang>                        # cards/<lang>/reel.mp4

race.json holds, per player who was in the top 9 after any round of the window, his season total after each of
those rounds. The drafting
routine adds, per language, "title" (what the race shows, no numbers; `*accent*` allowed) and, for el, "names": the
Greek spelling of each surname by player code.
"""
import argparse
import collections
import html
import json
import pathlib
import re

from brand_mark import centre_disc
from lineup import display_name, mark
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS, ROOT
from round_digest import get

STATS = {"pts": ("points", {"en": "Total points", "el": "Πόντοι σεζόν"}), "valuation": ("valuation", {"en": "Total PIR", "el": "PIR σεζόν"})}
KICKER = {"en": "Season leaders race", "el": "Η κούρσα της σεζόν"}
ROUND = {"en": "Round {n}", "el": "{n}η αγωνιστική"}
N, TOP, SLOT, BAR = 8, 500, 118, 96       # bars shown; first bar's y; px per place; bar height
X0, MAXW = 184, 700                        # bar start, the leader's bar length
INTRO, STEP, HOLD = .7, .85, 2.6           # seconds: the window's first round on screen; per round; the end held
WINDOW = 6                                 # rounds shown: the latest six (the owner's choice, 2026-11-17)


def race_data(folder, season, stat, upto=None, window=WINDOW):
    """Season totals after each of the latest `window` rounds (up to round `upto`, to replay an earlier one).

    The API's season statistics give today's totals in one call (its round filter is ignored), so earlier totals are
    worked backwards: today's, minus the box scores of every round after the one wanted. A race costs one call plus
    the box scores of the rounds it steps back through (about 50 calls), at any point of the season."""
    import time
    key, season_key = {"pts": ("points", "pointsScored"), "valuation": ("valuation", "pir")}[stat]
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    by_round = collections.defaultdict(list)
    for g in games:
        by_round[g["round"]].append(g)
    played = [r for r in sorted(by_round) if all(g["played"] for g in by_round[r])]
    rounds = [r for r in played if upto is None or r <= upto]
    if not rounds:
        raise SystemExit("No fully played round yet")
    shown = rounds[-window:]
    now = get(f"/v3/competitions/E/statistics/players/traditional?seasonMode=Range&fromSeasonCode={season}"
              f"&toSeasonCode={season}&statisticMode=Accumulated&limit=1000")["players"]
    total = {p["player"]["code"]: p[season_key] for p in now}
    who = {}
    for p in now:
        first, last = display_name({"name": p["player"]["name"]})
        who[p["player"]["code"]] = {"first": first, "last": last, "club": p["player"]["team"]["code"]}

    def delta(r):  # each player's tally in round r
        out = collections.Counter()
        for g in by_round[r]:
            box = get(f"/v2/competitions/E/seasons/{season}/games/{g['gameCode']}/stats")
            time.sleep(.2)  # the API answers 429 to bursts
            for side in ("local", "road"):
                for p in box[side]["players"]:
                    out[p["player"]["person"]["code"]] += p["stats"][key]
        return out

    for r in [r for r in played if r > shown[-1]]:  # a replay: take off the rounds after it
        for c, v in delta(r).items():
            total[c] = total.get(c, 0) - v
    after = {shown[-1]: dict(total)}
    for k in range(len(shown) - 1, 0, -1):  # step back one round at a time
        for c, v in delta(shown[k]).items():
            total[c] = total.get(c, 0) - v
        after[shown[k - 1]] = dict(total)
    totals = {c: [round(after[r].get(c, 0)) for r in shown] for c in who}
    keep = set()
    for i in range(len(shown)):
        keep |= set(sorted(totals, key=lambda c: (-totals[c][i], who[c]["last"]))[:N + 1])
    rounds = shown
    data = {"season": season, "stat": stat, "rounds": rounds,
            "players": sorted(({"code": c, **who[c], "values": totals[c]} for c in keep),
                              key=lambda p: (-p["values"][-1], p["last"]))}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "race.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    lead = data["players"][0]
    print(f"{folder}: rounds {rounds[0]}-{rounds[-1]}, {len(keep)} players; leader {lead['last']} {lead['values'][-1]}")
    return folder


def ranks(players, i):
    """Each player's place after round index i (0 = first), ties broken by name, so the order never flickers."""
    order = sorted(players, key=lambda p: (-p["values"][i], p["last"]))
    return {p["code"]: k for k, p in enumerate(order)}


def timeline(d):
    total_rounds = len(d["rounds"])
    race_end = INTRO + STEP * (total_rounds - 1)
    import render_reel
    return race_end, race_end + .4 + 1.2 + HOLD + render_reel.OUTRO


def rich(text):
    t = html.escape(text).replace("\n", "<br>")
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def reel_document(folder, lang):
    """The Reel's page and its length in seconds (render_reel.py records it)."""
    import render_reel
    C = BRAND["colors"]
    d = json.loads((folder / "race.json").read_text())
    loc = d.get(lang, {})
    names = loc.get("names", {})
    race_end, total = timeline(d)
    players = d["players"]
    rk = [ranks(players, i) for i in range(len(d["rounds"]))]
    rows = []
    for p in players:
        c = CLUBS[p["club"]]
        rows.append(f'<div class="row abs" data-code="{p["code"]}">{mark(p["club"], 84)}'
                    f'<div class="bar" style="background:{c["bg"]};color:{c["fg"]};box-shadow:inset 0 0 0 4px {c["dot"]}55">'
                    f'<span>{html.escape(names.get(p["code"], p["last"]))}</span></div><div class="val">0</div></div>')
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
.top {{ left:72px; top:110px; font-weight:700; font-size:26px; letter-spacing:.12em; text-transform:uppercase; color:{C['muted']}; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.kicker {{ left:72px; top:180px; }}
.kicker span {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:36px;
  letter-spacing:.06em; text-transform:uppercase; padding:4px 16px; }}
.head {{ left:72px; top:240px; font-weight:900; font-size:120px; line-height:.95; text-transform:uppercase; }}
.round {{ right:72px; top:1450px; text-align:right; font-weight:900; font-size:84px; line-height:1; text-transform:uppercase; color:{C['muted']}; }}
.round b {{ color:{C['accent']}; font-weight:900; }}
.row {{ left:72px; height:{BAR}px; display:flex; align-items:center; will-change:transform; }}
.mark {{ flex:none; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.bar {{ position:absolute; left:{X0 - 72}px; height:{BAR}px; border-radius:0 14px 14px 0; display:flex; align-items:center; overflow:hidden; }}
.bar span {{ padding-left:22px; font-weight:900; font-size:44px; text-transform:uppercase; white-space:nowrap; }}
.val {{ position:absolute; font-weight:900; font-size:56px; color:{C['fg']}; }}
.row.lead .val {{ color:{C['accent']}; }}
.line {{ left:72px; right:72px; top:1450px; font-weight:900; font-size:72px; line-height:1; text-transform:uppercase; }}
.line .ln {{ display:block; }}
"""
    title = loc.get("title", "")
    lines = "".join(f'<span class="ln">{l}</span>' for l in rich(title).split("<br>")) if title else ""
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span></div>
<div class="kicker abs"><span>{html.escape(KICKER[lang])}</span></div>
<div class="head abs">{html.escape(STATS[d['stat']][1][lang])}</div>
{''.join(rows)}
<div class="round abs"></div><div class="line abs">{lines}</div></div>"""
    data = {"rounds": d["rounds"], "label": ROUND[lang], "players": [{"code": p["code"], "values": p["values"]} for p in players],
            "ranks": rk}
    script = """
const D = %(data)s, INTRO = %(intro)d, STEP = %(step)d, END = %(race_end)d;
const N = %(n)d, TOP = %(top)d, SLOT = %(slot)d, X0 = %(x0)d, MAXW = %(maxw)d;
const ease = 'cubic-bezier(.2,.8,.2,1)';
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const rows = Object.fromEntries($$('.row').map(el => [el.dataset.code, el]));
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const smooth = f => f * f * (3 - 2 * f);
function setup() {
  // The end: the leader lights up, the others step back, the round counter makes way for the line.
  anim($('.round'), [{opacity: 1}, {opacity: 0}], END + 400, 300, 'linear', 'forwards');
  $$('.line .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(50px)'}, {opacity: 1, transform: 'none'}], END + 600 + i * 220, 420));
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
  const last = D.rounds.length - 1;
  const p = Math.min(last, Math.max(0, (ms - INTRO) / STEP));
  const i = Math.min(last - 1, Math.floor(p)), f = last ? p - i : 0, g = smooth(f);
  const val = pl => last ? pl.values[i] + (pl.values[i + 1] - pl.values[i]) * f : pl.values[0];
  const lead = Math.max(...D.players.map(val), 1);
  const done = ms >= END + 400, k = done ? Math.min(1, (ms - END - 400) / 400) : 0;
  for (const pl of D.players) {
    const el = rows[pl.code], v = val(pl);
    const r = last ? D.ranks[i][pl.code] + (D.ranks[i + 1][pl.code] - D.ranks[i][pl.code]) * g : D.ranks[0][pl.code];
    const w = Math.max(40, v / lead * MAXW);
    el.style.transform = `translateY(${TOP + r * SLOT}px)`;
    el.style.opacity = Math.max(0, Math.min(1, N - r)) * (done && r > .5 ? 1 - .6 * k : 1);  // 8th to 9th place: fades out
    el.querySelector('.bar').style.width = w + 'px';
    const val_el = el.querySelector('.val');
    val_el.style.left = (X0 - 72 + w + 18) + 'px';
    val_el.textContent = Math.round(v);
    el.classList.toggle('lead', r < .5);
  }
  const n = D.rounds[Math.min(last, Math.round(p))];
  $('.round').innerHTML = D.label.replace('{n}', `<b>${n}</b>`);
}
""" % dict(data=json.dumps(data), intro=INTRO * 1000, step=STEP * 1000, race_end=race_end * 1000, n=N, top=TOP,
           slot=SLOT, x0=X0, maxw=MAXW, outro_at=(total - render_reel.OUTRO) * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def soundtrack(folder, lang, total, out):
    """Write the Reel's sound to `out` (WAV), timed to reel_document's animation (effects from sfx.py)."""
    import numpy as np
    import render_reel
    from sfx import Mix
    d = json.loads((folder / "race.json").read_text())
    race_end, _ = timeline(d)
    m = Mix(total, seed=5)
    put, tone, noise, lowpass = m.put, m.tone, m.noise, m.lowpass
    # A pulse under the race, quickening slightly, then the rounds: a tick each, a whoosh when the top 8 reshuffle.
    bed = noise(race_end + .6)
    bed = lowpass(bed, 12) - lowpass(bed, 80)
    put(.18 * bed * np.linspace(.4, 1, len(bed)), 0)
    rk = [ranks(d["players"], i) for i in range(len(d["rounds"]))]
    for i in range(1, len(d["rounds"])):
        t = INTRO + STEP * (i - 1)
        put(.3 * tone(1500, 1500, .03, .008), t + STEP * .5)
        put(.25 * m.knock(1), t + STEP * .5)
        moves = sum(1 for c, r in rk[i].items() if r < N and r < rk[i - 1][c])
        if moves:
            m.swoosh(t + .1, gain=min(.4, .12 + .06 * moves), dur=.5)
    # The finish: a hit, a sparkle for the leader, the line's swooshes, the outro chord.
    put(.7 * tone(130, 40, .9, .35), race_end + .4)
    for i, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
        put(.14 * tone(f, f, 1.0, .3), race_end + .5 + i * .07)
    n_lines = len(d.get(lang, {}).get("title", "").split("\n")) if d.get(lang, {}).get("title") else 0
    for i in range(n_lines):
        m.swoosh(race_end + .6 + i * .22)
    m.chord(total - render_reel.OUTRO + .1)
    return m.write(out)


def pick(season, stat):
    """The race after the latest fully played round, in races/<season>/round-NN/ (once per round)."""
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    by_round = collections.defaultdict(list)
    for g in games:
        by_round[g["round"]].append(g["played"])
    done = [r for r, p in by_round.items() if all(p)]
    if not done:
        raise SystemExit("No fully played round yet")
    folder = ROOT / "races" / season / f"round-{max(done):02d}"
    if (folder / "race.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
        return folder
    return race_data(folder, season, stat)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    g = sub.add_parser("get")
    g.add_argument("folder")
    g.add_argument("--upto", type=int, help="replay the race as it stood after this round")
    g.add_argument("--window", type=int, default=WINDOW)
    for x in (p, g):
        x.add_argument("--stat", default="pts", choices=sorted(STATS))
        x.add_argument("--season", default="E2026")
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.season, a.stat)
    else:
        race_data(pathlib.Path(a.folder).resolve(), a.season, a.stat, a.upto, a.window)


if __name__ == "__main__":
    main()
