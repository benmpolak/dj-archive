# DJ Archive

A single-page web app that serves as a personal DJ music archive — 17,325 tracks curated over 14 years. No algorithms; every track was chosen by ear.

## Architecture

The entire app is a single `index.html` file (~6MB). It contains all HTML, CSS, and JavaScript inline, plus a large `const DATA=` array holding every track as a JSON object. There is no build step or backend — it's a fully static, self-contained page.

### Track data schema
Each track object in `DATA`: `{a (artist), t (title), al (album), r (release year), d (danceability 0-1), e (energy 0-1), v (valence 0-1), tp (tempo/BPM), ins (instrumentalness), c (crates array), vb (vibe string), n (playlist count), p (popularity), g (genres string), sid (Spotify ID — 22 chars if matched, or spotify:local:... if unmatched), vy (1=vinyl), era (string), tags (array), did (Discogs release ID), da (YYYYMM date added)}`

### Key stats
- 2,531 vinyl tracks (vy=1)
- 402 tracks still need Spotify matching (have spotify:local placeholder IDs)
- `_spArtists` JS Set routes known Spotify artists to Spotify search, others to YouTube

## Key features

- **Filtering & search** — sidebar with genre chips, mood/vibe chips, era chips, crate chips, subgenre chips, BPM zones, tempo range inputs, and free-text search
- **Sorting** — by date added, artist, title, BPM, year, etc.
- **Spotify integration** — inline play/preview via Spotify embeds, save filtered results as Spotify playlists, open tracks in Spotify app
- **Smart play buttons** — green = Spotify (real ID), green search = Spotify search (artist known on Spotify), red = YouTube search (fallback)
- **Set Builder** — drag-and-drop setlist builder with BPM flow indicators and transition helpers
- **Dig Deeper** — type an artist to discover related artists in the collection based on shared genres, moods, and crates
- **Rediscover** — surface random forgotten tracks
- **Stats dashboard** — collection statistics with bar charts, vinyl collection section (top artists, crate/decade breakdown, Spotify match %, vinyl-only artists)
- **Quick-edit menu** — inline editing of track metadata (vibes, crates, etc.) via hover pencil icon
- **Vinyl indicator** — inline SVG vinyl badge, links to Discogs release when did is present
- **Mini player** — persistent bottom audio player with skip controls
- **Discogs link** — links to Discogs collection (user: benmpolak)

## Supporting files

- `spotify-auth.html` — OAuth helper page that grabs a Spotify access token via implicit grant flow (used by the matcher script)
- `spotify-matcher.py` — Python script that batch-matches `spotify:local:` tracks to real Spotify IDs via the Spotify Search API. Processes ~330 albums per run with checkpointing. Needs a Spotify API token to run.
- `match-checkpoint.json` — checkpoint state for the matcher (processed albums, match count)
- `fix-data.py` — script for batch data fixes (dates, duplicates, vinyl crate/vibe assignments)
- `_old-backup-pre-vinyl.html` / `_old-v2-original.html` — earlier versions of the archive (backups)

## Development notes

- Editing `index.html` directly is the workflow. The `DATA` array is on line ~649 (single massive line) — avoid reading the whole file. Use grep/search to find specific sections.
- The `_spArtists` set is built on line ~650, right after DATA.
- The JavaScript logic (rendering, filtering, sorting, set builder, Spotify integration) follows the DATA array starting around line ~700+.
- CSS is all in a `<style>` block at the top of the file.
- The app uses a dark theme with CSS custom properties defined in `:root`.
- YouTube search URLs use simple format: `youtube.com/results?search_query=` + artist (first before semicolon) + title. No quotes, no album.

## Previous session work
- Fixed 2,005 false vinyl tags
- Fixed wrong dates on 30 vinyl expansion tracks
- Removed 23 duplicates (17 more found and removed this session)
- Assigned proper crates/vibes to 1,861 vinyl tracks
- Genre-fixed 196 well-known artists across 2,269 tracks

## Gig Radar rules

- Only explicitly listed performers qualify. A name in an event title never qualifies an artist, including titles copied into a scraper's names field.
- Require structured source lineup/performer evidence or explicitly verified manual performers. Drop uncertain cached matches, rather than labelling them confirmed.
- If Blue Note's or Ronnie Scott's listing is blocked or empty, keep that venue's upcoming shows from the last good listings (re-checked like saved data, dated in `carried_from`) and say so in the page note. With no saved shows to keep, the run still stops.
- Exclude cancelled/postponed events. Keep performer evidence in the exported data so the archive and desk screen apply the same rule.
- Run `python3 build.py` after changing `guest.js`, `dealer.js` or `design-pass.css`. It rebuilds the injected modules and shared device catalogue without changing imported track data.

## Front page and Discogs imports

- Preserve Ben's front-page rules: one card per record across shelves; one per artist within a shelf, with separate various-artists compilations treated as records. Keep existing pins and taste exclusions in `guest.js`.
- Just bought on vinyl shows purchases from the current year, newest first. Albums/EPs need at least four tracks, a verified Spotify recording and their actual sleeve. Two-track singles qualify only when Ben explicitly pins the release. Off-Spotify exceptions remain the existing hand-curated overrides.
- A compilation must appear as one physical release with its own title, sleeve and Discogs link, even when its tracks already exist under other albums. The Cuban boxset is represented by the DJ Koco mix override, never again as individual compilation-track cards.
- `vinyl-records.json` holds verified physical-release metadata, purchase dates and references to archive tracks for the November 2026 additions onward. `build.py` injects it into the guest layer. The Spotify staging workflow must copy it, so later playlist updates preserve the shelf.
- Reuse existing recordings when verified; preserve their Spotify IDs, album metadata, listening counts, archive dates and any prior vinyl ownership. Store the physical purchase date on the release rather than replacing an older archive date. Do not substitute a different remix or Spotify-only bonus track for the actual pressing's tracklist.
- Stage Discogs imports and compare against the prior archive before applying. Keep raw exports, API responses and backups out of commits. For music-only imports use `python3 build.py --catalogue-only`, preserving Gig Radar. Check the actual desktop/mobile shelves and publication before reporting completion.
