#!/usr/bin/env python3
"""Find and download freely licensed photos from Wikimedia Commons for a story's hook slide.

Usage:
  python3 scripts/commons_photo.py --search "Sasha Vezenkov"              # list candidates
  python3 scripts/commons_photo.py --get <story> "File:Sasha Vezenkov ... (4).jpg"

--get saves <story>/photo.jpg (1600 px wide) and <story>/photo.json with the credit line.
Only Creative Commons BY / BY-SA, CC0 and public-domain files are accepted. Official
EuroLeague, club or agency photos are never used: they are copyrighted.
"""
import argparse
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "ParquetHoops/1.0 (https://github.com/istovatis/euroleague)"}
OK_LICENSES = re.compile(r"^(CC BY(-SA)? [0-9.]+|CC0|Public domain)$", re.I)


def api(**params):
    params.update(format="json")
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def info(pages):
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        ii = p["imageinfo"][0]
        m = ii.get("extmetadata", {})
        yield {
            "title": p["title"],
            "width": ii["width"], "height": ii["height"],
            "license": m.get("LicenseShortName", {}).get("value", "?"),
            "author": re.sub(r"^User:", "", re.sub(r"<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()),
            "date": re.sub(r"<[^>]+>", "", m.get("DateTimeOriginal", {}).get("value", "")).strip()[:10],
            "source": ii.get("descriptionurl"),
            "thumb": ii.get("thumburl"),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search")
    ap.add_argument("--get", nargs=2, metavar=("STORY", "FILE_TITLE"))
    a = ap.parse_args()
    props = dict(prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=1600,
                 iiextmetadatafilter="LicenseShortName|Artist|DateTimeOriginal")

    if a.search:
        d = api(action="query", generator="search", gsrnamespace=6, gsrlimit=20, gsrsearch=a.search, **props)
        for f in info(d.get("query", {}).get("pages", {})):
            flag = "" if OK_LICENSES.match(f["license"]) else "  (license not usable)"
            print(f"{f['date']:10} {f['width']}x{f['height']:<5} {f['license']:14} {f['title'][5:]}{flag}")
        return

    if a.get:
        story, title = ROOT / a.get[0], a.get[1]
        d = api(action="query", titles=title, **props)
        f = next(info(d["query"]["pages"]))
        if not OK_LICENSES.match(f["license"]):
            sys.exit(f"Refusing {title}: license '{f['license']}' is not CC BY / BY-SA / CC0 / public domain")
        req = urllib.request.Request(f["thumb"], headers=UA)
        (story / "photo.jpg").write_bytes(urllib.request.urlopen(req, timeout=60).read())
        f["credit"] = f"Photo: {f['author']} / Wikimedia Commons, {f['license']}"
        (story / "photo.json").write_text(json.dumps(f, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {story / 'photo.jpg'}\n{f['credit']}\n{f['source']}")
        return
    ap.error("use --search or --get")


if __name__ == "__main__":
    main()
