// Real archive + Gig Radar pages, with external services/media blocked.
// Uses temporary browser contexts; never touches Ben's saved browser state.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const allowed = new Set(['index.html', 'gigs.html', 'gigs-data.json', 'music-home.css', 'music-home.js', 'music-core.js']);
(async () => {
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://local').pathname.slice(1) || 'index.html';
    if (!allowed.has(name)) return res.writeHead(404).end();
    const content = fs.readFileSync(path.join(root, name));
    res.writeHead(200, {'Content-Type': {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json'}[path.extname(name)]});
    res.end(content);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    browser = await chromium.launch({executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--mute-audio']});
    for (const width of [1280, 390]) {
      for (const mode of ['guest', 'storage-unavailable', 'owner']) {
        const context = await browser.newContext({viewport: {width, height: 900}});
        const page = await context.newPage(), errors = [], writes = [];
        await page.clock.setFixedTime(new Date('2026-11-09T12:00:00Z'));
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', route => {
          const request = route.request();
          if (request.method() !== 'GET') writes.push(request.method() + ' ' + request.url());
          if (new URL(request.url()).origin !== origin || request.resourceType() === 'media') return route.abort();
          return route.continue();
        });
        if (mode === 'owner') await page.addInitScript(() => localStorage.setItem('dj_owner', '1'));
        if (mode === 'storage-unavailable') await page.addInitScript(() => {
          for (const method of ['getItem', 'setItem', 'removeItem']) {
            const original = Storage.prototype[method];
            Storage.prototype[method] = function(key, ...rest) {
              if (key === 'gr_find') throw new Error('Storage unavailable');
              return original.call(this, key, ...rest);
            };
          }
        });
        await page.goto(origin + '/gigs.html?q=Ron%20Trent', {waitUntil: 'load'});
        await page.locator('.a-link:visible').filter({hasText: 'Ron Trent'}).first().click();
        await page.waitForLoadState('load');
        await page.waitForFunction(() => document.querySelector('#search')?.value === 'Ron Trent');
        assert(await page.locator('#table-wrap').isVisible(), mode + ': artist results must be visible, not behind Discover');
        assert.equal(await page.locator('.music-nav [aria-current]').innerText(), 'Full archive');
        assert.match(await page.locator('#tbody tr').first().innerText(), /Ron Trent/);
        assert.equal(await page.locator('body.guest-focus').count(), 0);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        if (mode === 'guest') {
          await page.goto(origin + '/index.html', {waitUntil: 'load'});
          assert.equal(await page.locator('body.guest-focus').count(), 1, 'An ordinary visit still opens Discover');
          await page.goto(origin + '/index.html#find=Ron%20Trent', {waitUntil: 'load'});
          await page.waitForFunction(() => document.querySelector('#search')?.value === 'Ron Trent');
          assert(await page.locator('#table-wrap').isVisible(), 'A copied artist link also opens its results');
        }
        await page.goto(origin + '/index.html?hear=Ron%20Trent', {waitUntil: 'load'});
        const dialog = page.locator('#music-dialog[open]');
        await dialog.waitFor();
        assert.match(await dialog.innerText(), /Ron Trent — five from the archive/);
        assert.match(await dialog.innerText(), /5 tracks · your order is kept/);
        assert.equal(await dialog.getByRole('link', {name: 'Listen', exact: true}).count(), 5);
        assert.deepEqual(errors, []);
        assert.deepEqual(writes, [], 'Navigation must not send playback or account requests');
        console.log('PASS ' + width + 'px ' + mode + ': artist link shows filtered archive; Hear five tracks preserved');
        await context.close();
      }
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {console.error(error);process.exitCode = 1;});
