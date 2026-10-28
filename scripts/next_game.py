#!/usr/bin/env python3
"""Next game of Olympiacos / Panathinaikos: automatic, data-only post the day after each of their games.

  python3 scripts/next_game.py                 # build + queue (approved) today's posts, if any (used by CI)
  python3 scripts/next_game.py --team OLY --force --no-queue   # build one now, for a preview

The day after OLY or PAN played, their next game gets a carousel on the Greek Instagram account (@parke.hoops) and an
English X post: 1) "Ο επόμενος αγώνας του Ολυμπιακού", 2) the opponent, 3) day, time and arena, 4) the numbers
(position and record, home/away record, last-5 form, points per game, the last meeting). Everything comes from the
EuroLeague API, so it goes out without approval (the owner's decision, 2026-10-28), at POST_AT Athens.
Folder: nextgame/<season>/<team>-<game code>/. If both clubs' next game is the derby, only one post is made.
"""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import zoneinfo

from round_digest import get
from round_status import tip

ROOT = pathlib.Path(__file__).resolve().parent.parent
ATHENS = zoneinfo.ZoneInfo("Europe/Athens")
CLUBS = json.loads((ROOT / "assets" / "clubs.json").read_text())
TEAMS = {"OLY": "Ολυμπιακού", "PAN": "Παναθηναϊκού"}  # genitive, for the title
POST_AT = "18:00"
DAYS_EL = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
MONTHS_EL = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
             "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]


def el(code):
    return CLUBS[code]["el"]


def en(code):
    return CLUBS[code]["en"]


def standings(season, games):
    played = [g["round"] for g in games if g["played"]]
    if not played:
        return {}
    data = get(f"/v3/competitions/E/seasons/{season}/rounds/{max(played)}/basicstandings")
    return {t["club"]["code"]: t for t in data["teams"]}


def last_meeting(season, team, opp, before):
    """The latest finished game between the two, this season or last."""
    prev = f"E{int(season[1:]) - 1}"
    found = []
    for s in (season, prev):
        try:
            gs = get(f"/v2/competitions/E/seasons/{s}/games")["data"]
        except Exception:
            continue
        found += [g for g in gs if g["played"] and {g["local"]["club"]["code"], g["road"]["club"]["code"]} == {team, opp}
                  and tip(g) < before]
    return max(found, key=tip) if found else None


def form(games, team, before):
    """The team's last five results from the game list, oldest first (Ν = win, Η = loss)."""
    done = sorted([g for g in games if g["played"] and tip(g) < before
                   and team in (g["local"]["club"]["code"], g["road"]["club"]["code"])], key=tip)[-5:]
    out = []
    for g in done:
        me, op = ("local", "road") if g["local"]["club"]["code"] == team else ("road", "local")
        out.append("Ν" if g[me]["score"] > g[op]["score"] else "Η")
    return "-".join(out)


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def ppg(t):
    return f"{t['pointsFor'] / t['gamesPlayed']:.1f}".replace(".", ",") if t.get("gamesPlayed") else "-"


