#!/usr/bin/env python3
"""Gig Radar v2 — upcoming London gigs matched to the archive.

Sources:
  - Resident Advisor GraphQL (all-London backbone: clubs + live + festivals)
  - KOKO, EartH, Jazz Cafe, Roundhouse, Alexandra Palace, Barbican,
    Eventim Apollo, Spiritland King's Cross, The O2 Arena (site scrapes)
  - AMG/Live Nation internal API (O2 Academy Brixton, Shepherd's Bush Empire,
    Forum Kentish Town, Islington Academies)
  - Ronnie Scott's via r.jina.ai reader proxy (their site is Cloudflare-walled
    for plain fetches; the proxy renders it)
  - Ticketmaster Discovery API IF env TM_API_KEY is set (optional extra)
Gaps (checked 2026-07-20): Union Chapel (JS-only); Space Talk & One Eighty One
programme on Instagram only.

Matching: structured lineup names exact + title phrase-scan (strict — see
match_event). Weighted on plays + recency + newly-added artists.
Tribute/covers/"vs" nights are dropped entirely (is_tribute).
first_seen per show persists across runs via gigs-data.json -> "Just announced".

Usage: python3 gigs-fetch.py [--days 365] [--out gigs.html]
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
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

TITLE_STOP = {'jungle', 'underground', 'electronic', 'liquid', 'forest', 'pleasure',
              'sundown', 'garage', 'house', 'techno', 'disco', 'funk', 'soul', 'jazz',
              'gospel', 'orchestra', 'ensemble', 'collective', 'social', 'summer',
              'winter', 'sunset', 'sunrise', 'midnight', 'warehouse', 'paradise',
              'daughter', 'mother', 'brother', 'sister', 'lovers', 'dreams', 'magic',
              'joseph', 'simone', 'marcel', 'george', 'marie', 'james', 'thomas',
              'charlie', 'jamie', 'oscar', 'leon', 'otis', 'ruby', 'pearl',
              'outside', 'return', 'prince', 'inside', 'weekend', 'holiday', 'disney',
              'salute', 'calendar'}

# hard signals always mean covers/tribute; soft ones ("celebrating", "vs") only
# count when the artist was matched from the free-text title — a structured
# lineup entry means the act is genuinely on the bill (Band of Horses
# "Celebrating 20 Years" is really them; "Fred Again vs Daft Punk" is not Daft Punk)
TRIBUTE_HARD_RE = re.compile(
    r'tribute|the music of|the songs of|the best of|songbook|plays the|'
    r're[: ]?imagined|orchestral|symphonic|candlelight|sounds of|queen of soul|'
    r'an evening of', re.I)
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
    'Minnie Riperton', 'Phyllis Hyman', 'Grover Washington Jr.')}



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
    if r['p1'] >= 6:
        b.append(('hot', 'On repeat'))
    if r['plays'] >= 50:
        b.append(('heavy', 'Heavy rotation'))
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
                           'start': start, 'source': 'RA', 'hint': ''})
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
        names = [re.sub(r'<[^>]+>', '', n).strip()
                 for n in re.findall(r'<li>(.*?)</li>', block, re.S)]
        events.append({'date': str(d), 'title': title or (names[0] if names else ''),
                       'venue': 'The Jazz Cafe', 'url': um.group(1),
                       'names': [n for n in names if n], 'start': '',
                       'source': 'JazzCafe', 'hint': hint})
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
                            'names': [nm.strip()], 'start': (it.get('startDate') or '')[11:16],
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
    """Ronnie Scott's find-a-show, rendered through the r.jina.ai reader proxy
    (their site Cloudflare-blocks plain fetches). Markdown pattern per show:
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
                if (title, str(pend_date)) not in seen:
                    seen.add((title, str(pend_date)))
                    events.append({'date': str(pend_date), 'title': title,
                                   'venue': "Ronnie Scott's",
                                   'url': 'https://www.ronniescotts.co.uk/find-a-show',
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
            names = [a.get('name', '') for a in x.get('lineup') or []] or [x.get('name', '')]
            events.append({'date': (x.get('eventDate') or '')[:10], 'title': x.get('name', ''),
                           'venue': vname, 'url': url,
                           'names': [n for n in names if n],
                           'start': x.get('doorTime') or '', 'source': 'AMG', 'hint': 'gig'})
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
                           'source': 'Ticketmaster', 'hint': 'gig'})
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


