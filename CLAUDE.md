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
- Posting plan (`day-K/README.md`): fresh, the same night. The posts are queued for "now" and go out as soon as the owner approves them, lead first, 30 minutes apart.
- Don't repeat a story that an earlier day of the same round already told.

## Round highlight
One post that closes the round, in `round-NN/highlight/`, drafted after the last game day:
- **Slide 1 (hook, with photo):** the defining story of the round, told with the whole round in view ("Round 7 belonged to …"). It may revisit the biggest day story, but with new framing.
- **Slide 2 (score card style):** player of the round, i.e. the top PIR across all game days, with their line.
- **Slide 3 (list card):** the table after the round, the top 4 plus the biggest climber or faller, with vivid tags ("New leader", "Still perfect", "Up 3"). Use `standings_after` from the digest.
- Caption and X post in the same vivid voice. Posting plan (`highlight/README.md`): the day after the round's last day, at 12:00 Athens, so it doesn't bury that night's day posts.

## Arena of the week (Sundays)
One post every Sunday about a EuroLeague arena, in `arenas/<season>/<arena-slug>/`, published Sunday evening.
- **Pick:** `python3 scripts/arena_facts.py --next` suggests an arena not covered yet that hosts a game in the next 7 days, so the post builds up to that game. `--list` shows every arena and which are done.
- **Facts:** `python3 scripts/arena_facts.py --get "<ARENA NAME>"` writes `facts.json`: official capacity, address, home teams and upcoming games from the EuroLeague API, opening date from Wikidata, and the Wikipedia article text. **Every fact must come from `facts.json`.** The headline capacity is always the EuroLeague figure (sources often disagree; you may mention, for example, "built for 14,940" if Wikipedia says so). List the URLs under `## Sources` in each post file, and put anything surprising under `## Facts to verify`.
- **Photos:** one outside and one inside photo from Wikimedia Commons (`commons_photo.py --search "<arena>"`, then `--get <folder> "File:…" --name exterior` and `--name interior`), same license rules as "Photos". Look at the candidates and pick ones where the building or the bowl is clearly visible. If no usable interior exists, drop that slide.
- **Slides (4):** 1) `hook` with `"photo": "exterior"`, `"badges"` listing the home clubs' codes from `assets/clubs.json` (rendered as crests or styled badges per `brand.json`), kicker "Arena of the week", a vivid title, and the arena's name as subtitle; 2) `hook` with `"photo": "interior"`, a line about what it is like inside; 3) `list` card with the facts: Capacity, Opened, Home of, This week (the upcoming game); 4) `hook` with the single most surprising fact ("Did you know"). The X card (EN only) is a `list` card with the key facts.
- **Voice:** same vivid rules as everything else: the arena is a character, not a spec sheet. The Greek version uses Greek names (ΣΕΦ, ΟΑΚΑ) and Greek angles.
- **Posting plan:** a short `README.md` in the folder, with the post time Sunday 18:00 Athens. The `README.md` also marks the arena as covered.

## Lineup of the week (Saturdays)
One single-image post every Saturday after a finished round, in `lineups/<season>/round-NN/`: five tiles, PG, SG, SF, PF and C, each with the player's name, club and photo. **No stats** on the image or in the copy (PIR only picks them: the round's top PIR per position; the API knows Guard / Forward / Center, so the guard with more assists is the PG and the forward with more rebounds the PF). Photos follow "Photos" below and must show the player in his current club's jersey; photos are used only if all five players have one (the owner's rule, for consistency); otherwise every tile shows our own drawing of a vest in the club's colours with the player's name and number (from the box score). Never official EuroLeague or club headshots. `scripts/lineup.py pick` / `render`; the Saturday routine follows ROUTINE.md and queues it as a draft for Saturday 19:00 Athens (Instagram EN + EL, X; no Reel).

