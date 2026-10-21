#!/usr/bin/env python3
"""Weekly countdown: an AI fan clip of the week's biggest game, posted the day before tip-off.

  python3 scripts/countdown.py pick                 # choose the game, write countdowns/<season>/round-NN/<home>-<away>/
  python3 scripts/countdown.py build <folder>       # clip.mp4 in the folder -> X video + EN/EL Reels, queued as a draft
  python3 scripts/countdown.py tags OLY ULK         # the hashtags for a game

1. pick (GitHub Actions, Sundays): scores the games in the coming week (rivalries, Greek clubs, top-of-the-table
   meetings) and writes the folder: meta.json, prompt.txt (the AI video prompt in the home fans' colours),
   post.en.md / post.el.md and a README. The workflow opens an issue with the prompt and an upload link.
2. The owner generates the clip (Veo or similar, 9:16, no sound) and uploads it to the folder as clip.mp4.
3. build (runs on that upload): our text layer ("1 DAY TO GO", the matchup, the time) and the logo outro over the
   clip, silent: cards/en/x.mp4 for X and cards/<lang>/reel.mp4 for the Reels. It queues the post as a draft for
   12:00 Athens the day before the game. AI video can go wrong, so the owner approves it like any other post.
"""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import unicodedata
import zoneinfo

from round_digest import get
from round_status import tip

ROOT = pathlib.Path(__file__).resolve().parent.parent
ATHENS = zoneinfo.ZoneInfo("Europe/Athens")
CLUBS = json.loads((ROOT / "assets" / "clubs.json").read_text())

# Fan colours (for the prompt), the home city (for the copy) and the short code used in matchup hashtags.
# Tags default to the EuroLeague TV codes; a few are overridden with the codes fans actually type.
FANS = {
    "ASV": ("green and white", "Villeurbanne", "ASV"), "BAR": ("deep blue and garnet red", "Barcelona", "BAR"),
    "BAS": ("navy blue and red", "Vitoria", "BKN"), "MUN": ("red and white", "Munich", "BAY"),
    "BES": ("black and white", "Istanbul", "BJK"), "RED": ("red and white", "Belgrade", "CZV"),
    "DUB": ("black and gold", "Dubai", "DUB"), "IST": ("navy blue and white", "Istanbul", "EFS"),
    "ULK": ("navy blue and yellow", "Istanbul", "FEN"), "HTA": ("red and white", "Tel Aviv", "HTA"),
    "TEL": ("yellow and blue", "Tel Aviv", "MTA"), "MIL": ("red and white", "Milan", "MIL"),
    "OLY": ("red and white", "Piraeus", "OLY"), "PAN": ("green and white", "Athens", "PAO"),
    "PRS": ("black and pink", "Paris", "PAR"), "PAR": ("black and white", "Belgrade", "PAR"),
    "MAD": ("white and purple", "Madrid", "RMB"), "PAM": ("orange and black", "Valencia", "VBC"),
    "VIR": ("black and white", "Bologna", "VIR"), "ZAL": ("green and white", "Kaunas", "ZAL"),
}
RIVALRIES = [{"OLY", "PAN"}, {"IST", "ULK"}, {"IST", "BES"}, {"ULK", "BES"}, {"MAD", "BAR"}, {"PAR", "RED"},
             {"TEL", "HTA"}, {"MIL", "VIR"}, {"PRS", "ASV"}, {"BAS", "MAD"}, {"BAS", "BAR"}, {"PAM", "MAD"}, {"PAM", "BAR"}]
GREEK = {"OLY", "PAN"}
DAYS_EL = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]

PROMPT = """Vertical 9:16 video, 8 seconds, cinematic, photorealistic. No audio.

Inside a packed indoor basketball arena about an hour before tip-off. The camera starts close behind a young fan
standing in the lower stands, holding a {colors} striped knitted scarf stretched above their head with both hands.
Slow, steady push-in over their shoulder, revealing the glowing empty hardwood court below and thousands of fans
behind and around them, all in {colors}, waving scarves and clapping in rhythm. Light haze hangs under the arena
spotlights, warm golden light on the court, the crowd slightly darker and full of motion. The fan turns their head
slightly toward the court, excited, anticipating. Shallow depth of field, anamorphic lens look, subtle film grain,
dramatic sports-broadcast atmosphere.

Strictly no text, no letters, no numbers, no logos, no crests, no sponsor boards with readable writing, no team
names, no recognizable real people, no players on the court.
"""


