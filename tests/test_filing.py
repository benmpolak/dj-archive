import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('filing', ROOT / 'filing.py')
filing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filing)


def sid(n):
    return ('%022d' % n)


def track(n, artist, title, da, tags=None, crates=None, genres=''):
    return {'sid': sid(n), 'a': artist, 't': title, 'da': da, 'tags': tags or [], 'c': crates or ['Uncategorized'], 'g': genres}


class FilingTests(unittest.TestCase):
    def setUp(self):
        # Twenty tracks Ben filed himself, all in one genre playlist, two artists.
        self.data = [track(i, 'Filed Artist %d' % (i % 2), 'Song %d' % i, 202301, ['Soul & Disco'], ['Soul & R&B'])
                     for i in range(20)]
        self.ledger = {'Soul & Disco revival': {sid(i): '2023-01' for i in range(20)}, 'November 2026': {}}

    def add(self, n, artist, title, da=202611, playlists=(), **kw):
        self.data.append(track(n, artist, title, da, **kw))
        for name in playlists:
            self.ledger.setdefault(name, {})[sid(n)] = '2026-11'
        return len(self.data) - 1

    def run_filing(self, auto=None):
        auto = {} if auto is None else auto
        changes = filing.propose(self.data, self.ledger, auto)
        filing.apply(self.data, changes, auto, '2026-11-20')
        return changes, auto

    def test_genre_playlist_files_tags_and_crate(self):
        i = self.add(100, 'Brand New Act', 'First Single', playlists=['Soul & Disco revival', 'November 2026'])
        changes, auto = self.run_filing()
        self.assertEqual([c['i'] for c in changes], [i])
        self.assertEqual(self.data[i]['tags'], ['Soul & Disco'])
        self.assertEqual(self.data[i]['c'], ['Soul & R&B'])
        self.assertEqual(auto[sid(100)], {'tags': ['Soul & Disco'], 'c': ['Soul & R&B'], 'on': '2026-11-20'})

    def test_monthly_playlist_alone_files_nothing(self):
        for i in range(20):  # make the monthly playlist look consistent; it must still be ignored
            self.ledger['November 2026'][sid(i)] = '2026-11'
        i = self.add(101, 'Unknown Act', 'Mystery', playlists=['November 2026'])
        self.assertEqual(self.run_filing()[0], [])
        self.assertEqual(self.data[i]['tags'], [])
        self.assertEqual(self.data[i]['c'], ['Uncategorized'])

    def test_same_artist_files_a_new_track(self):
        i = self.add(102, 'Filed Artist 1', 'Another One', playlists=['November 2026'])
        self.run_filing()
        self.assertEqual(self.data[i]['tags'], ['Soul & Disco'])

    def test_remixer_alone_is_not_enough(self):
        i = self.add(103, 'Unknown Act', 'Tune - Filed Artist 1 Remix', playlists=['November 2026'])
        self.assertEqual(self.run_filing()[0], [])
        self.assertEqual(self.data[i]['tags'], [])

    def test_only_recent_and_only_empty_fields(self):
        old = self.add(104, 'Filed Artist 1', 'Old And Bare', da=202001)
        kept = self.add(105, 'Filed Artist 1', 'Already Filed', tags=['New Jazz'], crates=['Jazz'])
        half = self.add(106, 'Filed Artist 1', 'Has A Crate', crates=['House'])
        before = copy.deepcopy(self.data)
        self.run_filing()
        self.assertEqual(self.data[old], before[old])
        self.assertEqual(self.data[kept], before[kept])
        self.assertEqual(self.data[half]['c'], ['House'])
        self.assertEqual(self.data[half]['tags'], ['Soul & Disco'])
        for i, row in enumerate(before[:20]):
            self.assertEqual(self.data[i], row)

    def test_second_run_changes_nothing_and_auto_filed_is_not_evidence(self):
        a = self.add(107, 'Fresh Act', 'One', playlists=['Soul & Disco revival'])
        _, auto = self.run_filing()
        self.assertEqual(self.data[a]['tags'], ['Soul & Disco'])
        self.assertEqual(filing.propose(self.data, self.ledger, auto), [])
        # Fresh Act's only filed track was filed by this module, so it cannot file their next one.
        self.add(108, 'Fresh Act', 'Two', playlists=['November 2026'])
        self.add(109, 'Fresh Act', 'Three', playlists=['November 2026'])
        self.data[-1]['tags'], self.data[-1]['c'] = ['Soul & Disco'], ['Soul & R&B']
        auto[sid(109)] = {'tags': ['Soul & Disco'], 'c': ['Soul & R&B'], 'on': '2026-11-20'}
        self.assertEqual(filing.propose(self.data, self.ledger, auto), [])

    def test_refuses_to_overwrite(self):
        i = self.add(110, 'Brand New Act', 'First Single', playlists=['Soul & Disco revival'])
        changes = filing.propose(self.data, self.ledger, {})
        self.data[i]['tags'] = ['Hand Filed']
        with self.assertRaises(ValueError):
            filing.apply(self.data, changes, {}, '2026-11-20')


if __name__ == '__main__':
    unittest.main()
