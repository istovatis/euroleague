#!/usr/bin/env python3
"""Final-score posts: published automatically, minutes after each game ends (no approval step).

  python3 scripts/final_scores.py                   # post every newly finished game (used by CI)
  python3 scripts/final_scores.py --dry-run         # render and print, post nothing
  python3 scripts/final_scores.py --game 57 --dry-run   # one game by its code, even an old one

Each game gets finals/<season>/round-NN/<code>-<HOME>-<AWAY>/: cards.en.json / cards.el.json, post.en.md and
the rendered cards (x.png for X, story.png for an Instagram Story on each account). Channels: X (EN) and an
Instagram Story on @parquet.hoops and @parke.hoops. Every channel writes its own published.*.json, so a
game is never posted twice and a failed channel is retried on the next run.

Everything in these posts is data straight from the EuroLeague API (score, overtimes, top scorers), which
is why the owner allowed them to go out without approval (2026-10-20). Only games that tipped off in the
last MAX_AGE hours qualify, so a first run never floods old results. FINALS_ENABLED=false (repository
variable) pauses them; X_ENABLED=false pauses only X.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

from round_digest import get
from round_status import tip

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLUBS = json.loads((ROOT / "assets" / "clubs.json").read_text())
FIRST_ROUND = 7  # the season's first round with final-score posts
MAX_AGE = dt.timedelta(hours=8)


def surname(person):
    """'CARR, MARCUS' -> 'Carr'; 'DE COLO' -> 'De Colo', 'MCCOLLUM' -> 'McCollum'."""
    last = person["name"].split(",")[0].strip().title()
    return re.sub(r"\bMc(\w)", lambda m: "Mc" + m.group(1).upper(), last)


def top_scorer(box_side):
    players = [p for p in box_side["players"] if p["stats"]["points"] is not None]
    p = max(players, key=lambda p: (p["stats"]["points"], p["stats"]["valuation"]))
    return surname(p["player"]["person"]), int(p["stats"]["points"])


def game_facts(season, g):
    sides = {}
    for side in ("local", "road"):
        c = g[side]
        ot = [v for _, v in sorted((c["partials"].get("extraPeriods") or {}).items(), key=lambda kv: int(kv[0]))]
        sides[side] = {"code": c["club"]["code"], "name": c["club"]["abbreviatedName"], "score": int(c["score"]),
                       "quarters": [c["partials"][f"partials{i}"] for i in range(1, 5)] + ot}
    try:
        box = get(f"/v2/competitions/E/seasons/{season}/games/{g['gameCode']}/stats")
        for side in sides:
            sides[side]["top"] = top_scorer(box[side])
    except Exception as e:  # the box score can lag the result; post without the scorers
        print(f"warning: no box score for game {g['gameCode']} ({e})", file=sys.stderr)
    h, r = sides["local"], sides["road"]
    win, lose = (h, r) if h["score"] > r["score"] else (r, h)
    margin = win["score"] - lose["score"]
    ots = len(h["quarters"]) - 4
    return {"round": g["round"], "code": g["gameCode"], "home": h, "away": r, "win": win, "lose": lose,
            "margin": margin, "overtimes": ots, "road_win": win is r}


def note(f, lang):
    en = lang == "en"
    if f["overtimes"]:
        n = f["overtimes"]
        return ("After overtime" if n == 1 else f"After {n} overtimes") if en else \
            ("Στην παράταση" if n == 1 else f"Μετά από {n} παρατάσεις")
    if f["margin"] <= 3:
        return "Down to the wire" if en else "Στο νήμα"
    if f["margin"] >= 20:
        return f"By {f['margin']}" if en else f"Με {f['margin']} πόντους"
    if f["road_win"]:
        return "Road win" if en else "Νίκη εκτός έδρας"
    return ""


def club_name(side, lang):
    return (CLUBS.get(side["code"], {}).get("el") if lang == "el" else None) or side["name"]


def card(f, lang):
    en = lang == "en"
    lines = [(f"{s['top'][0]} · {club_name(s, lang)}", f"{s['top'][1]} {'PTS' if en else 'ΠΟΝΤΟΙ'}")
             for s in (f["win"], f["lose"]) if s.get("top")]
    c = {"type": "score", "kicker": "Final" if en else "Τελικό", "badges": [f["win"]["code"], f["lose"]["code"]],
         "sides": [{"team": club_name(s, lang), "score": s["score"], "won": s is f["win"]} for s in (f["win"], f["lose"])],
         "lines": lines}
    if note(f, lang):
        c["note"] = note(f, lang)
    return c


def x_text(f):
    w, l = f["win"], f["lose"]
    out = [f"FINAL | Round {f['round']}", ""]
    out += [f"{s['name']} {s['score']}" + (f" ({s['top'][0]} {s['top'][1]})" if s.get("top") else "") for s in (w, l)]
    if note(f, "en"):
        out += ["", note(f, "en") + "."]
    return "\n".join(out + ["", "#EuroLeague"])


def build(season, f, folder):
    folder.mkdir(parents=True, exist_ok=True)
    label = {"en": f"Round {f['round']}", "el": f"{f['round']}η αγωνιστική"}
    for lang in ("en", "el"):
        spec = {"lang": lang, "round_label": label[lang], "ig": [], "story": card(f, lang)}
        if lang == "en":
            spec["x"] = card(f, lang)
        (folder / f"cards.{lang}.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "render_cards.py"), str(folder / f"cards.{lang}.json")],
                       check=True, stdout=subprocess.DEVNULL)
    (folder / "post.en.md").write_text(f"# Final: {f['win']['name']} {f['win']['score']}, "
                                       f"{f['lose']['name']} {f['lose']['score']}\n\n## X\n{x_text(f)}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="E2026")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--game", type=int, help="one game by its code (ignores the age and round limits)")
    a = ap.parse_args()
    if os.environ.get("FINALS_ENABLED", "").strip().lower() == "false":
        print("Final-score posts are paused (FINALS_ENABLED=false)")
        return

    now = dt.datetime.now(dt.timezone.utc)
    games = get(f"/v2/competitions/E/seasons/{a.season}/games")["data"]
    if a.game:
        due = [g for g in games if g["gameCode"] == a.game]
    else:
        due = [g for g in games if g["played"] and g["round"] >= FIRST_ROUND and now - tip(g) < MAX_AGE]
    sys.path.insert(0, str(ROOT / "scripts"))
    import publish_x

    failed = False
    for g in sorted(due, key=tip):
        if not (g["local"]["score"] and g["road"]["score"]):
            continue
        folder = ROOT / "finals" / a.season / f"round-{g['round']:02d}" / \
            f"{g['gameCode']}-{g['local']['club']['code']}-{g['road']['club']['code']}"
        channels = (["x"] if publish_x.configured() else []) + ["story-en", "story-el"]
        if not a.dry_run and all((folder / f"published.{c}.json").exists() for c in channels):
            continue
        f = game_facts(a.season, g)
        if not (folder / "post.en.md").exists() or a.dry_run:
            build(a.season, f, folder)
        print(f"== {folder.relative_to(ROOT)}\n{x_text(f)}\n", flush=True)
        if a.dry_run:
            continue
        for c in channels:
            if (folder / f"published.{c}.json").exists():
                continue
            if c == "x":
                cmd = [sys.executable, str(ROOT / "scripts" / "publish_x.py"), str(folder.relative_to(ROOT)), "--yes"]
            else:
                lang = c.split("-")[1]
                cmd = [sys.executable, "-c", "import sys, pathlib; sys.path.insert(0, 'scripts'); import publish_instagram as ig; "
                       f"ig.publish_story(pathlib.Path({str(folder)!r}), {lang!r}, pathlib.Path({str(folder / 'cards' / lang / 'story.png')!r}))"]
            failed |= subprocess.run(cmd, cwd=ROOT).returncode != 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
