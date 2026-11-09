#!/usr/bin/env python3
"""Gig Radar v2 — upcoming London gigs matched to the archive.

Sources:
  - Resident Advisor GraphQL (all-London backbone: clubs + live + festivals)
  - KOKO, EartH, Jazz Cafe, Roundhouse, Alexandra Palace, Barbican,
    Eventim Apollo, Spiritland King's Cross, The O2 Arena (site scrapes)
  - AMG/Live Nation internal API (O2 Academy Brixton, Shepherd's Bush Empire,
    Forum Kentish Town, Islington Academies)
  - Ronnie Scott's official line-ups/dates, with an attributed public Songkick backup
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
from html import unescape
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from collections import defaultdict

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HERE = str(Path(__file__).resolve().parent)
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


def http_get(url, referer=None, data=None, timeout=30, extra_headers=None):
    headers = {'User-Agent': UA, **(extra_headers or {})}
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
    """Every EartH URL ends in its DICE event code; DICE's MusicEvent JSON-LD
    carries the bill (and the real title and year). The slug never names anyone."""
    html = http_get('https://earthackney.co.uk/events/')
    listings, seen = [], set()
    for m in re.finditer(r'href="(https://earthackney\.co\.uk/events/([a-z0-9-]+)-(\d{1,2})(?:st|nd|rd|th)-'
                         r'([a-z]{3,4})-earth-london-tickets-([a-z0-9]+)/?)"', html):
        url, slug, day, mon, code = m.groups()
        if url in seen:
            continue
        seen.add(url)
        d = infer_year(int(day), MONTHS.get(mon[:3].lower(), 0) or 1)
        if not d:
            continue
        title = slug.replace('-', ' ').title()
        listings.append(({'date': str(d), 'title': title, 'venue': 'EartH',
                          'url': url, 'names': [], 'start': '',
                          'source': 'EartH', 'hint': 'gig'}, code))

    def one(item):
        ev, code = item
        return dice_verified(ev, fetch_dice('https://dice.fm/event/' + code, bundle=False),
                             'earth', dice_title=True)

    with ThreadPoolExecutor(8) as ex:
        return [ev for batch in ex.map(one, listings) for ev in batch]


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


def dice_links(html):
    """DICE ticket links on a venue's event page, not its DICE venue page."""
    return list(dict.fromkeys(re.findall(r'href="(https://link\.dice\.fm/(?!venue/)[^"]+)"', html)))


def dice_shows(html):
    """DICE MusicEvent JSON-LD: performers come from `performer` only."""
    shows = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            it = json.loads(block)
        except ValueError:
            continue
        if isinstance(it, dict) and 'Event' in str(it.get('@type', '')) and it.get('startDate'):
            shows.append({'date': it['startDate'][:10], 'start': it['startDate'][11:16],
                          'title': (it.get('name') or '').strip(),
                          'names': performer_names(it.get('performer')),
                          'status': it.get('eventStatus', ''),
                          'venue': (it.get('location') or {}).get('name', '')})
    return shows


def fetch_dice(url, bundle=True):
    """Multi-night runs link to a DICE bundle page whose nights are separate
    /event/ pages — follow those one level only."""
    try:
        h = http_get(url)
    except Exception:
        return []
    shows = dice_shows(h)
    if shows or not bundle:
        return shows
    nights = sorted(set(re.findall(r'href="(?:https://dice\.fm)?(/event/[a-z0-9-]+)"', h)))
    return [s for n in nights[:8] for s in fetch_dice('https://dice.fm' + n, bundle=False)]


def dice_verified(ev, shows, venue, dice_title=False):
    """A verified copy of the listing per named DICE bill at `venue` (a
    normalize()d prefix); otherwise the listing itself, unverified."""
    keys = ('date', 'start', 'names', 'status') + (('title',) if dice_title else ())
    shows = [s for s in shows if s['names'] and re.match(re.escape(venue) + r'\b', normalize(s['venue']))]
    return [ev | {k: s[k] for k in keys if s[k]} | {'lineup_verified': True} for s in shows] or [ev]


def fetch_allypally():
    """Ally Pally's own pages name no performers (their JSON-LD Event has no
    `performer`), but music nights link to DICE, whose MusicEvent JSON-LD lists
    the bill. Listings without that stay unverified and never match."""
    html = http_get('https://www.alexandrapalace.com/whats-on/')
    listings, seen = [], set()
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
        listings.append({'date': str(d), 'title': html_text(title), 'venue': 'Alexandra Palace',
                         'url': url, 'names': [], 'start': '',
                         'source': 'AllyPally', 'hint': 'gig'})

    def one(ev):
        try:
            page = http_get(ev['url'])
        except Exception:
            return [ev]
        return dice_verified(ev, [s for link in dice_links(page) for s in fetch_dice(link)],
                             'alexandra palace')

    events = []
    with ThreadPoolExecutor(8) as ex:
        for batch in ex.map(one, listings):
            events.extend(batch)
    return events


def barbican_performers(html):
    """Names in the page's "Performers" lists only — never Programme (composers),
    Creative Team or Cast. An untitled list continues the one before it; film
    credits put the role first ("Performed by" / London Symphony Orchestra)."""
    names, heading = [], ''
    for title, body in re.findall(r'<div class="related-people">\s*<h3 class="related-people__title">'
                                  r'(.*?)</h3>(.*?)</ul>', html, re.S):
        heading = html_text(title) or heading
        if heading.lower() != 'performers':
            continue
        rows = [(html_text(label), html_text(value)) for label, value in re.findall(
            r'label-value-list__label">(.*?)</span>.*?label-value-list__value">(.*?)</span>', body, re.S)]
        if any(label.lower().endswith(' by') for label, _ in rows):
            names += [value for label, value in rows if 'perform' in label.lower() and value]
        else:
            names += [label for label, _ in rows if label]
    return list(dict.fromkeys(names))


def barbican_event(url):
    """No JSON-LD Event here; the date is the event byline's <time>, not the
    related-event cards further down. Start is left blank so afternoon
    concerts aren't classified as day parties."""
    try:
        h = http_get(url)
    except Exception:
        return None
    tm = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
    dm = re.search(r'event-byline__date.*?<time datetime="(\d{4}-\d\d-\d\d)T', h, re.S)
    if not (tm and dm):
        return None
    names = barbican_performers(h)
    return {'date': dm.group(1), 'title': html_text(tm.group(1)), 'venue': 'Barbican', 'url': url,
            'names': names, 'lineup_verified': bool(names), 'start': '',
            'source': 'Barbican', 'hint': 'gig'}


def fetch_barbican():
    urls = set()
    for page in range(0, 12):
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
        for ev in ex.map(lambda u: barbican_event('https://www.barbican.org.uk' + u), sorted(urls)[:150]):
            if ev:
                events.append(ev)
    return events


