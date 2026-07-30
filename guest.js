/* Guest layer — first-visit welcome card + owner mode.
   Source of truth: guest.js, injected by patch-guest.py as <script id="guest-js">.
   Owner mode: visit ?owner once (persists in localStorage); ?guest to switch back.
   Guests never see edit affordances; the welcome card shows once per device.
   NB: use query params not hashes — the router replaceStates unknown hashes
   away before bottom scripts parse (same lesson as gigs find-route). */
(function(){
  function isOwner(){try{return localStorage.getItem('dj_owner')==='1'}catch(e){return true}}
  function setOwner(on){try{on?localStorage.setItem('dj_owner','1'):localStorage.removeItem('dj_owner')}catch(e){}}
  function seenWelcome(){try{return !!localStorage.getItem('dj_welcome_v1')}catch(e){return true}}
  function markWelcome(){try{localStorage.setItem('dj_welcome_v1','1')}catch(e){}}

  /* ?owner / ?guest switches */
  var params=new URLSearchParams(location.search);
  if(params.has('owner')){setOwner(true);history.replaceState(null,'',location.pathname+location.hash)}
  else if(params.has('guest')){setOwner(false);history.replaceState(null,'',location.pathname+location.hash)}
  if(isOwner())document.body.classList.add('owner');

  /* Retire the old #intro tour modal — the welcome card supersedes it */
  try{localStorage.setItem('dj-archive-seen','1')}catch(e){}
  var oi=document.getElementById('intro');if(oi)oi.style.display='none';

  /* Gate the quick-tag editor (pencil + right-click) behind owner mode */
  var _oqt=window.openQuickTag;
  if(_oqt)window.openQuickTag=function(){if(isOwner())return _oqt.apply(this,arguments)};

  function close(){var w=document.getElementById('guest-welcome');if(w)w.remove();markWelcome()}
  function door(action){close();action()}

  function showWelcome(){
    var w=document.createElement('div');
    w.id='guest-welcome';
    w.innerHTML=
      '<div class="gw-card">'
      +'<button class="gw-close" title="Close">&times;</button>'
      +'<div class="gw-title">The DJ Archive</div>'
      +'<div class="gw-sub">17,000 tracks dug by ear over 14 years &mdash; jazz, house, Brazilian, soul, disco, dub. No algorithm, one pair of ears.</div>'
      +'<div class="gw-doors">'
      +'<button class="gw-door" data-d="deal"><span class="gw-door-icon">📻</span><span><span class="gw-door-name">Ask the Selector</span><span class="gw-door-desc">Say what you fancy &mdash; artists, vibes, "90s deep house", "brazilian sunshine" &mdash; and get a sequenced selection.</span></span></button>'
      +'<button class="gw-door" data-d="crates"><span class="gw-door-icon">📦</span><span><span class="gw-door-name">Browse the crates</span><span class="gw-door-desc">Straight into the shelves &mdash; 13 crates from Jazz to Reggae &amp; Dub.</span></span></button>'
      +'<button class="gw-door" data-d="surprise"><span class="gw-door-icon">🔮</span><span><span class="gw-door-name">Surprise me</span><span class="gw-door-desc">A hand of forgotten gems from deep in the archive.</span></span></button>'
      +'</div>'
      +'<div class="gw-foot"><span class="gw-owner-link">This is my archive</span></div>'
      +'</div>';
    document.body.appendChild(w);
    w.querySelector('.gw-close').onclick=close;
    w.addEventListener('click',function(e){if(e.target===w)close()});
    w.querySelector('.gw-owner-link').onclick=function(){setOwner(true);document.body.classList.add('owner');close();if(window.showToast)showToast('Owner mode on — edit tools visible')};
    w.querySelector('[data-d="deal"]').onclick=function(){door(function(){if(window.openDealer)openDealer()})};
    w.querySelector('[data-d="crates"]').onclick=function(){door(function(){
      var sb=document.querySelector('.sidebar');if(sb)sb.classList.add('open');
      var cc=document.getElementById('crate-chips');
      if(cc){cc.style.display='flex';cc.scrollIntoView({behavior:'smooth',block:'center'})}
    })};
    w.querySelector('[data-d="surprise"]').onclick=function(){door(function(){if(window.showRediscover)showRediscover()})};
  }

  if(!isOwner()&&!seenWelcome()){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',showWelcome);
    else showWelcome();
  }
})();
