#!/usr/bin/env python3
"""Fetch Discogs release credits for every vinyl release in the DJ Archive.

Read-only on the archive: reads index.html through spotify_sync.read_data and
writes only enrichment/discogs-releases.json. Resumable: releases already in the
output file are skipped, progress is saved after every request.

Unauthenticated (no token is used anywhere in this repo), so the limit is
25 requests/minute: one request every 2.6 s. Stops at once on HTTP 429.

    python3 enrichment/discogs_fetch.py            # fetch what is missing
    python3 enrichment/discogs_fetch.py --retry    # also retry earlier failures
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import spotify_sync  # noqa: E402

OUT = HERE / 'discogs-releases.json'
UA = 'DJArchiveEnrichment/0.1'
SLEEP = 2.6


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def save(state):
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    os.replace(tmp, OUT)


def people(items):
    return [{'id': x.get('id'), 'name': x.get('name'), 'anv': x.get('anv') or '',
             'role': x.get('role') or '', 'tracks': x.get('tracks') or ''}
            for x in (items or [])]


def slim(rel):
    return {
        'id': rel.get('id'),
        'master_id': rel.get('master_id'),
        'title': rel.get('title'),
        'artists': [{'id': a.get('id'), 'name': a.get('name'), 'join': a.get('join') or ''}
                    for a in rel.get('artists') or []],
        'labels': [{'id': l.get('id'), 'name': l.get('name'), 'catno': l.get('catno')}
                   for l in rel.get('labels') or []],
        'year': rel.get('year'),
        'released': rel.get('released'),
        'country': rel.get('country'),
        'formats': [{'name': f.get('name'), 'qty': f.get('qty'),
                     'descriptions': f.get('descriptions') or [], 'text': f.get('text') or ''}
                    for f in rel.get('formats') or []],
        'genres': rel.get('genres') or [],
        'styles': rel.get('styles') or [],
        'extraartists': people(rel.get('extraartists')),
        'companies': [{'id': c.get('id'), 'name': c.get('name'),
                       'type': c.get('entity_type_name'), 'catno': c.get('catno') or ''}
                      for c in rel.get('companies') or []],
        'tracklist': [{'position': t.get('position'), 'type': t.get('type_'), 'title': t.get('title'),
                       'duration': t.get('duration') or '',
                       'artists': [{'id': a.get('id'), 'name': a.get('name')} for a in t.get('artists') or []],
                       'extraartists': people(t.get('extraartists'))}
                      for t in rel.get('tracklist') or []],
    }


def main():
    retry = '--retry' in sys.argv
    data, _, _ = spotify_sync.read_data((ROOT / 'index.html').read_text())
    archive = defaultdict(lambda: {'tracks': 0, 'artists': set(), 'albums': set()})
    for t in data:
        if t.get('vy') == 1 and t.get('did'):
            a = archive[str(t['did'])]
            a['tracks'] += 1
            a['artists'].add(t.get('a', '').split(';')[0].strip())
            a['albums'].add(t.get('al', ''))
    dids = sorted(archive, key=int)

    if OUT.exists():
        state = json.loads(OUT.read_text())
    else:
        state = {'meta': {'source': 'https://api.discogs.com/releases/{id}', 'auth': 'none (unauthenticated, 25/min)',
                          'user_agent': UA, 'started': now()}, 'releases': {}, 'failed': {}}
    state['meta']['distinct_release_ids'] = len(dids)
    if retry:
        state['failed'] = {}
    todo = [d for d in dids if d not in state['releases'] and d not in state['failed']]
    print(f'{len(dids)} release ids, {len(state["releases"])} done, {len(state["failed"])} failed, {len(todo)} to fetch', flush=True)

    errors_in_a_row = 0
    for n, did in enumerate(todo, 1):
        req = urllib.request.Request(f'https://api.discogs.com/releases/{did}',
                                     headers={'User-Agent': UA, 'Accept': 'application/json'})
        remaining = None
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                remaining = resp.headers.get('X-Discogs-Ratelimit-Remaining')
                rel = json.load(resp)
            entry = slim(rel)
            a = archive[did]
            entry['archive'] = {'tracks': a['tracks'], 'artists': sorted(a['artists']), 'albums': sorted(a['albums'])}
            entry['fetched'] = now()
            state['releases'][did] = entry
            errors_in_a_row = 0
        except urllib.error.HTTPError as e:
            remaining = e.headers.get('X-Discogs-Ratelimit-Remaining') if e.headers else None
            if e.code == 429:
                state['meta']['stopped'] = f'HTTP 429 at {now()} on release {did}; rerun later to resume'
                save(state)
                print(f'429 rate limited on {did}; stopping. {len(state["releases"])} saved.', flush=True)
                sys.exit(2)
            state['failed'][did] = {'status': e.code, 'error': str(e.reason), 'at': now()}
            errors_in_a_row += 1
        except Exception as e:  # network, timeout, bad JSON
            state['failed'][did] = {'status': None, 'error': f'{type(e).__name__}: {e}', 'at': now()}
            errors_in_a_row += 1
        state['meta']['updated'] = now()
        save(state)
        if n % 25 == 0 or n == len(todo):
            print(f'{n}/{len(todo)} fetched, failed so far {len(state["failed"])}, remaining header {remaining}', flush=True)
        if errors_in_a_row >= 5:
            state['meta']['stopped'] = f'5 errors in a row at {now()}; rerun with --retry'
            save(state)
            print('5 errors in a row; stopping.', flush=True)
            sys.exit(3)
        if n < len(todo):
            pause = SLEEP
            try:
                if remaining is not None and int(remaining) <= 2:
                    pause = 62  # let the one-minute window clear
            except ValueError:
                pass
            time.sleep(pause)
    state['meta'].pop('stopped', None)
    state['meta']['finished'] = now()
    save(state)
    print(f'done: {len(state["releases"])} releases, {len(state["failed"])} failed', flush=True)


if __name__ == '__main__':
    main()
