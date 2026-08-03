#!/usr/bin/env python3
"""
One-off: bring Patchwork Inc. "More Patchwork" (album, released 2026-07-30,
Spotify 0FRKLGFe8FAlw8WS06ekWA) into the archive — Ben wants it pinned on the
guest landing's New in shelf.

Singles->album regroup, same pattern as the Curio Curio one (fc4168b):
- existing "Anyone" (w/ Lynda Dawn) retagged al='More Patchwork' + album sid
- "Last Forever" b/w single is NOT on the album — left untouched
- remaining 6 album tracks appended (sids scraped from the CORS-open embed
  page — no client secret needed for this)
Crates/vibes by ear: retro soul collective, Soul & R&B home crate.
Re-runnable: idempotent (keyed on (first artist, title)).
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
ALBUM = 'More Patchwork'

def parse_data(html):
    s = html.index('const DATA=') + len('const DATA=')
    d = 0; ins = False; esc = False; i = s
    while i < len(html):
        c = html[i]
        if esc: esc = False; i += 1; continue
        if c == '\\' and ins: esc = True; i += 1; continue
        if c == '"': ins = not ins; i += 1; continue
        if not ins:
            if c == '[': d += 1
            elif c == ']':
                d -= 1
                if d == 0: return json.loads(html[s:i+1]), s, i+1
        i += 1

# title -> (co-artists, sid, crates, vibe)
TRACKS = {
    'Lalalalala':       ('Les Sons Du Cosmos;Sparklmami', '6XjUTt7YVt57kekzkyYP1F', ['Soul & R&B'], 'Feel Good'),
    'Time':             ('Manasseh',        '4LtxLWepwQCkXyeLFhthVF', ['Soul & R&B'], 'Deep & Mellow'),
    'Take You Home':    ('Taylor Williams', '1JcOsW1sOAhbrOVzQuLaCq', ['Soul & R&B'], 'Soulful'),
    "Can't Let Go":     ('Wyatt Waddell',   '194TABbV60FuNqNbAHLKAL', ['Soul & R&B'], 'Soulful'),
    'Shooting Star':    ('Michi',           '3lO1POZF8rCY48CmJddkRe', ['Soul & R&B'], 'Feel Good'),
    'Lady Of The Lake': ('Okonski',         '1DoiONbiYzBOyU5L0BQmai', ['Soul & R&B'], 'Deep & Mellow'),
    'Anyone':           ('Lynda Dawn',      '4V0cWomOgz3hM9ziMopf6I', None, None),  # existing row, retag only
}

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)

have = {}
for t in DATA:
    first = t['a'].split(';')[0].split(',')[0].strip().lower()
    if first == 'patchwork inc.':
        have[t['t'].strip().lower()] = t

changed = 0
for title, (co, sid, crates, vb) in TRACKS.items():
    row = have.get(title.strip().lower())
    if row:
        want_a = 'Patchwork Inc.;' + co
        if row.get('al') != ALBUM or row.get('sid') != sid or row.get('a') != want_a:
            # ';' join, not ',' — groupRecords keys on primary(a) which only
            # splits ';', so a comma row would sit outside the album group
            row['a'] = want_a
            row['al'] = ALBUM; row['sid'] = sid; row['r'] = 2026
            changed += 1
            print('retagged:', row['a'], '-', title)
    else:
        DATA.append({
            'a': 'Patchwork Inc.;' + co, 't': title, 'al': ALBUM, 'r': 2026,
            'd': 0, 'e': 0, 'v': 0, 'tp': 0, 'ins': 0,
            'c': crates, 'vb': vb, 'n': 0, 'p': 0, 'g': 'retro soul',
            'sid': sid, 'vy': 0, 'era': 'Latest', 'tags': [], 'did': '',
            'da': 202608,
        })
        changed += 1
        print('added:', title, 'w/', co)

if changed:
    new_json = json.dumps(DATA, separators=(',', ':'), ensure_ascii=False)
    with open(ARCHIVE, 'w') as f:
        f.write(html[:ds] + new_json + html[de:])
    print(f'{changed} changes -> archive now {len(DATA)} tracks')
else:
    print('nothing to do')
