# Weekly Spotify import

Ben authorised a weekly direct Spotify import on 22 September 2026. The selected scope is in `spotify-sync.json`: the current calendar month's playlist plus eleven regular playlists. Sunshine dance and Hip Hop were selected as the two additional regulars from the recorded June-September activity. During the first seven days of a month, also check the previous month to catch additions made after its last weekly run. Never automatically include other playlists based only on discovering them in the account. Regulars are pinned to exact Spotify IDs, so renaming them does not lose the connection; ambiguous monthly names stop for review. Brasil and Hispanic were verified against every Spotify ID in Ben’s 22 September exports, avoiding older lower-case playlists with the same names.

The scheduled Codex task runs on Monday at 08:30 Europe/London in the existing task. This is a local job: the Mac and Codex need to be available for it to execute. It is not a server-side Spotify subscription.

## Connection

The existing DJ Archive Matcher app is used, with its registered `http://127.0.0.1:8080` return address. `python3 spotify_sync.py connect` opens a temporary loopback listener and prints the Spotify authorisation URL. The user approves Spotify's read-only playlist scopes. No client secret is needed. Tokens are saved with mode 0600 under `~/desk-screen/.secrets/archive-sync/`, outside the public repository. Never copy them to Git, public reports, task messages or browser storage.

Spotify currently gives these refresh tokens a six-month lifetime. If the token expires or access is revoked, ask Ben to reconnect. Do not keep retrying invalid credentials. The user must have access to the selected playlists through ownership or collaboration, and the development app requires its owner's Premium subscription.

## Run

1. Read project instructions and inspect Git status. Preserve `.claude/`, local CSV folders, backups and all other unrelated changes. Fetch `origin/main` with the normal GitHub credential helper. Fast-forward only if the tracked working tree is clean; stop for overlapping local changes or divergence.
2. Run `python3 spotify_sync.py sync` for a preview. It fetches every page through the official API, validates complete counts and stable playlist snapshots, and stages the existing `playlist-import.py` in a temporary folder. The old `pull-playlists.py` is a historical embed-based fallback capped at 100; do not use it for the scheduled sync.
3. Inspect the private `latest-report.json`. Missing regular playlists, duplicate names, incomplete pagination or failed permissions are blockers. A not-yet-created monthly playlist is reported separately; regular playlists can still update. Do not create a monthly playlist without Ben's instruction.
4. If changes are expected and the tracked working tree is clean, run `python3 spotify_sync.py sync --apply`. It fetches a fresh snapshot, so use the resulting report for publication. It backs up every changed output under `_backup-spotify-sync-*` before applying it.
5. Run the relevant Python tests and `node --test tests/music-core.test.cjs`, then `git diff --check`. Inspect the diff summary and confirm only the exact files in `latest-report.json` changed. The allowed generated outputs are `index.html`, `add-ledger.json`, `guest-art.json`, `music/manifest.json`, and `music/tracks-*.json`. Never stage raw exports, snapshots, credentials, existing untracked files or unrelated changes.
6. Ben authorised publishing the successful weekly music import. Commit only those verified outputs, fetch once more, and push normally to `main`; never force-push. If the remote advances, reconcile before publishing, preserving unrelated remote changes. Check that the GitHub Pages build succeeded for the published commit, verify the live manifest count, and check a new record on the live archive when records were added.
7. Run `~/.local/bin/node ~/desk-screen/scripts/refresh-programmes.mjs` so The Dial's programme library receives the published catalogue. Its existing helper keeps future runs up to date; already-started FM programmes remain stable. Do not touch the defunct ChatGPT-hosted Dial.

The build uses `build.py --catalogue-only`. Never run a full Gig Radar refresh during this import: music automation must not prune or republish unrelated gig listings. No Spotify playlist write scope is requested and no music is removed from the archive when it disappears from a playlist. Existing listening counts, vinyl ownership, dates, titles, tags and manually curated metadata are preserved. New tracks use Spotify's supplied metadata and playlist-to-crate mapping; unavailable BPM, audio features, genres or moods are not invented. Playlist imports do not update listening-history rankings.

After a successful run, update the existing Ben OS DJ Archive note and keep the last reported result privately so unchanged checks do not create repetitive messages. Report a short summary when music was added, publication failed, a monthly playlist is missing, or reconnection/user action is needed. Stay quiet when there is no change.

## Checks

`python3 -m unittest discover -s tests -p 'test_spotify_sync.py'`

Tests use synthetic records, covering full pagination beyond 100 items, rejected truncation/foreign pagination, calendar rollover, missing/ambiguous playlist names, append-only imports, retained listening history, safe HTML serialisation, idempotence and private file permissions.

Official references: [playlist items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items), [PKCE sign-in](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow), [refresh tokens](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens).
