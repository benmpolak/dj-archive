"""Explicit Ronnie Scott's performers from Songkick's public venue calendar.

No title matching, private API, official-site fallback or retries. A failed or
incomplete feed raises SongkickFeedError so the caller can retain its cache.
"""
import json
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

CALENDAR = 'https://www.songkick.com/venues/36418-ronnie-scotts-jazz-club/calendar'
CALENDAR_PATH = '/venues/36418-ronnie-scotts-jazz-club/calendar'
MAX_PAGES = 6
PAGE_DELAY = 1.0
MAX_HTML_BYTES = 4 * 1024 * 1024
LONDON = ZoneInfo('Europe/London')
VENUE_SUFFIX = " @ Ronnie Scott's Jazz Club"
STATUSES = {'EventScheduled', 'EventCancelled', 'EventPostponed',
            'EventRescheduled', 'EventMovedOnline'}


class SongkickFeedError(ValueError):
    """The calendar cannot safely replace the last complete venue snapshot."""


class _CalendarHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.next_links = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and (attrs.get('type') or '').lower() == 'application/ld+json':
            if self._script is not None:
                raise SongkickFeedError('Malformed Songkick structured data.')
            self._script = []
        if tag in ('a', 'link') and 'next' in (attrs.get('rel') or '').lower().split():
            self.next_links.append(attrs.get('href'))

    def handle_data(self, value):
        if self._script is not None:
            self._script.append(value)

    def handle_endtag(self, tag):
        if tag == 'script' and self._script is not None:
            self.scripts.append(''.join(self._script))
            self._script = None


def _text(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def _schema_type(value, expected):
    values = value if isinstance(value, list) else [value]
    return any(item in (expected, 'https://schema.org/' + expected,
                        'http://schema.org/' + expected) for item in values)


def _nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from _nodes(item)
    elif isinstance(value, dict):
        yield value
        if '@graph' in value:
            if not isinstance(value['@graph'], (dict, list)):
                raise SongkickFeedError('Malformed Songkick schema graph.')
            yield from _nodes(value['@graph'])
    else:
        raise SongkickFeedError('Malformed Songkick structured data.')


def _official_venue_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme in ('http', 'https') and
                url.hostname in ('www.ronniescotts.co.uk', 'ronniescotts.co.uk') and
                not url.username and not url.password and url.port is None and
                url.path in ('', '/') and not url.query and not url.fragment)
    except ValueError:
        return False


def _is_ronnies(location):
    if not isinstance(location, dict) or not _schema_type(location.get('@type'), 'Place'):
        return False
    same_as = location.get('sameAs')
    links = same_as if isinstance(same_as, list) else [same_as]
    if not any(_official_venue_url(link) for link in links):
        return False
    address = location.get('address')
    if not isinstance(address, dict):
        return False
    street = re.findall(r'[a-z0-9]+', _text(address.get('streetAddress')).lower())
    street = ['street' if word == 'st' else word for word in street]
    postcode = re.sub(r'[^A-Z0-9]', '', _text(address.get('postalCode')).upper())
    country = _text(address.get('addressCountry')).lower()
    return (street in (['47', 'frith', 'street'], ['47', 'frith', 'street', 'soho']) and
            postcode == 'W1D4HT' and _text(address.get('addressLocality')).lower() == 'london' and
            country in ('', 'uk', 'gb', 'united kingdom'))


def _concert_url(value):
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname != 'www.songkick.com' or
                url.username or url.password or url.port is not None or
                not re.fullmatch(r'/concerts/[1-9][0-9]{0,19}-[A-Za-z0-9][A-Za-z0-9-]*/?', url.path)):
            raise ValueError()
        return 'https://www.songkick.com' + url.path.rstrip('/')
    except (TypeError, ValueError):
        raise SongkickFeedError('Invalid Songkick concert identity.') from None


def _date_and_time(value):
    if not isinstance(value, str):
        raise SongkickFeedError('Missing Songkick performance date.')
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return date.fromisoformat(value).isoformat(), None
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?', value):
            raise ValueError()
        iso = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', value.replace('Z', '+00:00'))
        moment = datetime.fromisoformat(iso)
        # Unzoned times on this London venue calendar are already local. Offset
        # timestamps are converted, including dates crossing midnight or BST.
        if moment.tzinfo is not None:
            moment = moment.astimezone(LONDON)
        return moment.date().isoformat(), moment.strftime('%H:%M')
    except ValueError:
        raise SongkickFeedError('Invalid Songkick performance date.') from None


