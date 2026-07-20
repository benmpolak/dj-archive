#!/usr/bin/env python3
"""Gig Radar — upcoming London gigs matched to the archive.

Sources:
  - Resident Advisor GraphQL (all-London backbone: clubs + live, incl. Jazz Cafe, EartH,
    Village Underground, Corsica, XOYO...)
  - Koko whats-on (Next.js event tiles, full lineup in img alt)
  - EartH events page (slug parse)
  - Jazz Cafe whats-on (event cards with line-up lists)
Roundhouse has no scrapeable feed (JS-rendered, no JSON API) — partial coverage via RA only.

Matching: event's structured artist names (exact, normalised) + event title
(word-boundary phrase scan, artists with >=2 words or >=6 chars only).

Scoring (Ben's brief: weight on plays and new music):
  3*sqrt(total plays) + 8*sqrt(plays last 1y) + 3*sqrt(plays last 3y) + 1.2*tracks
  + 40 if any track added last 6 months, else +20 if last 12 months.

Usage: python3 gigs-fetch.py [--days 120] [--out gigs.html]
Re-run any time; output is fully regenerated. Writes gigs-data.json alongside for debugging.
"""
import argparse, json, re, sys, time, unicodedata, urllib.request
from datetime import date, timedelta
from collections import defaultdict

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HERE = __file__.rsplit('/', 1)[0]
TODAY = date.today()

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}

# names that appear as "artists" on listings but are noise
NAME_STOP = {'tba', 'tbc', 'guests', 'special guests', 'friends', 'more', 'live',
             'dj set', 'djs', 'residents', 'support', 'and friends', 'special guest'}

# single-word archive artists that are also everyday scene/genre words or first names —
# too ambiguous to match inside free-text event titles (lineup matches still allowed)
TITLE_STOP = {'jungle', 'underground', 'electronic', 'liquid', 'forest', 'pleasure',
              'sundown', 'garage', 'house', 'techno', 'disco', 'funk', 'soul', 'jazz',
              'gospel', 'orchestra', 'ensemble', 'collective', 'social', 'summer',
              'winter', 'sunset', 'sunrise', 'midnight', 'warehouse', 'paradise',
              'daughter', 'mother', 'brother', 'sister', 'lovers', 'dreams', 'magic',
              'joseph', 'simone', 'marcel', 'george', 'marie', 'james', 'thomas',
              'charlie', 'jamie', 'oscar', 'leon', 'otis', 'ruby', 'pearl',
              'outside', 'return', 'prince', 'inside', 'weekend', 'holiday'}


def http_get(url, referer=None, data=None, timeout=30):
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')


# ---------- archive artists ----------

