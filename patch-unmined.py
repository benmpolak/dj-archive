#!/usr/bin/env python3
"""Unmined Albums panel (Collection tab): saved albums in Spotify library
with NO track in the archive — albums Ben rates but never crate-dug."""
import zipfile, json, os, re, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
z = zipfile.ZipFile('/Users/benpolak/Downloads/my_spotify_data (2).zip')
lib = json.loads(z.read('Spotify Account Data/YourLibrary.json'))

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
albs = {(re.split(r'[;,]', t.get('a') or '')[0].strip().lower(), (t.get('al') or '').strip().lower()) for t in DATA}

items = []
for a in lib.get('albums') or []:
    artist = (a.get('artist') or '').strip()
    album = (a.get('album') or '').strip()
    k = (artist.split(',')[0].strip().lower(), album.lower())
    if k in albs: continue
    aid = (a.get('uri') or '').split(':')[-1]
    items.append({'a': artist, 'al': album, 'id': aid})
print(f'{len(items)} unmined albums')

UNMINED = {'items': items, 'total': len(lib.get('albums') or [])}
inject = 'var UNMINED=' + json.dumps(UNMINED, separators=(',',':'), ensure_ascii=False) + ';'
if 'var UNMINED=' in html:
    html = re.sub(r'var UNMINED=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

PANEL = """  /* Unmined Albums (added) */
  if(window.UNMINED&&UNMINED.items&&UNMINED.items.length){
    h+='<div class="sd-section" data-tab="collection"><h3>Unmined Albums</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:10px">Albums you\\'ve saved to your Spotify library but never pulled a single track from into the archive &mdash; '+UNMINED.items.length+' of your '+UNMINED.total+' saved albums. A digging to-do list. Tap to open.</div>';
    h+='<div id="pgUnmined"></div>';
    h+='</div>';
  }
"""
if 'Unmined Albums (added)' not in html:
    anchor = '  /* Listening Clock (added, snapshot from streaming history) */'
    html = html.replace(anchor, PANEL + anchor, 1)

INIT = """if(window.UNMINED&&UNMINED.items&&UNMINED.items.length)pgInit('pgUnmined',UNMINED.items,function(v,i){return sdNameRow('<span style="color:var(--dim)">'+(i+1)+'.</span> '+v.a+' — '+v.al,'',0,_hamColors[i%8],v.id?('https://open.spotify.com/album/'+v.id):null);});
  """
if "pgInit('pgUnmined'" not in html:
    anchor2 = "if(window.VINYLVAL&&VINYLVAL.items&&VINYLVAL.items.length)pgInit('pgVinylVal'"
    html = html.replace(anchor2, INIT + anchor2, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-unmined-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected UNMINED panel')