## Picking the story (in priority order)
- **Underdog**: a win that breaks the table. Examples: a bottom-4 team beating a top-4 team, ending an unbeaten run, or a road win at a top seed. Use `upset_score`, `standings_gap` and `road_win`.
- **Coach**: when the result is clearly a coaching story, such as a tactical turnaround, a revenge game against a former club or mentor, or a big upset with a balanced box score where no single player dominated.
- **MVP**: the top PIR of the round, if it's exceptional (35+ PIR, or a historic shooting line) and the team won.
- **Game changer**: someone who decided a dramatic game, such as an OT game, a comeback from behind after Q3, or a margin of 3 points or fewer. Use `drama_score`.
Prefer the story with the strongest *narrative*, not just the biggest number. The strongest becomes the day's lead post (`01`). Other strong candidates get **their own posts** (`02`–`03`), each told with its own vivid angle. Only include a story if it stands on its own; three great posts beat four with a filler. Never bundle stories into an "Also in Round N" slide.

## Channel style
**X**: 280 characters or fewer, punchy hook on the first line, 3–4 stat lines. Hashtags: `#EuroLeague` plus, for a post about one game, its matchup tag (home + away short codes, e.g. `#OLYFEN`; `python3 scripts/countdown.py tags OLY ULK` prints them), plus at most one club tag: 3 at most. No emoji spam (2 at most).
**Instagram**: a carousel of 3 slides. Slide 1 is a big hook and the name; slide 2 is the stat card; slide 3 is a second narrative punch (a `hook` card with a big line, never a `text` card that explains). The caption opens with a hook, then 3–5 short lines and a question to drive comments, followed by 8–12 hashtags at the end, including the matchup tag (e.g. `#OLYFEN`) when the post is about one game. Greek captions add the clubs' Greek-name tags (`#Ολυμπιακός`).

