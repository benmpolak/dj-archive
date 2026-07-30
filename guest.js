/* Guest layer — focused landing with The Selector as hero, plus owner mode.
   Source of truth: guest.js, injected by patch-guest.py as <script id="guest-js">.
   Owner mode: visit ?owner once (persists in localStorage); ?guest to switch back.
   Guests land on a decluttered view (body.guest-focus): Selector hero, two quiet
   secondary routes, NEW IN + ON REPEAT shelves, and an "Explore the full archive"
   reveal. Owners see the normal site. Styling lives in design-pass.css.
   NB: query params not hashes — the router strips unknown hashes before bottom
   scripts parse (same lesson as gigs find-route). */
(function(){
  function isOwner(){try{return localStorage.getItem('dj_owner')==='1'}catch(e){return true}}
  function setOwner(on){try{on?localStorage.setItem('dj_owner','1'):localStorage.removeItem('dj_owner')}catch(e){}}

  /* ?owner / ?guest switches */
  var params=new URLSearchParams(location.search);
  if(params.has('owner')){setOwner(true);history.replaceState(null,'',location.pathname+location.hash)}
  else if(params.has('guest')){setOwner(false);history.replaceState(null,'',location.pathname+location.hash)}
  if(isOwner())document.body.classList.add('owner');

  /* Retire the old #intro tour modal for guests and first visits alike */
  try{localStorage.setItem('dj-archive-seen','1')}catch(e){}
  var oi=document.getElementById('intro');if(oi)oi.style.display='none';

  /* Gate the quick-tag editor (pencil + right-click) behind owner mode */
  var _oqt=window.openQuickTag;
  if(_oqt)window.openQuickTag=function(){if(isOwner())return _oqt.apply(this,arguments)};

  if(isOwner())return;   /* owners get the normal site — everything below is guest-only */

  /* ---------- helpers ---------- */
  function E(s){return (typeof esc==='function')?esc(s):String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function primary(a){return (a||'').split(';')[0].trim()}
  function fmtDa(da){if(!da)return'';var mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return mn[(da%100)-1]+' ’'+String(Math.floor(da/100)).slice(2)}
  function crateColor(t){var c=(t.c||[])[0];return (window.CC&&CC[c])||'#e8a040'}

  /* ---------- shelf data: group records (artist+album) from baked fields ---------- */
  function groupRecords(){
    var groups={};
    DATA.forEach(function(t,i){
      var k=(primary(t.a)+'|'+(t.al||'')).toLowerCase();
      var g=groups[k]||(groups[k]={tracks:[],da:0,idx:0,p1:0,vy:0});
      g.tracks.push(t);
      if((t.da||0)>g.da)g.da=t.da;
      if(i>g.idx)g.idx=i;
      g.p1+=(t.p1||0);
      if(t.vy)g.vy=1;
    });
    return Object.keys(groups).map(function(k){return groups[k]});
  }
  function rep(g,scoreFn){
    var best=null,bs=-1;
    g.tracks.forEach(function(t){
      var s=(scoreFn?scoreFn(t):0)+((t.sid||'').length===22?1000:0);
      if(s>bs){bs=s;best=t}
    });
    return best;
  }
  function playAttr(t){
    if((t.sid||'').length===22)return 'onclick="playPreview(\''+t.sid+'\',this)"';
    var q=encodeURIComponent(primary(t.a)+' '+t.t);
    return 'onclick="window.open(\'https://open.spotify.com/search/'+q+'\',\'_blank\')"';
  }
  function card(g,meta){
    var t=rep(g,function(t){return t.p1||0});
    return '<div class="gh-card">'
      +'<div class="gh-card-art" style="background:linear-gradient(150deg,'+crateColor(t)+'33,'+crateColor(t)+'0d 70%)">'
      +'<span class="gh-card-play" '+playAttr(t)+' title="Play">▶</span>'
      +(g.vy?'<span class="gh-card-vinyl">VINYL</span>':'')
      +'</div>'
      +'<div class="gh-card-a">'+E(primary(t.a))+'</div>'
      +'<div class="gh-card-al">'+E(t.al||t.t)+'</div>'
      +'<div class="gh-card-meta">'+meta(g,t)+'</div>'
      +'</div>';
  }
  function newInShelf(){
    var gs=groupRecords().filter(function(g){return g.da});
    gs.sort(function(a,b){return (b.da-a.da)||(b.idx-a.idx)});
    return gs.slice(0,10).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'archived '+fmtDa(g.da)});
    }).join('');
  }
  function onRepeatShelf(){
    var gs=groupRecords().filter(function(g){return g.p1>=3});
    gs.sort(function(a,b){return b.p1-a.p1});
    return gs.slice(0,10).map(function(g){
      return card(g,function(g,t){return g.p1+' plays · last 12 months'});
    }).join('');
  }
  function playCutoff(){
    var mx=0;DATA.forEach(function(t){if((t.lp||0)>mx)mx=t.lp});
    if(!mx)return'';
    var mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return mn[(mx%100)-1]+' '+Math.floor(mx/100);
  }

  /* ---------- hero actions ---------- */
  function runSelector(text){
    if(!text.trim()){document.getElementById('gh-input').focus();return}
    if(!window.openDealer)return;
    openDealer();
    var inp=document.getElementById('dlr-input');
    /* dealer's internals are IIFE-scoped — drive it through its own Enter handler */
    if(inp){inp.value=text;inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))}
  }
  window._ghExplore=function(){
    /* return the dig + rediscover panels to their normal spot before the table */
    var main=document.querySelector('.main-area'),tw=document.getElementById('table-wrap');
    if(main&&tw)['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)main.insertBefore(p,tw)});
    document.body.classList.remove('guest-focus');
    var h=document.getElementById('guest-hero');if(h)h.style.display='none';
    window.scrollTo(0,0);
  };

  /* ---------- build ---------- */
  var CHIPS=['Brazilian sunshine','Late-night jazz','90s deep house','70s funk','Dub session','Like Marcos Valle','Jazz on vinyl'];
  function buildHero(){
    var main=document.querySelector('.main-area');if(!main)return;
    var cutoff=playCutoff();
    var el=document.createElement('div');
    el.id='guest-hero';
    el.innerHTML=
      '<div class="gh-brand">The DJ Archive</div>'
      +'<div class="gh-prop">Tell Ben’s shelves what you fancy.</div>'
      +'<div class="gh-inputrow"><input id="gh-input" placeholder="Brazilian sunshine, late-night jazz, like Marcos Valle…" autocomplete="off"><button id="gh-select">SELECT</button></div>'
      +'<div class="gh-chips">'+CHIPS.map(function(c){return '<span class="gh-chip" data-q="'+E(c)+'">'+E(c)+'</span>'}).join('')+'</div>'
      +'<div class="gh-sub">The Selector deals 25 tracks from one human-curated archive — 17,000+ records dug by ear over 14 years: bankers, forgotten loves and a couple of wild cards. Sequenced, not shuffled. No algorithm.</div>'
      +'<div class="gh-secondary">'
      +'<button class="gh-2nd" id="gh-artist-btn">🔭 Start with an artist</button>'
      +'<button class="gh-2nd" id="gh-surprise-btn">🔮 Surprise me</button>'
      +'</div>'
      +'<div class="gh-artistrow" id="gh-artist-row" style="display:none"><input id="gh-artist-input" placeholder="Type an artist — Marcos Valle, Roy Ayers, Theo Parrish…" autocomplete="off"><button id="gh-artist-go">Dig</button></div>'
      +'<div id="gh-panels"></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">New in</div><div class="gh-bin">'+newInShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">On repeat'
      +(cutoff?'<span class="gh-shelf-note">listening data through '+cutoff+'</span>':'')
      +'</div><div class="gh-bin">'+onRepeatShelf()+'</div></div>'
      +'<button class="gh-explore" onclick="_ghExplore()">Explore the full archive ↓</button>';
    main.insertBefore(el,main.firstChild);
    document.body.classList.add('guest-focus');
    /* pull the dig + rediscover panels up into the hero so they open in view;
       _ghExplore puts them back in front of the table */
    var ghp=document.getElementById('gh-panels');
    ['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)ghp.appendChild(p)});

    var inp=document.getElementById('gh-input');
    document.getElementById('gh-select').onclick=function(){runSelector(inp.value)};
    inp.addEventListener('keydown',function(e){if(e.key==='Enter')runSelector(inp.value)});
    el.querySelectorAll('.gh-chip').forEach(function(ch){
      ch.onclick=function(){inp.value=ch.dataset.q;runSelector(ch.dataset.q)};
    });
    document.getElementById('gh-surprise-btn').onclick=function(){if(window.showRediscover)showRediscover()};
    var arow=document.getElementById('gh-artist-row'),ainp=document.getElementById('gh-artist-input');
    document.getElementById('gh-artist-btn').onclick=function(){
      arow.style.display=arow.style.display==='none'?'flex':'none';
      if(arow.style.display==='flex')ainp.focus();
    };
    function dig(){var v=ainp.value.trim();if(v&&window.digDeeper)digDeeper(v)}
    document.getElementById('gh-artist-go').onclick=dig;
    ainp.addEventListener('keydown',function(e){if(e.key==='Enter')dig()});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',buildHero);
  else buildHero();
})();
