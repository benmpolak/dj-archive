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
      var k=(primary(t.a)+'|'+(t.al||'').trim()).toLowerCase();
      var g=groups[k]||(groups[k]={tracks:[],da:0,idx:0,p1:0,pc:0,vy:0});
      g.tracks.push(t);
      if((t.da||0)>g.da)g.da=t.da;
      if(i>g.idx)g.idx=i;
      g.p1+=(t.p1||0);
      g.pc+=(t.pc||0);
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
    /* not on Spotify (matcher-confirmed) — YouTube search, same as the table's red buttons */
    var q=encodeURIComponent(primary(t.a)+' '+t.t);
    return 'onclick="window.open(\'https://www.youtube.com/results?search_query='+q+'\',\'_blank\')"';
  }
  /* hand-tuned crops for covers whose subject drowns at card size (framed photos,
     minimal art) — zoom + position into the interesting region. Key: artist|album. */
  var ART_TWEAKS={
    'kendrick lamar|gnx':{s:'175%',p:'12% 96%'},              /* car + Kendrick, bottom-left */
    'lynda dawn|at first light':{s:'152%',p:'50% 42%'},       /* crop off the white frame */
    'lynda dawn|fonk street':{s:'152%',p:'50% 42%'}           /* same framed artwork */
  };
  function card(g,meta){
    var t=rep(g,function(t){return t.p1||0});
    var sid=(t.sid||'').length===22?t.sid:'';
    var cc=crateColor(t);
    var tw=ART_TWEAKS[(primary(t.a).split(',')[0].trim()+'|'+(t.al||'').trim()).toLowerCase()];
    var twCss=tw?';background-size:'+tw.s+';background-position:'+tw.p:'';
    return '<div class="gh-card">'
      +'<div class="gh-card-art"'+(sid?' data-art-sid="'+sid+'"':'')+' data-art-q="'+E(primary(t.a)+' '+(t.al||t.t))+'" style="background:linear-gradient(150deg,'+cc+'55,'+cc+'14 75%)'+twCss+'">'
      +'<span class="gh-card-albtxt">'+E(t.al||t.t)+'</span>'
      +'<span class="gh-card-play" '+playAttr(t)+' title="Play">▶</span>'
      +(g.vy?'<span class="gh-card-vinyl">VINYL</span>':'')
      +'</div>'
      +'<div class="gh-card-a">'+E(primary(t.a))+'</div>'
      +'<div class="gh-card-al">'+E(t.al||t.t)+'</div>'
      +'<div class="gh-card-meta">'+meta(g,t)+'</div>'
      +'</div>';
  }
  /* real sleeves: Spotify oEmbed first (CORS-open, no auth), iTunes Search as the
     fallback for records not on Spotify (JSONP — iTunes sends no CORS headers).
     The text-led card underneath stays when both miss. Discogs is a dead end:
     anonymous API responses carry no images. */
  var _artCache={};try{_artCache=JSON.parse(localStorage.getItem('gh_art_cache')||'{}')}catch(e){}
  var _artCacheT=null;
  function cacheArt(key,url){
    _artCache[key]=url;
    clearTimeout(_artCacheT);
    _artCacheT=setTimeout(function(){try{
      var keys=Object.keys(_artCache);
      if(keys.length>600)keys.slice(0,keys.length-600).forEach(function(k){delete _artCache[k]});
      localStorage.setItem('gh_art_cache',JSON.stringify(_artCache));
    }catch(e){}},400);
  }
  function setArt(el,url){el.style.backgroundImage='url("'+url+'")';el.classList.add('has-art')}
  function itunesArt(el){
    var q=el.dataset.artQ;if(!q)return;
    var cb='_itArt'+Math.floor(Math.random()*1e9);
    window[cb]=function(d){
      try{var r=d&&d.results&&d.results[0];
        if(r&&r.artworkUrl100){var u=r.artworkUrl100.replace('100x100bb','400x400bb');setArt(el,u);cacheArt(el.dataset.artSid||q,u)}
      }finally{delete window[cb]}
    };
    var s=document.createElement('script');
    s.src='https://itunes.apple.com/search?term='+encodeURIComponent(q)+'&entity=album&limit=1&callback='+cb;
    s.onerror=function(){delete window[cb]};
    document.head.appendChild(s);
  }
  function fetchArt(el){
    if(el.dataset.artDone)return Promise.resolve();el.dataset.artDone='1';
    var key=el.dataset.artSid||el.dataset.artQ;
    if(key&&_artCache[key]){setArt(el,_artCache[key]);return Promise.resolve()}
    if(el.dataset.artSid){
      return fetch('https://open.spotify.com/oembed?url=https://open.spotify.com/track/'+el.dataset.artSid)
        .then(function(r){return r.json()})
        .then(function(j){if(j&&j.thumbnail_url){setArt(el,j.thumbnail_url);cacheArt(key,j.thumbnail_url)}else itunesArt(el)})
        .catch(function(){itunesArt(el)});
    }
    itunesArt(el);return Promise.resolve();
  }
  /* ~200 cards across the racks: fetch sleeves in a polite queue, twelve at a time,
     until every card is done — an IntersectionObserver proved unreliable for cards
     deep inside the horizontal bins (cards silently never loaded). URLs cache in
     localStorage so repeat visits paint instantly. */
  function loadSleeves(root){
    var els=[].slice.call(root.querySelectorAll('.gh-card-art'));
    (function next(){
      if(!els.length)return;
      Promise.all(els.splice(0,12).map(fetchArt)).then(next,next);
    })();
  }
  /* shelves only show records with a real Spotify link — unmatched comps and
     white labels get corrupt links and wrong fallback art, so they stay off */
  function hasSpotify(g){return (rep(g,function(t){return t.p1||0}).sid||'').length===22}
  /* one card per artist per shelf — an artist's run of singles shouldn't take
     multiple slots (the Okonski rule); list must already be sorted best-first.
     Key on the first artist before ';' AND ',' — playlist imports join
     collaborators with commas ("Okonski, Cochemea" vs "Okonski, Rachel Kitchlew"). */
  function artistKey(g){
    return primary(rep(g,function(t){return t.p1||0}).a).split(',')[0].trim().toLowerCase();
  }
  function onePerArtist(gs){
    var seen={};
    return gs.filter(function(g){
      var a=artistKey(g);
      if(seen[a])return false;seen[a]=1;return true;
    });
  }
  /* rank by the ARTIST's pooled plays across everything of theirs in the rack —
     an artist whose plays are spread over several singles (Curió Curió) shouldn't
     sink below one-record artists. Their single card is still their best record. */
  function sortByArtistPlays(gs,playsOf){
    var totals={};
    gs.forEach(function(g){var k=artistKey(g);totals[k]=(totals[k]||0)+playsOf(g)});
    gs.sort(function(a,b){
      return (totals[artistKey(b)]-totals[artistKey(a)])||(playsOf(b)-playsOf(a))||(b.idx-a.idx);
    });
    return gs;
  }
  function newReleasesShelf(){
    /* brand-new MUSIC: this year's releases added in the last two months,
       ordered by how much Ben has actually played them.
       (Archive stores release year only, so "past 90 days" = this year's releases.) */
    var yr=new Date().getFullYear();
    var maxDa=0;DATA.forEach(function(t){if((t.da||0)>maxDa)maxDa=t.da});
    var prevDa=(maxDa%100)===1?(Math.floor(maxDa/100)-1)*100+12:maxDa-1;
    /* rank on the artist's plays across ALL their releases this year, not just the
       rack window — Curió Curió's played April singles should lift their July ones */
    var yearGs=groupRecords().filter(function(g){
      return !g.vy&&hasSpotify(g)&&g.tracks.some(function(t){return (parseInt(t.r)||0)>=yr});
    });
    var yearTotals={};
    yearGs.forEach(function(g){var k=artistKey(g);yearTotals[k]=(yearTotals[k]||0)+g.pc});
    var gs=yearGs.filter(function(g){return g.da>=prevDa});
    gs.sort(function(a,b){
      return (yearTotals[artistKey(b)]-yearTotals[artistKey(a)])||(b.pc-a.pc)||(b.idx-a.idx);
    });
    gs=onePerArtist(gs);
    return gs.slice(0,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'archived '+fmtDa(g.da)});
    }).join('');
  }
  function unearthedShelf(){
    /* the second-hand bin: OLDER records dug up this month — release year before
       this year, added in the current intake */
    var yr=new Date().getFullYear();
    var maxDa=0;DATA.forEach(function(t){if((t.da||0)>maxDa)maxDa=t.da});
    var gs=groupRecords().filter(function(g){
      return g.da===maxDa&&!g.vy&&hasSpotify(g)&&g.tracks.every(function(t){return (parseInt(t.r)||0)<yr});
    });
    sortByArtistPlays(gs,function(g){return g.pc});
    gs=onePerArtist(gs);
    return gs.slice(0,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'dug up '+fmtDa(g.da)});
    }).join('');
  }
  /* hand-curated shelf entries for records that live off-Spotify (Bandcamp etc.)
     — art + link maintained by hand, Ben's call per record */
  var VINYL_OVERRIDES=[
    {a:'The Illusions & Nathan Haines',al:'Find Your Way',r:2026,da:202607,
     art:'https://f4.bcbits.com/img/a3484678180_5.jpg',
     url:'https://theillusionsband.bandcamp.com/album/find-your-way',tag:'BANDCAMP'}
  ];
  function overrideCard(o){
    return '<div class="gh-card">'
      +'<div class="gh-card-art has-art" style="background-image:url(\''+o.art+'\')">'
      +'<span class="gh-card-play" onclick="window.open(\''+o.url+'\',\'_blank\')" title="Open on '+(o.tag||'Bandcamp')+'">▶</span>'
      +'<span class="gh-card-vinyl">'+(o.tag||'VINYL')+'</span>'
      +'</div>'
      +'<div class="gh-card-a">'+E(o.a)+'</div>'
      +'<div class="gh-card-al">'+E(o.al)+'</div>'
      +'<div class="gh-card-meta">'+o.r+' · added '+fmtDa(o.da)+'</div>'
      +'</div>';
  }
  function freshVinylShelf(){
    /* albums and EPs only (4+ tracks), bought THIS year — 45s make loose, one-song cards */
    var thisYr=new Date().getFullYear()*100+1;
    var gs=groupRecords().filter(function(g){return g.da>=thisYr&&g.vy&&hasSpotify(g)&&g.tracks.length>=4});
    gs.sort(function(a,b){return (b.da-a.da)||(b.idx-a.idx)});
    gs=onePerArtist(gs);
    var ov=VINYL_OVERRIDES.map(overrideCard).join('');
    return ov+gs.slice(0,25-VINYL_OVERRIDES.length).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'added '+fmtDa(g.da)});
    }).join('');
  }
  function onRepeatShelf(){
    var gs=groupRecords().filter(function(g){return g.p1>=3&&hasSpotify(g)});
    gs.sort(function(a,b){return b.p1-a.p1});
    gs=onePerArtist(gs);
    return gs.slice(0,50).map(function(g){
      return card(g,function(g,t){return t.r||''});
    }).join('');
  }
  function prevYearShelf(){
    /* p2-p1 = plays in the year before the current 12-month window */
    var gs=groupRecords();
    gs.forEach(function(g){g.pPrev=0;g.tracks.forEach(function(t){g.pPrev+=Math.max((t.p2||0)-(t.p1||0),0)})});
    gs=gs.filter(function(g){return g.pPrev>=3&&hasSpotify(g)});
    gs.sort(function(a,b){return b.pPrev-a.pPrev});
    gs=onePerArtist(gs);
    return gs.slice(0,50).map(function(g){
      return card(g,function(g,t){return t.r||''});
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
      +'<div class="gh-sub">The Selector pulls 25 tracks from one human-curated archive — 17,000+ records dug by ear over 14 years: bankers, forgotten loves and a couple of wild cards. Sequenced, not shuffled. No algorithm.</div>'
      +'<div class="gh-secondary">'
      +'<button class="gh-2nd" id="gh-artist-btn">🔭 Start with an artist</button>'
      +'<button class="gh-2nd" id="gh-surprise-btn">🔮 Surprise me</button>'
      +'<button class="gh-2nd gh-explore-top" onclick="_ghExplore()">📚 Explore the full archive — 17,000 tracks</button>'
      +'</div>'
      +'<div class="gh-artistrow" id="gh-artist-row" style="display:none"><input id="gh-artist-input" placeholder="Type an artist — Marcos Valle, Roy Ayers, Theo Parrish…" autocomplete="off"><button id="gh-artist-go">Dig</button></div>'
      +'<div id="gh-panels"></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">New in<span class="gh-shelf-note">brand-new music &mdash; released this year, straight into the archive</span></div><div class="gh-bin">'+newReleasesShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Unearthed this month<span class="gh-shelf-note">older records Ben just dug up</span></div><div class="gh-bin">'+unearthedShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Just bought on vinyl<span class="gh-shelf-note">actual physical records, straight into Ben&rsquo;s crates</span></div><div class="gh-bin">'+freshVinylShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Hammered this year<span class="gh-shelf-note">what Ben has caned in the last 12 months</span>'
      +'</div><div class="gh-bin">'+onRepeatShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Hammered the year before<span class="gh-shelf-note">the previous 12 months&rsquo; obsessions</span></div><div class="gh-bin">'+prevYearShelf()+'</div></div>'
      +'<button class="gh-explore" onclick="_ghExplore()">Explore the full archive ↓</button>';
    main.insertBefore(el,main.firstChild);
    document.body.classList.add('guest-focus');
    /* pull the dig + rediscover panels up into the hero so they open in view;
       _ghExplore puts them back in front of the table */
    var ghp=document.getElementById('gh-panels');
    ['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)ghp.appendChild(p)});
    loadSleeves(el);

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
