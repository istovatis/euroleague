#!/usr/bin/env python3
"""Schedule a story to be published on Instagram at a local time, using macOS launchd.

Usage:
  python3 scripts/schedule_publish.py rounds/E2026/round-06/02-vezenkov "2026-10-18 10:00"
  python3 scripts/schedule_publish.py <story> "<YYYY-MM-DD HH:MM>" --dry-run    # test the job, posts nothing
  python3 scripts/schedule_publish.py --list

Runs on this Mac (the Instagram tokens live in its Keychain), so the Mac must be on and
logged in; if it is asleep at the scheduled time, launchd runs the job when it wakes.
Each job runs scripts/publish_story.sh once, then removes itself.
Logs: ~/Library/Logs/parquet-hoops/<label>.log
"""
import argparse
import datetime
import os
import pathlib
import plistlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENTS = pathlib.Path.home() / "Library" / "LaunchAgents"
LOGS = pathlib.Path.home() / "Library" / "Logs" / "parquet-hoops"
PREFIX = "com.parquethoops.publish."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?")
    ap.add_argument("when", nargs="?", help='local time, "YYYY-MM-DD HH:MM"')
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for p in sorted(AGENTS.glob(PREFIX + "*.plist")):
            job = plistlib.loads(p.read_bytes())
            t = job["StartCalendarInterval"]
            print(f"{t['Month']:02d}-{t['Day']:02d} {t['Hour']:02d}:{t['Minute']:02d}  {job['Label'][len(PREFIX):]}")
        return
    if not (a.story and a.when):
        ap.error("story and when are required")

    story = (ROOT / a.story).resolve()
    if not (story / "post.en.md").exists():
        sys.exit(f"Not a story folder: {story}")
    when = datetime.datetime.strptime(a.when, "%Y-%m-%d %H:%M")
    if when <= datetime.datetime.now():
        sys.exit(f"{a.when} is in the past")

    rel = story.relative_to(ROOT)
    label = PREFIX + f"{story.parent.name}-{story.name}" + ("-dryrun" if a.dry_run else "")
    plist = AGENTS / f"{label}.plist"
    LOGS.mkdir(parents=True, exist_ok=True)
    # Run once, then delete the plist and unload the job (the unload ends this process).
    cmd = (f'"{ROOT}/scripts/publish_story.sh" "{rel}"{" --dry-run" if a.dry_run else ""}; '
           f'rm -f "{plist}"; launchctl bootout gui/{os.getuid()}/{label}')
    job = {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-c", cmd],
        "StartCalendarInterval": {"Month": when.month, "Day": when.day, "Hour": when.hour, "Minute": when.minute},
        "StandardOutPath": str(LOGS / f"{label}.log"),
        "StandardErrorPath": str(LOGS / f"{label}.log"),
    }
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)  # replace if present
    plist.write_bytes(plistlib.dumps(job))
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], check=True)
    print(f"Scheduled {rel} for {when:%a %d %b %H:%M}{' (dry run)' if a.dry_run else ''}: {label}")


if __name__ == "__main__":
    main()
