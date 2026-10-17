# Daily post-round routine (cloud)

This runs every morning. Most days there is nothing new, and the run should exit quickly without committing.

1. Run `python3 scripts/round_digest.py`. It prints the latest fully played round N.
2. If `rounds/E2026/round-NN/post.en.md` already exists, the round is already drafted. **Stop**: no edits and no commit (run `git checkout -- . && git clean -fd rounds/` to drop the digest it just wrote).
3. Otherwise draft round N following `CLAUDE.md`, and use `rounds/E2026/round-06/` as the reference for format and tone:
   - `post.en.md` and `post.el.md`. The Greek version is localized for Greek fans, not translated: it uses the Greek names of clubs and players and Greek venue names (OAKA = ΟΑΚΑ, Peace and Friendship Stadium = ΣΕΦ), and plays up Olympiacos and Panathinaikos angles.
   - `cards.en.json` and `cards.el.json`. Render each one with `python3 scripts/render_cards.py <spec>`. If no Chrome is found, run `npx -y playwright install chromium` first.
   - Open every PNG with Read and fix any overflow, clipping or wrong text before committing.
   - Check that each X post is 280 characters or fewer (`python3 -c "print(len(open(...).read()))"` on the text only).
4. Every number must come from `rounds/E2026/round-NN/digest.json`. Background facts that aren't in the data, such as a coach's history, streaks or records, go into a `## Facts to verify` list at the top of each post file, so the human can check them before posting.
5. Commit everything in `rounds/E2026/round-NN/` to `main` with the message `Round N drafts (EN + EL)` and push. The human reviews the files on GitHub and posts them manually.
