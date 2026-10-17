# EuroLeague round recap: Instagram + X

One post per EuroLeague round, on one story. The project is not affiliated with EuroLeague. Never use the EuroLeague logo, club logos or official photos unless we hold the rights. Graphics are our own text and stat cards. Do **not** add a "fan account" or "not affiliated" disclaimer to cards, captions or X posts.

## Workflow per round (automated daily: see ROUTINE.md)
1. `python3 scripts/round_digest.py` writes `rounds/<season>/round-NN/digest.json` and prints the round summary. It picks the latest fully played round by default, or use `--round N`.
2. Pick **one** story, using the rules below.
3. Write `rounds/<season>/round-NN/post.en.md` with the X post, the Instagram caption and the carousel slide text.
4. Write `cards.<lang>.json` (card types: hook, score, text, list; `*accent*`, `**bold**` and `\n` are allowed). Then run `python3 scripts/render_cards.py rounds/<season>/round-NN/cards.<lang>.json`, which writes `cards/<lang>/ig-N.png` (1080×1350) and `x.png` (1600×900) using headless Chrome. Look at the PNGs before handing them over. The account name, handles (per channel: `ig` and `x`, since X does not allow dots) and colors live in `brand.json`.
5. Every number in the copy must come from `digest.json`. Background facts (a coach's history, streaks, records) must be ones you are sure of. If in doubt, leave them out.

## Picking the story (in priority order)
- **Underdog**: a win that breaks the table. Examples: a bottom-4 team beating a top-4 team, ending an unbeaten run, or a road win at a top seed. Use `upset_score`, `standings_gap` and `road_win`.
- **Coach**: when the result is clearly a coaching story, such as a tactical turnaround, a revenge game against a former club or mentor, or a big upset with a balanced box score where no single player dominated.
- **MVP**: the top PIR of the round, if it's exceptional (35+ PIR, or a historic shooting line) and the team won.
- **Game changer**: someone who decided a dramatic game, such as an OT game, a comeback from behind after Q3, or a margin of 3 points or fewer. Use `drama_score`.
Prefer the story with the strongest *narrative*, not just the biggest number. Use other strong candidates as a final slide ("Also in Round N").

## Channel style
**X**: 280 characters or fewer, punchy hook on the first line, 3–4 stat lines, one hashtag `#EuroLeague` plus at most one club tag. No emoji spam (2 at most).
**Instagram**: a carousel of 3–5 slides. Slide 1 is a big hook and the name; slide 2 is the stat card; slide 3 is context or "why it matters"; the last slide is "Also in Round N". The caption opens with a hook, then 3–5 short lines and a question to drive comments, followed by 8–12 hashtags at the end.

## Languages
Live: English (`post.en.md`), Greek (`post.el.md`). Planned markets, roughly by EuroLeague audience: Greek (el), Spanish (es), Turkish (tr), Serbian (sr), Lithuanian (lt), Hebrew (he), Italian (it), French (fr), German (de). Localize, don't translate. For each market, pick the angle that matters there. For example, Greek accounts lead with Olympiacos and Panathinaikos stories, and Turkish accounts with Fenerbahce, Efes and Besiktas.
