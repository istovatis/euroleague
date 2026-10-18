# Arena of the week: blocked (2026-10-18)

**Arena picked:** TURKCELL BASKETBALL DEVELOPMENT CENTER (`arena_facts.py --next`), ahead of round 7, Anadolu Efes Istanbul vs Besiktas Istanbul, 2026-10-22T17:30:00Z.

**Error:** `python3 scripts/arena_facts.py --get "TURKCELL BASKETBALL DEVELOPMENT CENTER"` failed in `find_title()` (Wikipedia search) with:

```
urllib.error.HTTPError: HTTP Error 429: Too Many Requests
```

Wikimedia's response: `x-envoy-ratelimited: true`, `retry-after: 23`, "You are making too many requests to the API." Wikidata (`www.wikidata.org/w/api.php`) returned 429 as well. The cloud runner's shared egress IP is rate-limited.

**Tried:** 7 attempts over about 10 minutes (13:18–13:30 UTC) with backoff of 30 s up to 180 s. Every one returned 429. The EuroLeague API worked (`--next` succeeded).

**Not written:** facts.json, photos, posts or cards. No facts were invented.

**Fix ideas:** run `arena_facts.py --get` on the Mac, or give `arena_facts.py` the same Retry-After retry loop that `commons_photo.py` already has (`fetch()`).
