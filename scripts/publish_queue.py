#!/usr/bin/env python3
"""Instagram publishing queue (publish/queue.json), run by the GitHub Actions workflow.

  python3 scripts/publish_queue.py add <story> "YYYY-MM-DD HH:MM" [--langs en,el]   # time is Athens local
  python3 scripts/publish_queue.py list
  python3 scripts/publish_queue.py run [--dry-run]     # publish every due, unpublished entry (used by CI)

An entry is published once per language: publish_instagram.py writes <story>/published.<lang>.json and
refuses to post a story twice, so re-running is always safe. Tokens come from IG_TOKEN_EN / IG_TOKEN_EL
(GitHub Actions secrets) or the macOS Keychain when run locally.
"""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "publish" / "queue.json"
ATHENS = zoneinfo.ZoneInfo("Europe/Athens")


def load():
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else []


def save(entries):
    QUEUE.parent.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(sorted(entries, key=lambda e: e["when"]), indent=2, ensure_ascii=False) + "\n")


def done(entry, lang):
    return (ROOT / entry["story"] / f"published.{lang}.json").exists()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("story")
    a.add_argument("when", help='Athens local time, "YYYY-MM-DD HH:MM"')
    a.add_argument("--langs", default="en,el")
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    entries = load()

    if args.cmd == "add":
        story = pathlib.Path(args.story)
        if not (ROOT / story / "post.en.md").exists():
            sys.exit(f"Not a story folder: {story}")
        when = dt.datetime.strptime(args.when, "%Y-%m-%d %H:%M").replace(tzinfo=ATHENS)
        entries = [e for e in entries if e["story"] != story.as_posix()]
        entries.append({"story": story.as_posix(), "when": when.isoformat(), "langs": args.langs.split(",")})
        save(entries)
        print(f"Queued {story} for {when:%a %d %b %H:%M} Athens ({', '.join(args.langs.split(','))})")
        return

    if args.cmd == "list":
        for e in entries:
            state = " ".join(f"{l}:{'done' if done(e, l) else 'pending'}" for l in e["langs"])
            print(f"{dt.datetime.fromisoformat(e['when']):%a %d %b %H:%M}  {e['story']}  {state}")
        return

    now = dt.datetime.now(dt.timezone.utc)
    failed = False
    for e in entries:
        if dt.datetime.fromisoformat(e["when"]) > now:
            continue
        for lang in e["langs"]:
            if done(e, lang):
                continue
            print(f"== {e['story']} [{lang}] due {e['when']}", flush=True)
            cmd = [sys.executable, str(ROOT / "scripts" / "publish_instagram.py"), e["story"], lang]
            if not args.dry_run:
                cmd.append("--yes")
            failed |= subprocess.run(cmd).returncode != 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