def tags(home, away):
    """#EuroLeague, the matchup tag (#OLYFEN) and both clubs' own tags."""
    h, a = FANS[home][2], FANS[away][2]
    plain = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()  # #Fenerbahce, not #Fenerbahçe
    club = lambda c: "#" + "".join(ch for ch in plain(CLUBS[c]["en"]) if ch.isalnum())
    greek = lambda c: "#" + "".join(ch for ch in CLUBS[c]["el"] if ch.isalnum())
    return {"x": ["#EuroLeague", f"#{h}{a}"], "ig": ["#EuroLeague", f"#{h}{a}", club(home), club(away)],
            "ig_el": ["#EuroLeague", f"#{h}{a}", greek(home), greek(away), club(home), club(away)]}


def standings(season, rnd):
    try:
        data = get(f"/v3/competitions/E/seasons/{season}/rounds/{rnd - 1}/basicstandings")
        return {t["club"]["code"]: t["position"] for t in data["teams"]}
    except Exception:
        return {}


def score(g, table):
    h, a = g["local"]["club"]["code"], g["road"]["club"]["code"]
    s = 10 * ({h, a} in RIVALRIES) + 4 * len({h, a} & GREEK)
    for c in (h, a):
        pos = table.get(c)
        s += 3 if pos and pos <= 4 else 1 if pos and pos <= 8 else 0
    return s


def pick(season, now):
    games = get(f"/v2/competitions/E/seasons/{season}/games")["data"]
    window = [g for g in games if not g["played"] and now + dt.timedelta(hours=36) <= tip(g) <= now + dt.timedelta(days=8)]
    if not window:
        print("No games in the coming week")
        return None
    table = standings(season, min(g["round"] for g in window))
    g = max(window, key=lambda g: (score(g, table), -tip(g).timestamp()))
    home, away = g["local"]["club"]["code"], g["road"]["club"]["code"]
    folder = ROOT / "countdowns" / season / f"round-{g['round']:02d}" / f"{home.lower()}-{away.lower()}"
    if (folder / "meta.json").exists():
        print(f"Already picked: {folder.relative_to(ROOT)}")
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    t = tip(g).astimezone(ATHENS)
    post_at = (t - dt.timedelta(days=1)).replace(hour=12, minute=0)
    meta = {"season": season, "round": g["round"], "game": g["gameCode"], "home": home, "away": away,
            "tip_athens": t.isoformat(), "post_at": post_at.strftime("%Y-%m-%d %H:%M"),
            "venue": (g.get("venue") or {}).get("name"), "score": score(g, table)}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    (folder / "prompt.txt").write_text(PROMPT.format(colors=FANS[home][0]))
    write_posts(folder, meta)
    upload = f"https://github.com/istovatis/euroleague/upload/main/{folder.relative_to(ROOT).as_posix()}"
    (folder / "README.md").write_text(
        f"# Countdown: {CLUBS[home]['en']} vs {CLUBS[away]['en']}\n\n"
        f"Round {g['round']}, {t:%a %d %b %H:%M} Athens. Goes out {post_at:%a %d %b %H:%M} (the day before), after approval.\n\n"
        f"1. Generate a clip with `prompt.txt` (9:16 vertical, 6-8 s, no sound).\n"
        f"2. Upload it here as **clip.mp4**: {upload}\n"
        f"3. The Countdown workflow builds the X video and both Reels and queues them as a draft; approve as usual.\n")
    print(folder.relative_to(ROOT))
    return folder