def html_text(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def ronnies_listings(html):
    """Actual detail links and booking IDs, never guessed title slugs."""
    shows = {}
    for block in html.split('<div class="listing">')[1:]:
        link = re.search(r'href="(https://www\.ronniescotts\.co\.uk/find-a-show/[^"?]+)"', block)
        title = re.search(r'<h2 class="listing__title">(.*?)</h2>', block, re.S)
        ident = re.search(r'<button[^>]*id="id-(\d+)"', block)
        if link and title and ident:
            url = unescape(link.group(1))
            shows[url] = {'url': url, 'title': html_text(title.group(1)), 'id': ident.group(1)}
    return list(shows.values())


def ronnies_performers(content):
    """Names in the Line-up block only; exclude prose and related shows."""
    section = re.search(r'<h3\b[^>]*>\s*Line-up\s*</h3>(.*?)</div>', content, re.S | re.I)
    if section:
        text = re.sub(r'<(?:br\s*/?|/p)>', '\n', section.group(1), flags=re.I)
        text = unescape(re.sub(r'<[^>]+>', '', text))
    else:
        section = re.search(r'^#{1,6}\s+Line-up\s*\n(.*?)(?=\nTimes and Tickets|\n#{1,6}\s|\Z)',
                            content, re.S | re.M | re.I)
        if not section:
            return []
        text = section.group(1)
    names = []
    for line in text.splitlines():
        line = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', line).strip(' *\t')
        match = re.match(r'^(.+?)\s+[–—-]\s+\S', line)
        if match:
            name = match.group(1).strip(' *')
            if name and name not in names:
                names.append(name)
    return names


def ronnies_dates(html):
    """Exact performance dates; a residency's range is not a daily run."""
    dates = {}
    for block in re.split(r'<div\b[^>]*class="performance-option\s', html)[1:]:
        heading = re.search(r'<h2 class="performance-option__heading">(.*?)</h2>', block, re.S)
        if not heading:
            continue
        dm = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d\d)',
                       html_text(heading.group(1)))
        if not dm or dm.group(2).lower()[:3] not in MONTHS:
            continue
        try:
            day = date(int(dm.group(3)), MONTHS[dm.group(2).lower()[:3]], int(dm.group(1)))
        except ValueError:
            continue
        tm = re.search(r'<h3[^>]*>Show Starts</h3>\s*<p[^>]*>(\d{2}:\d{2})</p>', block)
        start = tm.group(1) if tm else ''
        key = str(day)
        if key not in dates or (start and (not dates[key] or start < dates[key])):
            dates[key] = start
    return dates


class RonnieEvents(list):
    """A complete venue response or a separately attributed backup calendar."""
    def __init__(self, events, source='RonnieScotts'):
        super().__init__(events)
        self.source = source


def fetch_ronnies_official():
    base = 'https://www.ronniescotts.co.uk/find-a-show'
    first = http_get(base)
    shows = {show['url']: show for show in ronnies_listings(first)}
    pages = re.search(r'totalPages:\s*(\d+)', first)
    count = int(pages.group(1)) if pages else 1
    if count > 60:
        raise ValueError("Ronnie Scott's listing exceeds the checked page limit")
    # Stop on a blocked or incomplete response. Never use a reader/proxy to
    # get around the venue's access controls, or call a partial run complete.
    for page in range(2, count + 1):
        batch = ronnies_listings(http_get(f'{base}?page={page}'))
        if not batch:
            raise ValueError("Incomplete Ronnie Scott's listing page")
        shows.update((show['url'], show) for show in batch)
    if not shows:
        raise RuntimeError("No Ronnie Scott's detail links found")
    artists = load_artists()
    candidates = {name for name, artist in artists.items()
                  if not too_thin(artist) and name not in DEAD_ARTISTS | EXCLUDE_ARTISTS}
    shows = [show for show in shows.values()
             if any(' ' + name + ' ' in ' ' + normalize(show['title']) + ' '
                    for name in candidates)]
    events = []
    for show in shows:
        names = ronnies_performers(http_get(show['url'], timeout=15))
        if not names:
            raise ValueError("Ronnie Scott's show has no accessible line-up")
        event = {'title': show['title'], 'venue': "Ronnie Scott's", 'url': show['url'],
                 'names': names, 'lineup_verified': True, 'source': 'RonnieScotts',
                 'hint': 'gig', 'checked_at': str(TODAY)}
        if not match_event(event, artists):
            continue
        dates = ronnies_dates(http_get(base + '?id=' + show['id'] + '&ajax=1',
            extra_headers={'X-Requested-With': 'XMLHttpRequest', 'X-Loadmore-Key': 'ajax-drawer'}))
        if not dates:
            raise ValueError("No performance dates in Ronnie Scott's booking drawer")
        events.extend(dict(event, date=day, start=start) for day, start in sorted(dates.items()))
    return RonnieEvents(events)


def fetch_ronnies():
    try:
        return fetch_ronnies_official()
    except Exception as error:
        print(f"    Ronnie Scott's venue feed unavailable: {error}; checking Songkick's public calendar", flush=True)
    from gigs_ronnies import fetch_songkick_ronnies
    events = fetch_songkick_ronnies(lambda url: http_get(url, timeout=25,
        extra_headers={'User-Agent': 'GigRadar/1.0 (+https://benmpolak.github.io/dj-archive/)'}), TODAY)
    return RonnieEvents(events, 'RonnieSongkick')


def bluenote_performers(html):
    """Ticketmaster attraction headings, distinct from the event/page title."""
    names = re.findall(r'<div\b[^>]*class=[\'"][^\'"]*\bartist-bio-wrap\b[^\'"]*[\'"][^>]*>'
                       r'\s*<div\b[^>]*>\s*<h3\b[^>]*>(.*?)</h3>', html, re.S | re.I)
    return list(dict.fromkeys(html_text(name) for name in names if html_text(name)))


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
        names = bluenote_performers(h)
        if not names:
            return []
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
                 'names': names, 'lineup_verified': True, 'start': start,
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


def drop_repeat_nights(matches):
    """The same night can arrive from RA and the venue's own feed under
    different titles and room names ("EartH" / "EartH Kitchen"). Keep the
    first row; a later one survives only if it adds an archive artist."""
    seen, kept = set(), []
    for m in matches:
        room = normalize(m['venue']).split(' ')[0]
        keys = {(r['name'], m['date'], room) for r in [m['artist']] + m['co']}
        if keys <= seen:
            continue
        seen |= keys
        kept.append(m)
    return kept


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


def group_gig_dates(matches):
    """Presentation-only runs. Keep every source row, identity and date intact."""
    buckets = defaultdict(list)
    for match in matches:
        buckets[(match['artist']['name'].casefold(), match['venue'].casefold())].append(match)
    groups = []
    for rows in buckets.values():
        run = []
        for match in sorted(rows, key=lambda m: (m['date'], -m['score'])):
            if run and date.fromisoformat(match['date']) != date.fromisoformat(run[-1]['date']) + timedelta(days=1):
                groups.append(run)
                run = []
            run.append(match)
        if run:
            groups.append(run)
    return sorted(groups, key=lambda rows: (rows[0]['date'], -max(m['score'] for m in rows), rows[0]['artist']['name']))


