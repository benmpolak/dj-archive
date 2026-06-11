#!/usr/bin/env python3
"""The Hunt panel (Taste tab): search -> click -> add -> plays lifecycle.
SearchQueries.json logs the exact URI clicked from each search; join to
archive tracks, the add-ledger, and play history."""
import zipfile, json, os, re, shutil, datetime, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

z = zipfile.ZipFile('/Users/benpolak/Downloads/my_spotify_data (2).zip')
sq = json.loads(z.read('Spotify Account Data/SearchQueries.json'))

# clicked track URIs with query + time (earliest click per track)
clicks = {}
for r in sq:
    q = (r.get('searchQuery') or '').strip()
    ts = (r.get('searchTime') or '')[:10]
    for uri in r.get('searchInteractionURIs') or []:
        if isinstance(uri, str) and uri.startswith('spotify:track:'):
            sid = uri.split(':')[2]
            if sid not in clicks or ts < clicks[sid][1]:
                clicks[sid] = (q, ts)
print(f'{len(clicks)} distinct tracks clicked from search ({len(sq)} queries)')

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
bysid = {t.get('sid'): t for t in DATA}

# plays after the search date, from raw streaming history
hits = {sid for sid in clicks if sid in bysid}
playafter = {sid: 0 for sid in hits}
for f in glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json'):
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[2]
        if sid in hits and (r.get('ms_played') or 0) >= 30000 and r.get('ts','')[:10] >= clicks[sid][1]:
            playafter[sid] += 1

# which playlist took it, from the add ledger
ledger = json.load(open(os.path.join(HERE, 'add-ledger.json')))
addedto = {}
for pl, items in ledger.items():
    for sid, ym in items.items():
        if sid in hits and (sid not in addedto or ym < addedto[sid][1]):
            addedto[sid] = (pl, ym)

items = []
for sid in hits:
    t = bysid[sid]
    q, ts = clicks[sid]
    pl = addedto.get(sid, ('', ''))[0]
    items.append({'a': t.get('a',''), 't': t.get('t',''), 'q': q, 'd': ts,
                  'pl': pl, 'n': playafter[sid], 'sid': sid})
items.sort(key=lambda x: -x['n'])
items = items[:100]
print(f'{len(hits)} hunted tracks landed in the archive; top:')
for it in items[:8]:
    print(f"  {it['n']:3d} plays  {it['a']} — {it['t']}  (hunted \"{it['q']}\" {it['d']}, -> {it['pl'] or '?'})")

HUNT = {'items': items, 'nq': len(sq), 'nc': len(hits)}
inject = 'var HUNT=' + json.dumps(HUNT, separators=(',',':'), ensure_ascii=False) + ';'
if 'var HUNT=' in html:
    html = re.sub(r'var HUNT=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

PANEL = """  /* The Hunt (added) */
  if(window.HUNT&&HUNT.items&&HUNT.items.length){
    h+='<div class="sd-section" data-tab="taste"><h3>The Hunt</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:10px">From search box to heavy rotation &mdash; tracks you hunted down by name, when you found them, where you filed them and how hard they hit. '+HUNT.nc+' archive tracks traced from '+HUNT.nq.toLocaleString()+' recent searches.</div>';
    h+='<div id="pgHunt"></div>';
    h+='</div>';
  }
"""
if 'The Hunt (added)' not in html:
    anchor = '  /* Listening Clock (added, snapshot from streaming history) */'
    html = html.replace(anchor, PANEL + anchor, 1)

INIT = """if(window.HUNT&&HUNT.items&&HUNT.items.length){var _huntMax=(HUNT.items[0]&&HUNT.items[0].n)||1;pgInit('pgHunt',HUNT.items,function(v,i){var sub=' <span style="color:var(--dim);font-size:0.85em">&mdash; hunted '+v.d.slice(0,7)+(v.pl?(' &rarr; '+v.pl):'')+'</span>';return sdNameRow('<span style="color:var(--dim)">'+(i+1)+'.</span> '+v.a.split(';')[0]+' — '+v.t+sub,(v.n?v.n+' plays since':'fresh'),Math.round(v.n/_huntMax*100),_hamColors[i%8],'https://open.spotify.com/track/'+v.sid);});}
  """
if "pgInit('pgHunt'" not in html:
    anchor2 = "if(window.VINYLVAL&&VINYLVAL.items&&VINYLVAL.items.length)pgInit('pgVinylVal'"
    html = html.replace(anchor2, INIT + anchor2, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-hunt-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected HUNT panel')