def build(season, team, g, table, folder, games):
    home, away = g["local"]["club"]["code"], g["road"]["club"]["code"]
    opp = away if home == team else home
    at_home = home == team
    t = tip(g).astimezone(ATHENS)
    venue = (g.get("venue") or {}).get("name") or ""
    venue_t = venue.title() if venue.isupper() else venue
    me, them = table.get(team, {}), table.get(opp, {})
    when_el = f"{DAYS_EL[t.weekday()]} {t.day} {MONTHS_EL[t.month - 1]}"

    items = []
    if me and them:
        items.append({"tag": "Βαθμολογία", "text": f"{el(team)} {me['position']}η θέση ({me['gamesWon']}-{me['gamesLost']}) · "
                                                   f"{el(opp)} {them['position']}η ({them['gamesWon']}-{them['gamesLost']})"})
        items.append({"tag": "Εντός · εκτός", "text": (f"{el(team)} εντός {me['homeRecord']} · {el(opp)} εκτός {them['awayRecord']}"
                                                         if at_home else
                                                         f"{el(team)} εκτός {me['awayRecord']} · {el(opp)} εντός {them['homeRecord']}")})
        items.append({"tag": "Τελευταία 5 (→ πιο πρόσφατο)",
                      "text": f"{el(team)} {form(games, team, tip(g))} · {el(opp)} {form(games, opp, tip(g))}"})
        items.append({"tag": "Πόντοι ανά αγώνα", "text": f"{el(team)} {ppg(me)} · {el(opp)} {ppg(them)}"})
    lm = last_meeting(season, team, opp, tip(g))
    if lm:
        lh, la = lm["local"]["club"]["code"], lm["road"]["club"]["code"]
        d = tip(lm).astimezone(ATHENS)
        items.append({"tag": "Τελευταία αναμέτρηση", "text": f"{el(lh)} {lm['local']['score']}-{lm['road']['score']} {el(la)} "
                                                            f"({d.day}/{d.month}/{d.year})"})

    spec_el = {"lang": "el", "round_label": f"{g['round']}η αγωνιστική", "ig": [
        {"type": "hook", "badges": [team], "kicker": "Επόμενος αγώνας",
         "title": f"Ο επόμενος\nαγώνας του\n*{TEAMS[team]}*", "subtitle": f"{g['round']}η αγωνιστική EuroLeague"},
        {"type": "hook", "badges": [opp], "kicker": "Αντίπαλος",
         "title": f"*{el(opp)}*", "subtitle": "Στο σπίτι μας" if at_home else "Εκτός έδρας"},
        {"type": "list", "kicker": "Πότε και πού", "items": [
            {"tag": "Ημέρα", "text": when_el}, {"tag": "Ώρα", "text": f"{t:%H:%M}"},
            {"tag": "Γήπεδο", "text": f"{venue_t} · έδρα {'μας' if at_home else 'του αντιπάλου'}"}]},
        {"type": "list", "kicker": "Τα νούμερα", "items": items[:5]},
    ]}
    from countdown import tags
    tg = tags(home, away)
    me_en = f"{en(team)} {me['gamesWon']}-{me['gamesLost']} ({ordinal(me['position'])})" if me else en(team)
    them_en = f"{en(opp)} {them['gamesWon']}-{them['gamesLost']} ({ordinal(them['position'])})" if them else en(opp)
    spec_en = {"lang": "en", "round_label": f"Round {g['round']}", "ig": [], "x": {
        "type": "list", "kicker": f"Next up · {en(team)}", "items": [
            {"tag": "Opponent", "text": f"{'vs' if at_home else 'at'} {en(opp)}"},
            {"tag": "When", "text": f"{t:%a %d %b} · {t:%H:%M} Athens"},
            {"tag": "Where", "text": venue_t},
            {"tag": "Form", "text": f"{me_en} · {them_en}"}]}}
    folder.mkdir(parents=True, exist_ok=True)
    for lang, spec in (("el", spec_el), ("en", spec_en)):
        (folder / f"cards.{lang}.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "render_cards.py"), str(folder / f"cards.{lang}.json")],
                       check=True, stdout=subprocess.DEVNULL)
    hashtags_el = " ".join(tags(home, away)["ig_el"]) + " #μπάσκετ #ParquetHoops"
    (folder / "post.el.md").write_text(f"""# Ο επόμενος αγώνας του {TEAMS[team]}: {el(home)} - {el(away)}

## Instagram caption
Ο επόμενος αγώνας του {TEAMS[team]}. 🏀

{el(home)} - {el(away)}
{when_el}, {t:%H:%M}
{venue_t}

Πώς το βλέπετε; 👇

{hashtags_el}
""")
    (folder / "post.en.md").write_text(f"""# Next game: {en(home)} vs {en(away)}

## X
Next up for {en(team)}: {'vs' if at_home else 'at'} {en(opp)}.

{t:%a %d %b} · {t:%H:%M} Athens · {venue_t}
{me_en} · {them_en}

{' '.join(tg['x'])}
""")
    return folder


def due_posts(season, now):
    """(team, next game) for every team that played yesterday (Athens date)."""
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    yesterday = (now.astimezone(ATHENS) - dt.timedelta(days=1)).date()
    out, seen = [], set()
    for team in TEAMS:
        mine = sorted([g for g in games if team in (g["local"]["club"]["code"], g["road"]["club"]["code"])], key=tip)
        if not any(g["played"] and tip(g).astimezone(ATHENS).date() == yesterday for g in mine):
            continue
        upcoming = [g for g in mine if not g["played"] and tip(g) > now]
        if upcoming and upcoming[0]["gameCode"] not in seen:  # the derby gets one post, not two
            seen.add(upcoming[0]["gameCode"])
            out.append((team, upcoming[0]))
    return games, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="E2026")
    ap.add_argument("--team", choices=sorted(TEAMS), help="build this team's next game now (preview)")
    ap.add_argument("--force", action="store_true", help="with --team: ignore 'played yesterday'")
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    if a.team and a.force:
        games = get(f"/v2/competitions/E/seasons/{a.season}/games")["data"]
        nxt = sorted([g for g in games if a.team in (g["local"]["club"]["code"], g["road"]["club"]["code"])
                      and not g["played"]], key=tip)
        posts = [(a.team, nxt[0])] if nxt else []
    else:
        games, posts = due_posts(a.season, now)
    if not posts:
        print("No next-game post today")
        return
    table = standings(a.season, games)
    today = now.astimezone(ATHENS).strftime("%Y-%m-%d")
    for team, g in posts:
        folder = ROOT / "nextgame" / a.season / f"{team.lower()}-{g['gameCode']}"
        if (folder / "post.el.md").exists() and not a.force:
            print(f"Already built: {folder.relative_to(ROOT)}")
        else:
            build(a.season, team, g, table, folder, games)
            print(folder.relative_to(ROOT))
        if not a.no_queue:
            queue = [sys.executable, str(ROOT / "scripts" / "publish_queue.py")]
            if folder.relative_to(ROOT).as_posix() not in subprocess.run(queue + ["list"], capture_output=True, text=True).stdout:
                subprocess.run(queue + ["add", str(folder.relative_to(ROOT)), f"{today} {POST_AT}", "--langs", "el,x"], check=True)


if __name__ == "__main__":
    main()
