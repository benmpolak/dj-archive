// Read-only Job 2 viewport review. Isolated browsers; no service writes or audio.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.env.ARCHIVE_REVIEW_ROOT||path.join(__dirname,'..')),phase=process.env.ARCHIVE_REVIEW_PHASE||'after';
const output=process.env.ARCHIVE_REVIEW_OUTPUT||path.join('/private/tmp','archive-job2-review',phase);fs.mkdirSync(output,{recursive:true});
(async()=>{
 const server=http.createServer((req,res)=>{const name=new URL(req.url,'http://local').pathname;const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));if(!file.startsWith(root+path.sep)||/(?:^|\/)\.(?:git|env)|_backup/.test(name))return res.writeHead(404).end();try{const body=fs.readFileSync(file);res.writeHead(200,{'Content-Type':{'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.woff2':'font/woff2'}[path.extname(file)]||'application/octet-stream'});res.end(body);}catch{res.writeHead(404).end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--mute-audio']});const results=[];
 try{for(const width of [1280,390,320]){
  const context=await browser.newContext({viewport:{width,height:844},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],writes=[];
  await page.clock.setFixedTime(new Date('2026-11-09T12:00:00Z'));
  await page.addInitScript(()=>{let seed=91126;Math.random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};});
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){writes.push(r.method()+' '+new URL(r.url()).pathname);return route.abort();}if(r.resourceType()==='media')return route.abort();if(new URL(r.url()).origin!==origin&&r.resourceType()!=='image')return route.abort();return route.continue();});
  for(const [name,url,waitFor]of [['discover','index.html','#guest-hero'],['archive','index.html?view=records','#tbody tr'],['gigs','gigs.html','.row'],['gigs-share','gigs-share.html','.row']]){
   await page.goto(origin+'/'+url,{waitUntil:'domcontentloaded'});await page.locator(waitFor).first().waitFor();await page.waitForTimeout(500);await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));await page.waitForTimeout(100);
   const metrics=await page.evaluate(()=>{const visible=n=>!!n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden';const box=n=>{const r=n.getBoundingClientRect();return{top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height,width:r.width};};return{overflow:document.documentElement.scrollWidth>innerWidth,pageHeight:document.documentElement.scrollHeight,scrollY,rows:[...document.querySelectorAll('#tbody tr')].filter(visible).slice(0,8).map(box),gigs:[...document.querySelectorAll('.row')].filter(visible).map(box),search:document.querySelector('#search')&&visible(document.querySelector('#search'))?box(document.querySelector('#search')):null,filters:document.querySelector('.filters')?box(document.querySelector('.filters')):null,header:document.querySelector('.music-nav')?box(document.querySelector('.music-nav')):null};});
   await page.screenshot({path:path.join(output,name+'-'+width+'.png'),animations:'disabled'});
   if(name.startsWith('gigs'))await page.screenshot({path:path.join(output,name+'-full-'+width+'.png'),fullPage:true,animations:'disabled'});
   results.push({phase,screen:name,width,...metrics});
   if(phase==='after'){
    assert(!metrics.overflow,'No page overflow: '+name+' '+width);
    if(name==='archive'){
     assert(metrics.search&&metrics.search.top>=0&&metrics.search.bottom<=844,'Search visible on opening');
     if(width===1280)assert(metrics.rows[0].top<=844/3,'First desktop track in top third');
     if(width===390)assert(metrics.rows.filter(r=>r.top>=0&&r.bottom<=844).length>=4,'At least four full tracks visible on phone');
    }
    if(name.startsWith('gigs'))assert(metrics.gigs.length&&metrics.gigs[0].top>=0&&metrics.gigs[0].bottom<=844,'First gig visible on opening');
   }
  }
  assert.deepEqual(writes,[],'No service writes');assert.deepEqual(errors,[],'No uncaught browser errors');await context.close();
 }
 fs.writeFileSync(path.join(output,'metrics.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results.map(({rows,gigs,...r})=>({...r,visibleTracks:rows.filter(x=>x.top>=0&&x.bottom<=844).length,firstTrack:rows[0]?.top,gigRows:gigs.length,firstGig:gigs[0]?.top}))));
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
