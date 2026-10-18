#!/usr/bin/env python3
"""Arena of the week: the arena list, the next pick, and verifiable facts for a post.

  python3 scripts/arena_facts.py --list          # every EuroLeague home arena, home teams, capacity, covered or not
  python3 scripts/arena_facts.py --next          # suggested arena for this Sunday (uncovered, hosts a game in the next 7 days)
  python3 scripts/arena_facts.py --get "PEACE AND FRIENDSHIP STADIUM" [--wiki "Peace and Friendship Stadium"]

--get writes arenas/E2026/<slug>/facts.json (EuroLeague API: official capacity, address, home teams,
upcoming games there; Wikidata: opening date, capacity, architect; Wikipedia: summary and article
text) and prints it. Every fact in the post must come from facts.json; the sources are listed in it.
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEASON = "E2026"
GAMES = f"https://api-live.euroleague.net/v2/competitions/E/seasons/{SEASON}/games"
UA = {"User-Agent": "ParquetHoops/1.0 (https://github.com/istovatis/euroleague)"}
FOLDER = ROOT / "arenas" / SEASON


def get_json(url):
    """GET with retries: Wikipedia/Wikidata answer 429 to busy shared IPs (cloud runners) with a Retry-After."""
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == 7:
                raise
            wait = min(int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt, 60)
            print(f"Rate limited (HTTP {e.code}) by {urllib.parse.urlparse(url).netloc}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def arenas():
    """Arena name -> {capacity, address, teams: Counter, upcoming: [games]}."""
    out = {}
    now = dt.datetime.now(dt.timezone.utc)
    for g in get_json(GAMES)["data"]:
        v = g.get("venue")
        if not v:
            continue
        a = out.setdefault(v["name"], {"name": v["name"], "capacity": v.get("capacity"), "address": v.get("address"),
                                        "teams": collections.Counter(), "upcoming": []})
        a["teams"][g["local"]["club"]["name"]] += 1
        tip = dt.datetime.fromisoformat(g["utcDate"].replace("Z", "+00:00"))
        if not g["played"] and tip > now:
            a["upcoming"].append({"round": g["round"], "utc": g["utcDate"], "home": g["local"]["club"]["name"],
                                  "away": g["road"]["club"]["name"]})
    for a in out.values():
        a["upcoming"].sort(key=lambda x: x["utc"])
    return out


def covered(name):
    return (FOLDER / slug(name) / "README.md").exists()


def wikidata(title):
    """Find the Wikidata item through the English Wikipedia page, then read a few properties."""
    q = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        dict(action="query", prop="pageprops", ppprop="wikibase_item", titles=title, redirects=1, format="json")))
    page = next(iter(q["query"]["pages"].values()))
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not qid:
        return {}
    e = get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")["entities"][qid]
    claims = e.get("claims", {})

    def values(prop):
        vals = []
        for s in claims.get(prop, []):
            d = s["mainsnak"].get("datavalue", {}).get("value")
            if isinstance(d, dict):
                d = d.get("time") or d.get("amount") or d.get("id") or d.get("text")
            vals.append(d)
        return vals

    return {"qid": qid, "url": f"https://www.wikidata.org/wiki/{qid}",
            "opened (P1619)": values("P1619"), "inception (P571)": values("P571"),
            "capacity (P1083)": values("P1083"), "architect (P84, item ids)": values("P84")}


def find_title(name):
    """The English Wikipedia article for an arena name, via Wikipedia search."""
    q = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        dict(action="query", list="search", srsearch=f"{name} arena", srlimit=1, format="json")))
    hits = q["query"]["search"]
    return hits[0]["title"] if hits else name.title()


def wikipedia(title):
    q = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        dict(action="query", prop="extracts", explaintext=1, titles=title, redirects=1, format="json")))
    page = next(iter(q["query"]["pages"].values()))
    if "missing" in page:
        return {}
    return {"title": page["title"], "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
            "text": page.get("extract", "")[:12000]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--get", metavar="ARENA")
    ap.add_argument("--wiki", help="English Wikipedia title, if it differs from the arena name")
    a = ap.parse_args()
    all_arenas = arenas()

    if a.list or a.next:
        rows = sorted(all_arenas.values(), key=lambda x: -sum(x["teams"].values()))
        if a.list:
            for x in rows:
                teams = ", ".join(f"{t} ({n})" for t, n in x["teams"].most_common())
                print(f"{'done' if covered(x['name']) else '    '}  {x['name']:40} cap {x['capacity']}  {teams}")
            return
        soon = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
        for x in rows:
            nxt = next((g for g in x["upcoming"] if dt.datetime.fromisoformat(g["utc"].replace("Z", "+00:00")) < soon), None)
            if nxt and not covered(x["name"]):
                print(f"{x['name']}\tnext game: round {nxt['round']}, {nxt['home']} vs {nxt['away']}, {nxt['utc']}")
                return
        left = [x["name"] for x in rows if not covered(x["name"])]
        print(left[0] + "\t(no game in the next 7 days)" if left else "All arenas covered")
        return

    if a.get:
        x = all_arenas.get(a.get)
        if not x:
            sys.exit(f"Unknown arena {a.get!r}; see --list")
        title = a.wiki or find_title(x["name"])
        facts = {
            "arena": x["name"],
            "euroleague": {"capacity": x["capacity"], "address": x["address"], "home_teams": dict(x["teams"]),
                           "upcoming_games": x["upcoming"][:3], "source": GAMES},
            "wikidata": wikidata(title),
            "wikipedia": wikipedia(title),
        }
        dest = FOLDER / slug(x["name"])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "facts.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: v for k, v in facts.items() if k != "wikipedia"}, indent=2, ensure_ascii=False))
        print("\nWikipedia:", facts["wikipedia"].get("url", "NOT FOUND (pass --wiki with the right title)"))
        print(facts["wikipedia"].get("text", "")[:1500])
        print(f"\n-> {dest / 'facts.json'}")
        return
    ap.error("use --list, --next or --get")


if __name__ == "__main__":
    main()
