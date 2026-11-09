"""Presentation grouping must preserve date identities, source labels and evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gig_presentation', ROOT / 'gigs-fetch.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def item(day, artist='Fixture Artist', venue='Fixture Venue', tracks=3, **changes):
    value = {'date': day, 'title': artist+' live', 'venue': venue,
             'url': 'https://example.test/'+day, 'source': 'RA', 'how': 'lineup', 'score': 20,
             'etype': 'gig', 'first_seen': '2026-11-08', 'all_names': [artist, 'Guest Performer'],
             'co': [], 'artist': {'name': artist, 'tracks': tracks, 'plays': 1, 'p1': 1,
                                  'crate': 'Uncategorized', 'max_da': 202611}}
    value.update(changes)
    return value


class GigPresentationTests(unittest.TestCase):
    def test_consecutive_dates_group_without_mutating_or_losing_source_rows(self):
        rows = [item('2026-11-30', title='First line-up'), item('2026-12-01', title='Different line-up'),
                item('2026-12-03'), item('2026-12-02', venue='Other venue')]
        before = copy.deepcopy(rows)
        groups = g.group_gig_dates(rows)
        self.assertEqual([[r['date'] for r in group] for group in groups],
                         [['2026-11-30', '2026-12-01'], ['2026-12-02'], ['2026-12-03']])
        self.assertEqual(rows, before)
        self.assertCountEqual([id(r) for group in groups for r in group], [id(r) for r in rows])
        self.assertEqual(groups[0][1]['title'], 'Different line-up')

    def test_nonconsecutive_and_same_date_showings_stay_distinct(self):
        rows = [item('2026-11-11'), item('2026-11-11', title='Late show'), item('2026-11-13')]
        self.assertEqual(len(g.group_gig_dates(rows)), 3)

    def test_same_venue_different_artist_is_not_combined(self):
        self.assertEqual(len(g.group_gig_dates([item('2026-11-11'), item('2026-11-12', artist='Someone Else')])), 2)

    def render(self, rows, public=False):
        with tempfile.TemporaryDirectory() as directory, patch.object(g, 'TODAY', date(2026, 11, 9)):
            target = Path(directory) / 'gigs.html'
            g.render(rows, 200, 50, 'Original source warning', str(target), public=public, generated='2026-11-06')
            return target.read_text()

    def test_group_retains_each_date_key_ticket_title_and_source_check(self):
        rows = [item('2026-11-11', source='RonnieScotts', title='Original duo', retained_from='2026-10-22',
                     listing_check={'source':'Songkick','date':'2026-11-09','url':'https://example.test/backup'}),
                item('2026-11-12', source='RonnieSongkick', title='Different band', checked_at='2026-11-09')]
        for public in [False, True]:
            html = self.render(rows, public)
            self.assertEqual(html.count('class="row gig-row"'), 1)
            for row in rows:
                self.assertIn('data-key="'+row['date']+'|Fixture Artist|Fixture Venue"', html)
                self.assertIn(row['url'], html)
                self.assertIn(row['title'], html)
            self.assertIn('Listed performers: Fixture Artist, Guest Performer', html)
            self.assertIn('Venue line-up 22 Oct · date also listed on Songkick 9 Nov', html)
            self.assertIn('Songkick listing · checked 9 Nov', html)
            self.assertEqual(html.count('class="source-check"'), 2)

    def test_weak_match_is_kept_in_payload_and_full_count(self):
        html = self.render([item('2026-11-11', tracks=2)])
        self.assertIn('data-tracks="2"', html)
        self.assertIn('Show all 1 shows', html)
        self.assertIn('gr_saved_gigs_v1', html)
        self.assertIn('data-key="2026-11-11|Fixture Artist|Fixture Venue"', html)

    def test_uncategorized_is_not_a_visible_crate_or_evidence_label(self):
        html = self.render([item('2026-11-11')])
        self.assertNotIn('data-c="Uncategorized"', html)
        self.assertNotIn('· Uncategorized', html)
        self.assertNotIn('1 plays', html)
        self.assertIn('3 archive tracks · 1 play', html)
        self.assertNotIn(' · 1 play', self.render([item('2026-11-11')], public=True))

    def test_all_filters_start_behind_drawer_with_new_shared_navigation(self):
        html = self.render([item('2026-11-11')])
        self.assertIn('id="filter-more" hidden', html)
        self.assertIn('aria-controls="filter-more"', html)
        self.assertIn('https://the-dial-listen.benmpolak.workers.dev/', html)
        self.assertNotIn('Top picks', html)
        self.assertIn('updated 6 Nov 2026', html)
        self.assertIn('Original source warning', html)


if __name__ == '__main__':
    unittest.main()
