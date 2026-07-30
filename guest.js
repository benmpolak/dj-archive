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
    var albumName=(t.al||'').trim();
    /* Prefer the named album sleeve whenever the archived track belongs to an
       album, even if only one or two album tracks are in the archive. This avoids
       retaining a launch-single sleeve after the full album has arrived. */
    var useAlbumArt=!!albumName&&(g.tracks.length>=3||albumName.toLowerCase()!==String(t.t||'').trim().toLowerCase());
    var artKey=useAlbumArt?'alb:'+primary(t.a).toLowerCase()+'|'+albumName.toLowerCase():(sid||primary(t.a)+' '+(t.al||t.t));
    var artQuery=primary(t.a)+' '+(useAlbumArt?albumName:(t.al||t.t));
    var tw=ART_TWEAKS[(primary(t.a).split(',')[0].trim()+'|'+(t.al||'').trim()).toLowerCase()];
    var twCss=tw?';background-size:'+tw.s+';background-position:'+tw.p:'';
    return '<div class="gh-card">'
      +'<div class="gh-card-art"'+(sid?' data-art-sid="'+sid+'"':'')+(useAlbumArt?' data-art-album="1"':'')
      +' data-art-key="'+E(artKey)+'"'
      +' data-art-q="'+E(artQuery)+'" style="background:linear-gradient(150deg,'+cc+'55,'+cc+'14 75%)'+twCss+'">'
      +'<span class="gh-card-albtxt">'+E(t.al||t.t)+'</span>'
      +'<span class="gh-card-play" '+playAttr(t)+' title="Play">▶︎</span>'
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
    var q=el.dataset.artQ;if(!q)return Promise.resolve(false);
    return new Promise(function(res){
      var cb='_itArt'+Math.floor(Math.random()*1e9);
      window[cb]=function(d){
        var found=false;
        try{var r=d&&d.results&&d.results[0];
          if(r&&r.artworkUrl100){var u=r.artworkUrl100.replace('100x100bb','400x400bb');setArt(el,u);cacheArt(el.dataset.artKey||q,u);found=true}
        }finally{delete window[cb];res(found)}
      };
      var s=document.createElement('script');
      s.src='https://itunes.apple.com/search?term='+encodeURIComponent(q)+'&entity=album&limit=1&callback='+cb;
      s.onerror=function(){delete window[cb];res(false)};
      document.head.appendChild(s);
    });
  }
  function spotifyArt(el){
    if(!el.dataset.artSid)return Promise.resolve(false);
    return fetch('https://open.spotify.com/oembed?url=https://open.spotify.com/track/'+el.dataset.artSid)
      .then(function(r){return r.json()})
      .then(function(j){if(j&&j.thumbnail_url){setArt(el,j.thumbnail_url);cacheArt(el.dataset.artKey,j.thumbnail_url);return true}return false})
      .catch(function(){return false});
  }
  function fetchArt(el){
    if(el.dataset.artDone)return Promise.resolve();el.dataset.artDone='1';
    var key=el.dataset.artKey;
    if(key&&_artCache[key]){setArt(el,_artCache[key]);return Promise.resolve()}
    /* albums: look the ALBUM up by name first — the most-played track's Spotify id
       often points at a pre-album SINGLE release wearing the wrong sleeve */
    if(el.dataset.artAlbum)return itunesArt(el).then(function(f){if(!f)return spotifyArt(el)});
    return spotifyArt(el).then(function(f){if(!f)return itunesArt(el)});
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
  /* A record can live in several factual shelves, but the guest homepage should
     only show it once. Shelves claim records in display order while retaining
     the full depth of choice inside each rack. */
  var _shelfSeen={};
  function recordKey(g){
    var t=rep(g,function(t){return t.p1||0});
    return primary(t.a).toLowerCase()+'|'+String(t.al||t.t).trim().toLowerCase();
  }
  function takeUnseen(gs,limit){
    var out=[];
    for(var i=0;i<gs.length&&out.length<limit;i++){
      var k=recordKey(gs[i]);
      if(_shelfSeen[k])continue;
      _shelfSeen[k]=1;out.push(gs[i]);
    }
    return out;
  }
  /* never on the racks, whatever the play counts say */
  var SHELF_EXCLUDE={'everton f.c.':1,'everton':1};
  function onePerArtist(gs){
    var seen={};
    return gs.filter(function(g){
      var a=artistKey(g);
      if(SHELF_EXCLUDE[a]||seen[a])return false;seen[a]=1;return true;
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
    /* rack window: this month + two before (~90 days) */
    var m=Math.floor(maxDa/100)*12+(maxDa%100)-1-2;
    var prevDa=Math.floor(m/12)*100+(m%12)+1;
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
    return takeUnseen(gs,50).map(function(g){
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
    return takeUnseen(gs,50).map(function(g){
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
      +'<span class="gh-card-play" onclick="window.open(\''+o.url+'\',\'_blank\')" title="Open on '+(o.tag||'Bandcamp')+'">▶︎</span>'
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
    return ov+takeUnseen(gs,25-VINYL_OVERRIDES.length).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'added '+fmtDa(g.da)});
    }).join('');
  }
  function onRepeatShelf(){
    var yr=new Date().getFullYear();
    var gs=groupRecords().filter(function(g){
      var r=parseInt(rep(g,function(t){return t.p1||0}).r)||0;
      return g.p1>=3&&hasSpotify(g)&&(r===yr||r===yr-1);
    });
    /* Fresher release year first; listening rank decides within each year. */
    gs.sort(function(a,b){
      var ay=parseInt(rep(a,function(t){return t.p1||0}).r)||0;
      var by=parseInt(rep(b,function(t){return t.p1||0}).r)||0;
      return (by-ay)||(b.p1-a.p1);
    });
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+g.p1+' plays'});
    }).join('');
  }
  function prevYearShelf(){
    /* p2-p1 = plays in the year before the current 12-month window.
       Keep this to releases from that year and the year before; records already
       used by a fresher shelf remain excluded. */
    var yr=new Date().getFullYear();
    var gs=groupRecords().filter(function(g){
      var r=parseInt(rep(g,function(t){return t.p1||0}).r)||0;
      return r===yr-1||r===yr-2;
    });
    gs.forEach(function(g){g.pPrev=0;g.tracks.forEach(function(t){g.pPrev+=Math.max((t.p2||0)-(t.p1||0),0)})});
    gs=gs.filter(function(g){return g.pPrev>=3&&hasSpotify(g)});
    /* 2025 before 2024 (and equivalent in future years), then listening rank. */
    gs.sort(function(a,b){
      var ay=parseInt(rep(a,function(t){return t.p1||0}).r)||0;
      var by=parseInt(rep(b,function(t){return t.p1||0}).r)||0;
      return (by-ay)||(b.pPrev-a.pPrev);
    });
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+g.pPrev+' plays'});
    }).join('');
  }
  function decadeShelf(){
    var yr=new Date().getFullYear(),start=Math.floor(yr/10)*10;
    var gs=groupRecords().filter(function(g){
      var r=parseInt(rep(g,function(t){return t.p1||0}).r)||0;
      return g.pc>=3&&hasSpotify(g)&&r>=start&&r<=yr;
    });
    gs.sort(function(a,b){return b.pc-a.pc});
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+g.pc+' plays'});
    }).join('');
  }
  function allTimeShelf(){
    var gs=groupRecords().filter(function(g){return g.pc>=3&&hasSpotify(g)});
    gs.sort(function(a,b){return b.pc-a.pc});
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+g.pc+' plays'});
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

  function installShelfControls(root){
    root.querySelectorAll('.gh-shelf').forEach(function(shelf){
      var bin=shelf.querySelector('.gh-bin');if(!bin)return;
      var prev=document.createElement('button'),next=document.createElement('button');
      prev.className='gh-shelf-arrow prev';next.className='gh-shelf-arrow next';
      prev.type=next.type='button';prev.textContent='‹';next.textContent='›';
      prev.setAttribute('aria-label','Previous records');next.setAttribute('aria-label','More records');
      shelf.appendChild(prev);shelf.appendChild(next);
      function update(){
        var scrollable=bin.scrollWidth>bin.clientWidth+4;
        prev.hidden=next.hidden=!scrollable;
        prev.disabled=!scrollable||bin.scrollLeft<=4;
        next.disabled=!scrollable||bin.scrollLeft+bin.clientWidth>=bin.scrollWidth-4;
      }
      function move(dir){
        bin.scrollBy({left:dir*Math.max(320,Math.floor(bin.clientWidth*0.82)),behavior:'smooth'});
      }
      prev.onclick=function(){move(-1)};next.onclick=function(){move(1)};
      bin.addEventListener('scroll',update,{passive:true});
      window.addEventListener('resize',update);
      requestAnimationFrame(update);
    });
  }

  /* ---------- build ---------- */
  var CHIPS=['Brazilian sunshine','Late-night jazz','90s deep house','70s funk','Dub session','Like Marcos Valle','Jazz on vinyl'];
  function buildHero(){
    var main=document.querySelector('.main-area');if(!main)return;
    var cutoff=playCutoff();
    var yr=new Date().getFullYear();
    var el=document.createElement('div');
    el.id='guest-hero';
    el.innerHTML=
      '<div class="gh-brand">The DJ Archive</div>'
      +'<div class="gh-prop">Tell Ben’s shelves what you fancy.</div>'
      +'<div class="gh-inputrow"><input id="gh-input" placeholder="Brazilian sunshine, late-night jazz, like Marcos Valle…" autocomplete="off"><button id="gh-select">SELECT</button></div>'
      +'<div class="gh-chips">'+CHIPS.map(function(c){return '<span class="gh-chip" data-q="'+E(c)+'">'+E(c)+'</span>'}).join('')+'</div>'
      +'<div class="gh-sub">The Selector pulls 25 tracks from one human-curated archive — 17,000+ tracks dug by ear over 14 years: bankers, forgotten loves and a couple of wild cards. Sequenced, not shuffled. No algorithm.</div>'
      +'<div class="gh-secondary">'
      +'<button class="gh-2nd" id="gh-artist-btn">Start with an artist</button>'
      +'<button class="gh-2nd" id="gh-surprise-btn">Surprise me</button>'
      +'<button class="gh-2nd gh-explore-top" onclick="_ghExplore()">Explore the full archive — 17,000 tracks</button>'
      +'</div>'
      +'<div class="gh-artistrow" id="gh-artist-row" style="display:none"><input id="gh-artist-input" placeholder="Type an artist — Marcos Valle, Roy Ayers, Theo Parrish…" autocomplete="off"><button id="gh-artist-go">Go</button></div>'
      +'<div id="gh-panels"></div>'
      +'<div class="gh-shelf gh-shelf-first"><div class="gh-shelf-title">New in<span class="gh-shelf-note">brand-new music &mdash; released this year, straight into the archive</span></div><div class="gh-bin">'+newReleasesShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Unearthed this month<span class="gh-shelf-note">older records Ben just dug up</span></div><div class="gh-bin">'+unearthedShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Just bought on vinyl<span class="gh-shelf-note">actual physical records, straight into Ben&rsquo;s crates</span></div><div class="gh-bin">'+freshVinylShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Heavy rotation &mdash; this year<span class="gh-shelf-note">'+(yr-1)+'–'+yr+' releases Ben has played relentlessly</span>'
      +'</div><div class="gh-bin">'+onRepeatShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Heavy rotation &mdash; last year<span class="gh-shelf-note">'+(yr-2)+'–'+(yr-1)+' releases Ben played relentlessly</span></div><div class="gh-bin">'+prevYearShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Heavy rotation &mdash; this decade<span class="gh-shelf-note">'+(Math.floor(yr/10)*10)+'–'+yr+' releases Ben has returned to most</span></div><div class="gh-bin">'+decadeShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Heavy rotation &mdash; all time<span class="gh-shelf-note">the records Ben has returned to most across the full listening history</span></div><div class="gh-bin">'+allTimeShelf()+'</div></div>'
      +'<button class="gh-explore" onclick="_ghExplore()">Explore the full archive ↓</button>';
    main.insertBefore(el,main.firstChild);
    document.body.classList.add('guest-focus');
    /* pull the dig + rediscover panels up into the hero so they open in view;
       _ghExplore puts them back in front of the table */
    var ghp=document.getElementById('gh-panels');
    ['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)ghp.appendChild(p)});
    loadSleeves(el);
    installShelfControls(el);

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
