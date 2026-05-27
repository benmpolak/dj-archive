#!/usr/bin/env python3
"""Inject `var PLAYLISTED=[{a,t,n,sid}]` (top 100 tracks by number of distinct
playlists they appear in, across all 481 playlists) for the 'Your Bankers' panel."""
import zipfile, json, os, shutil, datetime, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
ZIP = '/Users/benpolak/Downloads/my_spotify_data (2).zip'
ZD = 'Spotify Account Data'

z = zipfile.ZipFile(ZIP)
plists = defaultdict(set); disp = {}; npl = 0
for n in ['Playlist1.json','Playlist2.json','Playlist3.json','Playlist4.json']:
    for p in json.loads(z.read(ZD+'/'+n))['playlists']:
        pn = p.get('name',''); npl += 1
        for it in p.get('items', []):
            tr = it.get('track') or {}
            uri = tr.get('trackUri') or ''
            if not uri.startswith('spotify:track:'): continue
            sid = uri.split(':')[-1]
            plists[sid].add(pn)
            if sid not in disp: disp[sid] = (tr.get('artistName',''), tr.get('trackName',''))

ranked = sorted(plists.items(), key=lambda kv: len(kv[1]), reverse=True)[:100]
items = [{'a':disp[sid][0], 't':disp[sid][1], 'n':len(pls), 'sid':sid} for sid, pls in ranked]
PLAYLISTED = {'total': npl, 'items': items}

html = open(ARCHIVE).read()
inject = 'var PLAYLISTED=' + json.dumps(PLAYLISTED, separators=(',',':'), ensure_ascii=False) + ';'
if 'var PLAYLISTED=' in html:
    html = re.sub(r'var PLAYLISTED=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var MONTHLY={', inject+'\n'+'var MONTHLY={', 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-playlisted-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE,'w').write(html)
print(f"injected PLAYLISTED: top {len(items)} across {npl} playlists")
for it in items[:10]:
    print(f"  {it['n']:>2} lists  {it['a']} — {it['t']}")
