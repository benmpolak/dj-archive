#!/usr/bin/env python3
"""Add windowed play counts to each track: py (last 365d), pm (last 30d), pw (last 7d),
relative to the most recent play in the history. pc (all-time) already present."""
import json, glob, os, shutil, datetime
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

# gather (sid, datetime) for plays >=30s
events = []
maxdt = None
for f in HIST:
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[-1]
        if sid not in sids: continue
        if (r.get('ms_played') or 0) < 30000: continue
        try: dt = datetime.datetime.strptime(r.get('ts','')[:10], '%Y-%m-%d')
        except: continue
        events.append((sid, dt))
        if maxdt is None or dt > maxdt: maxdt = dt

cutY = maxdt - datetime.timedelta(days=365)
cutM = maxdt - datetime.timedelta(days=30)
cutW = maxdt - datetime.timedelta(days=7)
py=Counter(); pm=Counter(); pw=Counter()
for sid, dt in events:
    if dt >= cutY: py[sid]+=1
    if dt >= cutM: pm[sid]+=1
    if dt >= cutW: pw[sid]+=1

for t in DATA:
    s = t.get('sid')
    if s in py: t['py']=py[s]
    if s in pm: t['pm']=pm[s]
    if s in pw: t['pw']=pw[s]

bak = os.path.join(HERE, f"_backup-pre-pwin-{datetime.datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html[:ds] + json.dumps(DATA, separators=(',',':'), ensure_ascii=False) + html[de:])
print(f"latest play in history: {maxdt:%Y-%m-%d}")
print(f"tracks with year plays: {sum(1 for t in DATA if t.get('py'))}, month: {sum(1 for t in DATA if t.get('pm'))}, week: {sum(1 for t in DATA if t.get('pw'))}")
print(f"saved. backup: {os.path.basename(bak)}")
