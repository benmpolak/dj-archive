#!/usr/bin/env python3
"""Ingest Spotify Extended Streaming History into the archive.
Adds to each matched track: pc (play count, plays >=30s), fp (first-played YYYYMM),
lp (last-played YYYYMM). Kids' content excluded automatically — only plays whose
spotify_track_uri matches an archive sid are counted."""
import json, glob, os, shutil
from datetime import datetime
from collections import Counter

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
sids = {t['sid'] for t in DATA if t.get('sid') and len(str(t['sid']))==22}

pc = Counter(); fp = {}; lp = {}
total_hits = 0
for f in HIST:
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[-1]
        if sid not in sids: continue
        if (r.get('ms_played') or 0) < 30000: continue
        ym = r.get('ts','')[:7].replace('-','')
        if not ym.isdigit(): continue
        ym = int(ym)
        pc[sid]+=1; total_hits+=1
        if sid not in fp or ym < fp[sid]: fp[sid]=ym
        if sid not in lp or ym > lp[sid]: lp[sid]=ym

for t in DATA:
    s = t.get('sid')
    if s in pc:
        t['pc']=pc[s]; t['fp']=fp[s]; t['lp']=lp[s]

played = sum(1 for t in DATA if t.get('pc'))
bak = os.path.join(HERE, f"_backup-pre-plays-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
open(ARCHIVE,'w').write(html[:ds] + new_json + html[de:])
print(f"plays matched to archive: {total_hits:,}")
print(f"tracks with a play count: {played:,} of {len(DATA):,}")
print(f"saved. backup: {os.path.basename(bak)}")
