#!/usr/bin/env python3
"""Add a 'When You Dig' snapshot section (day/hour/month) to the stats dashboard.
Data baked from the May 2026 playlist exports (full Added At timestamps), since the
archive itself only stores add-month, not day/time."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor found {n}x (expected 1): {old[:50]!r}"
    return s.replace(old, new)

COMPUTE = r"""/* --- When You Dig (snapshot from playlist exports, May 2026) --- */
  var digDOW=[['Mon',721],['Tue',690],['Wed',659],['Thu',606],['Fri',513],['Sat',316],['Sun',412]];
  var digHour=[22,2,0,0,0,1,10,120,187,301,334,323,282,414,287,250,227,94,128,160,229,302,172,72];
  var digMonth=[['Jan',232],['Feb',445],['Mar',398],['Apr',505],['May',434],['Jun',421],['Jul',401],['Aug',244],['Sep',235],['Oct',235],['Nov',181],['Dec',186]];
  var digMaxD=Math.max.apply(null,digDOW.map(function(x){return x[1]}));
  var digMaxH=Math.max.apply(null,digHour);
  var digMaxM=Math.max.apply(null,digMonth.map(function(x){return x[1]}));
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* When You Dig section (snapshot) */
  h+='<div class="sd-section"><h3>When You Dig</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">Snapshot from playlist exports &middot; times UTC &middot; as of May 2026</div>';
  h+='<div style="font-size:0.85em;line-height:1.5;color:var(--text);margin-bottom:12px"><p>You dig on <b style="color:var(--accent)">weekdays</b> &mdash; Monday heaviest, Saturday quietest &mdash; in two windows: <b style="color:var(--accent2)">late morning to lunch</b> and around <b style="color:var(--accent2)">9pm</b>. Spring is your busiest stretch.</p></div>';
  h+='<h4 style="margin-top:8px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">By day of week</h4>';
  digDOW.forEach(function(p,i){var pct=Math.round(p[1]/digMaxD*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'</span></div>';
  });
  h+='<h4 style="margin-top:14px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">By hour (UTC)</h4>';
  digHour.forEach(function(c,hh){var pct=Math.round(c/digMaxH*100);var lbl=(hh<10?'0':'')+hh+':00';
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+lbl+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[hh%colors.length]+'"></div></div><span class="sd-bar-count">'+c+'</span></div>';
  });
  h+='<h4 style="margin-top:14px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">By month (seasonality)</h4>';
  digMonth.forEach(function(p,i){var pct=Math.round(p[1]/digMaxM*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-whendig-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE, 'w').write(html)
print("patched. backup:", os.path.basename(bak))
