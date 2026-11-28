# Kick files

Each file here starts one data job when it changes on `main` (a push triggers GitHub Actions within seconds; GitHub's
scheduled clock often runs hours late or skips runs, so it is only a backup). The routines write the date into them
and push at the start of their run (ROUTINE.md):

- Saturday routine: `race`, `roundmap`, `crowds`, and `shotchart` once the MVP is committed
- Monday routine: `specialists`

Every job skips work that is already done, so a start by both the kick and the clock is harmless.
