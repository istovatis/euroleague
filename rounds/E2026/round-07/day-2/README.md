# Round 7, day 2 (Thu Oct 22, 2026): posting plan

Six games. Three posts. Fresh news: all queued as drafts for "now"; they go out as soon as the owner approves them, lead first, 30 minutes apart.

| # | Post | Story | Hook |
|---|---|---|---|
| 01 | now (on approval) | [Carlik Jones: game changer](01-carlik-jones/) | Partizan blow a 15-point lead in the Belgrade derby, then beat Crvena Zvezda 85-82 in OT; Jones 26 pts, 28 PIR |
| 02 | now +30 min | [Lessort: MVP of the night](02-lessort/) | 9/10 inside the arc, 20 pts, 28 PIR in 24 min; Panathinaikos 85-79 Baskonia, 6-1 |
| 03 | now +60 min | [Kabengele: MVP of the night](03-kabengele/) | Dubai 63-36 at the half in Munich, 107-91; Kabengele 24 pts, day-best 29 PIR; Dubai 5-2 |

Notes:
- Photos: all three from Wikimedia Commons (Zafer, CC BY 4.0), each in the player's current jersey (Partizan 2026-02-25, Panathinaikos 2024-10-25, Dubai 2025-12-19).
- Club crests now render on the score and X cards: the EuroLeague API had started answering in XML unless asked for JSON, which also broke the crest download on day 1. `round_status.py`, `round_digest.py`, `render_cards.py` and `arena_facts.py` now send `Accept: application/json`.
- Left out: Efes 89-80 Besiktas, Real's 113-99 road win over Maccabi (Campazzo 5/7 from three, 28 PIR), Barça 89-81 at Milan. Real was the closest call for a fourth story.