def match_event(ev, artists):
    hits = {}
    for raw in ev['names']:
        norm = normalize(clean_name(raw))
        if not norm or norm in NAME_STOP or norm not in artists:
            continue
        r = artists[norm]
        if ' ' not in norm and r['tracks'] < 2 and r['plays'] < 10:
            continue
        hits[norm] = 'lineup'
    tnorm = ' ' + normalize(ev['title']) + ' '
    for norm, r in artists.items():
        if norm in hits or norm in NAME_STOP:
            continue
        single = ' ' not in norm
        if single and (len(norm) < 6 or norm in TITLE_STOP):
            continue
        if r['tracks'] < 2 and r['plays'] < 3:
            continue
        needle = f' the {norm} ' if (r['the'] and single) else f' {norm} '
        if needle in tnorm:
            if single and _part_of_longer_name(r['name'], ev['title']):
                continue
            hits[norm] = 'title'
    return hits


_NEXT_OK = {'Live', 'Presents', 'DJ', 'Set', 'Band', 'All', 'At', 'In', 'On', 'And',
            'Takeover', 'Tour', 'London', 'Tickets', 'Plus', 'B2B', 'X'}
_PREV_OK = {'The', 'DJ', 'MC', 'With', 'Ft', 'Feat', 'And', 'Featuring', 'By'}


def _part_of_longer_name(name, title):
    """'Beirut' inside 'Beirut Groove Collective' is a different act: a single-word
    artist flanked by another capitalised word is part of a longer name."""
    m = re.search(r'(?:^|[^A-Za-z])(' + re.escape(name) + r')(?=$|[^A-Za-z])', title, re.I)
    if not m:
        return False
    after = re.match(r'\s+([A-Z][a-zA-Z&\']+)', title[m.end(1):])
    if after and after.group(1) not in _NEXT_OK:
        return True
    before = re.search(r'([A-Z][a-zA-Z&\']+)\s+$', title[:m.start(1)])
    if before and before.group(1) not in _PREV_OK:
        return True
    return False


def drop_generic_title_matches(per_event_hits):
    counts = defaultdict(set)
    for ev, hits in per_event_hits:
        tnorm = normalize(ev['title'])
        for norm, how in hits.items():
            if how == 'title' and tnorm != norm and not tnorm.startswith(norm + ' '):
                counts[norm].add(tnorm)
    generic = {n for n, evs in counts.items() if len(evs) >= 3}
    if generic:
        print(f"  dropped generic title-words: {sorted(generic)}")
    for _, hits in per_event_hits:
        for n in list(hits):
            if hits[n] == 'title' and n in generic:
                del hits[n]


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


