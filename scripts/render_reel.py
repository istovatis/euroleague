#!/usr/bin/env python3
"""Render a story's Instagram slides as a Reel: cards/<lang>/reel.mp4 (1080x1920, 30 fps, H.264).

Usage: python3 scripts/render_reel.py <story> <lang>      e.g. rounds/E2026/round-07/day-1/01-<slug> en

The same slides as the carousel (cards.<lang>.json "ig"), in motion: the photo slowly pushes in, kickers and
badges slide in, headline lines rise one by one, scores count up, stat lines stagger in; then a short brand
outro. Scenes are HTML (render_cards.py's styles at Story size); headless Chrome is stepped frame by frame
through Playwright and the frames go to ffmpeg. No music: the API can't add licensed audio, so the track
is silent.

Needs `pip install playwright==1.49.1 imageio-ffmpeg==0.5.1`; ensure_tools() installs them when missing.
"""
import html
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

from brand_mark import centre_disc
from render_cards import BRAND, CHROME, CSS, FONTS, ROOT, SIZES, card_html

FPS = 30
SCENE = 3.6    # seconds per slide
OUTRO = 1.8
W, H = 1080, 1920
TAGLINE = {"en": "Stories from the floor", "el": "Ιστορίες από το παρκέ"}


def ensure_tools():
    try:
        import imageio_ffmpeg  # noqa: F401
        import playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright==1.49.1", "imageio-ffmpeg==0.5.1"], check=True)


def load_photo(folder, name):
    meta = json.loads((folder / f"{name}.json").read_text())
    return {"uri": (folder / f"{name}.jpg").as_uri(), "credit": meta["credit"], "focus": meta.get("focus", "50% 20%")}


