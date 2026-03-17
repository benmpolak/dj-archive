# DJ Archive

A single-page web app that serves as a personal DJ music archive — 16,544 tracks curated over 14 years. No algorithms; every track was chosen by ear.

## Architecture

The entire app is a single `index.html` file (~6MB). It contains all HTML, CSS, and JavaScript inline, plus a large `const DATA=` array holding every track as a JSON object. There is no build step or backend — it's a fully static, self-contained page.

### Track data schema
Each track object in `DATA`: `{a (artist), t (title), al (album), r (release year), d (danceability 0-1), e (energy 0-1), v (valence 0-1), tp (tempo/BPM), ins (instrumentalness), c (crates array), vb (vibe string), n (playlist count), p (popularity), g (genres string), sid (Spotify ID — 22 chars if matched, or spotify:local:... if unmatched), vy (1=vinyl), era (string), tags (array), did (Discogs release ID), da (YYYYMM date added)}`

### Key stats
- ~2,380 vinyl tracks (vy=1)
- ~1,700 tracks still need Spotify matching (have spotify:local placeholder IDs)
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
