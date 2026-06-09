#!/usr/bin/env python3
"""
Pull Ben's live Spotify playlists and write Exportify-compatible CSVs,
so playlist-import.py works unchanged. Replaces the Exportify ritual.

Spotify reality check (June 2026, dev-mode app):
  WORKS:   /v1/search, /v1/playlists/{id} (metadata only)
  BLOCKED: playlist listing/search, /tracks sub-endpoint, /v1/tracks,
           /v1/artists, embedded track items, web-player anon token
So the pipeline is:
  1. Playlist IDs from playlist-ids.json (mined from AddedToPlaylist.json
     in the Account Data export's Technical Log — refresh from new export).
  2. Playlist names via /v1/playlists/{id}?fields=name,owner.id.
  3. Tracklists from open.spotify.com/embed/playlist/{id} (__NEXT_DATA__).
     CAPPED AT 100 tracks — fine for monthlies, big crate playlists get a
     truncation warning; their full contents come from the Account Data
     export's Playlist1-4.json when present.
  4. New tracks (not in archive) enriched via search (album, release date).
     Genres inherited from the artist's existing archive tracks.
  5. Added At from Playlist1-4.json / AddedToPlaylist.json, else today.

Usage:
    SPOTIFY_CLIENT_SECRET=xxx python3 pull-playlists.py
Then:
    python3 playlist-import.py "<folder it prints>"
"""
import csv, json, os, re, sys, time, zipfile, urllib.request, urllib.parse
from collections import Counter
from datetime import date

CID = '16c7847eda6740e3a02fd2d334bc803a'
USER_ID = '1130795251'
HERE = os.path.dirname(os.path.abspath(__file__))
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.4 Safari/605.1.15')

# Account Data exports (refresh paths when new ones land)
ZIP_TECHLOG = '/Users/benpolak/Downloads/my_spotify_data (1).zip'
ZIP_ACCOUNT = '/Users/benpolak/Downloads/my_spotify_data (2).zip'

NAMED = {
    'Africa_Sounds', 'All_That_Jazz', 'Brasil', 'Brasil_Novo',
    'Brazilian_Boogie', 'Hispanic', 'Older_Dance', 'R&B_Soul',
    'Soul_&_Disco_revival', 'Summer_Sounds', 'Sunshine_dance',
}
MONTHLY = re.compile(r'^(January|February|March|April|May|June|July|August|'
                     r'September|October|November|December)_20\d\d$')

HEADER = ['Track URI','Track Name','Album Name','Artist Name(s)','Release Date',
          'Duration (ms)','Popularity','Explicit','Added By','Added At','Genres',
          'Record Label','Danceability','Energy','Key','Loudness','Mode',
          'Speechiness','Acousticness','Instrumentalness','Liveness','Valence',
          'Tempo','Time Signature']

def norm_name(name):
    """'Soul & Disco revival  ' -> 'Soul_&_Disco_revival' (CSV-style key)."""
    return name.strip().replace(' ', '_').rstrip('_')

def get_token(secret):
    body = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': CID, 'client_secret': secret,
    }).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req) as r:
        return json.load(r)['access_token']

def api_get(url, token):
    while True:
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', '5')) + 1
                print(f'    rate limited, waiting {wait}s...')
                time.sleep(wait); continue
            raise

def embed_tracklist(pid):
    req = urllib.request.Request(f'https://open.spotify.com/embed/playlist/{pid}',
                                 headers={'User-Agent': UA})
    with urllib.request.urlopen(req) as r:
        html = r.read().decode()
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                  html, re.S)
    e = json.loads(m.group(1))['props']['pageProps']['state']['data']['entity']
    return e.get('trackList') or []

def load_archive_data():
    html = open(os.path.join(HERE, 'index.html')).read()
    s = html.index('const DATA=') + len('const DATA=')
    depth=0; instr=False; esc=False; i=s
    while True:
        c = html[i]
        if esc: esc=False
        elif c=='\\' and instr: esc=True
        elif c=='"': instr = not instr
        elif not instr:
            if c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: break
        i+=1
    return json.loads(html[s:i+1])

def load_added_dates():
    """sid -> earliest known add timestamp (ISO), from both exports."""
    added = {}
    try:
        z = zipfile.ZipFile(ZIP_ACCOUNT)
        names = [n for n in z.namelist() if re.search(r'Playlist\d+\.json$', n)]
        for n in names:
            for p in json.loads(z.read(n)).get('playlists', []):
                for it in p.get('items') or []:
                    uri = ((it.get('track') or {}).get('trackUri')) or ''
                    d = it.get('addedDate') or ''
                    if uri.startswith('spotify:track:') and d:
                        sid = uri.split(':')[2]
                        added[sid] = min(added.get(sid, '9999'), d)
    except Exception as ex:
        print(f'  (account zip unreadable: {ex})')
    try:
        z = zipfile.ZipFile(ZIP_TECHLOG)
        n = [x for x in z.namelist() if x.endswith('AddedToPlaylist.json')][0]
        for r in json.loads(z.read(n)):
            uri = r.get('message_item_uri') or ''
            ts = (r.get('timestamp_utc') or '')[:10]
            if uri.startswith('spotify:track:') and ts:
                sid = uri.split(':')[2]
                added[sid] = min(added.get(sid, '9999'), ts)
    except Exception as ex:
        print(f'  (techlog zip unreadable: {ex})')
    return added

