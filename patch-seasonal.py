#!/usr/bin/env python3
"""Seasonal Anthems: your #1 track for every season, 2012-2026 (a soundtrack to the chapters)."""
import os, shutil, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

def replace_once(s, old, new):
    n = s.count(old)
    assert n == 1, f"anchor {n}x (want 1): {old[:55]!r}"
    return s.replace(old, new)

# newest first
seasons = [
 ["Spring 2026","Everton FC — Spirit Of The Blues · 10x"],["Winter 2026","Cameron Winter — Love Takes Miles · 7x"],
 ["Autumn 2025","MARINI — Nightshade · 8x"],["Summer 2025","Bill Withers — Lovely Day (Studio Rio) · 11x"],
 ["Spring 2025","Doves — Last Year's Man · 11x"],["Winter 2025","Kendrick Lamar — heart pt. 6 · 22x"],
 ["Autumn 2024","Rosie Lowe — There Goes The Light · 9x"],["Summer 2024","Jessica Pratt — Get Your Head Out · 11x"],
 ["Spring 2024","Isaiah Collier — LOVE · 10x"],["Winter 2024","Everton FC — Spirit Of The Blues · 46x"],
 ["Autumn 2023","Greg Foat — Inconsequential Narrative · 9x"],["Summer 2023","Ana Frango Elétrico — Electric Fish · 10x"],
 ["Spring 2023","Rogê — Pra Vida · 19x"],["Winter 2023","Matthew Halsall — Positive Activity · 13x"],
 ["Autumn 2022","The Orielles — The Instrument · 9x"],["Summer 2022","Yard Act — 100% Endurance · 15x"],
 ["Spring 2022","Los Hermanos — Another Day · 10x"],["Winter 2022","Soichi Terada — Silent Chord · 8x"],
 ["Autumn 2021","Eddie Chacon — Hurt · 10x"],["Summer 2021","Overmono — So U Kno · 12x"],
 ["Spring 2021","Emma-Jean Thackray — Say Something · 23x"],["Winter 2021","SAULT — Free · 8x"],
 ["Autumn 2020","SAULT — Fear · 15x"],["Summer 2020","John Rocca — Southern Freeez 20+20 · 11x"],
 ["Spring 2020","Malcolm Strachan — Take Me to the Clouds · 12x"],["Winter 2020","Ed O'Brien — Brasil · 15x"],
 ["Autumn 2019","CRAC — You're Everything to Me · 14x"],["Summer 2019","Liquideep — Angel (DJ Spen mix) · 15x"],
 ["Spring 2019","EKO — M'ongeule M'am · 13x"],["Winter 2019","Kokoroko — Uman · 14x"],
 ["Autumn 2018","Evelyn \"Champagne\" King — I Don't Know If It's Right · 15x"],["Summer 2018","Benita — Time for a Change · 12x"],
 ["Spring 2018","Arctic Monkeys — Star Treatment · 13x"],["Winter 2018","Red Astaire — Reaching out to You · 13x"],
 ["Autumn 2017","Jamila Woods — LSD · 14x"],["Summer 2017","Phoenix — Fior Di Latte · 12x"],
 ["Spring 2017","Jens Lekman — How We Met · 15x"],["Winter 2017","Thundercat — Show You The Way · 14x"],
 ["Autumn 2016","Hamilton Leithauser + Rostam — A 1000 Times · 11x"],["Summer 2016","The Avalanches — Because I'm Me · 18x"],
 ["Spring 2016","Afriquoi — Kudaushe · 14x"],["Winter 2016","Anderson .Paak — Put Me Thru · 17x"],
 ["Autumn 2015","Dam Swindle — You, Me, Here, Now · 12x"],["Summer 2015","Hiatus Kaiyote — Fingerprints · 10x"],
 ["Spring 2015","Noel Gallagher's HFB — The Right Stuff · 16x"],["Winter 2015","Future Islands — Seasons (Waiting On You) · 30x"],
 ["Autumn 2014","Marvin Gaye — Time To Get It Together · 14x"],["Summer 2014","George Ezra — Cassy O' · 9x"],
 ["Spring 2014","Real Estate — Crime · 13x"],["Winter 2014","Blood Orange — Chosen · 13x"],
 ["Autumn 2013","Milton Nascimento — Tudo O Que Você Podia Ser · 10x"],["Summer 2013","Evergreen — Baby Blue · 18x"],
 ["Spring 2013","Daft Punk — Get Lucky · 20x"],["Winter 2013","Mos Def — Ms. Fat Booty · 10x"],
 ["Autumn 2012","Theme Park — Jamaica · 16x"],["Summer 2012","Trio Mocoto — Voltei Amor · 11x"],
]

COMPUTE = ("/* --- Seasonal anthems (added) --- */\n"
  "  var seasons=" + json.dumps(seasons, ensure_ascii=False) + ";\n"
  "  var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">")
html = replace_once(html, "var h='<span class=\"sd-close\" onclick=\"closeStatsDash()\">", COMPUTE)

RENDER = r"""/* Seasonal Anthems (added, listening) */
  h+='<div class="sd-section" data-tab="listening"><h3>Seasonal Anthems</h3>';
  h+='<div style="font-size:0.72em;color:var(--dim);margin:-4px 0 8px">Your most-played track every season since 2012 — the soundtrack to each chapter</div>';
  seasons.forEach(function(p){
    var win=p[0].indexOf('Winter')===0;
    h+='<div class="sd-bar-row"><span class="sd-bar-label" style="color:'+(win?'var(--accent2)':'var(--accent)')+'">'+p[0]+'</span><span style="flex:1;color:var(--text);font-size:0.8em">'+p[1]+'</span></div>';
  });
  h+='</div>';
  /* Vinyl Collection section */"""
html = replace_once(html, "/* Vinyl Collection section */", RENDER)

bak = os.path.join(HERE, f"_backup-pre-seasonal-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print("patched. backup:", os.path.basename(bak))
