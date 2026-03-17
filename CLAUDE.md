# DJ Archive

A single-page web app that serves as a personal DJ music archive — 15,181 tracks curated over 14 years. No algorithms; every track was chosen by ear.

## Architecture

The entire app is a single `index.html` file (~6MB). It contains all HTML, CSS, and JavaScript inline, plus a large `const DATA=` array holding every track as a JSON object. There is no build step or backend — it's a fully static, self-contained page.

### Track data fields
Each track object in `DATA` includes fields like: `a` (artist), `t` (title), `al` (album), `sid` (Spotify ID or `spotify:local:` for unlinked), plus metadata for year, BPM, genre, mood/vibe, crate, era, tags, and more.

## Key features

- **Filtering & search** — sidebar with genre chips, mood/vibe chips, era chips, crate chips, subgenre chips, BPM zones, tempo range inputs, and free-text search
- **Sorting** — by date added, artist, title, BPM, year, etc.
- **Spotify integration** — inline play/preview via Spotify embeds, save filtered results as Spotify playlists, open tracks in Spotify app
- **Set Builder** — drag-and-drop setlist builder with BPM flow indicators and transition helpers
- **Dig Deeper** — type an artist to discover related artists in the collection based on shared genres, moods, and crates
- **Rediscover** — surface random forgotten tracks
- **Stats dashboard** — collection statistics with bar charts
- **Quick-edit menu** — inline editing of track metadata (vibes, crates, etc.)
- **Vinyl indicator** — marks tracks that are also owned on vinyl
- **Mini player** — persistent bottom audio player with skip controls

## Supporting files

- `spotify-auth.html` — OAuth helper page that grabs a Spotify access token via implicit grant flow (used by the matcher script)
- `spotify-matcher.py` — Python script that batch-matches `spotify:local:` tracks to real Spotify IDs via the Spotify Search API. Processes ~330 albums per run with checkpointing
- `match-checkpoint.json` — checkpoint state for the matcher (processed albums, match count)
- `_old-backup-pre-vinyl.html` / `_old-v2-original.html` — earlier versions of the archive (backups)

## Development notes

- Editing `index.html` directly is the workflow. The `DATA` array starts at line ~649 and is very large — avoid reading the whole file. Use grep/search to find specific sections.
- The JavaScript logic (rendering, filtering, sorting, set builder, Spotify integration) follows the `DATA` array starting around line ~700+.
- CSS is all in a `<style>` block at the top of the file.
- The app uses a dark theme with CSS custom properties defined in `:root`.
