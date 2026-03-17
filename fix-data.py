#!/usr/bin/env python3
"""Apply data fixes to the DJ Archive: dates, duplicates, vinyl crates, vinyl vibes."""
import json, re, os

ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

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
                if depth == 0: return json.loads(html[data_start:i+1]), data_start, i+1
        i += 1

print("Loading archive...")
with open(ARCHIVE) as f:
    html = f.read()
DATA, data_start, data_end = parse_data(html)
print(f"Loaded {len(DATA)} tracks")

# === 1. FIX WRONG DATES ===
date_fixes = 0

# Discogs ID to correct date mapping
did_to_date = {
    9401499: 201705,
    35089718: 202501,
    33832128: 202501,
    32535108: 202401,
    35501086: 202501,
}

for t in DATA:
    if t.get('da') == 202602:
        sid = t.get('sid', '')
        is_local = sid.startswith('spotify:local') or sid == 'spotify'

        if is_local:
            did = t.get('did')
            if did and did in did_to_date:
                t['da'] = did_to_date[did]
                date_fixes += 1
            elif not did:
                t['da'] = 202501
                date_fixes += 1
        else:
            # Real Spotify ID tracks with wrong dates
            artist = t.get('a', '').lower()
            title = t.get('t', '').lower()
            if 'erykah badu' in artist and 'back in the day' in title:
                t['da'] = 201707
                date_fixes += 1
            elif 'bobby hutcherson' in artist and 'montara' in title:
                t['da'] = 202501
                date_fixes += 1

print(f"1. Fixed {date_fixes} wrong dates")

# === 2. REMOVE DUPLICATES ===
# Group by normalized artist+title
from collections import defaultdict
import unicodedata

def norm(s):
    s = s.lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

groups = defaultdict(list)
for i, t in enumerate(DATA):
    key = (norm(t.get('a', '')), norm(t.get('t', '')))
    groups[key].append(i)

to_remove = set()
for key, indices in groups.items():
    if len(indices) <= 1:
        continue
    tracks = [(i, DATA[i]) for i in indices]

    # Pick best: real Spotify ID wins, then most data
    def score(pair):
        idx, t = pair
        s = 0
        if t.get('sid') and len(t.get('sid', '')) == 22: s += 100
        if t.get('vy'): s += 10
        if t.get('did'): s += 5
        if t.get('g'): s += 3
        if t.get('vb') and t['vb'] != 'Deep & Mellow': s += 2
        return s

    tracks.sort(key=score, reverse=True)
    best_idx, best_track = tracks[0]

    # Merge: earliest da, preserve vinyl flag, preserve Discogs ID
    earliest_da = min(t.get('da', 999999) for _, t in tracks)
    has_vinyl = any(t.get('vy') for _, t in tracks)
    has_did = next((t.get('did') for _, t in tracks if t.get('did')), None)

    if earliest_da < 999999:
        best_track['da'] = earliest_da
    if has_vinyl:
        best_track['vy'] = 1
    if has_did and not best_track.get('did'):
        best_track['did'] = has_did

    # Mark others for removal
    for idx, _ in tracks[1:]:
        to_remove.add(idx)

if to_remove:
    DATA = [t for i, t in enumerate(DATA) if i not in to_remove]
    print(f"2. Removed {len(to_remove)} duplicates, {len(DATA)} tracks remain")
else:
    print(f"2. No duplicates found")

# === 3. FIX VINYL CRATES ===
genre_to_crate = {
    'jazz': 'Jazz', 'fusion': 'Jazz', 'bebop': 'Jazz', 'bossa nova': 'Jazz',
    'hard bop': 'Jazz', 'cool jazz': 'Jazz', 'free jazz': 'Jazz', 'soul jazz': 'Jazz',
    'jazz fusion': 'Jazz', 'vocal jazz': 'Jazz', 'jazz funk': 'Jazz',
    'latin jazz': 'Jazz', 'jazz ballads': 'Jazz', 'experimental jazz': 'Jazz',
    'ambient jazz': 'Jazz', 'brazilian jazz': 'Jazz',
    'house': 'House', 'deep house': 'House', 'uk garage': 'House', 'broken beat': 'House',
    'chicago house': 'House', 'acid house': 'House', 'lo-fi house': 'House',
    'disco house': 'House', 'funky house': 'House', 'uk funky': 'House',
    'latin house': 'House', 'jazz house': 'House',
    'disco': 'Disco & Boogie', 'boogie': 'Disco & Boogie', 'nu-disco': 'Disco & Boogie',
    'nu disco': 'Disco & Boogie', 'post-disco': 'Disco & Boogie', 'italo disco': 'Disco & Boogie',
    'soul': 'Soul & R&B', 'r&b': 'Soul & R&B', 'neo soul': 'Soul & R&B', 'motown': 'Soul & R&B',
    'classic soul': 'Soul & R&B', 'northern soul': 'Soul & R&B', 'quiet storm': 'Soul & R&B',
    'philly soul': 'Soul & R&B', 'retro soul': 'Soul & R&B', 'indie soul': 'Soul & R&B',
    'alternative r&b': 'Soul & R&B', 'uk r&b': 'Soul & R&B',
    'funk': 'Funk', 'afrobeat': 'Funk',
    'mpb': 'Brazilian', 'samba': 'Brazilian', 'tropicalia': 'Brazilian',
    'new mpb': 'Brazilian',
    'rock': 'Indie & Rock', 'indie': 'Indie & Rock', 'post-punk': 'Indie & Rock',
    'indie rock': 'Indie & Rock', 'neo-psychedelic': 'Indie & Rock',
    'hip hop': 'Hip Hop', 'rap': 'Hip Hop', 'trip hop': 'Hip Hop',
    'jazz rap': 'Hip Hop', 'east coast hip hop': 'Hip Hop', 'old school hip hop': 'Hip Hop',
    'downtempo': 'Downtempo', 'ambient': 'Downtempo', 'dub': 'Downtempo', 'idm': 'Downtempo',
    'world': 'Afro & World', 'latin': 'Afro & World', 'reggae': 'Afro & World',
    'african': 'Afro & World', 'highlife': 'Afro & World',
    'electronic': 'Electronic', 'techno': 'Electronic',
}

