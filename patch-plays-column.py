#!/usr/bin/env python3
"""Move play count from the in-cell badge to a proper sortable 'Plays' column
(next to Vibe), mirroring the BPM column. Window-aware value."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

WINVAL = "(function(){var _v=sorted_key==='playsW'?t.pw:sorted_key==='playsM'?t.pm:sorted_key==='playsY'?t.py:t.pc;return _v"

# 1) remove the in-cell badge from col-t
html = replace_once(html,
  "+editBtn+" + WINVAL + "?'<span class=\"pc-badge\" title=\"'+_v+' plays\">▶'+_v+'</span>':'';})()+(daStr?",
  "+editBtn+(daStr?")

# 2) add a col-pc <td> (window-aware) before the vibe cell
html = replace_once(html,
  "+(t.tp>0?t.tp.toFixed(0):'')+'</td><td class=\"col-vb\">",
  "+(t.tp>0?t.tp.toFixed(0):'')+'</td><td class=\"col-pc\">'+" + WINVAL + "||'';})()+'</td><td class=\"col-vb\">")

# 3) header cell (sortable)
html = replace_once(html,
  '<th class="col-vb">Vibe</th>',
  '<th class="col-pc sortable" data-sort="plays">Plays ↕</th><th class="col-vb">Vibe</th>')

# 4) CSS width rule, mirroring BPM
html = replace_once(html,
  ".col-bpm{width:4%;font-family:'JetBrains Mono',monospace;font-size:0.72em;text-align:right}",
  ".col-bpm{width:4%;font-family:'JetBrains Mono',monospace;font-size:0.72em;text-align:right}"
  ".col-pc{width:4%;font-family:'JetBrains Mono',monospace;font-size:0.72em;text-align:right;color:var(--accent)}")

# 5) hide col-pc on mobile wherever col-bpm hides
html = html.replace(".col-bpm,", ".col-bpm,.col-pc,")

# 6) make Plays sort descending-first from the header too
html = replace_once(html,
  "const k=th.dataset.sort;if(k===sorted_key)sdir*=-1;else{sorted_key=k;sdir=k==='recent'?-1:1}",
  "const k=th.dataset.sort;if(k===sorted_key)sdir*=-1;else{sorted_key=k;sdir=(k==='recent'||k.indexOf('plays')===0)?-1:1}")

bak = os.path.join(HERE, f"_backup-pre-pccol-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
