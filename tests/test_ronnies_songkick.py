"""Synthetic public schema fixtures; no live HTTP or user data writes."""
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gigs_ronnies', ROOT / 'gigs_ronnies.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
TODAY = date(2026, 11, 9)


def event(number=123, **changes):
    item = {'@type': 'MusicEvent', 'name': "Billed band @ Ronnie Scott's Jazz Club",
            'url': f'https://www.songkick.com/concerts/{number}-billed-band?utm_source=microformat',
            'startDate': '2026-11-11T19:30:00', 'eventStatus': 'https://schema.org/EventScheduled',
            'location': {'@type': 'Place', 'name': "Ronnie Scott's Jazz Club",
                         'sameAs': 'http://www.ronniescotts.co.uk/',
                         'address': {'addressLocality': 'London', 'streetAddress': '47 Frith Street, Soho',
                                     'postalCode': 'W1D 4HT', 'addressCountry': 'UK'}},
            'performer': [{'@type': 'MusicGroup', 'name': 'Billed band'},
                          {'@type': 'Person', 'name': 'Explicit guest'}]}
    return item | changes


def page(data, following=None):
    return ('<html><script type="application/ld+json">' + json.dumps(data) + '</script>' +
            (f'<a rel="next" href="{following}">Next</a>' if following is not None else '') + '</html>')


