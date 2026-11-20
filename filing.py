#!/usr/bin/env python3
"""File new tracks the way the rest of the archive is filed.

Tracks imported straight from Spotify arrive with no tags and often in Uncategorized.
This fills them from the archive's own filing, never from outside sources:

  P  the playlists the track sits in (add-ledger.json), judged by how the rest of each
     playlist is filed
  A  how the same artist's other tracks are filed
  R  how the remixer's / co-artists' own tracks are filed (supporting evidence only)
  G  the track's genre words, translated through tracks that carry the same words

Rules, approved 20 November 2026 for tracks added from September 2026:
  - a label is applied only at score >= 0.8, and only when the top score is >= 0.6
  - R alone is never enough
  - at most 3 tags and 2 crates; only empty tags and Uncategorized crates are filled
  - nothing else on a track is touched; vibe, BPM and genre words are never invented
  - tracks filed here are listed in filing-ledger.json and never count as evidence

    python3 filing.py            preview against index.html
    python3 filing.py --apply    back up index.html, write it and filing-ledger.json;
                                 then run: python3 build.py --catalogue-only
"""
import collections
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import sys

SINCE = 202609
LABEL_MIN, TOP_MIN = 0.8, 0.6
MAX_TAGS, MAX_CRATES = 3, 2
WEIGHT = {'P': 3.0, 'A': 2.0, 'R': 1.0, 'G': 1.5}
MIN_EVIDENCE = {'P': 15, 'A': 2, 'R': 3, 'G': 8}
PLAYLIST_CONSISTENCY = 0.6
UNFILED_CRATES = {'Uncategorized', 'Uncategorised'}
MIXED_PLAYLIST = re.compile(
    r'^(january|february|march|april|may|june|july|august|september|october|november|december) \d{4}$|^[0-9/ ]+$', re.I)
REMIXER = re.compile(r"[-(\[]\s*([^-()\[\]]{2,40}?)(?:'s)?\s+(remix|rework|re-edit|edit|dub|mix|refix|version)\b", re.I)


def _norm(text):
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


def _artists(track):
    return [_norm(a) for a in (track.get('a') or '').split(';') if a.strip()] or ['']


def _words(track):
    return [g.strip().lower() for g in (track.get('g') or '').split(',') if g.strip()]


def _remixer(track):
    match = REMIXER.search(track.get('t') or '')
    return _norm(match.group(1)) if match else None


def labels(track, field):
    if field == 'c':
        return [c for c in (track.get('c') or []) if c not in UNFILED_CRATES]
    return list(track.get('tags') or [])


def _model(data, playlists_of, field, auto):
    """Count how filed tracks carry each label, per playlist, artist and genre word."""
    count = {s: collections.defaultdict(collections.Counter) for s in 'PAG'}
    total = {s: collections.Counter() for s in 'PAG'}
    for track in data:
        if track.get('sid') in auto:
            continue  # filed by this module: not evidence
        if not (labels(track, 'tags') and labels(track, 'c')):
            continue  # evidence is only tracks Ben has fully filed
        found = labels(track, field)
        keys = [('P', p) for p in playlists_of.get(track.get('sid'), ())]
        keys.append(('A', _artists(track)[0]))
        keys += [('G', w) for w in _words(track)]
        for signal, key in keys:
            total[signal][key] += 1
            for label in found:
                count[signal][key][label] += 1
    return count, total


def _score(track, playlists_of, model):
    count, total = model

    def share(signal, key):
        n = total[signal][key]
        if n < MIN_EVIDENCE['R' if signal == 'R' else signal]:
            return None
        return {label: c / n for label, c in count[signal][key].items()}

    def merge(shares, mode):
        merged = collections.Counter()
        for s in shares:
            for label, value in s.items():
                merged[label] = max(merged[label], value) if mode == 'max' else merged[label] + value / len(shares)
        return merged

    parts = []
    playlists = [share('P', p) for p in playlists_of.get(track.get('sid'), ()) if not MIXED_PLAYLIST.match(p)]
    playlists = [s for s in playlists if s and max(s.values(), default=0) >= PLAYLIST_CONSISTENCY]
    if playlists:
        parts.append(('P', merge(playlists, 'max')))
    artist = share('A', _artists(track)[0])
    if artist:
        parts.append(('A', artist))
    lead = _artists(track)[0]
    others = [o for o in _artists(track)[1:] + [_remixer(track)] if o and o != lead]
    related = []
    for other in others:
        n = total['A'][other]
        if n >= MIN_EVIDENCE['R']:
            related.append({label: c / n for label, c in count['A'][other].items()})
    if related:
        parts.append(('R', merge(related, 'mean')))
    words = [s for s in (share('G', w) for w in _words(track)) if s]
    if words:
        parts.append(('G', merge(words, 'mean')))
    if not parts:
        return [], []
    weight = sum(WEIGHT[s] for s, _ in parts)
    score = collections.Counter()
    for signal, shares in parts:
        for label, value in shares.items():
            score[label] += WEIGHT[signal] * value / weight
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked, [s for s, _ in parts]


