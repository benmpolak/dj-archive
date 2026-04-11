#!/usr/bin/env python3
"""
Discogs collection importer for DJ Archive.
Reads a Discogs collection CSV export, diffs against existing archive by release_id,
and pulls tracklists from the Discogs API for new releases.

Usage: python3 discogs-import.py <collection-csv>
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error

if len(sys.argv) < 2:
    print("Usage: python3 discogs-import.py <collection-csv>")
    sys.exit(1)

CSV_PATH = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
USER_AGENT = 'DJArchiveImporter/1.0 +benmpolak'

# Discogs genre/style -> archive crate
GENRE_CRATE_MAP = {
    'Jazz':          'Jazz',
    'Funk / Soul':   'Soul & R&B',
    'Funk':          'Funk',
    'Soul':          'Soul & R&B',
    'Disco':         'Disco & Boogie',
    'Boogie':        'Disco & Boogie',
    'House':         'House',
    'Deep House':    'House',
    'Electronic':    'Electronic',
    'Latin':         'Afro & World',
    'Brazilian':     'Brazilian',
    'Bossa Nova':    'Brazilian',
    'MPB':           'Brazilian',
    'Samba':         'Brazilian',
    'Reggae':        'Afro & World',
    'African':       'Afro & World',
    'Afrobeat':      'Afro & World',
    'Rock':          'Indie & Rock',
    'Indie Rock':    'Indie & Rock',
    'Pop Rock':      'Indie & Rock',
    'Pop':           'Indie & Rock',
    'Hip Hop':       'Hip Hop',
    'Downtempo':     'Downtempo',
    'Ambient':       'Downtempo',
    'Soul-Jazz':     'Jazz',
    'Jazz-Funk':     'Jazz',
    'Modal':         'Jazz',
    'Fusion':        'Jazz',
    'Afro-Cuban':    'Afro & World',
    'Folk, World, & Country': 'Afro & World',
}

def parse_data(html):
    data_start = html.index('const DATA=') + len('const DATA=')
    depth = 0; in_str = False; escape = False; i = data_start
    while i < len(html):
        c = html[i]
        if escape: escape = False; i += 1; continue
        if c == '\\' and in_str: escape = True; i += 1; continue
        if c == '"': in_str = not in_str; i += 1; continue
        if not in_str:
            if c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return json.loads(html[data_start:i+1]), data_start, i+1
        i += 1

def save_archive(DATA, html, data_start, data_end):
    new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
    new_html = html[:data_start] + new_json + html[data_end:]
    with open(ARCHIVE, 'w') as f:
        f.write(new_html)

def discogs_api(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def map_crates(genres, styles):
    """Given Discogs genres + styles arrays, return sorted list of archive crates."""
    crates = set()
    for g in (genres or []) + (styles or []):
        if g in GENRE_CRATE_MAP:
            crates.add(GENRE_CRATE_MAP[g])
    return sorted(crates) if crates else ['Uncategorized']

def parse_yyyymm(date_added):
    """'2026-03-22 14:05:00' -> 202603"""
    if not date_added: return 0
    m = re.match(r'^(\d{4})-(\d{2})', date_added.strip())
    return int(m.group(1) + m.group(2)) if m else 0

def clean_artist(name):
    """Strip Discogs disambiguation suffixes like 'Stargazers (3)'."""
    return re.sub(r'\s*\(\d+\)\s*$', '', name or '').strip()

# --- Load archive ---
print(f"Loading archive...")
with open(ARCHIVE) as f:
    html = f.read()
DATA, data_start, data_end = parse_data(html)
print(f"  {len(DATA)} existing tracks")

existing_dids = set(str(t['did']) for t in DATA if t.get('did'))
print(f"  {len(existing_dids)} unique Discogs releases already in archive")

# --- Read CSV ---
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
print(f"\nDiscogs CSV: {len(rows)} releases")

new_rows = [r for r in rows if r['release_id'] not in existing_dids]
print(f"New releases to import: {len(new_rows)}")
for r in new_rows:
    print(f"  [{r['Date Added'][:10]}] {r['Artist']} — {r['Title']} (id={r['release_id']})")

# --- Pull tracklists ---
new_tracks = []
for idx, row in enumerate(new_rows, 1):
    rid = row['release_id']
    print(f"\n[{idx}/{len(new_rows)}] Fetching release {rid}...")
    try:
        time.sleep(1.5)  # Rate limit: ~40 req/min, well under Discogs cap
        rel = discogs_api(f'https://api.discogs.com/releases/{rid}')
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} — skipping")
        continue

    release_artist = clean_artist(rel.get('artists_sort') or row['Artist'])
    release_title = rel.get('title') or row['Title']
    year = int(rel.get('year') or 0)
    genres_list = rel.get('genres') or []
    styles_list = rel.get('styles') or []
    g_string = ', '.join(sorted(set(genres_list + styles_list)))
    crates = map_crates(genres_list, styles_list)
    da = parse_yyyymm(row.get('Date Added', ''))
    tracklist = rel.get('tracklist') or []

    print(f"  {release_artist} — {release_title} ({year})")
    print(f"  genres={genres_list}  styles={styles_list}  -> crates={crates}")
    print(f"  tracks in release: {len(tracklist)}")

    # Flatten: expand 'index' entries that have sub_tracks (e.g. suite movements)
    flat = []
    for tr in tracklist:
        if tr.get('type_') == 'index' and tr.get('sub_tracks'):
            parent_title = (tr.get('title') or '').strip()
            for sub in tr['sub_tracks']:
                if sub.get('type_') in (None, '', 'track'):
                    # Prefix parent suite name if sub title is generic like "Movements 1-5"
                    sub_copy = dict(sub)
                    if parent_title and parent_title.lower() not in (sub.get('title') or '').lower():
                        sub_copy['title'] = f"{parent_title} — {sub.get('title','')}"
                    flat.append(sub_copy)
        elif tr.get('type_') in (None, '', 'track'):
            flat.append(tr)
        # else: skip headings, dividers

    added_here = 0
    for tr in flat:
        title = (tr.get('title') or '').strip()
        if not title:
            continue
        # Track may have its own artists (compilations)
        track_artists = tr.get('artists') or []
        if track_artists:
            ta = ';'.join(clean_artist(a.get('name','')) for a in track_artists if a.get('name'))
        else:
            ta = release_artist

        new_track = {
            'a':   ta,
            't':   title,
            'al':  release_title,
            'r':   year,
            'd':   0,
            'e':   0,
            'v':   0,
            'tp':  0,
            'ins': 0,
            'c':   list(crates),
            'vb':  '',
            'n':   0,
            'p':   0,
            'g':   g_string,
            'sid': f'spotify:local:::{ta}:{title}',
            'vy':  1,
            'era': 'Latest',
            'tags': [],
            'did': str(rid),
            'da':  da,
        }
        new_tracks.append(new_track)
        added_here += 1
    print(f"  + {added_here} tracks queued")

# --- Append and save ---
print(f"\n{'='*50}")
print(f"Total new tracks to add: {len(new_tracks)}")
print(f"{'='*50}")

if new_tracks:
    DATA.extend(new_tracks)
    print(f"\nNew DATA size: {len(DATA)}")
    print("Saving archive...")
    save_archive(DATA, html, data_start, data_end)
    print("Done.")
else:
    print("\nNothing to add.")
