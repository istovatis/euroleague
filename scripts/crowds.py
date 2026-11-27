#!/usr/bin/env python3
"""Biggest crowds of the round, a Reel on both Instagram accounts (grid too) every Saturday at 17:00 Athens after a
finished round, without approval (the owner's decision, 2026-11-27): every game's crowd, and its share of the arena's capacity, both from the
EuroLeague API's games list (one call). The Reel ranks the round's games by crowd (the owner's choice, 2026-11-27),
revealed from the smallest up to the biggest: each row's bar fills in the home club's colours to its crowd's share of
the biggest crowd (the top row is full; the owner's choice, 2026-11-27), while the crowd counts up beside its "% full"; then the biggest lights up and a line names it;
then the brand outro. With our own synthesized sound (sfx.py): a crowd that grows as the ranking climbs.

  python3 scripts/crowds.py pick [--season E2026]                       # Saturday (crowds.yml): the latest round -> crowds/<season>/round-NN/
  python3 scripts/crowds.py get <folder> [--round N] [--season E2026]   # any round, into any folder (a preview)
  python3 scripts/render_reel.py <folder> <lang>                         # cards/<lang>/reel.mp4
"""
import argparse
import html
import json
import pathlib

from brand_mark import centre_disc
from lineup import mark
from race import rich
from render_brand import parquet
from render_cards import BRAND, CLUBS, FONTS
from round_digest import get
from roundmap import VENUES, arena_name

KICKER = {"en": "Round {n}", "el": "{n}η αγωνιστική"}
HEAD = {"en": "Biggest\ncrowds", "el": "Ο περισσότερος\nκόσμος"}
FULL = {"en": "{p}% full", "el": "{p}% πληρότητα"}
POST_AT = "17:00"                      # Athens, Saturday
INTRO, STEP, HOLD = 1.0, .75, 2.8      # seconds: before the first row; per row; the end held
TOP, ROW = 560, 100                    # px: the first row's y; per row


def light(hex_colour):
    r, g, b = (int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b > .6


def get_round(folder, season, rnd=None, games=None):
    games = games or get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    if rnd is None:
        rnd = max(g["round"] for g in games if g["played"] and g["audienceConfirmed"])
    rows = []
    for g in games:
        if g["round"] != rnd or not g["audienceConfirmed"] or not g["venue"]["capacity"]:
            continue
        rows.append({"home": g["local"]["club"]["code"], "away": g["road"]["club"]["code"], "venue": g["venue"]["name"],
                     "crowd": g["audience"], "capacity": g["venue"]["capacity"]})
    rows.sort(key=lambda r: -r["crowd"])
    top = rows[0]
    city = VENUES.get(top["venue"], ("", ""))
    d = {"season": season, "round": rnd, "arenas": rows,
         "en": {"title": f"Most fans:\n*{arena_name(top['venue'])}.*"},
         "el": {"title": f"Πρώτη σε κόσμο:\n*{arena_name(top['venue'])}{', ' + city[1] if city[1] else ''}.*"}}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "crowds.json").write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return d


def club_tag(code):
    """The club's official hashtag from assets/clubs.json ("hashtag", confirmed by the owner), else our tag from its name."""
    import unicodedata
    c = CLUBS[code]
    if c.get("hashtag"):
        return c["hashtag"]
    plain = unicodedata.normalize("NFKD", c["en"]).encode("ascii", "ignore").decode()
    return "#" + "".join(ch for ch in plain if ch.isalnum())


def posts(folder, d):
    """Captions, data only: the top three crowds, a question, hashtags. The English one carries the official hashtag
    of the club with the biggest crowd (the owner's choice, 2026-11-27)."""
    top = d["arenas"][:3]
    line = lambda a, lang, sep: (f"{CLUBS[a['home']][lang]} – {CLUBS[a['away']][lang]}: "
                                 f"{a['crowd']:,}".replace(",", sep) + f" ({round(a['crowd'] / a['capacity'] * 100)}%)")
    n = d["round"]
    (folder / "post.en.md").write_text(f"""# Round {n}: biggest crowds

## Instagram caption
Round {n}'s biggest crowds. 🏟️

{chr(10).join(f"{k}. {line(a, 'en', ',')}" for k, a in enumerate(top, 1))}

Which arena would you pick for a game night? 👇

#EuroLeague {club_tag(top[0]['home'])} #EuroLeagueBasketball #Basketball #BasketballEurope #Fans #Arena #Round{n} #ParquetHoops
""")
    (folder / "post.el.md").write_text(f"""# {n}η αγωνιστική: ο περισσότερος κόσμος

## Instagram caption
Πού είχε τον περισσότερο κόσμο η {n}η αγωνιστική. 🏟️

{chr(10).join(f"{k}. {line(a, 'el', '.')}" for k, a in enumerate(top, 1))}

Σε ποιο γήπεδο θα ήθελες να δεις αγώνα; 👇

#EuroLeague #μπάσκετ #basketball #EuroLeagueBasketball #κερκίδα #ParquetHoops
""")


