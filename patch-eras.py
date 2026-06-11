#!/usr/bin/env python3
"""Eras panel (Timeline tab): yearly genre-bucket shares of what Ben ADDED
and what he PLAYED, using the approved genre->bucket mapping (genre-map.py).
Fluid genres (e.g. jazz funk = 'Jazz|Funk') count fractionally in each."""
import json, glob, os, re, shutil, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

g = {'__name__': 'genre_map'}
exec(open(os.path.join(HERE, 'genre-map.py')).read(), g)
map_genre = g['map_genre']

html = open(ARCHIVE).read()
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
DATA = json.loads(html[s:i+1])

CRATE_BUCKETS = {'Jazz','Funk','Soul & R&B','Disco & Boogie','House','Electronic',
                 'Downtempo','Hip Hop','Brazilian','Afro & World','Indie & Rock'}

def track_buckets(t):
    """bucket -> weight, normalised to 1 per track."""
    w = defaultdict(float)
    for raw in (t.get('g') or '').split(','):
        b = map_genre(raw)
        if not b: continue
        parts = b.split('|')
        for p in parts: w[p] += 1.0/len(parts)
    if not w:
        crates = [c for c in (t.get('c') or []) if c in CRATE_BUCKETS]
        for c in crates: w[c] += 1.0
    tot = sum(w.values())
    return {k: v/tot for k, v in w.items()} if tot else {}

tb = {t.get('sid'): track_buckets(t) for t in DATA}
covered = sum(1 for v in tb.values() if v)
print(f'{covered}/{len(DATA)} tracks bucketed')

# adds by year
adds = defaultdict(lambda: defaultdict(float))
for t in DATA:
    da = t.get('da') or 0
    y = da // 100
    if 2012 <= y <= 2026:
        for b, w in tb.get(t.get('sid'), {}).items():
            adds[y][b] += w

# plays by year (>=30s, archive-matched)
plays = defaultdict(lambda: defaultdict(float))
sids = set(tb)
for f in glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json'):
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[2]
        if sid not in sids or (r.get('ms_played') or 0) < 30000: continue
        y = int(r.get('ts','0000')[:4] or 0)
        if 2012 <= y <= 2026:
            for b, w in tb[sid].items():
                plays[y][b] += w

def yearly(d):
    out = []
    for y in sorted(d, reverse=True):
        tot = sum(d[y].values())
        if tot < 20: continue
        top = sorted(d[y].items(), key=lambda kv: -kv[1])[:4]
        out.append({'y': y, 'n': round(tot),
                    'top': [[b, round(100*v/tot)] for b, v in top]})
    return out

ERAS = {'adds': yearly(adds), 'plays': yearly(plays)}
for label, rows in (('ADDS', ERAS['adds'][:5]), ('PLAYS', ERAS['plays'][:5])):
    print(label)
    for r in rows:
        print(f"  {r['y']}: {r['n']} — " + ', '.join(f'{b} {p}%' for b, p in r['top']))

inject = 'var ERAS=' + json.dumps(ERAS, separators=(',',':'), ensure_ascii=False) + ';'
if 'var ERAS=' in html:
    html = re.sub(r'var ERAS=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

PANEL = """  /* Eras (added) */
  if(window.ERAS&&ERAS.adds&&ERAS.adds.length){
    h+='<div class="sd-section" data-tab="timeline"><h3>Your Eras</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:10px">The stages of your taste, year by year &mdash; every genre collapsed into the 13 crate-level buckets. Bar length is volume; the chapters name themselves.</div>';
    h+='<h4 style="margin:8px 0 6px;font-size:0.8em;color:var(--dim)">What you added</h4><div id="pgErasA"></div>';
    h+='<h4 style="margin:14px 0 6px;font-size:0.8em;color:var(--dim)">What you played</h4><div id="pgErasP"></div>';
    h+='</div>';
  }
"""
if 'Eras (added)' not in html:
    anchor = '  /* Listening Clock (added, snapshot from streaming history) */'
    html = html.replace(anchor, PANEL + anchor, 1)

INIT = """if(window.ERAS&&ERAS.adds&&ERAS.adds.length){var _erR=function(items){var mx=Math.max.apply(null,items.map(function(x){return x.n}));return function(x,i){var lbl=x.y+' <span style="color:var(--dim);font-size:0.85em">&mdash; '+x.top.map(function(p){return p[0]+' '+p[1]+'%'}).join(', ')+'</span>';return sdNameRow(lbl,x.n.toLocaleString(),Math.round(x.n/mx*100),_hamColors[i%8],null);}};pgInit('pgErasA',ERAS.adds,_erR(ERAS.adds));pgInit('pgErasP',ERAS.plays,_erR(ERAS.plays));}
  """
if "pgInit('pgErasA'" not in html:
    anchor2 = "if(window.VINYLVAL&&VINYLVAL.items&&VINYLVAL.items.length)pgInit('pgVinylVal'"
    html = html.replace(anchor2, INIT + anchor2, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-eras-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected ERAS panel')
