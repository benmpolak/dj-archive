#!/usr/bin/env python3
"""Detect listening trips from raw streaming history (all events incl. skims).
Trip = burst of one or more artists over a few days, merged when overlapping."""
import json, glob, datetime
from collections import defaultdict

KIDS = {'duggee & the squirrels','bluey','mojo swoptops','super simple songs',
 'toddler fun learning','dream supplier','hey duggee','cocomelon','pinkfong',
 'rené aubry','the wiggles','kidz bop kids','kpop demon hunters cast','huddle',
 'gracie\'s corner','ms rachel','sesame street','baby shark','lullaby baby trio',
 'disney junior','frozen','various artists'}

events = defaultdict(lambda: defaultdict(int))   # artist -> date -> count
tracksper = defaultdict(lambda: defaultdict(set))
for f in glob.glob('/tmp/sp_data/Spotify Extended Streaming History/Streaming_History_Audio_*.json'):
    for r in json.load(open(f)):
        a = r.get('master_metadata_album_artist_name')
        t = r.get('master_metadata_track_name')
        ts = (r.get('ts') or '')[:10]
        if not a or not ts or a.lower() in KIDS: continue
        events[a][ts] += 1
        tracksper[a][ts].add(t)

def to_date(s): return datetime.date.fromisoformat(s)

# per-artist clusters: consecutive days (gap <= 2), >= 8 events, >= 3 distinct tracks
clusters = []
for a, days in events.items():
    ds = sorted(days)
    run = [ds[0]]
    for d in ds[1:]:
        if (to_date(d) - to_date(run[-1])).days <= 2:
            run.append(d)
        else:
            clusters.append((a, run)); run = [d]
    clusters.append((a, run))
cl = []
for a, run in clusters:
    n = sum(events[a][d] for d in run)
    tr = set().union(*(tracksper[a][d] for d in run))
    if n >= 8 and len(tr) >= 3 and len(run) <= 14:
        cl.append({'a': a, 'start': run[0], 'end': run[-1], 'n': n, 'tracks': len(tr)})

# merge overlapping artist-clusters into trips
cl.sort(key=lambda c: c['start'])
trips = []
for c in cl:
    placed = False
    for t in trips:
        if c['start'] <= t['end'] and c['end'] >= t['start']:
            t['start'] = min(t['start'], c['start']); t['end'] = max(t['end'], c['end'])
            t['arts'].append((c['a'], c['n'])); t['n'] += c['n']
            placed = True; break
    if not placed:
        trips.append({'start': c['start'], 'end': c['end'], 'arts': [(c['a'], c['n'])], 'n': c['n']})

trips.sort(key=lambda t: t['start'], reverse=True)
print(f'{len(trips)} trips detected')
for t in trips[:40]:
    arts = sorted(t['arts'], key=lambda x: -x[1])
    label = ', '.join(a for a, _ in arts[:3]) + (f' +{len(arts)-3}' if len(arts) > 3 else '')
    print(f"  {t['start']}..{t['end']}  {t['n']:4d} ev  {label}")
