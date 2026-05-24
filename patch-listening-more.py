#!/usr/bin/env python3
"""Three more Listening-tab panels: Hours Per Year, Track of the Year, Biggest Obsessions.
All archive-matched (kids/family excluded by construction)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

hoursYr = [["2012",128],["2013",258],["2014",249],["2015",232],["2016",262],["2017",258],
 ["2018",267],["2019",322],["2020",333],["2021",231],["2022",201],["2023",184],
 ["2024",174],["2025",180],["2026",62]]
trackYr = [
 ["2012","Wilson Simonal — Crioula · 17x"],["2013","Evergreen — Baby Blue · 22x"],
 ["2014","Future Islands — Seasons (Waiting On You) · 29x"],["2015","Hiatus Kaiyote — Fingerprints · 21x"],
 ["2016","Anderson .Paak — Put Me Thru · 27x"],["2017","Thundercat — Show You The Way · 18x"],
 ["2018","Kali Uchis — Tyrant · 20x"],["2019","Liquideep — Angel (DJ Spen mix) · 21x"],
 ["2020","Caserta — Luther (King Street Mix) · 17x"],["2021","Emma-Jean Thackray — Say Something · 24x"],
 ["2022","Yard Act — 100% Endurance · 17x"],["2023","Rogê — Pra Vida · 19x"],
 ["2024","Everton FC — Spirit Of The Blues · 43x"],["2025","Kendrick Lamar — luther (with sza) · 28x"],
 ["2026","Everton FC — Spirit Of The Blues · 13x so far"]]
obsess = [
 ["Dec '14","Future Islands — Seasons (Waiting On You) · 29x"],
 ["Jan '24","Everton FC — Spirit Of The Blues · 22x"],
 ["Dec '14","Spoon — Do You · 18x"],["Aug '13","Evergreen — Baby Blue · 18x"],
 ["Feb '20","Ed O'Brien — Brasil · 15x"],["Jul '16","The Avalanches — Because I'm Me · 15x"],
 ["Dec '14","Bonobo — Return to Air · 15x"],["Sep '12","Theme Park — Jamaica · 15x"],
 ["Jul '22","Yard Act — 100% Endurance · 14x"],["Aug '19","Theo Parrish — What You Gonna Ask For · 14x"]]

COMPUTE = ("/* --- Listening more (added) --- */\n"
  "  var hoursYr=" + json.dumps(hoursYr) + ";\n"
  "  var hoursMax=Math.max.apply(null,hoursYr.map(function(x){return x[1]}));\n"
  "  var trackYr=" + json.dumps(trackYr, ensure_ascii=False) + ";\n"
  "  var obsess=" + json.dumps(obsess, ensure_ascii=False) + ";\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* Hours Per Year (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>Hours Per Year</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Time on your own collection each year &middot; peaked in the 2020 lockdown</div>';
  hoursYr.forEach(function(p,i){var pct=Math.round(p[1]/hoursMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1]+'h</span></div>';
  });
  h+='</div>';
  /* Track of the Year (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>Track of the Year</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">Your single most-played track each year (your crates only)</div>';
  trackYr.slice().reverse().forEach(function(p){
    h+='<div class="sd-bar-row"><span class="sd-bar-label" style="color:var(--accent)">'+p[0]+'</span><span style="flex:1;color:var(--text);font-size:0.82em">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Biggest Obsessions (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>Biggest Obsessions</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">Most you played one track in a single month</div>';
  obsess.forEach(function(p){
    h+='<div class="sd-bar-row"><span class="sd-bar-label" style="color:var(--accent2)">'+p[0]+'</span><span style="flex:1;color:var(--text);font-size:0.82em">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-listmore-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