## Photos
When a story is about one person (player or coach), Instagram slide 1 carries a photo of them. It doesn't need to be from that game.
- Only freely licensed photos from Wikimedia Commons (CC BY, CC BY-SA, CC0, public domain). Never official EuroLeague, club or agency photos, even though the API links to them.
- `python3 scripts/commons_photo.py --search "<name>"` lists candidates. Download a few as thumbnails, look at them, and pick: the person clearly visible and facing the camera, most recent first.
- **Players must be in their current team's jersey** (the owner's rule, 2026-10-21). A photo in a former club's jersey is never used: no photo at all is better. Coaches: current team's kit or neutral clothes.
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
Publishing runs in GitHub Actions (`.github/workflows/publish.yml`, every 15 minutes). The tokens are the encrypted repository secrets `IG_TOKEN_EN` and `IG_TOKEN_EL`; they never go into the repo or a chat. Only the owner approves posts: never publish or approve one without their go-ahead.
- The drafting routines queue every post as a draft (`"approved": false`) at its suggested time. **Drafts are never published.** The owner approves them in one of three ways:
  - **by email:** when drafts are queued, `notify.yml` (`scripts/notify_drafts.py`) opens an issue labelled `approval` that @mentions the owner, so GitHub emails the previews; ticking "Approve all" (or one post's box) on GitHub, or replying `approve` (or `approve 01`), approves them via `approve-reply.yml` (only the owner counts);
  - the **Approve posts** workflow (Actions tab or the GitHub mobile app; match e.g. `round-07/day-1`, `day-1/01-` or `all`, with an optional new time);
  - by telling Claude, who runs `publish_queue.py approve <match> [--when "YYYY-MM-DD HH:MM"]` and pushes;
  - by setting `"approved": true` in `publish/queue.json`.
  A draft approved after its time is published on the next run.
- `scripts/publish_queue.py add <story> "YYYY-MM-DD HH:MM" [--draft]` (Athens time, `--langs en,el` by default) queues a story in `publish/queue.json`; without `--draft` it is approved already. Commit and push the queue: the workflow publishes every due, approved entry. `list` shows the queue with each language's state.
- X (EN only): `scripts/publish_x.py <story>` posts the `## X` section of `post.en.md` with `cards/en/x.png` (plus `x-2.png`… when the spec's `"x"` is a list of up to 4 cards; X cards can take `"photo"` too; `render_cards.py <spec> --x-only` re-renders just those); dry run unless `--yes`; writes `published.x.json`. Queue entries include `x` by default (`--langs en,el,x`); it is skipped until the `X_*` secrets are set, and while the repository variable `X_ENABLED` is `false` (`gh variable set X_ENABLED --body true|false`). X posting costs API credits (pay per use); with none left, tweets fail with HTTP 402.
- **Reels:** every queued post also goes out as a Reel on both Instagram accounts (queue channels `reel-en`, `reel-el`, on by default), from the same approval. `scripts/render_reel.py <story> <lang>` animates the story's `ig` slides at 1080×1920 (photo push-in, headline lines rising, scores counting up, brand outro; silent track) via Playwright + ffmpeg; it runs at publish time on GitHub, and the video reaches Instagram as a temporary asset of the `reels` GitHub release, deleted after publishing (never committed). Reels show in the Reels tab only (`share_to_feed=false`), so the grid keeps just the carousel. Preview without posting: run the publish workflow with `reel_story=<story folder>`; the videos are attached to the run.
- **Weekly report (private):** `.github/workflows/weekly-report.yml` runs `scripts/weekly_report.py` every Monday 10:00 Athens: last week's Instagram insights (reach, views, likes, comments, saves, shares per post, Reels' watch time) and X metrics, follower changes, and a few plain "What worked" comparisons. It writes to the **private** repo `istovatis/parquet-hoops-reports` (via the deploy-key secret `REPORTS_DEPLOY_KEY`) and opens an issue here with only a link. Never put report numbers in this public repo, its issues or its logs. Run any time: `gh workflow run weekly-report.yml`.
- **Countdown (weekly):** `.github/workflows/countdown.yml` runs `scripts/countdown.py pick` every Sunday: it picks the coming week's biggest game (rivalries, Greek clubs, top-of-the-table) and writes `countdowns/<season>/round-NN/<home>-<away>/` with `prompt.txt` (the AI video prompt in the home fans' colours), `post.*.md`, `meta.json`, and opens an issue with the prompt and an upload link. The owner generates the clip (9:16, silent, no crests/logos/real people) and uploads it as `clip.mp4`; that push runs `countdown.py build`, which adds our text layer ("1 DAY TO GO", matchup, time) and the logo outro and queues the X video + both Reels as a **draft** for 12:00 Athens the day before the game. Captions say "AI-generated visual".
- **MVP poll (automatic, no approval; the owner's decision 2026-10-23):** `.github/workflows/mvp-poll.yml` runs `scripts/mvp_poll.py` on Saturday evenings: once the week's Lineup of the week is published, a text-only X poll "Round N MVP?" goes out around 20:00 Athens, open 24 hours, with `#EuroLeague #MVP` and the club tag of every lineup player (each club once). X polls take 4 options, so the lineup's top 4 by PIR are the options and the fifth is named in the text. Records `published.poll.json` in the lineup folder.
- **Final scores (the one exception to approval, the owner's decision on 2026-10-20):** `.github/workflows/final-scores.yml` runs `scripts/final_scores.py` every 5 minutes from 15:00 to 23:55 UTC. Minutes after each game ends it posts a data-only card (score, overtime or road-win note, each team's top scorer) to X and as an Instagram Story on both accounts, under `finals/<season>/round-NN/<code>-<HOME>-<AWAY>/`. No narrative copy goes into these posts: keep them pure API data. Pause with the repository variable `FINALS_ENABLED=false`. Test with `gh workflow run final-scores.yml -f dry_run=true -f game=58` (the cards are uploaded as a run artifact).
- `scripts/publish_instagram.py <story> <lang>`: dry run; add `--yes` to publish. Writes `published.<lang>.json`, commits and pushes it right away, and never posts a story twice.
- To test the workflow: `gh workflow run publish.yml -f dry_run=true`.
- Backup on the owner's Mac (tokens in the Keychain, service `parquet-hoops-instagram`): `scripts/publish_story.sh <story>` publishes EN, then EL; `scripts/schedule_publish.py <story> "YYYY-MM-DD HH:MM"` sets a one-shot launchd job (`--list`, `--dry-run`; logs in `~/Library/Logs/parquet-hoops/`).
- The tokens expire around 2026-12-15. Refresh them, then update the Keychain and the secrets.