def render(matches, n_events, n_artists, sources_note, out, public=False, generated=None):
    matches = sorted(matches, key=lambda m: (m['date'], -m['score']))
    groups = group_gig_dates(matches)
    fresh_cut = str(TODAY - timedelta(days=7))
    upd = date.fromisoformat(generated or str(TODAY)).strftime('%-d %b %Y')
    venues = sorted({m['venue'] for m in matches if m['venue']}, key=str.lower)
    crates = sorted({m['artist']['crate'] for m in matches if m['artist']['crate'] and m['artist']['crate'].casefold() != 'uncategorized'},
                    key=lambda c: (-sum(1 for m in matches if m['artist']['crate'] == c), c))
    months = sorted({m['date'][:7] for m in matches})

    def why(m):
        r = m['artist']
        bits = [f"{r['tracks']} archive track{'s' if r['tracks'] != 1 else ''}"]
        if not public and r['plays']:
            bits.append(f"{r['plays']} play{'s' if r['plays'] != 1 else ''}")
        if r['crate'] and r['crate'].casefold() != 'uncategorized':
            bits.append(r['crate'])
        return ' · '.join(bits)

    def source_text(m):
        if m.get('source') not in ('RonnieScotts', 'RonnieSongkick'):
            return ''
        def short(day):
            try:
                return date.fromisoformat(day).strftime('%-d %b')
            except (ValueError, TypeError):
                return ''
        check = m.get('listing_check') or {}
        if m.get('retained_from'):
            text = ("Songkick listing " if m['source'] == 'RonnieSongkick' else "Venue line-up ") + short(m['retained_from'])
            if check.get('date'):
                text += ' · date also listed on Songkick ' + short(check['date'])
            else:
                text += ' · awaiting a fresh listing'
        elif m.get('source') == 'RonnieSongkick':
            text = 'Songkick listing · checked ' + short(m.get('checked_at'))
        else:
            text = 'Venue listing · checked ' + short(m.get('checked_at'))
        return text

    def member(m):
        r = m['artist']
        extras = ' '.join([x['name'] for x in m['co']] + [clean_name(x) for x in m['all_names']])
        return {'d': m['date'], 'key': f"{m['date']}|{r['name']}|{m['venue']}",
                'title': m['title'], 'artist': r['name'], 'v': m['venue'], 'url': m['url'],
                't': m['etype'], 'c': r['crate'], 'tracks': r['tracks'],
                'n': m['first_seen'] >= fresh_cut,
                's': f"{r['name']} {extras} {m['title']} {m['venue']}".lower(),
                'source': source_text(m)}

    def date_details(m, multiple):
        d = date.fromisoformat(m['date'])
        names = ', '.join(clean_name(x) for x in m['all_names'])
        data = member(m)
        attrs = ' '.join(f'data-{key}="{esc(str(data[key]))}"' for key in ['d', 'key', 'title', 'artist', 'v', 'url'])
        source = source_text(m)
        return f'''<li class="gig-date-detail" {attrs}>
  <p class="date-title">{d.strftime('%a %-d %b %Y')} · {esc(TYPE_LABEL[m['etype']])}</p>
  <p class="event-title">{esc(m['title'])}</p>
  {f'<p class="performers">Listed performers: {esc(names)}</p>' if names else ''}
  {f'<div class="source-check">{esc(source)}</div>' if source else ''}
  <div class="date-actions">{f'<button class="mini-action save-btn date-save" type="button" aria-label="Save {esc(data["artist"])} on {d.strftime("%-d %b")}" aria-pressed="false">Save date</button><a class="tix" href="{esc(m["url"])}" target="_blank" rel="noopener">Tickets for {d.strftime("%-d %b")}</a>' if multiple else ''}<button class="mini-action cal-btn" type="button" aria-label="Add {esc(data['artist'])} on {d.strftime('%-d %b')} to calendar">+ Cal</button></div>
</li>'''

    def row(rows, index):
        first = rows[0]
        nm = first['artist']['name']
        items = [member(m) for m in rows]
        payload = esc(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        sources = list(dict.fromkeys(x['source'] for x in items if x['source']))
        summary = sources[0] if len(sources) == 1 else 'Source dates vary · see each date below' if sources else ''
        dates = date.fromisoformat(first['date']).strftime('%-d %b')
        return f'''<details class="row gig-row" data-members="{payload}" data-v="{esc(first['venue'])}" data-d="{first['date']}" data-key="{esc(items[0]['key'])}" data-artist="{esc(nm)}" data-tracks="{first['artist']['tracks']}">
  <summary class="gig-summary" aria-label="Details for {esc(nm)} at {esc(first['venue'])}">
    <span class="r-date"><span class="date-range">{dates}</span><span class="detail-cue" aria-hidden="true">Details ↓</span></span>
    <span class="r-artist"><a class="a-link" href="index.html#find={quote(nm)}" onclick="try{{localStorage.setItem('gr_find',this.dataset.a)}}catch(e){{}}" data-a="{esc(nm)}" title="See them in the archive">{esc(nm)}</a></span>
    <span class="r-venue">{esc(first['venue'])}</span>
    <span class="why" title="{esc(why(first))}">{esc(why(first))}</span>
    <span class="source-summary">{esc(summary)}</span>
  <span class="row-actions"><button class="mini-action save-btn group-save" type="button" aria-label="Save {esc(nm)}" aria-pressed="false" title="Save">☆</button>{f'<button class="tix dates-toggle" type="button" aria-label="Choose tickets for {esc(nm)}">Tickets</button>' if len(rows)>1 else f'<a class="tix" href="{esc(first["url"])}" target="_blank" rel="noopener">Tickets</a>'}</span></summary>
  <div class="gig-expanded"><div class="expanded-actions"><a class="mini-action hear-link" href="index.html?hear={quote(nm)}">Hear five tracks</a><a class="sp-link" href="https://open.spotify.com/search/{quote(nm)}" target="_blank" rel="noopener" aria-label="Open {esc(nm)} in Spotify">▶</a></div><p class="why-full">{esc(why(first))}</p><ul class="date-details">{''.join(date_details(m,len(rows)>1) for m in rows)}</ul></div>
</details>'''

    month_chips = ''.join(f'<button class="fc fc-mo" data-mo="{ym}" type="button">{date.fromisoformat(ym + "-01").strftime("%b")}{" ’" + ym[2:4] if ym[:4] != str(TODAY.year) else ""}</button>' for ym in months)
    crate_chips = ''.join(f'<button class="fc fc-c" data-c="{esc(c)}" type="button">{esc(c)}</button>' for c in crates)
    venue_opts = '<option value="">All venues</option>' + ''.join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in venues)
    html = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gig Radar — DJ Archive</title><meta name="description" content="Upcoming London gigs and DJ nights matched to confirmed performers in the DJ Archive.">
