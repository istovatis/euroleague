# Cloud routine steps

Every game day of a round has its own one-time routine that fires 1h50m after that day's last tip-off; the last day of the round also drafts the round highlight. A daily routine at 06:00 UTC is the safety net. The schedule is in `rounds/E2026/SCHEDULE.md`. Folder layout:

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
1. `python3 scripts/lineup.py pick` picks the latest fully played round's five (PG, SG, SF, PF, C by PIR) into `lineups/E2026/round-NN/lineup.json`. If it prints "Already picked" and that folder has a `README.md`, stop: no changes. If the round isn't fully played, stop.
2. For each player, look for a photo: `python3 scripts/commons_photo.py --search "<first> <last>"` (also try with the club name). Download a few candidates as thumbnails and **look at them**. Use one only if the player is clearly visible **in his current club's jersey** (the club in `lineup.json`); a photo in any other jersey is never used. Save it with `python3 scripts/commons_photo.py --get lineups/E2026/round-NN "File:…" --name photo-<player code>` and set `"focus"` (and `"zoom"`, e.g. 220, for a full-length shot) in its JSON so the face fills the tile. No suitable photo: skip it; the tile shows the club's crest.
3. `python3 scripts/lineup.py render lineups/E2026/round-NN`. Open all three PNGs (`cards/en/ig-1.png`, `cards/el/ig-1.png`, `cards/en/x.png`) and fix any problems (overlaps, cut-off names, a bad crop).
4. Write `post.en.md` (`## X` and `## Instagram caption`) and `post.el.md` (`## Instagram caption`). No stats anywhere: a short hook ("Round 7's five."), the five names with their clubs, a question ("Who's missing?"), then the hashtags. Credit every photo in the caption: `📷 <author> / Wikimedia Commons (<license>)`. X: 280 characters or fewer, `#EuroLeague` plus at most two tags.
5. Write a short `README.md` (who, how they were picked: the round's top PIR per position; which photos are missing and why). Queue it as a draft for that Saturday at 19:00 Athens, single image, no Reel: `python3 scripts/publish_queue.py add lineups/E2026/round-NN "YYYY-MM-DD 19:00" --langs en,el,x --draft`.
6. Commit `lineups/` and `publish/queue.json` to `main` with the message `Lineup of the week: round N (EN + EL)` and push.

