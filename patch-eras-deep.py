#!/usr/bin/env python3
"""Make Your Eras rows expandable: each year opens its chapter —
soundtrack (top plays that year), artists discovered, biggest rabbit hole."""
import json, glob, os, re, shutil, datetime
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

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
bysid = {t.get('sid'): t for t in DATA if t.get('sid')}

# per-year per-track plays
yp = defaultdict(Counter)
for f in glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json'):
    for r in json.load(open(f)):
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[2]
        if sid not in bysid or (r.get('ms_played') or 0) < 30000: continue
        y = int(r.get('ts','0')[:4])
        yp[y][sid] += 1

# artist debut year by adds + volume that year
debut = {}
peryear = defaultdict(Counter)
for t in DATA:
    da = t.get('da') or 0
    y = da // 100
    if not (2012 <= y <= 2026): continue
    a = (t.get('a') or '').split(';')[0].strip()
    if not a: continue
    peryear[y][a] += 1
    if a not in debut or y < debut[a]: debut[a] = y

ERASD = {}
for y in range(2012, 2027):
    tracks = [{'a': bysid[sid]['a'], 't': bysid[sid]['t'], 'n': n, 'sid': sid}
              for sid, n in yp[y].most_common(10)]
    newa = [a for a, n in peryear[y].most_common(40) if debut.get(a) == y and n >= 3][:6]
    if tracks or newa:
        ERASD[str(y)] = {'tracks': tracks, 'newa': newa}
print('years with detail:', sorted(ERASD))
for y in ('2014','2025'):
    d = ERASD.get(y, {})
    print(y, 'top:', ', '.join(f"{t['a'].split(';')[0]} — {t['t']} ({t['n']})" for t in d.get('tracks', [])[:3]))
    print(y, 'discovered:', ', '.join(d.get('newa', [])))

inject = 'var ERASD=' + json.dumps(ERASD, separators=(',',':'), ensure_ascii=False) + ';'
if 'var ERASD=' in html:
    html = re.sub(r'var ERASD=\{.*?\};\n?', inject + '\n', html, count=1, flags=re.S)
else:
    html = html.replace('var PLAYLISTED=', inject + '\nvar PLAYLISTED=', 1)

OLD_INIT = """if(window.ERAS&&ERAS.adds&&ERAS.adds.length){var _erR=function(items){var mx=Math.max.apply(null,items.map(function(x){return x.n}));return function(x,i){var lbl=x.y+' <span style="color:var(--dim);font-size:0.85em">&mdash; '+x.top.map(function(p){return p[0]+' '+p[1]+'%'}).join(', ')+'</span>';return sdNameRow(lbl,x.n.toLocaleString(),Math.round(x.n/mx*100),_hamColors[i%8],null);}};pgInit('pgErasA',ERAS.adds,_erR(ERAS.adds));pgInit('pgErasP',ERAS.plays,_erR(ERAS.plays));}"""
NEW_INIT = """if(window.ERAS&&ERAS.adds&&ERAS.adds.length){var _erR=function(items){var mx=Math.max.apply(null,items.map(function(x){return x.n}));return function(x,i){var lbl=x.y+' <span style="color:var(--dim);font-size:0.85em">&mdash; '+x.top.map(function(p){return p[0]+' '+p[1]+'%'}).join(', ')+'</span> <span style="color:var(--dim);font-size:0.75em">&#9656;</span>';return '<div class="er-row" data-y="'+x.y+'" onclick="erToggle(this,event)" style="cursor:pointer">'+sdNameRow(lbl,x.n.toLocaleString(),Math.round(x.n/mx*100),_hamColors[i%8],null)+'<div class="er-detail" style="display:none;padding:2px 0 8px 8px;border-left:2px solid var(--border);margin:-4px 0 8px 2px"></div></div>';}};pgInit('pgErasA',ERAS.adds,_erR(ERAS.adds));pgInit('pgErasP',ERAS.plays,_erR(ERAS.plays));}
function erToggle(el,ev){if(ev&&ev.target&&ev.target.closest('.er-detail'))return;var d=el.querySelector('.er-detail');if(!d)return;if(d.style.display==='none'){if(!d.innerHTML)d.innerHTML=erDetailHtml(el.dataset.y);d.style.display='block';}else{d.style.display='none';}}
function erDetailHtml(y){var ed=(window.ERASD||{})[y];if(!ed)return '<div style="color:var(--dim);font-size:0.8em;padding:6px 0">No plays logged for '+y+'</div>';var h='';
  if(ed.tracks&&ed.tracks.length){h+='<div style="font-size:0.72em;color:var(--dim);margin:8px 0 4px;text-transform:uppercase;letter-spacing:0.05em">Soundtrack of '+y+'</div>';ed.tracks.forEach(function(t,i){var nm=t.a.split(';')[0]+' — '+t.t;var link=(t.sid&&(''+t.sid).length===22)?'<a href="https://open.spotify.com/track/'+t.sid+'" target="_blank" style="color:var(--text);text-decoration:none">'+nm+'</a>':nm;h+='<div style="display:flex;justify-content:space-between;gap:10px;font-size:0.8em;line-height:1.55"><span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span style="color:var(--dim)">'+(i+1)+'.</span> '+link+'</span><span style="color:var(--dim);font-family:\\'JetBrains Mono\\',monospace;font-size:0.85em;flex-shrink:0">'+t.n+'</span></div>';});}
  if(ed.newa&&ed.newa.length)h+='<div style="font-size:0.78em;color:var(--dim);margin:8px 0 2px">Discovered that year: <span style="color:var(--text)">'+ed.newa.join(', ')+'</span></div>';
  if(window.TRIPS&&TRIPS.items){var best=null;TRIPS.items.forEach(function(x){if(x.s.slice(0,4)==y&&(!best||x.n>best.n))best=x;});if(best)h+='<div style="font-size:0.78em;color:var(--dim);margin:4px 0 2px">Biggest rabbit hole: <span style="color:var(--text)">'+best.arts.join(', ')+(best.more?' +'+best.more:'')+'</span> ('+best.n+' plays)</div>';}
  return h||'<div style="color:var(--dim);font-size:0.8em">&mdash;</div>';}"""
assert OLD_INIT in html, 'eras init anchor missing'
html = html.replace(OLD_INIT, NEW_INIT, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-erasdeep-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('injected expandable eras')
