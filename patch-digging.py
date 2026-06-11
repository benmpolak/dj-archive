#!/usr/bin/env python3
"""
Digging Activity: archive the movement of Ben adding tracks to playlists,
and surface it as a Stats panel (Timeline tab).

Builds add-ledger.json — {playlist_name: {sid: 'YYYY-MM'}} merged from:
  - Account Data export Playlist1-4.json (full per-playlist addedDate history)
  - every playlist CSV folder in the repo (Exportify 'Added At' columns)
Earliest date wins per (playlist, sid). Site-generated playlists excluded.

Then injects `var DIGGING={months:[{m,n,top:[[name,n],..]}]}` and a
"Digging Activity" panel into index.html (re-runnable).
"""
import csv, glob, json, os, re, shutil, datetime, zipfile
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
ZIP_ACCOUNT = '/Users/benpolak/Downloads/my_spotify_data (2).zip'
CSV_FOLDERS = ['Playlists 11 april 2026', 'Playlists may 2026',
               'Playlists auto 2026-06-09', 'Playlists exportify 2026-06-11']

def skip_playlist(name):
    n = (name or '').strip()
    return (not n) or ('DJ Archive' in n) or n.startswith('Bobby & Luna')

ledger = defaultdict(dict)   # name -> sid -> 'YYYY-MM'

def record(pl, sid, ym):
    if not (pl and sid and ym): return
    cur = ledger[pl].get(sid)
    if cur is None or ym < cur:
        ledger[pl][sid] = ym

# --- Account Data export (full history) ---
try:
    z = zipfile.ZipFile(ZIP_ACCOUNT)
    names = [n for n in z.namelist() if re.search(r'Playlist\d+\.json$', n)]
    for n in names:
        for p in json.loads(z.read(n)).get('playlists', []):
            pn = (p.get('name') or '').strip()
            if skip_playlist(pn): continue
            for it in p.get('items') or []:
                uri = ((it.get('track') or {}).get('trackUri')) or ''
                d = (it.get('addedDate') or '')[:7]
                if uri.startswith('spotify:track:') and len(d) == 7:
                    record(pn, uri.split(':')[2], d)
    print(f'account export: {sum(len(v) for v in ledger.values())} add-events')
except Exception as e:
    print(f'(account zip skipped: {e})')

# --- CSV folders ---
def csv_playlist_name(path):
    base = re.sub(r'\.csv$', '', os.path.basename(path), flags=re.I)
    base = re.sub(r'\s*\(\d+\)\s*$', '', base).strip()
    return base.replace('_', ' ').rstrip('_ ').strip()

for folder in CSV_FOLDERS:
    for f in glob.glob(os.path.join(HERE, folder, '*.csv')):
        pn = csv_playlist_name(f)
        if skip_playlist(pn): continue
        for row in csv.DictReader(open(f, encoding='utf-8-sig')):
            uri = row.get('Track URI','')
            d = (row.get('Added At') or '')[:7]
            if uri.startswith('spotify:track:') and len(d) == 7:
                record(pn, uri.split(':')[2], d)

total = sum(len(v) for v in ledger.values())
print(f'ledger: {total} (playlist, track) adds across {len(ledger)} playlists')
json.dump({k: v for k, v in sorted(ledger.items())},
          open(os.path.join(HERE, 'add-ledger.json'), 'w'), indent=0, ensure_ascii=False)

# --- aggregate for the panel ---
bym = defaultdict(Counter)   # 'YYYY-MM' -> playlist -> n
for pl, items in ledger.items():
    for sid, ym in items.items():
        bym[ym][pl] += 1
months = []
for ym in sorted(bym, reverse=True)[:120]:
    c = bym[ym]
    months.append({'m': ym, 'n': sum(c.values()),
                   'top': [[p, n] for p, n in c.most_common(4)]})
DIGGING = {'months': months, 'total': total, 'np': len(ledger)}

# --- inject into index.html ---
html = open(ARCHIVE).read()
inject = 'var DIGGING=' + json.dumps(DIGGING, separators=(',',':'), ensure_ascii=False) + ';'
if 'var DIGGING=' in html:
    html = re.sub(r'var DIGGING=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

PANEL = """  /* Digging Activity (added) */
  if(window.DIGGING&&DIGGING.months&&DIGGING.months.length){
    h+='<div class="sd-section" data-tab="timeline"><h3>Digging Activity</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:10px">Where you\\'ve been busy adding &mdash; tracks added to your playlists each month, and which lists took them. '+DIGGING.total.toLocaleString()+' adds across '+DIGGING.np+' playlists.</div>';
    h+='<div id="pgDigging"></div>';
    h+='</div>';
  }
"""
if 'Digging Activity (added)' not in html:
    anchor = '  /* Listening Clock (added, snapshot from streaming history) */'
    assert anchor in html
    html = html.replace(anchor, PANEL + anchor, 1)

INIT = """if(window.DIGGING&&DIGGING.months&&DIGGING.months.length){var _digMax=Math.max.apply(null,DIGGING.months.map(function(x){return x.n}));var _digMo=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];pgInit('pgDigging',DIGGING.months,function(x,i){var lbl=_digMo[parseInt(x.m.slice(5),10)]+' '+x.m.slice(0,4)+' <span style="color:var(--dim);font-size:0.85em">&mdash; '+x.top.map(function(p){return p[0]+' '+p[1]}).join(', ')+'</span>';return sdNameRow(lbl,x.n+' adds',Math.round(x.n/_digMax*100),_hamColors[i%8],null);});}
  """
if "pgInit('pgDigging'" not in html:
    anchor2 = "if(window.VINYLVAL&&VINYLVAL.items&&VINYLVAL.items.length)pgInit('pgVinylVal'"
    assert anchor2 in html
    html = html.replace(anchor2, INIT + anchor2, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-digging-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected DIGGING + panel. Recent months:')
for m in months[:6]:
    print(f"  {m['m']}: {m['n']} adds — " + ', '.join(f'{p} {n}' for p, n in m['top']))
