#!/usr/bin/env python3
"""Rebuild source modules and the small shared desk-screen catalogue.
No fetching, credentials, playlist mutations or deployment.
"""
import hashlib, importlib.util, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def main():
    path = ROOT / 'index.html'
    html = path.read_text()
    start = html.index('const DATA=') + len('const DATA=')
    data, _ = json.JSONDecoder().raw_decode(html[start:])
    before = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    for name, tag, ident in [('dealer.js', 'script', 'dealer-js'), ('guest.js', 'script', 'guest-js'), ('design-pass.css', 'style', 'design-pass')]:
        source = (ROOT / name).read_text()
        if name == 'guest.js':
            source = source.replace('/*__GUEST_ART__*/{}', (ROOT / 'guest-art.json').read_text().strip())
        pattern = rf'<{tag} id="{ident}">.*?</{tag}>'
        html, n = re.subn(pattern, lambda _: f'<{tag} id="{ident}">\n{source}\n</{tag}>', html, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f'Missing injection marker: {ident}')
    after, _ = json.JSONDecoder().raw_decode(html[html.index('const DATA=') + len('const DATA='):])
    assert hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest() == before
    path.write_text(html)
    # Small device requests a shard using the first character of a Spotify ID.
    # Public musical metadata only; no tokens, private notes or listening history.
    out = ROOT / 'music'
    out.mkdir(exist_ok=True)
    shards = {}
    art = json.loads((ROOT / 'guest-art.json').read_text())
    for t in data:
        sid = t.get('sid', '')
        if not re.fullmatch(r'[A-Za-z0-9]{22}', sid):
            continue
        row = {k: t.get(k) for k in ['a','t','al','r','tp','vb','c','vy','did']}
        row.update({'id': 'sp:' + sid, 'sid': sid})
        if sid in art: row['art'] = art[sid]
        shards.setdefault(sid[0], {})[sid] = row
    for key, rows in shards.items():
        (out / f'tracks-{key}.json').write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
    manifest = {'version': 1, 'trackCount': len(data), 'spotifyTracks': sum(len(s) for s in shards.values()),
                'catalogueRevision': before[:16], 'shards': sorted(shards), 'lookup': 'tracks-{firstCharacterOfSpotifyId}.json',
                'gigs': '../gigs-data.json', 'selectionContract': '../music-core.js'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    spec = importlib.util.spec_from_file_location('gigs', ROOT / 'gigs-fetch.py')
    gigs = importlib.util.module_from_spec(spec);spec.loader.exec_module(gigs)
    payload = json.loads((ROOT / 'gigs-data.json').read_text())
    artists = gigs.load_artists();matches = gigs.hydrate_saved_matches(payload, artists)
    gigs.save_matches(matches, payload['generated'], payload['events'])
    for filename, public in [('gigs.html', False), ('gigs-share.html', True)]:
        gigs.render(matches, payload['events'], len(artists), gigs.existing_sources_note(), str(ROOT / filename), public=public, generated=payload['generated'])
    print(f'Built {len(data):,} unchanged tracks, {len(matches)} verified gigs and {len(shards)} catalogue shards.')

if __name__ == '__main__': main()
