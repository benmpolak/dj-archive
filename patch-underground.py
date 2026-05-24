#!/usr/bin/env python3
"""The Underground panel: obscurity index (live) + most-played sub-10-popularity tracks."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

COMPUTE = r"""/* --- The Underground (added, live) --- */
  var _pn=0,_pd=0,_deep=0,_tot=0;
  DATA.forEach(function(t){var pc=t.pc||0;if(pc&&t.p!=null){_pn+=pc*t.p;_pd+=pc;_tot+=pc;if(t.p<20)_deep+=pc;}});
  var ugAvgPop=_pd?Math.round(_pn/_pd):0;
  var ugDeepPct=_tot?Math.round(100*_deep/_tot):0;
  var ug=DATA.filter(function(t){return (t.pc||0)>=8&&t.p>=0&&t.p<=10;}).sort(function(a,b){return b.pc-a.pc}).slice(0,14);
  var ugMax=ug.length?ug[0].pc:1;
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* The Underground (added, live) */
  if(ug.length){
    h+='<div class="sd-section"><h3>The Underground</h3>';
    h+='<div style="font-size:0.85em;line-height:1.5;color:var(--text);margin-bottom:10px"><b style="color:var(--accent)">'+ugDeepPct+'%</b> of your listening is on tracks the world barely knows, and your play-weighted average popularity is <b style="color:var(--accent2)">'+ugAvgPop+'/100</b>. You live in the crates. These are the deepest you spin:</div>';
    ug.forEach(function(t,i){var pct=Math.round(t.pc/ugMax*100);
      h+='<div class="sd-bar-row"><span class="sd-bar-label">'+t.a.split(';')[0]+' — '+t.t+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+t.pc+' · p'+t.p+'</span></div>';
    });
    h+='</div>';
  }
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-underground-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
