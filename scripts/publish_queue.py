#!/usr/bin/env python3
"""Instagram publishing queue (publish/queue.json), run by the GitHub Actions workflow.

  python3 scripts/publish_queue.py add <story> "YYYY-MM-DD HH:MM" [--langs en,el,x,reel-en,reel-el] [--draft]   # time is Athens local
  python3 scripts/publish_queue.py approve <match> [--when "YYYY-MM-DD HH:MM"]   # approve drafts whose path contains <match> ("all" = every draft)
  python3 scripts/publish_queue.py list
  python3 scripts/publish_queue.py run [--dry-run]     # publish every due, unpublished entry (used by CI)
  python3 scripts/publish_queue.py check               # confirm each language's token works and matches its account

An entry is published once per channel: "en" and "el" are the Instagram accounts (publish_instagram.py),
"x" is the English X account (publish_x.py), and "reel-en" / "reel-el" are the story's Reel on each Instagram
account (publish_instagram.py --reel: rendered by render_reel.py at publish time, shown in the Reels tab only). Each writes <story>/published.<channel>.json and refuses to post a
story twice, so re-running is always safe. X is skipped while its credentials aren't set up. Tokens come from IG_TOKEN_EN / IG_TOKEN_EL
(GitHub Actions secrets) or the macOS Keychain when run locally.

The drafting routines queue every post with --draft ("approved": false) at its suggested time. Drafts are never
published: the owner approves them (approve command, the "Approve posts" workflow, or by setting "approved" to true
in publish/queue.json). A draft approved after its time is published on the next run.

Times can be "now" or "now+N" (N minutes from now), so day posts go out as soon as they are approved. Posts on the
same account are kept at least GAP_MINUTES apart: each run publishes at most one entry, in queue order, so a batch
approved together goes out one by one instead of all at once.
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
GAP_MINUTES = 30


def parse_when(text):
    """Athens "YYYY-MM-DD HH:MM", or "now" / "now+N" (minutes)."""
    if text.startswith("now"):
        minutes = int(text[4:]) if text.startswith("now+") else 0
        return (dt.datetime.now(ATHENS) + dt.timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    return dt.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=ATHENS)


def last_published():
    """When the most recent queued post went out (any language), or None."""
    times = [json.loads(f.read_text()).get("published_at") for e in load() for f in (ROOT / e["story"]).glob("published.*.json")]
    times = [dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) for t in times if t]
    return max(times, default=None)


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
    a.add_argument("when", help='Athens local time, "YYYY-MM-DD HH:MM", or "now" / "now+N" (minutes)')
    a.add_argument("--langs", default="en,el,x,reel-en,reel-el")
    a.add_argument("--draft", action="store_true", help="queue unapproved: publish only after approve")
    ap_ = sub.add_parser("approve")
    ap_.add_argument("match", help='part of the story path, e.g. "round-07/day-1" or "01-", or "all"')
    ap_.add_argument("--when", help='new Athens time, "YYYY-MM-DD HH:MM" or "now" (default: keep the queued time)')
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--drain", action="store_true", help="keep going until every due post is out, GAP_MINUTES apart (CI)")
    sub.add_parser("check")
    args = ap.parse_args()
    entries = load()

    if args.cmd == "check":
        sys.path.insert(0, str(ROOT / "scripts"))
        import publish_instagram as ig
        import publish_x
        if publish_x.configured():
            print(f"[x] token OK for @{publish_x.me(publish_x.credentials())['username']}")
        else:
            print("[x] not set up yet: skipped")
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
        when = parse_when(args.when)
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
            print(f"Nothing to approve: no drafts awaiting approval match {args.match!r} (new drafts arrive about 1h50m after a game day's last tip-off)")
            return
        for e in hits:
            e["approved"] = True
            if args.when:
                e["when"] = parse_when(args.when).isoformat()
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

    sys.path.insert(0, str(ROOT / "scripts"))
    import publish_x
    import time
    channels = lambda e: [c for c in e["langs"] if c != "x" or publish_x.configured()]
    failed_any = False
    tried = set()
    deadline = time.time() + 5 * 3600  # --drain: one CI job publishes the whole batch, GAP_MINUTES apart
    while True:
        if args.drain:  # pick up approvals made while this job runs
            subprocess.run(["git", "-C", str(ROOT), "pull", "-q", "--rebase", "--autostash", "origin", "main"], check=False)
            entries = load()
        now = dt.datetime.now(dt.timezone.utc)
        due = [e for e in entries if dt.datetime.fromisoformat(e["when"]) <= now and e.get("approved", True)
               and not all(done(e, lang) for lang in channels(e)) and e["story"] not in tried]
        if not due:
            # --drain also waits for approved posts scheduled within the job's time budget (e.g. today's 18:00 post),
            # because GitHub's timer often skips the run that would publish them
            later = sorted(dt.datetime.fromisoformat(e["when"]) for e in entries if e.get("approved", True)
                           and dt.datetime.fromisoformat(e["when"]) > now and e["story"] not in tried
                           and not all(done(e, lang) for lang in channels(e)))
            if args.drain and later and later[0].timestamp() < deadline:
                wait = (later[0] - now).total_seconds() + 5
                print(f"Next scheduled post at {later[0]:%H:%M %Z}: waiting {wait / 60:.0f} min", flush=True)
                time.sleep(wait)
                continue
            break
        last = last_published()
        if last and now - last < dt.timedelta(minutes=GAP_MINUTES) and not args.dry_run:
            wait = (last + dt.timedelta(minutes=GAP_MINUTES) - now).total_seconds()
            if not args.drain or time.time() + wait > deadline:
                print(f"{len(due)} due; the last post went out at {last:%H:%M} UTC, waiting for the {GAP_MINUTES}-minute gap")
                break
            print(f"{len(due)} due; next in {wait / 60:.0f} min (the {GAP_MINUTES}-minute gap)", flush=True)
            time.sleep(wait + 5)
            continue
        e = due[0]
        tried.add(e["story"])  # a failing entry is tried once per job, so it can't loop
        failed = False
        for lang in channels(e):
            if done(e, lang):
                continue
            print(f"== {e['story']} [{lang}] due {e['when']}", flush=True)
            if lang == "x":
                cmd = [sys.executable, str(ROOT / "scripts" / "publish_x.py"), e["story"]]
            elif lang.startswith("reel-"):
                cmd = [sys.executable, str(ROOT / "scripts" / "publish_instagram.py"), e["story"], lang[5:], "--reel"]
            else:
                cmd = [sys.executable, str(ROOT / "scripts" / "publish_instagram.py"), e["story"], lang]
            if not args.dry_run:
                cmd.append("--yes")
            failed |= subprocess.run(cmd).returncode != 0
        failed_any |= failed
        if not args.drain:
            break
    sys.exit(1 if failed_any else 0)


if __name__ == "__main__":
    main()
