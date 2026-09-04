#!/usr/bin/env python3
"""Gig Radar v2 — upcoming London gigs matched to the archive.

Sources:
  - Resident Advisor GraphQL (all-London backbone: clubs + live + festivals)
  - KOKO, EartH, Jazz Cafe, Roundhouse, Alexandra Palace, Barbican,
    Eventim Apollo, Spiritland King's Cross, The O2 Arena (site scrapes)
  - AMG/Live Nation internal API (O2 Academy Brixton, Shepherd's Bush Empire,
    Forum Kentish Town, Islington Academies)
  - Ronnie Scott's via the r.jina.ai reader service (their site doesn't serve
    plain fetches; the reader renders it)
  - Blue Note London via Yoast tm_events sitemap + event detail pages
  - Ticketmaster Discovery API IF env TM_API_KEY is set (optional extra)
Gaps (checked 2026-07-20): Union Chapel (JS-only); Space Talk & One Eighty One
programme on Instagram only.

Matching: explicit performer/lineup names only. Event titles NEVER qualify an
artist, even when a scraper previously copied the title into its names field. Weighted on plays + recency + newly-added artists.
Tribute/covers/"vs" nights are dropped entirely (is_tribute).
first_seen per show persists across runs via gigs-data.json -> "Just announced".

Usage: python3 gigs-fetch.py [--days 365] [--out gigs.html]
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from collections import defaultdict

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HERE = __file__.rsplit('/', 1)[0]
TODAY = date.today()

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}

NAME_STOP = {'tba', 'tbc', 'guests', 'special guests', 'friends', 'more', 'live',
             'dj set', 'djs', 'residents', 'support', 'and friends', 'special guest'}

# hard signals always mean covers/tribute; soft ones ("celebrating", "vs") only
# count when the artist was matched from the free-text title — a structured
# lineup entry means the act is genuinely on the bill (Band of Horses
# "Celebrating 20 Years" is really them; "Fred Again vs Daft Punk" is not Daft Punk)
TRIBUTE_HARD_RE = re.compile(
    r'tribute|the music of|the songs of|the best of|songbook|plays the|'
    r're[: ]?imagined|orchestral|symphonic|candlelight|sounds of|queen of soul|'
    r'an evening of|remembering|absolute bowie|nearly dan', re.I)
TRIBUTE_SOFT_RE = re.compile(r'celebrat|birthday|revisited|\bvs\.?\s', re.I)


def is_tribute(title, how):
    return bool(TRIBUTE_HARD_RE.search(title)
                or (how == 'title' and TRIBUTE_SOFT_RE.search(title)))

DAY_RE = re.compile(r'day party|all day|day &amp; night|day and night|rooftop|'
                    r'day fest|in the park|garden party|block party', re.I)

CLUB_VENUES = ('fabric', 'xoyo', 'phonox', 'corsica', 'ministry of sound',
               'the cause', 'colour factory', 'oval space', 'drumsheds', 'egg ',
               'night tales', 'fold', 'venue mot', 'm.o.t', 'peckham audio',
               'jumbi', 'spanners', 'basing house', 'dalston den', 'the pickle',
               'werkhaus', 'lion & lamb', 'ormside', 'rye wax', 'club makossa')


class _Redirect308(urllib.request.HTTPRedirectHandler):
    """urllib follows 301/302/303/307 but not 308 — treat 308 like 307."""
    def http_error_308(self, req, fp, code, msg, hdrs):
        return self.http_error_307(req, fp, 307, msg, hdrs)


_OPENER = urllib.request.build_opener(_Redirect308)


def http_get(url, referer=None, data=None, timeout=30):
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    raw = _OPENER.open(req, timeout=timeout).read()
    if raw[:2] == b'\x1f\x8b':  # some servers gzip regardless of Accept-Encoding
        import gzip
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', 'replace')


# ---------- archive artists ----------

def normalize(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace('&', ' and ').replace('+', ' and ')
    s = re.sub(r"[^a-z0-9]+", ' ', s).strip()
    if s.startswith('the '):
        s = s[4:]
    return s


# artists in the archive who have died — any listing carrying their name is a
# tribute/celebration night, never the act (names are normalize()d)
DEAD_ARTISTS = {normalize(n) for n in (
    'Tim Maia', 'Marvin Gaye', 'Fela Kuti', 'Aretha Franklin', 'Otis Redding',
    'Amy Winehouse', 'Prince', 'Michael Jackson', 'David Bowie', 'James Brown',
    'Isaac Hayes', 'Barry White', 'Luther Vandross', 'Whitney Houston',
    'Teddy Pendergrass', 'Curtis Mayfield', 'Donny Hathaway', 'Bill Withers',
    'Gil Scott-Heron', 'Roy Ayers', 'Quincy Jones', 'Sergio Mendes',
    'Antonio Carlos Jobim', 'Tom Jobim', 'Joao Gilberto', 'Astrud Gilberto',
    'Gal Costa', 'Elza Soares', 'Elis Regina', 'Erasmo Carlos', 'Wilson Simonal',
    'Cassiano', 'Miles Davis', 'John Coltrane', 'Alice Coltrane',
    'Pharoah Sanders', 'Thelonious Monk', 'Charles Mingus', 'Bill Evans',
    'Grant Green', 'Lee Morgan', 'Art Blakey', 'Horace Silver',
    'Cannonball Adderley', 'Dexter Gordon', 'McCoy Tyner', 'Freddie Hubbard',
    'Donald Byrd', 'Roy Hargrove', 'Ahmad Jamal', 'Wayne Shorter', 'Chick Corea',
    'Tony Allen', 'Manu Dibango', 'Cesaria Evora', 'Nina Simone', 'Etta James',
    'Sam Cooke', 'Sarah Vaughan', 'Ella Fitzgerald', 'Billie Holiday',
    'Louis Armstrong', 'Nat King Cole', 'Frank Sinatra', 'MF DOOM', 'J Dilla',
    'Nujabes', 'Mac Miller', 'The Notorious B.I.G.', '2Pac',
    'Frankie Knuckles', 'Larry Levan', 'Ron Hardy', 'David Mancuso',
    'Andrew Weatherall', 'Avicii', 'Sophie', 'DJ Rashad', 'Paul Johnson',
    'George Michael', 'Leonard Cohen', 'Lou Reed', 'Tom Petty', 'Fats Domino',
    'Bobby Womack', 'Sharon Jones', 'Charles Bradley', 'Betty Davis',
    'Pop Smoke', 'Jaco Pastorius', 'Weldon Irvine', 'Leon Ware',
    'Minnie Riperton', 'Phyllis Hyman', 'Grover Washington Jr.', 'Dennis Brown')}

# Listings occasionally leak into the London feeds with a non-London venue.
# Keep the public promise clean rather than quietly stretching "London".
OUTSIDE_LONDON_VENUES = {normalize(n) for n in (
    'C.S. Lewis Square', 'Dullingham Polo Club', 'Gaswrx Birmingham',
    'Kelvedon Hall', 'Preston Park, Brighton',
    'Summer Outdoor Garage Festival - Wheelers Farm Chelmsford')}



def load_artists():
    html = open(f'{HERE}/index.html', encoding='utf-8').read()
    i = html.index('const DATA=[')
    data, _ = json.JSONDecoder().raw_decode(html[i + len('const DATA='):])
    acc = {}
    for t in data:
        names = [(t.get('a') or '').strip()]
        if ';' in names[0]:
            names += [p.strip() for p in names[0].split(';')]
        for name in names:
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
    if not b and r['tracks'] == 1:
        b.append(('deep', 'Deep cut'))
    return b


def infer_year(day, month):
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
        data { event { id title date startTime contentUrl
                       artists { name } venue { name } } }
        totalResults
      }
    }"""
    events, seen, page = [], set(), 1
    while page <= 120:
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
            start = (e.get('startTime') or '')[11:16]
            events.append({'date': e['date'][:10], 'title': e['title'].strip(),
                           'venue': (e.get('venue') or {}).get('name') or '',
                           'url': 'https://ra.co' + e['contentUrl'],
                           'names': [a['name'] for a in e.get('artists') or []],
                           'start': start, 'source': 'RA', 'hint': '', 'lineup_verified': True})
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
                       'url': 'https://www.koko.co.uk' + href, 'names': names,
                       'start': '', 'source': 'KOKO', 'hint': 'gig'})
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
                       'url': url, 'names': [title], 'start': '',
                       'source': 'EartH', 'hint': 'gig'})
    return events