def _event(item, today):
    if not _is_ronnies(item.get('location')):
        return None
    title = _text(item.get('name'))
    if title.endswith(VENUE_SUFFIX):
        title = title[:-len(VENUE_SUFFIX)].rstrip()
    if not title or len(title) > 1000:
        raise SongkickFeedError('Missing Songkick event title.')
    performers = item.get('performer')
    performers = performers if isinstance(performers, list) else [performers]
    if not performers or len(performers) > 200:
        raise SongkickFeedError('Missing explicit Songkick performers.')
    names = []
    for performer in performers:
        if (not isinstance(performer, dict) or
                not any(_schema_type(performer.get('@type'), kind) for kind in ('MusicGroup', 'Person'))):
            raise SongkickFeedError('Unverified Songkick performer data.')
        name = _text(performer.get('name'))
        if not name or len(name) > 500:
            raise SongkickFeedError('Missing explicit Songkick performer name.')
        # Keep distinct aliases/entities exactly as explicitly billed; never
        # split a group name or infer additional performers from the title.
        if name not in names:
            names.append(name)
    status = item.get('eventStatus')
    if not isinstance(status, str) or not re.fullmatch(r'https?://schema\.org/(?:' + '|'.join(sorted(STATUSES)) + ')', status):
        raise SongkickFeedError('Missing or invalid Songkick event status.')
    day, start = _date_and_time(item.get('startDate'))
    result = {'date': day, 'title': title, 'venue': "Ronnie Scott's",
              'url': _concert_url(item.get('url')), 'names': names,
              'lineup_verified': True, 'source': 'RonnieSongkick', 'hint': 'gig',
              'status': status, 'checked_at': str(today)}
    if start is not None:
        result['start'] = start
    return result


def _next_url(href, current):
    if not isinstance(href, str) or not href or len(href) > 500:
        raise SongkickFeedError('Invalid Songkick pagination link.')
    try:
        url = urlsplit(urljoin(current, href))
        if (url.scheme != 'https' or url.hostname != 'www.songkick.com' or
                url.username or url.password or url.port is not None or
                url.path != CALENDAR_PATH or url.fragment or
                not re.fullmatch(r'page=[1-9][0-9]{0,5}', url.query)):
            raise ValueError()
        return 'https://www.songkick.com' + CALENDAR_PATH + '?' + url.query
    except ValueError:
        raise SongkickFeedError('Unsafe Songkick pagination link.') from None


def parse_songkick_page(html, today, current=CALENDAR):
    """Return verified event records and the one observed, validated next URL."""
    if not isinstance(html, str) or not html or len(html.encode('utf-8')) > MAX_HTML_BYTES:
        raise SongkickFeedError('Empty or oversized Songkick calendar.')
    parser = _CalendarHTML()
    try:
        parser.feed(html)
        parser.close()
        if parser._script is not None or not parser.scripts:
            raise SongkickFeedError('Incomplete Songkick structured data.')
        events = []
        for script in parser.scripts:
            for item in _nodes(json.loads(script)):
                if _schema_type(item.get('@type'), 'MusicEvent'):
                    event = _event(item, today)
                    if event is not None:
                        events.append(event)
        if not events:
            raise SongkickFeedError('No verified Ronnie Scott\'s events in the Songkick calendar.')
        next_urls = {_next_url(link, current) for link in parser.next_links}
        if len(next_urls) > 1:
            raise SongkickFeedError('Ambiguous Songkick pagination.')
        return events, next(iter(next_urls), None)
    except (json.JSONDecodeError, RecursionError) as error:
        raise SongkickFeedError('Malformed Songkick structured data.') from error


def fetch_songkick_ronnies(fetch, today):
    """Fetch a complete public calendar sequentially; fail without partial data.

    ``fetch(url)`` supplies the caller's ordinary bounded HTTP GET. HTTP failures
    (including403/429) are propagated as a feed error, with no retries/fallbacks.
    Cancelled/postponed records remain here for exact-URL tombstones upstream.
    """
    current = CALENDAR
    seen_pages = {1}
    events = {}
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(PAGE_DELAY)
        try:
            html = fetch(current)
        except Exception as error:
            code = getattr(error, 'code', None)
            message = f' (HTTP {code})' if isinstance(code, int) else ''
            raise SongkickFeedError('Songkick calendar fetch failed' + message + '.') from error
        records, following = parse_songkick_page(html, today, current)
        for record in records:
            previous = events.get(record['url'])
            if previous is not None and previous != record:
                raise SongkickFeedError('Conflicting Songkick concert records.')
            events[record['url']] = record
        if following is None:
            return list(events.values())
        number = int(urlsplit(following).query[5:])
        if number in seen_pages or number != page + 1:
            raise SongkickFeedError('Cyclic or incomplete Songkick pagination.')
        if page == MAX_PAGES:
            raise SongkickFeedError('Songkick calendar exceeds the bounded page limit.')
        seen_pages.add(number)
        current = following
    raise SongkickFeedError('Incomplete Songkick calendar.')
