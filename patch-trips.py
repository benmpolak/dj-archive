#!/usr/bin/env python3
"""Trips / Rabbit Holes panel (Listening tab): multi-day artist/scene binges
detected from RAW streaming history (every press of play, skims included)."""
import json, glob, os, re, shutil, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

KIDS = {'duggee & the squirrels','bluey','mojo swoptops','super simple songs',
 'toddler fun learning','dream supplier','hey duggee','cocomelon','pinkfong',
 'rené aubry','the wiggles','kidz bop kids','kpop demon hunters cast','huddle',
 "gracie's corner",'ms rachel','sesame street','baby shark','lullaby baby trio',
 'disney junior','frozen','various artists','peppa pig','julia donaldson',
 'idina menzel','kristen bell','danny go!',"caitie's classroom",
 'kids imagine nation','josh gad','jonathan groff','the learning station',
 'blippi','raffi','justine clarke','songs for littles','encanto cast'}

events = defaultdict(lambda: defaultdict(int))
tracksper = defaultdict(lambda: defaultdict(set))
for f in glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json'):
    for r in json.load(open(f)):
        a = r.get('master_metadata_album_artist_name')
        t = r.get('master_metadata_track_name')
        ts = (r.get('ts') or '')[:10]
        if not a or not ts or a.lower() in KIDS: continue
        events[a][ts] += 1
        tracksper[a][ts].add(t)

def to_date(s): return datetime.date.fromisoformat(s)

clusters = []
for a, days in events.items():
    ds = sorted(days)
    run = [ds[0]]
    for d in ds[1:]:
        if (to_date(d) - to_date(run[-1])).days <= 2:
            run.append(d)
        else:
            clusters.append((a, run)); run = [d]
    clusters.append((a, run))
cl = []
for a, run in clusters:
    n = sum(events[a][d] for d in run)
    tr = set().union(*(tracksper[a][d] for d in run))
    if n >= 8 and len(tr) >= 3 and len(run) <= 14:
        cl.append({'a': a, 'start': run[0], 'end': run[-1], 'n': n})

cl.sort(key=lambda c: c['start'])
trips = []
for c in cl:
    placed = False
    for t in trips:
        if c['start'] <= t['end'] and c['end'] >= t['start']:
            ns, ne = min(t['start'], c['start']), max(t['end'], c['end'])
            if (to_date(ne) - to_date(ns)).days <= 10:   # don't sprawl
                t['start'], t['end'] = ns, ne
                t['arts'].append((c['a'], c['n'])); t['n'] += c['n']
                placed = True; break
    if not placed:
        trips.append({'start': c['start'], 'end': c['end'], 'arts': [(c['a'], c['n'])], 'n': c['n']})

trips.sort(key=lambda t: -t['n'])
items = []
for t in trips[:100]:
    arts = sorted(t['arts'], key=lambda x: -x[1])
    items.append({'s': t['start'], 'e': t['end'], 'n': t['n'],
                  'arts': [a for a, _ in arts[:4]], 'more': max(0, len(arts)-4)})
items.sort(key=lambda x: x['s'], reverse=True)
print(f'{len(trips)} trips; panel gets {len(items)}. Recent:')
for it in items[:10]:
    print(f"  {it['s']}..{it['e']}  {it['n']:4d} ev  {', '.join(it['arts'])}" + (f" +{it['more']}" if it['more'] else ''))

TRIPS = {'items': items}
html = open(ARCHIVE).read()
inject = 'var TRIPS=' + json.dumps(TRIPS, separators=(',',':'), ensure_ascii=False) + ';'
if 'var TRIPS=' in html:
    html = re.sub(r'var TRIPS=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

PANEL = """  /* Trips / Rabbit Holes (added) */
  if(window.TRIPS&&TRIPS.items&&TRIPS.items.length){
    h+='<div class="sd-section" data-tab="listening"><h3>Trips &amp; Rabbit Holes</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:10px">Multi-day binges on an artist or scene, detected from every press of play since 2012 &mdash; skims and all. Your June indie pilgrimage lives here forever.</div>';
    h+='<div id="pgTrips"></div>';
    h+='</div>';
  }
"""
if 'Trips / Rabbit Holes (added)' not in html:
    anchor = '  /* Listening Clock (added, snapshot from streaming history) */'
    html = html.replace(anchor, PANEL + anchor, 1)

INIT = """if(window.TRIPS&&TRIPS.items&&TRIPS.items.length){var _trMax=Math.max.apply(null,TRIPS.items.map(function(x){return x.n}));var _trMo=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var _trD=function(s){return parseInt(s.slice(8),10)+' '+_trMo[parseInt(s.slice(5,7),10)]};pgInit('pgTrips',TRIPS.items,function(x,i){var dates=(x.s===x.e?_trD(x.s):_trD(x.s)+'&ndash;'+_trD(x.e))+' '+x.s.slice(0,4);var lbl=x.arts.join(', ')+(x.more?' +'+x.more:'')+' <span style="color:var(--dim);font-size:0.85em">&mdash; '+dates+'</span>';return sdNameRow(lbl,x.n+' plays',Math.round(x.n/_trMax*100),_hamColors[i%8],null);});}
  """
if "pgInit('pgTrips'" not in html:
    anchor2 = "if(window.VINYLVAL&&VINYLVAL.items&&VINYLVAL.items.length)pgInit('pgVinylVal'"
    html = html.replace(anchor2, INIT + anchor2, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-trips-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected TRIPS panel')
