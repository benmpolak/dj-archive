#!/usr/bin/env python3
"""MusicBrainz pilot: label and credits for the 150 most-played non-vinyl tracks.

PILOT ONLY. The sample is frozen in the output file on the first run and the
script never goes beyond it. Read-only on the archive; writes only
enrichment/musicbrainz-pilot.json. Resumable: tracks already in "results" are
skipped, progress is saved after every track.

Per track: one recording search (raw title), a second search with a cleaned
title only if the first gives no acceptable match, then one release lookup for
the accepted match (label + release-level and recording-level relationships).
Never more than one request per 1.1 s. Search 503s ("server busy" load
shedding) are retried a few times with growing pauses, then recorded as errors.

    python3 enrichment/musicbrainz_pilot.py
    python3 enrichment/musicbrainz_pilot.py --retry-errors
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import spotify_sync  # noqa: E402

OUT = HERE / 'musicbrainz-pilot.json'
UA = 'DJArchiveEnrichment/0.1'
GAP = 1.1
SAMPLE = 150
_last = [0.0]

VARIANT = re.compile(r'\s+-\s+.*\b(remaster(ed)?|version|edit|mix|mono|stereo|from|live|single|original|demo|bonus|acoustic|instrumental|radio|extended|feat\.?|with)\b.*$', re.I)
FEAT = re.compile(r'\s*[\(\[]\s*(feat\.?|ft\.?|featuring|with)\s[^\)\]]*[\)\]]', re.I)
PAREN_VARIANT = re.compile(r'\s*[\(\[][^\)\]]*\b(remaster(ed)?|version|edit|mono|stereo|bonus)\b[^\)\]]*[\)\]]', re.I)


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def save(state):
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    os.replace(tmp, OUT)


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = s.replace('&', ' and ')
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\b(the|and)\b', ' ', s)
    return re.sub(r'\s+', '', s)


def clean_title(t):
    c = VARIANT.sub('', t)
    c = FEAT.sub('', c)
    c = PAREN_VARIANT.sub('', c)
    return c.strip() or t


def clean_album(al):
    c = re.sub(r'\s*[\(\[][^\)\]]*\b(deluxe|remaster(ed)?|edition|expanded|anniversary|bonus|version|mono|stereo|reissue)\b[^\)\]]*[\)\]]', '', al or '', flags=re.I)
    c = re.sub(r'\s+-\s+.*\b(deluxe|remaster(ed)?|edition|expanded|anniversary)\b.*$', '', c, flags=re.I)
    return c.strip()


def flags(track):
    t, al = track['t'], track.get('al') or ''
    f = []
    if re.search(r'\b(remix|rmx|rework|re-edit|dub)\b', t, re.I) or re.search(r'-\s.*\bmix\b', t, re.I):
        f.append('remix')
    if re.search(r'\blive\b', t, re.I) or re.search(r'\blive\b', al, re.I):
        f.append('live')
    if re.search(r'remaster', t, re.I):
        f.append('remaster')
    if re.search(r'\b(edit|version)\b', t, re.I):
        f.append('edit_or_version')
    if re.search(r'\b(feat\.?|ft\.?|with)\b', t, re.I) or ';' in track['a']:
        f.append('multi_artist')
    if re.search(r'\b(best of|greatest|collection|anthology|essential|hits|presents|compiled|various|soundtrack|ultimate)\b', al, re.I):
        f.append('compilation_album')
    return f


class Busy(Exception):
    pass


def get(url):
    """One polite GET. Retries only the 'server busy' 503, at most 4 times."""
    for pause in (0, 3, 6, 12, 24):
        if pause:
            time.sleep(pause)
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 503:
                continue
            raise
    raise Busy('503 after 5 attempts')


def lucene(s):
    return re.sub(r'(["\\])', r'\\\1', s)


def search(title, artist):
    q = f'recording:"{lucene(title)}" AND artist:"{lucene(artist)}"'
    url = 'https://musicbrainz.org/ws/2/recording?' + urllib.parse.urlencode({'query': q, 'fmt': 'json', 'limit': 25})
    return get(url).get('recordings', [])


def artist_ok(track_artists, rec):
    names = []
    for ac in rec.get('artist-credit', []):
        names.append(ac.get('name', ''))
        art = ac.get('artist', {})
        names.append(art.get('name', ''))
        names.extend(al.get('name', '') for al in art.get('aliases', []) or [])
    have = {norm(n) for n in names if n}
    for a in track_artists:
        na = norm(a)
        if not na:
            continue
        if na in have:
            return True
        if len(na) >= 5 and any(na in h or (len(h) >= 5 and h in na) for h in have):
            return True
    return False


def rel_rank(r, album_n, want_live):
    rg = r.get('release-group', {}) or {}
    sec = [s.lower() for s in rg.get('secondary-types', []) or []]
    title_match = bool(album_n) and norm(clean_album(r.get('title', ''))) == album_n
    official = r.get('status') == 'Official'
    plain = (rg.get('primary-type') in ('Album', 'Single', 'EP')) and not (set(sec) - ({'live'} if want_live else set()))
    date = r.get('date') or '9999'
    return (not title_match, not official, not plain, date)


def choose(recs, track):
    """Pick the best acceptable recording: score >= 90, sensible artist, then prefer the
    one on the archive's album, then a plain official release, then most releases."""
    artists = [a.strip() for a in track['a'].split(';') if a.strip()]
    album_n = norm(clean_album(track.get('al') or ''))
    want_live = 'live' in flags(track)
    title_n = {norm(track['t']), norm(clean_title(track['t']))}
    best = None
    for rec in recs:
        if int(rec.get('score', 0)) < 90 or not artist_ok(artists, rec):
            continue
        rels = rec.get('releases', []) or []
        ranked = sorted(rels, key=lambda r: rel_rank(r, album_n, want_live))
        top = rel_rank(ranked[0], album_n, want_live) if ranked else (True, True, True, '9999')
        is_live = 'live' in (rec.get('disambiguation') or '').lower()
        key = (top[0], norm(rec.get('title', '')) not in title_n, is_live and not want_live, top[1], top[2],
               -len(rels), -int(rec.get('score', 0)))
        if best is None or key < best[0]:
            best = (key, rec, ranked[0] if ranked else None, not top[0])
    return best


