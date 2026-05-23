#!/usr/bin/env python3
"""Row play-count badge + 4 new stats panels (listening clock, most skipped [baked
from raw history], forgotten loves + evergreens [live from pc/fp/lp])."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

# 1) CSS for the row badge
html = replace_once(html,
  ".cc-quick-btn.stats-hero:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(232,160,64,0.55);color:#0a0a0f}",
  ".cc-quick-btn.stats-hero:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(232,160,64,0.55);color:#0a0a0f}"
  ".pc-badge{font-size:0.7em;color:var(--accent);background:var(--card2);border-radius:6px;padding:1px 5px;margin-left:6px;font-family:'JetBrains Mono',monospace;white-space:nowrap;vertical-align:middle}")

# 2) Row badge in the track cell
html = replace_once(html,
  "+editBtn+(daStr?'<span class=\"mob-da\">'+daStr+'</span>':'')+'</td><td class=\"col-al\">'",
  "+editBtn+(t.pc?'<span class=\"pc-badge\" title=\"'+t.pc+' plays in your listening history\">▶'+t.pc+'</span>':'')+(daStr?'<span class=\"mob-da\">'+daStr+'</span>':'')+'</td><td class=\"col-al\">'")

# 3) Compute block (baked clock/skip arrays + live forgotten/evergreen)
COMPUTE = r"""/* --- Listening data (added) --- */
  var lcHours=[785,391,220,197,120,110,398,2167,4223,3338,2358,3214,3247,3677,3839,3856,3661,3597,3407,3337,2769,2648,2666,1620];
  var lcMaxH=Math.max.apply(null,lcHours);
  var lcDOW=[['Mon',9080],['Tue',8788],['Wed',9067],['Thu',8510],['Fri',9750],['Sat',4990],['Sun',5660]];
  var lcMaxD=Math.max.apply(null,lcDOW.map(function(x){return x[1]}));
  var lcDeliberate=40;
  var skipList=[['Parov Stelar','Catgroove',463],['Paul Simon','You Can Call Me Al',81],['Bobby Womack','Across 110th Street',73],['Prince','Raspberry Beret',73],['Earth, Wind & Fire','Sun Goddess',71],["The O'Jays",'I Love Music',67],['Todd Terje','Strandbar (disko)',65],['CHIC','I Want Your Love',65],["The O'Jays",'Back Stabbers',64],['The Doobie Brothers','What a Fool Believes',64]];
  var skipMax=skipList[0][2];
  var forgotten=DATA.filter(function(t){return t.pc>=8&&t.lp&&t.lp<202505;}).sort(function(a,b){return b.pc-a.pc}).slice(0,12);
  var fMax=forgotten.length?forgotten[0].pc:1;
  var evergreen=DATA.filter(function(t){return t.pc>=10&&t.fp&&t.lp;}).map(function(t){return {t:t,span:Math.floor(t.lp/100)-Math.floor(t.fp/100)};}).filter(function(x){return x.span>=5;}).sort(function(a,b){return b.span-a.span||b.t.pc-a.t.pc}).slice(0,12);
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

# 4) Render block
RENDER = r"""/* Listening Clock (added, snapshot from streaming history) */
  h+='<div class="sd-section"><h3>Your Listening Clock</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">When you actually listen &middot; from your Spotify history &middot; '+lcDeliberate+'% deliberate, the rest on shuffle</div>';
  h+='<h4 style="margin:8px 0 6px;font-size:0.8em;color:var(--dim)">By hour</h4>';
  lcHours.forEach(function(c,hh){var pct=Math.round(c/lcMaxH*100);var lbl=(hh<10?'0':'')+hh+':00';
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+lbl+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[hh%colors.length]+'"></div></div><span class="sd-bar-count">'+c.toLocaleString()+'</span></div>';
  });
  h+='<h4 style="margin:14px 0 6px;font-size:0.8em;color:var(--dim)">By day</h4>';
  lcDOW.forEach(function(p,i){var pct=Math.round(p[1]/lcMaxD*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Forgotten Loves (added, live) */
  if(forgotten.length){
    h+='<div class="sd-section"><h3>Forgotten Loves</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Played to death once, not touched in over a year. Worth a revisit.</div>';
    forgotten.forEach(function(t,i){var pct=Math.round(t.pc/fMax*100);
      h+='<div class="sd-bar-row"><span class="sd-bar-label">'+t.a.split(';')[0]+' — '+t.t+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+t.pc+'</span></div>';
    });
    h+='</div>';
  }
  /* Evergreens (added, live) */
  if(evergreen.length){
    h+='<div class="sd-section"><h3>Evergreens</h3>';
    h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Still in rotation years after you found them &middot; years between first and last play</div>';
    evergreen.forEach(function(x,i){
      h+='<div class="sd-bar-row"><span class="sd-bar-label">'+x.t.a.split(';')[0]+' — '+x.t.t+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+Math.round(x.span/12*100)+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+x.span+'y &middot; '+x.t.pc+'</span></div>';
    });
    h+='</div>';
  }
  /* Most Skipped (added, snapshot) */
  h+='<div class="sd-section"><h3>Most Skipped</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">The ones you skip every time. Honesty hurts.</div>';
  skipList.forEach(function(s,i){var pct=Math.round(s[2]/skipMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+s[0]+' — '+s[1]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+s[2]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-liststats-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
