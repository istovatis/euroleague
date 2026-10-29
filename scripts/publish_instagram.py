#!/usr/bin/env python3
"""Publish one story's Instagram carousel via the Instagram API (Instagram Login).

Usage:
  python3 scripts/publish_instagram.py rounds/E2026/round-06/02-vezenkov en          # dry run
  python3 scripts/publish_instagram.py rounds/E2026/round-06/02-vezenkov en --yes    # publish
  python3 scripts/publish_instagram.py rounds/E2026/round-06/02-vezenkov en --reel --yes   # the Reel (render_reel.py)

The dry run checks the token, confirms it belongs to the expected account, and prints the
caption and image URLs without posting anything. --yes publishes and records the result in
<story>/published.<lang>.json; a story that already has that file is never published twice.

Token: macOS Keychain item (service "parquet-hoops-instagram", account = the Instagram
handle without @), or the env var IG_TOKEN_<LANG> (e.g. IG_TOKEN_EN) for the cloud.
The API only accepts public JPEG URLs, so the cards are converted to JPEG, committed and
pushed to the public GitHub repo first, and Instagram fetches them from there.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand.json").read_text())
API = "https://graph.instagram.com/v23.0"
RAW = "https://raw.githubusercontent.com/istovatis/euroleague/main"
KEYCHAIN_SERVICE = "parquet-hoops-instagram"
BLOCKED_SUBCODE = 2207051  # Instagram's anti-spam "action is blocked"
BLOCKED_EXIT = 75  # exit code for it, so publish_queue.py pauses the channel instead of retrying


def token_for(lang, handle):
    env = os.environ.get(f"IG_TOKEN_{lang.upper()}")
    if env:
        return env
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", handle, "-w"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"No token for {handle}: add it with\n  security add-generic-password -U -s {KEYCHAIN_SERVICE} -a {handle} -w")
    return r.stdout.strip()


def call(method, path, token, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(token, "<token>")
        print(f"Instagram API error on {method} {path}: HTTP {e.code}\n{body}", file=sys.stderr)
        try:
            subcode = json.loads(body).get("error", {}).get("error_subcode")
        except ValueError:
            subcode = None
        sys.exit(BLOCKED_EXIT if subcode == BLOCKED_SUBCODE else 1)


def caption_of(post_md):
    text = post_md.read_text()
    marker = "## Instagram caption"
    if marker not in text:
        sys.exit(f"No '{marker}' section in {post_md}")
    caption = text.split(marker, 1)[1].split("\n## ", 1)[0].strip()
    if len(caption) > 2200:
        sys.exit(f"Caption is {len(caption)} characters; Instagram allows 2200")
    return caption


def to_jpeg(png, jpg):
    """PNG -> JPEG: sips on macOS, Pillow elsewhere (GitHub Actions)."""
    import shutil
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92", str(png), "--out", str(jpg)],
                       check=True, capture_output=True)
    else:
        from PIL import Image
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92)


def jpegs_for(story, lang):
    """Convert ig-N.png to ig-N.jpg (Instagram's API rejects PNG) and return the repo paths."""
    pngs = sorted((story / "cards" / lang).glob("ig-*.png"))
    if not 1 <= len(pngs) <= 10:
        sys.exit(f"A post needs 1 image or a carousel of 2-10; found {len(pngs)} in {story / 'cards' / lang}")
    out = []
    for png in pngs:
        jpg = png.with_suffix(".jpg")
        if not jpg.exists() or jpg.stat().st_mtime < png.stat().st_mtime:
            to_jpeg(png, jpg)
        out.append(jpg.relative_to(ROOT))
    return out


def push():
    """Push main, rebasing first: drafting routines may have pushed in the meantime."""
    subprocess.run(["git", "-C", str(ROOT), "pull", "-q", "--rebase", "--autostash", "origin", "main"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "push", "-q", "origin", "main"], check=True)


def commit_record(record):
    """Commit and push the publish record right away, so a later failure can't cause a double post."""
    subprocess.run(["git", "-C", str(ROOT), "add", str(record)], check=True)
    subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m", f"Published {record.parent.name} ({record.stem})"], check=True)
    try:
        push()
    except subprocess.CalledProcessError:
        print(f"warning: could not push {record}; commit it by hand", file=sys.stderr)


def ensure_public(paths):
    """Commit and push the JPEGs so raw.githubusercontent.com serves them, then wait until it does."""
    subprocess.run(["git", "-C", str(ROOT), "add", *map(str, paths)], check=True)
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode:
        subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m", "Instagram JPEGs for publishing"], check=True)
    push()
    for p in paths:
        url = f"{RAW}/{p.as_posix()}"
        for _ in range(30):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                    if r.status == 200:
                        break
            except urllib.error.URLError:
                pass
            time.sleep(4)
        else:
            sys.exit(f"Image never became public: {url}")


def publish_story(folder, lang, png):
    """Publish one image as an Instagram Story (no approval step: used for final scores).
    Writes <folder>/published.story-<lang>.json; a folder that has it is never posted twice."""
    record = folder / f"published.story-{lang}.json"
    if record.exists():
        return
    handle = BRAND["handle"]["ig"][lang].lstrip("@")
    token = token_for(lang, handle)
    me = call("GET", "me", token, fields="user_id,username")
    if me.get("username") != handle:
        sys.exit(f"Token belongs to @{me.get('username')}, expected @{handle}")
    jpg = png.with_suffix(".jpg")
    to_jpeg(png, jpg)
    rel = jpg.relative_to(ROOT)
    ensure_public([rel])
    uid = me["user_id"]
    container = call("POST", f"{uid}/media", token, image_url=f"{RAW}/{rel.as_posix()}", media_type="STORIES")["id"]
    for _ in range(30):
        status = call("GET", container, token, fields="status_code").get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Story container {container} failed: {status}")
        time.sleep(5)
    media_id = call("POST", f"{uid}/media_publish", token, creation_id=container)["id"]
    record.write_text(json.dumps({"media_id": media_id, "account": handle,
                                  "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    commit_record(record)
    print(f"Published story on @{handle}")


REELS_RELEASE = "reels"  # a GitHub release that holds each Reel video only until Instagram has fetched it


def gh(*args, check=True):
    exe = shutil.which("gh") or str(pathlib.Path.home() / ".local/bin/gh")
    return subprocess.run([exe, *args, "--repo", "istovatis/euroleague"], check=check, capture_output=True, text=True)


def host_video(mp4, name):
    """Instagram fetches Reels from a public URL, and a video per post would bloat the repo, so the video
    becomes an asset of the "reels" release (not in git history) and is deleted after publishing."""
    if gh("release", "view", REELS_RELEASE, check=False).returncode:
        gh("release", "create", REELS_RELEASE, "--title", "Reel videos (temporary)", "--prerelease",
           "--notes", "Reel videos waiting to be fetched by Instagram; each is deleted once published.")
    staged = mp4.with_name(name)
    shutil.copyfile(mp4, staged)
    try:
        gh("release", "upload", REELS_RELEASE, str(staged), "--clobber")
    finally:
        staged.unlink()
    return f"https://github.com/istovatis/euroleague/releases/download/{REELS_RELEASE}/{name}"


def upload_reel(uid, token, mp4, caption, name):
    """Create a Reel container from the hosted video; returns its id once Instagram has processed it.
    Shown in the Reels tab only (share_to_feed=false), so the grid keeps just the carousel."""
    url = host_video(mp4, name)
    try:
        container = call("POST", f"{uid}/media", token, media_type="REELS", video_url=url,
                         caption=caption, share_to_feed="false")["id"]
        for _ in range(90):  # video processing takes a minute or two
            status = call("GET", container, token, fields="status_code,status")
            if status.get("status_code") == "FINISHED":
                return container
            if status.get("status_code") in ("ERROR", "EXPIRED"):
                sys.exit(f"Reel container {container} failed: {status}")
            time.sleep(5)
        sys.exit(f"Reel container {container} still processing after 7.5 minutes")
    finally:
        gh("release", "delete-asset", REELS_RELEASE, name, "-y", check=False)


def publish_reel(story, lang, yes):
    record = story / f"published.reel-{lang}.json"
    if record.exists():
        sys.exit(f"Already published: {json.loads(record.read_text()).get('permalink')}")
    handle = BRAND["handle"]["ig"][lang].lstrip("@")
    token = token_for(lang, handle)
    me = call("GET", "me", token, fields="user_id,username")
    if me.get("username") != handle:
        sys.exit(f"Token belongs to @{me.get('username')}, expected @{handle}")
    caption = caption_of(story / f"post.{lang}.md")
    mp4 = story / "cards" / lang / "reel.mp4"
    spec = story / f"cards.{lang}.json"  # no spec: a finished video (e.g. a countdown), used as it is
    if spec.exists() and (not mp4.exists() or mp4.stat().st_mtime < spec.stat().st_mtime):
        sys.path.insert(0, str(ROOT / "scripts"))
        import render_reel
        render_reel.render(str(story), lang)
    print(f"Account: @{handle} (id {me['user_id']})\nReel: {mp4.relative_to(ROOT)} ({mp4.stat().st_size // 1024} KB)")
    if not yes:
        print("Dry run: nothing was posted. Re-run with --yes to publish.")
        return
    container = upload_reel(me["user_id"], token, mp4, caption, f"{story.name}-{lang}.mp4")
    media_id = call("POST", f"{me['user_id']}/media_publish", token, creation_id=container)["id"]
    permalink = call("GET", media_id, token, fields="permalink").get("permalink")
    record.write_text(json.dumps({"media_id": media_id, "permalink": permalink, "account": handle,
                                  "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    commit_record(record)
    print(f"Published: {permalink}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", help="story folder, e.g. rounds/E2026/round-06/02-vezenkov")
    ap.add_argument("lang", choices=sorted(BRAND["handle"]["ig"]))
    ap.add_argument("--yes", action="store_true", help="actually publish (default is a dry run)")
    ap.add_argument("--reel", action="store_true", help="the story's Reel instead of the carousel")
    a = ap.parse_args()

    story = (ROOT / a.story).resolve() if not pathlib.Path(a.story).is_absolute() else pathlib.Path(a.story)
    if a.reel:
        return publish_reel(story, a.lang, a.yes)
    record = story / f"published.{a.lang}.json"
    if record.exists():
        sys.exit(f"Already published: {json.loads(record.read_text()).get('permalink')}")

    handle = BRAND["handle"]["ig"][a.lang].lstrip("@")
    token = token_for(a.lang, handle)
    me = call("GET", "me", token, fields="user_id,username")
    if me.get("username") != handle:
        sys.exit(f"Token belongs to @{me.get('username')}, expected @{handle}")
    caption = caption_of(story / f"post.{a.lang}.md")
    images = jpegs_for(story, a.lang)

    print(f"Account: @{handle} (id {me['user_id']})")
    print(f"Images: {', '.join(p.name for p in images)}")
    print(f"Caption ({len(caption)} chars):\n{caption}\n")
    if not a.yes:
        print("Dry run: nothing was posted. Re-run with --yes to publish.")
        return

    ensure_public(images)
    uid = me["user_id"]
    if len(images) == 1:  # a single-image post (e.g. the lineup of the week)
        container = call("POST", f"{uid}/media", token, image_url=f"{RAW}/{images[0].as_posix()}", caption=caption)["id"]
    else:
        children = [call("POST", f"{uid}/media", token, image_url=f"{RAW}/{p.as_posix()}", is_carousel_item="true")["id"]
                    for p in images]
        container = call("POST", f"{uid}/media", token, media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    for _ in range(30):
        status = call("GET", container, token, fields="status_code").get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Carousel container {container} failed: {status}")
        time.sleep(5)
    media_id = call("POST", f"{uid}/media_publish", token, creation_id=container)["id"]
    permalink = call("GET", media_id, token, fields="permalink").get("permalink")
    record.write_text(json.dumps({"media_id": media_id, "permalink": permalink, "account": handle,
                                  "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    commit_record(record)
    print(f"Published: {permalink}")


if __name__ == "__main__":
    main()