def fetch_jazzcafe():
    html = http_get('https://thejazzcafe.com/whats-on')
    events = []
    for block in re.split(r'<li\s+data-genre', html)[1:]:
        if re.search(r'data-outsidelondon="yes"', block):
            continue
        etype = re.search(r'data-event-type="([^"]*)"', block)
        hint = 'dj' if (etype and 'club' in etype.group(1).lower()) else 'gig'
        dm = re.search(r'event-date[^>]*>\s*\w+<span>(\d{1,2})</span>([A-Za-z]{3})', block)
        tm = re.search(r'<h2 class="event-title">(.*?)</h2>', block, re.S)
        um = re.search(r'href="(https://thejazzcafe\.com/event/[^"]+)"', block)
        if not (dm and tm and um):
            continue
        d = infer_year(int(dm.group(1)), MONTHS.get(dm.group(2).lower(), 0) or 1)
        if not d:
            continue
        title = re.sub(r'<span class="host">.*?</span>', '', tm.group(1), flags=re.S)
        title = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', title)).strip()
        lineup = re.search(r'<ul class="line-up[^"]*">(.*?)</ul>', block, re.S)
        names = [re.sub(r'<[^>]+>', '', n).strip()
                 for n in re.findall(r'<li>(.*?)</li>', lineup.group(1), re.S)] if lineup else []
        events.append({'date': str(d), 'title': title or (names[0] if names else ''),
                       'venue': 'The Jazz Cafe', 'url': um.group(1),
                       'names': [n for n in names if n], 'start': '',
                       'source': 'JazzCafe', 'hint': hint, 'lineup_verified': True})
    return events


def _detail_event(url, venue, hint):
    """Fetch one event detail page, extract title + date from schema/meta."""
    try:
        h = http_get(url)
    except Exception:
        return None
    # JSON-LD Event first
    for m in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m)
        except Exception:
            continue
        items = d if isinstance(d, list) else d.get('@graph', [d])
        for it in items:
            t = str(it.get('@type', ''))
            if 'Event' in t:
                sd = (it.get('startDate') or '')[:10]
                nm = it.get('name') or ''
                if sd and nm and 'Comedy' not in t:
                    return {'date': sd, 'title': nm.strip(), 'venue': venue, 'url': url,
                            'names': performer_names(it.get('performer')), 'lineup_verified': True,
                            'status': it.get('eventStatus', ''), 'start': (it.get('startDate') or '')[11:16],
                            'source': venue, 'hint': hint}
                return None
    # fallback: visible date like "Fri 19 Sep 2026" or "19 Sep 2026"
    tm = re.search(r'<title>([^<|]+)', h)
    dm = re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d\d)', h)
    if tm and dm:
        d = date(int(dm.group(3)), MONTHS[dm.group(2).lower()], int(dm.group(1)))
        title = tm.group(1).strip()
        return {'date': str(d), 'title': title, 'venue': venue, 'url': url,
                'names': [title], 'start': '', 'source': venue, 'hint': hint}
    return None


def fetch_roundhouse():
    html = http_get('https://www.roundhouse.org.uk/whats-on/')
    urls = sorted(set(re.findall(r'href="(https://www\.roundhouse\.org\.uk/whats-on/[a-z0-9-]+/)"', html)))
    urls = [u for u in urls if not re.search(r'podcast|comedy', u)][:80]
    events = []
    with ThreadPoolExecutor(8) as ex:
        for ev in ex.map(lambda u: _detail_event(u, 'The Roundhouse', 'gig'), urls):
            if ev:
                events.append(ev)
    return events


def fetch_allypally():
    html = http_get('https://www.alexandrapalace.com/whats-on/')
    events, seen = [], set()
    for m in re.finditer(
            r'<p class="dates uc"><strong>([^<]+)</strong></p>\s*'
            r'<a href="(https://www\.alexandrapalace\.com/whats-on/[^"]+)"[^>]*>'
            r'<h3>([^<]+)</h3>', html):
        dstr, url, title = m.groups()
        if url in seen:
            continue
        seen.add(url)
        dm = re.search(r'(\d{1,2})\s*(?:-|–|&ndash;)?\s*(?:\d{1,2}\s+)?([A-Za-z]{3})[a-z]*\s+(20\d\d)', dstr)
        if not dm:
            continue
        d = date(int(dm.group(3)), MONTHS.get(dm.group(2).lower(), 1), int(dm.group(1)))
        events.append({'date': str(d), 'title': title.strip(), 'venue': 'Alexandra Palace',
                       'url': url, 'names': [title.strip()], 'start': '',
                       'source': 'AllyPally', 'hint': 'gig'})
    return events


def fetch_barbican():
    urls = set()
    for page in range(0, 4):
        try:
            h = http_get(f'https://www.barbican.org.uk/whats-on/contemporary-music?page={page}')
        except Exception:
            break
        found = set(re.findall(r'href="(/whats-on/\d{4}/event/[a-z0-9-]+)"', h))
        if not found - urls:
            break
        urls |= found
    events = []
    with ThreadPoolExecutor(8) as ex:
        for ev in ex.map(lambda u: _detail_event('https://www.barbican.org.uk' + u,
                                                 'Barbican', 'gig'), sorted(urls)[:80]):
            if ev:
                events.append(ev)
    return events


RONNIE_DATE_RE = re.compile(
    r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})'
    r'(?:\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)?'
    r'(?:\s+(20\d\d))?\s*(?:-|–|$)')


def fetch_ronnies():
    """Ronnie Scott's find-a-show, rendered through the r.jina.ai reader service
    (their site doesn't serve plain fetches). Markdown pattern per show:
    a date line ("Tue 21 Jul 2026" / "Wed 22 - Wed 29 Jul 2026"), then
    "## Title", then a "[Find out more](url)" link."""
    events, seen = [], set()
    for page in range(1, 16):
        try:
            md = http_get(f'https://r.jina.ai/https://www.ronniescotts.co.uk/find-a-show?page={page}',
                          timeout=60)
        except Exception:
            break
        pend_date, added = None, 0
        for line in md.splitlines():
            line = line.strip()
            dm = RONNIE_DATE_RE.match(line)
            if dm:
                day = int(dm.group(1))
                mon = dm.group(2)
                yr = dm.group(3)
                if not mon:  # "Wed 22 - Wed 29 Jul 2026": month/year only at range end
                    tail = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d\d)', line)
                    if tail:
                        mon, yr = tail.group(1), tail.group(2)
                if mon:
                    if yr:
                        try:
                            pend_date = date(int(yr), MONTHS[mon.lower()[:3]], day)
                        except ValueError:
                            pend_date = None
                    else:
                        pend_date = infer_year(day, MONTHS[mon.lower()[:3]])
                continue
            if line.startswith('## ') and pend_date:
                title = line[3:].strip()
                slug = re.sub(r'[^a-z0-9]+', '-', title.lower().replace("'", '').replace('\u2019', '')).strip('-')
                if (title, str(pend_date)) not in seen:
                    seen.add((title, str(pend_date)))
                    events.append({'date': str(pend_date), 'title': title,
                                   'venue': "Ronnie Scott's",
                                   'url': f'https://www.ronniescotts.co.uk/find-a-show/{slug}',
                                   'names': [title], 'start': '',
                                   'source': 'RonnieScotts', 'hint': 'gig'})
                    added += 1
                continue
            lm = re.search(r'\[Find out more\]\((https://www\.ronniescotts\.co\.uk[^)]+)\)', line)
            if lm and events:
                events[-1]['url'] = lm.group(1)
        if not added:
            break
        time.sleep(2)
    return events


def _fetch_showtime(page_url, venue, link_host):
    events = []
    for off in ('', '/24', '/48', '/72'):
        try:
            h = http_get(f'{page_url}{off}')
        except Exception:
            break
        blocks = [b for b in h.split('eventItem entry')[1:] if ':href=' not in b[:400]]
        found = 0
        for b in blocks:
            um = re.search(r'href="(https://' + re.escape(link_host) + r'/events/detail/[^"]+)"', b)
            tm = re.search(r'<h3 class="title[^"]*">\s*<a[^>]*>([^<]+)</a>', b)
            dm = re.search(r'm-date__day">\s*(\d{1,2})\s*</span><span class="m-date__month">\s*'
                           r'([A-Za-z]{3})[a-z]*\s*</span>(?:<span class="m-date__year">\s*(\d{4}))?', b)
            if not (um and tm and dm):
                continue
            yr = int(dm.group(3)) if dm.group(3) else TODAY.year
            try:
                dd = date(yr, MONTHS.get(dm.group(2).lower(), 1), int(dm.group(1)))
            except ValueError:
                continue
            title = tm.group(1).strip()
            events.append({'date': str(dd), 'title': title, 'venue': venue,
                           'url': um.group(1), 'names': [title], 'start': '',
                           'source': venue, 'hint': 'gig'})
            found += 1
        if not found:
            break
    seen, out = set(), []
    for e in events:
        k = (e['title'], e['date'])
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def fetch_theo2():
    return _fetch_showtime('https://www.theo2.co.uk/events/venue/the-o2-arena',
                           'The O2 Arena', 'www.theo2.co.uk')


