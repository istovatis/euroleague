#!/usr/bin/env python3
"""MVP of the round: a Reel. A dark arena: spotlights sweep the floor, searching, past the player's silhouette, then all
lock onto him at once and the lights blaze up on his card; then a catchy line says why he was the MVP, then his best
numbers of the round count up; then the brand outro.

  python3 scripts/mvp.py pick [--round N]        # the latest fully played round's top PIR -> mvps/<season>/round-NN/mvp.json
  python3 scripts/render_reel.py <folder> <lang> # cards/<lang>/reel.mp4 (reel_document)

pick writes the player and his full box-score line. The drafting routine then adds, per language, "first"/"last" (the
Greek spelling for el), "title" (the catchy line: why he was the MVP, in the voice of CLAUDE.md; `*accent*` allowed) and
"stats": up to 4 [value, label] pairs, his most striking numbers, each taken from "line". Without them the Reel uses the
API name and PIR, points, rebounds, assists. Photos follow lineup.py: <folder>/photo-<code>.jpg + .json, current club's
jersey only; otherwise our own vest drawing.

Sound: our own effects, synthesized in soundtrack() and timed to the animation (no music or clips from elsewhere): a drum
roll and a rising rumble while the lights search, a swish on each sweep, then the lights clunk on with a boom, a sparkle
and a crowd roar, thumps as the name is stamped on, ticks while the numbers count up and a pop as each lands.
"""
import argparse
import html
import json
import re
import sys

from brand_mark import centre_disc
from lineup import display_name, jersey, mark
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS, ROOT
from round_digest import get