crate_fixes = 0
for t in DATA:
    if not t.get('vy'):
        continue
    crates = t.get('c', [])
    if not any(c in ('Uncategorized', 'Uncategorised') for c in crates):
        continue

    genres = t.get('g', '').lower().split(',')
    genres = [g.strip() for g in genres if g.strip()]

    new_crate = None
    for g in genres:
        if g in genre_to_crate:
            new_crate = genre_to_crate[g]
            break

    if new_crate:
        t['c'] = [new_crate if c in ('Uncategorized', 'Uncategorised') else c for c in crates]
        crate_fixes += 1

print(f"3. Fixed {crate_fixes} vinyl crate assignments")

# === 4. FIX VINYL VIBES ===
genre_to_vibe = {
    'funk': 'Groover', 'afrobeat': 'Groover', 'jazz funk': 'Groover', 'jazz-funk': 'Groover',
    'disco': 'Feel Good', 'boogie': 'Feel Good', 'motown': 'Feel Good',
    'post-disco': 'Feel Good', 'nu disco': 'Feel Good', 'nu-disco': 'Feel Good',
    'italo disco': 'Feel Good', 'disco house': 'Feel Good',
    'bossa nova': 'Sunshine', 'mpb': 'Sunshine', 'balearic': 'Sunshine',
    'reggae': 'Sunshine', 'new mpb': 'Sunshine', 'samba': 'Sunshine',
    'tropicalia': 'Sunshine',
    'soul': 'Soulful', 'r&b': 'Soulful', 'neo soul': 'Soulful',
    'classic soul': 'Soulful', 'northern soul': 'Soulful', 'quiet storm': 'Soulful',
    'philly soul': 'Soulful', 'retro soul': 'Soulful', 'indie soul': 'Soulful',
    'alternative r&b': 'Soulful', 'uk r&b': 'Soulful',
    'house': 'Peak Time', 'uk garage': 'Peak Time', 'deep house': 'Peak Time',
    'chicago house': 'Peak Time', 'acid house': 'Peak Time', 'funky house': 'Peak Time',
    'uk funky': 'Peak Time', 'broken beat': 'Peak Time', 'lo-fi house': 'Peak Time',
    'latin house': 'Peak Time', 'jazz house': 'Peak Time',
    'jazz': 'Instrumental Journey', 'fusion': 'Instrumental Journey',
    'bebop': 'Instrumental Journey', 'hard bop': 'Instrumental Journey',
    'cool jazz': 'Instrumental Journey', 'free jazz': 'Instrumental Journey',
    'soul jazz': 'Instrumental Journey', 'jazz fusion': 'Instrumental Journey',
    'vocal jazz': 'Instrumental Journey', 'latin jazz': 'Instrumental Journey',
    'jazz ballads': 'Instrumental Journey', 'experimental jazz': 'Instrumental Journey',
    'ambient jazz': 'Instrumental Journey', 'brazilian jazz': 'Instrumental Journey',
    'downtempo': 'Chill', 'dub': 'Chill', 'ambient': 'Chill', 'trip hop': 'Chill',
    'idm': 'Chill',
}

vibe_fixes = 0
for t in DATA:
    if not t.get('vy'):
        continue
    if t.get('vb') != 'Deep & Mellow':
        continue

    genres = t.get('g', '').lower().split(',')
    genres = [g.strip() for g in genres if g.strip()]

    new_vibe = None
    for g in genres:
        if g in genre_to_vibe:
            new_vibe = genre_to_vibe[g]
            break

    if new_vibe:
        t['vb'] = new_vibe
        vibe_fixes += 1

print(f"4. Fixed {vibe_fixes} vinyl vibe assignments")

# === Save ===
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
new_html = html[:data_start] + new_json + html[data_end:]
with open(ARCHIVE, 'w') as f:
    f.write(new_html)
print(f"\nSaved! Archive now has {len(DATA)} tracks.")
