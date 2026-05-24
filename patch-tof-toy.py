#!/usr/bin/env python3
"""Swap Everton out of Track of the Year (2024/2026) + add a live 'This Time of Year'
panel: your most-played tracks for the current calendar month across all years, playable."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()
MONTHLY = json.load(open('/tmp/monthly.json'))

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

# 1) Track of the Year swaps
html = replace_once(html,
  '["2024", "Everton FC — Spirit Of The Blues · 43x"]',
  '["2024", "Kendrick Lamar — heart pt. 6 · 19x"]')
html = replace_once(html,
  '["2026", "Everton FC — Spirit Of The Blues · 13x so far"]',
  '["2026", "Maston — Street Scene · 8x so far"]')

# 2) "This Time of Year" panel — inject before Most Played (top of Listening tab)
html = replace_once(html,
  '<div class="sd-section" data-tab="listening"><h3>Most Played</h3>',
  '<div class="sd-section" data-tab="listening"><h3>This Time of Year</h3><div id="toy"></div></div>'
  '<div class="sd-section" data-tab="listening"><h3>Most Played</h3>')

# 3) top-level data + render function
INJECT = ("<script>\nvar MONTHLY=" + json.dumps(MONTHLY, ensure_ascii=False) + ";\n"
 "function renderTimeOfYear(){var el=document.getElementById('toy');if(!el)return;"
 "var mn=['January','February','March','April','May','June','July','August','September','October','November','December'];"
 "var m=new Date().getMonth()+1;var list=MONTHLY[m]||[];"
 "var s='<div style=\"font-size:0.8em;color:var(--dim);margin-bottom:8px\">The tracks you have played most in <b style=\"color:var(--accent)\">'+mn[m-1]+'</b> across every year — your soundtrack to this time of year. Tap to play.</div>';"
 "s+=list.map(function(r){return '<div class=\"sd-bar-row\"><a href=\"https://open.spotify.com/track/'+r[2]+'\" target=\"_blank\" style=\"flex:1;color:var(--text);font-size:0.84em;text-decoration:none\">'+r[0]+'</a><span class=\"sd-bar-count\">'+r[1]+'</span></div>';}).join('');"
 "el.innerHTML=s;}\n</script>\n</body>")
html = replace_once(html, "</body>", INJECT)

# 4) call it after dash render
html = replace_once(html,
  "if(window.initObsArc)initObsArc();",
  "if(window.initObsArc)initObsArc();if(window.renderTimeOfYear)renderTimeOfYear();")

bak = os.path.join(HERE, f"_backup-pre-toftoy-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
