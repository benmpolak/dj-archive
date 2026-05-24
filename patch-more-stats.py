#!/usr/bin/env python3
"""Add 3 snapshot panels: Artist of the Year, Your Range (distinct tracks/artists per
year), Listening by Season. Data baked from the streaming history (kids excluded)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

aoty = [
 ["2012","The xx (94) · Stevie Wonder (80) · Tame Impala (80)"],
 ["2013","CHIC (150) · Daft Punk (133) · Fat Freddy's Drop (113)"],
 ["2014","Real Estate (153) · Marvin Gaye (122) · Sonzeira (86)"],
 ["2015","Tame Impala (140) · Marvin Gaye (126) · Kendrick Lamar (97)"],
 ["2016","Radiohead (257) · Anderson .Paak (243) · The Avalanches (139)"],
 ["2017","The National (160) · Erykah Badu (148) · Phoenix (132)"],
 ["2018","Arctic Monkeys (121) · Kamasi Washington (87) · Leroy Hutson (80)"],
 ["2019","Ashley Henry (145) · Anderson .Paak (135) · SAULT (127)"],
 ["2020","SAULT (192) · Doves (158) · The Orielles (112)"],
 ["2021","Emma-Jean Thackray (95) · Lewis Taylor (72) · Secret Night Gang (71)"],
 ["2022","Yaya Bey (99) · Kendrick Lamar (95) · SAULT (85)"],
 ["2023","Yazmin Lacey (126) · JIM (100) · Greg Foat (98)"],
 ["2024","Greg Foat (159) · Jessica Pratt (65) · Ashley Henry (60)"],
 ["2025","Radiohead (127) · Chaos In The CBD (108) · Kendrick Lamar (104)"],
 ["2026","Maston (56) · Fabiano do Nascimento (53)  · so far"],
]
rangeY = [["2012",1564,799],["2013",3168,1357],["2014",2621,1142],["2015",2423,1123],
 ["2016",3119,1457],["2017",2924,1446],["2018",2986,1406],["2019",3262,1473],
 ["2020",3768,1717],["2021",2667,1460],["2022",2589,1344],["2023",2706,1403],
 ["2024",2984,1444],["2025",3300,1609],["2026",1651,955]]
seasonM = [["Jan",7083],["Feb",7283],["Mar",8013],["Apr",7880],["May",8159],["Jun",7308],
 ["Jul",7738],["Aug",7589],["Sep",7228],["Oct",8055],["Nov",7860],["Dec",8271]]

COMPUTE = ("/* --- More stats (added, snapshot) --- */\n"
  "  var aoty=" + json.dumps(aoty, ensure_ascii=False) + ";\n"
  "  var rangeY=" + json.dumps(rangeY) + ";\n"
  "  var rangeMax=Math.max.apply(null,rangeY.map(function(x){return x[1]}));\n"
  "  var seasonM=" + json.dumps(seasonM) + ";\n"
  "  var seasonMax=Math.max.apply(null,seasonM.map(function(x){return x[1]}));\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* Artist of the Year (added, snapshot) */
  h+='<div class="sd-section"><h3>Artist of the Year</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">Your most-played artist each year &middot; from your listening history</div>';
  aoty.slice().reverse().forEach(function(p){
    h+='<div class="sd-bar-row"><span class="sd-bar-label" style="color:var(--accent)">'+p[0]+'</span><span style="flex:1;color:var(--text);font-size:0.82em">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Your Range (added, snapshot) */
  h+='<div class="sd-section"><h3>Your Range</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Different tracks you played each year &middot; 31,605 distinct tracks / 9,501 artists all-time</div>';
  rangeY.forEach(function(p,i){var pct=Math.round(p[1]/rangeMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Listening by Season (added, snapshot) */
  h+='<div class="sd-section"><h3>Listening by Season</h3>';
  h+='<div style="font-size:0.8em;color:var(--dim);margin-bottom:8px">Plays by month &middot; you listen evenly year-round (unlike your spring-heavy digging)</div>';
  seasonM.forEach(function(p,i){var pct=Math.round(p[1]/seasonMax*100);
    h+='<div class="sd-bar-row"><span class="sd-bar-label">'+p[0]+'</span><div class="sd-bar"><div class="sd-bar-fill" style="width:'+pct+'%;background:'+colors[i%colors.length]+'"></div></div><span class="sd-bar-count">'+p[1].toLocaleString()+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-morestats-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