def timeline(d):
    import render_reel
    end = INTRO + len(d["arenas"]) * STEP
    return end, end + HOLD + render_reel.OUTRO


def reel_document(folder, lang):
    import render_reel
    C = BRAND["colors"]
    d = json.loads((folder / "crowds.json").read_text())
    end, total = timeline(d)
    n = len(d["arenas"])
    ci = 0 if lang == "en" else 1
    rows = []
    for k, a in enumerate(d["arenas"]):
        c = CLUBS[a["home"]]
        fill = c["bg"]
        if light(fill):  # a white kit: its second colour if that is dark, else a neutral slate
            fill = c["dot"] if not light(c["dot"]) else "#4A5568"
        pct = a["crowd"] / a["capacity"] * 100
        city = VENUES.get(a["venue"], ("", ""))[ci]
        if city and city.lower() in CLUBS[a["home"]][lang].lower():  # "Valencia · Valencia – …": say it once
            city = ""
        name = arena_name(a["venue"])
        rows.append(
            f'<div class="row abs" style="top:{TOP + k * ROW}px" data-w="{a["crowd"] / d["arenas"][0]["crowd"] * 100:.1f}" data-crowd="{a["crowd"]}">'
            f'<div class="fill" style="background:{fill};box-shadow:inset 0 0 0 3px {c["dot"]}55"></div>'
            f'<div class="rank">{k + 1}</div>{mark(a["home"], 64)}'
            f'<div class="txt"><b class="{"long" if len(name) > 24 else ""}">{html.escape(name)}</b>'
            f'<span>{html.escape(city + " · " if city else "")}{html.escape(CLUBS[a["home"]][lang])} – {html.escape(CLUBS[a["away"]][lang])}</span></div>'
            f'<div class="num"><b>0</b><i>{FULL[lang].format(p=round(pct))}</i></div></div>')
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
.head {{ left:72px; top:240px; font-weight:900; font-size:112px; line-height:.95; text-transform:uppercase; }}
.head .ln {{ display:block; }}
.row {{ left:56px; right:56px; height:{ROW - 12}px; border-radius:14px; background:#ffffff0d; overflow:hidden;
  display:flex; align-items:center; gap:18px; padding:0 22px; }}
