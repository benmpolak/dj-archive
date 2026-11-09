"""Ronnie's refresh integration: synthetic sources, temporary outputs, no HTTP."""
import contextlib
from copy import deepcopy
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gigs_ronnies_integration', ROOT / 'gigs-fetch.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
import gigs_ronnies as backup

TODAY = date(2026, 11, 9)
VENUE_URL = 'https://www.ronniescotts.co.uk/find-a-show/original-band'
BACKUP_URL = 'https://www.songkick.com/concerts/123-original-band'


def event(**changes):
    return {'date': '2026-11-20', 'title': 'Original Band', 'venue': "Ronnie Scott's",
            'url': BACKUP_URL, 'names': ['Original Band'], 'lineup_verified': True,
            'source': 'RonnieSongkick', 'hint': 'gig', 'start': '19:30',
            'status': 'https://schema.org/EventScheduled', 'checked_at': str(TODAY), **changes}


def saved(**changes):
    return {'date': '2026-11-20', 'title': 'Original Band with Special Guest',
            'venue': "Ronnie Scott's", 'url': VENUE_URL, 'source': 'RonnieScotts',
            'how': 'lineup', 'score': 52, 'etype': 'gig', 'first_seen': '2026-10-22',
            'performers': ['Original Band', 'Shared Player'], 'artist': 'Original Band',
            'co': ['Shared Player'], **changes}


def calendar(following=None):
    item = {'@type': 'MusicEvent', 'name': "Original Band @ Ronnie Scott's Jazz Club",
            'url': BACKUP_URL, 'startDate': '2026-11-20T19:30:00',
            'eventStatus': 'https://schema.org/EventScheduled',
            'performer': [{'@type': 'MusicGroup', 'name': 'Original Band'}],
            'location': {'@type': 'Place', 'sameAs': 'https://www.ronniescotts.co.uk/',
                         'address': {'streetAddress': '47 Frith Street', 'postalCode': 'W1D 4HT',
                                     'addressLocality': 'London', 'addressCountry': 'UK'}}}
    return ('<script type="application/ld+json">' + json.dumps([item]) + '</script>' +
            (f'<a rel="next" href="{following}">Next</a>' if following else ''))


