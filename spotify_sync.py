#!/usr/bin/env python3
"""Read-only Spotify playlist sync. Credentials and snapshots stay outside Git.

connect: local PKCE sign-in; sync: fetch/preview; sync --apply: apply verified data.
Publication is a separate reviewed step in the scheduled Codex task.
"""
import argparse
import base64
import collections
import copy
import csv
import datetime as dt
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PRIVATE = Path.home() / 'desk-screen' / '.secrets' / 'archive-sync'
API = 'https://api.spotify.com/v1/'
SCOPES = 'playlist-read-private playlist-read-collaborative'
MONTHS = ('January February March April May June July August September October November December').split()
SID = re.compile(r'^[A-Za-z0-9]{22}$')


class SyncError(Exception):
    pass


def private_json(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def request_json(url, data=None, token=None):
    headers = {'User-Agent': 'DJArchiveSync/1.0'}
    if token:
        if not url.startswith(API):
            raise SyncError('Refusing to send a Spotify token to an unexpected destination.')
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', '5'))
                if wait <= 30 and attempt < 2:
                    time.sleep(max(1, wait))
                    continue
                raise SyncError('Spotify rate limit reached. Retry later; archive unchanged.') from None
            if e.code >= 500 and attempt < 2:
                time.sleep(2)
                continue
            if e.code in (400, 401) and 'accounts.spotify.com' in url:
                raise SyncError('Spotify connection expired or was declined. Run connect again.') from None
            raise SyncError(f'Spotify returned HTTP {e.code}; no partial import was applied.') from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                continue
            raise SyncError('Spotify could not be reached; archive unchanged.') from None


def connect(config, private):
    """Loopback only. No logs containing callback codes, tokens or request URLs."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(32)
    redirect = urllib.parse.urlsplit(config['redirect_uri'])
    if redirect.scheme != 'http' or redirect.hostname != '127.0.0.1':
        raise SyncError('The connection return address must be the registered loopback address.')
    result = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path != (redirect.path or '/'):
                self.send_error(404)
                return
            params = urllib.parse.parse_qs(parsed.query)
            if not secrets.compare_digest(params.get('state', [''])[0], state):
                self.send_error(400, 'Invalid sign-in return. Start again from the connection link.')
                return
            try:
                if params.get('error') or not params.get('code'):
                    raise SyncError('Spotify connection was not approved.')
                token = request_json('https://accounts.spotify.com/api/token', {
                    'grant_type': 'authorization_code', 'code': params['code'][0],
                    'redirect_uri': config['redirect_uri'], 'client_id': config['client_id'],
                    'code_verifier': verifier})
                if not token.get('refresh_token') or not set(SCOPES.split()) <= set(token.get('scope', '').split()):
                    raise SyncError('Spotify did not grant the requested playlist-reading permission.')
                token['expires_at'] = time.time() + token.get('expires_in', 3600) - 60
                token['connected_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
                private_json(private / 'auth.json', token)
                result['ok'] = True
                message = 'Spotify connected. Your weekly DJ Archive update is ready for its first check. You can close this tab.'
            except SyncError as e:
                result['error'] = str(e)
                message = str(e)
            self.send_response(200 if result.get('ok') else 400)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(message.encode())

    with http.server.HTTPServer(('127.0.0.1', redirect.port or 80), Callback) as server:
        server.timeout = 1
        url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
            'client_id': config['client_id'], 'response_type': 'code',
            'redirect_uri': config['redirect_uri'], 'scope': SCOPES,
            'state': state, 'code_challenge_method': 'S256', 'code_challenge': challenge})
        print('Open this Spotify connection link:\n' + url, flush=True)
        deadline = time.time() + 1800
        while not result and time.time() < deadline:
            server.handle_request()
    if not result.get('ok'):
        raise SyncError(result.get('error', 'Sign-in timed out. Run connect again.'))
    print('Spotify connected. Credentials saved privately; playlist read access only.')


def access_token(config, private):
    try:
        saved = json.loads((private / 'auth.json').read_text())
    except FileNotFoundError:
        raise SyncError('Spotify is not connected. Run: python3 spotify_sync.py connect') from None
    if saved.get('expires_at', 0) > time.time():
        return saved['access_token']
    fresh = request_json('https://accounts.spotify.com/api/token', {
        'grant_type': 'refresh_token', 'refresh_token': saved['refresh_token'],
        'client_id': config['client_id']})
    saved.update(fresh)
    saved['expires_at'] = time.time() + fresh.get('expires_in', 3600) - 60
    private_json(private / 'auth.json', saved)
    return saved['access_token']


def pages(get, url):
    rows, seen, total = [], set(), None
    while url:
        if not url.startswith(API) or url in seen or len(seen) >= 2000:
            raise SyncError('Invalid Spotify pagination; archive unchanged.')
        seen.add(url)
        page = get(url)
        if not isinstance(page.get('items'), list) or not isinstance(page.get('total'), int):
            raise SyncError('Incomplete Spotify page; archive unchanged.')
        if total is not None and total != page['total']:
            raise SyncError('Playlist changed during reading. Retry the complete check.')
        total = page['total']
        rows.extend(page['items'])
        url = page.get('next')
    if len(rows) != total:
        raise SyncError('Spotify returned a truncated playlist; archive unchanged.')
    return rows


def normalise(name):
    return ' '.join(unicodedata.normalize('NFKC', name).replace('_', ' ').split()).casefold()


def targets(playlists, config, today, user_id):
    names = list(config['regular_playlists'])
    month = f'{MONTHS[today.month - 1]} {today.year}'
    names.append(month)
    if today.day <= config.get('previous_month_grace_days', 0):
        previous = today.replace(day=1) - dt.timedelta(days=1)
        names.append(f'{MONTHS[previous.month - 1]} {previous.year}')
    selected, missing = [], []
    for name in names:
        pinned_id = config.get('playlist_ids', {}).get(name)
        matches = [p for p in playlists if p and (p.get('id') == pinned_id if pinned_id else normalise(p.get('name', '')) == normalise(name))
                   and ((p.get('owner') or {}).get('id') == user_id or p.get('collaborative'))]
        if len(matches) > 1:
            raise SyncError(f'Multiple eligible playlists named {name}; select an exact playlist before importing.')
        if not matches:
            missing.append(name)
            continue
        if not SID.fullmatch(matches[0].get('id', '')):
            raise SyncError('Spotify returned an invalid playlist ID.')
        selected.append((name, matches[0]))
    required_missing = [name for name in missing if name in config['regular_playlists']]
    if required_missing:
        raise SyncError('Regular playlists unavailable: ' + ', '.join(required_missing))
    return selected, missing


def fetch_snapshot(config, token, today):
    get = lambda url: request_json(url, token=token)
    user = get(API + 'me')['id']
    selected, missing = targets(pages(get, API + 'me/playlists?limit=50'), config, today, user)
    snapshot = {'date': today.isoformat(), 'playlists': [], 'missing_monthly': missing}
    for name, playlist in selected:
        pid = playlist['id']
        before = get(API + 'playlists/' + pid)
        items = pages(get, API + f'playlists/{pid}/items?limit=50')
        after = get(API + 'playlists/' + pid)
        if not before.get('snapshot_id') or before['snapshot_id'] != after.get('snapshot_id'):
            raise SyncError(f'{name} changed during reading. Retry the complete check.')
        rows, skipped = [], collections.Counter()
        for item in items:
            track = (item or {}).get('item') or (item or {}).get('track')
            if not track:
                skipped['unavailable'] += 1
                continue
            if item.get('is_local') or track.get('is_local'):
                skipped['local'] += 1
                continue
            if track.get('type') != 'track':
                skipped['non_track'] += 1
                continue
            if not SID.fullmatch(track.get('id') or ''):
                raise SyncError(f'Invalid track in {name}.')
            album = track.get('album') or {}
            rows.append({'sid': track['id'], 'a': ';'.join(a['name'] for a in track.get('artists', [])),
                         't': track['name'], 'al': album.get('name', ''), 'rd': album.get('release_date', ''),
                         'duration': track.get('duration_ms'), 'addedAt': item.get('added_at'),
                         'art': next((i['url'] for i in album.get('images', []) if i.get('url', '').startswith('https://i.scdn.co/')), None)})
        snapshot['playlists'].append({'name': name, 'id': pid, 'snapshot_id': before['snapshot_id'],
                                      'total': len(items), 'skipped': dict(skipped), 'tracks': rows})
    return snapshot


def read_data(html):
    start = html.index('const DATA=') + len('const DATA=')
    data, size = json.JSONDecoder().raw_decode(html[start:])
    return data, start, start + size


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')


def song_key(t):
    return (re.split(r'[;,]', t.get('a', ''))[0].strip().lower(), t.get('t', '').strip().lower())


def prepare(root, snapshot, stage):
    """Run the established importer in an isolated scratch directory, then enrich only new rows."""
    html = (root / 'index.html').read_text()
    baseline, _, _ = read_data(html)
    old_ledger = json.loads((root / 'add-ledger.json').read_text())
    ledger = copy.deepcopy(old_ledger)
    art = json.loads((root / 'guest-art.json').read_text())
    baseline_art = dict(art)
    stage.mkdir(parents=True, exist_ok=True)
    for name in ('playlist-import.py', 'index.html', 'build.py', 'guest.js', 'dealer.js', 'design-pass.css'):
        shutil.copy2(root / name, stage / name)
    exports = stage / 'exports'
    exports.mkdir()
    sources = collections.defaultdict(list)
    for playlist in snapshot['playlists']:
        name = playlist['name']
        # Names originate in the allowlist/current calendar month, not arbitrary API input.
        filename = name.replace(' ', '_') + '.csv'
        if Path(filename).name != filename:
            raise SyncError('Invalid configured playlist name.')
        with (exports / filename).open('w', newline='') as f:
            fields = ['Track URI', 'Track Name', 'Artist Name(s)', 'Album Name', 'Release Date', 'Added At']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in playlist['tracks']:
                sources[row['sid']].append((name, row))
                writer.writerow(dict(zip(fields, ['spotify:track:' + row['sid'], row['t'], row['a'], row['al'], row['rd'], row.get('addedAt') or ''])))
                added = row.get('addedAt') or ''
                if re.match(r'^\d{4}-\d{2}-\d{2}T', added):
                    current = ledger.setdefault(name, {}).get(row['sid'])
                    ledger[name][row['sid']] = min(current or added[:7], added[:7])
    subprocess.run([sys.executable, str(stage / 'playlist-import.py'), 'exports'], check=True, capture_output=True)
    html = (stage / 'index.html').read_text()
    data, start, end = read_data(html)
    by_sid = {t.get('sid'): t for t in data}
    by_title = {song_key(t): t for t in reversed(data)}
    counts = collections.Counter(sid for items in ledger.values() for sid in items)
    new_ids = {id(t) for t in data[len(baseline):]}
    for sid, entries in sources.items():
        track = by_sid.get(sid) or by_title.get(song_key(entries[0][1]))
        if track is None:
            raise SyncError('Importer failed to retain a selected track.')
        track['n'] = max(track.get('n', 0), counts.get(sid, 0))
        if id(track) not in new_ids:
            continue
        row = entries[0][1]
        dates = sorted(e.get('addedAt') for _, e in entries if e.get('addedAt'))
        if dates:
            track['addedAt'] = dates[0]
            track['da'] = int(dates[0][:7].replace('-', ''))
        else:
            track.pop('da', None)  # Unknown add dates must not become invented April dates.
        track['rd'] = row['rd']
        track['duration'] = row.get('duration') or 0
        track['playlists'] = sorted({n for n, _ in entries})
        for _, source in entries:
            if source.get('art'):
                art[track['sid']] = source['art']
                break
    # Append-only tracks; only importer-owned crate/count/Spotify matching fields may change.
    allowed = {'c', 'n', 'sid'}
    if len(data) < len(baseline):
        raise SyncError('Import would remove archive records.')
    for old, new in zip(baseline, data):
        if {k: v for k, v in old.items() if k not in allowed} != {k: v for k, v in new.items() if k not in allowed}:
            raise SyncError('Import would change existing music or listening-history metadata.')
        if SID.fullmatch(old.get('sid', '')) and old['sid'] != new.get('sid'):
            raise SyncError('Import would replace an existing Spotify ID.')
        if new.get('n', 0) < old.get('n', 0):
            raise SyncError('Import would reduce an existing playlist count.')
        if (set(old.get('c', [])) - {'Uncategorized', 'Uncategorised'}) - set(new.get('c', [])):
            raise SyncError('Import would remove an existing crate assignment.')
    old_sids = {t.get('sid') for t in baseline}
    added_sids = [t['sid'] for t in data[len(baseline):]]
    if len(added_sids) != len(set(added_sids)) or old_sids.intersection(added_sids):
        raise SyncError('Import would introduce duplicate tracks.')
    html = html[:start] + packed(data) + html[end:]
    by_month = collections.defaultdict(collections.Counter)
    for name, entries in ledger.items():
        for month in entries.values():
            by_month[month][name] += 1
    digging = {'months': [{'m': month, 'n': sum(by_month[month].values()),
                          'top': [[n, c] for n, c in by_month[month].most_common(4)]}
                         for month in sorted(by_month, reverse=True)[:120]],
               'total': sum(len(p) for p in ledger.values()), 'np': len(ledger)}
    html, n = re.subn(r'var DIGGING=\{.*?\};', lambda _: 'var DIGGING=' + packed(digging) + ';', html, count=1, flags=re.S)
    if n != 1:
        raise SyncError('Missing archive digging-history marker.')
    (stage / 'index.html').write_text(html)
    (stage / 'add-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=0))
    (stage / 'guest-art.json').write_text(json.dumps(art, ensure_ascii=False, indent=2) + '\n')
    # Explicitly avoid the Gig Radar pruning performed by a full build.
    subprocess.run([sys.executable, str(stage / 'build.py'), '--catalogue-only'], check=True, capture_output=True)
    outputs = ['index.html', 'add-ledger.json', 'guest-art.json', 'music/manifest.json']
    outputs += sorted(str(p.relative_to(stage)) for p in (stage / 'music').glob('tracks-*.json'))
    changes = [name for name in outputs if not (root / name).exists() or (root / name).read_bytes() != (stage / name).read_bytes()]
    return {'date': snapshot['date'], 'tracks_added': len(data) - len(baseline), 'total': len(data),
            'playlist_links_added': sum(len(p) for p in ledger.values()) - sum(len(p) for p in old_ledger.values()),
            'artwork_added': len(art) - len(baseline_art), 'changed_files': changes,
            'playlists': [{'name': p['name'], 'total': p['total'], 'skipped': p['skipped']} for p in snapshot['playlists']],
            'missing_monthly': snapshot['missing_monthly']}


def sync(config, root, private, apply=False):
    today = dt.datetime.now(ZoneInfo(config['timezone'])).date()
    token = access_token(config, private)
    snapshot = fetch_snapshot(config, token, today)
    private_json(private / 'latest-snapshot.json', snapshot)
    with tempfile.TemporaryDirectory(prefix='dj-archive-sync-') as tmp:
        stage = Path(tmp)
        report = prepare(root, snapshot, stage)
        if apply and report['changed_files']:
            # Never absorb someone else's in-progress catalogue edits into a scheduled publication.
            dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root, text=True)
            if dirty.strip():
                raise SyncError('Tracked archive edits are pending. Review them before applying the scheduled import.')
            backup = root / ('_backup-spotify-sync-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
            backup.mkdir()
            for name in report['changed_files']:
                source = root / name
                if source.exists():
                    (backup / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, backup / name)
            try:
                for name in report['changed_files']:
                    (root / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(stage / name, root / name)
            except OSError:
                for name in report['changed_files']:
                    if (backup / name).exists():
                        shutil.copy2(backup / name, root / name)
                raise
            report['backup'] = str(backup)
        report['applied'] = apply
        private_json(private / 'latest-report.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['connect', 'sync'])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--private-dir', type=Path, default=PRIVATE)
    args = parser.parse_args()
    config = json.loads((ROOT / 'spotify-sync.json').read_text())
    try:
        if args.command == 'connect':
            connect(config, args.private_dir)
        else:
            sync(config, ROOT, args.private_dir, args.apply)
    except (SyncError, OSError, ValueError, subprocess.CalledProcessError) as e:
        print('Sync stopped: ' + (str(e) if not isinstance(e, subprocess.CalledProcessError) else 'Archive build/import failed.'), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