.fill {{ position:absolute; left:0; top:0; bottom:0; width:0; opacity:.55; border-radius:14px 0 0 14px; }}
.row > *:not(.fill) {{ position:relative; }}
.rank {{ width:46px; font-weight:900; font-size:44px; color:{C['muted']}; text-align:center; }}
.mark {{ flex:none; border-radius:50%; background:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px #0008; }}
.mark img {{ width:72%; height:72%; object-fit:contain; }}
.mark span {{ font-weight:900; font-size:150%; letter-spacing:.04em; }}
.txt {{ flex:1; min-width:0; display:flex; flex-direction:column; }}
.txt b {{ font-weight:900; font-size:38px; line-height:1.05; text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.txt b.long {{ font-size:30px; }}
.txt b, .txt span, .rank, .num {{ text-shadow:0 1px 6px #000c; }}
.txt span {{ font-weight:700; font-size:24px; color:#ffffffbb; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.num {{ min-width:170px; text-align:right; display:flex; flex-direction:column; align-items:flex-end; }}
.num b {{ font-weight:900; font-size:48px; line-height:1; }}
.num i {{ font-style:normal; font-weight:700; font-size:24px; color:#ffffffcc; margin-top:4px; }}
.row.first {{ box-shadow:0 0 0 4px {C['accent']}, 0 0 40px {C['accent']}66; }}
.row.first .rank, .row.first .num b {{ color:{C['accent']}; }}
.line {{ left:72px; right:72px; top:{TOP + n * ROW + 40}px; font-weight:900; font-size:76px; line-height:1; text-transform:uppercase; }}
.line .ln {{ display:block; }}
"""
    head = "".join(f'<span class="ln">{html.escape(l)}</span>' for l in HEAD[lang].split("\n"))
    lines = "".join(f'<span class="ln">{l}</span>' for l in rich(d[lang]["title"]).split("<br>"))
    body = f"""<div class="stage abs" style="inset:0">{parquet(1080, 1920)}<div class="shade"></div>
<div class="top abs"><span class="brand">{centre_disc(C['accent'])}<b>{html.escape(BRAND['name'][lang])}</b></span></div>
<div class="kicker abs"><span>{html.escape(KICKER[lang].format(n=d['round']))}</span></div>
<div class="head abs">{head}</div>
{''.join(rows)}<div class="line abs">{lines}</div></div>"""
    script = """
const SEP = '%(sep)s', INTRO = %(intro)d, STEP = %(step)d, END = %(end)d, FILL = 600;
const ease = 'cubic-bezier(.2,.8,.2,1)';
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
const rows = $$('.row'), N = rows.length;
const at = k => INTRO + (N - 1 - k) * STEP;  // the smallest crowd first, the biggest last
function setup() {
  anim($('.kicker'), [{opacity: 0}, {opacity: 1}], 0, 300);
  $$('.head .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(50px)'}, {opacity: 1, transform: 'none'}], 100 + i * 180, 420));
  rows.forEach((r, k) => {
    anim(r, [{opacity: 0, transform: 'translateX(120px)'}, {opacity: 1, transform: 'none'}], at(k), 320);
    anim(r.querySelector('.fill'), [{width: '0%%'}, {width: r.dataset.w + '%%'}], at(k) + 120, FILL, 'cubic-bezier(.3,.7,.2,1)');
  });
  anim(rows[0], [{transform: 'scale(1)'}, {transform: 'scale(1.04)'}, {transform: 'scale(1)'}], END + 150, 500, 'ease-out', 'forwards');
  for (let k = 1; k < N; k++) anim(rows[k], [{opacity: 1}, {opacity: .45}], END + 200, 400, 'linear', 'forwards');
  $$('.line .ln').forEach((el, i) => anim(el, [{opacity: 0, transform: 'translateY(50px)'}, {opacity: 1, transform: 'none'}], END + 500 + i * 220, 420));
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
  rows.forEach((r, k) => {
    const f = Math.max(0, Math.min(1, (ms - at(k) - 120) / FILL)), g = 1 - Math.pow(1 - f, 3);
    r.querySelector('.num b').textContent = Math.round(+r.dataset.crowd * g).toString().replace(/\B(?=(\d{3})+(?!\d))/g, SEP);
  });
  rows[0].classList.toggle('first', ms >= END + 150);
}
""" % dict(sep="," if lang == "en" else ".", intro=INTRO * 1000, step=STEP * 1000, end=end * 1000, outro_at=(total - render_reel.OUTRO) * 1000)
    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}{render_reel.outro_css()}</style></head>'
           f'<body>{body}{render_reel.outro_html(lang)}<script>{script}</script></body></html>')
    return doc, total


def soundtrack(folder, lang, total, out):
    """A crowd that grows row by row (emptiest to fullest), a soft tick per row, a roar and a hit for the fullest, the
    outro chord."""
    import numpy as np
    import render_reel
    from sfx import Mix
    d = json.loads((folder / "crowds.json").read_text())
    end, _ = timeline(d)
    m = Mix(total)
    n = len(d["arenas"])
    for k in range(n):  # k = 0 is the emptiest, revealed first
        t0 = INTRO + k * STEP
        level = .05 + .25 * (k + 1) / n
        x = m.noise(STEP + .4)
        crowd = m.lowpass(m.lowpass(x, 40), 20) * np.sin(np.linspace(0, np.pi, len(x)))
        m.put(level * 6 * crowd, t0)
        m.put(m.knock(.18), t0)
    x = m.noise(2.6)
    roar = m.lowpass(m.lowpass(x, 25), 12) * np.minimum(1, m.t(len(x)) / .15) * m.decay(len(x), 1.1)
    m.put(2.2 * roar, end + .1)
    m.put(.55 * m.tone(110, 48, .7, .25), end + .1)
    m.swoosh(end + .45, gain=.12, dur=.25)
    m.swoosh(end + .67, gain=.12, dur=.25)
    m.chord(total - render_reel.OUTRO + .1)
    return m.write(out)


def pick(season):
    """Saturday: the latest fully played round, once every game's crowd is confirmed -> crowds/<season>/round-NN/ with
    captions, queued (approved) for today at POST_AT on both Instagram accounts as Reels."""
    import collections
    import datetime as dt
    import subprocess
    import sys
    import zoneinfo
    from render_cards import ROOT
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    rounds = collections.defaultdict(list)
    for g in games:
        rounds[g["round"]].append(g)
    done = [r for r, gs in rounds.items() if all(g["played"] for g in gs)]
    if not done:
        print("No fully played round yet")
        return
    rnd = max(done)
    folder = ROOT / "crowds" / season / f"round-{rnd:02d}"
    if (folder / "crowds.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
    else:
        if not all(g["audienceConfirmed"] and g["venue"]["capacity"] for g in rounds[rnd]):
            print(f"Round {rnd}: not every crowd is confirmed yet")  # the second run tries again
            return
        posts(folder, get_round(folder, season, rnd, games))
        print(folder.relative_to(ROOT))
    queue = [sys.executable, str(ROOT / "scripts" / "publish_queue.py")]
    if folder.relative_to(ROOT).as_posix() not in subprocess.run(queue + ["list"], capture_output=True, text=True).stdout:
        today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Athens")).strftime("%Y-%m-%d")
        subprocess.run(queue + ["add", str(folder.relative_to(ROOT)), f"{today} {POST_AT}", "--langs", "reel-en,reel-el"],
                       check=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick"); p.add_argument("--season", default="E2026")
    g = sub.add_parser("get"); g.add_argument("folder", type=pathlib.Path); g.add_argument("--round", type=int)
    g.add_argument("--season", default="E2026")
    a = ap.parse_args()
    if a.cmd == "pick":
        return pick(a.season)
    posts(a.folder, get_round(a.folder, a.season, a.round))
    print(a.folder / "crowds.json")


if __name__ == "__main__":
    main()