def _pick(track, playlists_of, model, cap):
    ranked, signals = _score(track, playlists_of, model)
    if not ranked or ranked[0][1] < TOP_MIN or not ({'P', 'A', 'G'} & set(signals)):
        return [], signals, ranked
    return [label for label, value in ranked if value >= LABEL_MIN][:cap], signals, ranked


def propose(data, ledger, auto=None, since=SINCE):
    """Return the fills this module would make. `ledger` is add-ledger.json; `auto` is filing-ledger.json."""
    auto = auto or {}
    playlists_of = collections.defaultdict(list)
    for name in sorted(ledger):
        for sid in ledger[name]:
            playlists_of[sid].append(name)
    models = {'tags': _model(data, playlists_of, 'tags', auto), 'c': _model(data, playlists_of, 'c', auto)}
    changes = []
    for index, track in enumerate(data):
        if (track.get('da') or 0) < since or not track.get('sid'):
            continue
        change = {'i': index, 'sid': track['sid'], 'a': track.get('a'), 't': track.get('t')}
        for field, cap in (('tags', MAX_TAGS), ('c', MAX_CRATES)):
            if labels(track, field):
                continue
            picked, signals, ranked = _pick(track, playlists_of, models[field], cap)
            if picked:
                change[field] = {'before': track.get(field), 'after': sorted(picked) if field == 'c' else picked,
                                 'signals': signals, 'scores': [[l, round(v, 2)] for l, v in ranked[:3]]}
        if 'tags' in change or 'c' in change:
            changes.append(change)
    return changes


def apply(data, changes, auto, date):
    """Write the fills into `data` and record them in `auto`. Only empty fields are ever filled."""
    for change in changes:
        track = data[change['i']]
        if track.get('sid') != change['sid']:
            raise ValueError('Filing change does not match its track.')
        entry = auto.setdefault(change['sid'], {})
        for field in ('tags', 'c'):
            if field not in change:
                continue
            if labels(track, field):
                raise ValueError('Filing would overwrite existing %s.' % field)
            track[field] = list(change[field]['after'])
            entry[field] = list(change[field]['after'])
        entry['on'] = date
    return len(changes)


def dump_ledger(auto):
    return json.dumps(auto, ensure_ascii=False, indent=0, sort_keys=True) + '\n'


def main():
    root = Path(__file__).resolve().parent
    html = (root / 'index.html').read_text(encoding='utf-8')
    start = html.index('const DATA=') + len('const DATA=')
    data, size = json.JSONDecoder().raw_decode(html[start:])
    ledger = json.loads((root / 'add-ledger.json').read_text())
    ledger_path = root / 'filing-ledger.json'
    auto = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    changes = propose(data, ledger, auto)
    since = [t for t in data if (t.get('da') or 0) >= SINCE]
    summary = {'since_tracks': len(since), 'to_file': len(changes),
               'tags': sum('tags' in c for c in changes), 'crates': sum('c' in c for c in changes),
               'left_without_tags': sum(not labels(t, 'tags') for t in since) - sum('tags' in c for c in changes),
               'left_uncategorized': sum(not labels(t, 'c') for t in since) - sum('c' in c for c in changes)}
    if '--apply' in sys.argv and changes:
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(root / 'index.html', root / ('_backup-pre-filing-%s.html' % stamp))
        apply(data, changes, auto, dt.date.today().isoformat())
        packed = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        (root / 'index.html').write_text(html[:start] + packed + html[start + size:], encoding='utf-8')
        ledger_path.write_text(dump_ledger(auto))
        summary['applied'] = True
    for change in changes:
        print(change['a'], '|', change['t'], '|', change.get('tags', {}).get('after'), change.get('c', {}).get('after'))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
