#!/usr/bin/env python3
"""Group the 23 stats sections into 5 tabs (Collection / Listening / Taste / Timeline / Vinyl)."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:60]!r}"
    return s.replace(old, new)

TABMAP = {
 'The Story':'collection','By Decade':'collection','Signature Artists':'collection',
 'By Crate':'collection','Deeper Cuts':'collection',
 'Most Played':'listening','Your Listening Clock':'listening','Forgotten Loves':'listening',
 'Evergreens':'listening','By The Numbers':'listening','New Discoveries':'listening',
 'How Your Taste Drifted':'taste','Genre by Year':'taste','Mood Map':'taste',
 'You Were Early':'taste','The Underground':'taste','Ride or Die':'taste','Artist of the Year':'taste',
 'When You Added It':'timeline','When You Dig':'timeline','Your Range':'timeline','Listening by Season':'timeline',
 'The Vinyl Collection':'vinyl',
}
TABBAR = ('<div class="sd-tabs">'
 '<div class="sd-tab active" data-st="collection">Collection</div>'
 '<div class="sd-tab" data-st="listening">Listening</div>'
 '<div class="sd-tab" data-st="taste">Taste</div>'
 '<div class="sd-tab" data-st="timeline">Timeline</div>'
 '<div class="sd-tab" data-st="vinyl">Vinyl</div>'
 '</div>')

# tag each section with its tab; prepend the tab bar before the first section (The Story)
for title, tab in TABMAP.items():
    old = '<div class="sd-section"><h3>'+title+'</h3>'
    new = '<div class="sd-section" data-tab="'+tab+'"><h3>'+title+'</h3>'
    if title == 'The Story':
        new = TABBAR + new
    html = replace_once(html, old, new)

# CSS
html = replace_once(html,
  ".pc-badge{font-size:0.7em;color:var(--accent);background:var(--card2);border-radius:6px;padding:1px 5px;margin-left:6px;font-family:'JetBrains Mono',monospace;white-space:nowrap;vertical-align:middle}",
  ".pc-badge{font-size:0.7em;color:var(--accent);background:var(--card2);border-radius:6px;padding:1px 5px;margin-left:6px;font-family:'JetBrains Mono',monospace;white-space:nowrap;vertical-align:middle}"
  ".sd-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 18px}"
  ".sd-tab{padding:6px 14px;border-radius:20px;font-size:0.8em;cursor:pointer;background:var(--card2);border:1px solid var(--border);color:var(--dim);font-weight:600}"
  ".sd-tab:hover{border-color:var(--accent);color:var(--text)}"
  ".sd-tab.active{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#0a0a0f;border:none}")

# tab-switch function
html = replace_once(html, "function closeStatsDash",
  "function selectStatsTab(tab){var d=document.getElementById('stats-dash');"
  "d.querySelectorAll('.sd-section').forEach(function(s){s.style.display=(s.getAttribute('data-tab')===tab)?'':'none'});"
  "d.querySelectorAll('.sd-tab').forEach(function(b){b.classList.toggle('active',b.getAttribute('data-st')===tab)});}\n"
  "function closeStatsDash")

# wire tabs + default after render
html = replace_once(html, "dash.innerHTML=h;",
  "dash.innerHTML=h;dash.querySelectorAll('.sd-tab').forEach(function(b){b.onclick=function(){selectStatsTab(b.getAttribute('data-st'))}});selectStatsTab('collection');")

bak = os.path.join(HERE, f"_backup-pre-tabs-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
