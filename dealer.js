/* ===== THE SELECTOR ===== Select a ~25-track curated loop from any slice of the archive.
   Spine of bankers + forgotten loves + never-played wild cards, sequenced on a BPM arc.
   Injected into index.html by patch-dealer.py. Relies on globals: DATA, CC, MOODS,
   playPreview, showToast, esc, _doSpotifySave. */
(function(){
'use strict';

/* ---------- slice state ---------- */
var DLR={crates:[],vibes:[],mood:null,yr:null,vinyl:false,gf:[],artist:null,bpm:null,ignored:[]};
var _deal=null;          /* [{t,role}] current deal, sequenced */
var _dealPools=null;     /* {banker:[],forgotten:[],wild:[]} leftover candidates for swaps */
var _poolSize=0;

/* ---------- parser vocab ---------- */
var CRATE_SYN={'indie & rock':'Indie & Rock','indie':'Indie & Rock','rock':'Indie & Rock',
'disco & boogie':'Disco & Boogie','disco':'Disco & Boogie','boogie':'Disco & Boogie',
'soul & r&b':'Soul & R&B','r&b':'Soul & R&B','rnb':'Soul & R&B','soul':'Soul & R&B',
'hip hop':'Hip Hop','hip-hop':'Hip Hop','hiphop':'Hip Hop','rap':'Hip Hop',
'afro & world':'Afro & World','afro':'Afro & World','african':'Afro & World','world':'Afro & World',
'brazilian':'Brazilian','brasil':'Brazilian','brazil':'Brazilian',
'house':'House','jazz':'Jazz','funk':'Funk','downtempo':'Downtempo','electronic':'Electronic'};
var VIBE_SYN={'deep & mellow':'Deep & Mellow','mellow':'Deep & Mellow','deep':'Deep & Mellow','slow':'Deep & Mellow','dusty':'Deep & Mellow','dinner':'Deep & Mellow','dinner party':'Deep & Mellow','cooking':'Deep & Mellow','wine':'Deep & Mellow',
'feel good':'Feel Good','feelgood':'Feel Good','feel-good':'Feel Good','upbeat':'Feel Good','uplifting':'Feel Good','happy':'Feel Good','fun':'Feel Good',
'sunshine':'Sunshine','sunny':'Sunshine','summer':'Sunshine','summery':'Sunshine','warm':'Sunshine',
'groover':'Groover','groovy':'Groover','groove':'Groover','grooves':'Groover',
'peak time':'Peak Time','peak':'Peak Time','bangers':'Peak Time','banger':'Peak Time','high energy':'Peak Time','energetic':'Peak Time','banging':'Peak Time','driving':'Peak Time','uptempo':'Peak Time',
'soulful':'Soulful','smooth':'Soulful','sexy':'Soulful','romantic':'Soulful',
'instrumental journey':'Instrumental Journey','instrumental':'Instrumental Journey',
'dark & moody':'Dark & Moody','dark':'Dark & Moody','moody':'Dark & Moody','brooding':'Dark & Moody',
'ambient':'Ambient','spacey':'Ambient','dreamy':'Ambient','atmospheric':'Ambient',
'chill':'Chill','chilled':'Chill','chillout':'Chill','laid back':'Chill','laidback':'Chill','laid-back':'Chill','relaxed':'Chill','relaxing':'Chill','easy':'Chill'};
/* everyday phrases -> mood presets (checked after exact mood-key match) */
var MOOD_SYN={'late night':'After Midnight','after midnight':'After Midnight','midnight':'After Midnight','small hours':'After Midnight','2am':'After Midnight',
'sunset':'Balearic Sunset','golden hour':'Balearic Sunset','balearic':'Balearic Sunset','beach':'Balearic Sunset','terrace':'Balearic Sunset',
'bbq':'Summer BBQ','barbecue':'Summer BBQ','garden':'Summer BBQ','poolside':'Summer BBQ',
'sunday morning':'Sunday Morning','morning':'Sunday Morning','breakfast':'Sunday Morning','coffee':'Sunday Morning','hangover':'Sunday Morning','lazy sunday':'Sunday Morning',
'party':'Dancefloor','dancefloor':'Dancefloor','dancing':'Dancefloor','club':'Dancefloor','peak hour':'Dancefloor',
'meditation':'Meditative','yoga':'Meditative','zen':'Meditative','sleep':'Meditative',
'work':'Chill Electronic','focus':'Chill Electronic','study':'Chill Electronic',
'cosmic':'Cosmic & Spiritual','spiritual':'Cosmic & Spiritual',
'wedding':'Wedding Party','yacht':'Yacht Rock & Soul Gliding','yacht rock':'Yacht Rock & Soul Gliding'};
var STOPWORDS={'the':1,'a':1,'an':1,'and':1,'&':1,'of':1,'on':1,'in':1,'with':1,'some':1,'me':1,'my':1,'from':1,'for':1,'era':1,'vibes':1,'vibe':1,'music':1,'tracks':1,'stuff':1,
'like':1,'something':1,'please':1,'want':1,'need':1,'give':1,'play':1,'put':1,'get':1,'feeling':1,'kind':1,'sort':1,'session':1,'playlist':1,'songs':1,'song':1,'records':1,'that':1,'this':1};

/* genre vocabulary built lazily from DATA (terms appearing on 3+ tracks) */
var _gvocab=null;
function gvocab(){
  if(_gvocab)return _gvocab;
  var ct={};
  DATA.forEach(function(t){
    if(!t.g)return;
    t.g.split(',').forEach(function(g){g=g.trim().toLowerCase();if(g.length>=4)ct[g]=(ct[g]||0)+1});
  });
  _gvocab={};
  Object.keys(ct).forEach(function(g){if(ct[g]>=3)_gvocab[g]=1});
  return _gvocab;
}

/* artist vocabulary: lowercase first-artist -> display name, for artists with 3+ tracks */
var _avocab=null;
function avocab(){
  if(_avocab)return _avocab;
  var ct={},disp={};
  DATA.forEach(function(t){
    var a=(t.a||'').split(';')[0].trim();
    var k=a.toLowerCase();
    if(k.length<4||STOPWORDS[k])return;
    ct[k]=(ct[k]||0)+1;disp[k]=a;
  });
  _avocab={};
  Object.keys(ct).forEach(function(k){if(ct[k]>=3)_avocab[k]=disp[k]});
  return _avocab;
}

/* parse free text into a slice. Longest phrase wins; crate > vibe > mood > genre on ties. */
function dlrParse(text){
  var S={crates:[],vibes:[],mood:null,yr:null,vinyl:false,gf:[],artist:null,bpm:null,ignored:[]};
  var s=(text||'').toLowerCase().replace(/[‘’']/g,'');
  /* bpm first (so "115-125 bpm" never reads as years) */
  var bm=s.match(/\b(\d{2,3})\s*(?:-|–|—|to)\s*(\d{2,3})\s*bpm\b/);
  if(bm){var b1=parseInt(bm[1]),b2=parseInt(bm[2]);if(b2<b1){var bt=b1;b1=b2;b2=bt}S.bpm=[b1,b2];s=s.replace(bm[0],' ')}
  if(!S.bpm){bm=s.match(/\b(?:around|about|circa)?\s*~?\s*(\d{2,3})\s*bpm\b/);
    if(bm){var bb=parseInt(bm[1]);S.bpm=[bb-6,bb+6];s=s.replace(bm[0],' ')}}
  /* years next (regex), then blank them out */
  var m=s.match(/\b(19\d{2}|20\d{2})\s*(?:-|–|—|to)\s*(19\d{2}|20\d{2}|\d{2})\b/);
  if(m){var y1=parseInt(m[1]),y2=parseInt(m[2]);if(y2<100)y2=Math.floor(y1/100)*100+y2;if(y2<y1){var tmp=y1;y1=y2;y2=tmp}S.yr=[y1,y2];s=s.replace(m[0],' ')}
  if(!S.yr){
    var dm=s.match(/\b(early|mid|late)?\s*((?:19|20)?([2-9]0|00|10))s\b/);
    if(dm){var d=parseInt(dm[3]);var base=(d>=30)?1900+d:2000+d;var a=base,b2=base+9;
      if(dm[1]==='early'){b2=base+4}else if(dm[1]==='mid'){a=base+3;b2=base+6}else if(dm[1]==='late'){a=base+5}
      S.yr=[a,b2];s=s.replace(dm[0],' ')}
  }
  if(!S.yr){var ym=s.match(/\b(19\d{2}|20\d{2})\b/);if(ym){var yy=parseInt(ym[1]);S.yr=[yy-1,yy+1];s=s.replace(ym[0],' ')}}
  if(/\bvinyl\b/.test(s)){S.vinyl=true;s=s.replace(/\bon vinyl\b|\bvinyl only\b|\bvinyl\b/g,' ')}
  /* phrase matching over word array */
  var words=s.split(/\s+/).filter(function(w){return w.length});
  var GV=gvocab();
  var AV=avocab();
  var moodKeys={};Object.keys(MOODS).forEach(function(k){moodKeys[k.toLowerCase()]=k});
  var i=0;
  while(i<words.length){
    var hit=null,hitLen=0;
    for(var L=Math.min(4,words.length-i);L>=1;L--){
      var ph=words.slice(i,i+L).join(' ');
      var cand=null;
      if(CRATE_SYN[ph])cand={k:'crate',v:CRATE_SYN[ph]};
      else if(VIBE_SYN[ph])cand={k:'vibe',v:VIBE_SYN[ph]};
      else if(moodKeys[ph])cand={k:'mood',v:moodKeys[ph]};
      else if(MOOD_SYN[ph])cand={k:'mood',v:MOOD_SYN[ph]};
      else if(GV[ph]&&L>=1&&ph.length>=4)cand={k:'gf',v:ph};
      else if(AV[ph]&&ph.length>=4)cand={k:'artist',v:ph};
      if(cand){hit=cand;hitLen=L;break}
    }
    if(hit){
      if(hit.k==='crate'&&S.crates.indexOf(hit.v)<0)S.crates.push(hit.v);
      else if(hit.k==='vibe'&&S.vibes.indexOf(hit.v)<0)S.vibes.push(hit.v);
      else if(hit.k==='mood'&&!S.mood)S.mood=hit.v;
      else if(hit.k==='gf'&&S.gf.indexOf(hit.v)<0)S.gf.push(hit.v);
      else if(hit.k==='artist'&&!S.artist)S.artist=hit.v;
      i+=hitLen;
    }else{
      if(!STOPWORDS[words[i]]&&words[i].length>2)S.ignored.push(words[i]);
      i++;
    }
  }
  return S;
}

/* canonical display title for the slice */
function dlrTitle(){
  var bits=[];
  if(DLR.artist){var AV=avocab();bits.push('Like '+(AV[DLR.artist]||DLR.artist.replace(/\b\w/g,function(c){return c.toUpperCase()})))}
  if(DLR.yr){
    var y=DLR.yr;
    if(y[0]%10===0&&y[1]===y[0]+9)bits.push((y[0]%100===0?'20':'')+String(y[0]).slice(2)+'s');
    else if(y[1]-y[0]===2)bits.push(String(y[0]+1));
    else bits.push(y[0]+'–'+y[1]);
  }
  bits=bits.concat(DLR.crates);
  if(DLR.mood)bits.push(DLR.mood);
  bits=bits.concat(DLR.gf.map(function(g){return g.replace(/\b\w/g,function(c){return c.toUpperCase()})}));
  bits=bits.concat(DLR.vibes);
  if(DLR.bpm)bits.push(DLR.bpm[0]+'–'+DLR.bpm[1]+' BPM');
  if(DLR.vinyl)bits.push('on Vinyl');
  return bits.length?bits.join(' · '):'The Whole Archive';
}

/* ---------- pool + dealing ---------- */
function moodOk(t,mood){
  if(mood.gf||mood.tf){var gfOk=false,tfOk=false;
    if(mood.gf){var gl=(t.g||'').toLowerCase();gfOk=mood.gf.some(function(g){return gl.indexOf(g)>=0})}
    if(mood.tf){tfOk=t.tags&&mood.tf.some(function(mt){return t.tags.indexOf(mt)>=0})}
    if(!gfOk&&!tfOk)return false}
  if(mood.yr){var ry=parseInt(t.r)||0;if(!ry||ry<mood.yr[0]||ry>mood.yr[1])return false}
  if(t.e<mood.e[0]||t.e>mood.e[1])return false;
  if(t.v<mood.v[0]||t.v>mood.v[1])return false;
  if(t.d<mood.d[0]||t.d>mood.d[1])return false;
  if(t.tp>0&&(t.tp<mood.tp[0]||t.tp>mood.tp[1]))return false;
  if(mood.pop&&t.p<mood.pop)return false;
  return true;
}
/* artist anchor v2: reuse Dig Deeper's frequency-weighted artist-profile scoring
   (_digCompute) so "like X" pools from genuinely adjacent artists, not everything
   sharing a loose crate+genre pair. Cached per artist — _digCompute scans DATA. */
var _anchorCache=null;
function anchorInfo(name){
  if(_anchorCache&&_anchorCache.name===name)return _anchorCache;
  if(typeof _digCompute!=='function'||typeof baseArtist!=='function')return null;
  var keep=window._digPicks;                 /* _digCompute clobbers the dig panel's picks */
  var R;try{R=_digCompute(name)}catch(e){R=null}
  window._digPicks=keep;
  if(!R)return null;
  var seed=new Set(R.at);
  var adj=new Set(R.picks.map(function(t){return baseArtist(t.a)}));
  _anchorCache={name:name,seed:seed,adj:adj,n:R.at.length,exact:R.exactName,traits:R.topGenres};
  return _anchorCache;
}

function dlrPool(S){
  S=S||DLR;
  var mood=S.mood?MOODS[S.mood]:null;
  var anchor=null,anchorLoose=null;
  if(S.artist){
    anchor=anchorInfo(S.artist);
    if(!anchor){
      /* fallback if dig scoring is unavailable: old loose crate+genre overlap */
      anchorLoose={name:S.artist,crates:{},g:{}};
      DATA.forEach(function(t){
        if((t.a||'').split(';')[0].trim().toLowerCase()!==S.artist)return;
        (t.c||[]).forEach(function(c){if(c.indexOf('Uncategor')<0)anchorLoose.crates[c]=1});
        (t.g||'').toLowerCase().split(',').forEach(function(g){g=g.trim();if(g.length>=4)anchorLoose.g[g]=1});
      });
    }
  }
  return DATA.filter(function(t){
    if(!t.sid||t.sid.length!==22)return false;
    if(S.vinyl&&!t.vy)return false;
    if(S.crates.length&&!t.c.some(function(c){return S.crates.indexOf(c)>=0}))return false;
    if(S.vibes.length&&S.vibes.indexOf(t.vb)<0)return false;
    if(S.yr){var r=parseInt(t.r)||0;if(!r||r<S.yr[0]||r>S.yr[1])return false}
    if(S.bpm){if(!(t.tp>0)||t.tp<S.bpm[0]-0.5||t.tp>S.bpm[1]+0.5)return false}
    if(S.gf.length){var gl=(t.g||'').toLowerCase();if(!S.gf.some(function(g){return gl.indexOf(g)>=0}))return false}
    if(mood&&!moodOk(t,mood))return false;
    if(anchor){
      if(!anchor.seed.has(t)&&!anchor.adj.has(baseArtist(t.a)))return false;
    }else if(anchorLoose){
      var fa=(t.a||'').split(';')[0].trim().toLowerCase();
      if(fa!==anchorLoose.name){
        var shareC=(t.c||[]).some(function(c){return anchorLoose.crates[c]});
        var shareG=(t.g||'').toLowerCase().split(',').some(function(g){return anchorLoose.g[g.trim()]});
        if(!shareC||!shareG)return false;
      }
    }
    return true;
  });
}

/* when a slice is too thin to deal, widen it step by step and say what changed */
var VIBE_ADJ={'Deep & Mellow':['Chill','Ambient','Soulful'],'Sunshine':['Feel Good','Groover'],
'Feel Good':['Sunshine','Groover'],'Groover':['Feel Good','Peak Time'],'Peak Time':['Groover','Dark & Moody'],
'Soulful':['Deep & Mellow','Feel Good'],'Instrumental Journey':['Ambient','Deep & Mellow'],
'Ambient':['Chill','Instrumental Journey'],'Dark & Moody':['Ambient','Peak Time'],'Chill':['Deep & Mellow','Ambient']};
var MIN_DEAL=26;
function relaxedPool(){
  var S={crates:DLR.crates.slice(),vibes:DLR.vibes.slice(),mood:DLR.mood,yr:DLR.yr?DLR.yr.slice():null,vinyl:DLR.vinyl,gf:DLR.gf.slice(),artist:DLR.artist,bpm:DLR.bpm?DLR.bpm.slice():null,ignored:[]};
  var notes=[];
  var pool=dlrPool(S);
  if(pool.length<MIN_DEAL&&S.vibes.length){
    var extra=[];
    S.vibes.forEach(function(v){(VIBE_ADJ[v]||[]).forEach(function(av){if(S.vibes.indexOf(av)<0&&extra.indexOf(av)<0)extra.push(av)})});
    if(extra.length){S.vibes=S.vibes.concat(extra);pool=dlrPool(S);notes.push('widened vibe to include '+extra.join(', '))}
  }
  if(pool.length<MIN_DEAL&&S.bpm){
    S.bpm=[S.bpm[0]-10,S.bpm[1]+10];pool=dlrPool(S);notes.push('widened BPM to '+S.bpm[0]+'–'+S.bpm[1]);
  }
  if(pool.length<MIN_DEAL&&S.yr){
    S.yr=[S.yr[0]-5,S.yr[1]+5];pool=dlrPool(S);notes.push('stretched years to '+S.yr[0]+'–'+S.yr[1]);
  }
  if(pool.length<MIN_DEAL&&S.vibes.length){
    S.vibes=[];pool=dlrPool(S);notes.push('let go of the vibe filter');
  }
  if(pool.length<MIN_DEAL&&S.yr){
    S.yr=null;pool=dlrPool(S);notes.push('let go of the year filter');
  }
  return{pool:pool,notes:notes};
}
function bankerScore(t){return (t.n||0)*3+Math.sqrt(t.pc||0)*2}

/* weighted sample without replacement */
function wSample(cands,k,wfn){
  var picks=[],pool=cands.slice();
  while(picks.length<k&&pool.length){
    var tot=0,ws=pool.map(function(c){var w=Math.max(wfn(c),0.001);tot+=w;return w});
    var r=Math.random()*tot,idx=pool.length-1;
    for(var i=0;i<pool.length;i++){r-=ws[i];if(r<=0){idx=i;break}}
    picks.push(pool.splice(idx,1)[0]);
  }
  return picks;
}

var ARTIST_CAP=3;  /* max tracks per primary artist in a deal — "like Marcos Valle" must not become mostly Marcos Valle */
function dealArtist(t){return (t.a||'').split(';')[0].trim().toLowerCase()}
/* wSample with a shared per-artist counter: over-cap picks are discarded and sampling continues */
function wSampleCapped(cands,k,wfn,counts){
  var picks=[],pool=cands.slice();
  while(picks.length<k&&pool.length){
    var tot=0,ws=pool.map(function(c){var w=Math.max(wfn(c),0.001);tot+=w;return w});
    var r=Math.random()*tot,idx=pool.length-1;
    for(var i=0;i<pool.length;i++){r-=ws[i];if(r<=0){idx=i;break}}
    var t=pool.splice(idx,1)[0],a=dealArtist(t);
    if((counts[a]||0)>=ARTIST_CAP)continue;
    counts[a]=(counts[a]||0)+1;picks.push(t);
  }
  return picks;
}

function dealFromPool(pool,total){
  total=Math.min(total||25,pool.length);
  var used={},artistCounts={};
  function take(arr){arr.forEach(function(t){used[t.sid]=1})}
  /* forgotten loves: loved once (4+ lifetime plays), untouched for 3+ years */
  var fCands=pool.filter(function(t){return (t.pc||0)>=4&&!(t.p3||0)})
    .sort(function(a,b){return bankerScore(b)-bankerScore(a)}).slice(0,40);
  var forgotten=wSampleCapped(fCands,Math.min(5,Math.floor(total/5)),bankerScore,artistCounts);take(forgotten);
  /* wild cards: never played, barely playlisted — pure chance from the shelf */
  var wCands=pool.filter(function(t){return !(t.pc||0)&&(t.n||0)<=1&&!used[t.sid]});
  var wild=wSampleCapped(wCands,Math.min(3,Math.floor(total/8)),function(){return 1},artistCounts);take(wild);
  /* bankers: the spine — most playlisted + most played */
  var bCands=pool.filter(function(t){return !used[t.sid]&&bankerScore(t)>=2})
    .sort(function(a,b){return bankerScore(b)-bankerScore(a)}).slice(0,70);
  var bankers=wSampleCapped(bCands,total-forgotten.length-wild.length,function(t){var s=bankerScore(t);return s*s},artistCounts);take(bankers);
  /* thin slice: backfill with best of whatever remains — capped first, then uncapped
     only if the pool genuinely can't fill the deal otherwise */
  var need=total-forgotten.length-wild.length-bankers.length;
  if(need>0){
    var rest=pool.filter(function(t){return !used[t.sid]})
      .sort(function(a,b){return bankerScore(b)-bankerScore(a)}).slice(0,need*3);
    var fill=wSampleCapped(rest,need,function(t){return bankerScore(t)+0.5},artistCounts);take(fill);
    bankers=bankers.concat(fill);
    need=total-forgotten.length-wild.length-bankers.length;
    if(need>0){
      var rest2=pool.filter(function(t){return !used[t.sid]})
        .sort(function(a,b){return bankerScore(b)-bankerScore(a)});
      bankers=bankers.concat(wSample(rest2,need,function(t){return bankerScore(t)+0.5}));
    }
  }
  var entries=bankers.map(function(t){return{t:t,role:'banker'}})
    .concat(forgotten.map(function(t){return{t:t,role:'forgotten'}}))
    .concat(wild.map(function(t){return{t:t,role:'wild'}}));
  _dealPools={
    banker:bCands.filter(function(t){return !used[t.sid]}),
    forgotten:fCands.filter(function(t){return !used[t.sid]}),
    wild:wCands.filter(function(t){return !used[t.sid]})
  };
  return sequenceDeal(entries);
}

/* sequence: BPM arc — open mellow, climb to a peak ~2/3 in, cool down. Avoid artist/album
   adjacency, keep era steps gentle. Tracks without BPM assume the deal's average. */
function sequenceDeal(entries){
  if(entries.length<3)return entries;
  var known=entries.filter(function(e){return e.t.tp>0});
  var avg=known.length?known.reduce(function(s,e){return s+e.t.tp},0)/known.length:110;
  function B(e){return e.t.tp>0?e.t.tp:avg}
  function Y(e){var y=parseInt(e.t.r);return y>1900?y:(e.t.da?Math.floor(e.t.da/100):2015)}
  var bs=entries.map(B).sort(function(a,b){return a-b});
  var lo=bs[Math.floor(bs.length*0.1)],hi=bs[Math.floor(bs.length*0.9)];
  var n=entries.length,peak=Math.max(2,Math.round(n*0.65));
  function target(i){
    if(i<=peak)return lo+(hi-lo)*(i/peak);
    return hi-(hi-lo)*0.55*((i-peak)/Math.max(1,n-1-peak));
  }
  var rem=entries.slice(),out=[];
  for(var i=0;i<n;i++){
    var best=0,bc=Infinity;
    for(var j=0;j<rem.length;j++){
      var e=rem[j],c=Math.abs(B(e)-target(i));
      if(out.length){
        var p=out[out.length-1];
        if(p.t.a.split(';')[0].trim().toLowerCase()===e.t.a.split(';')[0].trim().toLowerCase())c+=30;
        if(p.t.al&&e.t.al&&p.t.al===e.t.al)c+=12;
        c+=Math.min(Math.abs(Y(e)-Y(p)),20)*0.25;
      }
      if(c<bc){bc=c;best=j}
    }
    out.push(rem.splice(best,1)[0]);
  }
  return out;
}

/* ---------- UI ---------- */
var ROLE_META={banker:{label:'banker',cls:'dlr-role-b',title:'A banker — heavily playlisted/played in this slice'},
forgotten:{label:'forgotten love',cls:'dlr-role-f',title:'Loved hard once, untouched for 3+ years'},
wild:{label:'wild card',cls:'dlr-role-w',title:'Never played — a shelf gamble from the same slice'}};
var PRESETS=['Brazilian Sunshine','90s House Deep & Mellow','Indie & Rock 2009-2012','Late Night Jazz','70s Funk','Disco & Boogie Peak Time','Balearic Sunset','Jazz on Vinyl'];

var CSS='\
.dlr-overlay{position:fixed;inset:0;background:rgba(5,5,10,0.82);z-index:1200;display:none;align-items:flex-start;justify-content:center;backdrop-filter:blur(6px);overflow-y:auto;padding:4vh 14px}\
.dlr-overlay.open{display:flex}\
.dlr-modal{background:var(--card);border:1px solid var(--border);border-radius:16px;width:100%;max-width:820px;padding:26px 30px 30px;position:relative;margin-bottom:6vh}\
.dlr-modal h2{font-size:1.45em;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--pink));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;display:inline-block}\
.dlr-sub{color:var(--dim);font-size:0.8em;margin-bottom:14px;line-height:1.5;max-width:600px}\
.dlr-close{position:absolute;top:16px;right:20px;font-size:1.2em;cursor:pointer;color:var(--dim)}.dlr-close:hover{color:var(--text)}\
.dlr-inputrow{display:flex;gap:8px;margin-bottom:10px}\
.dlr-input{flex:1;background:var(--card2);border:1px solid var(--border);border-radius:10px;color:var(--text);padding:11px 14px;font-size:0.95em;font-family:inherit;outline:none;transition:border-color 0.15s}\
.dlr-input:focus{border-color:var(--accent)}\
.dlr-dealbtn{padding:11px 26px;border:none;border-radius:10px;background:linear-gradient(135deg,var(--accent),#e86040);color:#000;font-weight:700;font-size:0.95em;cursor:pointer;font-family:inherit;letter-spacing:0.04em;transition:transform 0.1s,box-shadow 0.15s;box-shadow:0 2px 14px rgba(232,160,64,0.25)}\
.dlr-dealbtn:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(232,160,64,0.4)}\
.dlr-dealbtn:disabled{opacity:0.4;cursor:default;transform:none;box-shadow:none}\
.dlr-poolct{font-size:0.72em;color:var(--dim);margin-bottom:12px;min-height:1.2em}\
.dlr-poolct b{color:var(--accent)}\
.dlr-presets{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}\
.dlr-preset{padding:4px 12px;border-radius:14px;font-size:0.72em;cursor:pointer;background:var(--card2);border:1px solid var(--border);color:var(--dim);transition:all 0.15s;user-select:none}\
.dlr-preset:hover{border-color:var(--accent);color:var(--text)}\
.dlr-preset.dlr-lucky{border-color:var(--purple);color:var(--purple)}\
.dlr-pickers{margin-bottom:6px}\
.dlr-pickrow{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:7px;align-items:center}\
.dlr-picklabel{font-size:0.65em;color:var(--dim);text-transform:uppercase;letter-spacing:0.08em;width:52px;flex-shrink:0}\
.dlr-chip{padding:3px 10px;border-radius:12px;font-size:0.7em;cursor:pointer;background:var(--card2);border:1px solid var(--border);color:var(--dim);transition:all 0.15s;user-select:none;white-space:nowrap}\
.dlr-chip:hover{color:var(--text);border-color:var(--accent)}\
.dlr-chip.on{color:var(--text);border-color:var(--accent);background:rgba(232,160,64,0.12)}\
.dlr-chip .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:1px}\
.dlr-result{margin-top:16px;border-top:1px solid var(--border);padding-top:16px}\
.dlr-rtitle{font-size:1.15em;font-weight:700;margin-bottom:2px}\
.dlr-rsub{font-size:0.74em;color:var(--dim);margin-bottom:8px}\
.dlr-evidence{font-size:0.74em;color:var(--accent);margin-bottom:4px}\
.dlr-cratebar{display:flex;height:4px;border-radius:2px;overflow:hidden;margin-bottom:14px;max-width:420px}\
.dlr-actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}\
.dlr-abtn{padding:7px 16px;border-radius:10px;font-size:0.78em;cursor:pointer;border:1px solid var(--border);background:var(--card2);color:var(--text);font-weight:600;font-family:inherit;transition:all 0.15s}\
.dlr-abtn:hover{border-color:var(--accent)}\
.dlr-abtn.dlr-spotify{background:#1DB954;color:#000;border-color:#1DB954}.dlr-abtn.dlr-spotify:hover{background:#1ed760}\
.dlr-rows{display:flex;flex-direction:column;gap:3px}\
.dlr-row{display:flex;align-items:center;gap:9px;padding:6px 10px;border-radius:8px;background:var(--card2);font-size:0.8em}\
.dlr-row:hover{background:var(--border)}\
.dlr-num{color:var(--dim);font-family:"JetBrains Mono",monospace;font-size:0.85em;width:18px;text-align:right;flex-shrink:0}\
.dlr-tt{flex:1;min-width:0;overflow:hidden}\
.dlr-a{font-weight:600}\
.dlr-t{color:var(--dim)} .dlr-tt .dlr-t::before{content:" — "}\
.dlr-meta{display:block;font-size:0.78em;color:var(--dim);opacity:0.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\
.dlr-bpm{font-family:"JetBrains Mono",monospace;font-size:0.75em;color:var(--dim);width:34px;text-align:right;flex-shrink:0}\
.dlr-role{font-size:0.62em;padding:2px 8px;border-radius:9px;white-space:nowrap;flex-shrink:0;letter-spacing:0.03em}\
.dlr-role-b{background:rgba(232,160,64,0.14);color:var(--accent)}\
.dlr-role-f{background:rgba(64,160,232,0.14);color:var(--accent2)}\
.dlr-role-w{background:rgba(255,105,180,0.14);color:var(--pink)}\
.dlr-swap{cursor:pointer;color:var(--dim);opacity:0.5;flex-shrink:0;transition:all 0.15s;font-size:0.9em}\
.dlr-swap:hover{opacity:1;color:var(--accent)}\
.dlr-row .play-btn{flex-shrink:0}\
.dlr-cardwrap{position:fixed;inset:0;background:rgba(5,5,10,0.9);z-index:1300;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:20px}\
.dlr-cardwrap img{max-width:min(86vw,560px);max-height:72vh;border-radius:6px;box-shadow:0 12px 60px rgba(0,0,0,0.7)}\
.dlr-cardbtns{display:flex;gap:10px}\
@media(max-width:768px){.dlr-modal{padding:18px 16px 22px}.dlr-inputrow{flex-direction:column}.dlr-dealbtn{width:100%}.dlr-picklabel{width:100%}.dlr-role{display:none}.dlr-meta{display:none}}\
';

var _built=false;
function buildUI(){
  if(_built)return;_built=true;
  var st=document.createElement('style');st.textContent=CSS;document.head.appendChild(st);
  var ov=document.createElement('div');ov.className='dlr-overlay';ov.id='dlr-overlay';
  var crateChips=Object.keys(CC).filter(function(c){return c!=='Uncategorized'&&c!=='Uncategorised'}).sort().map(function(c){
    return '<span class="dlr-chip" data-term="'+c+'" data-kind="crate" data-val="'+c+'"><span class="dot" style="background:'+CC[c]+'"></span>'+c+'</span>';
  }).join('');
  var vibes=['Feel Good','Groover','Sunshine','Deep & Mellow','Peak Time','Soulful','Instrumental Journey','Ambient','Dark & Moody','Chill'];
  var vibeChips=vibes.map(function(v){return '<span class="dlr-chip" data-term="'+v+'" data-kind="vibe" data-val="'+v+'">'+v+'</span>'}).join('');
  var decs=[['60s','60s'],['70s','70s'],['80s','80s'],['90s','90s'],['00s','00s'],['10s','10s'],['20s','20s']];
  var decChips=decs.map(function(d){return '<span class="dlr-chip" data-term="'+d[0]+'" data-kind="dec" data-val="'+d[1]+'">'+d[1]+'</span>'}).join('');
  var presetChips=PRESETS.map(function(p){return '<span class="dlr-preset" data-preset="'+p+'">'+p+'</span>'}).join('')
    +'<span class="dlr-preset dlr-lucky" data-preset="*">🎲 Surprise me</span>';
  ov.innerHTML='<div class="dlr-modal">'
    +'<span class="dlr-close" onclick="closeDealer()">✕</span>'
    +'<h2>📻 The Selector</h2>'
    +'<div class="dlr-sub">Tell the Selector what you’re after — crate, vibe, era, mood, any combo — and get a 25-track selection from your own shelves: a spine of bankers, a few forgotten loves, a couple of wild cards. Sequenced, not shuffled.</div>'
    +'<div class="dlr-inputrow"><input class="dlr-input" id="dlr-input" placeholder="Try “Brazilian sunshine”, “dinner party jazz”, “late night 120 bpm”, “like Marcos Valle”…" autocomplete="off"><button class="dlr-dealbtn" id="dlr-deal-btn" onclick="dealNow()">SELECT</button></div>'
    +'<div class="dlr-poolct" id="dlr-poolct"></div>'
    +'<div class="dlr-presets" id="dlr-presets">'+presetChips+'</div>'
    +'<div class="dlr-pickers">'
    +'<div class="dlr-pickrow"><span class="dlr-picklabel">Crate</span>'+crateChips+'</div>'
    +'<div class="dlr-pickrow"><span class="dlr-picklabel">Vibe</span>'+vibeChips+'</div>'
    +'<div class="dlr-pickrow"><span class="dlr-picklabel">Era</span>'+decChips+'<span class="dlr-chip" data-term="vinyl" data-kind="vinyl" data-val="1" style="margin-left:8px">💿 vinyl only</span></div>'
    +'</div>'
    +'<div id="dlr-result"></div>'
    +'</div>';
  document.body.appendChild(ov);
  ov.addEventListener('click',function(e){if(e.target===ov)closeDealer()});
  var inp=document.getElementById('dlr-input');
  var _syncT=null;
  inp.addEventListener('input',function(){clearTimeout(_syncT);_syncT=setTimeout(syncFromInput,120)});
  inp.addEventListener('keydown',function(e){if(e.key==='Enter'){clearTimeout(_syncT);syncFromInput();dealNow()}});
  document.getElementById('dlr-presets').addEventListener('click',function(e){
    var p=e.target.closest('[data-preset]');if(!p)return;
    var v=p.dataset.preset;
    if(v==='*')v=luckySlice();
    inp.value=v;syncFromInput();dealNow();
  });
  ov.querySelectorAll('.dlr-chip').forEach(function(ch){
    ch.addEventListener('click',function(){toggleTerm(ch.dataset.term)});
  });
}

/* a random crate+vibe combo with a decent pool behind it */
function luckySlice(){
  var crates=Object.keys(CC).filter(function(c){return c.indexOf('Uncategor')<0});
  var vibes=['Feel Good','Groover','Sunshine','Deep & Mellow','Peak Time','Soulful','Instrumental Journey','Dark & Moody'];
  for(var tries=0;tries<25;tries++){
    var c=crates[Math.floor(Math.random()*crates.length)];
    var v=vibes[Math.floor(Math.random()*vibes.length)];
    var txt=c+' '+v;
    var save=DLR;DLR=dlrParse(txt);
    var ok=dlrPool().length>=80;DLR=save;
    if(ok)return txt;
  }
  return 'Jazz Feel Good';
}

function toggleTerm(term){
  var inp=document.getElementById('dlr-input');
  var re=new RegExp('(^|\\s)'+term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?=\\s|$)','i');
  if(re.test(inp.value))inp.value=inp.value.replace(re,' ').replace(/\s+/g,' ').trim();
  else inp.value=(inp.value+' '+term).trim();
  syncFromInput();
}

function syncFromInput(){
  var inp=document.getElementById('dlr-input');
  DLR=dlrParse(inp.value);
  var rp=relaxedPool();var pool=rp.pool;_poolSize=pool.length;
  var pc=document.getElementById('dlr-poolct');
  var relaxNote=rp.notes.length?' <span style="color:var(--accent2)">(thin slice — '+rp.notes.join(', ')+')</span>':'';
  if(!inp.value.trim()){pc.innerHTML='No slice named — the Selector will draw from the <b>whole archive</b> ('+pool.length.toLocaleString()+' tracks).'}
  else if(pool.length<8){pc.innerHTML='<span style="color:var(--red)">Only '+pool.length+' tracks in that slice, even after loosening it — name something broader.</span>'}
  else{pc.innerHTML='Selecting <b>'+dlrTitle()+'</b> from <b>'+pool.length.toLocaleString()+'</b> tracks'+relaxNote
    +(DLR.ignored.length?' <span style="opacity:0.6">(ignored: '+DLR.ignored.join(', ')+')</span>':'')}
  /* reflect state on chips */
  document.querySelectorAll('#dlr-overlay .dlr-chip').forEach(function(ch){
    var k=ch.dataset.kind,v=ch.dataset.val,on=false;
    if(k==='crate')on=DLR.crates.indexOf(v)>=0;
    else if(k==='vibe')on=DLR.vibes.indexOf(v)>=0;
    else if(k==='vinyl')on=DLR.vinyl;
    else if(k==='dec'&&DLR.yr){var d=parseInt(v);var base=(d>=30)?1900+d:2000+d;on=DLR.yr[0]===base&&DLR.yr[1]===base+9}
    ch.classList.toggle('on',on);
  });
  document.getElementById('dlr-deal-btn').disabled=pool.length<8;
}

window.openDealer=function(){
  buildUI();
  document.getElementById('dlr-overlay').classList.add('open');
  syncFromInput();
  if(window.innerWidth>768)document.getElementById('dlr-input').focus();
};
window.closeDealer=function(){
  var ov=document.getElementById('dlr-overlay');if(ov)ov.classList.remove('open');
};

var _dealNotes=[];
window.dealNow=function(){
  var rp=relaxedPool();
  if(rp.pool.length<8){showToast('Slice too thin — loosen it up');return}
  _poolSize=rp.pool.length;_dealNotes=rp.notes;
  _deal=dealFromPool(rp.pool,25);
  renderDeal();
};

window.dlrSwap=function(i){
  if(!_deal||!_deal[i])return;
  var e=_deal[i];
  var swapCounts={};
  _deal.forEach(function(d,j){if(j!==i)swapCounts[dealArtist(d.t)]=(swapCounts[dealArtist(d.t)]||0)+1});
  var cands=(_dealPools[e.role]||[]).filter(function(t){
    return !_deal.some(function(d){return d.t.sid===t.sid})&&(swapCounts[dealArtist(t)]||0)<ARTIST_CAP;
  });
  if(!cands.length){showToast('No more '+ROLE_META[e.role].label+'s in this slice');return}
  var pick=wSample(cands,1,e.role==='wild'?function(){return 1}:bankerScore)[0];
  _deal[i]={t:pick,role:e.role};
  renderDeal();
};

function dealStatsLine(){
  var ts=_deal.map(function(e){return e.t});
  var bpms=ts.filter(function(t){return t.tp>0}).map(function(t){return Math.round(t.tp)});
  var yrs=ts.map(function(t){return parseInt(t.r)}).filter(function(y){return y>1900});
  var bits=[ts.length+' tracks'];
  if(bpms.length)bits.push(Math.min.apply(null,bpms)+'–'+Math.max.apply(null,bpms)+' BPM');
  if(yrs.length)bits.push(Math.min.apply(null,yrs)+'–'+Math.max.apply(null,yrs));
  bits.push('selected from '+_poolSize.toLocaleString());
  return bits.join(' · ');
}
function crateShares(){
  var ct={},tot=0;
  _deal.forEach(function(e){var c=(e.t.c||[])[0];if(c&&c.indexOf('Uncategor')<0){ct[c]=(ct[c]||0)+1;tot++}});
  return Object.keys(ct).map(function(c){return{c:c,n:ct[c],f:ct[c]/Math.max(tot,1)}}).sort(function(a,b){return b.n-a.n});
}

function renderDeal(){
  var el=document.getElementById('dlr-result');
  var title=dlrTitle();
  var bar=crateShares().map(function(s){return '<div style="flex:'+s.n+';background:'+(CC[s.c]||'#555')+'" title="'+s.c+' ×'+s.n+'"></div>'}).join('');
  var rowsH=_deal.map(function(e,i){
    var t=e.t,rm=ROLE_META[e.role];
    return '<div class="dlr-row">'
      +'<span class="dlr-num">'+String(i+1).padStart(2,'0')+'</span>'
      +'<span class="play-btn" onclick="playPreview(\''+t.sid+'\',this)" title="Play">▶</span>'
      +'<div class="dlr-tt"><span class="dlr-a">'+esc(t.a.split(';')[0])+'</span><span class="dlr-t">'+esc(t.t)+'</span>'
      +'<span class="dlr-meta">'+esc(t.al||'')+(t.r?' · '+t.r:'')+'</span></div>'
      +'<span class="dlr-bpm">'+(t.tp>0?Math.round(t.tp):'')+'</span>'
      +'<span class="dlr-role '+rm.cls+'" title="'+rm.title+'">'+rm.label+'</span>'
      +'<span class="dlr-swap" onclick="dlrSwap('+i+')" title="Swap this card for another from the same pile">↻</span>'
      +'</div>';
  }).join('');
  /* factual evidence line when an artist anchors the pool — counts and traits, no prose */
  var evid='';
  if(DLR.artist&&_anchorCache&&_anchorCache.name===DLR.artist){
    evid='<div class="dlr-evidence">Based on '+_anchorCache.n+' '+esc(_anchorCache.exact)+' track'+(_anchorCache.n>1?'s':'')
      +' in the archive · strongest shared traits: '+esc(_anchorCache.traits)+'</div>';
  }
  el.innerHTML='<div class="dlr-result">'
    +'<div class="dlr-rtitle">'+esc(title)+'</div>'
    +evid
    +'<div class="dlr-rsub">'+dealStatsLine()+(_dealNotes.length?' · <span style="color:var(--accent2)">'+_dealNotes.join(', ')+'</span>':'')+'</div>'
    +'<div class="dlr-cratebar">'+bar+'</div>'
    +'<div class="dlr-actions">'
    +'<button class="dlr-abtn dlr-spotify" id="dlr-save-btn" onclick="saveDealToSpotify(this)">💚 Save to Spotify</button>'
    +'<button class="dlr-abtn" onclick="showEraCard()">🖼️ Era Card</button>'
    +'<button class="dlr-abtn" onclick="dealNow()">↻ Reselect</button>'
    +'</div>'
    +'<div class="dlr-rows">'+rowsH+'</div>'
    +'</div>';
  el.scrollIntoView({behavior:'smooth',block:'nearest'});
}

window.saveDealToSpotify=function(btn){
  if(!_deal)return;
  var mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var d=new Date();
  var name='The Selector: '+dlrTitle()+' — '+mn[d.getMonth()]+' '+d.getFullYear();
  _doSpotifySave(_deal.map(function(e){return e.t}),name,btn);
};

/* ---------- era card (canvas sleeve) ---------- */
window.showEraCard=function(){
  if(!_deal)return;
  var ready=(document.fonts&&document.fonts.ready)?document.fonts.ready:Promise.resolve();
  Promise.all([ready,(document.fonts?document.fonts.load('700 64px Inter'):0),(document.fonts?document.fonts.load('400 22px "JetBrains Mono"'):0)])
    .then(function(){drawEraCard()}).catch(function(){drawEraCard()});
};
function drawEraCard(){
  var W=1080,H=1080,P=76;
  var cv=document.createElement('canvas');cv.width=W;cv.height=H;
  var x=cv.getContext('2d');
  var shares=crateShares();
  var domColor=shares.length?(CC[shares[0].c]||'#e8a040'):'#e8a040';
  var mn=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  var dt=new Date();
  /* background — near-black with a soft wash of the slice colour */
  x.fillStyle='#0c0c12';x.fillRect(0,0,W,H);
  var rg=x.createRadialGradient(W*0.18,H*0.12,60,W*0.18,H*0.12,1100);
  rg.addColorStop(0,domColor+'1f');rg.addColorStop(0.55,domColor+'08');rg.addColorStop(1,'rgba(0,0,0,0)');
  x.fillStyle=rg;x.fillRect(0,0,W,H);
  /* the record — anchored bottom-right, half off the sleeve */
  var cx=W-150,cy=H-70,R=430;
  x.save();
  /* drop shadow behind the disc */
  x.beginPath();x.arc(cx-14,cy-8,R,0,7);x.fillStyle='rgba(0,0,0,0.55)';x.fill();
  /* disc body */
  var dg=x.createRadialGradient(cx-R*0.45,cy-R*0.45,40,cx,cy,R);
  dg.addColorStop(0,'#23232e');dg.addColorStop(0.5,'#16161e');dg.addColorStop(1,'#101016');
  x.beginPath();x.arc(cx,cy,R,0,7);x.fillStyle=dg;x.fill();
  /* crate-share ring on the outer band */
  var a0=-Math.PI*0.62;
  shares.forEach(function(s){
    var a1=a0+s.f*Math.PI*2;
    x.beginPath();x.strokeStyle=CC[s.c]||'#555';x.globalAlpha=0.92;x.lineWidth=44;
    x.arc(cx,cy,R-36,a0+0.015,Math.max(a1-0.015,a0+0.02));x.stroke();
    a0=a1;
  });
  x.globalAlpha=1;
  /* grooves */
  for(var r=R-78;r>150;r-=8){
    x.beginPath();x.strokeStyle='rgba(255,255,255,'+(r%24<8?0.075:0.035)+')';x.lineWidth=1;
    x.arc(cx,cy,r,0,7);x.stroke();
  }
  /* rim light, top-left arc */
  x.beginPath();x.strokeStyle='rgba(255,255,255,0.22)';x.lineWidth=2;
  x.arc(cx,cy,R-1,Math.PI*0.78,Math.PI*1.52);x.stroke();
  /* centre label */
  x.beginPath();x.fillStyle=domColor;x.arc(cx,cy,138,0,7);x.fill();
  var lg=x.createRadialGradient(cx-50,cy-50,10,cx,cy,138);
  lg.addColorStop(0,'rgba(255,255,255,0.16)');lg.addColorStop(1,'rgba(0,0,0,0.28)');
  x.beginPath();x.fillStyle=lg;x.arc(cx,cy,138,0,7);x.fill();
  x.fillStyle='rgba(0,0,0,0.78)';x.textAlign='center';
  x.font='700 30px Inter, sans-serif';
  x.fillText('THE DEALER',cx,cy-36);
  x.font='500 20px Inter, sans-serif';
  x.fillText(mn[dt.getMonth()]+' '+dt.getFullYear(),cx,cy+52);
  x.beginPath();x.fillStyle='#0c0c12';x.arc(cx,cy,10,0,7);x.fill();
  x.beginPath();x.strokeStyle='rgba(0,0,0,0.35)';x.lineWidth=1.5;x.arc(cx,cy,138,0,7);x.stroke();
  x.restore();
  /* eyebrow */
  x.textAlign='left';
  x.font='500 21px "JetBrains Mono", monospace';
  x.fillStyle=domColor;
  x.fillText('THE DEALER  ·  BEN’S DJ ARCHIVE',P,P+10);
  /* title */
  var title=dlrTitle();
  x.fillStyle='#f4f4f8';
  var fs=84;var maxW=W-P*2;
  function wrap(){
    x.font='700 '+fs+'px Inter, sans-serif';
    var words=title.split(' '),lines=[],cur='';
    words.forEach(function(w){
      var t2=cur?cur+' '+w:w;
      if(x.measureText(t2).width>maxW&&cur){lines.push(cur);cur=w}else cur=t2;
    });
    if(cur)lines.push(cur);
    return lines;
  }
  var lines=wrap();
  while(lines.length>3&&fs>46){fs-=8;lines=wrap()}
  var ty=P+62+fs*0.86;
  lines.forEach(function(l){x.fillText(l,P-3,ty);ty+=fs*1.1});
  /* subtitle */
  x.fillStyle='rgba(255,255,255,0.5)';x.font='500 28px Inter, sans-serif';
  x.fillText(dealStatsLine().replace(/ · selected from.*$/,''),P,ty+8);
  ty+=8;
  /* tracklist — left column, clear of the disc */
  var listTop=Math.max(ty+76,560);
  var rows=Math.min(10,_deal.length,Math.floor((H-110-listTop)/41));
  var ly=listTop;
  x.font='400 23px "JetBrains Mono", monospace';
  var maxTW=W-150-R-P-30; /* stop left of the disc */
  if(maxTW<420)maxTW=420;
  _deal.slice(0,rows).forEach(function(e,i){
    var t=e.t;
    x.fillStyle=domColor;x.globalAlpha=0.9;
    x.fillText(String(i+1).padStart(2,'0'),P,ly);
    x.globalAlpha=1;x.fillStyle='rgba(255,255,255,0.82)';
    var full=t.a.split(';')[0]+' — '+t.t;
    var s=full;
    while(x.measureText(s).width>maxTW&&s.length>6)s=s.slice(0,-1);
    if(s!==full)s=s.replace(/\s+$/,'')+'…';
    x.fillText(s,P+48,ly);
    ly+=41;
  });
  if(_deal.length>rows){
    x.fillStyle='rgba(255,255,255,0.38)';
    x.fillText('+ '+(_deal.length-rows)+' more in the loop',P+48,ly);
  }
  /* footer */
  x.font='500 20px Inter, sans-serif';
  x.fillStyle='rgba(255,255,255,0.34)';
  x.fillText('one DJ’s ears, no algorithm',P,H-44);
  showCardPreview(cv);
}
function showCardPreview(cv){
  var wrap=document.createElement('div');wrap.className='dlr-cardwrap';
  var img=document.createElement('img');img.src=cv.toDataURL('image/png');
  var btns=document.createElement('div');btns.className='dlr-cardbtns';
  var dl=document.createElement('button');dl.className='dlr-abtn dlr-spotify';dl.textContent='⬇ Download PNG';
  dl.onclick=function(){
    var a=document.createElement('a');
    a.download='selector-'+dlrTitle().toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'.png';
    a.href=img.src;a.click();
  };
  var cl=document.createElement('button');cl.className='dlr-abtn';cl.textContent='Close';
  cl.onclick=function(){wrap.remove()};
  wrap.addEventListener('click',function(e){if(e.target===wrap)wrap.remove()});
  btns.appendChild(dl);btns.appendChild(cl);
  wrap.appendChild(img);wrap.appendChild(btns);
  document.body.appendChild(wrap);
}

/* entry button + deep link */
function mount(){
  var qa=document.querySelector('.cc-quick-actions');
  if(qa&&!document.getElementById('btn-dealer')){
    var b=document.createElement('button');
    b.className='cc-quick-btn';b.id='btn-dealer';
    b.style.cssText='background:linear-gradient(135deg,rgba(232,160,64,0.18),rgba(232,64,96,0.18));border-color:var(--accent);color:var(--accent);font-weight:700';
    b.innerHTML='📻 The Selector';
    b.onclick=window.openDealer;
    qa.insertBefore(b,qa.firstChild);
  }
  if(/#(dealer|selector)\b/.test(location.hash))window.openDealer();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
window.addEventListener('hashchange',function(){if(/#(dealer|selector)\b/.test(location.hash))window.openDealer()});

/* expose pure core for testing */
window._dlrCore={parse:dlrParse,pool:dlrPool,deal:dealFromPool,seq:sequenceDeal,title:dlrTitle,setSlice:function(s){DLR=s},getSlice:function(){return DLR}};
})();
