#!/usr/bin/env python3
"""Two more panels: You Were Early (live, high plays + low popularity) and
Ride or Die (baked, artists played in the most distinct years)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

rideOrDie = [["Crazy P",15],["Bill Withers",15],["Aretha Franklin",14],["Kendrick Lamar",14],
 ["Badly Drawn Boy",14],["Marvin Gaye",14],["Erykah Badu",14],["A Tribe Called Quest",14],
 ["Gil Scott-Heron",14],["Marcos Valle",14],["Steely Dan",14],["Real Estate",13]]

COMPUTE = ("/* --- Panels 2 (added) --- */\n"
  "  var early=DATA.filter(function(t){return (t.pc||0)>=15&&t.p>0&&t.p<=25;}).sort(function(a,b){return b.pc-a.pc}).slice(0,12);\n"
  "  var earlyMax=early.length?early[0].pc:1;\n"
  "  var rideOrDie=" + json.dumps(rideOrDie, ensure_ascii=False) + ";\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* You Were Early (added, live) */
  if(early.length){
    h+='<div class="sd-section"><h3>You Were Early</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Played to bits, yet barely anyone else has — low Spotify popularity. You back the underdogs.</div>';
    early.forEach(function(t,i){var pct=Math.round(t.pc/earlyMax*100);
      h+='<div class="sd-bar-row"><span class="sd-bar-label">'+t.a.split(';')[0]+' — '+t.t+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+t.pc+' · p'+t.p+'</span></div>';
    });
    h+='</div>';
  }
  /* Ride or Die (added, snapshot) */
  h+='<div class="sd-section"><h3>Ride or Die</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Artists you\'ve played every year, for years &middot; distinct years they appear in your listening</div>';
  rideOrDie.forEach(function(p,i){var pct=Math.round(p[1]/15*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'y</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-panels2-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
