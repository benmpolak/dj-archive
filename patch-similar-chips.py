#!/usr/bin/env python3
"""Better-presented similar artists: the strip now renders the top similar
artists as clickable chips inline (chain-digging), with a 'full dig' link
to the existing panel. Refactors digDeeper into _digCompute + display."""
import os, re, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

# 1) split digDeeper into compute + display
assert html.count('function digDeeper(name){') == 1
html = html.replace('function digDeeper(name){', 'function _digCompute(name){', 1)

OLD_TAIL = """  const topGenres=Object.keys(gFreq).sort((a,b)=>gFreq[b]-gFreq[a]).slice(0,4).join(', ')||'various';
  q('#dig-artist-name').textContent=exactName;"""
NEW_TAIL = """  const topGenres=Object.keys(gFreq).sort((a,b)=>gFreq[b]-gFreq[a]).slice(0,4).join(', ')||'various';
  return {exactName:exactName,picks:picks,at:at,topGenres:topGenres};
}
function digDeeper(name){
  var R=_digCompute(name);if(!R)return;
  var exactName=R.exactName,picks=R.picks,at=R.at,topGenres=R.topGenres;
  q('#dig-artist-name').textContent=exactName;"""
assert OLD_TAIL in html
html = html.replace(OLD_TAIL, NEW_TAIL, 1)

# 2) rewrite the strip: inline artist chips
start = html.index('function showSimilarCta(n){')
end_anchor = '\n\nfunction renderSet(){'
end = html.index(end_anchor, start)
NEW_CTA = """function showSimilarCta(n){
  var el=document.getElementById('similar-cta');
  if(!el){
    el=document.createElement('div');el.id='similar-cta';
    var tb=document.getElementById('tbody');var tbl=tb?tb.closest('table'):null;
    if(!tbl||!tbl.parentNode)return;
    tbl.parentNode.insertBefore(el,tbl);
  }
  if(el.dataset.artist!==n||!el.innerHTML){
    el.dataset.artist=n;
    var base=n.split(';')[0].trim();
    var R=_digCompute(n);
    if(!R||!R.picks||!R.picks.length){el.style.display='none';return}
    var seen={},chips='';
    for(var ci=0;ci<R.picks.length&&Object.keys(seen).length<8;ci++){
      var pa=R.picks[ci].a,pb=pa.split(';')[0].trim();
      if(seen[pb.toLowerCase()])continue;seen[pb.toLowerCase()]=1;
      chips+='<span class="sc-chip" data-artist="'+esc(pa)+'" style="display:inline-block;padding:4px 11px;margin:3px 5px 3px 0;border:1px solid var(--border);border-radius:14px;background:var(--card);color:var(--text);font-size:0.95em;cursor:pointer;white-space:nowrap">'+esc(pb)+'</span>';
    }
    el.innerHTML='<div style="font-size:0.68em;color:var(--dim);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:5px">More like '+esc(base)+' <span style="color:var(--border)">&middot;</span> from your archive</div><div>'+chips+'<span class="sc-chip sc-dig" data-artist="'+esc(n)+'" style="display:inline-block;padding:4px 11px;margin:3px 0;border-radius:14px;background:transparent;color:var(--accent2);font-size:0.95em;cursor:pointer;white-space:nowrap">full dig &rarr;</span></div>';
    el.style.cssText='margin:8px 0;padding:10px 13px;border:1px solid var(--border);border-radius:10px;background:var(--card2);font-size:0.85em;display:block';
    el.onclick=function(ev){var c=ev.target.closest('.sc-chip');if(!c)return;if(c.classList.contains('sc-dig')){digDeeper(c.dataset.artist)}else{showSimilar(c.dataset.artist)}};
  }
  el.style.display='block';
}"""
html = html[:start] + NEW_CTA + html[end:]

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-simchips-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE, 'w').write(html)
print('similar-artists strip now renders inline chips')