def fetch_ovo():
    return _fetch_showtime('https://www.ovoarena.co.uk/events',
                           'OVO Arena Wembley', 'www.ovoarena.co.uk')


WEMBLEY_DATE_RE = re.compile(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d\d)')


def fetch_wembley():
    h = http_get('https://www.wembleystadium.com/events')
    events, seen = [], set()
    for b in h.split('fa-filter-content__item')[1:]:
        b = b[:5000]
        lm = re.search(r'href="(/events/[^"]+)"', b)
        txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', b))
        dm = WEMBLEY_DATE_RE.search(txt)
        if not (lm and dm):
            continue
        try:
            dd = date(int(dm.group(3)), MONTHS[dm.group(2).lower()[:3]], int(dm.group(1)))
        except ValueError:
            continue
        title = txt[dm.end():].split('Find Out More')[0]
        title = re.sub(r'^\s*(?:TBC|\d{2}:\d{2})\s*', '', title).strip()
        if not title or (title, str(dd)) in seen:
            continue
        seen.add((title, str(dd)))
        events.append({'date': str(dd), 'title': title, 'venue': 'Wembley Stadium',
                       'url': 'https://www.wembleystadium.com' + lm.group(1),
                       'names': [title], 'start': '', 'source': 'Wembley', 'hint': 'gig'})
    return events



def fetch_openair():
    """Regent's Park Open Air Theatre — summer gig strand (Doves, Bunnymen...)."""
    h = http_get('https://openairtheatre.com/whats-on')
    events, seen = [], set()
    for b in re.split(r'<article class="ProductionTeaser', h)[1:]:
        um = re.search(r'href="(https://openairtheatre\.com/production/[^"]+)"', b)
        dm = re.search(r'ProductionTeaser-content-dates">\s*(\d{1,2})\s+([A-Za-z]+)', b)
        tm = re.search(r'alt="[^"]*"[^>]*>.*?<h\d[^>]*>([^<]+)</h\d>', b, re.S) or \
             re.search(r'ProductionTeaser-content-title[^>]*>([^<]+)<', b)
        title = (tm.group(1).strip() if tm else
                 um.group(1).rstrip('/').rsplit('/', 1)[-1].replace('-', ' ').title() if um else '')
        if not (um and dm and title) or um.group(1) in seen:
            continue
        seen.add(um.group(1))
        mon = MONTHS.get(dm.group(2).lower()[:3], 0)
        if not mon:
            continue
        d = infer_year(int(dm.group(1)), mon)
        if not d:
            continue
        events.append({'date': str(d), 'title': title, 'venue': "Regent's Park Open Air Theatre",
                       'url': um.group(1), 'names': [title], 'start': '',
                       'source': 'OpenAir', 'hint': 'gig'})
    return events


def fetch_spiritland():
    html = http_get('https://spiritland.com/whats-on/')
    events = []
    for m in re.finditer(
            r'<p class="title"><a href="(https://spiritland\.com/events/[^"]+)">([^<]+)</a></p>\s*'
            r'<p class="time"><a[^>]*>(\d{2})/(\d{2})/(\d{4})\s+(\d{2}:\d{2})</a>', html):
        url, title, dd, mm, yyyy, start = m.groups()
        events.append({'date': f'{yyyy}-{mm}-{dd}', 'title': title.strip(),
                       'venue': "Spiritland King's Cross", 'url': url,
                       'names': [title.strip()], 'start': start,
                       'source': 'Spiritland', 'hint': 'dj'})
    return events


def fetch_bluenote():
    """Blue Note London (Covent Garden, opened Sept 2026). The what's-on page
    is client-rendered by Ticketweb's event-discovery plugin, but Yoast's
    tm_events sitemap lists every event page, and each page server-renders a
    <time> block plus a Ticketmaster URL carrying the full date
    (...-london-29-11-2026/event/...). Duplicate slugs (-2, -3...) are the
    early/late seatings of the same night — deduped by (title, date)."""
    try:
        xml = http_get('https://www.bluenotejazz.com/london/tm_events-sitemap.xml')
    except Exception:
        return []
    urls = re.findall(r'<loc>(https://www\.bluenotejazz\.com/london/tm-event/[^<]+)</loc>', xml)

    def one(u):
        """A run's every seating page renders the WHOLE run's group listing
        (all nights, both seatings) — collect every distinct TM date on the
        page; cross-page dupes collapse in the (title, date) dedupe below."""
        try:
            h = http_get(u)
        except Exception:
            return []
        tm = re.search(r'<title>([^<|]+)', h)
        if not tm:
            return []
        title = re.sub(r'&#?\w+;', lambda m: {'&amp;': '&', '&#039;': "'",
                       '&#8217;': '’'}.get(m.group(0), ' '), tm.group(1)).strip()
        dates = {f'{yyyy}-{mm}-{dd}' for dd, mm, yyyy in re.findall(
            r'ticketmaster\.[a-z.]+/[a-z0-9-]*?-(\d{2})-(\d{2})-(\d{4})/event/', h)}
        if not dates:
            dm = re.search(r"class='day'>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+"
                           r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})", h)
            if not dm:
                return []
            inferred = infer_year(int(dm.group(2)), MONTHS[dm.group(1).lower()])
            if not inferred:
                return []
            dates = {str(inferred)}
        st = re.search(r"class='time'>(\d{1,2}):(\d{2})\s*(AM|PM)", h)
        start = ''
        if st:
            hh = int(st.group(1)) % 12 + (12 if st.group(3) == 'PM' else 0)
            start = f'{hh:02d}:{st.group(2)}'
        return [{'date': d, 'title': title, 'venue': 'Blue Note London', 'url': u,
                 'names': [title], 'start': start,
                 'source': 'BlueNote', 'hint': 'gig'} for d in sorted(dates)]

    events, seen = [], set()
    with ThreadPoolExecutor(8) as ex:
        for batch in ex.map(one, urls[:200]):
            for ev in batch:
                key = (ev['title'].lower(), ev['date'])
                if key in seen:
                    continue
                seen.add(key)
                events.append(ev)
    return events


AMG_SLUGS = {'O2 Academy Brixton': 'o2academybrixton',
             "O2 Shepherd's Bush Empire": 'o2shepherdsbushempire',
             'O2 Forum Kentish Town': 'o2forumkentishtown',
             'O2 Academy Islington': 'o2academyislington',
             'O2 Academy2 Islington': 'o2academyislington'}


def fetch_amg():
    """Live Nation / Academy Music Group London rooms via their site's own
    search API (found in their JS bundle; CityIds 102908 = London)."""
    events, page = [], 1
    while page <= 25:
        d = json.loads(http_get('https://www.academymusicgroup.com/__api/search/events'
                                f'?culture=en-GB&CityIds=102908&Page={page}'))
        docs = d.get('documents') or []
        if not docs:
            break
        for x in docs:
            vname = (x.get('venue') or {}).get('name') or ''
            slug = AMG_SLUGS.get(vname, '')
            url = ('https://www.academymusicgroup.com/' + slug + x['url']) if slug and x.get('url') \
                else 'https://www.academymusicgroup.com'
            names = [a.get('name', '') for a in x.get('lineup') or []]
            events.append({'date': (x.get('eventDate') or '')[:10], 'title': x.get('name', ''),
                           'venue': vname, 'url': url,
                           'names': [n for n in names if n],
                           'start': x.get('doorTime') or '', 'source': 'AMG', 'hint': 'gig', 'lineup_verified': True})
        if page * 20 >= (d.get('total') or 0):
            break
        page += 1
        time.sleep(0.3)
    return events


def fetch_apollo():
    html = http_get('https://www.eventimapollo.com/events')
    urls = sorted(set(re.findall(r'href="(/events/[a-z0-9-]+)"', html)))[:100]
    events = []
    with ThreadPoolExecutor(8) as ex:
        for ev in ex.map(lambda u: _detail_event('https://www.eventimapollo.com' + u,
                                                 'Eventim Apollo', 'gig'), urls):
            if ev:
                events.append(ev)
    return events


