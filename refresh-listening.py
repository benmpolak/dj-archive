#!/usr/bin/env python3
"""Refresh every listening-history block from a Spotify Extended Streaming History export.

    python3 refresh-listening.py "/path/to/Spotify Extended Streaming History" [--apply] [--until YYYY-MM-DD]

Reruns the calculations of the original panel scripts, unchanged, against the new
export: play counts and windows (ingest-plays-multiwindow.py), Biggest Binges
(patch-binges.py), Trips (patch-trips.py), Your Eras (patch-eras.py, patch-eras-deep.py)
and Obsession Arcs (patch-obsession-arcs.py). This Time of Year (MONTHLY) had no
saved generator, so its rule lives here.

Everything runs on a scratch copy. Only data lines may differ from the live page:
DATA, BINGES, TRIPS, ERAS, ERASD, OBSESS and MONTHLY. Any other difference stops the
run. Without --apply it reports what would change and leaves index.html alone.
--until trims the export to an earlier end date, for comparing against old data.

Football and children's songs stay out of the panels, as they always have (Ben
swapped Everton out of Track of the Year; guest.js keeps it off the racks). His
Spotify history includes his children's plays, so tracks he confirms as theirs go
in PANEL_EXCLUDE_TRACKS. Play counts in the track table are left alone.

Not covered: The Hunt, Unmined Albums and Playlisted need Spotify's Account data
export, and the stats panels with pasted snapshot figures (listening clock, listened
abroad, seasonal) are not recalculated here."""
import collections, datetime, glob, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OLD_HIST = '/tmp/sp_data/Spotify Extended Streaming History'
DATA_LINES = ['BINGES', 'TRIPS', 'ERAS', 'ERASD', 'OBSESS', 'MONTHLY']
# Kept out of every panel, never out of the track table.
PANEL_EXCLUDE_ARTISTS = ('everton f.c.',)
PANEL_EXCLUDE_TITLES = ('paddington bear',)
# The children's favourites, confirmed by Ben (11 Nov 2026): first artist and
# exact title, then the date their plays took over ('' = every play). Lovely Day
# was Ben's from 2017 to 2022; from 2023 it is played alongside children's music.
PANEL_EXCLUDE_TRACKS = {
    ('daft punk', 'one more time'): '',
    ('daft punk', 'around the world'): '',
    ('bill withers', 'lovely day - studio rio version'): '2023-01-01',
}


def excluded_sids(data):
    """Spotify ID -> first excluded date ('' = every play)."""
    found = {}
    for t in data:
        artist, title = t.get('a', '').lower(), t.get('t', '').lower()
        if not t.get('sid'):
            continue
        if artist.startswith(PANEL_EXCLUDE_ARTISTS) or any(x in title for x in PANEL_EXCLUDE_TITLES):
            found[t['sid']] = ''
        elif (artist.split(';')[0].strip(), title) in PANEL_EXCLUDE_TRACKS:
            found[t['sid']] = PANEL_EXCLUDE_TRACKS[(artist.split(';')[0].strip(), title)]
    return found


def in_panels(row, skip):
    sid = (row.get('spotify_track_uri') or '').split(':')[-1]
    return sid not in skip or row.get('ts', '')[:10] < skip[sid]


def load_history(folder, until):
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, 'Streaming_History_Audio_*.json'))):
        rows += [r for r in json.load(open(path)) if not until or r.get('ts', '')[:10] <= until]
    if not rows:
        sys.exit('No Streaming_History_Audio_*.json files found in ' + folder)
    return rows


def write_history(rows, folder):
    """One file the original scripts can glob, already trimmed to --until."""
    os.makedirs(folder)
    json.dump(rows, open(os.path.join(folder, 'Streaming_History_Audio_all.json'), 'w'))


def parse_data(html):
    start = html.index('const DATA=') + len('const DATA=')
    end = html.index('\n', start)
    text = html[start:end].rstrip().rstrip(';')
    return json.loads(text), start, start + len(text)


def run_original(name, work, history, edits=()):
    """Run a panel script against the scratch copy and hand back its variables.
    Scripts that also add page furniture stop at their own already-added checks
    or assertions; the data they calculated is still in the namespace."""
    source = open(os.path.join(HERE, name)).read()
    assert OLD_HIST in source, name + ' no longer reads the old history path'
    source = source.replace(OLD_HIST, history)
    for old, new in edits:
        assert len(re.findall(old, source)) == 1, f'{name}: expected one match for {old}'
        source = re.sub(old, lambda _m, new=new: new, source)
    space = {'__file__': os.path.join(work, name), '__name__': '__main__'}
    stopped = None
    cwd = os.getcwd()
    out = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        os.chdir(work)
        exec(compile(source, name, 'exec'), space)
    except AssertionError as error:
        stopped = str(error)
    finally:
        sys.stdout.close()
        sys.stdout = out
        os.chdir(cwd)
    return space, stopped


def set_line(html, name, value):
    line = 'var %s=%s;' % (name, json.dumps(value, separators=(',', ':'), ensure_ascii=False))
    found = re.findall(r'(?m)^var %s=.*;$' % name, html)
    assert len(found) == 1, f'expected exactly one "var {name}=" line, found {len(found)}'
    return html.replace(found[0], line, 1)


