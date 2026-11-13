#!/usr/bin/env python3
"""Build discogs-connections.json from discogs-releases.json (no network).

Counts are numbers of distinct releases in the vinyl collection, never tracks.
A person is identified by Discogs artist id (name only where Discogs has no id).
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'discogs-releases.json'
OUT = HERE / 'discogs-connections.json'

INSTRUMENTS = ('bass', 'drum', 'guitar', 'piano', 'keyboard', 'sax', 'trumpet', 'trombone', 'flute', 'percussion',
               'conga', 'organ', 'synth', 'vibraphone', 'vibes', 'violin', 'viola', 'cello', 'horn', 'clarinet',
               'harp', 'rhodes', 'clavinet', 'timbales', 'bongos', 'strings', 'tuba', 'harmonica', 'flugelhorn',
               'oboe', 'bassoon', 'marimba', 'tambourine', 'cowbell', 'moog', 'mellotron', 'accordion', 'banjo',
               'sitar', 'tabla', 'kora', 'steel', 'cuica', 'berimbau', 'shekere', 'guiro', 'cavaquinho', 'reeds',
               'brass', 'woodwind', 'cornet', 'celesta', 'kalimba', 'talking drum', 'tres', 'bata', 'turntables',
               'scratches', 'programmed', 'drum programming', 'performer', 'musician', 'soloist', 'ensemble',
               'orchestra', 'conductor', 'leader', 'concertmaster')
NON_MUSIC = ('design', 'photo', 'artwork', 'art direction', 'liner notes', 'sleeve', 'cover', 'illustration',
             'layout', 'typography', 'painting', 'management', 'coordinator', 'a&r', 'legal', 'thanks', 'compiled',
             'research', 'supervised', 'product manager', 'graphics', 'lettering', 'calligraphy', 'film', 'creative director',
             'text by', 'translated', 'booking', 'promotion', 'public relations', 'crew', 'technician', 'logo',
             'concept', 'curated', 'licens', 'transferred', 'restoration', 'reissue')


def split_roles(role):
    parts, depth, cur = [], 0, ''
    for ch in role or '':
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def family(role):
    r = role.lower()
    base = re.sub(r'\[.*?\]', '', r).strip()
    if 'executive' in base and 'produc' in base:
        return 'executive_producer'
    if any(k in base for k in NON_MUSIC):
        return 'other'
    if 'produc' in base:
        return 'producer'
    if 'arrang' in base or 'orchestrated' in base:
        return 'arranger'
    if 'concertmaster' in base or 'concert master' in base:
        return 'instrumentalist'
    if 'master' in base or 'lacquer' in base or 'cut by' in base:
        return 'mastering'
    if 'remix' in base or 'edited by' in base or base == 'edit' or 're-edit' in base:
        return 'remixer'
    if 'engineer' in base or 'mixed' in base or 'recorded by' in base or base.startswith('mix') or 'recording' in base:
        return 'engineer_mixer'
    if any(k in base for k in ('written', 'composed', 'lyrics', 'songwriter', 'music by', 'words by', 'score')):
        return 'written_by'
    if 'vocal' in base or 'voice' in base or 'rap' == base or 'mc' == base or 'choir' in base or 'chorus' in base:
        return 'vocals'
    if any(k in base for k in INSTRUMENTS):
        return 'instrumentalist'
    return 'other'


def clean(name):
    return re.sub(r'\s\(\d+\)$', '', name or '').strip()


def main():
    state = json.loads(SRC.read_text())
    releases = state['releases']
    label_rel = defaultdict(set)
    label_name = {}
    people = defaultdict(lambda: {'name': '', 'by_family': defaultdict(set), 'roles': defaultdict(Counter),
                                  'as_main': set()})
    company = defaultdict(lambda: defaultdict(set))
    rinfo = {}
    style_count, genre_count, country_count, decade_count = Counter(), Counter(), Counter(), Counter()
    stats = Counter()

    for did, r in releases.items():
        main_names = [clean(a['name']) for a in r['artists']]
        main_ids = {a['id'] for a in r['artists'] if a.get('id')}
        rinfo[did] = {'artist': ' / '.join(main_names) or '?', 'title': r['title'], 'year': r.get('year') or None,
                      'label': clean(r['labels'][0]['name']) if r['labels'] else '', 'main_ids': main_ids,
                      'various': any(n.lower() == 'various' for n in main_names)}
        for g in r['genres']:
            genre_count[g] += 1
        for s in r['styles']:
            style_count[s] += 1
        if r.get('country'):
            country_count[r['country']] += 1
        if r.get('year'):
            decade_count[f"{r['year'] // 10 * 10}s"] += 1
        for l in r['labels']:
            key = l.get('id') or clean(l['name'])
            if clean(l['name']).lower() == 'not on label' or (l.get('name') or '').lower().startswith('not on label'):
                continue
            label_rel[key].add(did)
            label_name[key] = clean(l['name'])
        for c in r['companies']:
            company[(c['type'] or '?')][(c.get('id') or c['name'], clean(c['name']))].add(did)
        for a in r['artists']:
            if a.get('id') and clean(a['name']).lower() != 'various':
                p = people[a['id']]
                p['name'] = p['name'] or clean(a['name'])
                p['as_main'].add(did)
        credits = [(x, None) for x in r['extraartists']]
        for t in r['tracklist']:
            credits += [(x, t['title']) for x in t['extraartists']]
            for a in t['artists']:
                if a.get('id') and clean(a['name']).lower() != 'various':
                    p = people[a['id']]
                    p['name'] = p['name'] or clean(a['name'])
                    p['as_main'].add(did)
        has_rel = bool(r['extraartists'])
        has_trk = any(t['extraartists'] for t in r['tracklist'])
        stats['with_release_credits'] += has_rel
        stats['with_track_credits'] += has_trk
        stats['with_any_credit'] += (has_rel or has_trk)
        stats['with_label'] += bool([l for l in r['labels'] if not (l.get('name') or '').lower().startswith('not on label')])
        stats['with_companies'] += bool(r['companies'])
        fams_here = set()
        for x, _ in credits:
            key = x.get('id') or ('name:' + clean(x['name']))
            p = people[key]
            p['name'] = p['name'] or clean(x['name'])
            for role in split_roles(x['role']):
                f = family(role)
                p['by_family'][f].add(did)
                p['roles'][f][re.sub(r'\s*\[.*?\]', '', role).strip()] += 1
                fams_here.add(f)
        for f in fams_here:
            stats[f'releases_with_{f}'] += 1

    def rel_label(d):
        i = rinfo[d]
        return f"{i['artist']} – {i['title']} ({i['year'] or 'n.d.'})"

    top_labels = [{'label': label_name[k], 'releases': len(v), 'examples': [rel_label(d) for d in sorted(v, key=int)[:6]]}
                  for k, v in sorted(label_rel.items(), key=lambda kv: (-len(kv[1]), label_name[kv[0]]))[:40]]

    fams = ['producer', 'arranger', 'engineer_mixer', 'written_by', 'instrumentalist', 'vocals', 'mastering',
            'remixer', 'executive_producer']
    top_people = {}
    for f in fams:
        rows = []
        for key, p in people.items():
            n = len(p['by_family'].get(f, ()))
            if n >= 2:
                dids = p['by_family'][f]
                rows.append({'name': p['name'], 'discogs_artist_id': key if isinstance(key, int) else None,
                             'releases': n, 'distinct_main_artists': len({rinfo[d]['artist'] for d in dids}),
                             'roles': [r for r, _ in p['roles'][f].most_common(4)],
                             'on': [rel_label(d) for d in sorted(dids, key=int)[:8]]})
        rows.sort(key=lambda x: (-x['releases'], x['name']))
        top_people[f] = rows[:40]

    musical = ['producer', 'arranger', 'engineer_mixer', 'written_by', 'instrumentalist', 'vocals', 'remixer']
    overall = []
    for key, p in people.items():
        dids = set()
        for f in musical:
            dids |= p['by_family'].get(f, set())
        if len(dids) >= 2:
            overall.append({'name': p['name'], 'releases': len(dids),
                            'families': {f: len(p['by_family'][f]) for f in musical if p['by_family'].get(f)}})
    overall.sort(key=lambda x: (-x['releases'], x['name']))

    # Cross-artist links: a credited person (musical roles, mastering kept apart) on releases by different main artists,
    # where that person is not a main artist on those releases.
    links = []
    for key, p in people.items():
        per_rel = defaultdict(set)
        for f in musical + ['mastering']:
            for d in p['by_family'].get(f, ()):
                per_rel[d].add(f)
        outside = {d: fs for d, fs in per_rel.items() if key not in rinfo[d]['main_ids']}
        artists = {rinfo[d]['artist'] for d in outside if not rinfo[d]['various']}
        if len(artists) >= 2:
            only_mastering = all(fs == {'mastering'} for fs in outside.values())
            links.append({'person': p['name'], 'discogs_artist_id': key if isinstance(key, int) else None,
                          'kind': 'mastering_only' if only_mastering else 'musical',
                          'distinct_artists': len(artists), 'releases': len(outside),
                          'own_releases_in_collection': [rel_label(d) for d in sorted(p['as_main'], key=int)[:5]],
                          'credits': [{'release': rel_label(d), 'label': rinfo[d]['label'],
                                       'as': sorted(fs),
                                       'roles': sorted({re.sub(r'\s*\[.*?\]', '', role).strip()
                                                        for x in ([e for e in releases[d]['extraartists']] +
                                                                  [e for t in releases[d]['tracklist'] for e in t['extraartists']])
                                                        if (x.get('id') or ('name:' + clean(x['name']))) == key
                                                        for role in split_roles(x['role'])})[:8]}
                                      for d, fs in sorted(outside.items(), key=lambda kv: (rinfo[kv[0]]['year'] or 0))]})
    links.sort(key=lambda x: (x['kind'] != 'musical', -x['distinct_artists'], -x['releases'], x['person']))

    # Sidemen who are also leaders in the collection: own record on the shelf and credited on someone else's.
    leaders = [l for l in links if l['kind'] == 'musical' and l['own_releases_in_collection']]

    label_links = []
    for k, v in sorted(label_rel.items(), key=lambda kv: -len(kv[1])):
        arts = {rinfo[d]['artist'] for d in v if not rinfo[d]['various']}
        if len(arts) >= 3:
            label_links.append({'label': label_name[k], 'releases': len(v), 'distinct_artists': len(arts),
                                'artists': sorted(arts)[:25]})

    companies = {}
    for typ, d in company.items():
        rows = [{'name': name, 'releases': len(v), 'distinct_artists': len({rinfo[x]['artist'] for x in v}),
                 'examples': [rel_label(x) for x in sorted(v, key=int)[:5]]}
                for (_, name), v in d.items() if len(v) >= 2]
        rows.sort(key=lambda x: (-x['releases'], x['name']))
        if rows:
            companies[typ] = rows[:20]

    n = len(releases)
    out = {
        'meta': {'built': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'source': SRC.name,
                 'counting_unit': 'distinct Discogs releases in the vinyl collection',
                 'releases': n, 'failed': len(state.get('failed', {})),
                 'distinct_labels': len(label_rel), 'distinct_credited_people': len(people)},
        'coverage': {k: {'releases': v, 'share': round(v / n, 3)} for k, v in sorted(stats.items())},
        'top_labels': top_labels,
        'top_people_by_role_family': top_people,
        'top_people_overall_musical_roles': overall[:60],
        'cross_artist_links': links[:400],
        'sidemen_who_are_also_leaders_in_collection': leaders[:150],
        'labels_shared_by_3plus_artists': label_links[:60],
        'companies_shared': companies,
        'top_styles': style_count.most_common(30), 'top_genres': genre_count.most_common(15),
        'countries': country_count.most_common(15), 'decades': sorted(decade_count.items()),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'{n} releases, {len(label_rel)} labels, {len(people)} people, {len(links)} cross-artist links')
    for k, v in sorted(stats.items()):
        print(f'  {k}: {v} ({v / n:.0%})')


if __name__ == '__main__':
    main()