def rel_credit(r):
    art = r.get('artist') or {}
    return {'type': r.get('type'), 'name': art.get('name'), 'mbid': art.get('id'),
            'attributes': r.get('attributes') or []}


def family(c):
    t = (c['type'] or '').lower()
    if t in ('producer',):
        return 'producer'
    if t in ('engineer', 'mix', 'recording', 'mastering', 'sound', 'audio', 'programming', 'editor', 'balance'):
        return 'engineer'
    if t in ('instrument', 'vocal', 'performer', 'performing orchestra', 'conductor', 'chorus master', 'concertmaster'):
        return 'performer'
    if t in ('arranger', 'instrument arranger', 'vocal arranger', 'orchestrator'):
        return 'arranger'
    if t in ('composer', 'lyricist', 'writer', 'librettist'):
        return 'writer'
    return 'other'


def lookup(release_id, recording_id):
    inc = 'labels+recordings+artist-rels+recording-level-rels+work-rels+work-level-rels+release-groups'
    rel = get(f'https://musicbrainz.org/ws/2/release/{release_id}?inc={inc}&fmt=json')
    labels = [{'name': (li.get('label') or {}).get('name'), 'mbid': (li.get('label') or {}).get('id'),
               'catno': li.get('catalog-number')} for li in rel.get('label-info', []) or [] if li.get('label')]
    release_credits = [rel_credit(r) for r in rel.get('relations', []) or [] if r.get('target-type') == 'artist']
    rec_credits, writers, found = [], [], False
    for m in rel.get('media', []) or []:
        for tr in m.get('tracks', []) or []:
            rec = tr.get('recording') or {}
            if rec.get('id') != recording_id:
                continue
            found = True
            for r in rec.get('relations', []) or []:
                if r.get('target-type') == 'artist':
                    rec_credits.append(rel_credit(r))
                elif r.get('target-type') == 'work':
                    for wr in (r.get('work') or {}).get('relations', []) or []:
                        if wr.get('target-type') == 'artist':
                            writers.append(rel_credit(wr))
    rg = rel.get('release-group') or {}
    return {'release': {'mbid': rel.get('id'), 'title': rel.get('title'), 'date': rel.get('date'),
                        'country': rel.get('country'), 'status': rel.get('status'),
                        'primary_type': rg.get('primary-type'), 'secondary_types': rg.get('secondary-types') or [],
                        'tracks': sum(len(m.get('tracks', []) or []) for m in rel.get('media', []) or [])},
            'labels': labels, 'recording_found_on_release': found,
            'recording_credits': rec_credits, 'writer_credits': writers, 'release_credits': release_credits}


