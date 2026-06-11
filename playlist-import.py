#!/usr/bin/env python3
"""
Playlist importer for DJ Archive.
Reads Exportify CSVs from a folder and merges new tracks into index.html DATA.
Existing tracks (matched by Spotify ID) get new crates merged in.
New tracks are appended with full audio features from the CSV.

Usage: python3 playlist-import.py "Playlists 11 april 2026"
"""
import csv, json, os, re, sys, glob, shutil
from datetime import datetime
from collections import defaultdict

if len(sys.argv) < 2:
    print("Usage: python3 playlist-import.py <playlist-folder>")
    sys.exit(1)

FOLDER = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
PLAYLIST_DIR = os.path.join(HERE, FOLDER)

# Playlist filename -> list of crates to assign
# Monthly / mixed playlists map to [] so tracks only get crates from other playlists they appear in
PLAYLIST_CRATES = {
    'Africa_Sounds':         ['Afro & World'],
    'All_That_Jazz':         ['Jazz'],
    'April_2026':            [],
    'Brasil':                ['Brazilian'],
    'Brasil_Novo':           ['Brazilian'],
    'Brazilian_Boogie':      ['Brazilian', 'Disco & Boogie'],
    'Hispanic':              ['Afro & World'],
    'Hip_Hop':               ['Hip Hop'],
    '70s_and_80s_Chilled_':  [],
    'Sunshine_sounds':       [],
    'May_2026':              [],
    'June_2026':             [],
    'March_2026':            [],
    'Older_Dance':           ['House'],
    'R&B_Soul':              ['Soul & R&B'],
    'Soul_&_Disco_revival_': ['Soul & R&B', 'Disco & Boogie'],
    'Soul_&_Disco_revival':  ['Soul & R&B', 'Disco & Boogie'],
    'Summer_Sounds':         [],
    'Sunshine_dance':        ['House'],
}

def playlist_key(filename):
    """'Brasil (1).csv' -> 'Brasil'"""
    base = os.path.basename(filename)
    base = re.sub(r'\.csv$', '', base, flags=re.I)
    base = re.sub(r'\s*\(\d+\)\s*$', '', base)
    return base.strip()

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

def safe_float(v, default=0):
    try: return float(v) if v not in (None, '') else default
    except: return default

def safe_int(v, default=0):
    try: return int(float(v)) if v not in (None, '') else default
    except: return default

def parse_year(rel):
    if not rel: return 0
    m = re.match(r'^(\d{4})', rel.strip())
    return int(m.group(1)) if m else 0

def parse_yyyymm(added_at):
    """'2026-04-04T18:22:20Z' -> 202604 (int)"""
    if not added_at: return 0
    m = re.match(r'^(\d{4})-(\d{2})', added_at.strip())
    if m: return int(m.group(1) + m.group(2))
    return 0

def normalize_genres(g):
    if not g: return ''
    parts = [p.strip() for p in g.split(',') if p.strip()]
    return ', '.join(parts)

def extract_sid(track_uri):
    """'spotify:track:1Fuxx2SM49Br613ri3I0h6' -> '1Fuxx2SM49Br613ri3I0h6'
       Returns None for local tracks or malformed URIs."""
    if not track_uri: return None
    m = re.match(r'^spotify:track:([A-Za-z0-9]{22})$', track_uri.strip())
    return m.group(1) if m else None

# --- Load archive ---
print(f"Loading {ARCHIVE}...")
with open(ARCHIVE) as f:
    html = f.read()
DATA, data_start, data_end = parse_data(html)
print(f"  {len(DATA)} existing tracks")

# Build sid -> index lookup
sid_index = {}
for i, t in enumerate(DATA):
    sid = t.get('sid', '')
    if sid and not sid.startswith('spotify:local:'):
        sid_index[sid] = i

# Fallback lookup by (first artist, title) — the same song often carries a
# different Spotify ID on different releases (single vs album vs comp), so
# sid alone re-imports tracks the archive already has.
def title_key(artist, title):
    a = re.split(r'[;,]', artist or '')[0].strip().lower()
    return (a, (title or '').strip().lower())

