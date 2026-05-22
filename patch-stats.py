#!/usr/bin/env python3
"""Add taste-drift + genre-by-year to the stats dashboard, and de-spike the add timeline."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor found {n}x (expected 1): {old[:60]!r}"
    return s.replace(old, new)

# 1) De-spike the existing "When You Added It" year chart: drop the two bulk-import
#    months (Jan 2010 = 2844 migration, Feb 2019 = 530 Deep Dive batch).
html = replace_once(html,
  "DATA.forEach(function(t){if(t.da&&t.da>=201001){var y=Math.floor(t.da/100);yearAdded[y]=(yearAdded[y]||0)+1}});",
  "DATA.forEach(function(t){if(t.da&&t.da>201001&&t.da!=201902){var y=Math.floor(t.da/100);yearAdded[y]=(yearAdded[y]||0)+1}});")

# 2) Insert taste-drift + genre-evolution computation right before the HTML assembly.
COMPUTE = r"""/* --- Taste drift + genre-by-year (added) --- */
  var DEEPDIVE=201902;
  var driftData={};var driftYears=[];
  DATA.forEach(function(t){
    if(t.da&&t.da>=201601&&t.da!=DEEPDIVE){
      var y=Math.floor(t.da/100);
      if(!driftData[y]){driftData[y]={n:0,e:0,d:0,v:0,tp:0,ins:0};driftYears.push(y);}
      var o=driftData[y];o.n++;o.e+=(+t.e||0);o.d+=(+t.d||0);o.v+=(+t.v||0);o.tp+=(+t.tp||0);o.ins+=(+t.ins||0);
    }
  });
  driftYears.sort(function(a,b){return a-b});
  driftYears.forEach(function(y){var o=driftData[y];o.e/=o.n;o.d/=o.n;o.v/=o.n;o.tp/=o.n;o.ins/=o.n;});
  var maxBPM=driftYears.reduce(function(m,y){return Math.max(m,driftData[y].tp)},1);
  var dFirst=driftYears.length?driftData[driftYears[0]]:null;
  var dLast=driftYears.length?driftData[driftYears[driftYears.length-1]]:null;
  var genreYear={};
  DATA.forEach(function(t){
    if(t.da&&t.da>=201601&&t.da!=DEEPDIVE&&t.g){
      var y=Math.floor(t.da/100);
      if(!genreYear[y])genreYear[y]={};
      t.g.split(',').forEach(function(g){var gk=g.trim().toLowerCase();if(gk)genreYear[y][gk]=(genreYear[y][gk]||0)+1;});
    }
  });
  var genreYearTop=Object.keys(genreYear).map(Number).sort(function(a,b){return a-b}).map(function(y){
    var top=Object.entries(genreYear[y]).sort(function(a,b){return b[1]-a[1]})[0];
    return [y, top?top[0]:'—'];
  });
  var h='<span class="sd-close" onclick="closeStatsDash()">"""
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

# 3) Insert the two new render sections right before the Vinyl Collection section.
RENDER = r"""/* Taste Drift section (added) */
  h+='<div class="sd-section"><h3>How Your Taste Drifted</h3>';
  if(dFirst&&dLast){
    h+='<div style="font-size:0.85em;line-height:1.5;color:var(--text);margin-bottom:12px">';
    h+='<p>Your picks moved from <b style="color:var(--accent)">'+Math.round(dFirst.tp)+' BPM</b> in '+driftYears[0]+' to <b style="color:var(--accent)">'+Math.round(dLast.tp)+' BPM</b> in '+driftYears[driftYears.length-1]+', while instrumentalness climbed from <b style="color:var(--accent2)">'+dFirst.ins.toFixed(2)+'</b> to <b style="color:var(--accent2)">'+dLast.ins.toFixed(2)+'</b> &mdash; slower, deeper, more instrumental over time.</p>';
    h+='</div>';
  }
  h+='<h4 style="margin-top:8px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">Tempo (avg BPM)</h4>';
  driftYears.forEach(function(y,i){var o=driftData[y];var pct=Math.round(o.tp/maxBPM*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+y+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+Math.round(o.tp)+'</span></div>';
  });
  h+='<h4 style="margin-top:14px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">Energy (avg)</h4>';
  driftYears.forEach(function(y,i){var o=driftData[y];var pct=Math.round(o.e*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+y+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+o.e.toFixed(2)+'</span></div>';
  });
  h+='<h4 style="margin-top:14px;margin-bottom:6px;font-size:0.8em;color:var(--dim)">Instrumental (avg)</h4>';
  driftYears.forEach(function(y,i){var o=driftData[y];var pct=Math.round(o.ins*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+y+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+o.ins.toFixed(2)+'</span></div>';
  });
  h+='</div>';
  /* Genre by Year section (added) */
  h+='<div class="sd-section"><h3>Genre by Year</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Top genre you added each year</div>';
  genreYearTop.forEach(function(pair){
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+pair[0]+'</span><span style="flex:1;color:var(--text);font-size:0.85em;text-transform:capitalize">'+pair[1]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

# also relabel the de-spiked timeline so the exclusion is honest
html = replace_once(html, "<h3>When You Added It</h3>",
  "<h3>When You Added It</h3><div style=\\'font-size:0.72em;color:var(--dim);margin:-4px 0 8px\\'>Excludes two bulk back-catalogue imports (2010, Feb 2019)</div>")

bak = os.path.join(HERE, f"_backup-pre-stats-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE, 'w').write(html)
print("patched. backup:", os.path.basename(bak))
