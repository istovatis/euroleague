#!/usr/bin/env python3
"""Fetch completed EuroLeague games and rank story candidates for the posts.

Usage:
  python3 scripts/round_digest.py --round 7 --date 2026-10-21   # one game day -> round-07/day-K/digest.json
  python3 scripts/round_digest.py --round 7 --highlight         # whole round + table after it -> round-07/highlight/
  python3 scripts/round_digest.py [--round N]                    # whole round -> round-NN/digest.json
Without --round, picks the latest round where every game is played.
Game days are Athens calendar dates; day K is the K-th date the round is played on.
"""
import argparse
import json
import pathlib
import sys
import urllib.request

from round_status import athens_date, round_days

API = "https://api-live.euroleague.net"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def latest_complete_round(games):
    rounds = {}
    for g in games:
        rounds.setdefault(g["round"], []).append(g["played"])
    done = [r for r, played in rounds.items() if all(played)]
    return max(done)


def standings_before(season, rnd):
    if rnd <= 1:
        return {}
    data = get(f"/v3/competitions/E/seasons/{season}/rounds/{rnd - 1}/basicstandings")
    return {t["club"]["code"]: t for t in data["teams"]}


def standings_after(season, rnd):
    data = get(f"/v3/competitions/E/seasons/{season}/rounds/{rnd}/basicstandings")
    return [{"position": t["position"], "code": t["club"]["code"], "name": t["club"]["editorialName"],
             "record": f'{t["gamesWon"]}-{t["gamesLost"]}', "change": t.get("positionChange"),
             "last5": t.get("last5Form")} for t in data["teams"]]


