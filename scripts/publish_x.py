#!/usr/bin/env python3
"""Publish one story's X post (text + cards/en/x.png, x-2.png, ...) via the X API v2.

Usage:
  python3 scripts/publish_x.py rounds/E2026/round-07/day-1/01-<slug>          # dry run
  python3 scripts/publish_x.py rounds/E2026/round-07/day-1/01-<slug> --yes    # publish
  python3 scripts/publish_x.py --check                                         # token check only

The dry run checks the credentials, confirms they belong to the expected account and prints
the post without sending anything. --yes publishes and records the result in
<story>/published.x.json; a story that already has that file is never posted twice.

Credentials (OAuth 1.0a user context, they don't expire): the environment variables
X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN and X_ACCESS_SECRET (GitHub Actions secrets), or the
macOS Keychain (service "parquet-hoops-x", accounts api_key, api_secret, access_token,
access_secret) when run locally.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand.json").read_text())
HANDLE = BRAND["handle"]["x"]["en"].lstrip("@")
API = "https://api.x.com/2"
KEYCHAIN_SERVICE = "parquet-hoops-x"
CREDS = {"X_API_KEY": "api_key", "X_API_SECRET": "api_secret",
         "X_ACCESS_TOKEN": "access_token", "X_ACCESS_SECRET": "access_secret"}


def configured():
    """True when credentials are available, so the queue can skip X until they are set up."""
    if all(os.environ.get(env) for env in CREDS):
        return True
    return sys.platform == "darwin" and subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", "api_key"], capture_output=True).returncode == 0


def x_length(text):
    """X's weighted length: most Latin, Greek and Cyrillic characters count 1, emoji and CJK count 2."""
    light = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
    return sum(1 if any(lo <= ord(c) <= hi for lo, hi in light) else 2 for c in text)


def credentials():
    out = {}
    for env, account in CREDS.items():
        value = os.environ.get(env, "").strip()
        if not value:
            r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
                               capture_output=True, text=True) if sys.platform == "darwin" else None
            value = r.stdout.strip() if r and r.returncode == 0 else ""
        if not value:
            sys.exit(f"No X credential {env}: set the GitHub secret, or locally\n"
                     f"  security add-generic-password -U -s {KEYCHAIN_SERVICE} -a {account} -w")
        out[account] = value
    return out


def q(s):
    return urllib.parse.quote(str(s), safe="~")


def auth_header(method, url, creds, params=None):
    """OAuth 1.0a HMAC-SHA1. JSON and multipart bodies are not part of the signature."""
    oauth = {"oauth_consumer_key": creds["api_key"], "oauth_nonce": secrets.token_hex(16),
             "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())),
             "oauth_token": creds["access_token"], "oauth_version": "1.0"}
    allp = {**oauth, **(params or {})}
    base = "&".join([method, q(url), q("&".join(f"{q(k)}={q(v)}" for k, v in sorted(allp.items())))])
    key = f"{q(creds['api_secret'])}&{q(creds['access_secret'])}"
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in sorted(oauth.items()))


def request(method, url, creds, body=None, content_type=None, params=None):
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full, data=body, method=method)
    req.add_header("Authorization", auth_header(method, url, creds, params))
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        for v in creds.values():
            text = text.replace(v, "<secret>")
        sys.exit(f"X API error on {method} {url}: HTTP {e.code}\n{text}")


def me(creds):
    user = request("GET", f"{API}/users/me", creds).get("data", {})
    if user.get("username", "").lower() != HANDLE.lower():
        sys.exit(f"X credentials belong to @{user.get('username')}, expected @{HANDLE}")
    return user


def upload_png(path, creds):
    boundary = secrets.token_hex(16)
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="media_category"\r\n\r\ntweet_image\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="media_type"\r\n\r\nimage/png\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="{path.name}"\r\n'
             f'Content-Type: image/png\r\n\r\n'.encode() + path.read_bytes() + b"\r\n",
             f"--{boundary}--\r\n".encode()]
    data = request("POST", f"{API}/media/upload", creds, b"".join(parts), f"multipart/form-data; boundary={boundary}")
    return data.get("data", data).get("id") or data.get("media_id_string")


def post_text(post_md):
    """The text under '## X (...)' up to the '---' line or the next section."""
    text = post_md.read_text()
    if "\n## X" not in text:
        sys.exit(f"No '## X' section in {post_md}")
    section = text.split("\n## X", 1)[1].split("\n", 1)[1]
    section = section.split("\n## ", 1)[0].split("\n---", 1)[0].strip()
    if x_length(section) > 280:
        sys.exit(f"X post is {x_length(section)} characters as X counts them; the limit is 280")
    return section


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", nargs="?", help="story folder, e.g. rounds/E2026/round-07/day-1/01-<slug>")
    ap.add_argument("--yes", action="store_true", help="actually publish (default is a dry run)")
    ap.add_argument("--check", action="store_true", help="only check the credentials")
    a = ap.parse_args()

    creds = credentials()
    user = me(creds)
    if a.check or not a.story:
        print(f"[x] credentials OK for @{user['username']}")
        return

    story = (ROOT / a.story).resolve()
    record = story / "published.x.json"
    if record.exists():
        sys.exit(f"Already published: {json.loads(record.read_text()).get('url')}")
    text = post_text(story / "post.en.md")
    images = sorted((story / "cards" / "en").glob("x*.png"), key=lambda f: f.stem)  # x.png, x-2.png, ...
    print(f"Account: @{user['username']} (id {user['id']})")
    print(f"Images: {', '.join(f.name for f in images) or 'none'}")
    print(f"Text ({x_length(text)} chars):\n{text}\n")
    if not a.yes:
        print("Dry run: nothing was posted. Re-run with --yes to publish.")
        return

    body = {"text": text}
    if images:
        body["media"] = {"media_ids": [upload_png(f, creds) for f in images[:4]]}
    tweet = request("POST", f"{API}/tweets", creds, json.dumps(body).encode(), "application/json")["data"]
    url = f"https://x.com/{user['username']}/status/{tweet['id']}"
    record.write_text(json.dumps({"id": tweet["id"], "url": url, "account": user["username"],
                                  "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    sys.path.insert(0, str(ROOT / "scripts"))
    from publish_instagram import commit_record
    commit_record(record)
    print(f"Published: {url}")


if __name__ == "__main__":
    main()