title_index = {}
for i, t in enumerate(DATA):
    title_index.setdefault(title_key(t.get('a'), t.get('t')), i)

# --- Read all CSVs ---
csv_files = sorted(glob.glob(os.path.join(PLAYLIST_DIR, '*.csv')))
print(f"\nFound {len(csv_files)} CSV files in {PLAYLIST_DIR}")

# sid -> {row: latest csv row dict, playlists: set of playlist keys, crates: set of crate strings}
tracks = {}

for csv_path in csv_files:
    pkey = playlist_key(csv_path)
    crates_for_playlist = PLAYLIST_CRATES.get(pkey, [])
    print(f"  [{pkey}] crates={crates_for_playlist}")
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            sid = extract_sid(row.get('Track URI', ''))
            if not sid:
                continue
            if sid not in tracks:
                tracks[sid] = {'row': row, 'playlists': set(), 'crates': set()}
            else:
                # Keep the row with the latest 'Added At' so audio features are consistent
                if (row.get('Added At') or '') > (tracks[sid]['row'].get('Added At') or ''):
                    tracks[sid]['row'] = row
            tracks[sid]['playlists'].add(pkey)
            for cr in crates_for_playlist:
                tracks[sid]['crates'].add(cr)
            count += 1
    print(f"     {count} track rows")

print(f"\nTotal unique tracks across CSVs: {len(tracks)}")

# --- Merge into DATA ---
new_count = 0
updated_count = 0
crates_added_total = 0

for sid, info in tracks.items():
    row = info['row']
    new_crates = info['crates']

    if sid not in sid_index:
        # Same song under a different release ID? Treat as existing.
        ti = title_index.get(title_key(row.get('Artist Name(s)'), row.get('Track Name')))
        if ti is not None:
            sid = DATA[ti].get('sid')

    if sid in sid_index:
        # Existing track: merge crates if any
        idx = sid_index[sid]
        existing = DATA[idx]
        existing_crates = set(existing.get('c') or [])
        additions = new_crates - existing_crates
        if additions:
            # Drop Uncategorized if we're adding a real crate
            merged = (existing_crates | additions) - {'Uncategorized', 'Uncategorised'} \
                     if (existing_crates | additions) - {'Uncategorized', 'Uncategorised'} \
                     else existing_crates | additions
            existing['c'] = sorted(merged)
            updated_count += 1
            crates_added_total += len(additions)
        # Bump playlist count if new value is higher
        pl_count = len(info['playlists'])
        if pl_count > safe_int(existing.get('n'), 0):
            existing['n'] = pl_count
    else:
        # New track
        crates = sorted(new_crates) if new_crates else ['Uncategorized']
        new_track = {
            'a':   row.get('Artist Name(s)', '') or '',
            't':   row.get('Track Name', '') or '',
            'al':  row.get('Album Name', '') or '',
            'r':   parse_year(row.get('Release Date', '')),
            'd':   round(safe_float(row.get('Danceability')), 3),
            'e':   round(safe_float(row.get('Energy')), 3),
            'v':   round(safe_float(row.get('Valence')), 3),
            'tp':  round(safe_float(row.get('Tempo')), 1),
            'ins': round(safe_float(row.get('Instrumentalness')), 4),
            'c':   crates,
            'vb':  '',
            'n':   len(info['playlists']),
            'p':   safe_int(row.get('Popularity')),
            'g':   normalize_genres(row.get('Genres', '')),
            'sid': sid,
            'vy':  0,
            'era': 'Latest',
            'tags': [],
            'did': '',
            'da':  parse_yyyymm(row.get('Added At', '')) or 202604,
        }
        DATA.append(new_track)
        new_count += 1

# --- Save ---
print(f"\n{'='*50}")
print(f"New tracks added:        {new_count}")
print(f"Existing tracks updated: {updated_count} (crates merged)")
print(f"Crate additions total:   {crates_added_total}")
print(f"New DATA size:           {len(DATA)}")
print(f"{'='*50}")

print("\nSaving archive...")
save_archive(DATA, html, data_start, data_end)
print("Done.")
