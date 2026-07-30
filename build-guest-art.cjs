#!/usr/bin/env node
/*
  Bake the guest shelves' Spotify sleeves into the static page.

  Usage:
    python3 -m http.server 8768
    NODE_PATH=/path/to/node_modules node build-guest-art.cjs

  Spotify's oEmbed response no longer includes thumbnail_url. The embed HTML still
  contains the cover URL, so this resolves it at build time instead of making every
  guest's browser repeat hundreds of fallible cross-origin lookups.
*/
const fs = require('fs');
const { execFile } = require('child_process');
const { promisify } = require('util');
const { chromium } = require('playwright');
const runFile = promisify(execFile);

const PAGE = process.env.GUEST_ART_PAGE || 'http://127.0.0.1:8768/?guest';
const OUT = 'guest-art.json';
const WORKERS = 2;
const CHROME = process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: CHROME });
  const page = await browser.newPage();
  await page.goto(PAGE, { waitUntil: 'domcontentloaded' });
  const cards = await page.locator('.gh-card-art[data-art-sid]').evaluateAll(els =>
    els.map(el => ({
      key: el.dataset.artKey,
      sid: el.dataset.artSid
    }))
  );
  await browser.close();

  const unique = [...new Map(cards.map(card => [card.key, card])).values()];
  const old = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : {};
  const map = {};
  unique.forEach(card => { if (old[card.key]) map[card.key] = old[card.key]; });
  const misses = [];
  let cursor = 0;

  async function worker() {
    while (cursor < unique.length) {
      const card = unique[cursor++];
      if (map[card.key]) continue;
      try {
        const url = `https://open.spotify.com/embed/track/${card.sid}`;
        /* curl opens a fresh short-lived connection. Spotify throttles Node's
           pooled build-time connection long before it throttles real visitors. */
        const { stdout: html } = await runFile('/usr/bin/curl',
          ['-sS', '--fail', '--max-time', '15', url],
          { maxBuffer: 4 * 1024 * 1024 });
        const match = html.match(/<link rel="preload" as="image" href="([^"]+)"/);
        if (match) map[card.key] = match[1].replace(/&amp;/g, '&');
        else misses.push({ key: card.key, sid: card.sid, status: 'no image' });
      } catch (_) {
        misses.push({ key: card.key, sid: card.sid, status: 'network' });
      }
      await new Promise(resolve => setTimeout(resolve, 120));
    }
  }

  await Promise.all(Array.from({ length: WORKERS }, worker));
  fs.writeFileSync(OUT, JSON.stringify(map, null, 2) + '\n');
  console.log(`Baked ${Object.keys(map).length}/${unique.length} guest sleeves into ${OUT}`);
  if (misses.length) console.log('Unresolved examples:', misses.slice(0, 8));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
