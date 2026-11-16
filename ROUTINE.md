# Cloud routine steps

Every game day of a round has its own one-time routine that fires 1h30m after that day's last tip-off; the last day of the round also drafts the round highlight. A daily routine at 06:00 UTC is the safety net. The schedule is in `rounds/E2026/SCHEDULE.md`. Folder layout:

```
rounds/E2026/round-07/
  day-1/            digest.json, README.md (posting plan), 01-<slug>/, 02-<slug>/, …
  day-2/
  day-3/
  highlight/        digest.json, README.md, post.<lang>.md, cards.<lang>.json, cards/, photo.*
```

## Per-day run (the prompt names round N, game day k of K, date D)
1. `python3 scripts/round_status.py N --date D --wait`. It re-checks every 5 minutes for up to 100 minutes. If it exits non-zero (a game ran late or was postponed), stop with no changes and no commit; the daily run picks the day up later.
2. If `rounds/E2026/round-NN/day-k/README.md` exists, the day is already drafted: skip to step 5.
3. `python3 scripts/round_digest.py --round N --date D` writes `round-NN/day-k/digest.json`. Draft that day's posts following `CLAUDE.md` ("Day posts"): a lead story and up to two more, **only from that day's games**, one folder each under `day-k/`, then the day's `README.md` posting plan.
4. For every story folder:
   - `post.en.md` (X post + Instagram) and `post.el.md` (Instagram only: no X section, no `x` card). The Greek version is localized for Greek fans, not translated: it uses the Greek names of clubs and players and Greek venue names (OAKA = ΟΑΚΑ, Peace and Friendship Stadium = ΣΕΦ), and plays up Olympiacos and Panathinaikos angles.
   - If the story is about one person, find their photo on Wikimedia Commons (see "Photos" in `CLAUDE.md`). If Commons is unreachable, skip the photo and note it in the day's `README.md`.
   - `cards.en.json` and `cards.el.json`, rendered with `python3 scripts/render_cards.py <spec>`. The renderer picks the right browser itself; if none is found, run `npx -y playwright install chromium-headless-shell` first.
   - Open every PNG with Read and fix any overflow, clipping or wrong text.
   - Check that each X post is 280 characters or fewer.