def main():
    if OUT.exists():
        state = json.loads(OUT.read_text())
    else:
        data, _, _ = spotify_sync.read_data((ROOT / 'index.html').read_text())
        pool = [t for t in data if t.get('vy') != 1 and isinstance(t.get('sid'), str) and len(t['sid']) == 22
                and not t['sid'].startswith('spotify:') and t.get('pc')]
        pool.sort(key=lambda t: -t['pc'])
        sample = [{'sid': t['sid'], 'a': t['a'], 't': t['t'], 'al': t.get('al') or '', 'r': t.get('r'), 'pc': t['pc']}
                  for t in pool[:SAMPLE]]
        state = {'meta': {'source': 'https://musicbrainz.org/ws/2', 'user_agent': UA, 'started': now(),
                          'sample_rule': f'top {SAMPLE} by pc, not vinyl, 22-character Spotify id',
                          'accept_rule': 'search score >= 90 and artist name match'},
                 'sample': sample, 'results': {}}
        save(state)
    if '--retry-errors' in sys.argv:
        state['results'] = {k: v for k, v in state['results'].items() if v.get('status') != 'error'}
    todo = [t for t in state['sample'] if t['sid'] not in state['results']]
    print(f'{len(state["sample"])} in sample, {len(state["results"])} done, {len(todo)} to do', flush=True)
    errors_in_a_row = 0
    for n, t in enumerate(todo, 1):
        res = {'a': t['a'], 't': t['t'], 'al': t['al'], 'r': t['r'], 'pc': t['pc'], 'flags': flags(t), 'at': now()}
        primary = t['a'].split(';')[0].strip()
        try:
            recs = search(t['t'], primary)
            pick, stage = choose(recs, t), 'raw_title'
            res['raw_hits'] = len(recs)
            res['raw_top_score'] = max([int(r.get('score', 0)) for r in recs], default=0)
            ct = clean_title(t['t'])
            if pick is None and ct != t['t']:
                recs = search(ct, primary)
                pick, stage = choose(recs, t), 'cleaned_title'
                res['cleaned_title'] = ct
                res['cleaned_hits'] = len(recs)
                res['cleaned_top_score'] = max([int(r.get('score', 0)) for r in recs], default=0)
            if pick is None:
                res['status'] = 'no_match'
            else:
                _, rec, release, album_match = pick
                res.update({'status': 'matched', 'stage': stage, 'score': int(rec['score']),
                            'recording': {'mbid': rec['id'], 'title': rec.get('title'),
                                          'artists': [ac.get('name') for ac in rec.get('artist-credit', [])],
                                          'disambiguation': rec.get('disambiguation') or '',
                                          'first_release_date': rec.get('first-release-date'),
                                          'releases_in_search': len(rec.get('releases', []) or [])},
                            'album_match': album_match})
                if release:
                    res.update(lookup(release['id'], rec['id']))
                else:
                    res.update({'release': None, 'labels': [], 'recording_credits': [], 'writer_credits': [],
                                'release_credits': []})
            errors_in_a_row = 0
        except Exception as e:
            res['status'] = 'error'
            res['error'] = f'{type(e).__name__}: {e}'
            errors_in_a_row += 1
        state['results'][t['sid']] = res
        state['meta']['updated'] = now()
        save(state)
        if n % 10 == 0 or n == len(todo):
            c = [r['status'] for r in state['results'].values()]
            print(f'{n}/{len(todo)}: matched {c.count("matched")}, no_match {c.count("no_match")}, error {c.count("error")}', flush=True)
        if errors_in_a_row >= 8:
            state['meta']['stopped'] = f'8 errors in a row at {now()}; rerun with --retry-errors'
            save(state)
            print('8 errors in a row; stopping.', flush=True)
            sys.exit(3)
    state['meta'].pop('stopped', None)
    state['meta']['finished'] = now()
    save(state)
    print('done', flush=True)


if __name__ == '__main__':
    main()