<link rel="canonical" href="https://benmpolak.github.io/dj-archive/__PAGE__"><link rel="icon" href="assets/dj-archive-logo.svg" type="image/svg+xml">
<meta property="og:title" content="Gig Radar — DJ Archive"><meta property="og:description" content="London shows matched to 14 years of music collected by ear."><meta property="og:type" content="website"><meta property="og:url" content="https://benmpolak.github.io/dj-archive/__PAGE__"><meta property="og:image" content="https://benmpolak.github.io/dj-archive/assets/gig-radar-social.png"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="music-home.css">
<style>
:root{--bg:#0a0a0f;--card:#12121a;--card2:#181824;--border:#303039;--text:#e0e0e8;--dim:#aaa8ae;--accent:#e8a040}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',Roboto,sans-serif;padding-bottom:60px}
.visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
.gig-radar .wrap,.gig-radar .f-inner{max-width:880px;margin:0 auto;padding:0 18px}
.gig-radar header.hero{border-bottom:1px solid var(--border);padding:20px 0 16px;margin:0;background:#101014}
.gig-radar h1{margin:0;color:#f4c17b;font-size:28px;font-weight:700;letter-spacing:.07em}
.gig-radar .sub{margin:6px 0 0;color:var(--dim);font-size:13px!important;line-height:1.4!important}
.gig-radar .sub a,.gig-radar .foot a{color:var(--accent)}
.gig-radar .filters{position:sticky!important;top:0;z-index:20;background:#101014;border-bottom:1px solid var(--border)}
.gig-radar .f-inner{position:relative}
.gig-radar .f-primary{display:flex;align-items:center;gap:8px;min-height:62px;overflow-x:auto;scrollbar-width:thin;white-space:nowrap}
.gig-radar .mobile-search{display:none}
.gig-radar .search-field{flex:1;min-width:170px}
.gig-radar .compact-label{display:none}
.gig-radar #q{min-width:0;width:100%;height:44px;background:var(--card);border:1px solid var(--border);border-radius:7px;padding:8px 12px;color:var(--text);font:inherit;font-size:14px}
.gig-radar .fc,.gig-radar #venue{min-height:44px;flex-shrink:0;background:var(--card);border:1px solid var(--border);border-radius:7px;padding:8px 12px;color:var(--dim);font:inherit;font-size:13px!important;cursor:pointer}
.gig-radar .fc.on{color:#f4c17b;border-color:var(--accent);background:#25211b}
.gig-radar button:focus-visible,.gig-radar a:focus-visible,.gig-radar input:focus-visible,.gig-radar select:focus-visible,.gig-radar summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.gig-radar #filters-toggle{position:sticky;right:0;background:#181824;box-shadow:-8px 0 10px #101014;z-index:1}
.gig-radar .filter-more{position:absolute;left:18px;right:18px;top:100%;background:#181824;border:1px solid var(--border);border-radius:0 0 9px 9px;padding:16px;max-height:65vh;overflow-y:auto;box-shadow:0 10px 20px #0005;display:flex;flex-direction:column;gap:14px}
.gig-radar .filter-more[hidden]{display:none!important}
.gig-radar .f-line{display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.gig-radar .f-label{min-width:45px;color:var(--dim);font-size:12px}
.gig-radar #venue{min-width:0;max-width:100%;flex:1}
.gig-radar .filter-actions{border-top:1px solid var(--border);padding-top:12px;justify-content:space-between}
.gig-radar .filter-summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;min-height:64px}
.gig-radar #result-count{color:var(--dim);font-size:12px}
.gig-radar #scope-toggle{color:#f4c17b}
.gig-radar .row.gig-row{display:block;position:relative;background:var(--card);border:1px solid var(--border);border-radius:9px;margin:0 0 6px;padding:6px 12px;color:var(--text)}
.gig-radar .gig-summary{display:block;list-style:none;cursor:pointer;padding-right:90px;min-height:97px}
.gig-radar .gig-summary::-webkit-details-marker{display:none}
.gig-radar .r-date{display:flex;align-items:center;gap:12px;color:#f4c17b;font-size:12px;line-height:1.4}
.gig-radar .detail-cue{font-size:10px;color:var(--dim);margin-left:auto;white-space:nowrap}
.gig-radar details[open] .detail-cue{font-size:0}.gig-radar details[open] .detail-cue:after{content:'Less ↑';font-size:10px}
.gig-radar .r-artist{display:block;margin:0;font-size:17px!important;line-height:1.25}
.gig-radar .a-link{display:flex;align-items:center;min-height:44px;color:var(--text);text-decoration:none;font-weight:650;overflow-wrap:anywhere}
.gig-radar .a-link:hover{color:#f4c17b}
.gig-radar .r-venue{display:block;color:var(--dim)!important;font-size:13px!important;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gig-radar .why{display:block;margin:0;color:var(--dim)!important;font-size:12px!important;line-height:1.5!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gig-radar .source-summary{display:block;margin-top:2px;color:var(--dim);font-size:10px;line-height:1.4}
.gig-radar .source-summary:empty{display:none}
.gig-radar .row-actions{position:absolute;top:8px;right:10px;margin:0;width:76px;display:flex;flex-direction:column;align-items:stretch;gap:4px}
.gig-radar .mini-action,.gig-radar .tix{display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card2);color:var(--text);font:inherit;font-size:12px!important;text-decoration:none;cursor:pointer}
.gig-radar .group-save{font-size:21px!important;align-self:flex-end;width:44px;padding:0}
.gig-radar .save-btn.saved{color:#f4c17b;border-color:var(--accent);background:#25211b}
.gig-radar .gig-expanded{border-top:1px solid var(--border);margin-top:10px;padding:12px 0 6px}
.gig-radar .expanded-actions,.gig-radar .date-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.gig-radar .sp-link{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:#1DB954;color:#000;text-decoration:none;font-size:13px;flex-shrink:0}
.gig-radar .why-full,.gig-radar .performers{font-size:12px;line-height:1.5;color:var(--dim);margin:8px 0}
.gig-radar .date-details{padding:0;margin:12px 0 0;list-style:none}
.gig-radar .gig-date-detail{padding:12px 0;border-top:1px solid var(--border)}
.gig-radar .gig-date-detail[hidden]{display:none}
.gig-radar .date-title{font-size:13px;color:#f4c17b;margin:0 0 6px}
.gig-radar .event-title{margin:0 0 6px;font-size:14px;line-height:1.4}
.gig-radar .source-check{font-size:12px;line-height:1.5;color:var(--dim);margin:6px 0 10px}
.gig-radar #none{display:none;color:var(--dim);font-size:14px;padding:28px 0}
.gig-radar .foot{color:var(--dim);font-size:12px;line-height:1.6;margin:28px 0 0}
@media(max-width:560px){.gig-radar .mobile-search{display:block;padding-top:10px;padding-bottom:0}.gig-radar .f-primary{gap:6px;justify-content:space-between;overflow:visible}.gig-radar .f-primary .fc{padding-left:10px;padding-right:10px}.gig-radar #filters-toggle{position:static;box-shadow:none}.gig-radar .wrap,.gig-radar .f-inner{padding-left:12px;padding-right:12px}.gig-radar header.hero{padding:16px 0 12px}.gig-radar .filter-more{left:12px;right:12px}.gig-radar .filter-summary{gap:8px}.gig-radar #scope-toggle{font-size:12px!important;padding:8px}.gig-radar .row.gig-row{padding:6px 10px}.gig-radar .gig-summary{padding-right:78px}.gig-radar .row-actions{right:8px;width:68px}.gig-radar .tix{padding:8px 6px}.gig-radar .r-artist{font-size:16px!important}.gig-radar .detail-cue{margin-left:0}.gig-radar .source-summary{font-size:10px}}
@media(max-width:360px){.gig-radar .f-primary .full-label{display:none}.gig-radar .f-primary .compact-label{display:inline}.gig-radar .f-primary .fc{padding-left:9px;padding-right:9px}}
</style></head><body class="gig-radar">
<nav class="music-nav" aria-label="Music"><a class="music-brand" href="index.html">DJ Archive</a><a href="index.html">Discover</a><a href="index.html?view=records">Full archive</a><a href="gigs.html" aria-current="page">Gigs</a><a href="index.html?view=saved">Saved</a><a href="https://the-dial-listen.benmpolak.workers.dev/" target="_blank" rel="noopener">The Dial</a></nav>
<header class="hero"><div class="wrap"><h1>Gig Radar</h1><p class="sub">London shows matched to the archive · updated __UPDATED____SHARE__</p></div></header>
<div class="mobile-search wrap" id="mobile-search"></div>
<div class="filters"><div class="f-inner"><div class="f-primary"><div class="search-field"><label class="visually-hidden" for="q">Search gigs</label><input id="q" type="search" placeholder="Artist, event, venue…" autocomplete="off"></div><button class="fc fc-range" data-range="weekend" type="button" aria-label="This weekend"><span class="full-label">This weekend</span><span class="compact-label" aria-hidden="true">Weekend</span></button><button class="fc fc-range" data-range="30" type="button" aria-label="Next 30 days"><span class="full-label">Next 30 days</span><span class="compact-label" aria-hidden="true">30 days</span></button><button class="fc" id="fsaved" type="button">Saved</button><button class="fc" id="filters-toggle" type="button" aria-expanded="false" aria-controls="filter-more">Filters</button></div>
<div class="filter-more" id="filter-more" hidden><div class="f-line"><span class="f-label">Month</span>__MONTHS__</div><div class="f-line"><label class="f-label" for="venue">Venue</label><select id="venue">__VENUES__</select></div><div class="f-line"><span class="f-label">Type</span><button class="fc fc-t" data-t="gig" type="button">Live gigs</button><button class="fc fc-t" data-t="dj" type="button">DJ nights</button><button class="fc fc-t" data-t="day" type="button">Day parties</button><button class="fc" id="fnew" type="button">New this week</button></div><div class="f-line"><span class="f-label">Crate</span>__CRATES__</div><div class="f-line filter-actions"><button class="fc" id="copy-link" type="button">Copy link</button><button class="fc" id="clear" type="button">Clear filters</button><button class="fc" id="filters-close" type="button">Done</button></div></div></div></div>
<main class="wrap"><div class="filter-summary"><span id="result-count" role="status" aria-live="polite"></span><button class="fc" id="scope-toggle" type="button" aria-pressed="false">Show all __COUNT__ shows</button></div><div id="gig-list">__ROWS__</div><p id="none">Nothing matches those filters.</p><div class="foot">Matched from __EVENTS__ London listings against __ARTISTS__ archive artists · updated __UPDATED__.<br>__SOURCES__<br>Chosen by ear. Matched against confirmed performers.</div></main>
<script>
(function(){
'use strict';
var phone=matchMedia('(max-width:560px)'),searchField=document.querySelector('.search-field'),primary=document.querySelector('.f-primary');
function placeSearch(){if(phone.matches)document.getElementById('mobile-search').appendChild(searchField);else primary.insertBefore(searchField,primary.firstChild)}
placeSearch();phone.addEventListener('change',placeSearch);
var F={q:'',v:'',t:null,mo:null,c:null,n:false,range:null,saved:false,all:false};
var TODAY=new Date();TODAY.setHours(0,0,0,0);
var SAVED_KEY='gr_saved_gigs_v1',saved={};
try{var stored=JSON.parse(localStorage.getItem(SAVED_KEY)||'{}');if(stored&&typeof stored==='object'&&!Array.isArray(stored))saved=stored}catch(e){}
var rows=Array.from(document.querySelectorAll('.gig-row')).map(function(el){return {el:el,items:JSON.parse(el.dataset.members),visible:[]}});
var cut=iso(TODAY);
function on(sel,ev,fn){document.querySelectorAll(sel).forEach(function(el){el.addEventListener(ev,fn)})}
function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
function nextDay(day){var d=new Date(day+'T12:00:00');d.setDate(d.getDate()+1);return iso(d)}
function dayLabel(day,year){return new Date(day+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',...(year?{year:'numeric'}:{})})}
function dateLabel(items){
 var dates=Array.from(new Set(items.map(function(x){return x.d}))).sort(),runs=[];
 dates.forEach(function(d){var last=runs[runs.length-1];if(last&&nextDay(last[last.length-1])===d)last.push(d);else runs.push([d])});
 return runs.map(function(run){var first=run[0],last=run[run.length-1],year=first.slice(0,4)!==String(TODAY.getFullYear())||last.slice(0,4)!==String(TODAY.getFullYear());if(first===last)return dayLabel(first,year);return first.slice(0,7)===last.slice(0,7)?Number(first.slice(-2))+'–'+dayLabel(last,year):dayLabel(first,year)+' – '+dayLabel(last,year)}).join(', ');
}
function dateInRange(value,range){
 if(!range)return true;
 var end=new Date(TODAY),start=new Date(TODAY),day=TODAY.getDay();
 if(range==='30'){end.setDate(end.getDate()+30);return value>=iso(start)&&value<=iso(end)}
 if(day>=1&&day<=5){start.setDate(start.getDate()+((5-day+7)%7));end=new Date(start);end.setDate(end.getDate()+2)}else if(day===6)end.setDate(end.getDate()+1);
 return value>=iso(start)&&value<=iso(end);
}
function toggle(key,val){F[key]=F[key]===val?null:val;apply()}
on('.fc-t','click',function(){toggle('t',this.dataset.t)});
on('.fc-mo','click',function(){F.range=null;toggle('mo',this.dataset.mo)});
on('.fc-c','click',function(){toggle('c',this.dataset.c)});
on('.fc-range','click',function(){F.mo=null;toggle('range',this.dataset.range)});
on('#fnew','click',function(){F.n=!F.n;apply()});on('#fsaved','click',function(){F.saved=!F.saved;apply()});
on('#q','input',function(){F.q=this.value.toLowerCase().trim();apply()});on('#venue','change',function(){F.v=this.value;apply()});
on('#scope-toggle','click',function(){F.all=!F.all;apply()});
function sizeDrawer(){var panel=document.getElementById('filter-more');if(!panel.hidden)panel.style.maxHeight='min(65vh, '+Math.max(0,innerHeight-panel.getBoundingClientRect().top-12)+'px)'}
function drawer(open,focus){document.getElementById('filter-more').hidden=!open;document.getElementById('filters-toggle').setAttribute('aria-expanded',String(open));sizeDrawer();if(focus)document.getElementById('filters-toggle').focus()}
window.addEventListener('scroll',sizeDrawer,{passive:true});window.addEventListener('resize',sizeDrawer);
on('#filters-toggle','click',function(){drawer(this.getAttribute('aria-expanded')!=='true')});on('#filters-close','click',function(){drawer(false,true)});
document.addEventListener('keydown',function(e){if(e.key==='Escape')drawer(false,true)});
document.addEventListener('pointerdown',function(e){if(!e.target.closest('.filters'))drawer(false)});
on('#clear','click',function(){F={q:'',v:'',t:null,mo:null,c:null,n:false,range:null,saved:false,all:false};document.getElementById('q').value='';document.getElementById('venue').value='';apply()});
on('#copy-link','click',function(){var btn=this;function done(){btn.textContent='Copied';setTimeout(function(){btn.textContent='Copy link'},1400)}if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(location.href).then(done).catch(function(){btn.textContent='Could not copy'});else{var ta=document.createElement('textarea');ta.value=location.href;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();done()}});
function syncUrl(){var p=new URLSearchParams();['q','v','t','mo','c','range'].forEach(function(k){if(F[k])p.set(k,F[k])});if(F.n)p.set('new','1');if(F.saved)p.set('saved','1');if(F.all)p.set('all','1');history.replaceState(null,'',location.pathname+(p.toString()?'?'+p:'')+location.hash)}
function pressed(el,on){el.classList.toggle('on',on);el.setAttribute('aria-pressed',String(on))}
function matching(x){return x.d>=cut&&(!F.q||x.s.indexOf(F.q)>-1)&&(!F.v||x.v===F.v)&&(!F.t||x.t===F.t)&&(!F.mo||x.d.slice(0,7)===F.mo)&&(!F.c||x.c===F.c)&&(!F.n||x.n)&&dateInRange(x.d,F.range)&&(!F.saved||saved[x.key])&&(F.all||F.q||F.saved||x.tracks>=3)}
function apply(skipUrl){
 var total=0,count=0,allDates=0;
 rows.forEach(function(row){
  allDates+=row.items.filter(function(x){return x.d>=cut}).length;
  row.visible=row.items.filter(matching);row.el.hidden=!row.visible.length;row.el.style.display=row.visible.length?'':'none';
  var visibleKeys=new Set(row.visible.map(function(x){return x.key}));row.el.querySelectorAll('.gig-date-detail').forEach(function(el){el.hidden=!visibleKeys.has(el.dataset.key)});
  if(!row.visible.length){row.el.open=false;return}
  total+=row.visible.length;count++;row.el.querySelector('.date-range').textContent=dateLabel(row.visible);
  var sources=Array.from(new Set(row.visible.map(function(x){return x.source}).filter(Boolean)));
  row.el.querySelector('.source-summary').textContent=sources.length===1?sources[0]:sources.length?'Source dates vary · see each date below':'';
  row.el.querySelector('.gig-summary').setAttribute('aria-label','Details for '+row.visible[0].artist+' · '+dateLabel(row.visible)+' · '+row.visible[0].v);
 });
 document.getElementById('result-count').textContent=count+' listing'+(count===1?'':'s')+(total!==count?' · '+total+' dates':'')+(!F.all&&!F.q&&!F.saved?' · 3+ archive tracks':'');
 document.getElementById('scope-toggle').textContent=F.all?'Three or more tracks':'Show all '+allDates+' shows';document.getElementById('scope-toggle').setAttribute('aria-pressed',String(F.all));
 document.getElementById('none').style.display=count?'none':'block';
 [['.fc-t','t'],['.fc-mo','mo'],['.fc-c','c'],['.fc-range','range']].forEach(function(pair){document.querySelectorAll(pair[0]).forEach(function(b){pressed(b,F[pair[1]]===b.dataset[pair[1]])})});
 pressed(document.getElementById('fnew'),F.n);pressed(document.getElementById('fsaved'),F.saved);
 var filterCount=[F.v,F.t,F.mo,F.c,F.n].filter(Boolean).length;document.getElementById('filters-toggle').textContent='Filters'+(filterCount?' · '+filterCount:'');
 refreshSaves();if(!skipUrl)syncUrl();
}
function refreshSaves(){rows.forEach(function(row){var keys=row.visible.map(function(x){return x.key}),n=keys.filter(function(k){return saved[k]}).length,btn=row.el.querySelector('.group-save');btn.classList.toggle('saved',n>0);btn.textContent=n?'★':'☆';btn.setAttribute('aria-pressed',n&&n<keys.length?'mixed':String(n>0));btn.title=n&&n<keys.length?'Some dates saved; save all shown dates':n?'Remove shown saved dates':'Save shown dates';row.el.querySelectorAll('.date-save').forEach(function(b){var yes=!!saved[b.closest('.gig-date-detail').dataset.key];b.classList.toggle('saved',yes);b.textContent=yes?'Saved date':'Save date';b.setAttribute('aria-pressed',String(yes))})})}
function persist(){try{localStorage.setItem(SAVED_KEY,JSON.stringify(saved))}catch(e){}if(F.saved)apply();else refreshSaves()}
on('.group-save','click',function(e){e.preventDefault();e.stopPropagation();var row=rows.find(function(r){return r.el===e.target.closest('.gig-row')}),keys=row.visible.map(function(x){return x.key}),remove=keys.every(function(k){return saved[k]});keys.forEach(function(k){if(remove)delete saved[k];else saved[k]=1});persist()});
on('.date-save','click',function(e){e.preventDefault();var key=this.closest('.gig-date-detail').dataset.key;if(saved[key])delete saved[key];else saved[key]=1;persist()});
on('.dates-toggle','click',function(){var row=this.closest('.gig-row');row.open=true;row.querySelector('.gig-date-detail:not([hidden]) .tix')?.focus()});
function icsEscape(s){return (s||'').replace(/\\/g,'\\\\').replace(/;/g,'\\;').replace(/,/g,'\\,').replace(/\n/g,'\\n')}
on('.cal-btn','click',function(e){e.preventDefault();var box=this.closest('.gig-date-detail'),start=box.dataset.d.replace(/-/g,''),end=nextDay(box.dataset.d).replace(/-/g,''),title=box.dataset.title===box.dataset.artist?box.dataset.artist:box.dataset.artist+' — '+box.dataset.title;var lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//DJ Archive//Gig Radar//EN','BEGIN:VEVENT','UID:'+start+'-'+encodeURIComponent(box.dataset.key)+'@dj-archive','DTSTART;VALUE=DATE:'+start,'DTEND;VALUE=DATE:'+end,'SUMMARY:'+icsEscape(title),'LOCATION:'+icsEscape(box.dataset.v),'DESCRIPTION:'+icsEscape('Tickets: '+box.dataset.url),'URL:'+box.dataset.url,'END:VEVENT','END:VCALENDAR'];var blob=new Blob([lines.join('\r\n')],{type:'text/calendar;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(box.dataset.artist+' '+box.dataset.d+'.ics').replace(/[^a-z0-9 ._-]/gi,'');document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},500)});
window.addEventListener('storage',function(e){if(e.key===SAVED_KEY){try{var value=JSON.parse(e.newValue||'{}');saved=value&&typeof value==='object'&&!Array.isArray(value)?value:{}}catch(err){saved={}}apply(true)}});
var p=new URLSearchParams(location.search);F.q=(p.get('q')||'').toLowerCase().trim();F.v=p.get('v')||'';F.t=p.get('t');F.mo=p.get('mo');F.c=p.get('c');F.range=p.get('range');F.n=p.get('new')==='1';F.saved=p.get('saved')==='1';F.all=p.get('all')==='1';document.getElementById('q').value=F.q;document.getElementById('venue').value=F.v;apply(true);
})();
</script></body></html>'''
    replacements = {'__PAGE__': 'gigs-share.html' if public else 'gigs.html', '__UPDATED__': upd,
                    '__SHARE__': '' if public else ' · <a href="gigs-share.html">Shareable version</a>',
                    '__MONTHS__': month_chips, '__VENUES__': venue_opts, '__CRATES__': crate_chips,
                    '__COUNT__': str(len(matches)), '__ROWS__': '\n'.join(row(rows, i) for i, rows in enumerate(groups)),
                    '__EVENTS__': f'{n_events:,}', '__ARTISTS__': f'{n_artists:,}', '__SOURCES__': sources_note}
    for token, value in replacements.items():
        html = html.replace(token, value)
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
                or re.search(r'cancel|postpon|movedonline', str(event.get('status', '')), re.I))


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


def serialise_match(match):
    return {**{key: match[key] for key in ('date', 'title', 'venue', 'url', 'source',
                'how', 'score', 'etype', 'first_seen')},
            'performers': match['performers'], 'artist': match['artist']['name'],
            'co': [artist['name'] for artist in match['co']],
            **{key: match[key] for key in ('checked_at', 'retained_from', 'listing_check') if key in match}}


def same_ronnies_show(match, event):
    if match['date'] != event.get('date'):
        return False
    checked_url = (match.get('listing_check') or {}).get('url')
    if event.get('url') and event['url'] in (match.get('url'), checked_url):
        return True
    # A title can identify a duplicate listing, but never qualifies an artist.
    old, new = normalize(match['title']), normalize(event.get('title', ''))
    return bool(new and (old == new or (len(new) >= 4 and ' ' + new + ' ' in ' ' + old + ' ')))


def reconcile_ronnies(fresh, retained, events):
    """Keep venue line-ups intact; a backup can corroborate the date only.

    Missing backup entries are not cancellations. Explicit cancelled backup
    events suppress the corresponding retained listing, without changing others.
    """
    cancelled = [event for event in events if is_cancelled(event)]
    current_urls = {event['url'] for event in events}
    retained = [dict(match) for match in retained
                if not (match['source'] == 'RonnieSongkick' and match['url'] in current_urls)
                and not any(same_ronnies_show(match, event) for event in cancelled)]
    additions = []
    for match in fresh:
        retained = [old for old in retained if not (old['source'] == 'RonnieSongkick' and same_ronnies_show(old, match))]
        duplicates = [old for old in retained if same_ronnies_show(old, match)]
        if duplicates:
            for old in duplicates:
                old['listing_check'] = {'source': 'Songkick', 'date': match['checked_at'], 'url': match['url']}
        else:
            additions.append(match)
    return retained + drop_repeat_nights(additions)


def matched_ronnies(events, artists, previous):
    seen = {(match['artist'], match['date']): match.get('first_seen', '2000-01-01')
            for match in previous.get('matches', [])}
    groups = {}
    for event in events:
        if not str(TODAY) <= event['date'] <= str(TODAY + timedelta(days=365)):
            continue
        hits = match_event(event, artists)
        for norm, how in hits.items():
            if is_tribute(event['title'], how) or norm in DEAD_ARTISTS | EXCLUDE_ARTISTS:
                continue
            artist = artists[norm]
            match = {'date': event['date'], 'title': event['title'], 'venue': event['venue'],
                     'url': event['url'], 'source': event['source'], 'how': how,
                     'artist': artist, 'co': [], 'performers': event['names'], 'all_names': event['names'],
                     'etype': classify(event, event['title']), 'score': artist_score(artist),
                     'first_seen': seen.get((artist['name'], event['date']), str(TODAY)),
                     'checked_at': event.get('checked_at', str(TODAY))}
            key = (match['date'], normalize(match['title']))
            old = groups.get(key)
            if old is not None:
                names = list(dict.fromkeys(old['performers'] + match['performers']))
                old['performers'] = old['all_names'] = names
                match['performers'] = match['all_names'] = names
            if old is None:
                groups[key] = match
            elif artist['name'] != old['artist']['name'] and artist['name'] not in {item['name'] for item in old['co']}:
                if match['score'] > old['score']:
                    match['co'] = old['co'] + [old['artist']]
                    groups[key] = match
                else:
                    old['co'].append(artist)
    matches = drop_repeat_nights(list(groups.values()))
    for match in matches:
        match['score'] += 5 * len(match['co'])
    return matches


def refresh_ronnies_only(artists, out):
    """A targeted refresh preserves every other venue row and its generation date."""
    previous = json.loads(Path(HERE, 'gigs-data.json').read_text())
    events = fetch_ronnies()  # An incomplete/failed fallback raises before any write.
    source = getattr(events, 'source', 'RonnieScotts')
    fresh = matched_ronnies(events, artists, previous)
    counts = dict(previous.get('source_counts', {}))
    carried = dict(previous.get('carried_from', {}))
    if source == 'RonnieSongkick':
        old = hydrate_saved_matches({'matches': [match for match in previous['matches']
                                     if match.get('source') in ('RonnieScotts', 'RonnieSongkick')]}, artists)
        for match in old:
            match['retained_from'] = match.get('retained_from') or match.get('checked_at') or carried.get("Ronnie Scott's", previous['generated'])
        fresh = reconcile_ronnies(fresh, old, events)
        counts["Ronnie Scott's"] = 0
        counts["Songkick (Ronnie Scott's)"] = len(events)
        dates = [match['retained_from'] for match in fresh if match.get('retained_from')]
        if dates:
            carried["Ronnie Scott's"] = min(dates)
        else:
            carried.pop("Ronnie Scott's", None)
    else:
        counts["Ronnie Scott's"] = len(events)
        counts.pop("Songkick (Ronnie Scott's)", None)
        carried.pop("Ronnie Scott's", None)
    payload = {**previous, 'source_counts': counts,
               'matches': [match for match in previous['matches'] if match.get('source') not in ('RonnieScotts', 'RonnieSongkick')]
                          + [serialise_match(match) for match in fresh]}
    if carried:
        payload['carried_from'] = carried
    else:
        payload.pop('carried_from', None)
    Path(HERE, 'gigs-data.json').write_text(json.dumps(payload, indent=1))
    visible = hydrate_saved_matches(payload, artists)
    note = existing_sources_note()
    render(visible, payload.get('events', 0), len(artists), note, out, generated=payload['generated'])
    render(visible, payload.get('events', 0), len(artists), note, out.replace('gigs.html', 'gigs-share.html'),
           public=True, generated=payload['generated'])
    print(f"Ronnie Scott's refreshed: {len(events)} source events, {len(fresh)} matched shows; other venue data unchanged")


def save_matches(matches, generated, n_events, source_counts=None, carried_from=None):
    if source_counts is None:
        try:
            source_counts = json.loads(Path(HERE, 'gigs-data.json').read_text()).get('source_counts', {})
        except (OSError, ValueError):
            source_counts = {}
    payload = {'generated': generated, 'events': n_events, 'matching_rule': 'explicit-performers-v1',
               'source_counts': source_counts,
               'matches': [serialise_match(match) for match in matches]}
    if carried_from:
        payload['carried_from'] = carried_from
    Path(HERE, 'gigs-data.json').write_text(json.dumps(payload, indent=1))


def existing_sources_note():
    try:
        payload = json.loads(Path(HERE, 'gigs-data.json').read_text())
        counts, carried = payload.get('source_counts', {}), payload.get('carried_from', {})
        if counts or carried:
            sources = ', '.join(name for name, count in counts.items() if count)
            checks = [m.get('checked_at', '') for m in payload.get('matches', []) if m.get('source') == 'RonnieSongkick']
            checks += [(m.get('listing_check') or {}).get('date', '') for m in payload.get('matches', [])]
            held = ''
            for name, day in carried.items():
                when = date.fromisoformat(day).strftime('%-d %b')
                if name == "Ronnie Scott's" and any(checks):
                    held += f" Earlier Ronnie Scott's listings are retained from {when}; the venue feed is unavailable."
                else:
                    held += f' {name} shows are from its {when} listings; its site is blocking the refresh.'
            if any(checks):
                held += " Ronnie Scott's backup: Songkick listings checked " + date.fromisoformat(max(checks)).strftime('%-d %b') + ". Earlier venue line-ups keep their original dates."

            return (('Sources: ' + sources + '.' if sources else 'Saved listings.') + held +
                    ' Only explicitly listed performers qualify. Title mentions, cancelled shows '
                    'and tribute nights are excluded.')
    except (OSError, ValueError):
        pass
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
    ap.add_argument('--refresh-ronnies', action='store_true', help="refresh Ronnie Scott's only, retaining other venue data")
    args = ap.parse_args()

    print('Loading archive artists...')
    artists = load_artists()
    print(f'  {len(artists)} unique artists')

    if args.refresh_ronnies:
        refresh_ronnies_only(artists, args.out)
        return

    if args.render_existing:
        payload = json.load(open(f'{HERE}/gigs-data.json'))
        matches = hydrate_saved_matches(payload, artists)
        note = existing_sources_note()
        save_matches(matches, payload['generated'], payload.get('events', 0),
                     payload.get('source_counts', {}), payload.get('carried_from', {}))
        render(matches, payload.get('events', 0), len(artists), note, args.out, generated=payload['generated'])
        share_out = args.out.replace('gigs.html', 'gigs-share.html')
        render(matches, payload.get('events', 0), len(artists), note, share_out, public=True, generated=payload['generated'])
        print(f'Wrote {args.out} + {share_out} from existing data')
        return

    # previous run's first_seen map
    prev_seen, prev_sources, bootstrap = {}, set(), True
    prev = {'matches': []}
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

    events, src_counts, ronnies_batch = [], {}, None
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
            if label == "Ronnie Scott's":
                ronnies_batch = batch
                if getattr(batch, 'source', None) == 'RonnieSongkick':
                    src_counts[label] = 0
                    src_counts["Songkick (Ronnie Scott's)"] = len(batch)
            events.extend(batch)
        except Exception as e:
            print(f'  {label} FAILED: {e}', file=sys.stderr)
            src_counts[label] = 0

    # A blocked jazz listing shouldn't freeze every other venue. Keep its upcoming shows
    # from the last good listings, re-checked like saved data, and say so on the page.
    carried, carried_from = [], {}
    for name, source in (('Blue Note', 'BlueNote'), ("Ronnie Scott's", 'RonnieScotts')):
        official_complete = name == "Ronnie Scott's" and getattr(ronnies_batch, 'source', None) == 'RonnieScotts'
        if src_counts.get(name) or official_complete:
            continue
        fallback = name == "Ronnie Scott's" and getattr(ronnies_batch, 'source', None) == 'RonnieSongkick'
        sources = {source, 'RonnieSongkick'} if name == "Ronnie Scott's" else {source}
        kept = hydrate_saved_matches({'matches': [m for m in prev['matches'] if m.get('source') in sources]}, artists)
        if not kept and not fallback:
            sys.exit(f'Jazz source failed: {name}, with no saved shows to keep. '
                     'Keeping the existing gig files for review.')
        if kept:
            day = prev.get('carried_from', {}).get(name, prev.get('generated', str(TODAY)))
            for match in kept:
                if name == "Ronnie Scott's":
                    match['retained_from'] = match.get('retained_from') or match.get('checked_at') or day
            carried += kept
            carried_from[name] = day
            print(f'::warning::{name} venue listing unavailable; keeping {len(kept)} earlier line-ups from {day}')

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
                            'score': artist_score(r), **({'checked_at': ev['checked_at']} if ev.get('checked_at') else {})})
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
    matches = drop_repeat_nights(list(grouped.values()))
    if not matches:
        sys.exit('No verified performers found — retaining the existing gig files.')
    for m in matches:
        m['score'] += 5 * len(m['co'])
    if getattr(ronnies_batch, 'source', None) == 'RonnieSongkick':
        backup = [match for match in matches if match['source'] == 'RonnieSongkick']
        old = [match for match in carried if match['source'] in ('RonnieScotts', 'RonnieSongkick')]
        matches = [match for match in matches if match['source'] != 'RonnieSongkick']
        reconciled = reconcile_ronnies(backup, old, ronnies_batch)
        matches += reconciled
        dates = [match['retained_from'] for match in reconciled if match.get('retained_from')]
        if dates:
            carried_from["Ronnie Scott's"] = min(dates)
        else:
            carried_from.pop("Ronnie Scott's", None)
        carried = [match for match in carried if match['source'] not in ('RonnieScotts', 'RonnieSongkick')]
    matches += carried

    print(f'{len(events)} events in window -> {len(matches)} matched shows')

    save_matches(matches, str(TODAY), len(events), src_counts, carried_from)

    note = existing_sources_note()
    render(matches, len(events), len(artists), note, args.out)
    share_out = args.out.replace('gigs.html', 'gigs-share.html')
    render(matches, len(events), len(artists), note, share_out, public=True)
    print(f'Wrote {args.out} + {share_out}')


if __name__ == '__main__':
    main()