def render(matches, n_events, n_artists, sources_note, out, public=False):
    matches = sorted(matches, key=lambda m: (m['date'], -m['score']))
    fresh_cut = str(TODAY - timedelta(days=10))
    picks = sorted(matches, key=lambda m: -m['score'])[:12]
    upd = TODAY.strftime('%-d %b %Y')
    venues = sorted({m['venue'] for m in matches if m['venue']}, key=str.lower)
    crates = sorted({m['artist']['crate'] for m in matches if m['artist']['crate']},
                    key=lambda c: -sum(1 for m in matches if m['artist']['crate'] == c))
    months = sorted({m['date'][:7] for m in matches})
    n_new = sum(1 for m in matches if m['first_seen'] >= fresh_cut)

    def why(m):
        if public:
            return ''
        r = m['artist']
        bits = [f"{r['tracks']} track{'s' if r['tracks'] != 1 else ''}"]
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
            h = '<span class="bdg bdg-just">Just announced</span>' + h
        return h

    def attrs(m):
        text = f"{m['artist']['name']} {m['title']} {m['venue']}".lower()
        return (f'data-v="{esc(m["venue"])}" data-mo="{m["date"][:7]}" '
                f'data-c="{esc(m["artist"]["crate"])}" data-t="{m["etype"]}" '
                f'data-n="{1 if m["first_seen"] >= fresh_cut else 0}" '
                f'data-s="{esc(text)}"')

    def card(m):
        d = date.fromisoformat(m['date'])
        return f'''<a class="card" {attrs(m)} href="{esc(m['url'])}" target="_blank" rel="noopener">
  <div class="card-top"><span class="card-date">{d.strftime('%a %-d %b').upper()}</span><span class="card-type">{TYPE_LABEL[m['etype']]}</span></div>
  <div class="card-artist">{esc(m['artist']['name'])}</div>
  <div class="card-venue">{esc(m['venue'])}</div>
  <div class="badges">{badge_html(m)}</div>
  {f'<div class="why">{why(m)}</div>' if why(m) else ''}
</a>'''

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
    <div class="r-artist">{esc(m['artist']['name'])}<span class="r-type">{TYPE_LABEL[m['etype']]}</span>{co} {badge_html(m)}</div>
    <div class="r-sub">{title}{('<span class="dot">·</span>' if title else '')}<span class="r-venue">{esc(m['venue'])}</span></div>
    {f'<div class="why">{why(m)}</div>' if why(m) else ''}
  </div>
  <a class="tix" href="{esc(m['url'])}" target="_blank" rel="noopener">Tickets</a>
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
        f'<button class="fc fc-mo" data-mo="{ym}">{date.fromisoformat(ym + "-01").strftime("%b")}'
        f'{" ’" + ym[2:4] if ym[:4] != str(TODAY.year) else ""}</button>'
        for ym in months)
    crate_chips = ''.join(f'<button class="fc fc-c" data-c="{esc(c)}">{esc(c)}</button>' for c in crates)
    venue_opts = '<option value="">All venues</option>' + ''.join(
        f'<option value="{esc(v)}">{esc(v)}</option>' for v in venues)

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gig Radar — DJ Archive</title>
<style>
:root{{--bg:#0a0a0f;--card:#12121a;--card2:#181824;--border:#1e1e2e;--text:#e0e0e8;--dim:#6a6a80;--accent:#e8a040;--pink:#ff69b4;--green:#60e8a0}}
*{{box-sizing:border-box;margin:0;padding:0}}
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
.f-line{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
#q{{flex:1;min-width:160px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);padding:8px 13px;font-size:0.85em;outline:none}}
#q:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(232,160,64,0.12)}}
#venue{{background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);padding:8px 10px;font-size:0.8em;max-width:220px}}
.fc{{background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--dim);padding:5px 11px;font-size:0.72em;font-weight:600;cursor:pointer;line-height:1.5}}
.fc:hover{{border-color:var(--accent);color:var(--text)}}
.fc.on{{background:rgba(232,160,64,0.14);border-color:var(--accent);color:var(--accent)}}
.f-label{{font-size:0.6em;text-transform:uppercase;letter-spacing:0.14em;color:var(--dim);margin-right:2px;min-width:44px}}
#clear{{display:none;margin-left:auto}}
#clear.vis{{display:inline-block}}
h2,.eyebrow{{font-size:0.72em;text-transform:uppercase;letter-spacing:0.16em;color:var(--accent);opacity:0.9;margin:30px 0 10px}}
.mh-n{{opacity:0.55;font-variant-numeric:tabular-nums}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}}
.card{{display:block;background:linear-gradient(160deg,#14141e,#101018);border:1px solid var(--border);border-radius:14px;padding:15px 17px;text-decoration:none;color:var(--text);transition:border-color .15s,transform .15s,box-shadow .15s}}
.card:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 6px 22px rgba(232,160,64,0.10)}}
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
.row{{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:8px;transition:border-color .12s}}
.row:hover{{border-color:#2c2c40}}
.r-date{{display:flex;flex-direction:column;align-items:center;min-width:46px;color:var(--dim)}}
.r-dow{{font-size:0.6em;letter-spacing:0.1em}}
.r-day{{font-size:1.3em;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}}
.r-mon{{font-size:0.6em;letter-spacing:0.1em}}
.r-main{{flex:1;min-width:0}}
.r-artist{{font-weight:700;font-size:0.98em}}
.r-type{{font-size:0.58em;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim);border:1px solid var(--border);border-radius:5px;padding:1px 6px;margin-left:8px;vertical-align:2px}}
.also{{color:var(--dim);font-weight:400;font-size:0.85em}}
.r-sub{{color:var(--dim);font-size:0.78em;margin-top:2px}}
.ev-title{{color:#9a9ab0}}
.dot{{margin:0 6px}}
.tix{{padding:7px 14px;border-radius:10px;font-size:0.74em;font-weight:600;border:1px solid var(--border);background:var(--card2);color:var(--text);text-decoration:none;white-space:nowrap}}
.tix:hover{{border-color:var(--accent);color:var(--accent)}}
#none{{display:none;color:var(--dim);font-size:0.85em;padding:30px 0;text-align:center}}
.foot{{color:var(--dim);font-size:0.7em;margin-top:40px;line-height:1.7}}
@media(max-width:560px){{.row{{flex-wrap:wrap}}.tix{{margin-left:60px}}.hero-stats{{gap:18px}}}}
</style></head><body>
<header class="hero"><div class="wrap">
<h1>Gig Radar</h1>
<div class="sub">{('Upcoming London shows, hand-filtered through <a href="index.html">the DJ Archive</a> — 17,000+ tracks curated by ear over 14 years. Only artists in the archive make this list. No algorithm.' if public else f'London listings matched to the archive · updated {upd} · <a href="index.html">← back to the archive</a> · <a href="gigs-share.html">shareable version</a>')}</div>
<div class="hero-stats">
<div class="hs"><b>{len(matches)}</b><span>shows</span></div>
<div class="hs"><b>{len({m['artist']['name'] for m in matches})}</b><span>artists</span></div>
<div class="hs"><b>{len(venues)}</b><span>venues</span></div>
<div class="hs"><b>{n_new}</b><span>just announced</span></div>
</div>
</div></header>
<div class="filters"><div class="f-inner">
<div class="f-line">
<input id="q" type="search" placeholder="Search artist, event, venue…" autocomplete="off">
<select id="venue">{venue_opts}</select>
<button class="fc" id="clear">✕ Clear</button>
</div>
<div class="f-line"><span class="f-label">Type</span>
<button class="fc fc-t" data-t="gig">Live gigs</button>
<button class="fc fc-t" data-t="dj">DJ nights</button>
<button class="fc fc-t" data-t="day">Day parties</button>
<button class="fc" id="fnew">Just announced</button>
</div>
<div class="f-line"><span class="f-label">Month</span>{month_chips}</div>
<div class="f-line"><span class="f-label">Crate</span>{crate_chips}</div>
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
One DJ&rsquo;s ears, no algorithm.{('' if public else ' Refresh: <code>python3 gigs-fetch.py</code>')}</div>
</div>
<script>
(function(){{
var F={{q:'',v:'',t:null,mo:null,c:null,n:false}};
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
document.getElementById('fnew').addEventListener('click',function(){{
  this.classList.toggle('on');F.n=this.classList.contains('on');apply()}});
document.getElementById('q').addEventListener('input',function(){{F.q=this.value.toLowerCase().trim();apply()}});
document.getElementById('venue').addEventListener('change',function(){{F.v=this.value;apply()}});
document.getElementById('clear').addEventListener('click',function(){{
  F={{q:'',v:'',t:null,mo:null,c:null,n:false}};
  document.getElementById('q').value='';document.getElementById('venue').value='';
  document.querySelectorAll('.fc.on').forEach(function(b){{b.classList.remove('on')}});
  apply()}});
function active(){{return F.q||F.v||F.t||F.mo||F.c||F.n}}
function show(el,yes){{el.style.display=yes?'':'none'}}
function apply(){{
  var any=false;
  document.querySelectorAll('.row').forEach(function(r){{
    var ok=(!F.q||r.dataset.s.indexOf(F.q)>-1)&&(!F.v||r.dataset.v===F.v)&&
           (!F.t||r.dataset.t===F.t)&&(!F.mo||r.dataset.mo===F.mo)&&
           (!F.c||r.dataset.c===F.c)&&(!F.n||r.dataset.n==='1');
    show(r,ok);if(ok)any=true;
  }});
  document.querySelectorAll('.mh').forEach(function(h){{
    var vis=false,el=h.nextElementSibling;
    while(el&&el.classList.contains('row')){{if(el.style.display!=='none')vis=true;el=el.nextElementSibling}}
    show(h,vis);
  }});
  show(document.getElementById('picks-w'),!active());
  show(document.getElementById('none'),!any);
  document.getElementById('clear').classList.toggle('vis',!!active());
}}
}})();
</script>
</body></html>'''
    open(out, 'w', encoding='utf-8').write(html)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=365)
    ap.add_argument('--out', default=f'{HERE}/gigs.html')
    args = ap.parse_args()

    print('Loading archive artists...')
    artists = load_artists()
    print(f'  {len(artists)} unique artists')

    # previous run's first_seen map
    prev_seen, bootstrap = {}, True
    try:
        prev = json.load(open(f'{HERE}/gigs-data.json'))
        pm = prev.get('matches', [])
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

    horizon = str(TODAY + timedelta(days=args.days))
    events = [e for e in events if e['date'] and str(TODAY) <= e['date'] <= horizon]
    if len(events) < 100:
        sys.exit(f'Only {len(events)} events fetched — sources look down; '
                 'keeping the existing gigs.html.')

    per_event = [(ev, match_event(ev, artists)) for ev in events]
    drop_generic_title_matches(per_event)

    matches, seen, n_trib = [], set(), 0
    for ev, hits in per_event:
        for norm, how in hits.items():
            # tribute / covers / "vs" nights: the artist isn't actually playing — drop
            # (same for dead artists: any listing with their name is a tribute)
            if is_tribute(ev['title'], how) or norm in DEAD_ARTISTS:
                n_trib += 1
                continue
            key = (norm, ev['date'])
            if key in seen:
                continue
            seen.add(key)
            r = artists[norm]
            matches.append({'date': ev['date'], 'title': ev['title'], 'venue': ev['venue'],
                            'url': ev['url'], 'source': ev['source'], 'how': how,
                            'artist': r, 'all_names': ev['names'],
                            'etype': classify(ev, ev['title']),
                            'first_seen': ('2000-01-01' if bootstrap else
                                           prev_seen.get((r['name'], ev['date']), str(TODAY))),
                            'score': artist_score(r)})
    print(f'  dropped {n_trib} tribute/covers-night matches')

    grouped = {}
    for m in matches:
        gk = (m['date'], normalize(m['venue']), normalize(m['title']))
        g = grouped.setdefault(gk, m | {'co': []})
        if m is not g and m['artist'] is not g['artist']:
            if m['score'] > g['score']:
                g['co'].append(g['artist'])
                g.update({k: m[k] for k in ('artist', 'score', 'how', 'first_seen')})
            else:
                g['co'].append(m['artist'])
    matches = list(grouped.values())
    for m in matches:
        m['score'] += 5 * len(m['co'])
    print(f'{len(events)} events in window -> {len(matches)} matched shows')

    json.dump({'generated': str(TODAY), 'events': len(events),
               'matches': [{**{k: m[k] for k in ('date', 'title', 'venue', 'url', 'source',
                                                 'how', 'score', 'etype', 'first_seen')},
                            'artist': m['artist']['name'],
                            'co': [r['name'] for r in m['co']]} for m in matches]},
              open(f'{HERE}/gigs-data.json', 'w'), indent=1)

    got = [k for k, v in src_counts.items() if v]
    note = ('Sources: ' + ', '.join(got) +
            '. Tribute / covers / &ldquo;plays the music of&rdquo; nights are filtered out. '
            'Gaps: Union Chapel, Tottenham &amp; London Stadium (no listings feeds); '
            'Space Talk &amp; One Eighty One programme on Instagram only.')
    render(matches, len(events), len(artists), note, args.out)
    share_out = args.out.replace('gigs.html', 'gigs-share.html')
    render(matches, len(events), len(artists), note, share_out, public=True)
    print(f'Wrote {args.out} + {share_out}')


if __name__ == '__main__':
    main()