def normalize(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace('&', ' and ').replace('+', ' and ')
    s = re.sub(r"[^a-z0-9]+", ' ', s).strip()
    if s.startswith('the '):
        s = s[4:]
    return s


def load_artists():
    html = open(f'{HERE}/index.html', encoding='utf-8').read()
    i = html.index('const DATA=[')
    data, _ = json.JSONDecoder().raw_decode(html[i + len('const DATA='):])
    acc = {}
    for t in data:
        # collab rows join artists with ';' — credit every artist on the track
        for name in [(t.get('a') or '').strip()] + \
                    ([p.strip() for p in t['a'].split(';')] if ';' in (t.get('a') or '') else []):
            _add_artist(acc, name, t)
    for r in acc.values():
        r['crate'] = max(r['crates'], key=r['crates'].get) if r['crates'] else ''
        del r['crates']
    return acc


def _add_artist(acc, name, t):
        norm = normalize(name)
        if not norm or norm in NAME_STOP:
            return
        r = acc.setdefault(norm, {'name': name, 'tracks': 0, 'plays': 0, 'p1': 0,
                                  'p3': 0, 'min_da': 999999, 'max_da': 0,
                                  'the': name.lower().startswith('the '),
                                  'crates': defaultdict(int)})
        r['tracks'] += 1
        r['plays'] += t.get('pc') or 0
        r['p1'] += t.get('p1') or 0
        r['p3'] += t.get('p3') or 0
        da = t.get('da') or 0
        if da:
            r['min_da'] = min(r['min_da'], da)
            r['max_da'] = max(r['max_da'], da)
        for c in t.get('c') or []:
            r['crates'][c] += 1


def yyyymm_ago(months):
    y, m = TODAY.year, TODAY.month - months
    while m <= 0:
        y, m = y - 1, m + 12
    return y * 100 + m


def artist_score(r):
    s = (3 * (r['plays'] ** 0.5) + 8 * (r['p1'] ** 0.5)
         + 3 * (r['p3'] ** 0.5) + 1.2 * r['tracks'])
    if r['max_da'] >= yyyymm_ago(6):
        s += 40
    elif r['max_da'] >= yyyymm_ago(12):
        s += 20
    return round(s, 1)


def badges(r):
    b = []
    if r['min_da'] >= yyyymm_ago(12) and r['min_da'] < 999999:
        b.append(('new', 'New find'))
    if r['p1'] >= 6:
        b.append(('hot', 'On repeat'))
    if r['plays'] >= 50:
        b.append(('heavy', 'Heavy rotation'))
    if not b and r['tracks'] == 1:
        b.append(('deep', 'Deep cut'))
    return b


# ---------- date helpers ----------

def infer_year(day, month):
    """Listings give day+month, no year: assume the next occurrence."""
    try:
        d = date(TODAY.year, month, day)
    except ValueError:
        return None
    if d < TODAY - timedelta(days=7):
        d = date(TODAY.year + 1, month, day)
    return d


# ---------- sources ----------

def fetch_ra(days):
    query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $pageSize: Int, $page: Int) {
      eventListings(filters: $filters, pageSize: $pageSize, page: $page) {
        data { event { id title date contentUrl
                       artists { name } venue { name } } }
        totalResults
      }
    }"""
    events, seen, page = [], set(), 1
    while page <= 60:
        variables = {'filters': {'areas': {'eq': 13},
                                 'listingDate': {'gte': str(TODAY),
                                                 'lte': str(TODAY + timedelta(days=days))}},
                     'pageSize': 100, 'page': page}
        try:
            resp = json.loads(http_get('https://ra.co/graphql', referer='https://ra.co/events/uk/london',
                                       data={'query': query, 'variables': variables}))
        except Exception as e:
            print(f'  RA page {page} failed: {e}', file=sys.stderr)
            break
        rows = (resp.get('data') or {}).get('eventListings') or {}
        batch = rows.get('data') or []
        if not batch:
            break
        for row in batch:
            e = row['event']
            if e['id'] in seen:
                continue
            seen.add(e['id'])
            events.append({
                'date': e['date'][:10],
                'title': e['title'].strip(),
                'venue': (e.get('venue') or {}).get('name') or '',
                'url': 'https://ra.co' + e['contentUrl'],
                'names': [a['name'] for a in e.get('artists') or []],
                'source': 'RA',
            })
        total = rows.get('totalResults') or 0
        if page * 100 >= total:
            break
        page += 1
        time.sleep(0.5)
    return events


def fetch_koko():
    html = http_get('https://www.koko.co.uk/whats-on')
    events = []
    for m in re.finditer(
            r'<a href="(/events/[^"]+)">.*?alt="([^"]*)".*?__title">([^<]+)</div>'
            r'<div class="[^"]*__date">([^<]+)</div>', html, re.S):
        href, alt, title, dstr = m.groups()
        dm = re.search(r'(\d{1,2})\s+([A-Za-z]{3})', dstr)
        if not dm:
            continue
        d = infer_year(int(dm.group(1)), MONTHS.get(dm.group(2).lower(), 0) or 1)
        if not d:
            continue
        names = [n.strip() for n in re.split(r'\s*[+,]\s*|\s+x\s+', alt) if n.strip()]
        events.append({'date': str(d), 'title': title.strip(), 'venue': 'KOKO',
                       'url': 'https://www.koko.co.uk' + href, 'names': names, 'source': 'KOKO'})
    return events


def fetch_earth():
    html = http_get('https://earthackney.co.uk/events/')
    events, seen = [], set()
    for m in re.finditer(r'href="(https://earthackney\.co\.uk/events/([a-z0-9-]+)-(\d{1,2})(?:st|nd|rd|th)-'
                         r'([a-z]{3,4})-earth-london-tickets-[a-z0-9]+/?)"', html):
        url, slug, day, mon = m.groups()
        if url in seen:
            continue
        seen.add(url)
        d = infer_year(int(day), MONTHS.get(mon[:3].lower(), 0) or 1)
        if not d:
            continue
        title = slug.replace('-', ' ').title()
        events.append({'date': str(d), 'title': title, 'venue': 'EartH',
                       'url': url, 'names': [title], 'source': 'EartH'})
    return events


def fetch_jazzcafe():
    html = http_get('https://thejazzcafe.com/whats-on')
    events = []
    for block in re.split(r'<li\s+data-genre', html)[1:]:
        dm = re.search(r'event-date[^>]*>\s*\w+<span>(\d{1,2})</span>([A-Za-z]{3})', block)
        tm = re.search(r'<h2 class="event-title">(.*?)</h2>', block, re.S)
        um = re.search(r'href="(https://thejazzcafe\.com/event/[^"]+)"', block)
        if not (dm and tm and um):
            continue
        d = infer_year(int(dm.group(1)), MONTHS.get(dm.group(2).lower(), 0) or 1)
        if not d:
            continue
        title_html = tm.group(1)
        title = re.sub(r'<span class="host">.*?</span>', '', title_html, flags=re.S)
        title = re.sub(r'<[^>]+>', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        names = [re.sub(r'<[^>]+>', '', n).strip()
                 for n in re.findall(r'<li>(.*?)</li>', block, re.S)]
        events.append({'date': str(d), 'title': title or names[0] if names else title,
                       'venue': 'The Jazz Cafe', 'url': um.group(1),
                       'names': [n for n in names if n], 'source': 'JazzCafe'})
    return events


# ---------- matching ----------

def clean_name(n):
    n = re.sub(r'\((?:dj set|live|full live band|band|solo|uk|album launch)[^)]*\)', '', n, flags=re.I)
    n = re.sub(r'\b(?:dj set|full live band)\b', '', n, flags=re.I)
    return n.strip(' -–—:')


def match_event(ev, artists):
    hits = {}
    for raw in ev['names']:
        norm = normalize(clean_name(raw))
        if norm and norm not in NAME_STOP and norm in artists:
            hits[norm] = 'lineup'
    tnorm = ' ' + normalize(ev['title']) + ' '
    for norm, r in artists.items():
        if norm in hits or norm in NAME_STOP:
            continue
        single = ' ' not in norm
        if single and (len(norm) < 6 or norm in TITLE_STOP):
            continue
        # free-text title matches need real archive presence; deep cuts
        # (1 track, barely played) only surface via structured lineups
        if r['tracks'] < 2 and r['plays'] < 3:
            continue
        # "The Futures" must appear as "the futures", not bare "futures"
        needle = f' the {norm} ' if (r['the'] and single) else f' {norm} '
        if needle in tnorm:
            hits[norm] = 'title'
    return hits


def drop_generic_title_matches(per_event_hits):
    """A name that title-matches 3+ different events is a scene word, not a booking."""
    counts = defaultdict(set)
    for ev, hits in per_event_hits:
        for norm, how in hits.items():
            if how == 'title':
                counts[norm].add((ev['date'], ev['title']))
    generic = {n for n, evs in counts.items() if len(evs) >= 3}
    if generic:
        print(f"  dropped generic title-words: {sorted(generic)}")
    for _, hits in per_event_hits:
        for n in list(hits):
            if hits[n] == 'title' and n in generic:
                del hits[n]


# ---------- render ----------

def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def fmt_da(da):
    if not da or da >= 999999:
        return ''
    return date(da // 100, da % 100, 1).strftime('%b %Y')


BADGE_CSS = {'new': ('rgba(96,232,160,0.12)', '#60e8a0'),
             'hot': ('rgba(232,64,96,0.12)', '#ff8098'),
             'heavy': ('rgba(232,160,64,0.14)', '#e8a040'),
             'deep': ('rgba(64,160,232,0.12)', '#40a0e8')}


def render(matches, n_events, n_artists, out):
    matches = sorted(matches, key=lambda m: m['date'])
    picks = sorted(matches, key=lambda m: -m['score'])[:12]
    upd = TODAY.strftime('%-d %b %Y')

    def why(m):
        r = m['artist']
        bits = [f"{r['tracks']} track{'s' if r['tracks'] != 1 else ''} in the archive"]
        if r['plays']:
            bits.append(f"{r['plays']} plays")
        if r['p1']:
            bits.append(f"{r['p1']} this year")
        if r['crate']:
            bits.append(r['crate'])
        if fmt_da(r['max_da']):
            bits.append('added ' + fmt_da(r['max_da']))
        return ' · '.join(bits)

    def badge_html(m):
        h = ''.join(
            f'<span class="bdg" style="background:{bg};color:{fg}">{lbl}</span>'
            for (k, lbl), (bg, fg) in ((b, BADGE_CSS[b[0]]) for b in badges(m['artist'])))
        if re.search(r'tribute|the music of|the best of|birthday|celebrat|songbook|plays the',
                     m['title'], re.I):
            h += ('<span class="bdg" style="background:rgba(160,64,232,0.12);'
                  'color:#b07ae0">Tribute / celebration</span>')
        return h

    def others(m):
        rest = [r['name'] for r in m['co']]
        if not rest:
            rest = [clean_name(a) for a in m['all_names']
                    if normalize(clean_name(a)) != normalize(m['artist']['name'])]
        return (' <span class="also">with ' + esc(', '.join(rest[:4])) + '</span>') if rest else ''

    def card(m):
        d = date.fromisoformat(m['date'])
        return f'''<a class="card" href="{esc(m['url'])}" target="_blank" rel="noopener">
  <div class="card-date">{d.strftime('%a %-d %b').upper()}</div>
  <div class="card-artist">{esc(m['artist']['name'])}</div>
  <div class="card-venue">{esc(m['venue'])}</div>
  <div class="badges">{badge_html(m)}</div>
  <div class="why">{why(m)}</div>
</a>'''

    def row(m):
        d = date.fromisoformat(m['date'])
        title = '' if normalize(m['title']) == normalize(m['artist']['name']) else \
            f'<span class="ev-title">{esc(m["title"])}</span>'
        return f'''<div class="row">
  <div class="r-date"><span class="r-dow">{d.strftime('%a').upper()}</span><span class="r-day">{d.day}</span><span class="r-mon">{d.strftime('%b').upper()}</span></div>
  <div class="r-main">
    <div class="r-artist">{esc(m['artist']['name'])}{others(m)} {badge_html(m)}</div>
    <div class="r-sub">{title}{('<span class="dot">·</span>' if title else '')}<span class="r-venue">{esc(m['venue'])}</span></div>
    <div class="why">{why(m)}</div>
  </div>
  <a class="tix" href="{esc(m['url'])}" target="_blank" rel="noopener">Tickets</a>
</div>'''

    by_month = defaultdict(list)
    for m in matches:
        by_month[m['date'][:7]].append(m)
    sections = ''
    for ym in sorted(by_month):
        label = date.fromisoformat(ym + '-01').strftime('%B %Y')
        sections += f'<h2>{label}</h2>\n' + '\n'.join(row(m) for m in by_month[ym])

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gig Radar — DJ Archive</title>
<style>
:root{{--bg:#0a0a0f;--card:#12121a;--card2:#181824;--border:#1e1e2e;--text:#e0e0e8;--dim:#6a6a80;--accent:#e8a040;--pink:#ff69b4}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',Roboto,sans-serif;padding:28px 18px 60px}}
.wrap{{max-width:860px;margin:0 auto}}
h1{{font-size:1.3em;font-weight:700;text-transform:uppercase;letter-spacing:0.18em;
  background:linear-gradient(135deg,var(--accent),var(--pink));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;display:inline-block}}
.sub{{color:var(--dim);font-size:0.8em;margin:6px 0 26px}}
.sub a{{color:var(--accent);text-decoration:none}}
h2{{font-size:0.72em;text-transform:uppercase;letter-spacing:0.16em;color:var(--accent);opacity:0.9;margin:30px 0 10px}}
.eyebrow{{font-size:0.72em;text-transform:uppercase;letter-spacing:0.16em;color:var(--accent);opacity:0.9;margin:4px 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
.card{{display:block;background:linear-gradient(160deg,#13131c,#101018);border:1px solid var(--border);border-radius:12px;padding:14px 16px;text-decoration:none;color:var(--text);transition:border-color .15s}}
.card:hover{{border-color:var(--accent)}}
.card-date{{font-size:0.68em;letter-spacing:0.12em;color:var(--accent);font-weight:600}}
.card-artist{{font-weight:700;font-size:1.02em;margin:4px 0 2px}}
.card-venue{{color:var(--dim);font-size:0.78em}}
.badges{{margin-top:6px}}
.bdg{{display:inline-block;border-radius:6px;padding:1px 7px;font-size:0.62em;font-weight:600;letter-spacing:0.04em;margin-right:4px}}
.why{{color:var(--dim);font-size:0.7em;margin-top:6px;line-height:1.5}}
.row{{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:8px}}
.r-date{{display:flex;flex-direction:column;align-items:center;min-width:44px;color:var(--dim)}}
.r-dow{{font-size:0.6em;letter-spacing:0.1em}}
.r-day{{font-size:1.25em;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}}
.r-mon{{font-size:0.6em;letter-spacing:0.1em}}
.r-main{{flex:1;min-width:0}}
.r-artist{{font-weight:700;font-size:0.98em}}
.also{{color:var(--dim);font-weight:400;font-size:0.85em}}
.r-sub{{color:var(--dim);font-size:0.78em;margin-top:2px}}
.ev-title{{color:#9a9ab0}}
.dot{{margin:0 6px}}
.tix{{padding:7px 14px;border-radius:10px;font-size:0.74em;font-weight:600;border:1px solid var(--border);background:var(--card2);color:var(--text);text-decoration:none;white-space:nowrap}}
.tix:hover{{border-color:var(--accent);color:var(--accent)}}
.foot{{color:var(--dim);font-size:0.7em;margin-top:40px;line-height:1.7}}
@media(max-width:560px){{.row{{flex-wrap:wrap}}.tix{{margin-left:58px}}}}
</style></head><body><div class="wrap">
<h1>Gig Radar</h1>
<div class="sub">Upcoming London shows matched to the archive · updated {upd} ·
<a href="index.html">← back to the archive</a></div>
<div class="eyebrow">Top picks</div>
<div class="grid">
{''.join(card(m) for m in picks)}
</div>
{sections}
<div class="foot">Matched {len(matches)} shows from {n_events} London listings against {n_artists:,} archive artists.<br>
Sources: Resident Advisor (all London venues), KOKO, EartH, The Jazz Cafe. Roundhouse has no open feed — partial coverage via RA.<br>
One DJ&rsquo;s ears, no algorithm. Refresh: <code>python3 gigs-fetch.py</code></div>
</div></body></html>'''
    open(out, 'w', encoding='utf-8').write(html)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=120)
    ap.add_argument('--out', default=f'{HERE}/gigs.html')
    args = ap.parse_args()

    print('Loading archive artists...')
    artists = load_artists()
    print(f'  {len(artists)} unique artists')

    events = []
    for label, fn in [('RA', lambda: fetch_ra(args.days)), ('KOKO', fetch_koko),
                      ('EartH', fetch_earth), ('Jazz Cafe', fetch_jazzcafe)]:
        try:
            batch = fn()
            print(f'  {label}: {len(batch)} events')
            events.extend(batch)
        except Exception as e:
            print(f'  {label} FAILED: {e}', file=sys.stderr)

    horizon = str(TODAY + timedelta(days=args.days))
    events = [e for e in events if str(TODAY) <= e['date'] <= horizon]
    if len(events) < 100:
        sys.exit(f'Only {len(events)} events fetched — sources look down; '
                 'keeping the existing gigs.html.')

    per_event = [(ev, match_event(ev, artists)) for ev in events]
    drop_generic_title_matches(per_event)

    # one entry per (event, matched artist), deduped across sources by artist+date.
    # RA is processed first so its (true) venue wins — the Jazz Cafe site also
    # lists off-site shows under its own banner.
    matches, seen = [], set()
    for ev, hits in per_event:
        for norm, how in hits.items():
            key = (norm, ev['date'])
            if key in seen:
                continue
            seen.add(key)
            matches.append({'date': ev['date'], 'title': ev['title'], 'venue': ev['venue'],
                            'url': ev['url'], 'source': ev['source'], 'how': how,
                            'artist': artists[norm], 'all_names': ev['names'],
                            'score': artist_score(artists[norm])})

    # merge multiple matched artists on the same listing into one entry
    grouped = {}
    for m in matches:
        gk = (m['date'], normalize(m['venue']), normalize(m['title']))
        g = grouped.setdefault(gk, m | {'co': []})
        if m is not g and m['artist'] is not g['artist']:
            if m['score'] > g['score']:
                g['co'].append(g['artist'])
                g.update({k: m[k] for k in ('artist', 'score', 'how')})
            else:
                g['co'].append(m['artist'])
    matches = list(grouped.values())
    for m in matches:
        m['score'] += 5 * len(m['co'])
    print(f'{len(events)} events in window -> {len(matches)} matched shows')

    json.dump({'generated': str(TODAY), 'events': len(events),
               'matches': [{**{k: m[k] for k in ('date', 'title', 'venue', 'url',
                                                 'source', 'how', 'score')},
                            'artist': m['artist']['name'],
                            'co': [r['name'] for r in m['co']]} for m in matches]},
              open(f'{HERE}/gigs-data.json', 'w'), indent=1)
    render(matches, len(events), len(artists), args.out)
    print(f'Wrote {args.out}')


if __name__ == '__main__':
    main()