# The lime tag at the top asks, the big headline under it says what this is (the owner's choice, 2026-11-16)
KICKER = {"en": "Who was it?", "el": "Ποιος ήταν;"}
HEADLINE = {"en": "Round {n}\nMVP", "el": "Ο MVP της\n{n}ης αγωνιστικής"}
BURST, TITLE_AT, STATS_AT = 2.8, 5.6, 7.8  # seconds: the lights lock on, the title rises, the numbers start
# The spotlights: source x above the screen and their angles while searching (degrees; they speed up), before locking on.
SPOTS = [(120, [22, -18, 14, -26, 8]), (540, [-16, 24, -22, 18, -10]), (960, [-28, 12, -34, 6, -16])]
SWEEP_AT = [0, .3, .52, .7, .84]  # when each angle is reached, as a share of the search; then they lock on
DEFAULT = {"en": [("pir", "PIR"), ("pts", "points"), ("reb", "rebounds"), ("ast", "assists")],
           "el": [("pir", "PIR"), ("pts", "πόντοι"), ("reb", "ριμπάουντ"), ("ast", "ασίστ")]}


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
    folder = ROOT / "mvps" / season / f"round-{rnd:02d}"
    if (folder / "mvp.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
        return folder
    best = None
    for g in rgames:
        box = get(f"/v2/competitions/E/seasons/{season}/games/{g['gameCode']}/stats")
        for side, other in (("local", "road"), ("road", "local")):
            for p in box[side]["players"]:
                s, pl = p["stats"], p["player"]
                if not s.get("timePlayed"):
                    continue
                if best and (s["valuation"], s["points"]) <= (best[0]["valuation"], best[0]["points"]):
                    continue
                best = (s, pl, g, side, other)
    s, pl, g, side, other = best
    first, last = display_name(pl["person"])
    m = lambda a, b: f"{s[a]:.0f}/{s[b]:.0f}"
    line = {"pir": s["valuation"], "pts": s["points"], "reb": s["totalRebounds"], "oreb": s["offensiveRebounds"],
            "ast": s["assistances"], "stl": s["steals"], "blk": s["blocksFavour"], "tov": s["turnovers"],
            "min": round(s["timePlayed"] / 60, 1), "fg2": m("fieldGoalsMade2", "fieldGoalsAttempted2"),
            "fg3": m("fieldGoalsMade3", "fieldGoalsAttempted3"), "ft": m("freeThrowsMade", "freeThrowsAttempted"),
            "plus_minus": s["plusMinus"]}
    data = {"season": season, "round": rnd, "code": pl["person"]["code"], "first": first, "last": last,
            "club": pl["club"]["code"], "dorsal": str(pl.get("dorsal") or s.get("dorsal") or ""), "game": g["gameCode"],
            "opponent": g[other]["club"]["code"], "won": g[side]["score"] > g[other]["score"],
            "score": f"{g['local']['club']['code']} {g['local']['score']}-{g['road']['score']} {g['road']['club']['code']}",
            "line": line}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mvp.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{folder.relative_to(ROOT)}: {first} {last} ({data['club']}), PIR {line['pir']:.0f}")
    return folder


def rich(text):
    """`*accent*` and line breaks, as on the cards."""
    t = html.escape(text).replace("\n", "<br>")
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def face(folder, p, w, h):
    photo = folder / f"photo-{p['code']}.jpg"
    if photo.exists():
        meta = json.loads((folder / f"photo-{p['code']}.json").read_text())
        return (f'<div class="face" style="width:{w}px;height:{h}px;background-image:url({photo.as_uri()});'
                f'background-position:{meta.get("focus", "50% 20%")}">{mark(p["club"], 96)}</div>'
                f'<div class="credit">{html.escape(meta["credit"])}</div>')
    vest = jersey(p, round(w * .66)) if p.get("dorsal") else mark(p["club"], round(w * .5))
    return f'<div class="face none" style="width:{w}px;height:{h}px">{vest}{mark(p["club"], 96)}</div>'


def reel_document(folder, lang):
    """The Reel's page and its length in seconds (render_reel.py records it)."""
    import render_reel
    C = BRAND["colors"]
    p = json.loads((folder / "mvp.json").read_text())
    loc = p.get(lang, {})
    first, last = loc.get("first", p["first"]), loc.get("last", p["last"])
    club = CLUBS[p["club"]].get(lang) or CLUBS[p["club"]]["en"]
    stats = loc.get("stats") or [[f"{p['line'][k]:.0f}", label] for k, label in DEFAULT[lang]]
    title = loc.get("title", "")
    kicker, headline = KICKER[lang], HEADLINE[lang].format(n=p["round"])
    # Final layout keeps clear of the bottom ~350px, where Instagram puts its caption and buttons.
    # seconds: the lights search, lock on, the card lights up; the title; the numbers; the full picture held
    burst, title_at, stats_at, hold = BURST, TITLE_AT, STATS_AT, 2.2
    total = stats_at + .45 * len(stats) + hold + render_reel.OUTRO
    css = f"""
@font-face {{ font-family: F; font-weight: 500; src: url({FONTS}/FiraSansExtraCondensed-Medium.ttf); }}
@font-face {{ font-family: F; font-weight: 700; src: url({FONTS}/FiraSansExtraCondensed-Bold.ttf); }}
@font-face {{ font-family: F; font-weight: 900; src: url({FONTS}/FiraSansExtraCondensed-Black.ttf); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; }}
body {{ font-family:F, sans-serif; color:{C['fg']}; background:{C['bg']}; position:relative; }}
em {{ font-style:normal; color:{C['accent']}; }}
.abs {{ position:absolute; }}
.shade {{ position:absolute; inset:0; background: radial-gradient(ellipse at 50% 40%, {C['bg']}44 0%, {C['bg']}AA 65%, {C['bg']}F2 100%); }}
.top {{ left:72px; right:72px; top:110px; display:flex; font-weight:700; font-size:26px; letter-spacing:.12em;
  text-transform:uppercase; color:{C['muted']}; }}
.top b {{ color:{C['fg']}; font-weight:900; }} .brand {{ display:inline-flex; align-items:center; gap:.4em; }}
.brand svg {{ width:1.15em; height:1.15em; }}
.kicker {{ left:0; right:0; top:200px; text-align:center; }}
.kicker span {{ display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:44px;
  letter-spacing:.06em; text-transform:uppercase; padding:6px 22px; }}
.teaser {{ left:0; right:0; top:300px; text-align:center; font-weight:900; font-size:104px; line-height:.95; text-transform:uppercase; }}
.dark {{ inset:0; background:#000; opacity:.86; }}
.beam {{ top:-140px; width:480px; height:2300px; margin-left:-240px; transform-origin:50% 0; mix-blend-mode:screen;
  filter:blur(16px); }}
.beam i {{ position:absolute; inset:0; clip-path:polygon(47% 0, 53% 0, 100% 100%, 0 100%);
  background:linear-gradient(to bottom, #fff6d677, #fff6d633 50%, #fff6d608); }}
.beam b {{ position:absolute; left:50%; width:300px; height:120px; margin-left:-150px; top:1060px; border-radius:50%;
  background:radial-gradient(ellipse, #fff6d6aa, #fff6d600 70%); }}
.hush {{ left:14px; right:14px; top:14px; height:560px; display:flex; align-items:center; justify-content:center;
  font-weight:900; font-size:330px; color:{C['fg']}; text-shadow:0 0 50px #000; }}
.rays {{ left:540px; top:835px; width:0; height:0; }}
.rays i {{ position:absolute; left:-14px; bottom:0; width:28px; height:1100px; transform-origin:50% 100%;
  background:linear-gradient(to top, {C['accent']}, {C['accent']}00); border-radius:14px; }}
.flash {{ inset:0; background:{C['accent']}; opacity:0; }}
.card {{ left:250px; top:440px; width:580px; }}
.tc {{ position:relative; border-radius:30px; padding:14px; background:linear-gradient(160deg, #2a3545, #10151c);
  box-shadow:0 0 0 7px {C['accent']}, 0 0 120px 24px {C['accent']}66, 0 30px 60px #000d; }}
.tc .face {{ box-shadow:none; border-radius:20px; }}
.plate {{ padding:18px 6px 8px; text-align:center; text-transform:uppercase; }}
.plate .first {{ font-weight:700; font-size:40px; color:{C['muted']}; letter-spacing:.05em; line-height:1; }}
.plate .last {{ font-weight:900; font-size:100px; line-height:.95; white-space:nowrap; }}
.plate .club {{ margin-top:6px; font-weight:700; font-size:30px; color:{C['accent']}; letter-spacing:.1em; }}
.face {{ position:relative; border-radius:28px; background-size:cover; background-color:#1b222c; overflow:hidden;
  box-shadow:0 0 0 6px {C['accent']}, 0 0 90px 10px {C['accent']}55, 0 24px 50px #000c; }}
.face.none {{ display:flex; align-items:center; justify-content:center; background:linear-gradient(160deg, #222b37, #12171f); }}
.face .mark {{ position:absolute; right:16px; bottom:16px; }}
.mark {{ border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.credit {{ margin-top:8px; font-size:16px; color:{C['muted']}; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.title {{ left:72px; right:72px; top:1035px; text-align:center; font-weight:900; font-size:70px; line-height:1; text-transform:uppercase; }}
.title .ln {{ display:block; }}
.stats {{ left:56px; right:56px; top:1345px; display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; }}
.stat {{ background:#ffffff0d; border-top:8px solid {C['accent']}; border-radius:10px; padding:14px 8px 16px; text-align:center; }}
.stat .v {{ font-weight:900; font-size:96px; line-height:.95; color:{C['accent']}; }}
.stat .l {{ font-weight:700; font-size:24px; line-height:1.1; text-transform:uppercase; letter-spacing:.06em; color:{C['fg']}; }}
"""
    rays = "".join(f'<i style="transform:rotate({a}deg)"></i>' for a in range(0, 360, 30))
    lines = "".join(f'<span class="ln">{l}</span>' for l in rich(title).split("<br>")) if title else ""
    stat_html = "".join(f'<div class="stat"><div class="v">{html.escape(str(v))}</div><div class="l">{html.escape(l)}</div></div>'
                        for v, l in stats)
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span></div>
<div class="dark abs"></div>
<div class="rays abs">{rays}</div>
<div class="card abs"><div class="tc">{face(folder, p, 552, 560)}<div class="hush abs">?</div><div class="plate"><div class="first">{html.escape(first)}</div>
<div class="last">{html.escape(last)}</div><div class="club">{html.escape(club)}</div></div></div></div>
{"".join(f'<div class="beam abs" style="left:{x}px"><i></i><b></b></div>' for x, _ in SPOTS)}
<div class="kicker abs"><span>{html.escape(kicker)}</span></div>
<div class="teaser abs">{rich(headline)}</div>
<div class="title abs">{lines}</div>
<div class="stats abs">{stat_html}</div>
<div class="flash abs"></div></div>
<script>for (const el of document.querySelectorAll('.plate .last')) {{ let fs = 100;
  while (el.scrollWidth > 540 && fs > 44) {{ fs -= 4; el.style.fontSize = fs + 'px'; }} }}</script>"""
    script = """
const ease = 'cubic-bezier(.2,.8,.2,1)', pop = 'cubic-bezier(.3,1.5,.5,1)';
const counters = [];
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
function setup() {
  const B = %(burst)d, T = %(title_at)d, S = %(stats_at)d;
  // From the first frame (the Reel's cover): a dark arena, the player's card in shadow with a "?", lights searching.
  // Each spotlight swings across the floor, faster and faster, missing him; then all three lock onto him.
  const card = $('.card'), spots = %(spots)s, at = %(sweep_at)s;
  $$('.beam').forEach((beam, i) => {
    // Aim at the card's centre while it waits in the dark (y 1005, set below), from the source 140px above the screen.
    const [x, angles] = spots[i], lock = -Math.atan2(540 - x, 1005 + 140) * 180 / Math.PI;
    const frames = angles.map((a, k) => ({transform: `rotate(${a}deg)`, offset: at[k] * .86, easing: 'ease-in-out'}));
    frames.push({transform: `rotate(${lock}deg)`, offset: .97, easing: 'cubic-bezier(.3,1.4,.5,1)'});
    frames.push({transform: `rotate(${lock}deg)`});
    anim(beam, frames, 0, B, 'linear');
    // The lights blaze up: the beams flare, then dissolve into the full arena light.
    anim(beam, [{opacity: 1}, {opacity: 1, offset: .25}, {opacity: 0}], B, 700, 'linear', 'forwards');
  });
  anim(card, [{transform: 'translateY(170px) scale(.84)'}, {transform: 'translateY(170px) scale(.84)'}], 0, B, 'linear', 'backwards');
  anim($('.tc .face'), [{filter: 'brightness(.06) blur(9px)'}, {filter: 'none'}], B, 450, ease);
  anim($('.tc'), [{boxShadow: '0 0 0 4px #ffffff1c, 0 30px 60px #000d'}, {boxShadow: '0 0 0 7px %(accent)s, 0 0 120px 24px %(accent)s66, 0 30px 60px #000d'}], B, 450, ease);
  $$('.credit').forEach(el => anim(el, [{opacity: 0}, {opacity: 1}], B + 300, 300, 'linear'));
  const hush = $('.hush');
  hush.animate([{opacity: .55, transform: 'scale(1)'}, {opacity: 1, transform: 'scale(1.08)'}, {opacity: .55, transform: 'scale(1)'}],
               {duration: 700, iterations: Infinity, easing: 'ease-in-out'}).pause();
  anim(hush, [{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'scale(2.4)'}], B, 300, ease, 'forwards');
  anim($('.dark'), [{opacity: .86}, {opacity: 0}], B, 350, 'linear', 'forwards');
  anim($('.flash'), [{opacity: 0}, {opacity: .5}, {opacity: 0}], B, 450, 'linear', 'forwards');
  anim($('.teaser'), [{opacity: 1}, {opacity: 0}], B, 200, 'linear', 'forwards');
  anim($('.rays'), [{opacity: 0, transform: 'scale(.2) rotate(0)'}, {opacity: 1, transform: 'scale(1) rotate(25deg)', offset: .3},
                    {opacity: 0, transform: 'scale(1.3) rotate(60deg)'}], B, 1800, 'linear');
  // The card steps into the light, then the name is stamped on.
  anim(card, [{transform: 'translateY(170px) scale(.84)'}, {transform: 'translateY(-20px) scale(1.05)', offset: .7},
              {transform: 'none'}], B + 60, 650, ease, 'forwards');
  const n = $$('.plate > div');
  n.forEach((el, i) => anim(el, [{opacity: 0, transform: 'scale(2.2)'}, {opacity: 1, transform: 'none'}], B + 650 + i * 160, 300, pop));
  // The card makes room but stays the star: it moves up and shrinks only a little.
  anim($('.card'), [{transform: 'none'}, {transform: 'translateY(-150px) scale(.8)'}], T - 500, 500, ease, 'forwards');
  // Why he was the MVP: the lines rise one by one.
  $$('.title .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}], T + i * 220, 420));
  // The numbers: each box slides in and its value counts up.
  $$('.stat').forEach((el, i) => {
    const t = S + i * 450;
    anim(el, [{opacity: 0, transform: 'translateX(' + (i %% 2 ? 120 : -120) + 'px)'}, {opacity: 1, transform: 'none'}], t, 380);
    const v = el.querySelector('.v'), m = v.textContent.match(/^([+-]?)(\\d+)$/);
    if (m) counters.push({el: v, sign: m[1], to: +m[2], start: t, dur: 700});
    anim(v, [{transform: 'scale(1)'}, {transform: 'scale(1.25)'}, {transform: 'none'}], t + 700, 260, pop);
  });
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
  for (const c of counters) {
    const k = Math.min(1, Math.max(0, (ms - c.start) / c.dur));
    c.el.textContent = c.sign + Math.round(c.to * (1 - Math.pow(1 - k, 3)));
  }
}
""" % dict(burst=burst * 1000, title_at=title_at * 1000, stats_at=stats_at * 1000, spots=json.dumps(SPOTS),
           sweep_at=json.dumps(SWEEP_AT), accent=C["accent"],
           outro_at=(total - render_reel.OUTRO) * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def soundtrack(folder, lang, total, out):
    """Write the Reel's sound to `out` (WAV), timed to reel_document's animation (effects from sfx.py)."""
    import numpy as np
    from sfx import RATE, Mix
    p = json.loads((folder / "mvp.json").read_text())
    loc = p.get(lang, {})
    n_stats = len(loc.get("stats") or DEFAULT[lang])
    n_lines = len(loc.get("title", "").split("\n")) if loc.get("title") else 0
    m = Mix(total)
    put, tone, noise, lowpass, knock = m.put, m.tone, m.noise, m.lowpass, m.knock

    # 1. The lights search: a drum roll speeding up and a rumble rising, both getting louder.
    shake0, b = .3, BURST
    at = shake0
    while at < b - .05:
        k = (at - shake0) / (b - shake0)
        put(m.snare(.15 + .45 * k), at)
        at += .11 - .07 * k
    n = int((b - shake0) * RATE)
    k = np.linspace(0, 1, n)
    rumble = np.sin(2 * np.pi * np.cumsum(np.linspace(45, 110, n)) / RATE) * k ** 2
    hiss = (lambda x: x - lowpass(x, 6))(noise(b - shake0)) * k ** 3
    put(.35 * rumble + .12 * hiss, shake0)
    for k in SWEEP_AT[1:]:  # a swish as the beams swing
        w = noise(.4)
        put(.22 * (w - lowpass(w, 30)) * np.sin(np.linspace(0, np.pi, len(w))) ** 2, k * .86 * b - .2)
    # 2. The lights lock on and blaze up: three heavy clunks, a boom, a sparkle of bells and a crowd roar.
    w = noise(.35)
    put(.5 * (w - lowpass(w, 4)) * np.linspace(0, 1, len(w)) ** 2, b - .33)
    for i in range(3):
        put(.6 * tone(70, 45, .3, .06), b - .14 + i * .07)
        put(.35 * knock(1), b - .14 + i * .07)
    put(.9 * tone(130, 38, .9, .35), b)
    crowd = noise(2.6)
    crowd = lowpass(crowd, 8) - lowpass(crowd, 40)
    t = m.t(len(crowd))
    put(1.4 * crowd * np.minimum(1, t / .35) * np.exp(-np.maximum(0, t - .5) / .9), b + .05)
    put(.6 * lowpass(noise(.4), 5) * m.decay(int(.4 * RATE), .07), b)
    for i, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0, 2637.0)):
        put(.16 * tone(f, f, 1.2, .35), b + .12 + i * .07)
    # 3. The name is stamped on: three thumps.
    for i in range(3):
        put(.55 * tone(110, 55, .25, .07), b + .75 + i * .16)
        put(.2 * knock(1), b + .75 + i * .16)
    # 4. The title lines: a soft swoosh each.
    for i in range(n_lines):
        m.swoosh(TITLE_AT + i * .22)
    # 5. The numbers: ticks while each counts up (slowing like the counter), then a pop.
    for i in range(n_stats):
        t0 = STATS_AT + i * .45
        for j in range(12):
            put(.12 * tone(3200, 3200, .015, .004), t0 + .7 * (1 - (1 - j / 12) ** 0.5))
        put(.4 * tone(520, 980, .12, .04), t0 + .7)
        put(.15 * knock(1), t0 + .7)
    # 6. The outro: one warm chord.
    import render_reel
    m.chord(total - render_reel.OUTRO + .1)
    return m.write(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--season", default="E2026")
    p.add_argument("--round", type=int)
    a = ap.parse_args()
    pick(a.season, a.round)


if __name__ == "__main__":
    main()
