# Archive, Gig Radar and Wax On FM

The archive remains the source for music choices. The desk screen is another client, not a second catalogue or a second selection engine.

## Shared integration

- `music-core.js` is a UI-independent, versioned selection contract used by the website. A selection carries a name, source and ordered stable track IDs. It round-trips through saved selections, copied links and exported JSON without reselecting or reordering tracks.
- `music/manifest.json` describes the catalogue revision and small track lookup files. Given a Spotify ID, the screen loads `music/tracks-{first character}.json` and looks up the full ID. These contain musical metadata, not account credentials or personal listening statistics.
- `gigs-data.json` carries explicit performer evidence. Names in titles cannot make an artist eligible. The website's record detail and gig listening links use the same artists and catalogue.
- `python3 build.py` rebuilds the existing injected modules, both gig pages and the device catalogue. It verifies the imported track data has not changed.

## Wax On FM next

Keep selection/programming in the archive. Move the pure portion of `dealer.js` into a shared module when building the station scheduler; do not reimplement its scoring in firmware. Each scheduled show should carry the same version-1 selection, plus a show ID and its scheduled window in Europe/London.

Playback must be separate from the published schedule: the schedule says what is offered; Spotify/Sonos supplies what is actually playing, position and device. Do not display a track as playing merely because its scheduled time has arrived. Playback credentials stay out of static JSON and Git.

The phone/site can open and keep a show as a normal selection. The desk screen displays sleeve, show name, actual track and next show; it controls the existing room player through the authenticated playback integration. The archive does not yet implement the nightly scheduler, Spotify/Sonos control or firmware.

## Local saves and privacy

Named selections, the current set and metadata overrides persist in this browser. They do not automatically sync to another device. Links and JSON exports provide an explicit portable copy. `?owner` only changes the interface and is not authentication.

## Run / verify

- `python3 build.py`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `node --test tests/music-core.test.cjs`
- `python3 -m http.server 8137 --bind 127.0.0.1`

GitHub Pages publishes the repository root from main. Run the checks above before pushing a release.
