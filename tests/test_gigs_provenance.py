"""No-fetch rebuilds must preserve the age of carried venue listings."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


g = module('gigs_provenance', 'gigs-fetch.py')
builder = module('gigs_build_provenance', 'build.py')


class SavedListingProvenance(unittest.TestCase):
    def fixture(self, root):
        track = {'a': 'Che Wax', 't': 'A record', 'al': 'An album', 'sid': '1' * 22,
                 'da': 202601, 'pc': 100, 'c': ['House']}
        payload = {
            'generated': '2026-11-06', 'events': 120, 'matching_rule': 'explicit-performers-v1',
            'source_counts': {'RA': 120, "Ronnie Scott's": 0},
            'carried_from': {"Ronnie Scott's": '2026-10-22'},
            'matches': [{'date': str(g.TODAY + g.timedelta(days=7)), 'title': 'Che Wax Live',
                         'venue': "Ronnie Scott's", 'url': 'https://www.ronniescotts.co.uk/find-a-show/fixture',
                         'source': 'RonnieScotts', 'how': 'lineup', 'score': 20, 'etype': 'gig',
                         'first_seen': '2026-10-22', 'performers': ['Che Wax'], 'artist': 'Che Wax', 'co': []}]
        }
        (root / 'gigs-data.json').write_text(json.dumps(payload))
        (root / 'index.html').write_text('const DATA=' + json.dumps([track]) + ';\n'
            '<script id="dealer-js"></script>\n<script id="guest-js"></script>\n<style id="design-pass"></style>')
        for name in ['dealer.js', 'guest.js', 'design-pass.css']:
            (root / name).write_text('')
        (root / 'guest-art.json').write_text('{}')
        # The real build imports its parser from its own root, so copy only code.
        (root / 'gigs-fetch.py').write_text((ROOT / 'gigs-fetch.py').read_text())
        return payload

    def assert_preserved(self, root, before):
        after = json.loads((root / 'gigs-data.json').read_text())
        for field in ['generated', 'events', 'source_counts', 'carried_from']:
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after['matches'][0]['first_seen'], '2026-10-22')
        for page in ['gigs.html', 'gigs-share.html']:
            html = (root / page).read_text()
            self.assertIn("Ronnie Scott's shows are from its 22 Oct listings", html)
            self.assertIn('its site is blocking the refresh', html)
            self.assertIn('updated 6 Nov 2026', html)

    def test_render_existing_keeps_source_counts_date_and_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self.fixture(root)
            with patch.object(g, 'HERE', str(root)), \
                 patch.object(g, 'http_get', side_effect=AssertionError('A no-fetch render must not fetch')), \
                 patch.object(g.urllib.request, 'urlopen', side_effect=AssertionError('No network permitted')), \
                 patch.object(sys, 'argv', ['gigs-fetch.py', '--render-existing', '--out', str(root / 'gigs.html')]), \
                 contextlib.redirect_stdout(io.StringIO()):
                g.main()
            self.assert_preserved(root, before)

    def test_full_build_keeps_provenance_and_unchanged_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self.fixture(root)
            data_before = (root / 'index.html').read_text().split(';', 1)[0]
            with patch.object(builder, 'ROOT', root), \
                 patch.object(g.urllib.request, 'urlopen', side_effect=AssertionError('No network permitted')), \
                 contextlib.redirect_stdout(io.StringIO()):
                builder.main()
            self.assert_preserved(root, before)
            self.assertEqual((root / 'index.html').read_text().split(';', 1)[0], data_before)
            self.assertEqual(json.loads((root / 'music/manifest.json').read_text())['trackCount'], 1)

    def test_saved_only_note_keeps_original_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.fixture(root)
            payload['source_counts'] = {}
            (root / 'gigs-data.json').write_text(json.dumps(payload))
            with patch.object(g, 'HERE', str(root)):
                self.assertIn("Ronnie Scott's shows are from its 22 Oct listings", g.existing_sources_note())

    def test_explicit_fresh_save_can_clear_old_carry_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            with patch.object(g, 'HERE', str(root)):
                g.save_matches([], '2026-11-09', 1, {"Ronnie Scott's": 1}, {})
                self.assertNotIn('carried_from', json.loads((root / 'gigs-data.json').read_text()))
                self.assertNotIn('blocking the refresh', g.existing_sources_note())


if __name__ == '__main__':
    unittest.main()