def document(folder, spec):
    lang, colors = spec["lang"], BRAND["colors"]
    css = CSS % dict(SIZES["story"], f=FONTS, **colors)
    css += f"""
body {{ padding: 0; }}
.scene {{ position: absolute; inset: 0; padding: {SIZES['story']['pad_y']}px {SIZES['story']['pad']}px;
  display: flex; flex-direction: column; background: {colors['bg']}; overflow: hidden; opacity: 0; }}
.scene::before {{ content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(circle at 85% 10%, {colors['accent']}22, transparent 45%); }}
.scene.has-photo::before {{ display: none; }}
.scene.has-photo .main {{ justify-content: flex-end; padding-bottom: 28px; }}
.title .ln {{ display: block; }}
.outro {{ align-items: center; justify-content: center; text-align: center; gap: 36px; }}
.outro .word {{ font-weight: 900; font-size: 120px; line-height: 1; position: relative; }}
.outro .tag {{ font-weight: 700; font-size: 44px; letter-spacing: .08em; text-transform: uppercase; color: {colors['muted']}; position: relative; }}
.outro .handle {{ font-weight: 700; font-size: 40px; color: {colors['accent']}; position: relative; }}
.outro svg {{ position: relative; }}
"""
    scenes = []
    slides = spec["ig"]
    for n, card in enumerate(slides, 1):
        photo = None
        if card.get("photo"):
            photo = load_photo(folder, card["photo"])
        elif n == 1 and (folder / "photo.jpg").exists():
            photo = load_photo(folder, "photo")
        bg = credit = ""
        if photo:
            bg = f'<div class="photo" style="background-image:url({photo["uri"]}); background-position:{photo["focus"]}"></div>'
            credit = f'<span class="credit">{html.escape(photo["credit"])}</span>'
        scenes.append(f"""<section class="scene{' has-photo' if photo else ''}">{bg}
<div class="top"><span class="brand">{centre_disc(colors['accent'])}<b>{html.escape(BRAND['name'][lang])}</b> · {html.escape(spec['round_label'])}</span><span></span></div>
<div class="main">{card_html(card, lang)}</div>
<div class="foot"><span>{html.escape(BRAND['handle']['ig'][lang])}</span>{credit}</div></section>""")
    scenes.append(f"""<section class="scene outro">{centre_disc(colors['accent'], 300, 'o')}
<div class="word">{html.escape(BRAND['name'][lang])}</div><div class="tag">{html.escape(TAGLINE[lang])}</div>
<div class="handle">{html.escape(BRAND['handle']['ig'][lang])}</div></section>""")

    script = """
const SCENE = %(scene)d, OUTRO = %(outro)d;
const ease = 'cubic-bezier(.2,.8,.2,1)';
const counters = [];
function anim(el, frames, delay, dur, easing, fill) {
  el.animate(frames, {delay, duration: dur, fill: fill || 'both', easing: easing || ease}).pause();
}
function setup() {
  // Headlines that don't fit shrink first (same rule as the static cards), then split into lines.
  for (const el of document.querySelectorAll('.title, .team')) {
    let fs = parseFloat(getComputedStyle(el).fontSize);
    while (el.scrollWidth > el.clientWidth + 1 && fs > 40) { fs -= 4; el.style.fontSize = fs + 'px'; }
  }
  // One span per headline line; an accent that runs across a line break is closed and reopened.
  for (const el of document.querySelectorAll('.title')) {
    const open = [];
    el.innerHTML = el.innerHTML.split(/<br\\s*\\/?>/).map(l => {
      const pre = open.map(t => `<${t}>`).join('');
      for (const m of l.matchAll(/<(\\/?)(em|strong)>/g)) {
        if (m[1]) open.splice(open.lastIndexOf(m[2]), 1); else open.push(m[2]);
      }
      return `<span class="ln">${pre}${l}${[...open].reverse().map(t => `</${t}>`).join('')}</span>`;
    }).join('');
  }
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach((sc, i) => {
    const last = i === scenes.length - 1;
    const s = i * SCENE, d = last ? OUTRO : SCENE;
    // Scene in (a quick rise) and out (a quick fade), except the first in and the last out.
    anim(sc, i ? [{opacity: 0, transform: 'translateY(60px)'}, {opacity: 1, transform: 'none'}] : [{opacity: 1}, {opacity: 1}],
         s, i ? 260 : 1);
    // 'forwards' only: a backwards fill would show the scene before its turn.
    if (!last) anim(sc, [{opacity: 1}, {opacity: 0}], s + d - 180, 180, 'linear', 'forwards');
    const photo = sc.querySelector('.photo');
    if (photo) anim(photo, [{transform: 'scale(1.12)'}, {transform: 'scale(1)'}], s, d, 'linear');
    let t = s + 150;
    const step = (el, frames, dur, gap) => { anim(el, frames, t, dur); t += gap; };
    const fromLeft = [{opacity: 0, transform: 'translateX(-80px)'}, {opacity: 1, transform: 'none'}];
    const rise = [{opacity: 0, transform: 'translateY(70px)'}, {opacity: 1, transform: 'none'}];
    for (const el of sc.querySelectorAll('.scoreline, .badges, .kicker')) step(el, fromLeft, 420, 120);
    for (const el of sc.querySelectorAll('.title .ln')) step(el, rise, 480, 140);
    for (const el of sc.querySelectorAll('.score .team')) {
      step(el, fromLeft, 420, 0);
      const pts = el.nextElementSibling;
      step(pts, [{opacity: 0}, {opacity: 1}], 200, 160);
      counters.push({el: pts, to: parseInt(pts.textContent, 10), start: t - 160, dur: 900});
    }
    for (const el of sc.querySelectorAll('.sub, .note, .lines')) step(el, rise, 420, 120);
    for (const el of sc.querySelectorAll('.line, .item, .body p')) step(el, fromLeft, 380, 130);
    for (const el of sc.querySelectorAll('.item .txt')) {
      if (/^[0-9][0-9,]*$/.test(el.textContent.trim()))
        counters.push({el, to: parseInt(el.textContent.replace(/,/g, ''), 10), start: t - 300, dur: 900, comma: true});
    }
    if (last) {
      const parts = [...sc.children];
      t = s + 100;
      anim(parts[0], [{opacity: 0, transform: 'scale(.6) rotate(-90deg)'}, {opacity: 1, transform: 'none'}], t, 600);
      parts.slice(1).forEach((el, k) => anim(el, rise, t + 250 + k * 120, 420));
    }
  });
}
function seek(ms) {
  document.getAnimations().forEach(a => { a.currentTime = ms; });
  for (const c of counters) {
    const p = Math.min(Math.max((ms - c.start) / c.dur, 0), 1);
    const v = Math.round(c.to * (1 - Math.pow(1 - p, 3)));
    c.el.textContent = c.comma ? v.toLocaleString('en-US') : String(v);
  }
}
""" % dict(scene=SCENE * 1000, outro=OUTRO * 1000)
    total = len(slides) * SCENE + OUTRO
    doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}</style></head>
<body>{''.join(scenes)}<script>{script}</script></body></html>"""
    return doc, total


def render(story, lang):
    ensure_tools()
    import imageio_ffmpeg
    from playwright.sync_api import sync_playwright

    folder = (ROOT / story).resolve() if not pathlib.Path(story).is_absolute() else pathlib.Path(story)
    spec = json.loads((folder / f"cards.{lang}.json").read_text())
    doc, total = document(folder, spec)
    out = folder / "cards" / lang / "reel.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
    page_file = pathlib.Path(f.name)
    ffmpeg = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=shutil.which(CHROME) or CHROME,
                                        args=["--allow-file-access-from-files", "--disable-gpu"])
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(page_file.as_uri())
            page.evaluate("document.fonts.ready.then(() => true)")
            page.wait_for_load_state("networkidle")
            page.evaluate("setup()")
            for i in range(round(total * FPS)):
                page.evaluate(f"seek({i * 1000 / FPS})")
                ffmpeg.stdin.write(page.screenshot(type="jpeg", quality=92))
            browser.close()
    finally:
        ffmpeg.stdin.close()
        ffmpeg.wait()
        page_file.unlink()
    if ffmpeg.returncode:
        sys.exit("ffmpeg failed")
    print(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    render(sys.argv[1], sys.argv[2])