def fetch_ticketmaster(days):
    key = os.environ.get('TM_API_KEY')
    if not key:
        return []
    events, page = [], 0
    while page < 5:
        u = ('https://app.ticketmaster.com/discovery/v2/events.json?'
             f'apikey={key}&city=London&countryCode=GB&classificationName=music'
             f'&size=200&page={page}&sort=date,asc'
             f'&startDateTime={TODAY}T00:00:00Z'
             f'&endDateTime={TODAY + timedelta(days=min(days, 365))}T00:00:00Z')
        try:
            d = json.loads(http_get(u))
        except Exception as e:
            print(f'  TM page {page} failed: {e}', file=sys.stderr)
            break
        for e in (d.get('_embedded') or {}).get('events', []):
            venues = (e.get('_embedded') or {}).get('venues') or [{}]
            atts = (e.get('_embedded') or {}).get('attractions') or []
            events.append({'date': ((e.get('dates') or {}).get('start') or {}).get('localDate', ''),
                           'title': e.get('name', ''), 'venue': venues[0].get('name', ''),
                           'url': e.get('url', ''), 'names': [a.get('name', '') for a in atts],
                           'start': ((e.get('dates') or {}).get('start') or {}).get('localTime', '')[:5],
                           'source': 'Ticketmaster', 'hint': 'gig', 'lineup_verified': True,
                           'status': (e.get('dates') or {}).get('status', {}).get('code', '')})
        if page >= (d.get('page') or {}).get('totalPages', 1) - 1:
            break
        page += 1
        time.sleep(0.3)
    return events


# ---------- matching ----------

def clean_name(n):
    n = re.sub(r'\((?:dj set|live|full live band|band|solo|uk|album launch)[^)]*\)', '', n, flags=re.I)
    n = re.sub(r'\b(?:dj set|full live band)\b', '', n, flags=re.I)
    return n.strip(' -–—:')


# Ben's vetoes — artists that pass the rules but he doesn't want gigs for.
# Add names here as they come up.
EXCLUDE_ARTISTS = {normalize(n) for n in (
    'Bruno Mars', 'Jarreau Vandal', 'Church', 'Movement', 'MOVEMENT')}


def too_thin(r):
    """One-track artists need real engagement: 5+ plays ever, or a recent add
    that's actually been played. Kills 'who even is this' matches while keeping
    genuine one-edit artists (Hunee, Tim Reaper) and fresh finds."""
    return (r['tracks'] == 1 and r['plays'] < 5
            and not (r['max_da'] >= yyyymm_ago(6) and r['plays'] >= 1))


def match_event(ev, artists):
    hits = {}
    if not ev.get("lineup_verified") or is_cancelled(ev):
        return hits
    for raw in ev.get("names", []):
        norm = normalize(clean_name(raw))
        if not norm or norm in NAME_STOP or norm not in artists:
            continue
        r = artists[norm]
        if too_thin(r):
            continue
        if ' ' not in norm and r['tracks'] < 2 and r['plays'] < 10:
            continue
        hits[norm] = 'lineup'
    return hits


def classify(ev, title):
    """gig | dj | day"""
    hour = int(ev['start'][:2]) if re.match(r'\d\d:\d\d', ev.get('start') or '') else None
    if DAY_RE.search(title) or (hour is not None and 11 <= hour <= 16):
        return 'day'
    if ev.get('hint') in ('gig', 'dj'):
        return ev['hint']
    if re.search(r'\(live\)|\blive\b', title, re.I):
        return 'gig'
    v = ev['venue'].lower()
    if any(c in v for c in CLUB_VENUES):
        return 'dj'
    return 'dj' if ev['source'] == 'RA' else 'gig'


