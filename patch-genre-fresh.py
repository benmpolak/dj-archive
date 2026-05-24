#!/usr/bin/env python3
"""New-Music Bias panel (Listening) + Genre: Listen vs Own panel (Taste)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

ageBias = [["within 3 months",69],["3–12 months",10],["1–3 years",8],["3+ years",12]]
crateLO = [["Jazz",19,21],["Soul & R&B",16,14],["Disco & Boogie",14,15],["House",14,13],
 ["Indie & Rock",10,9],["Funk",8,8],["Brazilian",4,4],["Downtempo",3,2],["Hip Hop",3,2],
 ["Afro & World",3,3],["Electronic",1,2]]

COMPUTE = ("/* --- Genre/fresh (added) --- */\n"
  "  var ageBias=" + json.dumps(ageBias, ensure_ascii=False) + ";\n"
  "  var ageMax=Math.max.apply(null,ageBias.map(function(x){return x[1]}));\n"
  "  var crateLO=" + json.dumps(crateLO, ensure_ascii=False) + ";\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* New-Music Bias (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>New-Music Bias</h3>';
  h+='<div style="font-size:0.85em;line-height:1.5;color:var(--text);margin-bottom:10px"><b style="color:var(--accent)">69%</b> of your plays are on tracks you added in the last three months — and it has held near <b style="color:var(--accent2)">80% every year</b> since 2012. You chase the new and rarely look back. How old a track is when you play it:</div>';
  ageBias.forEach(function(p,i){var pct=Math.round(p[1]/ageMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'%</span></div>';
  });
  h+='</div>';
  /* Genre: Listen vs Own (added, taste) */
  h+='<div class="sd-section" data-tab="taste"><h3>Listen vs Own</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">You play almost exactly in proportion to what you collect — no genre runs the show. Properly eclectic.</div>';
  crateLO.forEach(function(p){
    h+='<div class="sd-bar-row"><span class="sd-bar-label" style="color:var(--accent)">'+p[0]+'</span><span style="flex:1;color:var(--text);font-size:0.82em">played '+p[1]+'% &middot; owned '+p[2]+'%</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-genrefresh-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
