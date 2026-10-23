#!/usr/bin/env python3
"""MVP poll on X, Saturdays around 20:00 Athens, fully automatic (the owner's decision, 2026-10-23).

  python3 scripts/mvp_poll.py              # post the poll if it's time and the week's lineup is out (used by CI)
  python3 scripts/mvp_poll.py --dry-run    # print the poll, post nothing
  python3 scripts/mvp_poll.py --now        # ignore the time window

The options come from the latest Lineup of the week (lineups/<season>/round-NN/lineup.json), and only once that
post is published. X polls take at most 4 options, so the 4 with the highest PIR are the options and the fifth is
named in the text. Text only, no media; the poll runs 24 hours. Writes published.poll.json in the lineup folder,
so it is posted once.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import publish_x  # noqa: E402

ATHENS = zoneinfo.ZoneInfo("Europe/Athens")
WINDOW = (20, 23)  # post between 20:00 and 23:00 Athens; the cron fires several times so a dropped run doesn't matter


def latest_lineup():
    folders = sorted((ROOT / "lineups").glob("*/round-*/lineup.json"))
    return folders[-1].parent if folders else None


def label(p):
    """A poll option: 25 characters at most."""
    for text in (f"{p['first']} {p['last']}", p["last"]):
        if len(text) <= 25:
            return text
    return p["last"][:25]


def build(folder):
    data = json.loads((folder / "lineup.json").read_text())
    ranked = sorted(data["players"], key=lambda p: (-p["pir"], -p.get("pts", 0)))
    options, fifth = ranked[:4], ranked[4]
    # Three hashtags at most (more reads as spam on X): the competition, MVP, and the PIR leader's club, whose fans
    # are the likeliest to vote and share.
    from countdown import tags
    club_tag = tags(ranked[0]["club"], ranked[0]["club"])["ig"][2]
    text = (f"Round {data['round']} MVP? 🏆\n\nVote from our Lineup of the week.\n"
            f"X polls take four: {fifth['first']} {fifth['last']} fans, reply 👇\n\n#EuroLeague #MVP {club_tag}")
    return text, [label(p) for p in options]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", action="store_true", help="ignore the Saturday-evening time window")
    a = ap.parse_args()

    now = dt.datetime.now(ATHENS)
    if not (a.now or a.dry_run) and not (now.weekday() == 5 and WINDOW[0] <= now.hour < WINDOW[1]):
        print(f"Not poll time ({now:%a %H:%M} Athens)")
        return
    folder = latest_lineup()
    if not folder:
        print("No lineup yet")
        return
    record = folder / "published.poll.json"
    if record.exists():
        print(f"Already posted: {json.loads(record.read_text())['url']}")
        return
    if not any((folder / f"published.{c}.json").exists() for c in ("x", "en", "el")) and not a.dry_run:
        print(f"{folder.relative_to(ROOT)} isn't published yet: no poll until it is")
        return
    text, options = build(folder)
    print(f"{text}\n\nOptions: {options} ({publish_x.x_length(text)} chars)")
    if a.dry_run:
        return
    if not publish_x.configured():
        sys.exit("X is not set up or paused (X_ENABLED=false)")
    creds = publish_x.credentials()
    user = publish_x.me(creds)
    body = {"text": text, "poll": {"options": options, "duration_minutes": 24 * 60}}
    tweet = publish_x.request("POST", f"{publish_x.API}/tweets", creds, json.dumps(body).encode(), "application/json")["data"]
    url = f"https://x.com/{user['username']}/status/{tweet['id']}"
    record.write_text(json.dumps({"id": tweet["id"], "url": url, "options": options,
                                  "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    from publish_instagram import commit_record
    commit_record(record)
    print(f"Published: {url}")


if __name__ == "__main__":
    main()
