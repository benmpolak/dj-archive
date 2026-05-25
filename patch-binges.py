#!/usr/bin/env python3
"""Compute 'Biggest Binges' (days you played one album into the ground) and inject
as `var BINGES=[...];` before MONTHLY. One row per album (its single biggest day).
Plays = 30s+, filtered to archive sids."""
import json, glob, os, shutil, datetime
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
HIST = glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json')

def parse_data(html):
    ds = html.index('const DATA=') + len('const DATA=')
    depth=0; ins=False; esc=False; i=ds
    while i < len(html):
        c=html[i]
        if esc: esc=False; i+=1; continue
        if c=='\\' and ins: esc=True; i+=1; continue
        if c=='"': ins=not ins; i+=1; continue
        if not ins:
            if c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: return json.loads(html[ds:i+1]), ds, i+1
        i+=1

html = open(ARCHIVE).read()
DATA, ds, de = parse_data(html)
meta = {t['sid']:t for t in DATA if t.get('sid') and len(str(t['sid']))==22}

# per (day, artist, album): play count + which track got most spins (for a play link)
dayAlb = defaultdict(int)
dayAlbTrk = defaultdict(Counter)
for f in HIST:
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[-1]
        if sid not in meta: continue
        if (r.get('ms_played') or 0) < 30000: continue
        d = r.get('ts','')[:10]
        if len(d) != 10: continue
        t = meta[sid]
        al = t.get('al')
        if not al: continue
        a = t.get('a','').split(';')[0]
        dayAlb[(d,a,al)] += 1
        dayAlbTrk[(d,a,al)][sid] += 1

MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
rows = []
for (d,a,al),n in dayAlb.items():
    sid = dayAlbTrk[(d,a,al)].most_common(1)[0][0]
    rows.append((n, d, a, al, sid))
rows.sort(reverse=True)

# keep the single biggest day per (artist, album)
seen = set(); BINGES = []
for n, d, a, al, sid in rows:
    key = (a.lower(), al.lower())
    if key in seen: continue
    seen.add(key)
    y, m, day = d.split('-')
    dl = f"{int(day)} {MONTHS[int(m)-1]} {y}"
    BINGES.append({'a':a,'al':al,'n':n,'dl':dl,'sid':sid})
    if len(BINGES) >= 15: break

inject = 'var BINGES=' + json.dumps(BINGES, separators=(',',':'), ensure_ascii=False) + ';'
anchor = 'var MONTHLY={'
assert anchor in html, 'MONTHLY anchor not found'
if 'var BINGES=' in html:
    import re
    html = re.sub(r'var BINGES=\[.*?\];', inject, html, count=1, flags=re.S)
else:
    html = html.replace(anchor, inject+'\n'+anchor, 1)

bak = os.path.join(HERE, f"_backup-pre-binges-{datetime.datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print('injected', len(BINGES), 'binges')
for b in BINGES:
    print(f"  {b['n']:>3}x  {b['dl']:<13} {b['a']} — {b['al']}")
print('backup:', os.path.basename(bak))
