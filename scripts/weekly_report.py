#!/usr/bin/env python3
"""Weekly insights report: how last week's posts did on Instagram (both accounts) and X.

  python3 scripts/weekly_report.py --out <dir>   # last 7 days -> <dir>/weekly/<date>.md + <dir>/latest.md
  python3 scripts/weekly_report.py --days 14     # a longer window
  python3 scripts/weekly_report.py --print       # print only, write nothing

The reports are private: .github/workflows/weekly-report.yml runs this every Monday with --out pointing at a checkout
of the private repo istovatis/parquet-hoops-reports, commits there, and opens an issue in this (public) repo that
holds only a link, so the owner gets a notification without any numbers becoming public. Never write reports into
this repo (reports/ is gitignored).

Per post: reach, views, likes, comments, saves, shares (Instagram insights; Reels also average watch time) and
impressions, likes, reposts, replies (X public metrics). Follower counts are stored in <dir>/data/<date>.json, so
each report shows the change since the previous one. Instagram Stories (final scores) are left out: their insights
expire after 24 hours. Every number comes from the APIs; the takeaways are simple comparisons of those numbers.
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import publish_instagram as ig  # noqa: E402
import publish_x  # noqa: E402

IG_METRICS = ["reach", "views", "likes", "comments", "saved", "shares", "follows", "profile_visits"]
REEL_EXTRA = ["ig_reels_avg_watch_time"]


def ig_get(token, path, **params):
    params["access_token"] = token
    try:
        with urllib.request.urlopen(f"{ig.API}/{path}?{urllib.parse.urlencode(params)}", timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(errors="replace").replace(token, "<token>")}


def ig_insights(token, media_id, reel):
    metrics = IG_METRICS + (REEL_EXTRA if reel else [])
    data = ig_get(token, f"{media_id}/insights", metric=",".join(metrics))
    if "error" in data:  # one unsupported metric fails the whole call: fall back to one at a time
        out = {}
        for m in metrics:
            d = ig_get(token, f"{media_id}/insights", metric=m)
            if "data" in d:
                out[m] = d["data"][0]["values"][0]["value"]
        return out
    return {d["name"]: d["values"][0]["value"] for d in data["data"]}


def kind(folder):
    rel = folder.relative_to(ROOT).as_posix()
    if rel.startswith("arenas/"):
        return "Arena"
    if rel.startswith("finals/"):
        return "Final score"
    if "/highlight" in rel:
        return "Round highlight"
    return "Lead story" if folder.name.startswith("01-") else "Day story"


def angle(folder, lang):
    """The first slide's kicker ("MVP of the round", "Coach of the round", ...): the closest thing to the story's
    angle. Always the English one, so both accounts' posts of a story group together."""
    for spec in (folder / "cards.en.json", folder / f"cards.{lang}.json"):
        if spec.exists():
            ig_cards = json.loads(spec.read_text()).get("ig") or []
            if ig_cards:
                return ig_cards[0].get("kicker", "").split("·")[0].strip() or "-"
    return "-"


def has_photo(folder, lang):
    spec = folder / f"cards.{lang}.json"
    first = (json.loads(spec.read_text()).get("ig") or [{}])[0] if spec.exists() else {}
    return bool(first.get("photo")) or (folder / "photo.jpg").exists()


def collect(since):
    posts, x_posts = [], []
    for record in sorted(ROOT.glob("*/**/published.*.json")):
        channel = record.name[len("published."):-len(".json")]
        data = json.loads(record.read_text())
        when = dt.datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
        if when < since or channel.startswith("story-"):
            continue
        folder = record.parent
        if channel == "x":
            x_posts.append({"folder": folder, "id": data["id"], "url": data["url"], "when": when})
        else:
            lang = channel.split("-")[-1]
            posts.append({"folder": folder, "lang": lang, "reel": channel.startswith("reel-"), "when": when,
                          "media_id": data["media_id"], "url": data.get("permalink") or ""})
    return posts, x_posts


def avg(xs):
    return sum(xs) / len(xs) if xs else 0


