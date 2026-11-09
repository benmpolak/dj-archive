/* Local presentation regression: no venue fetches, media or account actions.
   GIG_REVIEW_ROOT points to an isolated no-fetch build. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const repo = path.resolve(__dirname, '..');
const review = process.env.GIG_REVIEW_ROOT || repo;
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'gig-presentation-test-'));
const visible = '.gig-row:not([hidden])';
const errors = [];
function expectEqual(actual, expected, message) { assert.deepEqual(actual, expected, message); }
execFileSync('python3', ['-c', String.raw`
import importlib.util, sys
from pathlib import Path
from datetime import date
spec=importlib.util.spec_from_file_location('g', Path(sys.argv[1])/'gigs-fetch.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
g.TODAY=date(2026,11,9)
def row(day, artist, **extra):
    value={'date':day,'title':artist+' live','venue':'Fixture Venue','url':'https://tickets.example.test/'+artist.replace(' ','-')+'/'+day,'source':'RA','how':'lineup','score':20,'etype':'gig','first_seen':'2026-11-08','all_names':[artist,'Guest Performer'],'co':[],'artist':{'name':artist,'tracks':3,'plays':1,'p1':1,'crate':'Uncategorized','max_da':202611}}
    value.update(extra);return value
rows=[]
for day in ['2026-11-30','2026-12-01','2026-12-02']: rows.append(row(day,'Month Artist'))
for day in ['2026-11-12','2026-11-13','2026-11-14','2026-11-15','2026-11-16']: rows.append(row(day,'Weekend Artist'))
for day in ['2026-12-09','2026-12-10']: rows.append(row(day,'Range Artist'))
for day in ['2026-11-08','2026-11-09','2026-11-10']: rows.append(row(day,'Today Artist'))
rows.append(row('2026-11-11','Calendar Artist',title='Special, duo; evening\\show',source='RonnieSongkick',checked_at='2026-11-06'))
weak=row('2026-11-17','Weak Artist');weak['artist']['tracks']=1;rows.append(weak)
for public in [False,True]:
 g.render(rows,50,10,'Existing source warning',str(Path(sys.argv[2])/('fixture-share.html' if public else 'fixture.html')),public=public,generated='2026-11-06')
`, repo, temp], {stdio:'pipe'});

(async () => {
  const server = http.createServer((request, response) => {
    let pathname = decodeURIComponent(new URL(request.url, 'http://local').pathname);
    const target = path.join(pathname.startsWith('/fixture') ? temp : review, pathname);
    try {const data = fs.readFileSync(target);response.writeHead(200, {'Content-Type':target.endsWith('.css')?'text/css':'text/html'});response.end(data);}
    catch {response.writeHead(404).end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  async function newPage(width=390) {
    const page=await browser.newPage({viewport:{width,height:844},acceptDownloads:true});
    await page.clock.setFixedTime(new Date('2026-11-09T12:00:00Z'));
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
    return page;
  }
  async function dates(page) {return page.locator(visible).evaluateAll(rows=>rows.flatMap(row=>[...row.querySelectorAll('.gig-date-detail:not([hidden])')].map(x=>x.dataset.d)));}
  async function label(page,artist) {return page.locator('.gig-row[data-artist="'+artist+'"] .date-range').textContent();}
  async function seedSaved(page, keys) {await page.evaluate(keys=>localStorage.setItem('gr_saved_gigs_v1',JSON.stringify(Object.fromEntries(keys.map(k=>[k,1])))),keys);}
  const measurements=[];
    // Expected counts come from source-date payloads, so a listing refresh is safe.
    // Pixel limits retain the Job 2 acceptance baseline; synthetic dates stay fixed.
  try {
    for (const width of [1280,390,320]) for (const file of ['gigs.html','gigs-share.html']) {
      const page=await newPage(width);
      await page.goto(origin+'/'+file);
      const measurement=await page.evaluate(()=>{
        const all=[...document.querySelectorAll('.gig-row')].map(el=>({el,items:JSON.parse(el.dataset.members).filter(x=>x.d>='2026-11-09')})),rows=all.filter(x=>!x.el.hidden).map(x=>x.el),first=rows[0].getBoundingClientRect();
        const expectedRows=all.filter(x=>x.items.some(m=>m.tracks>=3)).length,expectedDates=all.flatMap(x=>x.items).filter(x=>x.tracks>=3).length,allRows=all.filter(x=>x.items.length).length,allDates=all.reduce((n,x)=>n+x.items.length,0);
        const box=selector=>{const r=rows[0].querySelector(selector).getBoundingClientRect();return {width:r.width,height:r.height}};
        return {expectedRows,expectedDates,allRows,allDates,height:document.documentElement.scrollHeight,overflow:document.documentElement.scrollWidth>innerWidth,firstTop:first.top,firstBottom:first.bottom,rows:rows.length,sticky:document.querySelector('.filters').getBoundingClientRect().height,save:box('.group-save'),tickets:box('.tix'),dates:rows.reduce((sum,r)=>sum+r.querySelectorAll('.gig-date-detail:not([hidden])').length,0)};
      });
      measurements.push({width,file,...measurement});
      expectEqual(measurement.rows,measurement.expectedRows,'default grouped rows');expectEqual(measurement.dates,measurement.expectedDates,'default original dates');
      assert(!measurement.overflow,'no document horizontal overflow');assert(measurement.firstBottom<844,'first listing visible');
      assert(measurement.sticky<=64,'one-line sticky bar');
      expectEqual(await page.locator('.filters').evaluate(e=>getComputedStyle(e).position),'sticky','quick controls really remain pinned');
      assert(measurement.save.width>=44&&measurement.save.height>=44,'44px save');assert(measurement.tickets.width>=44&&measurement.tickets.height>=44,'44px Tickets');
      if(width===390) assert(measurement.height<(file==='gigs.html'?19514:16387),'less than one third baseline length');
      expectEqual(await page.locator('#scope-toggle').textContent(),'Show all '+measurement.allDates+' shows');
      assert(await page.locator('#filter-more').isHidden());
      for(const selector of ['#q','.fc-range[data-range="weekend"]','.fc-range[data-range="30"]','#fsaved','#filters-toggle']) {
        await page.locator(selector).scrollIntoViewIfNeeded();
        assert(await page.locator(selector).isVisible(),'default control available without Filters: '+selector);
        if(width<560&&selector!=='#q'){const b=await page.locator(selector).boundingBox();assert(b.x>=0&&b.x+b.width<=width,'phone quick control fully visible: '+selector)}
      }
      await page.locator('#filters-toggle').click();assert(await page.locator('#filter-more').isVisible());
      expectEqual(await page.locator('.filters').evaluate(e=>e.getBoundingClientRect().height),measurement.sticky,'drawer leaves pinned height unchanged');
      assert(await page.locator('#venue').isVisible());assert(await page.locator('.fc-mo').first().isVisible());
      assert(await page.locator('#venue').evaluate(e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2))}),'open drawer controls are above listing cards');
      assert(!await page.locator('.fc-c[data-c="Uncategorized"]').count());
      const initialPanel=await page.locator('#filter-more').boundingBox();assert(initialPanel.y>=0&&initialPanel.y+initialPanel.height<=844,'initial drawer stays within viewport');
      await page.keyboard.press('Escape');assert(await page.locator('#filter-more').isHidden());
      await page.evaluate(()=>window.scrollTo(0,1500));
      expectEqual(Math.round((await page.locator('.filters').boundingBox()).y),0,'quick bar stays at viewport top while scrolling');
      assert(await page.locator('.music-nav').evaluate(e=>e.getBoundingClientRect().bottom<0),'header navigation scrolls clear of pinned controls');
      await page.locator('#filters-toggle').click();
      const scrolledPanel=await page.locator('#filter-more').boundingBox();assert(scrolledPanel.y>=62&&scrolledPanel.y+scrolledPanel.height<=844,'scrolled drawer opens inside viewport below quickbar');
      await page.keyboard.press('Escape');await page.evaluate(()=>window.scrollTo(0,0));
      await page.locator('#scope-toggle').click();expectEqual(await page.locator(visible).count(),measurement.allRows,'all grouped rows');
      expectEqual((await dates(page)).length,measurement.allDates,'all source dates retained');
      await page.locator('#scope-toggle').click();expectEqual(await page.locator(visible).count(),measurement.expectedRows);
      const groupData=await page.locator(visible).evaluateAll(rows=>rows.map((el,index)=>({index,key:el.dataset.key,artist:el.dataset.artist,items:JSON.parse(el.dataset.members).filter(x=>x.d>='2026-11-09'&&x.tracks>=3)})).find(row=>row.items.length>1));
      // Real data may occasionally have no consecutive run; fixed fixtures always do.
      if(groupData){
        const group=page.locator(visible).nth(groupData.index);
        await group.locator('.dates-toggle').click();assert(await group.evaluate(e=>e.open),'group Tickets opens date choices');
        expectEqual(await group.locator('.gig-date-detail:not([hidden]) .tix').count(),groupData.items.length);
        assert(await group.locator('.hear-link').isVisible());
        const playBox=await group.locator('.sp-link').boundingBox();assert(playBox.width>=44&&playBox.height>=44);
        const selected=groupData.items[groupData.items.length-1];
        await seedSaved(page,[selected.key]);
        await page.goto(origin+'/'+file+'?saved=1');expectEqual(await page.locator(visible).count(),1);
        expectEqual(await dates(page),[selected.d],'old later-night save opens correct group/date');
        await page.locator(visible+' .group-save').click();expectEqual(await page.locator(visible).count(),0);
        expectEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('gr_saved_gigs_v1'))),{});
      }
      await page.close();
    }
    for(const file of ['fixture.html','fixture-share.html']) {
      const page=await newPage();
      await page.goto(origin+'/'+file);
      expectEqual(await label(page,'Today Artist'),'9–10 Nov','past member removed from live date range');
      expectEqual(await label(page,'Month Artist'),'30 Nov – 2 Dec');
      assert(!(await page.locator('body').innerText()).includes('1 plays'));
      await page.goto(origin+'/'+file+'?mo=2026-12');
      expectEqual(await label(page,'Month Artist'),'1–2 Dec','cross-month range narrowed to chosen month');
      expectEqual(await dates(page),['2026-12-01','2026-12-02','2026-12-09','2026-12-10']);
      await page.goto(origin+'/'+file+'?mo=2026-11');expectEqual(await label(page,'Month Artist'),'30 Nov');
      await page.goto(origin+'/'+file+'?range=weekend');expectEqual(await dates(page),['2026-11-13','2026-11-14','2026-11-15']);expectEqual(await label(page,'Weekend Artist'),'13–15 Nov');
      await page.goto(origin+'/'+file+'?range=30');expectEqual(await label(page,'Range Artist'),'9 Dec');assert(!(await dates(page)).includes('2026-12-10'));
      await seedSaved(page,['2026-11-30|Month Artist|Fixture Venue','2026-12-02|Month Artist|Fixture Venue','2026-11-17|Weak Artist|Fixture Venue']);
      await page.goto(origin+'/'+file+'?saved=1');expectEqual(await label(page,'Month Artist'),'30 Nov, 2 Dec','partial saved gaps are not a false continuous range');
      expectEqual(await dates(page),['2026-11-17','2026-11-30','2026-12-02'],'Saved includes existing one-track match');
      await page.goto(origin+'/'+file+'?saved=1&mo=2026-12');expectEqual(await dates(page),['2026-12-02']);expectEqual(await label(page,'Month Artist'),'2 Dec');
      await page.goto(origin+'/'+file+'?q=Weak');expectEqual(await dates(page),['2026-11-17'],'direct search can retrieve weak existing artist');
      await page.goto(origin+'/'+file+'?q=Calendar');
      const cal=page.locator(visible);await cal.locator('.detail-cue').click();
      expectEqual(await cal.locator('.source-check').textContent(),'Songkick listing · checked 6 Nov');
      const [download]=await Promise.all([page.waitForEvent('download'),cal.locator('.cal-btn').click()]);
      const body=fs.readFileSync(await download.path(),'utf8');
      assert(body.includes('\r\nDTSTART;VALUE=DATE:20261111\r\n'));assert(body.includes('DTEND;VALUE=DATE:20261112\r\n'));
      assert(body.includes('SUMMARY:Calendar Artist — Special\\, duo\\; evening\\\\show\r\n'),'ICS special characters escaped');
      assert(body.includes('URL:https://tickets.example.test/Calendar-Artist/2026-11-11\r\n'));
      assert(!body.includes('DTSTART;VALUE=DATE:20261112'),'calendar does not shift to another member date');
      await page.close();
    }
    expectEqual(errors,[],'no browser exceptions');
    console.log(JSON.stringify({status:'PASS',contexts:8,measurements},null,2));
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
