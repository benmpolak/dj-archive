#!/usr/bin/env python3
"""Interactive Obsession Arcs: pick a top track, see its monthly play history (spike + fade)."""
import os, shutil, json, glob
from datetime import datetime
from collections import defaultdict, Counter

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
                if depth==0: return json.loads(html[ds:i+1])
        i+=1

html = open(ARCHIVE).read()
DATA = parse_data(html)
# top 100 archive tracks by play count
top = sorted([t for t in DATA if t.get('pc')], key=lambda t:-t['pc'])[:100]
topsid = {t['sid']: (t['a'].split(';')[0]+' — '+t['t'], t['pc']) for t in top}

# monthly counts per top sid
months = defaultdict(Counter)  # sid -> ym(int yyyymm) -> count
for f in HIST:
    for r in json.load(open(f)):
        if (r.get('ms_played') or 0) < 30000: continue
        u = r.get('spotify_track_uri') or ''
        if not u.startswith('spotify:track:'): continue
        sid = u.split(':')[-1]
        if sid not in topsid: continue
        ym = r.get('ts','')[:7]
        if len(ym)==7: months[sid][ym]+=1

def ym_to_idx(ym):
    y,m = int(ym[:4]), int(ym[5:7]); return y*12+(m-1)

OBSESS = []
for t in top:
    sid = t['sid']
    mc = months.get(sid)
    if not mc: continue
    idxs = sorted(ym_to_idx(k) for k in mc)
    lo, hi = idxs[0], idxs[-1]
    counts = [0]*(hi-lo+1)
    for k,v in mc.items():
        counts[ym_to_idx(k)-lo] = v
    start = f"{lo//12}-{(lo%12)+1:02d}"
    OBSESS.append({"l": topsid[sid][0], "pc": t['pc'], "start": start, "c": counts})

INJECT = ("<script>\nvar OBSESS=" + json.dumps(OBSESS, ensure_ascii=False) + ";\n"
 "function renderObsArc(i){var o=OBSESS[i];if(!o)return;var max=Math.max.apply(null,o.c)||1;"
 "var sy=+o.start.slice(0,4),sm=+o.start.slice(5,7);"
 "var bars=o.c.map(function(v,k){var mm=sm-1+k,yy=sy+Math.floor(mm/12),mo=(mm%12)+1;"
 "var lbl=yy+'-'+('0'+mo).slice(-2);var hh=v?Math.max(4,Math.round(v/max*64)):1;"
 "var col=v?'var(--accent)':'var(--border)';"
 "return '<div title=\"'+lbl+': '+v+' plays\" style=\"flex:1;min-width:2px;height:'+hh+'px;background:'+col+';border-radius:2px 2px 0 0\"></div>';}).join('');"
 "var last=o.c.length-1,mm=sm-1+last,ey=sy+Math.floor(mm/12),em=(mm%12)+1;"
 "document.getElementById('obsArc').innerHTML='<div style=\"display:flex;align-items:flex-end;gap:1px;height:68px;margin:8px 0\">'+bars+'</div><div style=\"display:flex;justify-content:space-between;font-size:0.65em;color:var(--dim)\"><span>'+o.start+'</span><span>peak '+max+'/mo</span><span>'+ey+'-'+('0'+em).slice(-2)+'</span></div>';}"
 "function initObsArc(){var sel=document.getElementById('obsSel');if(!sel||sel._init)return;sel._init=1;"
 "sel.innerHTML=OBSESS.map(function(o,i){return '<option value=\"'+i+'\">'+o.l+' ('+o.pc+')</option>'}).join('');"
 "sel.onchange=function(){renderObsArc(+sel.value)};renderObsArc(0);}\n</script>\n</body>")
html = html.replace("</body>", INJECT, 1)

# dashboard panel (Listening tab)
PANEL = ("/* Obsession Arcs (added, listening) */\n"
 "  h+='<div class=\"sd-section\" data-tab=\"listening\"><h3>Obsession Arcs</h3>';\n"
 "  h+='<div style=\"font-size:0.8em;color:var(--dim);margin-bottom:8px\">Pick a track and watch the obsession spike and fade, month by month</div>';\n"
 "  h+='<select id=\"obsSel\" style=\"width:100%;padding:8px;border-radius:8px;background:var(--card2);color:var(--text);border:1px solid var(--border);font-size:0.82em\"></select>';\n"
 "  h+='<div id=\"obsArc\"></div>';\n"
 "  h+='</div>';\n"
 "  /* Vinyl Collection section */")
assert html.count("/* Vinyl Collection section */")==1
html = html.replace("/* Vinyl Collection section */", PANEL)

# init after render
assert html.count("selectStatsTab('collection');")==1
html = html.replace("selectStatsTab('collection');", "selectStatsTab('collection');if(window.initObsArc)initObsArc();")

bak = os.path.join(HERE, f"_backup-pre-obsarc-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print(f"patched. {len(OBSESS)} tracks with arcs. backup: {os.path.basename(bak)}")