5. If k = K (the round's last day) and `round-NN/highlight/README.md` doesn't exist yet, draft the round highlight: `python3 scripts/round_digest.py --round N --highlight` writes `round-NN/highlight/digest.json` (all games of the round plus the table after it). Follow "Round highlight" in `CLAUDE.md`, with the same post, photo, card and check steps as above, and a short `highlight/README.md`.
6. Every number must come from the relevant `digest.json`. Background facts that aren't in the data, such as a coach's history, streaks or records, go into a `## Facts to verify` list at the top of each post file, so the human can check them before posting.
7. Queue every new post as a draft, in story order, using `python3 scripts/publish_queue.py add <story folder> <when> --draft`. Day posts are fresh news: `01-` gets `now`, `02-` gets `now+1` and `03-` gets `now+2`. The publisher keeps them 30 minutes apart, so they go out one by one as soon as the owner approves. The highlight folder gets `"<day after the round's last day> 12:00"` (Athens), so it doesn't bury that night's stories. Drafts are never published until the owner approves them.
8. Commit `rounds/E2026/round-NN/` and `publish/queue.json` to `main` with the message `Round N day k drafts (EN + EL)` (add `+ highlight` when you drafted it) and push. The owner reviews the files on GitHub and approves them.

## Daily safety net (no round named)
1. `python3 scripts/round_status.py --pending` lists played game days without a `README.md` and fully played rounds without a highlight (rounds 7+).
2. If it prints nothing, stop: no changes, no commit.
3. Otherwise, for each pending day, do steps 3–4 of the per-day run, and for each pending highlight, step 5. Then do steps 6–8. A suggested time already in the past is fine: the owner sets a new time when approving.

## Arena of the week run (Sundays, named in the prompt)
1. `python3 scripts/arena_facts.py --next`. If it prints "All arenas covered", stop: no changes.
2. `python3 scripts/arena_facts.py --get "<ARENA>"` (add `--wiki "<title>"` if it found the wrong Wikipedia page). Read `facts.json` in full. Wikimedia sites rate-limit the cloud (HTTP 429); the scripts wait and retry on their own, so run them in the foreground and let them finish. Never move work into background tasks and end your turn: the run stops when you do.
3. Find and download the exterior and interior photos (see "Arena of the week" in `CLAUDE.md`).
4. Write `post.en.md` (X + Instagram, with `## Sources`) and `post.el.md` (Instagram only), plus `cards.en.json` and `cards.el.json`. Render them, open every PNG and fix any problems, and check the X post is 280 characters or fewer.
5. Write the folder's `README.md`. Queue the post as a draft for that Sunday at 18:00 Athens: `python3 scripts/publish_queue.py add arenas/E2026/<slug> "YYYY-MM-DD 18:00" --draft`.
6. Commit `arenas/` and `publish/queue.json` to `main` with the message `Arena of the week: <arena> (EN + EL)` and push.

## Lineup of the week run (Saturdays, named in the prompt)
1. `python3 scripts/lineup.py pick` picks the latest fully played round's five (PG, SG, SF, PF, C by PIR) into `lineups/E2026/round-NN/lineup.json`. If it prints "Already picked" and that folder has a `README.md`, skip to "MVP of the round" below. If the round isn't fully played, stop.
2. For each player, look for a photo. Search several ways before giving up: `python3 scripts/commons_photo.py --search "<first> <last>"`, `"<last> <club>"`, `"<last> basketball"`, the club's name plus the season, and the image on the player's Wikipedia article (it is usually on Commons). Download a few candidates as thumbnails and **look at them**. Use one only if the player is clearly visible **in his current club's jersey** (the club in `lineup.json`); a photo in any other jersey is never used. Save it with `python3 scripts/commons_photo.py --get lineups/E2026/round-NN "File:…" --name photo-<player code>` and set `"focus"` (and `"zoom"`, e.g. 220, for a full-length shot) in its JSON so the face fills the tile. Photos are used only if **all five** players have one: as soon as one player has no suitable photo, stop searching; every tile then shows our drawing of a vest in the club's colours with the name and number (the renderer does this by itself), and the caption credits no photo.
3. `python3 scripts/lineup.py render lineups/E2026/round-NN`. Open all three PNGs (`cards/en/ig-1.png`, `cards/el/ig-1.png`, `cards/en/x.png`) and fix any problems (overlaps, cut-off names, a bad crop).
4. Write `post.en.md` (`## X` and `## Instagram caption`) and `post.el.md` (`## Instagram caption`). No stats anywhere: a short hook ("Round 7's five."), the five names with their clubs, a question ("Who's missing?"), then the hashtags. If the card uses photos (all five), credit every one in the caption: `📷 <author> / Wikimedia Commons (<license>)`. X: 280 characters or fewer, `#EuroLeague` plus at most two tags.
5. Write a short `README.md` (who, how they were picked: the round's top PIR per position; which photos are missing and why). Queue it as a draft for that Saturday at 19:00 Athens, single image plus a Reel on both accounts (players landing PG to C; rendered at publish time): `python3 scripts/publish_queue.py add lineups/E2026/round-NN "YYYY-MM-DD 19:00" --draft`.
6. Commit `lineups/` and `publish/queue.json` to `main` with the message `Lineup of the week: round N (EN + EL)` and push. Then do the MVP below.

### MVP of the round (same Saturday run, after the lineup)
A Reel on both accounts, Sunday 12:00 Athens, **published without approval** (the owner's decision, 2026-11-16): spotlights search a dark arena, lock onto the player, then a line on why he was the MVP and his four best numbers (`scripts/mvp.py`; rendered at publish time, with our own synthesized sound).
1. `python3 scripts/mvp.py pick` writes the round's top PIR player and his full line into `mvps/E2026/round-NN/mvp.json`. If it prints "Already picked" and that folder has a `README.md`, stop: no changes.
2. Photo: if the lineup folder has `photo-<his code>.jpg`, copy it and its JSON into the MVP folder. Otherwise search as in step 2 above (current club's jersey only) and save it with `--get mvps/E2026/round-NN "File:…" --name photo-<code>`; set `"focus"` so the face sits in the upper half of the square. Without one, the card shows our vest drawing on its own.
3. Add to `mvp.json`, for `"en"` and `"el"`: `"first"`/`"last"` (Greek spelling for el, as in the round's Greek posts), `"title"` and `"stats"`.
   - `"title"`: why he was the MVP, in the voice of `CLAUDE.md` (it interprets, it doesn't count: no numbers), 2–4 short lines split with `\n`, the payoff in `*accent*`. Example: `"Βασίλεψε κάτω\nαπό τα καλάθια\n*και έφερε διπλό\nαπό το Μιλάνο*"` / `"He owned\nthe glass\n*and stole a win\nin Milan*"`.
   - `"stats"`: his 4 most striking numbers as `[value, label]`, PIR first, every value from `"line"` (e.g. `["36", "PIR"], ["20", "rebounds"], ["17", "points"], ["+23", "plus/minus"]`). Pick what made his night special (rebounds for a big man's 20, threes for a shooter), not always points/rebounds/assists.
4. Render both to check: `python3 scripts/render_reel.py mvps/E2026/round-NN el` (and `en`), then look at a frame near the end, e.g. with the ffmpeg from `imageio_ffmpeg` (`-ss <length − 3> -frames:v 1`): the title must fit above the numbers, the name must not be cut. The videos are gitignored.
5. Write `post.en.md` and `post.el.md` (`## Instagram caption` only): a vivid hook naming him, 2–3 short lines on his night (numbers from `mvp.json`), a question, the photo credit if there is a photo (`📷 <author> / Wikimedia Commons (<license>)`), then 8–12 hashtags including the game's matchup tag (`python3 scripts/countdown.py tags <HOME> <AWAY>`) and `#MVP`.
6. Write a short `README.md` (who, his PIR, which game). Queue it **approved** (no `--draft`) for Sunday 12:00 Athens, Reels only: `python3 scripts/publish_queue.py add mvps/E2026/round-NN "YYYY-MM-DD 12:00" --langs reel-en,reel-el` (a Reel with no carousel beside it is shared to the grid too).
7. Commit `mvps/` and `publish/queue.json` to `main` with the message `MVP of the round: round N (EN + EL)` and push.