class RonnieRefreshIntegration(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(g, 'HERE', str(self.root)))
        self.stack.enter_context(patch.object(g, 'TODAY', TODAY))
        self.stack.enter_context(patch.object(g.urllib.request, 'urlopen',
                                             side_effect=AssertionError('Live HTTP is forbidden in this test')))
        self.stack.enter_context(patch.object(backup.time, 'sleep'))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.artists = {g.normalize(name): {'name': name, 'tracks': 20, 'plays': 100,
                        'p1': 0, 'p3': 0, 'min_da': 202001, 'max_da': 202608,
                        'the': False, 'crate': ''}
                        for name in ['Original Band', 'Other Band', 'Shared Player', 'Fresh Band']}
        self.stack.enter_context(patch.object(g, 'load_artists', return_value=self.artists))

    def fixture(self, rows=None):
        payload = {'generated': '2026-11-06', 'events': 1440,
                   'matching_rule': 'explicit-performers-v1',
                   'source_counts': {'RA': 1200, 'Blue Note': 14, "Ronnie Scott's": 0},
                   'carried_from': {"Ronnie Scott's": '2026-10-22', 'Blue Note': '2026-11-01'},
                   'extra_metadata': {'preserve': ['unrelated', 'values']},
                   'matches': rows if rows is not None else [saved()]}
        (self.root / 'gigs-data.json').write_text(json.dumps(payload))
        (self.root / 'gigs.html').write_text('old private output')
        (self.root / 'gigs-share.html').write_text('old public output')
        return deepcopy(payload)

    def read(self):
        return json.loads((self.root / 'gigs-data.json').read_text())

    def refresh(self, events, day=TODAY, source='RonnieSongkick'):
        with patch.object(g, 'TODAY', day), \
             patch.object(g, 'fetch_ronnies', return_value=g.RonnieEvents(events, source)):
            g.refresh_ronnies_only(self.artists, str(self.root / 'gigs.html'))
        return self.read()

    def scheduled(self, events, day=TODAY):
        ra = [event(date='2026-11-25', title=f'Club night {n}', venue=f'Club {n}',
                    url=f'https://ra.co/events/{n}', source='RA',
                    names=['Other Band'] if n == 0 else ['Uncollected act']) for n in range(120)]
        notes = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(g, 'TODAY', day))
            for name in dir(g):
                if not name.startswith('fetch_'):
                    continue
                result = ra if name == 'fetch_ra' else []
                if name == 'fetch_ronnies':
                    result = g.RonnieEvents(events, 'RonnieSongkick')
                elif name == 'fetch_bluenote':
                    result = [event(source='BlueNote', names=[], venue='Blue Note London')]
                stack.enter_context(patch.object(g, name, return_value=result))
            stack.enter_context(patch.object(g, 'render',
                side_effect=lambda matches, count, artists, note, *args, **kw: notes.append(note)))
            stack.enter_context(patch.object(sys, 'argv', ['gigs-fetch.py', '--out', str(self.root / 'gigs.html')]))
            g.main()
        return self.read(), notes

    def test_conflicting_backup_preserves_venue_title_date_performers_and_age(self):
        before = self.fixture()
        result = self.refresh([event(names=['Other Band'])])
        row = result['matches'][0]
        for key in ['title', 'date', 'performers', 'artist', 'co', 'source', 'url', 'first_seen']:
            self.assertEqual(row[key], before['matches'][0][key], key)
        self.assertEqual(row['retained_from'], '2026-10-22')
        self.assertNotIn('checked_at', row, 'Backup corroboration cannot freshen venue line-up evidence')
        self.assertEqual(row['listing_check'], {'source': 'Songkick', 'date': str(TODAY), 'url': BACKUP_URL})
        self.assertEqual(result['carried_from']["Ronnie Scott's"], '2026-10-22')
        for page in ['gigs.html', 'gigs-share.html']:
            text = (self.root / page).read_text()
            self.assertIn('Venue line-up 22 Oct', text)
            self.assertIn('date also listed on Songkick 9 Nov', text)
            self.assertNotIn('Venue listing · checked 9 Nov', text)

    def test_missing_backup_event_keeps_prior_venue_and_backup_evidence_dates(self):
        old_backup = saved(title='Fresh Band', source='RonnieSongkick', artist='Fresh Band',
                           performers=['Fresh Band'], co=[], date='2026-11-22',
                           url='https://www.songkick.com/concerts/456-fresh-band', checked_at='2026-11-07')
        self.fixture([saved(checked_at='2026-10-22'), old_backup])
        result = self.refresh([event(date='2026-11-23', title='Other Band', names=['Other Band'],
                                     url='https://www.songkick.com/concerts/789-other-band')])
        by_url = {row['url']: row for row in result['matches']}
        self.assertIn(VENUE_URL, by_url)
        self.assertIn(old_backup['url'], by_url)
        self.assertEqual(by_url[old_backup['url']]['checked_at'], '2026-11-07')
        self.assertEqual(by_url[VENUE_URL]['checked_at'], '2026-10-22')
        self.assertNotIn('listing_check', by_url[VENUE_URL])

    def test_shared_backing_player_does_not_merge_different_bands(self):
        self.fixture()
        result = self.refresh([event(title='Other Band', names=['Other Band', 'Shared Player'],
                                     url='https://www.songkick.com/concerts/789-other-band')])
        self.assertEqual(len(result['matches']), 2)
        self.assertEqual({row['title'] for row in result['matches']},
                         {'Original Band with Special Guest', 'Other Band'})
        self.assertNotIn('listing_check', next(row for row in result['matches'] if row['url'] == VENUE_URL))

    def test_explicit_cancellation_removes_retained_show_and_cannot_return_next_run(self):
        self.fixture([saved(), saved(title='Fresh Band', artist='Fresh Band', performers=['Fresh Band'],
                                    co=[], date='2026-11-22', url=VENUE_URL + '-fresh')])
        cancelled = event(status='https://schema.org/EventCancelled')
        first = self.refresh([cancelled])
        self.assertEqual([row['artist'] for row in first['matches']], ['Fresh Band'])
        second = self.refresh([cancelled], day=date(2026, 11, 10))
        self.assertEqual([row['artist'] for row in second['matches']], ['Fresh Band'])

    def test_same_backup_url_cancellation_or_reschedule_retires_old_date(self):
        old = saved(title='Original Band', source='RonnieSongkick', url=BACKUP_URL,
                    performers=['Original Band'], co=[], checked_at='2026-11-07')
        for status in ['EventCancelled', 'EventPostponed', 'EventRescheduled']:
            with self.subTest(status=status):
                self.fixture([old])
                result = self.refresh([event(date='2026-12-02', status='https://schema.org/' + status)])
                self.assertNotIn('2026-11-20', [row['date'] for row in result['matches']])
                self.assertEqual([row['date'] for row in result['matches']],
                                 ['2026-12-02'] if status == 'EventRescheduled' else [])

    def test_duplicate_links_do_not_duplicate_dates_but_distinct_dates_remain(self):
        self.fixture([])
        first = event()
        another_link = event(url='https://www.songkick.com/concerts/124-original-band')
        next_night = event(date='2026-11-21', url='https://www.songkick.com/concerts/125-original-band')
        result = self.refresh([first, deepcopy(first), another_link, next_night])
        self.assertEqual(sorted(row['date'] for row in result['matches']), ['2026-11-20', '2026-11-21'])
        self.assertTrue(all(row['checked_at'] == str(TODAY) for row in result['matches']))

    def test_duplicate_title_date_keeps_each_explicit_coartist_evidenced_after_reload(self):
        self.fixture([])
        result = self.refresh([event(names=['Original Band']),
                               event(url='https://www.songkick.com/concerts/124-original-band',
                                     names=['Shared Player'])])
        self.assertEqual(len(result['matches']), 1)
        row = result['matches'][0]
        self.assertEqual(set(row['performers']), {'Original Band', 'Shared Player'})
        hydrated = g.hydrate_saved_matches(result, self.artists)
        self.assertEqual({hydrated[0]['artist']['name']} | {artist['name'] for artist in hydrated[0]['co']},
                         {'Original Band', 'Shared Player'})

    def test_targeted_refresh_preserves_other_raw_rows_even_past_and_top_level_metadata(self):
        other_rows = [saved(source='RA', venue='Elsewhere', date=day,
                            url=f'https://ra.co/events/{n}', private_extra={'unmodified': n})
                      for n, day in enumerate(['2025-01-01', '2026-11-24'])]
        before = self.fixture(other_rows + [saved()])
        result = self.refresh([event()])
        self.assertEqual(result['matches'][:2], other_rows)
        for key in ['generated', 'events', 'matching_rule', 'extra_metadata']:
            self.assertEqual(result[key], before[key], key)
        self.assertEqual(result['carried_from']['Blue Note'], before['carried_from']['Blue Note'])
        for source in ['RA', 'Blue Note']:
            self.assertEqual(result['source_counts'][source], before['source_counts'][source])
        self.assertEqual(result['source_counts']["Ronnie Scott's"], 0)
        self.assertEqual(result['source_counts']["Songkick (Ronnie Scott's)"], 1)

    def test_partial_official_detail_failure_discards_partial_results_and_uses_public_backup(self):
        base = 'https://www.ronniescotts.co.uk/find-a-show'
        listings = ''.join(f'<div class="listing"><h2 class="listing__title">{name}</h2>'
                           f'<button id="id-{number}">Book</button>'
                           f'<a href="{base}/{slug}">Details</a></div>'
                           for name, number, slug in [('Original Band', 1234, 'original'), ('Other Band', 5678, 'other')])
        drawer = ('<div class="performance-option has-standard"><h2 class="performance-option__heading">'
                  'Friday 20th November, 2026</h2><h3>Show Starts</h3><p>19:00</p></div>')
        requests = []
        def fetch(url, **kwargs):
            requests.append(url)
            if url == base:
                return listings
            if url == base + '/original':
                return '<h3>Line-up</h3><p>Original Band – guitar</p></div>'
            if url == base + '?id=1234&ajax=1':
                return drawer
            if url == base + '/other':
                raise HTTPError(url, 403, 'Forbidden', {}, None)
            if url == backup.CALENDAR:
                return calendar()
            raise AssertionError('Unexpected source request: ' + url)
        with patch.object(g, 'http_get', side_effect=fetch):
            results = g.fetch_ronnies()
        self.assertEqual(results.source, 'RonnieSongkick')
        self.assertEqual([row['url'] for row in results], [BACKUP_URL])
        self.assertEqual(requests, [base, base + '/original', base + '?id=1234&ajax=1',
                                    base + '/other', backup.CALENDAR])

    def test_failed_or_partial_backup_leaves_every_output_byte_unchanged(self):
        for partial in [False, True]:
            with self.subTest(partial=partial):
                self.fixture()
                paths = [self.root / name for name in ['gigs-data.json', 'gigs.html', 'gigs-share.html']]
                before = {path: path.read_bytes() for path in paths}
                requests = []
                def fetch(url, **kwargs):
                    requests.append(url)
                    if partial and url == backup.CALENDAR:
                        return calendar(backup.CALENDAR + '?page=2')
                    raise HTTPError(url, 403, 'Forbidden', {}, None)
                with patch.object(g, 'fetch_ronnies_official', side_effect=OSError('Official feed unavailable')), \
                     patch.object(g, 'http_get', side_effect=fetch), self.assertRaises(backup.SongkickFeedError):
                    g.refresh_ronnies_only(self.artists, str(self.root / 'gigs.html'))
                self.assertEqual({path: path.read_bytes() for path in paths}, before)
                self.assertEqual(requests, [backup.CALENDAR] + ([backup.CALENDAR + '?page=2'] if partial else []))

    def test_scheduled_fallback_preserves_saved_provenance_across_next_run(self):
        self.fixture()
        first, _ = self.scheduled([event(names=['Other Band']), event(date='2026-11-22', title='Fresh Band',
                       names=['Fresh Band'], url='https://www.songkick.com/concerts/456-fresh-band')])
        first_venue = next(row for row in first['matches'] if row['source'] == 'RonnieScotts')
        self.assertEqual(first_venue['retained_from'], '2026-10-22')
        self.assertEqual(first_venue['listing_check']['date'], str(TODAY))
        second, notes = self.scheduled([event(date='2026-11-23', title='Other Band', names=['Other Band'],
                       url='https://www.songkick.com/concerts/789-other-band', checked_at='2026-11-10')],
                       day=date(2026, 11, 10))
        second_venue = next(row for row in second['matches'] if row['source'] == 'RonnieScotts')
        self.assertEqual(second_venue, first_venue)
        retained_backup = next(row for row in second['matches'] if row['artist'] == 'Fresh Band')
        self.assertEqual(retained_backup['checked_at'], str(TODAY))
        self.assertEqual(second['carried_from']["Ronnie Scott's"], '2026-10-22')
        self.assertIn('retained from 22 Oct', notes[0])
        self.assertIn('Songkick listings checked 10 Nov', notes[0])
        self.assertEqual(second['source_counts']["Ronnie Scott's"], 0)
        self.assertEqual(second['source_counts']["Songkick (Ronnie Scott's)"], 1)

    def test_scheduled_cancellation_clears_obsolete_venue_carry_warning(self):
        self.fixture()
        result, notes = self.scheduled([event(status='https://schema.org/EventCancelled')])
        self.assertFalse(any(row['source'] == 'RonnieScotts' for row in result['matches']))
        self.assertNotIn("Ronnie Scott's", result.get('carried_from', {}))
        self.assertNotIn('retained from 22 Oct', notes[0])
        self.assertNotIn('shows are from its 22 Oct', notes[0])


if __name__ == '__main__':
    unittest.main()
