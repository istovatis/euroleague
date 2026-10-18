#!/usr/bin/env python3
"""Calendar helpers for the per-round routines.

  python3 scripts/round_status.py 7              # exit 0 if round 7 is fully played, else 1
  python3 scripts/round_status.py --wait 7       # re-check every 5 min for up to 75 min
  python3 scripts/round_status.py --schedule     # each upcoming round: last tip-off and run time (UTC)
"""
import argparse
import collections
import datetime as dt
import json
import sys
import time
import urllib.request

API = "https://api-live.euroleague.net/v2/competitions/E/seasons/{season}/games"
RUN_AFTER_LAST_TIP = dt.timedelta(hours=2, minutes=15)  # a game takes ~2h; this is roughly the final buzzer


def games(season):
    req = urllib.request.Request(API.format(season=season), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


def by_round(season):
    rounds = collections.defaultdict(list)
    for g in games(season):
        rounds[g["round"]].append(g)
    return rounds


def status(season, rnd):
    gs = by_round(season)[rnd]
    return sum(g["played"] for g in gs), len(gs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round", nargs="?", type=int)
    ap.add_argument("--season", default="E2026")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    a = ap.parse_args()

    if a.schedule:
        now = dt.datetime.now(dt.timezone.utc)
        for rnd, gs in sorted(by_round(a.season).items()):
            if all(g["played"] for g in gs):
                continue
            last = max(dt.datetime.fromisoformat(g["utcDate"].replace("Z", "+00:00")) for g in gs)
            run = last + RUN_AFTER_LAST_TIP
            if run > now:
                confirmed = all(g["confirmedDate"] and g["confirmedHour"] for g in gs)
                print(f"{rnd}\t{last:%Y-%m-%dT%H:%M:%SZ}\t{run:%Y-%m-%dT%H:%M:%SZ}\t{'confirmed' if confirmed else 'TBC'}")
        return

    if a.round is None:
        ap.error("round number required")
    for attempt in range(16 if a.wait else 1):
        played, total = status(a.season, a.round)
        print(f"Round {a.round}: {played}/{total} games played")
        if total and played == total:
            sys.exit(0)
        if a.wait and attempt < 15:
            time.sleep(300)
    sys.exit(1)


if __name__ == "__main__":
    main()
