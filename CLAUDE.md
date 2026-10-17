# EuroLeague round recap: Instagram + X

Every EuroLeague round becomes a set of posts: one lead story plus up to three more, each its own post with its own vivid angle. The project is not affiliated with EuroLeague. Never use the EuroLeague logo, club logos or official photos unless we hold the rights. Graphics are our own text and stat cards. Do **not** add a "fan account" or "not affiliated" disclaimer to cards, captions or X posts.

## Workflow per round (automated daily: see ROUTINE.md)
1. `python3 scripts/round_digest.py` writes `rounds/<season>/round-NN/digest.json` and prints the round summary. It picks the latest fully played round by default, or use `--round N`.
2. Pick the stories, using the rules below: a lead story (`01-…`) and up to three more (`02-…` to `04-…`).
3. Give each story its own folder, `rounds/<season>/round-NN/NN-<slug>/`, holding `post.<lang>.md` (X post, Instagram caption, slide text) and `cards.<lang>.json`.
4. Render each card spec with `python3 scripts/render_cards.py <story>/cards.<lang>.json` (card types: hook, score, text, list; `*accent*`, `**bold**` and `\n` are allowed). It writes `cards/<lang>/ig-N.png` (1080×1350) and `x.png` (1600×900) next to the spec using headless Chrome. Look at the PNGs before handing them over. The account name, handles (per channel: `ig` and `x`, since X does not allow dots) and colors live in `brand.json`.
5. Write `rounds/<season>/round-NN/README.md`: the posting plan, listing the stories in order with one line each and the day to post them (lead story the morning after the round, then one per day, all out before the next round tips off).
6. Every number in the copy must come from `digest.json` (box scores, records before the round, quarter and overtime scores). Background facts (a coach's history, streaks, records) must be ones you are sure of. If in doubt, leave them out.

## Picking the story (in priority order)
- **Underdog**: a win that breaks the table. Examples: a bottom-4 team beating a top-4 team, ending an unbeaten run, or a road win at a top seed. Use `upset_score`, `standings_gap` and `road_win`.
- **Coach**: when the result is clearly a coaching story, such as a tactical turnaround, a revenge game against a former club or mentor, or a big upset with a balanced box score where no single player dominated.
- **MVP**: the top PIR of the round, if it's exceptional (35+ PIR, or a historic shooting line) and the team won.
- **Game changer**: someone who decided a dramatic game, such as an OT game, a comeback from behind after Q3, or a margin of 3 points or fewer. Use `drama_score`.
Prefer the story with the strongest *narrative*, not just the biggest number. The strongest becomes the lead post (`01`). Other strong candidates get **their own posts** (`02`–`04`), each told with its own vivid angle. Only include a story if it stands on its own; three great posts beat four with a filler. Never bundle stories into an "Also in Round N" slide.

## Channel style
**X**: 280 characters or fewer, punchy hook on the first line, 3–4 stat lines, one hashtag `#EuroLeague` plus at most one club tag. No emoji spam (2 at most).
**Instagram**: a carousel of 3 slides. Slide 1 is a big hook and the name; slide 2 is the stat card; slide 3 is a second narrative punch (a `hook` card with a big line, never a `text` card that explains). The caption opens with a hook, then 3–5 short lines and a question to drive comments, followed by 8–12 hashtags at the end.

## Voice: vivid, not analytical
Tell each round like a story, the way a commentator would, not like a stats report. The model is "The student won in Athens": a headline with a character, a rivalry and a payoff.
- Every slide and every caption line is a beat of the story: tension, turn, payoff. Use fragments and strong verbs ("5-0. Unbeaten. At home." / "Leday dropped 17.").
- Numbers back the story up; they are never the point. No stat-trivia lines like "No player scored 20" or "They shot 48% from three".
- No explainer kickers or slides: no "Why it matters", "Context", "Key stat", "The numbers".
- Lean on drama the data supports: unbeaten runs ending, comebacks, overtime, road wins, rivalries, a coach facing his old club or mentor.

## Languages
Live: English (`post.en.md`: Instagram + X), Greek (`post.el.md`: **Instagram only** for now; no Greek X post, no `x` card in `cards.el.json`). Planned markets, roughly by EuroLeague audience: Greek (el), Spanish (es), Turkish (tr), Serbian (sr), Lithuanian (lt), Hebrew (he), Italian (it), French (fr), German (de). Localize, don't translate. For each market, pick the angle that matters there. For example, Greek accounts lead with Olympiacos and Panathinaikos stories, and Turkish accounts with Fenerbahce, Efes and Besiktas.

## Publishing (Instagram)
Publishing runs on the owner's Mac, because the Instagram tokens live in its Keychain (service `parquet-hoops-instagram`). Never publish without the owner's go-ahead.
- `scripts/publish_instagram.py <story> <lang>`: dry run; add `--yes` to publish. Writes `published.<lang>.json` and never posts a story twice.
- `scripts/publish_story.sh <story>`: publishes EN, then EL, and commits the records.
- `scripts/schedule_publish.py <story> "YYYY-MM-DD HH:MM"`: one-shot launchd job at local (Athens) time; `--list` shows pending jobs, `--dry-run` tests one. Logs go to `~/Library/Logs/parquet-hoops/`.
