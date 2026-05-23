#!/usr/bin/env python3
"""Wire play counts into the UI: a 'Plays' sort button + a 'Most Played' stats section."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

# 1) add a 'plays' comparator
html = replace_once(html,
  "album:(a,b)=>(a.al||'').localeCompare(b.al||'')*sdir};",
  "album:(a,b)=>(a.al||'').localeCompare(b.al||'')*sdir,plays:(a,b)=>((a.pc||0)-(b.pc||0))*sdir};")

# 2) add the Plays sort button
html = replace_once(html,
  '<div class="sort-btn" data-s="album">Album</div>',
  '<div class="sort-btn" data-s="album">Album</div>\n        <div class="sort-btn" data-s="plays">Plays</div>')

# 3) default Plays to descending (most-played first)
html = replace_once(html,
  "const k=b.dataset.s;if(k===sorted_key)sdir*=-1;else{sorted_key=k;sdir=k==='recent'?-1:1}",
  "const k=b.dataset.s;if(k===sorted_key)sdir*=-1;else{sorted_key=k;sdir=(k==='recent'||k==='plays')?-1:1}")

# 4) Most Played stats computation
COMPUTE = r"""/* --- Most played (added) --- */
  var played=DATA.filter(function(t){return t.pc});
  var mostPlayed=played.slice().sort(function(a,b){return b.pc-a.pc}).slice(0,15);
  var maxPlay=mostPlayed.length?mostPlayed[0].pc:1;
  var artPlays={};played.forEach(function(t){var a=t.a.split(';')[0].trim();artPlays[a]=(artPlays[a]||0)+t.pc;});
  var topPlayedArt=Object.entries(artPlays).sort(function(a,b){return b[1]-a[1]}).slice(0,12);
  var maxArtPlay=topPlayedArt.length?topPlayedArt[0][1]:1;
  var totalPlays=played.reduce(function(s,t){return s+t.pc},0);
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

# 5) Most Played render section
RENDER = r"""/* Most Played section (added) */
  h+='<div class="sd-section"><h3>Most Played</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">'+totalPlays.toLocaleString()+' plays across '+played.length.toLocaleString()+' of your tracks &middot; from your Spotify listening history</div>';
  mostPlayed.forEach(function(t,i){var pct=Math.round(t.pc/maxPlay*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+t.a.split(';')[0]+' — '+t.t+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+t.pc+'</span></div>';
  });
  h+='<h4 style="margin-top:14px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">Most-played artists</h4>';
  topPlayedArt.forEach(function(p,i){var pct=Math.round(p[1]/maxArtPlay*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-playsui-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
