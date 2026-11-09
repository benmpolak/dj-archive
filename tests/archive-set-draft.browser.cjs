// Real Random Mix -> draft -> Keep selection -> reload, without account/media requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const allowed = new Set(['index.html', 'music-home.css', 'music-home.js', 'music-core.js', 'gigs-data.json']);
(async () => {
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://local').pathname.slice(1) || 'index.html';
    if (!allowed.has(name)) return res.writeHead(404).end();
    res.writeHead(200, {'Content-Type': {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.json':'application/json'}[path.extname(name)]});
    res.end(fs.readFileSync(path.join(root, name)));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    browser = await chromium.launch({executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true, args:['--mute-audio']});
    const context = await browser.newContext({viewport:{width:390, height:844}});
    const page = await context.newPage(), errors = [], writes = [];
    page.on('pageerror', e => errors.push(e.message));
    await context.route('**/*', route => {
      const request = route.request();
      if (request.method() !== 'GET') writes.push(request.method() + ' ' + request.url());
      if (request.method() !== 'GET' || new URL(request.url()).origin !== origin || request.resourceType() === 'media') return route.abort();
      return route.continue();
    });
    await page.goto(origin + '/index.html?view=records');
    // Stable random choices in the existing real catalogue, rather than mocked tracks.
    await page.evaluate(() => { let seed = 177; Math.random = () => ((seed = Math.imul(seed, 1664525) + 1013904223 >>> 0) / 4294967296); });
    await page.locator('#archive-tools summary').click();
    await page.locator('.archive-tool-actions').getByRole('button', {name:'Random Mix', exact:true}).click();
    const generated = await page.evaluate(() => ({
      ids:djSet.map(MusicCore.trackId), description:setDesc,
      stored:JSON.parse(localStorage.getItem('dj_music_home_v1'))
    }));
    assert.equal(generated.ids.length, 10);
    assert(generated.description.length > 120, 'Exercise a real long generated narrative');
    assert(generated.stored.draft.name.length <= 120);
    assert.deepEqual(generated.stored.draft.tracks, generated.ids);
    assert.equal(generated.stored.draftDescription, generated.description);
    assert.equal(await page.locator('#set-desc').innerText(), generated.description, 'The full narrative stays in the set builder');
    await page.getByRole('button', {name:'Keep this set', exact:true}).click();
    assert.equal(await page.locator('#music-dialog .mh-tracklist li').count(), 10);
    assert.equal(await page.locator('#mh-name').inputValue(), generated.stored.draft.name);
    await page.getByRole('button', {name:'Keep selection', exact:true}).click();
    const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('dj_music_home_v1')).selections[0]);
    assert.deepEqual(kept.tracks, generated.ids);
    await page.reload();
    const restored = await page.evaluate(() => ({ids:djSet.map(MusicCore.trackId), description:setDesc, saved:JSON.parse(localStorage.getItem('dj_music_home_v1')).selections[0]}));
    assert.deepEqual(restored.ids, generated.ids, 'Reload restores exact draft track order');
    assert.equal(restored.description, generated.description, 'Reload retains the narrative');
    assert.deepEqual(restored.saved.tracks, generated.ids);
    await page.locator('.music-nav a[href="?view=saved"]').click();
    await page.locator('.mh-saved-row .mh-saved-item').first().click();
    assert.equal(await page.locator('#music-dialog .mh-tracklist li').count(), 10);
    const shortName = 'My  Sunday mix';
    const namedDraft = await page.evaluate(name => {
      setDesc = name; renderSet();
      return JSON.parse(localStorage.getItem('dj_music_home_v1')).draft;
    }, shortName);
    assert.equal(namedDraft.name, shortName, 'Existing short names retain their wording and spacing');
    assert.deepEqual(namedDraft.tracks, generated.ids);
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    console.log('PASS Random Mix: full narrative retained; ten-track draft and kept selection survive reload in order');
    await context.close();
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
