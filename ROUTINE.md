# Cloud routine steps

Every game day of a round has its own one-time routine that fires 2h15m after that day's last tip-off; the last day of the round also drafts the round highlight. A daily routine at 06:00 UTC is the safety net. The schedule is in `rounds/E2026/SCHEDULE.md`. Folder layout:

```
rounds/E2026/round-07/
  day-1/            digest.json, README.md (posting plan), 01-<slug>/, 02-<slug>/, …
  day-2/
  day-3/
  highlight/        digest.json, README.md, post.<lang>.md, cards.<lang>.json, cards/, photo.*
```

## Per-day run (the prompt names round N, game day k of K, date D)
1. `python3 scripts/round_status.py N --date D --wait`. It re-checks every 5 minutes for up to 75 minutes. If it exits non-zero (a game ran late or was postponed), stop with no changes and no commit; the daily run picks the day up later.
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
7. Commit `rounds/E2026/round-NN/` to `main` with the message `Round N day k drafts (EN + EL)` (add `+ highlight` when you drafted it) and push. The human reviews the files on GitHub and publishes them.

## Daily safety net (no round named)
1. `python3 scripts/round_status.py --pending` lists played game days without a `README.md` and fully played rounds without a highlight (rounds 7+).
2. If it prints nothing, stop: no changes, no commit.
3. Otherwise, for each pending day, do steps 3–4 of the per-day run, and for each pending highlight, step 5. Then do steps 6–7.