# ---------- render ----------

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def fmt_da(da):
    if not da or da >= 999999:
        return ''
    return date(da // 100, da % 100, 1).strftime('%b %Y')


BADGE_CSS = {'new': ('rgba(96,232,160,0.12)', '#60e8a0'),
             'hot': ('rgba(232,64,96,0.12)', '#ff8098'),
             'heavy': ('rgba(232,160,64,0.14)', '#e8a040'),
             'deep': ('rgba(64,160,232,0.12)', '#40a0e8')}

TYPE_LABEL = {'gig': 'Live gig', 'dj': 'DJ night', 'day': 'Day party'}


def render(matches, n_events, n_artists, sources_note, out, public=False, generated=None):
    matches = sorted(matches, key=lambda m: (m['date'], -m['score']))
    fresh_cut = str(TODAY - timedelta(days=7))
    picks, picked_artists = [], set()
    soon = [m for m in matches if m['date'] <= str(TODAY + timedelta(days=30))]
    for m in sorted(soon or matches, key=lambda m: -m['score']):
        artist_name = m['artist']['name']
        if artist_name in picked_artists:
            continue
        picked_artists.add(artist_name)
        picks.append(m)
        if len(picks) == 3:
            break
    picks.sort(key=lambda m: (m['date'], -m['score']))
    upd = date.fromisoformat(generated or str(TODAY)).strftime('%-d %b %Y')
    venues = sorted({m['venue'] for m in matches if m['venue']}, key=str.lower)
    crates = sorted({m['artist']['crate'] for m in matches if m['artist']['crate']},
                    key=lambda c: (-sum(1 for m in matches if m['artist']['crate'] == c), c))
    months = sorted({m['date'][:7] for m in matches})
    n_new = sum(1 for m in matches if m['first_seen'] >= fresh_cut)

    def why(m):
        r = m['artist']
        bits = [f"{r['tracks']} archive track{'s' if r['tracks'] != 1 else ''}"]
        if public:
            if r['crate']:
                bits.append(r['crate'])
            return ' · '.join(bits)
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
        if m['first_seen'] >= fresh_cut:
            h = '<span class="bdg bdg-just">New this week</span>' + h
        return h

    def attrs(m):
        extras = ' '.join([r['name'] for r in m['co']] + [clean_name(a) for a in m['all_names']])
        text = f"{m['artist']['name']} {extras} {m['title']} {m['venue']}".lower()
        event_key = f"{m['date']}|{m['artist']['name']}|{m['venue']}"
        return (f'data-v="{esc(m["venue"])}" data-mo="{m["date"][:7]}" '
                f'data-c="{esc(m["artist"]["crate"])}" data-t="{m["etype"]}" '
                f'data-n="{1 if m["first_seen"] >= fresh_cut else 0}" '
                f'data-d="{m["date"]}" data-key="{esc(event_key)}" '
                f'data-title="{esc(m["title"])}" data-artist="{esc(m["artist"]["name"])}" '
                f'data-url="{esc(m["url"])}" '
                f'data-s="{esc(text)}"')

    def event_actions(m):
        nm = esc(m['artist']['name'])
        return (f'<button class="mini-action save-btn" type="button" '
                f'aria-label="Save {nm}" aria-pressed="false" title="Save">☆</button>'
                f'<button class="mini-action cal-btn" type="button" '
                f'aria-label="Add {nm} to calendar" title="Add to calendar">+ Cal</button>'
                f'<a class="mini-action" href="index.html?hear={quote(m["artist"]["name"])}">Hear five tracks</a>')

    def card(m):
        d = date.fromisoformat(m['date'])
        nm = esc(m['artist']['name'])
        return f'''<div class="card" {attrs(m)}>
  <a class="card-cover" href="{esc(m['url'])}" target="_blank" rel="noopener" aria-label="Tickets: {nm}"></a>
  <div class="card-top"><span class="card-date">{d.strftime('%a %-d %b').upper()}</span><span class="card-type">{TYPE_LABEL[m['etype']]}</span></div>
  <div class="card-artist"><a class="a-link" href="index.html#find={nm}" onclick="try{{localStorage.setItem('gr_find',this.dataset.a)}}catch(e){{}}" data-a="{nm}" title="See them in the archive">{nm}</a><a class="sp-link" href="https://open.spotify.com/search/{nm}" target="_blank" rel="noopener" title="Open in Spotify">&#9654;</a></div>
  <div class="card-event">{esc(m['title'])}</div>
  <div class="card-venue">{esc(m['venue'])}</div>
  <div class="badges">{badge_html(m)}</div>
  {f'<div class="why">{why(m)}</div>' if why(m) else ''}
  <div class="card-actions">{event_actions(m)}<a class="mini-action" href="{esc(m['url'])}" target="_blank" rel="noopener">Tickets</a></div>
</div>'''

    def row(m):
        d = date.fromisoformat(m['date'])
        title = '' if normalize(m['title']) == normalize(m['artist']['name']) else \
            f'<span class="ev-title">{esc(m["title"])}</span>'
        co = ''
        if m['co']:
            co = ' <span class="also">with ' + esc(', '.join(r['name'] for r in m['co'][:4])) + '</span>'
        elif len(m['all_names']) > 1:
            rest = [clean_name(a) for a in m['all_names']
                    if normalize(clean_name(a)) != normalize(m['artist']['name'])]
            if rest:
                co = ' <span class="also">with ' + esc(', '.join(rest[:4])) + '</span>'
        return f'''<div class="row" {attrs(m)}>
  <div class="r-date"><span class="r-dow">{d.strftime('%a').upper()}</span><span class="r-day">{d.day}</span><span class="r-mon">{d.strftime('%b').upper()}</span></div>
  <div class="r-main">
    <div class="r-artist"><a class="a-link" href="index.html#find={esc(m['artist']['name'])}" onclick="try{{localStorage.setItem('gr_find',this.dataset.a)}}catch(e){{}}" data-a="{esc(m['artist']['name'])}" title="See them in the archive">{esc(m['artist']['name'])}</a><a class="sp-link" href="https://open.spotify.com/search/{esc(m['artist']['name'])}" target="_blank" rel="noopener" title="Open in Spotify">&#9654;</a><span class="r-type">{TYPE_LABEL[m['etype']]}</span>{co} {badge_html(m)}</div>
    <div class="r-sub">{title}{('<span class="dot">·</span>' if title else '')}<span class="r-venue">{esc(m['venue'])}</span></div>
    {f'<div class="why">{why(m)}</div>' if why(m) and not public else ''}
  </div>
  <div class="row-actions">{event_actions(m)}<a class="tix" href="{esc(m['url'])}" target="_blank" rel="noopener">Tickets</a></div>
</div>'''

    by_month = defaultdict(list)
    for m in matches:
        by_month[m['date'][:7]].append(m)
    sections = ''
    for ym in sorted(by_month):
        label = date.fromisoformat(ym + '-01').strftime('%B %Y')
        sections += (f'<h2 class="mh" data-mo="{ym}">{label} '
                     f'<span class="mh-n">{len(by_month[ym])}</span></h2>\n'
                     + '\n'.join(row(m) for m in by_month[ym]))

    month_chips = ''.join(
        f'<button class="fc fc-mo" data-mo="{ym}" type="button">{date.fromisoformat(ym + "-01").strftime("%b")}'
        f'{" ’" + ym[2:4] if ym[:4] != str(TODAY.year) else ""}</button>'
        for ym in months)
    crate_chips = ''.join(f'<button class="fc fc-c" data-c="{esc(c)}" type="button">{esc(c)}</button>' for c in crates)
    venue_opts = '<option value="">All venues</option>' + ''.join(
        f'<option value="{esc(v)}">{esc(v)}</option>' for v in venues)

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gig Radar — DJ Archive</title>
<meta name="description" content="Upcoming London gigs and DJ nights, hand-filtered through one DJ's 17,000-track archive.">
<link rel="canonical" href="https://benmpolak.github.io/dj-archive/{'gigs-share.html' if public else 'gigs.html'}">
<link rel="icon" href="assets/dj-archive-logo.svg" type="image/svg+xml">
<meta property="og:title" content="Gig Radar — DJ Archive">
<meta property="og:description" content="Upcoming London gigs and DJ nights, selected from 14 years of music collected by ear. No algorithm.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://benmpolak.github.io/dj-archive/{'gigs-share.html' if public else 'gigs.html'}">
<meta property="og:image" content="https://benmpolak.github.io/dj-archive/assets/gig-radar-social.png">
<meta name="twitter:card" content="summary_large_image">
<style>
:root{{--bg:#0a0a0f;--card:#12121a;--card2:#181824;--border:#1e1e2e;--text:#e0e0e8;--dim:#6a6a80;--accent:#e8a040;--pink:#ff69b4;--green:#60e8a0}}
*{{box-sizing:border-box;margin:0;padding:0}}
.visually-hidden{{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',Roboto,sans-serif;padding-bottom:80px}}
.wrap{{max-width:880px;margin:0 auto;padding:0 18px}}
header.hero{{background:linear-gradient(160deg,#13131c 0%,#101018 55%,#11111a 100%);border-bottom:1px solid var(--border);padding:34px 0 22px;margin-bottom:14px}}
h1{{font-size:1.5em;font-weight:700;text-transform:uppercase;letter-spacing:0.2em;
  background:linear-gradient(135deg,var(--accent),var(--pink));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;display:inline-block}}
.sub{{color:var(--dim);font-size:0.8em;margin-top:6px}}
.sub a{{color:var(--accent);text-decoration:none}}
.hero-stats{{display:flex;gap:26px;margin-top:18px;flex-wrap:wrap}}
.hs b{{display:block;font-size:1.25em;font-variant-numeric:tabular-nums}}
.hs span{{font-size:0.64em;text-transform:uppercase;letter-spacing:0.14em;color:var(--dim)}}
.filters{{position:sticky;top:0;z-index:20;background:rgba(10,10,15,0.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:10px 0}}
.f-inner{{max-width:880px;margin:0 auto;padding:0 18px;display:flex;flex-direction:column;gap:8px}}
.filter-more{{display:flex;flex-direction:column;gap:8px}}
.f-line{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.f-primary{{flex-wrap:nowrap}}
.filter-summary{{min-height:20px;display:flex;align-items:center;justify-content:space-between;gap:10px}}
#result-count{{color:var(--dim);font-size:0.68em;font-variant-numeric:tabular-nums}}
#filters-toggle{{display:none}}
#copy-link.copied{{border-color:var(--green);color:var(--green)}}
#q{{flex:1;min-width:160px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);padding:8px 13px;font-size:0.85em;outline:none}}
#q:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(232,160,64,0.12)}}
#venue{{background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);padding:8px 10px;font-size:0.8em;max-width:220px}}
.fc{{background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--dim);padding:5px 11px;font-size:0.72em;font-weight:600;cursor:pointer;line-height:1.5}}
.fc:hover{{border-color:var(--accent);color:var(--text)}}
.fc.on{{background:rgba(232,160,64,0.14);border-color:var(--accent);color:var(--accent)}}
.fc:focus-visible,.mini-action:focus-visible,.tix:focus-visible,.a-link:focus-visible,.sp-link:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.f-label{{font-size:0.6em;text-transform:uppercase;letter-spacing:0.14em;color:var(--dim);margin-right:2px;min-width:44px}}
#clear{{display:none;margin-left:auto}}
#clear.vis{{display:inline-block}}
h2,.eyebrow{{font-size:0.72em;text-transform:uppercase;letter-spacing:0.16em;color:var(--accent);opacity:0.9;margin:30px 0 10px}}
.mh-n{{opacity:0.55;font-variant-numeric:tabular-nums}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}}
.card{{position:relative;display:block;background:linear-gradient(160deg,#14141e,#101018);border:1px solid var(--border);border-radius:14px;padding:15px 17px;text-decoration:none;color:var(--text);transition:border-color .15s,transform .15s,box-shadow .15s}}
.card:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 6px 22px rgba(232,160,64,0.10)}}
.card-cover{{position:absolute;inset:0;border-radius:14px}}
.card .a-link,.card .sp-link,.card-actions{{position:relative;z-index:1}}
.card-top{{display:flex;justify-content:space-between;align-items:baseline}}
.card-date{{font-size:0.68em;letter-spacing:0.12em;color:var(--accent);font-weight:700}}
.card-type{{font-size:0.6em;letter-spacing:0.1em;text-transform:uppercase;color:var(--dim)}}
.card-artist{{font-weight:700;font-size:1.05em;margin:5px 0 2px}}
.card-venue{{color:var(--dim);font-size:0.78em}}
.badges{{margin-top:6px}}
.bdg{{display:inline-block;border-radius:6px;padding:1px 7px;font-size:0.62em;font-weight:600;letter-spacing:0.04em;margin:1px 4px 1px 0}}
.bdg-just{{background:rgba(96,232,160,0.16);color:var(--green);border:1px solid rgba(96,232,160,0.3)}}
.bdg-trib{{background:rgba(160,64,232,0.12);color:#b07ae0}}
.why{{color:var(--dim);font-size:0.7em;margin-top:6px;line-height:1.5}}
.card-actions{{display:flex;gap:6px;margin-top:10px}}
.row{{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:8px;transition:border-color .12s}}
.row:hover{{border-color:#2c2c40}}
.r-date{{display:flex;flex-direction:column;align-items:center;min-width:46px;color:var(--dim)}}
.r-dow{{font-size:0.6em;letter-spacing:0.1em}}
.r-day{{font-size:1.3em;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}}
.r-mon{{font-size:0.6em;letter-spacing:0.1em}}
.r-main{{flex:1;min-width:0}}
.r-artist{{font-weight:700;font-size:0.98em}}
.a-link{{color:var(--text);text-decoration:none}}
.a-link:hover{{color:var(--accent)}}
.sp-link{{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:#1DB954;color:#000;text-decoration:none;font-size:0.55em;font-weight:700;margin-left:7px;vertical-align:2px;transition:all .12s}}
.sp-link:hover{{transform:scale(1.12)}}
.r-type{{font-size:0.58em;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim);border:1px solid var(--border);border-radius:5px;padding:1px 6px;margin-left:8px;vertical-align:2px}}
.also{{color:var(--dim);font-weight:400;font-size:0.85em}}
.r-sub{{color:var(--dim);font-size:0.78em;margin-top:2px}}
.ev-title{{color:#9a9ab0}}
.dot{{margin:0 6px}}
.tix{{padding:7px 14px;border-radius:10px;font-size:0.74em;font-weight:600;border:1px solid var(--border);background:var(--card2);color:var(--text);text-decoration:none;white-space:nowrap}}
.tix:hover{{border-color:var(--accent);color:var(--accent)}}
.row-actions{{display:flex;gap:6px;align-items:center}}
.mini-action{{border:1px solid var(--border);background:var(--card2);color:var(--dim);border-radius:9px;padding:6px 9px;font-size:0.7em;font-weight:600;cursor:pointer;white-space:nowrap}}
.mini-action:hover{{border-color:var(--accent);color:var(--text)}}
.save-btn.saved{{border-color:var(--green);color:var(--green);background:rgba(96,232,160,0.08)}}
#none{{display:none;color:var(--dim);font-size:0.85em;padding:30px 0;text-align:center}}
.foot{{color:var(--dim);font-size:0.7em;margin-top:40px;line-height:1.7}}
@media(max-width:560px){{
  .filters{{padding:9px 0}}
  #filters-toggle{{display:inline-block}}
  .filter-more{{display:none}}
  .filters.open .filter-more{{display:flex}}
  #venue{{max-width:none;flex:1}}
  .row{{flex-wrap:wrap}}
  .row-actions{{margin-left:60px;width:calc(100% - 60px)}}
  .hero-stats{{gap:18px}}
  .card-actions{{margin-top:8px}}
}}
</style><link rel="stylesheet" href="music-home.css"></head><body>
<nav class="music-nav" aria-label="Music"><a class="music-brand" href="index.html">DJ Archive</a><a href="index.html">Discover</a><a href="index.html?view=records">Full archive</a><a href="gigs.html" aria-current="page">Gigs</a><a href="index.html?view=saved">Saved</a></nav>
<header class="hero"><div class="wrap">
<h1>Gig Radar</h1>
<div class="sub">{('Upcoming London shows, hand-filtered through <a href="index.html">the DJ Archive</a> — 17,000+ tracks curated by ear over 14 years. Only confirmed performers from the archive make this list.' if public else f'Confirmed performers from the archive · updated {upd} · <a href="gigs-share.html">shareable version</a>')}</div>
<div class="hero-stats">
<div class="hs"><b>{len(matches)}</b><span>shows</span></div>
<div class="hs"><b>{n_new}</b><span>new this week</span></div>
</div>
</div></header>
<div class="filters"><div class="f-inner">
<div class="f-line f-primary">
<label class="visually-hidden" for="q">Search gigs</label>
<input id="q" type="search" placeholder="Search artist, event, venue…" autocomplete="off">
<button class="fc" id="filters-toggle" type="button" aria-expanded="false" aria-controls="filter-more">Filters</button>
</div>
<div class="filter-summary"><span id="result-count" role="status" aria-live="polite">Showing {len(matches)} shows</span><span><button class="fc" id="copy-link" type="button">Copy link</button><button class="fc" id="clear" type="button">Clear</button></span></div>
<div class="f-line quick-when">
<button class="fc fc-range" data-range="weekend" type="button">This weekend</button>
<button class="fc fc-range" data-range="30" type="button">Next 30 days</button>
<button class="fc" id="fsaved" type="button">Saved</button>
</div>
<div class="filter-more" id="filter-more">
<div class="f-line"><span class="f-label">Venue</span><label class="visually-hidden" for="venue">Venue</label><select id="venue">{venue_opts}</select></div>
<div class="f-line"><span class="f-label">Type</span>
<button class="fc fc-t" data-t="gig" type="button">Live gigs</button>
<button class="fc fc-t" data-t="dj" type="button">DJ nights</button>
<button class="fc fc-t" data-t="day" type="button">Day parties</button>
<button class="fc" id="fnew" type="button">New this week</button>
</div>
<div class="f-line"><span class="f-label">Month</span>{month_chips}</div>
<div class="f-line"><span class="f-label">Crate</span>{crate_chips}</div>
</div>
</div></div>
<div class="wrap">
<div id="picks-w"><div class="eyebrow">Top picks</div>
<div class="grid">
{''.join(card(m) for m in picks)}
</div></div>
{sections}
<div id="none">Nothing matches those filters.</div>
<div class="foot">Matched from {n_events:,} London listings against {n_artists:,} archive artists · updated {upd}.<br>
{sources_note}<br>
Chosen by ear. Matched against confirmed performers.{('' if public else ' Refresh: <code>python3 gigs-fetch.py</code>')}</div>
</div>
<script>
(function(){{
var F={{q:'',v:'',t:null,mo:null,c:null,n:false,range:null,saved:false}};
var TODAY=new Date();TODAY.setHours(0,0,0,0);
var SAVED_KEY='gr_saved_gigs_v1';
var saved={{}};
try{{saved=JSON.parse(localStorage.getItem(SAVED_KEY)||'{{}}')}}catch(e){{saved={{}}}}
var _cut=iso(TODAY);
document.querySelectorAll('.row,.card').forEach(function(el){{if(el.dataset.d&&el.dataset.d<_cut)el.remove()}});
function on(sel,ev,fn){{document.querySelectorAll(sel).forEach(function(el){{el.addEventListener(ev,fn)}})}}
function toggle(btn,group,key,val){{
  var was=btn.classList.contains('on');
  document.querySelectorAll(group).forEach(function(b){{b.classList.remove('on')}});
  if(!was){{btn.classList.add('on');F[key]=val}}else{{F[key]=null}}
  apply();
}}
on('.fc-t','click',function(){{toggle(this,'.fc-t','t',this.dataset.t)}});
on('.fc-mo','click',function(){{toggle(this,'.fc-mo','mo',this.dataset.mo)}});
on('.fc-c','click',function(){{toggle(this,'.fc-c','c',this.dataset.c)}});
on('.fc-range','click',function(){{toggle(this,'.fc-range','range',this.dataset.range)}});
document.getElementById('fnew').addEventListener('click',function(){{
  this.classList.toggle('on');F.n=this.classList.contains('on');apply()}});
document.getElementById('fsaved').addEventListener('click',function(){{
  this.classList.toggle('on');F.saved=this.classList.contains('on');apply()}});
document.getElementById('q').addEventListener('input',function(){{F.q=this.value.toLowerCase().trim();apply()}});
document.getElementById('venue').addEventListener('change',function(){{F.v=this.value;apply()}});
document.getElementById('clear').addEventListener('click',function(){{
  F={{q:'',v:'',t:null,mo:null,c:null,n:false,range:null,saved:false}};
  document.getElementById('q').value='';document.getElementById('venue').value='';
  document.querySelectorAll('.fc.on').forEach(function(b){{b.classList.remove('on')}});
  apply()}});
document.getElementById('filters-toggle').addEventListener('click',function(){{
  var filters=document.querySelector('.filters');
  var open=filters.classList.toggle('open');
  this.setAttribute('aria-expanded',String(open));
}});
document.getElementById('copy-link').addEventListener('click',function(){{
  var btn=this,url=location.href;
  function done(){{btn.textContent='Copied';btn.classList.add('copied');setTimeout(function(){{btn.textContent='Copy link';btn.classList.remove('copied')}},1400)}}
  if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(url).then(done)}}
  else{{var ta=document.createElement('textarea');ta.value=url;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();done()}}
}});
function active(){{return F.q||F.v||F.t||F.mo||F.c||F.n||F.range||F.saved}}
function show(el,yes){{el.style.display=yes?'':'none'}}
function iso(d){{return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}}
function dateInRange(value,range){{
  if(!range)return true;
  var end=new Date(TODAY),start=new Date(TODAY),day=TODAY.getDay();
  if(range==='30'){{end.setDate(end.getDate()+30);return value>=iso(start)&&value<=iso(end)}}
  if(day>=1&&day<=5){{start.setDate(start.getDate()+((5-day+7)%7));end=new Date(start);end.setDate(end.getDate()+2)}}
  else if(day===6){{end.setDate(end.getDate()+1)}}
  return value>=iso(start)&&value<=iso(end);
}}
function syncUrl(){{
  var p=new URLSearchParams();
  ['q','v','t','mo','c','range'].forEach(function(k){{if(F[k])p.set(k,F[k])}});
  if(F.n)p.set('new','1');if(F.saved)p.set('saved','1');
  history.replaceState(null,'',location.pathname+(p.toString()?'?'+p.toString():'')+location.hash);
}}
function setPressed(){{
  document.querySelectorAll('.fc-t').forEach(function(b){{b.setAttribute('aria-pressed',String(F.t===b.dataset.t))}});
  document.querySelectorAll('.fc-mo').forEach(function(b){{b.setAttribute('aria-pressed',String(F.mo===b.dataset.mo))}});
  document.querySelectorAll('.fc-c').forEach(function(b){{b.setAttribute('aria-pressed',String(F.c===b.dataset.c))}});
  document.querySelectorAll('.fc-range').forEach(function(b){{b.setAttribute('aria-pressed',String(F.range===b.dataset.range))}});
  document.getElementById('fnew').setAttribute('aria-pressed',String(F.n));
  document.getElementById('fsaved').setAttribute('aria-pressed',String(F.saved));
}}
function apply(skipUrl){{
  var total=0,monthCounts={{}};
  document.querySelectorAll('.row').forEach(function(r){{
    var ok=(!F.q||r.dataset.s.indexOf(F.q)>-1)&&(!F.v||r.dataset.v===F.v)&&
           (!F.t||r.dataset.t===F.t)&&(!F.mo||r.dataset.mo===F.mo)&&
           (!F.c||r.dataset.c===F.c)&&(!F.n||r.dataset.n==='1')&&
           dateInRange(r.dataset.d,F.range)&&(!F.saved||saved[r.dataset.key]);
    show(r,ok);if(ok){{total++;monthCounts[r.dataset.mo]=(monthCounts[r.dataset.mo]||0)+1}}
  }});
  document.querySelectorAll('.mh').forEach(function(h){{
    var count=monthCounts[h.dataset.mo]||0;
    h.querySelector('.mh-n').textContent=count;
    show(h,count>0);
  }});
  show(document.getElementById('picks-w'),!active());
  show(document.getElementById('none'),total===0);
  document.getElementById('result-count').textContent='Showing '+total+' show'+(total===1?'':'s');
  document.getElementById('clear').classList.toggle('vis',!!active());
  var filterCount=[F.v,F.t,F.mo,F.c,F.n,F.range,F.saved].filter(Boolean).length;
  document.getElementById('filters-toggle').textContent='Filters'+(filterCount?' · '+filterCount:'');
  setPressed();refreshSaves();if(!skipUrl)syncUrl();
}}
function refreshSaves(){{
  document.querySelectorAll('.save-btn').forEach(function(btn){{
    var box=btn.closest('.row,.card'),on=!!saved[box.dataset.key];
    btn.classList.toggle('saved',on);btn.textContent=on?'★':'☆';
    btn.setAttribute('aria-pressed',String(on));btn.title=on?'Remove saved gig':'Save gig';
  }});
}}
on('.save-btn','click',function(e){{
  e.preventDefault();e.stopPropagation();var box=this.closest('.row,.card'),key=box.dataset.key;
  if(saved[key])delete saved[key];else saved[key]=1;
  try{{localStorage.setItem(SAVED_KEY,JSON.stringify(saved))}}catch(err){{}}
  if(F.saved)apply();else refreshSaves();
}});
function icsEscape(s){{return (s||'').replace(/\\\\/g,'\\\\\\\\').replace(/;/g,'\\\\;').replace(/,/g,'\\\\,').replace(/\\n/g,'\\\\n')}}
on('.cal-btn','click',function(e){{
  e.preventDefault();e.stopPropagation();var box=this.closest('.row,.card');
  var start=box.dataset.d.replace(/-/g,''),endDate=new Date(box.dataset.d+'T00:00:00');endDate.setDate(endDate.getDate()+1);
  var title=box.dataset.title===box.dataset.artist?box.dataset.artist:box.dataset.artist+' — '+box.dataset.title;
  var lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//DJ Archive//Gig Radar//EN','BEGIN:VEVENT',
    'UID:'+start+'-'+encodeURIComponent(box.dataset.key)+'@dj-archive','DTSTART;VALUE=DATE:'+start,
    'DTEND;VALUE=DATE:'+iso(endDate).replace(/-/g,''),'SUMMARY:'+icsEscape(title),
    'LOCATION:'+icsEscape(box.dataset.v),'DESCRIPTION:'+icsEscape('Tickets: '+box.dataset.url),
    'URL:'+box.dataset.url,'END:VEVENT','END:VCALENDAR'];
  var blob=new Blob([lines.join('\\r\\n')],{{type:'text/calendar;charset=utf-8'}}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=(box.dataset.artist+' '+box.dataset.d+'.ics').replace(/[^a-z0-9 ._-]/gi,'');document.body.appendChild(a);a.click();a.remove();setTimeout(function(){{URL.revokeObjectURL(url)}},500);
}});
var params=new URLSearchParams(location.search);
F.q=(params.get('q')||'').toLowerCase().trim();F.v=params.get('v')||'';F.t=params.get('t');
F.mo=params.get('mo');F.c=params.get('c');F.range=params.get('range');F.n=params.get('new')==='1';F.saved=params.get('saved')==='1';
document.getElementById('q').value=F.q;document.getElementById('venue').value=F.v;
document.querySelectorAll('.fc-t').forEach(function(b){{b.classList.toggle('on',F.t===b.dataset.t)}});
document.querySelectorAll('.fc-mo').forEach(function(b){{b.classList.toggle('on',F.mo===b.dataset.mo)}});
document.querySelectorAll('.fc-c').forEach(function(b){{b.classList.toggle('on',F.c===b.dataset.c)}});
document.querySelectorAll('.fc-range').forEach(function(b){{b.classList.toggle('on',F.range===b.dataset.range)}});
document.getElementById('fnew').classList.toggle('on',F.n);document.getElementById('fsaved').classList.toggle('on',F.saved);
apply(true);
}})();
</script>
</body></html>'''
    open(out, 'w', encoding='utf-8').write('\n'.join(line.rstrip() for line in html.split('\n')))


# ---------- main ----------

def performer_names(value):
    """JSON-LD performer, never Event.name or a page title."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [value['name']] if isinstance(value.get('name'), str) else []
    if isinstance(value, list):
        return [name for item in value for name in performer_names(item)]
    return []


def is_cancelled(event):
    return bool(re.search(r'\bcancelled\b|\bcanceled\b|\bpostponed\b', event.get('title', ''), re.I)
                or re.search(r'cancel|postpon', str(event.get('status', '')), re.I))


def hydrate_saved_matches(payload, artists):
    """Fail closed: legacy 'lineup' is reliable only for these structured feeds.
    Old co-artists lack individual provenance and must be re-fetched.
    """
    rebuilt = []
    for saved in payload.get('matches', []):
        norm = normalize(saved.get('artist', ''))
        explicit = saved.get('performers')
        trusted = (norm in {normalize(clean_name(n)) for n in explicit}
                   if isinstance(explicit, list) else
                   saved.get('how') == 'lineup' and saved.get('source') in {'RA', 'JazzCafe', 'Ticketmaster'})
        if (not trusted or is_cancelled(saved) or saved.get('date', '') < str(TODAY)
                or norm not in artists or norm in DEAD_ARTISTS or norm in EXCLUDE_ARTISTS
                or normalize(saved.get('venue', '')) in OUTSIDE_LONDON_VENUES
                or is_tribute(saved.get('title', ''), 'lineup')):
            continue
        verified = {normalize(clean_name(n)) for n in explicit or []}
        co = [artists[normalize(name)] for name in saved.get('co', [])
              if normalize(name) in artists and normalize(name) in verified
              and normalize(name) not in DEAD_ARTISTS | EXCLUDE_ARTISTS]
        rebuilt.append({**saved, 'how': 'lineup', 'artist': artists[norm], 'co': co,
                        'performers': explicit or [saved['artist']],
                        'all_names': explicit or [saved['artist']]})
    return rebuilt


def save_matches(matches, generated, n_events):
    payload = {'generated': generated, 'events': n_events, 'matching_rule': 'explicit-performers-v1',
               'matches': [{**{k: m[k] for k in ('date', 'title', 'venue', 'url', 'source',
                                              'how', 'score', 'etype', 'first_seen')},
                            'performers': m['performers'], 'artist': m['artist']['name'],
                            'co': [r['name'] for r in m['co']]} for m in matches]}
    Path(HERE, 'gigs-data.json').write_text(json.dumps(payload, indent=1))


def existing_sources_note():
    return ('Sources: RA, KOKO, EartH, Jazz Cafe, Roundhouse, Ally Pally, '
            'Barbican, AMG/Live Nation, Apollo, Spiritland, Blue Note London, '
            'Ronnie Scott\'s, '
            'The O2, OVO Arena, Wembley Stadium, Open Air Theatre. Coverage requires explicit performer data; title-only listings are omitted. Tribute / '
            'covers / &ldquo;plays the music of&rdquo; nights are filtered out. '
            'Gaps: Union Chapel, Tottenham &amp; London Stadium (no listings feeds); '
            'Title-only venue feeds are excluded. Space Talk, One Eighty One &amp; Brilliant Corners programme on '
            'Instagram only (their RA-listed nights are covered). SJQ via RA.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=365)
    ap.add_argument('--out', default=f'{HERE}/gigs.html')
    ap.add_argument('--render-existing', action='store_true',
                    help='rebuild HTML from gigs-data.json without fetching listings')
    args = ap.parse_args()

    print('Loading archive artists...')
    artists = load_artists()
    print(f'  {len(artists)} unique artists')

    if args.render_existing:
        payload = json.load(open(f'{HERE}/gigs-data.json'))
        matches = hydrate_saved_matches(payload, artists)
        note = existing_sources_note()
        save_matches(matches, payload['generated'], payload.get('events', 0))
        render(matches, payload.get('events', 0), len(artists), note, args.out, generated=payload['generated'])
        share_out = args.out.replace('gigs.html', 'gigs-share.html')
        render(matches, payload.get('events', 0), len(artists), note, share_out, public=True, generated=payload['generated'])
        print(f'Wrote {args.out} + {share_out} from existing data')
        return

    # previous run's first_seen map
    prev_seen, prev_sources, bootstrap = {}, set(), True
    try:
        prev = json.load(open(f'{HERE}/gigs-data.json'))
        pm = prev.get('matches', [])
        prev_sources = {m.get('source') for m in pm}
        # older data files have no first_seen — everything is "old", nothing is
        # "just announced" until the next run establishes a baseline
        bootstrap = not any('first_seen' in m for m in pm)
        for m in pm:
            prev_seen[(m['artist'], m['date'])] = m.get('first_seen', '2000-01-01')
    except Exception:
        pass

    events, src_counts = [], {}
    for label, fn in [('RA', lambda: fetch_ra(args.days)), ('KOKO', fetch_koko),
                      ('EartH', fetch_earth), ('Jazz Cafe', fetch_jazzcafe),
                      ('Roundhouse', fetch_roundhouse), ('Ally Pally', fetch_allypally),
                      ('Barbican', fetch_barbican),
                      ('AMG/Live Nation', fetch_amg), ('Apollo', fetch_apollo),
                      ('Spiritland', fetch_spiritland),
                      ('Blue Note', fetch_bluenote),
                      ("Ronnie Scott's", fetch_ronnies), ('The O2', fetch_theo2),
                      ('OVO Arena', fetch_ovo), ('Wembley Stadium', fetch_wembley),
                      ('Open Air Theatre', fetch_openair),
                      ('Ticketmaster', lambda: fetch_ticketmaster(args.days))]:
        try:
            batch = fn()
            print(f'  {label}: {len(batch)} events')
            src_counts[label] = len(batch)
            events.extend(batch)
        except Exception as e:
            print(f'  {label} FAILED: {e}', file=sys.stderr)
            src_counts[label] = 0

    # hand-added shows (e.g. Instagram-only listening bars, swept manually):
    # gigs-extra.json = [{"date","title","venue","url","names":[...]}]
    try:
        extra = json.load(open(f'{HERE}/gigs-extra.json'))
        for e in extra:
            e.setdefault('names', [])
            e['lineup_verified'] = bool(e.get('performers_verified'))
            e.setdefault('start', '')
            e.setdefault('source', 'Manual')
            e.setdefault('hint', 'dj')
        events.extend(extra)
        print(f'  Manual (gigs-extra.json): {len(extra)} events')
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'  gigs-extra.json skipped: {e}', file=sys.stderr)

    horizon = str(TODAY + timedelta(days=args.days))
    events = [e for e in events if e['date'] and str(TODAY) <= e['date'] <= horizon]
    outside = [e for e in events if normalize(e.get('venue', '')) in OUTSIDE_LONDON_VENUES]
    events = [e for e in events if normalize(e.get('venue', '')) not in OUTSIDE_LONDON_VENUES]
    if outside:
        print(f'  dropped {len(outside)} non-London listings')
    if len(events) < 100:
        sys.exit(f'Only {len(events)} events fetched — sources look down; '
                 'keeping the existing gigs.html.')

    per_event = [(ev, match_event(ev, artists)) for ev in events]

    matches, seen, n_trib = [], set(), 0
    for ev, hits in per_event:
        for norm, how in hits.items():
            # tribute / covers / "vs" nights: the artist isn't actually playing — drop
            # (same for dead artists: any listing with their name is a tribute)
            if is_tribute(ev['title'], how) or norm in DEAD_ARTISTS or norm in EXCLUDE_ARTISTS:
                n_trib += 1
                continue
            key = (norm, ev['date'], ev['url'])
            if key in seen:
                continue
            seen.add(key)
            r = artists[norm]
            matches.append({'date': ev['date'], 'title': ev['title'], 'venue': ev['venue'],
                            'url': ev['url'], 'source': ev['source'], 'how': how,
                            'artist': r, 'all_names': ev['names'], 'performers': ev['names'],
                            'etype': classify(ev, ev['title']),
                            'first_seen': ('2000-01-01' if bootstrap or ev['source'] not in prev_sources
                                           else prev_seen.get((r['name'], ev['date']), str(TODAY))),
                            'score': artist_score(r)})
    print(f'  dropped {n_trib} tribute/covers-night matches')

    grouped = {}
    for m in matches:
        gk = (m['date'], normalize(m['venue']), normalize(m['title']))
        g = grouped.setdefault(gk, m | {'co': []})
        g['performers'] = list(dict.fromkeys(g['performers'] + m['performers']))
        if m is not g and m['artist'] is not g['artist']:
            if m['score'] > g['score']:
                g['co'].append(g['artist'])
                g.update({k: m[k] for k in ('artist', 'score', 'how', 'first_seen')})
            else:
                g['co'].append(m['artist'])
    matches = list(grouped.values())
    if not matches:
        sys.exit('No verified performers found — retaining the existing gig files.')
    for m in matches:
        m['score'] += 5 * len(m['co'])

    # Ronnie's URLs are slug-guesses — validate the few matched ones via the
    # proxy and fall back to the listings page when the guess 404s
    for m in matches:
        if m['source'] != 'RonnieScotts' or m['url'].endswith('/find-a-show'):
            continue
        try:
            head = http_get('https://r.jina.ai/' + m['url'], timeout=60)[:400]
            if 'Page not found' in head:
                m['url'] = 'https://www.ronniescotts.co.uk/find-a-show'
        except Exception:
            pass
        time.sleep(1.5)
    print(f'{len(events)} events in window -> {len(matches)} matched shows')

    save_matches(matches, str(TODAY), len(events))

    got = [k for k, v in src_counts.items() if v]
    note = ('Sources: ' + ', '.join(got) +
            '. Only explicitly listed performers qualify. Title mentions and cancelled shows are excluded. '
            'Gaps: Union Chapel, Tottenham &amp; London Stadium (no listings feeds); '
            'Title-only venue feeds are excluded. Space Talk, One Eighty One &amp; Brilliant Corners programme on '
            'Instagram only (their RA-listed nights are covered). SJQ via RA.')
    render(matches, len(events), len(artists), note, args.out)
    share_out = args.out.replace('gigs.html', 'gigs-share.html')
    render(matches, len(events), len(artists), note, share_out, public=True)
    print(f'Wrote {args.out} + {share_out}')


if __name__ == '__main__':
    main()
