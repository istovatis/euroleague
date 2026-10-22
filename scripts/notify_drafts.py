#!/usr/bin/env python3
"""Email the owner when posts wait for approval, and approve them from a reply.

  python3 scripts/notify_drafts.py notify                       # open an issue for drafts not announced yet
  python3 scripts/notify_drafts.py comment <issue> <author> <text>   # a comment on such an issue (run by CI)
  python3 scripts/notify_drafts.py cleanup                      # close issues whose drafts were approved elsewhere

notify: every draft in publish/queue.json that hasn't been announced ("notified" not set) goes into one GitHub
issue that @mentions the owner, so GitHub emails it: each post's first slide, its X text, a link to its folder,
and how to approve. The entries are then marked "notified" (the caller commits publish/queue.json).

comment: when the owner comments on (or replies by email to) that issue with "approve", every draft listed in it is
approved; "approve 01" approves only the drafts whose path contains "01". Comments by anyone else are ignored.
Once nothing in the issue waits any more, it is closed.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import publish_queue as q  # noqa: E402

REPO = "istovatis/euroleague"
OWNER = "istovatis"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
LABEL = "approval"
MARK = re.compile(r"<!-- drafts: (.*?) -->")


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "--repo", REPO], check=check, capture_output=True, text=True)


def title_of(story):
    parts = story.split("/")
    if parts[0] == "rounds":
        return f"{parts[2].replace('round-', 'Round ').replace(' 0', ' ')} {parts[3].replace('day-', 'day ')}" \
            if len(parts) > 4 else f"{parts[2].replace('round-', 'Round ').replace(' 0', ' ')} highlight"
    if parts[0] == "countdowns":
        return f"Countdown {parts[-1].upper()}"
    if parts[0] == "arenas":
        return f"Arena of the week: {parts[-1].replace('-', ' ')}"
    return story


def x_text(story):
    post = ROOT / story / "post.en.md"
    try:
        import publish_x
        return publish_x.post_text(post)
    except SystemExit:
        return ""


def preview(story):
    cards = ROOT / story / "cards" / "en"
    for name in ("ig-1.png", "x.png"):
        if (cards / name).exists():
            return f"{RAW}/{story}/cards/en/{name}"
    return None  # a video post: the folder link shows the videos


def notify():
    entries = q.load()
    new = [e for e in entries if not e.get("approved", True) and not e.get("notified")]
    if not new:
        print("No new drafts to announce")
        return False
    titles = sorted({title_of(e["story"]) for e in new})
    lines = [f"@{OWNER} {len(new)} post{'s' if len(new) > 1 else ''} waiting for your approval.", "",
             "**To approve all of them, reply to this email with `approve`** (or comment it here). "
             "`approve 01` approves only the posts whose folder contains `01`.", "",
             f"Or use the [Approve posts workflow](https://github.com/{REPO}/actions/workflows/approve.yml).", ""]
    for e in new:
        s = e["story"]
        when = q.dt.datetime.fromisoformat(e["when"]).astimezone(q.ATHENS)
        lines += [f"### [{s.split('/')[-1]}](https://github.com/{REPO}/tree/main/{s})",
                  f"Goes out {when:%a %d %b %H:%M} Athens (or right away if that has passed) to: {', '.join(e['langs'])}", ""]
        img = preview(s)
        if img:
            lines += [f'<img src="{img}" width="360">', ""]
        text = x_text(s)
        if text:
            lines += ["X text:", "", "> " + text.replace("\n", "\n> "), ""]
    lines.append(f"<!-- drafts: {','.join(e['story'] for e in new)} -->")
    if gh("label", "view", LABEL, check=False).returncode:
        gh("label", "create", LABEL, "--color", "D7FF3A", "--description", "Posts waiting for the owner's approval", check=False)
    body = ROOT / ".approval-body.md"
    body.write_text("\n".join(lines))
    try:
        url = gh("issue", "create", "--title", f"Approve: {', '.join(titles)}", "--label", LABEL,
                 "--assignee", OWNER, "--body-file", str(body)).stdout.strip()
    finally:
        body.unlink()
    for e in new:
        e["notified"] = url
    q.save(entries)
    print(url)
    return True


def comment(number, author, text):
    if author != OWNER:
        print(f"Ignoring a comment by {author}")
        return False
    lines = text.strip().splitlines()
    words = lines[0].split() if lines else []  # only the first line: email replies carry the quoted message below
    if not words or words[0].lower().strip(".!,") != "approve":
        print("Not an approval")
        return False
    issue = json.loads(gh("issue", "view", str(number), "--json", "body,labels").stdout)
    if LABEL not in [l["name"] for l in issue["labels"]] or not MARK.search(issue["body"]):
        print("Not an approval issue")
        return False
    stories = MARK.search(issue["body"]).group(1).split(",")
    only = words[1] if len(words) > 1 else None
    entries = q.load()
    approved = []
    for e in entries:
        if e["story"] in stories and not e.get("approved", True) and (not only or only in e["story"]):
            e["approved"] = True
            approved.append(e["story"])
    q.save(entries)
    waiting = [e for e in entries if e["story"] in stories and not e.get("approved", True)]
    msg = (f"Approved {len(approved)}: " + ", ".join(f"`{s.split('/')[-1]}`" for s in approved) +
           ". They go out on the next publishing run (within 15 minutes), 30 minutes apart." if approved
           else "Nothing new to approve here.")
    if waiting:
        msg += f" Still waiting: {', '.join(e['story'].split('/')[-1] for e in waiting)}."
    gh("issue", "comment", str(number), "--body", msg)
    if not waiting:
        gh("issue", "close", str(number))
    print(msg)
    return bool(approved)


def cleanup():
    """Close approval issues whose drafts were all approved another way (workflow, CLI)."""
    entries = {e["story"]: e for e in q.load()}
    issues = json.loads(gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number,body").stdout or "[]")
    for i in issues:
        m = MARK.search(i["body"])
        if m and all(entries.get(s, {}).get("approved", True) for s in m.group(1).split(",")):
            gh("issue", "close", str(i["number"]), "--comment", "All approved.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["notify"]:
        notify()
    elif sys.argv[1:2] == ["cleanup"]:
        cleanup()
    elif sys.argv[1:2] == ["comment"] and len(sys.argv) == 5:
        comment(int(sys.argv[2]), sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
