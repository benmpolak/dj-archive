# Labels and credits enrichment (pilot)

Pulled 13 November 2026. Nothing here changes the archive: the scripts only read `index.html` (through `spotify_sync.read_data`) and write into this folder. No Spotify calls, no tokens, generic User-Agent `DJArchiveEnrichment/0.1`.

## Files

- `discogs-releases.json`: all 400 Discogs releases behind the 2,630 vinyl tracks (fetched 22:03–22:24 UTC, 0 failed). Per release: title, artists, labels and catalogue numbers, year (of that pressing, not the original), country, formats, genres, styles, release-level credits, companies (pressed by, mastered at and so on), tracklist with per-track credits, and which archive tracks point at it.
- `discogs-connections.json`: summary built from that file. Top labels, top credited people by role family, cross-artist links (one person credited on records by different artists), sidemen who also have their own record on the shelf, labels shared by 3+ artists, shared companies, styles, decades. Counts are releases, not tracks.
- `musicbrainz-pilot.json`: 150 most-played non-vinyl tracks with a real Spotify id, the frozen sample, and per track the match (recording, score, release used), label, and credits (recording-level, songwriters via the work, release-level).
- `discogs_fetch.py`, `discogs_connections.py`, `musicbrainz_pilot.py`: the scripts.

## Re-running or resuming

From the `Dj Archive` folder:

- `python3 -B enrichment/discogs_fetch.py` fetches only the releases not yet in the file (new vinyl purchases get picked up the same way). `--retry` retries earlier failures. Unauthenticated, one request every 2.6 s; stops at once on HTTP 429.
- `python3 -B enrichment/discogs_connections.py` rebuilds the summary offline.
- `python3 -B enrichment/musicbrainz_pilot.py` finishes any unfinished part of the 150-track sample and never goes beyond it. `--retry-errors` retries failed tracks. One request per 1.1 s; a "server busy" 503 is retried at most 4 times with growing pauses.

Keep `-B` so no `__pycache__` lands in the repo. This folder is untracked; decide before committing anything, since the JSON files are bulky API output.

## Known limits

- Discogs credits are for the pressing Ben owns. Reissue labels (Mr Bongo, Athens Of The North) count as labels, so "label" means the shelf label, not always the original one.
- Role families are keyword rules over Discogs role text. Spot-checked, not hand-verified.
- MusicBrainz matches that land on a compilation, DJ mix or rehearsal recording usually carry a label but few or no credits.
