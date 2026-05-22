#!/usr/bin/env python3
"""Make the Stats button prominent + add depth sections (Signature Artists, By Crate,
Mood Map, Deeper Cuts flavour). All computed live from DATA."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor found {n}x (expected 1): {old[:50]!r}"
    return s.replace(old, new)

# 1) Prominent Stats button — add a hero style after the .cc-quick-btn:hover rule.
html = replace_once(html,
  ".cc-quick-btn:hover{border-color:var(--accent);color:var(--text)}",
  ".cc-quick-btn:hover{border-color:var(--accent);color:var(--text)}"
  ".cc-quick-btn.stats-hero{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#0a0a0f;border:none;font-weight:700;padding:5px 16px;box-shadow:0 2px 10px rgba(232,160,64,0.35)}"
  ".cc-quick-btn.stats-hero:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(232,160,64,0.55);color:#0a0a0f}")

# 2) Give the button the hero class.
html = replace_once(html,
  '<button class="cc-quick-btn" onclick="openStatsDash()">📊 Stats</button>',
  '<button class="cc-quick-btn stats-hero" onclick="openStatsDash()">📊 Stats</button>')

# 3) Depth computation (reuses artistCounts/genreCounts/total from earlier in the fn).
COMPUTE = r"""/* --- Depth stats (added) --- */
  var topArtists=Object.entries(artistCounts).sort(function(a,b){return b[1]-a[1]}).slice(0,12);
  var maxArtist=topArtists.length?topArtists[0][1]:1;
  var vibeCounts={};DATA.forEach(function(t){var vv=(t.vb||'').trim();if(vv)vibeCounts[vv]=(vibeCounts[vv]||0)+1;});
  var vibePairs=Object.entries(vibeCounts).sort(function(a,b){return b[1]-a[1]});
  var maxVibe=vibePairs.length?vibePairs[0][1]:1;
  var crateCounts={};DATA.forEach(function(t){(t.c||[]).forEach(function(cc){if(cc!=='Uncategorized'&&cc!=='Uncategorised')crateCounts[cc]=(crateCounts[cc]||0)+1;});});
  var cratePairs=Object.entries(crateCounts).sort(function(a,b){return b[1]-a[1]});
  var maxCrate=cratePairs.length?cratePairs[0][1]:1;
  var distinctGenres=Object.keys(genreCounts).length;
  var deepCuts=DATA.filter(function(t){var p=+t.p||0;return p>0&&p<20;}).length;
  var deepPct=Math.round(deepCuts/total*100);
  var oldest=DATA.reduce(function(m,t){var y=+t.r||0;return (y>1900&&(!m||y<m.r))?{r:y,a:t.a,t:t.t}:m;},null);
  var gaps=[];DATA.forEach(function(t){var r=+t.r||0;var y=t.da?Math.floor(t.da/100):0;if(r>1900&&y>2000&&y>=r)gaps.push(y-r);});
  gaps.sort(function(a,b){return a-b});var medGap=gaps.length?gaps[Math.floor(gaps.length/2)]:0;
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

# 4) Depth render sections (before the Vinyl Collection section).
RENDER = r"""/* Signature Artists section (added) */
  h+='<div class="sd-section"><h3>Signature Artists</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Most-collected across the archive</div>';
  topArtists.forEach(function(p,i){var pct=Math.round(p[1]/maxArtist*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* By Crate section (added) */
  h+='<div class="sd-section"><h3>By Crate</h3>';
  cratePairs.forEach(function(p,i){var pct=Math.round(p[1]/maxCrate*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Mood Map section (added) */
  h+='<div class="sd-section"><h3>Mood Map</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Your collection by vibe</div>';
  vibePairs.forEach(function(p,i){var pct=Math.round(p[1]/maxVibe*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Deeper Cuts flavour (added) */
  h+='<div class="sd-section"><h3>Deeper Cuts</h3>';
  h+='<div style="display:flex;flex-direction:column;gap:10px;font-size:0.85em;line-height:1.5;color:var(--text)">';
  h+='<p>You span <b style="color:var(--accent2)">'+distinctGenres.toLocaleString()+'</b> distinct genres.</p>';
  h+='<p><b style="color:var(--accent)">'+deepPct+'%</b> of your picks are deep cuts &mdash; Spotify popularity under 20. You back the underdogs.</p>';
  if(oldest)h+='<p>Your oldest track: <b style="color:var(--accent)">'+oldest.a+' &mdash; '+oldest.t+'</b> ('+oldest.r+').</p>';
  h+='<p>Typical gap from a track being released to you adding it: <b style="color:var(--accent2)">'+medGap+' year'+(medGap===1?'':'s')+'</b>.</p>';
  h+='</div></div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-depth-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE, 'w').write(html)
print("patched. backup:", os.path.basename(bak))