def get_line(html, name):
    found = re.findall(r'(?m)^var %s=(.*);$' % name, html)
    assert len(found) == 1, f'expected exactly one "var {name}=" line, found {len(found)}'
    return json.loads(found[0])


def monthly(data, rows, skip):
    """This Time of Year: for each calendar month, the 15 archive tracks most
    played (30 seconds or more) in that month across every year. Ties go to the
    track first played in that month."""
    tracks = {t['sid']: t for t in data if t.get('sid') and len(str(t['sid'])) == 22}
    rows = [r for r in rows if in_panels(r, skip)]
    counts = collections.defaultdict(collections.Counter)
    for r in sorted(rows, key=lambda r: r.get('ts', '')):
        uri = r.get('spotify_track_uri') or ''
        if not uri.startswith('spotify:track:') or (r.get('ms_played') or 0) < 30000:
            continue
        sid = uri.split(':')[-1]
        if sid in tracks and len(r.get('ts', '')) >= 7:
            counts[int(r['ts'][5:7])][sid] += 1
    result = {}
    for month in range(1, 13):
        ranked = counts[month].most_common(15)
        result[str(month)] = [[tracks[sid]['a'].split(';')[0] + ' — ' + tracks[sid]['t'], n, sid] for sid, n in ranked]
    return result


def main():
    argv = sys.argv[1:]
    until = ''
    if '--until' in argv:
        at = argv.index('--until')
        until = argv[at + 1] if at + 1 < len(argv) else sys.exit(__doc__)
        datetime.date.fromisoformat(until)
        del argv[at:at + 2]
    args = [a for a in argv if a != '--apply']
    if len(args) != 1 or args[0].startswith('--'):
        sys.exit(__doc__)
    rows = load_history(args[0], until)
    last = max(r.get('ts', '')[:10] for r in rows)
    ref = datetime.date.fromisoformat(last)
    live = open(os.path.join(HERE, 'index.html')).read()

    work = tempfile.mkdtemp(prefix='dj-archive-listening-')
    try:
        shutil.copy(os.path.join(HERE, 'index.html'), work)
        shutil.copy(os.path.join(HERE, 'genre-map.py'), work)  # patch-eras.py reads its genre buckets
        skip = excluded_sids(parse_data(live)[0])
        history, panel_history = os.path.join(work, 'history'), os.path.join(work, 'panel-history')
        write_history(rows, history)
        write_history([r for r in rows if in_panels(r, skip)], panel_history)

        run_original('ingest-plays-multiwindow.py', work, history,
                     [(r'REF = datetime\.date\(\d+, \d+, \d+\)', 'REF = datetime.date(%d, %d, %d)' % (ref.year, ref.month, ref.day))])
        for name in ('patch-binges.py', 'patch-trips.py', 'patch-eras.py'):
            _, stopped = run_original(name, work, panel_history)
            assert not stopped, f'{name} stopped: {stopped}'
        html = open(os.path.join(work, 'index.html')).read()

        space, _ = run_original('patch-eras-deep.py', work, panel_history)
        html = set_line(html, 'ERASD', space['ERASD'])
        space, _ = run_original('patch-obsession-arcs.py', work, panel_history,
                                [(r"\[t for t in DATA if t\.get\('pc'\)\]", "[t for t in DATA if t.get('pc') and t['sid'] not in %r]" % sorted(skip))])
        html = set_line(html, 'OBSESS', space['OBSESS'])
        data, _, _ = parse_data(html)
        html = set_line(html, 'MONTHLY', monthly(data, rows, skip))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Nothing but the data lines may have moved.
    before, after = live.split('\n'), html.split('\n')
    assert len(before) == len(after), 'line count changed'
    allowed = ('const DATA=',) + tuple('var %s=' % name for name in DATA_LINES)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    for i in changed:
        assert before[i].startswith(allowed) and after[i].startswith(allowed), f'unexpected change on line {i + 1}'

    old, _, _ = parse_data(live)
    new, _, _ = parse_data(html)
    assert len(old) == len(new), 'track count changed'
    keys = {'pc', 'fp', 'lp', 'p1', 'p2', 'p3', 'p5', 'p7', 'p10'}
    for a, b in zip(old, new):
        assert {k: v for k, v in a.items() if k not in keys} == {k: v for k, v in b.items() if k not in keys}, 'a track changed beyond its play fields'
    total = lambda tracks: sum(t.get('pc', 0) for t in tracks)
    print(f'history to {last}; {len(rows):,} rows')
    print(f'plays matched to the archive: {total(old):,} -> {total(new):,}')
    print(f'tracks with a play count: {sum(1 for t in old if t.get("pc")):,} -> {sum(1 for t in new if t.get("pc")):,} of {len(new):,}')
    print(f'tracks played in the last year: {sum(1 for t in old if t.get("p1")):,} -> {sum(1 for t in new if t.get("p1")):,}')
    for name in DATA_LINES:
        print(f'{name}: {"changed" if get_line(live, name) != get_line(html, name) else "same"}')
    if '--apply' in sys.argv:
        open(os.path.join(HERE, 'index.html'), 'w').write(html)
        print('index.html updated. Run python3 build.py --catalogue-only and the tests next.')
    else:
        out = os.path.join(tempfile.gettempdir(), 'dj-archive-listening-preview.html')
        open(out, 'w').write(html)
        print('dry run: index.html untouched. Preview written to ' + out)


if __name__ == '__main__':
    main()