def write_posts(folder, m):
    home, away = m["home"], m["away"]
    t = dt.datetime.fromisoformat(m["tip_athens"])
    tg = tags(home, away)
    en_h, en_a, el_h, el_a = CLUBS[home]["en"], CLUBS[away]["en"], CLUBS[home]["el"], CLUBS[away]["el"]
    (folder / "post.en.md").write_text(f"""# Countdown: {en_h} vs {en_a} (Round {m['round']}, {t:%a %d %b %H:%M} Athens)

AI-generated fan clip (no crests, logos or real people) with our own text layer and outro. Silent.

## X
1 day. {FANS[home][1]} is already loud.

{en_h} vs {en_a} · {t:%a %H:%M}

AI-generated visual · {' '.join(tg['x'])}

## Instagram caption
1 day. {FANS[home][1]} is already loud.

{en_h} vs {en_a}. {t:%A}, {t:%H:%M}.
Who takes it?

AI-generated visual

{' '.join(tg['ig'])} #Basketball #EuroLeagueBasketball #GameDay #ParquetHoops
""")
    (folder / "post.el.md").write_text(f"""# Αντίστροφη μέτρηση: {el_h} – {el_a} ({m['round']}η αγωνιστική)

## Instagram caption
1 μέρα ακόμα.

{el_h} – {el_a}. {DAYS_EL[t.weekday()]} {t:%d/%m}, {t:%H:%M}.
Ποιος την παίρνει;

Οπτικό υλικό από AI

{' '.join(tg['ig_el'])} #μπάσκετ #ParquetHoops
""")


def layer(m, lang, w, h):
    """Transparent text layer: brand mark, "1 DAY TO GO", the matchup, the time."""
    import render_brand as b
    from brand_mark import centre_disc
    C = b.C
    t = dt.datetime.fromisoformat(m["tip_athens"])
    home, away = CLUBS[m["home"]], CLUBS[m["away"]]
    if lang == "el":
        txt = ("1 μέρα ακόμα", home["el"], f"– {away['el']}", f"{DAYS_EL[t.weekday()]} {t:%d/%m} · {t:%H:%M}")
    else:
        txt = ("1 day to go", home["en"], f"vs {away['en']}", f"{t:%a %d %b} · {t:%H:%M} · {FANS[m['home']][1]}")
    vertical = h > w
    pad, big = (72, 150) if vertical else (80, 130)
    body = f"""<div style="position:absolute; inset:0; background: linear-gradient(180deg, {C['bg']}AA 0%, transparent 18%,
      transparent {48 if vertical else 35}%, {C['bg']}E6 {78 if vertical else 80}%, {C['bg']} 100%)"></div>
    <div style="position:absolute; left:{pad}px; top:{250 if vertical else 60}px; display:flex; align-items:center; gap:14px;
      font-weight:700; font-size:30px; letter-spacing:.12em; text-transform:uppercase; color:{C['fg']}">
      {centre_disc(C['accent'], 36, 'k')}<b style="font-weight:900">{b.BRAND['name'][lang]}</b></div>
    <div style="position:absolute; left:{pad}px; right:{pad}px; bottom:{330 if vertical else 70}px">
      <div style="display:inline-block; background:{C['accent']}; color:{C['bg']}; font-weight:900; font-size:{48 if vertical else 40}px;
        letter-spacing:.08em; text-transform:uppercase; padding:8px 20px; margin-bottom:24px">{txt[0]}</div>
      <div class="t" style="font-weight:900; font-size:{big}px; line-height:.92; text-transform:uppercase; color:{C['fg']}">{txt[1]}<br>
        <span style="color:{C['accent']}">{txt[2]}</span></div>
      <div style="margin-top:22px; font-weight:700; font-size:{40 if vertical else 36}px; letter-spacing:.06em; text-transform:uppercase;
        color:{C['fg']}CC">{txt[3]}</div></div>
    <script>for (const el of document.querySelectorAll('.t')) {{ let fs = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollWidth > el.clientWidth + 1 && fs > 60) {{ fs -= 6; el.style.fontSize = fs + 'px'; }} }}</script>"""
    return b.CSS % dict(w=w, h=h) + " body{display:block; position:relative; background:transparent}", body, w, h, False


def outro(lang, w, h, handle):
    import render_brand as b
    from brand_mark import centre_disc
    C = b.C
    body = f"""<div style="position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:30px">
      {centre_disc(C['accent'], 260 if h > w else 200, 'o')}
      <div style="font-weight:900; font-size:{110 if h > w else 96}px; line-height:1">{b.BRAND['name'][lang]}</div>
      <div style="font-weight:700; font-size:40px; letter-spacing:.08em; text-transform:uppercase; color:{C['muted']}">{b.LANGS[lang]['tagline']}</div>
      <div style="font-weight:700; font-size:38px; color:{C['accent']}">{handle}</div></div>"""
    return b.CSS % dict(w=w, h=h) + " body{display:block; position:relative}", body, w, h, True


