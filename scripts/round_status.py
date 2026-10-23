#!/usr/bin/env python3
"""Calendar helpers for the per-day routines.

  python3 scripts/round_status.py 7                        # exit 0 if round 7 is fully played, else 1
  python3 scripts/round_status.py 7 --date 2026-10-21      # same, for one game day (Athens date)
  python3 scripts/round_status.py 7 --date 2026-10-21 --wait   # re-check every 5 min for up to 100 min
  python3 scripts/round_status.py --schedule               # upcoming game days: round, day k/K, date, last tip-off, run time (UTC)
  python3 scripts/round_status.py --pending                # played game days / rounds not drafted yet (daily safety net)
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.request
import zoneinfo

API = "https://api-live.euroleague.net/v2/competitions/E/seasons/{season}/games"
ROOT = pathlib.Path(__file__).resolve().parent.parent
ATHENS = zoneinfo.ZoneInfo("Europe/Athens")
RUN_AFTER_LAST_TIP = dt.timedelta(hours=1, minutes=30)  # a game takes ~1h45-2h; --wait (every 5 min, 100 min) waits for the finish


def games(season):
    req = urllib.request.Request(API.format(season=season), headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


def tip(g):
    return dt.datetime.fromisoformat(g["utcDate"].replace("Z", "+00:00"))


def athens_date(g):
    return tip(g).astimezone(ATHENS).date().isoformat()


def round_days(all_games, rnd):
    """The round's game days (Athens dates), in order: day 1, day 2, ..."""
    return sorted({athens_date(g) for g in all_games if g["round"] == rnd})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round", nargs="?", type=int)
    ap.add_argument("--season", default="E2026")
    ap.add_argument("--date")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--pending", action="store_true")
    a = ap.parse_args()

    if a.schedule or a.pending:
        all_games = games(a.season)
        by_day = collections.defaultdict(list)
        for g in all_games:
            by_day[(g["round"], athens_date(g))].append(g)
        now = dt.datetime.now(dt.timezone.utc)
        for rnd in sorted({r for r, _ in by_day}):
            days = round_days(all_games, rnd)
            folder = ROOT / "rounds" / a.season / f"round-{rnd:02d}"
            for k, day in enumerate(days, 1):
                gs = by_day[(rnd, day)]
                played = all(g["played"] for g in gs)
                if a.schedule and not played:
                    run = max(map(tip, gs)) + RUN_AFTER_LAST_TIP
                    if run > now:
                        print(f"{rnd}\t{k}\t{len(days)}\t{day}\t{max(map(tip, gs)):%Y-%m-%dT%H:%M:%SZ}\t{run:%Y-%m-%dT%H:%M:%SZ}")
                if a.pending and played and rnd >= 7 and not (folder / f"day-{k}" / "README.md").exists():
                    print(f"day\tround {rnd}\tday {k}/{len(days)}\t{day}")
            if a.pending and rnd >= 7 and all(g["played"] for d in days for g in by_day[(rnd, d)]) \
                    and not (folder / "highlight" / "README.md").exists():
                print(f"highlight\tround {rnd}")
        return

    if a.round is None:
        ap.error("round number required")
    for attempt in range(21 if a.wait else 1):
        gs = [g for g in games(a.season) if g["round"] == a.round and (not a.date or athens_date(g) == a.date)]
        played = sum(g["played"] for g in gs)
        print(f"Round {a.round}{' on ' + a.date if a.date else ''}: {played}/{len(gs)} games played")
        if gs and played == len(gs):
            sys.exit(0)
        if a.wait and attempt < 15:
            time.sleep(300)
    sys.exit(1)


if __name__ == "__main__":
    main()
