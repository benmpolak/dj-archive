#!/usr/bin/env python3
"""Two more panels: By The Numbers (milestones) and New Discoveries (new artists/yr)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

newDisc = [["2012",316],["2013",477],["2014",680],["2015",440],["2016",347],["2017",429],
 ["2018",1278],["2019",649],["2020",497],["2021",550],["2022",1040],["2023",777],
 ["2024",701],["2025",898],["2026",422]]

COMPUTE = ("/* --- Panels 3 (added) --- */\n"
  "  var newDisc=" + json.dumps(newDisc) + ";\n"
  "  var ndMax=Math.max.apply(null,newDisc.map(function(x){return x[1]}));\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* By The Numbers (added, snapshot) */
  h+='<div class="sd-section"><h3>By The Numbers</h3>';
  h+='<div style="display:flex;flex-direction:column;gap:10px;font-size:0.85em;line-height:1.5;color:var(--text)">';
  h+='<p><b style="color:var(--accent)">308,727</b> streams logged since 2012.</p>';
  h+='<p><b style="color:var(--accent)">5,790 hours</b> of listening — 241 days solid.</p>';
  h+='<p>Your first ever Spotify play: <b style="color:var(--accent2)">JAY-Z — Otis</b>, 16 June 2012.</p>';
  h+='<p>Busiest single day: <b style="color:var(--accent2)">14 April 2016</b> — 209 tracks in one day.</p>';
  h+='<p>You skip roughly <b style="color:var(--accent)">1 in 3</b> of what comes on. Ruthless.</p>';
  h+='</div></div>';
  /* New Discoveries (added, snapshot) */
  h+='<div class="sd-section"><h3>New Discoveries</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">New artists you heard for the first time each year &middot; you never stop digging</div>';
  newDisc.forEach(function(p,i){var pct=Math.round(p[1]/ndMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-panels3-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
