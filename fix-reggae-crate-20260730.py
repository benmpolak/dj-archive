#!/usr/bin/env python3
"""
Create the Reggae & Dub crate (2026-07-30, Ben's call after Cornell Campbell
had nowhere to live). Genre-token driven, same family list as genre-map.py:

  - MAJORITY-reggae tracks (reggae-family tokens >= 1/2 of genre tokens):
    add Reggae & Dub, drop Afro & World + Uncategorized (they were only there
    for lack of a home). Other crates kept — Natiruts stays Brazilian,
    rocksteady-soul keeps Soul & R&B.
  - PRIMARY-reggae tracks (first genre token is reggae-family, or tokens >=
    1/3): add Reggae & Dub alongside existing crates.
  - Below that (a stray 'dub'/'reggae fusion' tail token — Massive Attack,
    Evelyn King): untouched.

By-ear prune: acts whose reggae-family tokens are influence/junk, not identity
(Massive Attack trip hop, Mala + Feed Me dubstep, Raze acid house, Manny
Corchado boogaloo, Dino maloya) never get the crate.

Re-runnable: idempotent.
"""
import json, os

EXCLUDE_ARTISTS = {'Massive Attack', 'Feed Me', 'Raze',
                   'Manny Corchado & His Orchestra'}
EXCLUDE_TRACKS = {('Mala', 'Noche Sueños'), ('Dino', 'Feels so good')}

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
CRATE = 'Reggae & Dub'

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

def toks(g):
    return [x.strip().lower() for x in (g or '').split(',') if x.strip()]

def is_reggae(t):
    return (t in ('reggae', 'dub', 'ska', 'dancehall', 'ragga', 'rocksteady',
                  'lovers rock', 'riddim', 'reggae fusion')
            or t.endswith(' reggae') or t.endswith(' ska')
            or t.endswith(' dancehall'))

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)
print(f"{len(DATA)} tracks loaded")

majority = primary = pruned = 0
for t in DATA:
    excluded = (t['a'].split(';')[0] in EXCLUDE_ARTISTS
                or (t['a'].split(';')[0], t['t']) in EXCLUDE_TRACKS)
    if excluded:
        if CRATE in t.get('c', []):
            t['c'] = [c for c in t['c'] if c != CRATE]
            pruned += 1
        continue
    tk = toks(t.get('g'))
    if not tk:
        continue
    share = sum(1 for x in tk if is_reggae(x)) / len(tk)
    if share == 0:
        continue
    c = set(t.get('c', []))
    if share >= 0.5:
        c -= {'Afro & World', 'Uncategorized', 'Uncategorised'}
        c.add(CRATE)
        majority += 1
    elif share >= 1/3 or is_reggae(tk[0]):
        c.add(CRATE)
        primary += 1
    else:
        continue
    if not c:
        c = {CRATE}
    new = sorted(c)
    if new != t.get('c'):
        t['c'] = new

n = sum(1 for t in DATA if CRATE in t.get('c', []))
print(f"majority treated: {majority}, primary add-only: {primary}, "
      f"pruned: {pruned}, total in crate: {n}")

new_json = json.dumps(DATA, separators=(',', ':'), ensure_ascii=False)
with open(ARCHIVE, 'w') as f:
    f.write(html[:ds] + new_json + html[de:])
print("Saved.")
