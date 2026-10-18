#!/usr/bin/env python3
"""Instagram publishing queue (publish/queue.json), run by the GitHub Actions workflow.

  python3 scripts/publish_queue.py add <story> "YYYY-MM-DD HH:MM" [--langs en,el] [--draft]   # time is Athens local
  python3 scripts/publish_queue.py approve <match> [--when "YYYY-MM-DD HH:MM"]   # approve drafts whose path contains <match> ("all" = every draft)
  python3 scripts/publish_queue.py list
  python3 scripts/publish_queue.py run [--dry-run]     # publish every due, unpublished entry (used by CI)
  python3 scripts/publish_queue.py check               # confirm each language's token works and matches its account

An entry is published once per language: publish_instagram.py writes <story>/published.<lang>.json and
refuses to post a story twice, so re-running is always safe. Tokens come from IG_TOKEN_EN / IG_TOKEN_EL
(GitHub Actions secrets) or the macOS Keychain when run locally.

The drafting routines queue every post with --draft ("approved": false) at its suggested time. Drafts are never
published: the owner approves them (approve command, the "Approve posts" workflow, or by setting "approved" to true
in publish/queue.json). A draft approved after its time is published on the next run.
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
    a.add_argument("--draft", action="store_true", help="queue unapproved: publish only after approve")
    ap_ = sub.add_parser("approve")
    ap_.add_argument("match", help='part of the story path, e.g. "round-07/day-1" or "01-", or "all"')
    ap_.add_argument("--when", help='new Athens time, "YYYY-MM-DD HH:MM" (default: keep the queued time)')
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    args = ap.parse_args()
    entries = load()

    if args.cmd == "check":
        sys.path.insert(0, str(ROOT / "scripts"))
        import publish_instagram as ig
        for lang, handle in sorted(ig.BRAND["handle"]["ig"].items()):
            handle = handle.lstrip("@")
            me = ig.call("GET", "me", ig.token_for(lang, handle), fields="username")
            if me.get("username") != handle:
                sys.exit(f"[{lang}] token belongs to @{me.get('username')}, expected @{handle}")
            print(f"[{lang}] token OK for @{handle}")
        return

    if args.cmd == "add":
        story = pathlib.Path(args.story)
        if not (ROOT / story / "post.en.md").exists():
            sys.exit(f"Not a story folder: {story}")
        when = dt.datetime.strptime(args.when, "%Y-%m-%d %H:%M").replace(tzinfo=ATHENS)
        entries = [e for e in entries if e["story"] != story.as_posix()]
        entries.append({"story": story.as_posix(), "when": when.isoformat(), "langs": args.langs.split(","),
                        "approved": not args.draft})
        save(entries)
        print(f"Queued {story} for {when:%a %d %b %H:%M} Athens ({', '.join(args.langs.split(','))})"
              + (", awaiting approval" if args.draft else ""))
        return

    if args.cmd == "approve":
        hits = [e for e in entries if not e.get("approved", True)
                and (args.match == "all" or args.match in e["story"])]
        if not hits:
            sys.exit(f"No drafts awaiting approval match {args.match!r}")
        for e in hits:
            e["approved"] = True
            if args.when:
                e["when"] = dt.datetime.strptime(args.when, "%Y-%m-%d %H:%M").replace(tzinfo=ATHENS).isoformat()
            print(f"Approved {e['story']} for {dt.datetime.fromisoformat(e['when']):%a %d %b %H:%M} Athens")
        save(entries)
        return

    if args.cmd == "list":
        for e in entries:
            state = " ".join(f"{l}:{'done' if done(e, l) else 'pending'}" for l in e["langs"])
            if not e.get("approved", True):
                state += "  (awaiting approval)"
            print(f"{dt.datetime.fromisoformat(e['when']):%a %d %b %H:%M}  {e['story']}  {state}")
        return

    now = dt.datetime.now(dt.timezone.utc)
    failed = False
    for e in entries:
        if dt.datetime.fromisoformat(e["when"]) > now or not e.get("approved", True):
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
