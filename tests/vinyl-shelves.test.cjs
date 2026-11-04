const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../guest.js'),'utf8');
const selection=source.slice(source.indexOf('  function E(s)'),source.indexOf('  function shuffleShelf('));
function shelves(data,records){
  class Today extends Date {constructor(...args){super(...(args.length?args:['2026-11-04T20:00:00Z']));}}
  const ctx={DATA:data,Date:Today,window:{},localStorage:{getItem:()=>null},setTimeout,clearTimeout};
  vm.createContext(ctx);vm.runInContext(selection,ctx);ctx._vinylRecords=records;ctx.VINYL_OVERRIDES=[];
  return ctx;
}
function track(n,more={}){return {sid:String(n).padStart(22,'0'),a:'Artist '+n,t:'Song '+n,al:'Original album '+n,da:202001,vy:1,did:'100',c:['Jazz'],...more};}
function record(did,tracks,more={}){return {did,a:'Various Artists',al:'The compilation',r:1974,da:202611,added:'2026-11-04 11:00:00',art:'https://example.test/real-sleeve.jpg',tracks:tracks.map(({sid,a,t})=>({sid,a,t})),...more};}
test('an owned compilation is one card with its purchase date and exact release link',()=>{
  const data=[1,2,3,4].map(n=>track(n));const ctx=shelves(data,[record('100',data)]);
  const before=JSON.stringify(data),html=ctx.freshVinylShelf();
  assert.equal((html.match(/class="gh-card"/g)||[]).length,1);
  assert.match(html,/data-artist="Various Artists"/);assert.match(html,/data-album="The compilation"/);
  assert.match(html,/data-did="100"/);assert.match(html,/added Nov ’26/);assert.match(html,/1974/);
  assert.equal(JSON.stringify(data),before);
});
test('two compilations both qualify even if the same artist dominates their tracks',()=>{
  const a=[1,2,3,4].map(n=>track(n,{a:'Same Artist'}));
  const b=[5,6,7,8].map(n=>track(n,{a:'Same Artist',did:'200'}));
  const ctx=shelves([...a,...b],[record('100',a),record('200',b,{al:'Second compilation',added:'2026-11-04 12:00:00'})]);
  const html=ctx.freshVinylShelf();assert.equal((html.match(/class="gh-card"/g)||[]).length,2);
  assert.ok(html.indexOf('Second compilation')<html.indexOf('The compilation'));
});
test('buying one compilation cut does not imply ownership of its original album',()=>{
  const oldAlbum=[1,2,3,4].map(n=>track(n,{a:'First artist',al:'Not owned as an album',vy:n===1?1:0,da:202611}));
  const other=[5,6,7].map(n=>track(n));const ctx=shelves([...oldAlbum,...other],[record('100',[oldAlbum[0],...other])]);
  const html=ctx.freshVinylShelf();assert.doesNotMatch(html,/data-album="Not owned as an album"/);
  assert.equal((html.match(/class="gh-card"/g)||[]).length,1);
});
test('singles, unplayable records and missing sleeves stay off the shelf',()=>{
  for(const scenario of ['single','offline','no-art']){
    const data=Array.from({length:scenario==='single'?2:4},(_,i)=>track(i+1,scenario==='offline'?{sid:'spotify:local:'+i}:{}));
    const ctx=shelves(data,[record('100',data,scenario==='no-art'?{art:''}:{})]);
    assert.equal(ctx.freshVinylShelf(),'');
  }
});
test('specific vinyl pins and prior exclusions still apply',()=>{
  const pinned=[track(1,{did:'37291038'}),track(2,{did:'37291038'})];
  const excluded=[3,4,5,6].map(n=>track(n,{did:'13927173'}));
  const ctx=shelves([...pinned,...excluded],[record('37291038',pinned,{a:'Ron Trent',al:'Electric Jungle'}),record('13927173',excluded,{al:'Excluded compilation'})]);
  const html=ctx.freshVinylShelf();assert.match(html,/Electric Jungle/);assert.doesNotMatch(html,/Excluded compilation/);
});
test('record lookup survives a later Spotify match and a record appears only once',()=>{
  const data=[1,2,3,4].map(n=>track(n));const rec=record('100',data);rec.tracks[0].sid='spotify:local:old-placeholder';
  const ctx=shelves(data,[rec]);assert.match(ctx.freshVinylShelf(),/The compilation/);
  assert.equal(ctx.freshVinylShelf(),'');
});
test('the Cuban boxset mix cannot reappear as a loose compilation track',()=>{
  const data=[track(1,{a:'FA-5',al:'Cuban 45s (DJ Mix)',vy:0,p1:25,r:2026})];
  const ctx=shelves(data,[]);assert.equal(ctx.onRepeatShelf(),'');
});