def player_line(p, team, opp, won):
    s = p["stats"]
    per = p["player"]["person"]
    return {
        "name": per["name"],
        "alias": per.get("jerseyName") or per["name"],
        "country": per["country"]["name"] if per.get("country") else None,
        "team": team, "opponent": opp, "won": won,
        "min": round(s["timePlayed"] / 60, 1),
        "pir": s["valuation"], "pts": s["points"],
        "reb": s["totalRebounds"], "ast": s["assistances"],
        "stl": s["steals"], "blk": s["blocksFavour"], "tov": s["turnovers"],
        "fg2": f'{int(s["fieldGoalsMade2"])}/{int(s["fieldGoalsAttempted2"])}',
        "fg3": f'{int(s["fieldGoalsMade3"])}/{int(s["fieldGoalsAttempted3"])}',
        "ft": f'{int(s["freeThrowsMade"])}/{int(s["freeThrowsAttempted"])}',
        "plus_minus": s["plusMinus"],
        "headshot": p["player"].get("images", {}).get("headshot"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="E2026")
    ap.add_argument("--round", type=int)
    ap.add_argument("--date", help="Athens date YYYY-MM-DD: only that game day")
    ap.add_argument("--highlight", action="store_true", help="whole round plus the table after it")
    a = ap.parse_args()

    games = get(f"/v2/competitions/E/seasons/{a.season}/games")["data"]
    rnd = a.round or latest_complete_round(games)
    table = standings_before(a.season, rnd)
    out = {"season": a.season, "round": rnd, "games": [], "players": []}
    selected = [g for g in games if g["round"] == rnd]
    days = round_days(games, rnd)
    if a.date:
        if a.date not in days:
            sys.exit(f"Round {rnd} has no games on {a.date} (game days: {', '.join(days)})")
        selected = [g for g in selected if athens_date(g) == a.date]
        out.update(date=a.date, day=days.index(a.date) + 1, days=len(days))
    if not all(g["played"] for g in selected):
        sys.exit(f"Not all games are played yet ({sum(g['played'] for g in selected)}/{len(selected)})")
    if a.highlight:
        out["days"] = len(days)
        out["standings_after"] = standings_after(a.season, rnd)

    for g in sorted(selected, key=lambda g: g["date"]):
        box = get(f"/v2/competitions/E/seasons/{a.season}/games/{g['gameCode']}/stats")
        sides = {}
        for side in ("local", "road"):
            c = g[side]
            p = c["partials"]
            sides[side] = {
                "code": c["club"]["code"], "name": c["club"]["editorialName"],
                "score": c["score"],
                "after_q3": p["partials1"] + p["partials2"] + p["partials3"],
                "quarters": [p["partials1"], p["partials2"], p["partials3"], p["partials4"]],
                "overtimes": [v for _, v in sorted((p.get("extraPeriods") or {}).items(), key=lambda kv: int(kv[0]))],
                "coach": box[side]["coach"]["name"],
                "record_before": (lambda t: f'{t["gamesWon"]}-{t["gamesLost"]}' if t else "0-0")(table.get(c["club"]["code"])),
                "pos_before": table.get(c["club"]["code"], {}).get("position"),
            }
        h, r = sides["local"], sides["road"]
        win, lose = (h, r) if h["score"] > r["score"] else (r, h)
        margin = win["score"] - lose["score"]
        q3_deficit = lose["after_q3"] - win["after_q3"]  # >0 means winner trailed after Q3
        pos_gap = (win["pos_before"] or 0) - (lose["pos_before"] or 0)  # >0: lower-ranked team won
        ot = bool(g["local"]["partials"].get("extraPeriods"))
        game = {
            "code": g["gameCode"], "date": g["date"], "venue": g["venue"]["name"] if g.get("venue") else None,
            "home": h, "away": r, "winner": win["name"], "loser": lose["name"],
            "road_win": win is r, "margin": margin, "overtime": ot,
            "winner_trailed_after_q3_by": max(q3_deficit, 0),
            "standings_gap": pos_gap,
            "upset_score": max(pos_gap, 0) + (3 if win is r else 0) + (2 if q3_deficit > 0 else 0),
            "drama_score": (10 - min(margin, 10)) + (5 if ot else 0) + max(q3_deficit, 0) / 2,
        }
        out["games"].append(game)
        for side, opp in (("local", "road"), ("road", "local")):
            team, oppname = sides[side]["name"], sides[opp]["name"]
            for p in box[side]["players"]:
                if p["stats"]["timePlayed"]:
                    out["players"].append(player_line(p, team, oppname, sides[side] is win))

    out["players"].sort(key=lambda p: -p["pir"])
    dest = ROOT / "rounds" / a.season / f"round-{rnd:02d}"
    if a.date:
        dest = dest / f"day-{out['day']}"
    elif a.highlight:
        dest = dest / "highlight"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "digest.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    label = f"day {out['day']}/{out['days']} ({a.date})" if a.date else ("highlight" if a.highlight else "")
    print(f"== {a.season} Round {rnd} {label} -> {dest / 'digest.json'}\n")
    for g in out["games"]:
        h, r = g["home"], g["away"]
        flags = [f for f, on in (("ROAD WIN", g["road_win"]), ("OT", g["overtime"]),
                 (f"comeback from -{g['winner_trailed_after_q3_by']} after Q3", g["winner_trailed_after_q3_by"]),
                 (f"upset: #{max(h['pos_before'] or 0, r['pos_before'] or 0)} beat higher seed", g["standings_gap"] >= 5)) if on]
        print(f"{h['name']} ({h['record_before']}) {h['score']}-{r['score']} {r['name']} ({r['record_before']})  {'; '.join(flags)}")
    print("\nTop PIR:")
    for p in out["players"][:8]:
        print(f"  {p['pir']:>4.0f} PIR  {p['name']} ({p['team']}{' W' if p['won'] else ' L'} vs {p['opponent']}): "
              f"{p['pts']:.0f}p {p['reb']:.0f}r {p['ast']:.0f}a, 2P {p['fg2']} 3P {p['fg3']} FT {p['ft']}")
    print("\nMost upset-y:", max(out["games"], key=lambda g: g["upset_score"])["winner"])
    print("Most dramatic:", max(out["games"], key=lambda g: g["drama_score"])["winner"])
    if a.highlight:
        print("\nTable after the round:")
        for t in out["standings_after"][:6]:
            print(f"  {t['position']:>2}. {t['name']} {t['record']} ({t['change']})")


if __name__ == "__main__":
    main()