def probe(ffmpeg, clip):
    """(width, height, seconds) of the clip, read from ffmpeg's banner."""
    import re
    info = subprocess.run([ffmpeg, "-hide_banner", "-i", str(clip)], capture_output=True, text=True).stderr
    w, h = map(int, re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", info).groups())
    hh, mm, ss = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info).groups()
    return w, h, int(hh) * 3600 + int(mm) * 60 + float(ss)


def compose(ffmpeg, clip, size, txt_png, end_png, out, seconds):
    """Clip (cropped to fill the frame, up to 4.2 s) + text layer rising in + 0.8 s logo outro. No audio."""
    w, h = size
    body = min(seconds, 4.2)
    total = body + 0.8
    fill = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-t", f"{body:.2f}", "-i", str(clip),
                    "-loop", "1", "-t", f"{total:.2f}", "-i", str(txt_png), "-loop", "1", "-t", f"{total:.2f}", "-i", str(end_png),
                    "-filter_complex",
                    f"[0:v]{fill},setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=0.8[bg];"
                    "[1:v]format=rgba,fade=in:st=0.4:d=0.45:alpha=1[txt];"
                    f"[2:v]format=rgba,fade=in:st={body - 0.05:.2f}:d=0.35:alpha=1[end];"
                    "[bg][txt]overlay=x=0:y='min(70,max(0,70*(1-(t-0.4)/0.45)))'[v1];"
                    f"[v1][end]overlay=0:0,trim=duration={total:.2f},format=yuv420p[v]",
                    "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", "30",
                    "-movflags", "+faststart", str(out)], check=True)


def build(folder, queue_it=True):
    sys.path.insert(0, str(ROOT / "scripts"))
    import render_brand as b
    import render_reel
    render_reel.ensure_tools()
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    folder = (ROOT / folder).resolve()
    m = json.loads((folder / "meta.json").read_text())
    clip = folder / "clip.mp4"
    if not clip.exists():
        sys.exit(f"No clip.mp4 in {folder}")
    cw, ch, seconds = probe(ffmpeg, clip)
    tmp = folder / ".build"
    tmp.mkdir(exist_ok=True)
    b.ROOT = folder  # shoot() prints paths relative to ROOT
    jobs = [("en", (1080, 1920), b.BRAND["handle"]["ig"]["en"], folder / "cards" / "en" / "reel.mp4"),
            ("el", (1080, 1920), b.BRAND["handle"]["ig"]["el"], folder / "cards" / "el" / "reel.mp4"),
            # X: the clip's own shape (X plays vertical and horizontal video alike)
            ("en", (1920, 1080) if cw > ch else (1080, 1920), b.BRAND["handle"]["x"]["en"], folder / "cards" / "en" / "x.mp4")]
    for lang, (w, h), handle, out in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        txt, end = tmp / f"txt-{lang}-{w}.png", tmp / f"end-{lang}-{w}-{handle.strip('@')}.png"
        b.shoot(*layer(m, lang, w, h), txt, lang)
        b.shoot(*outro(lang, w, h, handle), end, lang)
        compose(ffmpeg, clip, (w, h), txt, end, out, seconds)
        print(out.relative_to(ROOT))
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    if cw > ch:
        print("note: the clip is horizontal; the Reels are a centre crop of it. A 9:16 clip looks better.")
    queue = [sys.executable, str(ROOT / "scripts" / "publish_queue.py")]
    listing = subprocess.run(queue + ["list"], capture_output=True, text=True).stdout
    if queue_it and folder.relative_to(ROOT).as_posix() not in listing:
        subprocess.run(queue + ["add", str(folder.relative_to(ROOT)), m["post_at"], "--langs", "x,reel-en,reel-el", "--draft"], check=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--season", default="E2026")
    bld = sub.add_parser("build")
    bld.add_argument("folder")
    bld.add_argument("--no-queue", action="store_true", help="build only (testing)")
    t = sub.add_parser("tags")
    t.add_argument("home")
    t.add_argument("away")
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.season, dt.datetime.now(dt.timezone.utc))
    elif a.cmd == "build":
        build(a.folder, not a.no_queue)
    else:
        print(json.dumps(tags(a.home, a.away), ensure_ascii=False))


if __name__ == "__main__":
    main()