def takeaways(posts):
    """Plain comparisons, only where both sides have at least two posts."""
    out = []

    def compare(label_a, a, label_b, b, what="reach"):
        if len(a) >= 2 and len(b) >= 2:
            ra, rb = avg([p["m"].get(what, 0) for p in a]), avg([p["m"].get(what, 0) for p in b])
            if rb and ra / rb >= 1.2:
                out.append(f"{label_a} reached {ra / rb:.1f}x more people than {label_b} (avg {ra:.0f} vs {rb:.0f}).")
            elif ra and rb / ra >= 1.2:
                out.append(f"{label_b} reached {rb / ra:.1f}x more people than {label_a} (avg {rb:.0f} vs {ra:.0f}).")

    compare("Reels", [p for p in posts if p["reel"]], "carousels", [p for p in posts if not p["reel"]])
    carousels = [p for p in posts if not p["reel"]]
    compare("Posts with a photo", [p for p in carousels if p["photo"]], "posts without", [p for p in carousels if not p["photo"]])
    compare("Greek posts", [p for p in posts if p["lang"] == "el"], "English posts", [p for p in posts if p["lang"] == "en"])
    by_angle = collections.defaultdict(list)
    for p in carousels:
        by_angle[p["angle"]].append(p["m"].get("reach", 0))
    ranked = sorted(((avg(v), k, len(v)) for k, v in by_angle.items() if k != "-" and len(v) >= 2), reverse=True)
    if len(ranked) >= 2:
        out.append(f"Best angle by average reach: **{ranked[0][1]}** ({ranked[0][0]:.0f}, {ranked[0][2]} posts); "
                   f"weakest: {ranked[-1][1]} ({ranked[-1][0]:.0f}, {ranked[-1][2]} posts).")
    engaged = [p for p in posts if p["m"].get("reach")]
    if engaged:
        best = max(engaged, key=lambda p: (p["m"].get("saved", 0) + p["m"].get("shares", 0)) / p["m"]["reach"])
        sv = best["m"].get("saved", 0) + best["m"].get("shares", 0)
        if sv:
            out.append(f"Most saved and shared for its reach: [{best['folder'].name}]({best['url']}) "
                       f"({sv} saves + shares from {best['m']['reach']} reached).")
    return out or ["Not enough posts yet for comparisons: they start once there are at least two of each kind."]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--print", action="store_true", help="print the report, write nothing")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "reports", help="report folder (the private repo's checkout)")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=a.days)
    today = now.date().isoformat()

    posts, x_posts = collect(since)
    tokens, followers = {}, {}
    for lang, handle in ig.BRAND["handle"]["ig"].items():
        tokens[lang] = ig.token_for(lang, handle.lstrip("@"))
        me = ig_get(tokens[lang], "me", fields="followers_count,media_count")
        followers[handle] = me.get("followers_count")
    for p in posts:
        p["m"] = ig_insights(tokens[p["lang"]], p["media_id"], p["reel"])
        p["kind"], p["angle"], p["photo"] = kind(p["folder"]), angle(p["folder"], p["lang"]), has_photo(p["folder"], p["lang"])

    x_metrics = {}
    if publish_x.configured():
        creds = publish_x.credentials()
        user = publish_x.request("GET", f"{publish_x.API}/users/me", creds, params={"user.fields": "public_metrics"})["data"]
        followers["@" + user["username"]] = user["public_metrics"]["followers_count"]
        ids = [p["id"] for p in x_posts]
        for i in range(0, len(ids), 100):
            data = publish_x.request("GET", f"{publish_x.API}/tweets", creds,
                                     params={"ids": ",".join(ids[i:i + 100]), "tweet.fields": "public_metrics"})
            x_metrics.update({t["id"]: t["public_metrics"] for t in data.get("data", [])})

    previous = sorted((a.out / "data").glob("*.json"))
    before = json.loads(previous[-1].read_text())["followers"] if previous else {}

    lines = [f"# Weekly report: {since:%d %b} to {now:%d %b %Y}", "",
             "## Followers", "", "| Account | Followers | Change |", "|---|---:|---:|"]
    for handle, n in followers.items():
        change = f"{n - before[handle]:+d}" if n is not None and before.get(handle) is not None else "-"
        lines.append(f"| {handle} | {n if n is not None else '-'} | {change} |")

    lines += ["", "## What worked", ""] + [f"- {t}" for t in takeaways(posts)]

    lines += ["", f"## Instagram ({len(posts)} posts)", "",
              "| Post | Account | Format | Kind | Angle | Reach | Views | Likes | Comments | Saves | Shares | Follows |",
              "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for p in sorted(posts, key=lambda p: -p["m"].get("reach", 0)):
        m = p["m"]
        fmt = "Reel" + (f" ({m['ig_reels_avg_watch_time'] / 1000:.1f}s avg watch)" if m.get("ig_reels_avg_watch_time") else "") \
            if p["reel"] else "Carousel" + (" + photo" if p["photo"] else "")
        lines.append(f"| [{p['folder'].name}]({p['url']}) | {ig.BRAND['handle']['ig'][p['lang']]} | {fmt} | {p['kind']} | "
                     f"{p['angle']} | " + " | ".join(str(m.get(k, "-")) for k in
                                                     ("reach", "views", "likes", "comments", "saved", "shares", "follows")) + " |")

    lines += ["", f"## X ({len(x_posts)} posts)", ""]
    if x_metrics or x_posts:
        lines += ["| Post | Kind | Impressions | Likes | Reposts | Replies | Bookmarks |", "|---|---|---:|---:|---:|---:|---:|"]
        finals = [p for p in x_posts if kind(p["folder"]) == "Final score"]
        for p in sorted([p for p in x_posts if p not in finals], key=lambda p: -x_metrics.get(p["id"], {}).get("impression_count", 0)):
            m = x_metrics.get(p["id"], {})
            lines.append(f"| [{p['folder'].name}]({p['url']}) | {kind(p['folder'])} | " + " | ".join(
                str(m.get(k, "-")) for k in ("impression_count", "like_count", "retweet_count", "reply_count", "bookmark_count")) + " |")
        if finals:
            tot = lambda k: sum(x_metrics.get(p["id"], {}).get(k, 0) for p in finals)
            lines.append(f"| Final scores ({len(finals)} posts, total) | Final score | {tot('impression_count')} | {tot('like_count')} | "
                         f"{tot('retweet_count')} | {tot('reply_count')} | {tot('bookmark_count')} |")
    else:
        lines.append("X is not set up or nothing was posted there.")
    lines += ["", "_Instagram Stories (final scores) aren't included: Instagram keeps their insights for 24 hours only._", ""]
    report = "\n".join(lines)

    if a.print:
        print(report)
        return
    (a.out / "weekly").mkdir(parents=True, exist_ok=True)
    (a.out / "data").mkdir(parents=True, exist_ok=True)
    (a.out / "weekly" / f"{today}.md").write_text(report)
    (a.out / "latest.md").write_text(report)
    (a.out / "data" / f"{today}.json").write_text(json.dumps({"date": today, "followers": followers}, indent=2) + "\n")
    print(report)


if __name__ == "__main__":
    main()
