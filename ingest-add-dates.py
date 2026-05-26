#!/usr/bin/env python3
"""Replace the archive's lumpy `da` (date added) with the true earliest playlist
add-date from the Spotify Account Data export. For each track matched by URI, da =
the first date it ever appeared in any playlist (YYYYMM). Unmatched tracks still
carrying a bulk-import placeholder (pre-2012, or the Feb-2019 lump) get their da
removed — we have no honest date for them — rather than asserting a fake one."""
import json, os, shutil, zipfile, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
ZIP = '/Users/benpolak/Downloads/my_spotify_data (2).zip'
ZD = 'Spotify Account Data'
PLACEHOLDER = lambda da: da is not None and (da < 201206 or da == 201902)  # bulk-import junk

# earliest playlist add-date per track uri
z = zipfile.ZipFile(ZIP)
earliest = {}
for n in ['Playlist1.json','Playlist2.json','Playlist3.json','Playlist4.json']:
    for p in json.loads(z.read(ZD+'/'+n))['playlists']:
        for it in p.get('items', []):
            tr = it.get('track') or {}
            uri = tr.get('trackUri') or ''
            ad = it.get('addedDate') or ''
            if not uri.startswith('spotify:track:') or len(ad) < 7 or ad[:4] == '1970':
                continue
            sid = uri.split(':')[-1]
            ym = int(ad[:7].replace('-', ''))
            if sid not in earliest or ym < earliest[sid]:
                earliest[sid] = ym

html = open(ARCHIVE).read()
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
            if depth==0: break
    i+=1
de = i+1
DATA = json.loads(html[ds:de])

real=0; nulled=0; kept=0
for t in DATA:
    sid = t.get('sid')
    if sid in earliest:
        t['da'] = earliest[sid]; real += 1
    elif PLACEHOLDER(t.get('da')):
        t.pop('da', None); nulled += 1
    else:
        kept += 1

bak = os.path.join(HERE, f"_backup-pre-adddates-{datetime.datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html[:ds] + json.dumps(DATA, separators=(',',':'), ensure_ascii=False) + html[de:])
from collections import Counter
yr = Counter(int(str(t['da'])[:4]) for t in DATA if t.get('da'))
print(f"real add-dates set: {real:,}  |  bogus placeholders removed: {nulled:,}  |  kept as-is: {kept:,}")
print("year histogram (true dates):")
for y in range(2012, 2027):
    print(f"  {y}: {yr.get(y,0)}")
print('backup:', os.path.basename(bak))
