#!/usr/bin/env python3
"""Add windowed play sorts (1y/30d/7d) + make the row badge reflect the active window."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

# 1) comparators
html = replace_once(html,
  ",plays:(a,b)=>((a.pc||0)-(b.pc||0))*sdir};",
  ",plays:(a,b)=>((a.pc||0)-(b.pc||0))*sdir,playsY:(a,b)=>((a.py||0)-(b.py||0))*sdir,playsM:(a,b)=>((a.pm||0)-(b.pm||0))*sdir,playsW:(a,b)=>((a.pw||0)-(b.pw||0))*sdir};")

# 2) buttons
html = replace_once(html,
  '<div class="sort-btn" data-s="plays">Plays</div>',
  '<div class="sort-btn" data-s="plays">Plays</div>\n        <div class="sort-btn" data-s="playsY">Plays 1y</div>\n        <div class="sort-btn" data-s="playsM">Plays 30d</div>\n        <div class="sort-btn" data-s="playsW">Plays 7d</div>')

# 3) all play-sorts default to descending
html = replace_once(html,
  "sdir=(k==='recent'||k==='plays')?-1:1}",
  "sdir=(k==='recent'||k.indexOf('plays')===0)?-1:1}")

# 4) window-aware row badge
html = replace_once(html,
  "(t.pc?'<span class=\"pc-badge\" title=\"'+t.pc+' plays in your listening history\">▶'+t.pc+'</span>':'')",
  "(function(){var _v=sorted_key==='playsW'?t.pw:sorted_key==='playsM'?t.pm:sorted_key==='playsY'?t.py:t.pc;return _v?'<span class=\"pc-badge\" title=\"'+_v+' plays\">▶'+_v+'</span>':'';})()")

bak = os.path.join(HERE, f"_backup-pre-pwinui-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
