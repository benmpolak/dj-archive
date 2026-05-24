#!/usr/bin/env python3
"""Listened Abroad (Listening) + Your Listening Mellowed (Taste)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

abroad = [["Spain",701],["Greece",345],["USA",271],["Italy",241],["Israel",204],
 ["Cyprus",165],["Mexico",152],["South Africa",126]]
ergYr = [["2012",66],["2013",65],["2014",64],["2015",63],["2016",63],["2017",64],
 ["2018",63],["2019",61],["2020",61],["2021",63],["2022",60],["2023",55],
 ["2024",55],["2025",57],["2026",58]]

COMPUTE = ("/* --- Where / mellow (added) --- */\n"
  "  var abroad=" + json.dumps(abroad, ensure_ascii=False) + ";\n"
  "  var abroadMax=Math.max.apply(null,abroad.map(function(x){return x[1]}));\n"
  "  var ergYr=" + json.dumps(ergYr) + ";\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* Listened Abroad (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>Listened Abroad</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">97% of your listening is in the UK — the rest is basically your holidays. Plays logged abroad:</div>';
  abroad.forEach(function(p,i){var pct=Math.round(p[1]/abroadMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Your Listening Mellowed (added, taste) */
  h+='<div class="sd-section" data-tab="taste"><h3>You Mellowed</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Average energy of what you play, by year. Down from 0.66 to ~0.56 — sharpest after 2022. Tempo held (~117bpm), so it is lower-energy, not slower.</div>';
  ergYr.forEach(function(p,i){var pct=p[1];
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">0.'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-wheremellow-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
