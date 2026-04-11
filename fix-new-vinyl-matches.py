#!/usr/bin/env python3
"""
One-shot fix for edge-case matches on the 6 new April 2026 Discogs imports:
- Vila (Fabiano do Nascimento) — artist mismatch, match directly by Spotify album ID
- Roland Haynes Jr. — Mind Games — artist mismatch, match directly by Spotify album ID
- Promises (Floating Points) — replace 2 vinyl-side suite entries with 9 individual Movement tracks

Re-runnable: idempotent aside from the Promises replacement (which dedupes by did).
Needs a Spotify token as first arg.

Usage: python3 fix-new-vinyl-matches.py <spotify_token>
"""
import json, re, sys, unicodedata, urllib.request

if len(sys.argv) < 2:
    print("Usage: python3 fix-new-vinyl-matches.py <token>")
    sys.exit(1)

TOKEN = sys.argv[1]
ARCHIVE = 'index.html'

def api(u):
    req = urllib.request.Request(u, headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def norm(s):
    s = unicodedata.normalize('NFKD', (s or '').lower().strip())
    return re.sub(r'[^\w\s]', '', s)

def parse_data(html):
    start = html.index('const DATA=') + len('const DATA=')
    d = 0; s = False; e = False; i = start
    while i < len(html):
        c = html[i]
        if e: e = False; i += 1; continue
        if c == '\\' and s: e = True; i += 1; continue
        if c == '"': s = not s; i += 1; continue
        if not s:
            if c == '[': d += 1
            elif c == ']':
                d -= 1
                if d == 0: return json.loads(html[start:i+1]), start, i+1
        i += 1

with open(ARCHIVE) as f:
    html = f.read()
DATA, data_start, data_end = parse_data(html)

fixed = 0

# ---- 1. Vila: match placeholder tracks to Spotify album ----
vila = api('https://api.spotify.com/v1/albums/6irs8cDzSNLsy8UL0ZeAes/tracks?limit=50')['items']
vila_map = {norm(t['name']): t['id'] for t in vila if 'no strings' not in t['name'].lower()}
for t in DATA:
    if str(t.get('did','')) == '36638488' and t.get('sid','').startswith('spotify:local:'):
        key = norm(t['t'])
        if key in vila_map:
            t['sid'] = vila_map[key]
            fixed += 1
            print(f"Vila: {t['t']} -> {vila_map[key]}")

# ---- 2. Roland Haynes Mind Games: match placeholder tracks ----
rh = api('https://api.spotify.com/v1/albums/4uskFUCMvzZ5HAaVbPjuNx/tracks?limit=50')['items']
rh_map = {norm(t['name']): t['id'] for t in rh}
for t in DATA:
    if str(t.get('did','')) == '36310123' and t.get('sid','').startswith('spotify:local:'):
        key = norm(t['t'])
        if key in rh_map:
            t['sid'] = rh_map[key]
            fixed += 1
            print(f"Roland Haynes: {t['t']} -> {rh_map[key]}")
        else:
            for k, sid in rh_map.items():
                if key and (key in k or k in key):
                    t['sid'] = sid
                    fixed += 1
                    print(f"Roland Haynes (substr): {t['t']} -> {k}")
                    break

# ---- 3. Promises: replace all did=17985154 entries with 9 individual movements ----
existing_promises = [i for i, t in enumerate(DATA) if str(t.get('did','')) == '17985154']
if existing_promises:
    # Check if they already look like individual movements
    titles = [DATA[i]['t'] for i in existing_promises]
    needs_replace = not all(re.match(r'^Movement \d$', t) for t in titles)
    if needs_replace:
        template = dict(DATA[existing_promises[0]])
        for i in sorted(existing_promises, reverse=True):
            del DATA[i]
        promises = api('https://api.spotify.com/v1/albums/4pDYkOvRt8GA6PxpVaHnLC/tracks?limit=50')['items']
        for st in promises:
            new_t = dict(template)
            new_t['t'] = st['name']
            new_t['sid'] = st['id']
            DATA.append(new_t)
            fixed += 1
            print(f"Promises: added {st['name']} -> {st['id']}")
    else:
        print(f"Promises: already in individual-movement form, skipping")

# ---- Save ----
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
new_html = html[:data_start] + new_json + html[data_end:]
with open(ARCHIVE, 'w') as f:
    f.write(new_html)
print(f"\nFixed: {fixed} tracks — DATA size: {len(DATA)}")
