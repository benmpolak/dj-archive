#!/usr/bin/env python3
"""
Spotify batch matcher for DJ Archive.
Saves progress every 50 albums. Run ~350 albums per day.
Usage: python3 spotify-matcher.py YOUR_SPOTIFY_TOKEN
"""
import json, re, time, urllib.request, urllib.parse, unicodedata, sys, os

if len(sys.argv) < 2:
    print("Usage: python3 spotify-matcher.py YOUR_SPOTIFY_TOKEN")
    sys.exit(1)

TOKEN = sys.argv[1]
ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
CHECKPOINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'match-checkpoint.json')
MAX_ALBUMS = 330  # Stop after this many to stay under rate limit

def norm(s):
    s = s.lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

def sim(a, b):
    a, b = norm(a), norm(b)
    if a == b: return 1.0
    if a in b or b in a: return 0.85
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb: return 0
    return len(wa & wb) / max(len(wa), len(wb))

def api(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def log(msg):
    print(msg, flush=True)

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

def save_archive(DATA, html, data_start, data_end):
    new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
    new_html = html[:data_start] + new_json + html[data_end:]
    with open(ARCHIVE, 'w') as f:
        f.write(new_html)
    return new_html, data_start, data_start + len(new_json)

def save_checkpoint(processed_keys, matched_total, day):
    with open(CHECKPOINT, 'w') as f:
        json.dump({'processed': list(processed_keys), 'matched': matched_total, 'day': day}, f)

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            cp = json.load(f)
        return set(tuple(k) for k in cp['processed']), cp['matched'], cp.get('day', 0)
    return set(), 0, 0

# Load
log("Loading archive...")
with open(ARCHIVE) as f:
    html = f.read()
DATA, data_start, data_end = parse_data(html)

# Load checkpoint
processed, prev_matched, prev_day = load_checkpoint()
log(f"Checkpoint: {len(processed)} albums already processed, {prev_matched} previously matched")

# Group unlinked by album
albums = {}
for idx, t in enumerate(DATA):
    if t.get('sid', '').startswith('spotify:local:'):
        artist = t.get('a', '').split(';')[0].split(',')[0].strip()
        album = t.get('al', '')
        key = (artist, album)
        if key not in albums:
            albums[key] = []
        albums[key].append(idx)

# Filter out already-processed albums
remaining = {k: v for k, v in albums.items() if k not in processed}
log(f"Total unlinked: {sum(len(v) for v in albums.values())} in {len(albums)} albums")
log(f"Remaining this run: {sum(len(v) for v in remaining.values())} in {len(remaining)} albums")
log(f"Will process up to {MAX_ALBUMS} albums today\n")

matched = 0
calls = 0
today_processed = 0
album_list = list(remaining.items())

for ai, ((artist, album), indices) in enumerate(album_list):
    if today_processed >= MAX_ALBUMS:
        log(f"\nReached daily limit ({MAX_ALBUMS} albums). Resume tomorrow.")
        break
    
    try:
        # Search by album
        q = urllib.parse.quote(f"artist:{artist} album:{album}")
        time.sleep(1.0)
        result = api(f"https://api.spotify.com/v1/search?q={q}&type=album&limit=5")
        calls += 1
        
        sp_albums = result.get('albums', {}).get('items', [])
        best_al = None
        best_score = 0
        for sa in sp_albums:
            ns = sim(sa['name'], album)
            ars = max((sim(a['name'], artist) for a in sa['artists']), default=0)
            sc = ns * 0.6 + ars * 0.4
            if sc > best_score:
                best_score = sc
                best_al = sa
        
        if best_al and best_score >= 0.4:
            time.sleep(1.0)
            at = api(f"https://api.spotify.com/v1/albums/{best_al['id']}/tracks?limit=50")
            calls += 1
            sp_tracks = at.get('items', [])
            
            for idx in indices:
                tn = DATA[idx]['t']
                best_t = None
                best_ts = 0
                for st in sp_tracks:
                    ts = sim(st['name'], tn)
                    if ts > best_ts:
                        best_ts = ts
                        best_t = st
                if best_t and best_ts >= 0.5:
                    DATA[idx]['sid'] = best_t['id']
                    matched += 1
        else:
            # Fallback: individual track search
            for idx in indices:
                tn = DATA[idx]['t']
                try:
                    time.sleep(1.0)
                    q2 = urllib.parse.quote(f"{artist} {tn}")
                    r2 = api(f"https://api.spotify.com/v1/search?q={q2}&type=track&limit=5")
                    calls += 1
                    items = r2.get('tracks', {}).get('items', [])
                    if items:
                        best_t = None
                        best_s = 0
                        for st in items:
                            s = sim(st['name'], tn) * 0.6 + max((sim(a['name'], artist) for a in st['artists']), default=0) * 0.4
                            if s > best_s:
                                best_s = s
                                best_t = st
                        if best_t and best_s >= 0.45:
                            DATA[idx]['sid'] = best_t['id']
                            matched += 1
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        log(f"Rate limited on track search, stopping early.")
                        break
                except:
                    pass

        processed.add((artist, album))
        today_processed += 1

    except urllib.error.HTTPError as e:
        if e.code == 429:
            log(f"\nRate limited at album {today_processed+1}. Saving progress and stopping.")
            break
        elif e.code == 401:
            log(f"\nToken expired at album {today_processed+1}. Saving progress and stopping.")
            break
        else:
            processed.add((artist, album))
            today_processed += 1
    except Exception:
        processed.add((artist, album))
        today_processed += 1
    
    # Checkpoint every 50
    if today_processed % 50 == 0:
        save_checkpoint(processed, prev_matched + matched, prev_day + 1)
        html, data_start, data_end = save_archive(DATA, html, data_start, data_end)
        log(f"[{today_processed}/{min(MAX_ALBUMS, len(album_list))}] matched={matched} total_matched={prev_matched+matched} calls={calls} — saved checkpoint")

# Final save
save_checkpoint(processed, prev_matched + matched, prev_day + 1)
html, data_start, data_end = save_archive(DATA, html, data_start, data_end)

total_unlinked = sum(1 for t in DATA if t.get('sid', '').startswith('spotify:local:'))
log(f"\n{'='*50}")
log(f"Day complete!")
log(f"Matched today: {matched}")
log(f"Total matched all time: {prev_matched + matched}")
log(f"Still unlinked: {total_unlinked}")
log(f"Albums processed today: {today_processed}")
log(f"Albums remaining: {len(remaining) - today_processed}")
log(f"API calls today: {calls}")
log(f"Archive saved. Push to GitHub when ready.")