def search_track(token, sid, title, artist):
    """Find exact track by id via search; returns track object or None."""
    q = urllib.parse.quote(f'track:"{title}" artist:"{artist}"')
    for url in [f'https://api.spotify.com/v1/search?q={q}&type=track&limit=10',
                'https://api.spotify.com/v1/search?q=' +
                urllib.parse.quote(f'{title} {artist}') + '&type=track&limit=10']:
        try:
            d = api_get(url, token)
        except urllib.error.HTTPError:
            continue
        for t in (d.get('tracks') or {}).get('items') or []:
            if t and t.get('id') == sid:
                return t
    return None

def main():
    secret = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SPOTIFY_CLIENT_SECRET')
    if not secret:
        print('Need the client secret (arg or SPOTIFY_CLIENT_SECRET).'); sys.exit(1)
    token = get_token(secret)

    with open(os.path.join(HERE, 'playlist-ids.json')) as f:
        known_ids = list(json.load(f).keys())
    print(f'Resolving {len(known_ids)} known playlist IDs...')
    targets = []
    for pid in known_ids:
        try:
            p = api_get(f'https://api.spotify.com/v1/playlists/{pid}?fields=name,owner.id', token)
        except urllib.error.HTTPError:
            continue
        if (p.get('owner') or {}).get('id') != USER_ID:
            continue
        key = norm_name(p['name'])
        if key in NAMED or MONTHLY.match(key):
            targets.append((key, pid))
    print(f'{len(targets)} import targets: ' + ', '.join(k for k, _ in targets))

    print('Loading archive + export add-dates...')
    DATA = load_archive_data()
    archive_sids = {t.get('sid','') for t in DATA}
    # artist -> most common genre string among their archive tracks
    artist_genres = {}
    by_artist = {}
    for t in DATA:
        a = (t.get('a') or '').split(';')[0].strip().lower()
        g = t.get('g') or ''
        if a and g:
            by_artist.setdefault(a, Counter())[g] += 1
    artist_genres = {a: c.most_common(1)[0][0] for a, c in by_artist.items()}
    added_dates = load_added_dates()

    outdir = os.path.join(HERE, f'Playlists auto {date.today().isoformat()}')
    os.makedirs(outdir, exist_ok=True)

    enrich_cache = {}
    total_new = 0
    for key, pid in targets:
        tl = embed_tracklist(pid)
        trunc = ' [TRUNCATED at 100 — full contents need Account Data export]' if len(tl) == 100 else ''
        rows = []
        new_in_pl = 0
        for it in tl:
            uri = it.get('uri') or ''
            if not uri.startswith('spotify:track:'): continue
            sid = uri.split(':')[2]
            title = it.get('title') or ''
            artists = (it.get('subtitle') or '').replace('\xa0', ' ')
            first_artist = artists.split(',')[0].strip()
            row = {
                'Track URI': uri, 'Track Name': title, 'Artist Name(s)': artists,
                'Duration (ms)': it.get('duration',''),
                'Explicit': str(bool(it.get('isExplicit'))).lower(),
                'Added By': USER_ID,
                'Added At': (added_dates.get(sid,'') + 'T00:00:00Z') if added_dates.get(sid) else '',
                'Album Name': '', 'Release Date': '', 'Popularity': '', 'Genres': '',
            }
            if sid not in archive_sids:
                new_in_pl += 1
                if sid not in enrich_cache:
                    enrich_cache[sid] = search_track(token, sid, title, first_artist)
                    time.sleep(0.3)
                t = enrich_cache[sid]
                if t:
                    row['Album Name'] = (t.get('album') or {}).get('name','')
                    row['Release Date'] = (t.get('album') or {}).get('release_date','')
                row['Genres'] = artist_genres.get(first_artist.lower(), '')
                if not row['Added At']:
                    row['Added At'] = date.today().isoformat() + 'T00:00:00Z'
            rows.append(row)
        total_new += new_in_pl
        path = os.path.join(outdir, f'{key}.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=HEADER, extrasaction='ignore')
            w.writeheader()
            for r in rows: w.writerow(r)
        print(f'  {key}: {len(rows)} tracks, {new_in_pl} new{trunc}')

    print(f'\n{total_new} tracks not yet in archive.')
    print(f'Now run:\n  python3 playlist-import.py "{os.path.basename(outdir)}"')

if __name__ == '__main__':
    main()
