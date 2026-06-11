#!/usr/bin/env python3
"""Refresh play data + add multi-year windowed counts.
Re-ingests pc (all-time plays >=30s), fp/lp (first/last YYYYMM) so any newly
matched tracks pick up plays, then adds windowed counts measured back from today:
p1,p2,p3,p5,p7,p10 = plays in the last 1/2/3/5/7/10 years.
Only plays whose spotify_track_uri matches an archive sid are counted (excludes kids/family)."""
import json, glob, os, shutil, datetime
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
HIST = glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json')
WINDOWS = [1, 2, 3, 5, 7, 10]
REF = datetime.date(2026, 6, 9)  # "now" for windowing = end of latest export

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
win = {w: Counter() for w in WINDOWS}
cuts = {w: REF - datetime.timedelta(days=365*w) for w in WINDOWS}
total_hits = 0
for f in HIST:
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[-1]
        if sid not in sids: continue
        if (r.get('ms_played') or 0) < 30000: continue
        ts = r.get('ts','')[:10]
        try: d = datetime.date.fromisoformat(ts)
        except: continue
        ym = int(ts[:7].replace('-',''))
        pc[sid]+=1; total_hits+=1
        if sid not in fp or ym < fp[sid]: fp[sid]=ym
        if sid not in lp or ym > lp[sid]: lp[sid]=ym
        for w in WINDOWS:
            if d >= cuts[w]: win[w][sid]+=1

for t in DATA:
    s = t.get('sid')
    if s in pc:
        t['pc']=pc[s]; t['fp']=fp[s]; t['lp']=lp[s]
        for w in WINDOWS:
            k = 'p%d' % w
            if win[w][s]: t[k]=win[w][s]
            elif k in t: del t[k]

played = sum(1 for t in DATA if t.get('pc'))
bak = os.path.join(HERE, f"_backup-pre-multiwin-{datetime.datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html[:ds] + json.dumps(DATA, separators=(',',':'), ensure_ascii=False) + html[de:])
print(f"plays matched to archive: {total_hits:,}")
print(f"tracks with a play count: {played:,} of {len(DATA):,}")
for w in WINDOWS:
    print(f"  tracks played in last {w}y: {sum(1 for t in DATA if t.get('p%d'%w)):,}")
print(f"saved. backup: {os.path.basename(bak)}")
