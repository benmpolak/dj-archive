#!/usr/bin/env python3
"""When the archive is filtered to an artist (clicking an artist name),
show a 'More like X' strip above the results that opens Dig Deeper.
Fixes discoverability: Dig Deeper existed but was buried."""
import os, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

OLD_FBA = "function filterByArtist(n){q('#search').value=n;F.search=n.toLowerCase();applyFilters();closeSimilar();closeDig()}"
NEW_FBA = """function filterByArtist(n){q('#search').value=n;F.search=n.toLowerCase();applyFilters();closeSimilar();closeDig();showSimilarCta(n)}
function showSimilarCta(n){
  var el=document.getElementById('similar-cta');
  if(!el){
    el=document.createElement('div');el.id='similar-cta';
    var tb=document.getElementById('tbody');var tbl=tb?tb.closest('table'):null;
    if(!tbl||!tbl.parentNode)return;
    tbl.parentNode.insertBefore(el,tbl);
  }
  el.dataset.artist=n;
  var base=n.split(';')[0].trim();
  el.innerHTML='<span class="sc-go" data-artist="'+esc(n)+'">\\u25c6 More like '+esc(base)+' \\u2014 surface similar artists from your archive</span>';
  el.style.cssText='margin:8px 0;padding:9px 13px;border:1px solid var(--border);border-radius:10px;background:var(--card2);font-size:0.85em;color:var(--accent2);display:block;cursor:pointer';
  el.onclick=function(){digDeeper(el.dataset.artist)};
  el.style.display='block';
}"""
assert OLD_FBA in html, 'filterByArtist anchor missing'
html = html.replace(OLD_FBA, NEW_FBA, 1)

# hide the strip when the search no longer matches that artist
OLD_AF = "page=0;q('#tbody').innerHTML=rows(filtered.slice(0,PAGE_SZ),0);stats();pushState();"
NEW_AF = OLD_AF + "var _sc=document.getElementById('similar-cta');if(_sc&&(!F.search||F.search!==(_sc.dataset.artist||'').toLowerCase()))_sc.style.display='none';"
assert OLD_AF in html, 'applyFilters anchor missing'
html = html.replace(OLD_AF, NEW_AF, 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-simcta-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('similar-artists strip wired into artist view')
