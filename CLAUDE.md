# EuroLeague round recap: Instagram + X

Every EuroLeague game day becomes a set of posts (a lead story plus up to two more, each its own post with its own vivid angle), and every round closes with one round-highlight post. Round 6 was done per round, before this split; its folders are still a good reference for format and tone. The project is not affiliated with EuroLeague. Never use the EuroLeague logo or official, club or agency photos (they are copyrighted). Club crests appear only through the renderer's club marks (`"club_marks": "crests"` in `brand.json`, the owner's choice on 2026-10-18, accepting the trademark risk): they are fetched from the EuroLeague API at render time and cached in the gitignored `.cache/`, never committed or used anywhere else. Set it to `"badges"` to switch every post back to our own styled badges. Graphics are our own text and stat cards. Do **not** add a "fan account" or "not affiliated" disclaimer to cards, captions or X posts.

## Workflow (automated: see ROUTINE.md)
1. `python3 scripts/round_digest.py --round N --date YYYY-MM-DD` writes one game day's `rounds/<season>/round-NN/day-K/digest.json`; `--highlight` writes the whole round plus the table after it to `round-NN/highlight/`.
2. Pick the stories, using the rules below.
3. Give each story its own folder, `day-K/NN-<slug>/`, holding `post.<lang>.md` (X post, Instagram caption, slide text) and `cards.<lang>.json`.
4. Render each card spec with `python3 scripts/render_cards.py <story>/cards.<lang>.json` (card types: hook, score, text, list; `*accent*`, `**bold**` and `\n` are allowed). It writes `cards/<lang>/ig-N.png` (1080×1350) and `x.png` (1600×900) next to the spec using headless Chrome. Look at the PNGs before handing them over. The account name, handles (per channel: `ig` and `x`, since X does not allow dots) and colors live in `brand.json`.
5. Write a `README.md` posting plan for each day and for the highlight (see below).
6. Every number in the copy must come from `digest.json` (box scores, records before the round, quarter and overtime scores, the table after the round). Background facts (a coach's history, streaks, records) must be ones you are sure of. If in doubt, leave them out.

## Day posts
- One lead post (`01-…`) plus up to two more (`02-…`, `03-…`), **only from that day's games**. Include a story only if it stands on its own; a quiet day can have just one post.
- Posting plan (`day-K/README.md`): publish the next day, before that evening's games tip off. Suggested times (Athens): lead 09:00, then 12:00 and 15:00.
- Don't repeat a story that an earlier day of the same round already told.

## Round highlight
One post that closes the round, in `round-NN/highlight/`, drafted after the last game day:
- **Slide 1 (hook, with photo):** the defining story of the round, told with the whole round in view ("Round 7 belonged to …"). It may revisit the biggest day story, but with new framing.
- **Slide 2 (score card style):** player of the round, i.e. the top PIR across all game days, with their line.
- **Slide 3 (list card):** the table after the round, the top 4 plus the biggest climber or faller, with vivid tags ("New leader", "Still perfect", "Up 3"). Use `standings_after` from the digest.
- Caption and X post in the same vivid voice. Posting plan (`highlight/README.md`): the evening after the round's last day, at 19:00 Athens, after that day's posts.

## Arena of the week (Sundays)
One post every Sunday about a EuroLeague arena, in `arenas/<season>/<arena-slug>/`, published Sunday evening.
- **Pick:** `python3 scripts/arena_facts.py --next` suggests an arena not covered yet that hosts a game in the next 7 days, so the post builds up to that game. `--list` shows every arena and which are done.
- **Facts:** `python3 scripts/arena_facts.py --get "<ARENA NAME>"` writes `facts.json`: official capacity, address, home teams and upcoming games from the EuroLeague API, opening date from Wikidata, and the Wikipedia article text. **Every fact must come from `facts.json`.** The headline capacity is always the EuroLeague figure (sources often disagree; you may mention, for example, "built for 14,940" if Wikipedia says so). List the URLs under `## Sources` in each post file, and put anything surprising under `## Facts to verify`.
- **Photos:** one outside and one inside photo from Wikimedia Commons (`commons_photo.py --search "<arena>"`, then `--get <folder> "File:…" --name exterior` and `--name interior`), same license rules as "Photos". Look at the candidates and pick ones where the building or the bowl is clearly visible. If no usable interior exists, drop that slide.
- **Slides (4):** 1) `hook` with `"photo": "exterior"`, `"badges"` listing the home clubs' codes from `assets/clubs.json` (rendered as crests or styled badges per `brand.json`), kicker "Arena of the week", a vivid title, and the arena's name as subtitle; 2) `hook` with `"photo": "interior"`, a line about what it is like inside; 3) `list` card with the facts: Capacity, Opened, Home of, This week (the upcoming game); 4) `hook` with the single most surprising fact ("Did you know"). The X card (EN only) is a `list` card with the key facts.
- **Voice:** same vivid rules as everything else: the arena is a character, not a spec sheet. The Greek version uses Greek names (ΣΕΦ, ΟΑΚΑ) and Greek angles.
- **Posting plan:** a short `README.md` in the folder, with the post time Sunday 18:00 Athens. The `README.md` also marks the arena as covered.