class RonnieSongkickTests(unittest.TestCase):
    def setUp(self):
        self.sleep = patch.object(g.time, 'sleep')
        self.sleep_mock = self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def parse(self, item):
        return g.parse_songkick_page(page([item]), TODAY)[0][0]

    def test_explicit_performers_and_canonical_identity_survive_without_alias_inference(self):
        item = event(performer=[{'@type': 'MusicGroup', 'name': 'Sumudu'},
                                {'@type': 'Person', 'name': 'Sumudu Jayatilaka'},
                                {'@type': 'MusicGroup', 'name': 'Artist & Friends'}])
        result = self.parse(item)
        self.assertEqual(result['names'], ['Sumudu', 'Sumudu Jayatilaka', 'Artist & Friends'])
        self.assertEqual(result['title'], 'Billed band')
        self.assertEqual(result['url'], 'https://www.songkick.com/concerts/123-billed-band')
        self.assertEqual((result['venue'], result['source']), ("Ronnie Scott's", 'RonnieSongkick'))
        self.assertTrue(result['lineup_verified'])
        self.assertEqual(result['checked_at'], '2026-11-09')
        self.assertEqual((result['date'], result['start']), ('2026-11-11', '19:30'))
        other_title = "Title mentioning Ronnie Scott's Jazz Club, with a real bill"
        self.assertEqual(self.parse(event(name=other_title))['title'], other_title)

    def test_only_music_events_and_explicit_supported_performer_types_qualify(self):
        for item in [event(**{'@type': 'Event'}), event(performer=None),
                     event(performer=[]), event(performer=['Billed band']),
                     event(performer={'@type': 'Organization', 'name': 'Billed band'}),
                     event(performer={'@type': 'Person', 'name': ''})]:
            with self.subTest(item=item), self.assertRaises(g.SongkickFeedError):
                self.parse(item)
        result = self.parse(event(name='Famous title-only artist', performer={'@type': 'Person', 'name': 'Actual performer'}))
        self.assertEqual(result['names'], ['Actual performer'])

    def test_arrays_graphs_and_multiple_schema_scripts_are_supported(self):
        data = [{'@type': 'Organization', 'name': 'Not an event'}, {'@graph': [event(), {'@graph': [event(124)]}]}]
        records, following = g.parse_songkick_page(page(data), TODAY)
        self.assertEqual(len(records), 2)
        self.assertIsNone(following)
        html = page(event()) + page([event(124)])
        self.assertEqual(len(g.parse_songkick_page(html, TODAY)[0]), 2)

    def test_exact_venue_website_london_street_and_postcode_are_all_required(self):
        valid = event()
        valid['location']['address'].update(streetAddress=' 47 FRITH St., Soho ', postalCode='w1d4ht', addressLocality=' london ')
        self.assertEqual(self.parse(valid)['venue'], "Ronnie Scott's")
        alterations = [lambda x: x['location'].update(sameAs='https://ronniescotts.co.uk.evil.invalid/'),
                       lambda x: x['location'].update(sameAs='https://www.ronniescotts.co.uk@evil.invalid/'),
                       lambda x: x['location']['address'].update(streetAddress='147 Frith Street'),
                       lambda x: x['location']['address'].update(addressLocality='Birmingham'),
                       lambda x: x['location']['address'].update(postalCode='W1D 4HA'),
                       lambda x: x['location']['address'].update(addressCountry='US')]
        for alter in alterations:
            wrong = event(); alter(wrong)
            with self.subTest(wrong=wrong), self.assertRaises(g.SongkickFeedError):
                self.parse(wrong)
        wrong = event(124); wrong['location']['address']['addressLocality'] = 'Birmingham'
        records, _ = g.parse_songkick_page(page([event(), wrong]), TODAY)
        self.assertEqual([r['url'] for r in records], ['https://www.songkick.com/concerts/123-billed-band'])

    def test_dates_are_exact_and_offset_times_convert_to_london_without_invented_end(self):
        day_only = self.parse(event(startDate='2027-01-02', endDate='2099-01-01'))
        self.assertEqual(day_only['date'], '2027-01-02')
        self.assertNotIn('start', day_only)
        self.assertNotIn('end', day_only)
        for stamp, expected in [('2026-07-01T23:30:00Z', ('2026-07-02', '00:30')),
                                ('2026-11-11T00:30:00+02:00', ('2026-11-10', '22:30')),
                                ('2026-07-01T19:30:00+0100', ('2026-07-01', '19:30'))]:
            result = self.parse(event(startDate=stamp))
            self.assertEqual((result['date'], result['start']), expected)
        for invalid in ['11 November', '2026-02-30', '2026-11-11T25:30:00', '2026-11-11 19:30', '2026-11-11T19:30:00+99:00', None]:
            with self.subTest(invalid=invalid), self.assertRaises(g.SongkickFeedError):
                self.parse(event(startDate=invalid))

    def test_cancelled_and_postponed_records_remain_for_exact_url_tombstones(self):
        for status in ['EventCancelled', 'EventPostponed', 'EventRescheduled']:
            result = self.parse(event(eventStatus='https://schema.org/' + status))
            self.assertEqual(result['status'], 'https://schema.org/' + status)
            self.assertEqual(result['url'], 'https://www.songkick.com/concerts/123-billed-band')
        for invalid in [None, 'cancelled', 'https://evil.invalid/EventScheduled']:
            with self.assertRaises(g.SongkickFeedError):
                self.parse(event(eventStatus=invalid))

    def test_concert_urls_cannot_point_to_other_hosts_routes_or_embedded_credentials(self):
        for url in ['http://www.songkick.com/concerts/123-band', 'https://evil.invalid/concerts/123-band',
                    'https://www.songkick.com@evil.invalid/concerts/123-band',
                    'https://www.songkick.com/concerts/123-band/extra', 'https://www.songkick.com/concerts/%2e%2e-band',
                    'https://www.songkick.com:443/concerts/123-band', None]:
            with self.subTest(url=url), self.assertRaises(g.SongkickFeedError):
                self.parse(event(url=url))

    def test_pagination_is_observed_sequential_paced_and_deduplicates_identical_concerts(self):
        next_url = g.CALENDAR + '?page=2'
        first = page([event()], next_url) + f'<link rel="next" href="{g.CALENDAR_PATH}?page=2">'
        fetch = Mock(side_effect=[first, page([event(), event(124)])])
        events = g.fetch_songkick_ronnies(fetch, TODAY)
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [g.CALENDAR, next_url])
        self.assertEqual(len(events), 2)
        self.sleep_mock.assert_called_once_with(g.PAGE_DELAY)
        with self.assertRaisesRegex(g.SongkickFeedError, 'Conflicting'):
            g.fetch_songkick_ronnies(Mock(return_value=page([event(), event(startDate='2026-11-12')])), TODAY)

    def test_unsafe_ambiguous_cycle_and_skipped_page_links_fail_without_following(self):
        for link in ['https://evil.invalid' + g.CALENDAR_PATH + '?page=2',
                     'http://www.songkick.com' + g.CALENDAR_PATH + '?page=2',
                     '/venues/999-other/calendar?page=2', g.CALENDAR_PATH + '?page=2&redirect=elsewhere',
                     g.CALENDAR_PATH + '?page=2#part', g.CALENDAR_PATH + '?page=0',
                     g.CALENDAR_PATH + '?page=1', g.CALENDAR_PATH + '?page=3',
                     'https://www.songkick.com@evil.invalid' + g.CALENDAR_PATH + '?page=2']:
            fetch = Mock(return_value=page([event()], link))
            with self.subTest(link=link), self.assertRaises(g.SongkickFeedError):
                g.fetch_songkick_ronnies(fetch, TODAY)
            fetch.assert_called_once_with(g.CALENDAR)
        html = page([event()], g.CALENDAR + '?page=2') + f'<a rel="next" href="{g.CALENDAR}?page=3">Next</a>'
        with self.assertRaises(g.SongkickFeedError):
            g.fetch_songkick_ronnies(Mock(return_value=html), TODAY)
        fetch = Mock(side_effect=[page([event()], '?page=2'), page([event(124)], '?page=1')])
        with self.assertRaisesRegex(g.SongkickFeedError, 'Cyclic'):
            g.fetch_songkick_ronnies(fetch, TODAY)
        self.assertEqual(fetch.call_count, 2)

    def test_partial_http_failure_and_malformed_or_empty_feeds_never_return_partial_data(self):
        for code in [403, 429, 503]:
            fetch = Mock(side_effect=[page([event()], '?page=2'), HTTPError(g.CALENDAR, code, 'Blocked', {}, None)])
            with self.subTest(code=code), self.assertRaisesRegex(g.SongkickFeedError, str(code)):
                g.fetch_songkick_ronnies(fetch, TODAY)
            self.assertEqual(fetch.call_count, 2)
        for bad in ['', '<html>Access denied</html>', page([]), '<script type="application/ld+json">{broken}</script>',
                    '<script type="application/ld+json">[]', page({'@graph': 'invalid'})]:
            fetch = Mock(side_effect=[page([event()], '?page=2'), bad])
            with self.subTest(bad=bad), self.assertRaises(g.SongkickFeedError):
                g.fetch_songkick_ronnies(fetch, TODAY)
            self.assertEqual(fetch.call_count, 2)

    def test_page_limit_fails_closed_instead_of_publishing_first_six_pages(self):
        fetch = Mock(side_effect=[page([event(123 + n)], '?page=' + str(n + 2)) for n in range(6)])
        with self.assertRaisesRegex(g.SongkickFeedError, 'page limit'):
            g.fetch_songkick_ronnies(fetch, TODAY)
        self.assertEqual(fetch.call_count, 6)
        self.assertEqual(self.sleep_mock.call_count, 5)


if __name__ == '__main__':
    unittest.main()
