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
      var g=groups[k]||(groups[k]={tracks:[],da:0,idx:0,p1:0,pc:0,vy:0,ids:{},uc:0});
      g.tracks.push(t);
      if((t.da||0)>g.da)g.da=t.da;
      if(i>g.idx)g.idx=i;
      var sid=t.sid||('row:'+i);
      if(!g.ids[sid]){g.ids[sid]=1;g.uc++;g.p1+=(t.p1||0);g.pc+=(t.pc||0)}
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
    /* Three or more archived tracks means Ben is treating this as an album, so
       prefer its album sleeve over whichever launch single supplied the track id. */
    var useAlbumArt=!!albumName&&g.uc>=3;
    var artKey=useAlbumArt?'alb:'+primary(t.a).toLowerCase()+'|'+albumName.toLowerCase():(sid||primary(t.a)+' '+(t.al||t.t));
    var artQuery=primary(t.a)+' '+(useAlbumArt?albumName:(t.al||t.t));
    var tw=ART_TWEAKS[(primary(t.a).split(',')[0].trim()+'|'+(t.al||'').trim()).toLowerCase()];
    var twCss=tw?';background-size:'+tw.s+';background-position:'+tw.p:'';
    var artist=primary(t.a),title=t.al||t.t,metaText=meta(g,t);
    /* Listening evidence belongs in the opened record view, not under every
       sleeve. Keep the rack visual and fast to scan. */
    var rackMeta=metaText.replace(/\s*·\s*\d+\s+plays?\s*$/i,'');
    return '<div class="gh-card" role="button" tabindex="0" aria-label="View '+E(artist)+' — '+E(title)+'"'
      +' data-sid="'+E(sid)+'" data-did="'+E(t.did||'')+'"'
      +' data-artist="'+E(artist)+'" data-album="'+E(title)+'"'
      +' data-crate="'+E((t.c||[])[0]||'')+'" data-crates="'+E((t.c||[]).join('|'))+'" data-vibe="'+E(t.vb||'')+'"'
      +' data-meta="'+E(metaText)+'">'
      +'<div class="gh-card-art"'+(sid?' data-art-sid="'+sid+'"':'')+(useAlbumArt?' data-art-album="1"':'')
      +' data-art-key="'+E(artKey)+'"'
      +' data-art-q="'+E(artQuery)+'" style="background:linear-gradient(150deg,'+cc+'55,'+cc+'14 75%)'+twCss+'">'
      +'<span class="gh-card-albtxt">'+E(t.al||t.t)+'</span>'
      +'<span class="gh-card-play" '+playAttr(t)+' title="Play">▶︎</span>'
      +(g.vy?'<span class="gh-card-vinyl">VINYL</span>':'')
      +'</div>'
      +'<div class="gh-card-a">'+E(artist)+'</div>'
      +'<div class="gh-card-al">'+E(title)+'</div>'
      +'<div class="gh-card-meta">'+rackMeta+'</div>'
      +'</div>';
  }
  /* real sleeves: Spotify oEmbed first (CORS-open, no auth), iTunes Search as the
     fallback for records not on Spotify (JSONP — iTunes sends no CORS headers).
     The text-led card underneath stays when both miss. Discogs is a dead end:
     anonymous API responses carry no images. */
  var _bakedArt=/*__GUEST_ART__*/{};
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
    if(key&&_bakedArt[key]){setArt(el,_bakedArt[key]);return Promise.resolve()}
    if(key&&_artCache[key]){setArt(el,_artCache[key]);return Promise.resolve()}
    /* albums: look the ALBUM up by name first — the most-played track's Spotify id
       often points at a pre-album SINGLE release wearing the wrong sleeve */
    if(el.dataset.artAlbum)return itunesArt(el).then(function(f){if(!f)return spotifyArt(el)});
    return spotifyArt(el).then(function(f){if(!f)return itunesArt(el)});
  }
  /* One controlled queue: a burst of concurrent iTunes JSONP calls gets throttled
     and leaves blank sleeves. Eight workers are quick without flooding it. Shelves
     approaching the viewport move their first ten covers to the head of the queue. */
  var _artQueue=[],_artActive=0,ART_WORKERS=8;
  function pumpArt(){
    while(_artActive<ART_WORKERS&&_artQueue.length){
      var el=_artQueue.shift();
      delete el.dataset.artQueued;
      _artActive++;
      fetchArt(el).then(artDone,artDone);
    }
    function artDone(){_artActive--;pumpArt()}
  }
  function queueArt(el,urgent){
    if(el.dataset.artDone)return;
    if(el.dataset.artQueued){
      if(urgent){
        var i=_artQueue.indexOf(el);
        if(i>0){_artQueue.splice(i,1);_artQueue.unshift(el)}
      }
      return;
    }
    el.dataset.artQueued='1';
    if(urgent)_artQueue.unshift(el);else _artQueue.push(el);
  }
  function loadSleeves(root){
    var priority=[],rest=[],fronts=[];
    var shelves=[].slice.call(root.querySelectorAll('.gh-shelf'));
    if(shelves.length){
      shelves.forEach(function(shelf){
        var els=[].slice.call(shelf.querySelectorAll('.gh-card-art'));
        fronts.push(els.slice(0,10));
        rest=rest.concat(els.slice(10));
      });
      /* Round-robin the front cards so no lower shelf sits at the back of the queue. */
      for(var i=0;i<10;i++)fronts.forEach(function(run){if(run[i])priority.push(run[i])});
      if('IntersectionObserver'in window){
        var io=new IntersectionObserver(function(entries){
          entries.forEach(function(entry){
            if(!entry.isIntersecting)return;
            var run=[].slice.call(entry.target.querySelectorAll('.gh-card-art'),0,10);
            /* Reverse because urgent items are unshifted: card one stays first. */
            run.reverse().forEach(function(el){queueArt(el,true)});
            pumpArt();
            io.unobserve(entry.target);
          });
        },{root:document.querySelector('.main-area'),rootMargin:'650px 0px'});
        shelves.forEach(function(shelf){io.observe(shelf)});
      }
    }else{
      priority=[].slice.call(root.querySelectorAll('.gh-card-art'));
    }
    priority.concat(rest).forEach(function(el){queueArt(el,false)});
    pumpArt();
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
      if(SHELF_RECORD_EXCLUDE[k]||_shelfSeen[k])continue;
      _shelfSeen[k]=1;out.push(gs[i]);
    }
    return out;
  }
  /* never on the racks, whatever the play counts say */
  var SHELF_EXCLUDE={'everton f.c.':1,'everton':1};
  /* hand-pinned to the front of New in, whatever the play counts say —
     also exempt from the rack's date window so they stay put until unpinned */
  var SHELF_PIN={'patchwork inc.':1};
  var SHELF_RECORD_EXCLUDE={'gary barlow|paddington bear (from “the adventures of paddington”)':1};
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
    var gs=yearGs.filter(function(g){return g.da>=prevDa||SHELF_PIN[artistKey(g)]});
    gs.sort(function(a,b){
      var pin=(SHELF_PIN[artistKey(b)]?1:0)-(SHELF_PIN[artistKey(a)]?1:0);
      return pin||(yearTotals[artistKey(b)]-yearTotals[artistKey(a)])||(b.pc-a.pc)||(b.idx-a.idx);
    });
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'archived '+fmtDa(g.da)});
    }).join('');
  }
  function unearthedShelf(){
    /* The second-hand bin: older records dug up in the current archive month and
       two before it. Broad enough to keep 50 choices without pretending they are
       all from this week. */
    var yr=new Date().getFullYear();
    var maxDa=0;DATA.forEach(function(t){if((t.da||0)>maxDa)maxDa=t.da});
    var m=Math.floor(maxDa/100)*12+(maxDa%100)-1-2;
    var cutoffDa=Math.floor(m/12)*100+(m%12)+1;
    var gs=groupRecords().filter(function(g){
      return g.da>=cutoffDa&&!g.vy&&hasSpotify(g)&&g.tracks.every(function(t){return (parseInt(t.r)||0)<yr});
    });
    /* These records only entered the archive in the last three months, so p1 is
       effectively plays since arrival — the right weighting for this time zone. */
    gs.sort(function(a,b){return (b.p1-a.p1)||(b.pc-a.pc)||(b.da-a.da)||(b.idx-a.idx)});
    gs=onePerArtist(gs);
    return takeUnseen(gs,50).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+'dug up '+fmtDa(g.da)+(g.p1?' · '+g.p1+' plays':'')});
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
    return '<div class="gh-card" role="button" tabindex="0" aria-label="View '+E(o.a)+' — '+E(o.al)+'"'
      +' data-artist="'+E(o.a)+'" data-album="'+E(o.al)+'" data-meta="'+o.r+' · added '+fmtDa(o.da)+'"'
      +' data-url="'+E(o.url)+'" data-service="'+E(o.tag||'Bandcamp')+'" data-crate="Vinyl" data-crates="Vinyl">'
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
  function shuffleShelf(records){
    for(var i=records.length-1;i>0;i--){
      var j=Math.floor(Math.random()*(i+1)),tmp=records[i];
      records[i]=records[j];records[j]=tmp;
    }
    return records;
  }
  function decadeShelf(){
    var yr=new Date().getFullYear(),start=Math.floor(yr/10)*10;
    var gs=groupRecords().filter(function(g){
      var r=parseInt(rep(g,function(t){return t.p1||0}).r)||0;
      return g.pc>=3&&hasSpotify(g)&&r>=start&&r<=yr;
    });
    gs.sort(function(a,b){return b.pc-a.pc});
    gs=onePerArtist(gs);
    /* Membership remains the factual top 50; only their display order changes
       once per visit so the same famous sleeves do not permanently own the front. */
    return shuffleShelf(takeUnseen(gs,50)).map(function(g){
      return card(g,function(g,t){return (t.r?t.r+' · ':'')+g.pc+' plays'});
    }).join('');
  }
  function allTimeShelf(){
    var gs=groupRecords().filter(function(g){return g.pc>=3&&hasSpotify(g)});
    gs.sort(function(a,b){return b.pc-a.pc});
    gs=onePerArtist(gs);
    return shuffleShelf(takeUnseen(gs,50)).map(function(g){
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
    document.body.classList.add('guest-archive-open');
    var h=document.getElementById('guest-hero');if(h)h.style.display='none';
    if(main)main.scrollTop=0;
    window.scrollTo(0,0);
  };
  window._ghBackHome=function(){
    var main=document.querySelector('.main-area'),h=document.getElementById('guest-hero'),panels=document.getElementById('gh-panels');
    if(panels)['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)panels.appendChild(p)});
    var sidebar=document.querySelector('.sidebar');if(sidebar)sidebar.classList.remove('open');
    document.body.classList.remove('guest-archive-open');
    document.body.classList.add('guest-focus');
    if(h)h.style.display='';
    if(main)main.scrollTop=0;
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

  function installLongView(root){
    var box=root.querySelector('.gh-longview');if(!box)return;
    var tabs=[].slice.call(box.querySelectorAll('.gh-long-tab'));
    var shelves=[].slice.call(box.querySelectorAll('.gh-long-shelf'));
    tabs.forEach(function(tab){
      tab.onclick=function(){
        tabs.forEach(function(t){t.classList.toggle('active',t===tab)});
        shelves.forEach(function(s){s.hidden=s.dataset.long!==tab.dataset.long});
        requestAnimationFrame(function(){window.dispatchEvent(new Event('resize'))});
      };
    });
    box.addEventListener('toggle',function(){
      if(box.open)requestAnimationFrame(function(){window.dispatchEvent(new Event('resize'))});
    });
  }

  /* A small, explicit filter over the four new/recent-release racks — never a
     disguised query of the full archive. Unearthed and the long view remain the
     editorial context that shows the taste behind those recommendations. */
  function installRifle(root){
    var rifle=root.querySelector('.gh-rifle'),results=root.querySelector('#gh-rifle-results');
    if(!rifle||!results)return;
    var sourceShelves=[].slice.call(root.querySelectorAll('.gh-new-source'));
    var sourceCards=[];
    sourceShelves.forEach(function(shelf){
      shelf.querySelectorAll('.gh-card').forEach(function(card){
        sourceCards.push(card);
      });
    });
    var state={genre:'',vibe:''};
    function counts(attr,split){
      var out={};
      sourceCards.forEach(function(card){
        var vals=split?(card.dataset[attr]||'').split('|'):[card.dataset[attr]||''];
        vals.forEach(function(v){if(v&&v!=='Uncategorized'&&v!=='Vinyl')out[v]=(out[v]||0)+1});
      });
      return Object.keys(out).sort(function(a,b){return out[b]-out[a]||a.localeCompare(b)}).map(function(k){return[k,out[k]]});
    }
    function buildChips(id,kind,items){
      var wrap=root.querySelector(id);
      items.forEach(function(item){
        var b=document.createElement('button');
        b.type='button';b.className='gh-rifle-chip '+(kind==='genre'?'gh-rifle-genre':'gh-rifle-vibe');b.dataset.value=item[0];
        b.textContent=item[0];b.title=item[1]+' matching records';
        if(kind==='genre')b.style.setProperty('--divider',(window.CC&&CC[item[0]])||'#e8a040');
        b.onclick=function(){
          state[kind]=state[kind]===b.dataset.value?'':b.dataset.value;
          wrap.querySelectorAll('.gh-rifle-chip').forEach(function(x){x.classList.toggle('active',x.dataset.value===state[kind])});
          render();
        };
        wrap.appendChild(b);
      });
    }
    buildChips('#gh-rifle-genres','genre',counts('crates',true));
    buildChips('#gh-rifle-vibes','vibe',counts('vibe',false));
    var bin=results.querySelector('.gh-bin'),title=results.querySelector('.gh-rifle-result-title');
    var note=results.querySelector('.gh-rifle-result-note'),matches=[];
    function render(){
      bin.innerHTML='';
      matches=sourceCards.filter(function(card){
        var crates=(card.dataset.crates||'').split('|');
        return (!state.genre||crates.indexOf(state.genre)>=0)&&(!state.vibe||card.dataset.vibe===state.vibe);
      });
      var active=state.genre||state.vibe;
      results.hidden=!active;
      if(!active){
        rifle.querySelector('.gh-rifle-summary-note').textContent='choose a section · add a feel if you fancy';
        return;
      }
      title.textContent=[state.genre,state.vibe].filter(Boolean).join(' · ');
      note.textContent=matches.length+' recent release'+(matches.length===1?'':'s')+' from Ben’s current racks';
      matches.forEach(function(card){bin.appendChild(card.cloneNode(true))});
      results.querySelector('.gh-rifle-pick').disabled=!matches.length;
      rifle.querySelector('.gh-rifle-summary-note').textContent=[state.genre||'Any genre',state.vibe||'Any mood'].join(' · ');
      requestAnimationFrame(function(){window.dispatchEvent(new Event('resize'))});
    }
    results.querySelector('.gh-rifle-clear').onclick=function(){
      state.genre=state.vibe='';
      rifle.querySelectorAll('.gh-rifle-chip').forEach(function(x){x.classList.remove('active')});
      rifle.querySelector('.gh-rifle-summary-note').textContent='choose a section · add a feel if you fancy';
      results.hidden=true;bin.innerHTML='';
    };
    results.querySelector('.gh-rifle-pick').onclick=function(){
      if(!matches.length)return;
      var target=matches[Math.floor(Math.random()*matches.length)];
      var clone=[].slice.call(bin.querySelectorAll('.gh-card')).find(function(card){
        return card.dataset.artist===target.dataset.artist&&card.dataset.album===target.dataset.album;
      });
      if(clone)clone.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    };
  }

  /* Sleeves stay fast to scan; the facts arrive only when a record is chosen.
     This is a lightbox, not a product page: one large sleeve, archive evidence,
     then the useful listening / digging exits. */
  function installRecordViewer(root){
    var viewer=document.createElement('div');
    viewer.className='gh-detail';
    viewer.setAttribute('aria-hidden','true');
    viewer.innerHTML=
      '<div class="gh-detail-backdrop"></div>'
      +'<div class="gh-detail-panel" role="dialog" aria-modal="true" aria-labelledby="gh-detail-album">'
      +'<button class="gh-detail-close" type="button" aria-label="Close">×</button>'
      +'<button class="gh-detail-nav prev" type="button" aria-label="Previous record">‹</button>'
      +'<button class="gh-detail-nav next" type="button" aria-label="Next record">›</button>'
      +'<div class="gh-detail-art"></div>'
      +'<div class="gh-detail-copy">'
      +'<div class="gh-detail-kicker">From Ben&rsquo;s shelves</div>'
      +'<div class="gh-detail-artist"></div>'
      +'<div class="gh-detail-album" id="gh-detail-album"></div>'
      +'<div class="gh-detail-meta"></div>'
      +'<div class="gh-detail-tags"></div>'
      +'<div class="gh-detail-actions"></div>'
      +'</div></div>';
    document.body.appendChild(viewer);
    var lastFocus=null,currentCards=[],currentIndex=0,touchX=0;
    function close(){
      viewer.classList.remove('open');
      viewer.setAttribute('aria-hidden','true');
      document.body.classList.remove('gh-detail-open');
      if(lastFocus)lastFocus.focus();
    }
    function action(label,cls,fn,href){
      var el=document.createElement(href?'a':'button');
      el.className='gh-detail-action '+(cls||'');
      el.textContent=label;
      if(href){el.href=href;el.target='_blank';el.rel='noopener'}
      else{el.type='button';el.onclick=fn}
      return el;
    }
    function show(card){
      var art=card.querySelector('.gh-card-art');
      viewer.querySelector('.gh-detail-art').style.backgroundImage=art.style.backgroundImage;
      viewer.querySelector('.gh-detail-artist').textContent=card.dataset.artist||'';
      viewer.querySelector('.gh-detail-album').textContent=card.dataset.album||'';
      viewer.querySelector('.gh-detail-meta').textContent=card.dataset.meta||'';
      var tags=viewer.querySelector('.gh-detail-tags');tags.innerHTML='';
      [['CRATE',card.dataset.crate],['VIBE',card.dataset.vibe]].forEach(function(x){
        if(!x[1])return;
        var tag=document.createElement('span');
        tag.innerHTML='<small>'+x[0]+'</small>'+E(x[1]);
        tags.appendChild(tag);
      });
      var actions=viewer.querySelector('.gh-detail-actions');actions.innerHTML='';
      var sid=card.dataset.sid,did=card.dataset.did,url=card.dataset.url;
      if(sid){
        actions.appendChild(action('Play','primary',function(){playPreview(sid,this)}));
        actions.appendChild(action('Spotify ↗','',null,'https://open.spotify.com/track/'+sid));
      }
      if(did)actions.appendChild(action('Discogs ↗','',null,'https://www.discogs.com/release/'+did));
      if(url)actions.appendChild(action((card.dataset.service||'Listen')+' ↗','primary',null,url));
      var shelf=card.closest('.gh-shelf'),title=shelf&&shelf.querySelector('.gh-shelf-title');
      var shelfName=title&&title.childNodes[0]?title.childNodes[0].textContent.trim():'From Ben’s shelves';
      viewer.querySelector('.gh-detail-kicker').textContent=shelfName+' · '+(currentIndex+1)+' of '+currentCards.length;
      viewer.querySelector('.gh-detail-nav.prev').disabled=currentIndex===0;
      viewer.querySelector('.gh-detail-nav.next').disabled=currentIndex===currentCards.length-1;
    }
    function open(card){
      lastFocus=card;
      currentCards=[].slice.call(card.closest('.gh-bin').querySelectorAll('.gh-card'));
      currentIndex=currentCards.indexOf(card);
      show(card);
      viewer.classList.add('open');
      viewer.setAttribute('aria-hidden','false');
      document.body.classList.add('gh-detail-open');
      requestAnimationFrame(function(){viewer.querySelector('.gh-detail-close').focus()});
    }
    function step(dir){
      var next=currentIndex+dir;
      if(next<0||next>=currentCards.length)return;
      currentIndex=next;show(currentCards[currentIndex]);
    }
    root.addEventListener('click',function(e){
      var card=e.target.closest('.gh-card');
      if(!card||e.target.closest('.gh-card-play'))return;
      open(card);
    });
    root.addEventListener('keydown',function(e){
      var card=e.target.closest('.gh-card');
      if(!card||e.target!==card||(e.key!=='Enter'&&e.key!==' '))return;
      e.preventDefault();open(card);
    });
    viewer.querySelector('.gh-detail-close').onclick=close;
    viewer.querySelector('.gh-detail-nav.prev').onclick=function(){step(-1)};
    viewer.querySelector('.gh-detail-nav.next').onclick=function(){step(1)};
    viewer.querySelector('.gh-detail-backdrop').onclick=close;
    viewer.querySelector('.gh-detail-panel').addEventListener('touchstart',function(e){touchX=e.changedTouches[0].clientX},{passive:true});
    viewer.querySelector('.gh-detail-panel').addEventListener('touchend',function(e){
      var dx=e.changedTouches[0].clientX-touchX;
      if(Math.abs(dx)>55)step(dx<0?1:-1);
    },{passive:true});
    document.addEventListener('keydown',function(e){
      if(!viewer.classList.contains('open'))return;
      if(e.key==='Escape')close();
      else if(e.key==='ArrowLeft')step(-1);
      else if(e.key==='ArrowRight')step(1);
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
      +'<div class="gh-proofline">17,000+ tracks &middot; 14 years &middot; chosen by ear</div>'
      +'<div class="gh-prop">Tell Ben’s shelves what you fancy.</div>'
      +'<div class="gh-inputrow"><input id="gh-input" placeholder="Brazilian sunshine, late-night jazz, like Marcos Valle…" autocomplete="off"><button id="gh-select">SELECT</button></div>'
      +'<div class="gh-chips">'+CHIPS.map(function(c){return '<span class="gh-chip" data-q="'+E(c)+'">'+E(c)+'</span>'}).join('')+'</div>'
      +'<div class="gh-sub">The Selector deals 25 tracks from Ben&rsquo;s shelves: bankers, forgotten loves and a couple of wild cards. Sequenced, not shuffled. No algorithm.</div>'
      +'<div class="gh-secondary">'
      +'<button class="gh-2nd" id="gh-artist-btn">Start with an artist</button>'
      +'<button class="gh-2nd" id="gh-surprise-btn">Surprise me</button>'
      +'</div>'
      +'<div class="gh-artistrow" id="gh-artist-row" style="display:none"><input id="gh-artist-input" placeholder="Type an artist — Marcos Valle, Roy Ayers, Theo Parrish…" autocomplete="off"><button id="gh-artist-go">Go</button></div>'
      +'<div id="gh-panels"></div>'
      +'<div class="gh-route-divider"><span>Or browse</span></div>'
      +'<details class="gh-rifle"><summary><span class="gh-rifle-summary-title">Flick through the new arrivals</span><span class="gh-rifle-summary-note">choose a section &middot; add a feel if you fancy</span><span class="gh-fold-mark">+</span></summary>'
      +'<div class="gh-rifle-body"><div class="gh-rifle-row"><span>Section</span><div class="gh-rifle-chips" id="gh-rifle-genres"></div></div>'
      +'<div class="gh-rifle-row"><span>Feel</span><div class="gh-rifle-chips" id="gh-rifle-vibes"></div></div></div></details>'
      +'<div class="gh-recommend-intro"><div class="gh-shelf-title">Recommended from Ben&rsquo;s shelves<span class="gh-shelf-note">records Ben is buying, playing and returning to &middot; tap any cover to listen</span></div></div>'
      +'<div class="gh-shelf" id="gh-rifle-results" hidden><div class="gh-rifle-result-head"><div><div class="gh-shelf-title gh-rifle-result-title"></div><div class="gh-rifle-result-note"></div></div>'
      +'<div class="gh-rifle-result-actions"><button class="gh-rifle-pick" type="button">Pull one for me</button><button class="gh-rifle-clear" type="button">Clear</button></div></div><div class="gh-bin"></div></div>'
      +'<div class="gh-shelf gh-new-source gh-shelf-first"><div class="gh-shelf-title">New in<span class="gh-shelf-note">brand-new music &mdash; released this year, straight into the archive</span></div><div class="gh-bin">'+newReleasesShelf()+'</div></div>'
      +'<div class="gh-shelf gh-new-source"><div class="gh-shelf-title">Just bought on vinyl<span class="gh-shelf-note">actual physical records, straight into Ben&rsquo;s crates</span></div><div class="gh-bin">'+freshVinylShelf()+'</div></div>'
      +'<div class="gh-shelf gh-new-source"><div class="gh-shelf-title">Heavy rotation &mdash; this year<span class="gh-shelf-note">'+(yr-1)+'–'+yr+' releases Ben has played relentlessly</span>'
      +'</div><div class="gh-bin">'+onRepeatShelf()+'</div></div>'
      +'<div class="gh-shelf gh-new-source"><div class="gh-shelf-title">Heavy rotation &mdash; last year<span class="gh-shelf-note">'+(yr-2)+'–'+(yr-1)+' releases Ben played relentlessly</span></div><div class="gh-bin">'+prevYearShelf()+'</div></div>'
      +'<div class="gh-shelf"><div class="gh-shelf-title">Unearthed recently<span class="gh-shelf-note">older records Ben dug up in the last three months</span></div><div class="gh-bin">'+unearthedShelf()+'</div></div>'
      +'<details class="gh-longview"><summary><span><b>Heavy rotation &mdash; the long view</b><small>This decade and ever &middot; shuffled each visit</small></span><span class="gh-fold-mark">+</span></summary>'
      +'<div class="gh-longview-body"><div class="gh-long-tabs"><button class="gh-long-tab active" data-long="decade" type="button">This decade</button><button class="gh-long-tab" data-long="ever" type="button">Ever</button></div>'
      +'<div class="gh-shelf gh-long-shelf" data-long="decade"><div class="gh-shelf-title">This decade<span class="gh-shelf-note">'+(Math.floor(yr/10)*10)+'–'+yr+' releases Ben has returned to most</span></div><div class="gh-bin">'+decadeShelf()+'</div></div>'
      +'<div class="gh-shelf gh-long-shelf" data-long="ever" hidden><div class="gh-shelf-title">Ever<span class="gh-shelf-note">the records Ben has returned to most across the full listening history</span></div><div class="gh-bin">'+allTimeShelf()+'</div></div>'
      +'</div></details>'
      +'<button class="gh-explore" onclick="_ghExplore()">Explore the full archive ↓</button>';
    main.insertBefore(el,main.firstChild);
    var back=document.createElement('div');
    back.className='gh-back-strip';
    back.innerHTML='<button type="button" onclick="_ghBackHome()">&larr; Back to recommendations</button><span>Full archive &middot; 17,000+ tracks</span>';
    main.insertBefore(back,el.nextSibling);
    document.body.classList.add('guest-focus');
    /* pull the dig + rediscover panels up into the hero so they open in view;
       _ghExplore puts them back in front of the table */
    var ghp=document.getElementById('gh-panels');
    ['dig-panel','rd-panel'].forEach(function(id){var p=document.getElementById(id);if(p)ghp.appendChild(p)});
    loadSleeves(el);
    installShelfControls(el);
    installRecordViewer(el);
    installRifle(el);
    installLongView(el);

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