## Picking the story (in priority order)
- **Underdog**: a win that breaks the table. Examples: a bottom-4 team beating a top-4 team, ending an unbeaten run, or a road win at a top seed. Use `upset_score`, `standings_gap` and `road_win`.
- **Coach**: when the result is clearly a coaching story, such as a tactical turnaround, a revenge game against a former club or mentor, or a big upset with a balanced box score where no single player dominated.
- **MVP**: the top PIR of the round, if it's exceptional (35+ PIR, or a historic shooting line) and the team won.
- **Game changer**: someone who decided a dramatic game, such as an OT game, a comeback from behind after Q3, or a margin of 3 points or fewer. Use `drama_score`.
Prefer the story with the strongest *narrative*, not just the biggest number. The strongest becomes the day's lead post (`01`). Other strong candidates get **their own posts** (`02`–`03`), each told with its own vivid angle. Only include a story if it stands on its own; three great posts beat four with a filler. Never bundle stories into an "Also in Round N" slide.

## Channel style
**X**: 280 characters or fewer, punchy hook on the first line, 3–4 stat lines, one hashtag `#EuroLeague` plus at most one club tag. No emoji spam (2 at most).
**Instagram**: a carousel of 3 slides. Slide 1 is a big hook and the name; slide 2 is the stat card; slide 3 is a second narrative punch (a `hook` card with a big line, never a `text` card that explains). The caption opens with a hook, then 3–5 short lines and a question to drive comments, followed by 8–12 hashtags at the end.

## Photos
When a story is about one person (player or coach), Instagram slide 1 carries a photo of them. It doesn't need to be from that game.
- Only freely licensed photos from Wikimedia Commons (CC BY, CC BY-SA, CC0, public domain). Never official EuroLeague, club or agency photos, even though the API links to them.
- `python3 scripts/commons_photo.py --search "<name>"` lists candidates. Download a few as thumbnails, look at them, and pick: the person clearly visible and facing the camera, ideally in their current team's jersey, most recent first.
- `python3 scripts/commons_photo.py --get <story> "File:…"` saves `photo.jpg` + `photo.json` (credit). The renderer then puts the photo full-bleed behind slide 1 with the credit in the footer. Set `"focus"` in `photo.json` (CSS background-position, default `50% 20%`) if the face is cropped.
- Add the credit as the last caption line before the hashtags: `📷 <author> / Wikimedia Commons (<license>)`.
- Team stories (no single person) and people without a usable photo get no photo. Example: `assets/brand/example-photo-slide.png`.

## Voice: vivid, not analytical
Tell each round like a story, the way a commentator would, not like a stats report. The model is "The student won in Athens": a headline with a character, a rivalry and a payoff.
- Every slide and every caption line is a beat of the story: tension, turn, payoff. Use fragments and strong verbs ("5-0. Unbeaten. At home." / "Leday dropped 17.").
- Numbers back the story up; they are never the point. No stat-trivia lines like "No player scored 20" or "They shot 48% from three".
- No explainer kickers or slides: no "Why it matters", "Context", "Key stat", "The numbers".
- Lean on drama the data supports: unbeaten runs ending, comebacks, overtime, road wins, rivalries, a coach facing his old club or mentor.

## Languages
Live: English (`post.en.md`: Instagram + X), Greek (`post.el.md`: **Instagram only** for now; no Greek X post, no `x` card in `cards.el.json`). Planned markets, roughly by EuroLeague audience: Greek (el), Spanish (es), Turkish (tr), Serbian (sr), Lithuanian (lt), Hebrew (he), Italian (it), French (fr), German (de). Localize, don't translate. For each market, pick the angle that matters there. For example, Greek accounts lead with Olympiacos and Panathinaikos stories, and Turkish accounts with Fenerbahce, Efes and Besiktas.

## Publishing (Instagram)
Publishing runs in GitHub Actions (`.github/workflows/publish.yml`, every 15 minutes). The tokens are the encrypted repository secrets `IG_TOKEN_EN` and `IG_TOKEN_EL`; they never go into the repo or a chat. Never publish or queue a post without the owner's go-ahead.
- `scripts/publish_queue.py add <story> "YYYY-MM-DD HH:MM"` (Athens time, `--langs en,el` by default) queues a story in `publish/queue.json`. Commit and push the queue: the workflow publishes every due entry. `list` shows the queue with each language's state.
- `scripts/publish_instagram.py <story> <lang>`: dry run; add `--yes` to publish. Writes `published.<lang>.json`, commits and pushes it right away, and never posts a story twice.
- To test the workflow: `gh workflow run publish.yml -f dry_run=true`.
- Backup on the owner's Mac (tokens in the Keychain, service `parquet-hoops-instagram`): `scripts/publish_story.sh <story>` publishes EN, then EL; `scripts/schedule_publish.py <story> "YYYY-MM-DD HH:MM"` sets a one-shot launchd job (`--list`, `--dry-run`; logs in `~/Library/Logs/parquet-hoops/`).
- The tokens expire around 2026-12-15. Refresh them, then update the Keychain and the secrets.
