import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch, call
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spotify_sync', ROOT / 'spotify_sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SpotifySyncTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(sync.time, 'sleep')
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    @staticmethod
    def page(offset, total, items=None):
        return {'total': total, 'offset': offset, 'limit': 50,
                'items': list(range(offset, min(offset + 50, total))) if items is None else items,
                'next': sync.API + 'test?limit=50&offset=' + str(offset + 50) if offset + 50 < total else None}

    @staticmethod
    def offset(url):
        return int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('offset', ['0'])[0])

    def test_all_pages_including_past_100(self):
        self.assertEqual(sync.pages(lambda url: self.page(self.offset(url), 125),
                                    sync.API+'test?limit=50'), list(range(125)))
        self.sleep.assert_not_called()

    def test_empty_inventory_pages_are_retried_in_place_without_losing_entries(self):
        attempts = {}; offsets = []
        def get(url):
            offset = self.offset(url); offsets.append(offset)
            attempts[offset] = attempts.get(offset, 0) + 1
            empty = offset in (0, 300, 350, 400) and attempts[offset] == 1
            return self.page(offset, 507, [] if empty else None)
        self.assertEqual(sync.pages(get, sync.API+'test?limit=50'), list(range(507)))
        self.assertEqual(offsets, [0, 0, 50, 100, 150, 200, 250, 300, 300, 350, 350, 400, 400, 450, 500])
        self.assertEqual(self.sleep.call_args_list, [call(2)] * 4)

    def test_short_middle_and_final_track_pages_recover_without_duplicate_tracks(self):
        attempts = {}
        def get(url):
            offset = self.offset(url); attempts[offset] = attempts.get(offset, 0) + 1
            page = self.page(offset, 107)
            if offset in (50, 100) and attempts[offset] == 1:
                page['items'] = page['items'][:-1]
            return page
        self.assertEqual(sync.pages(get, sync.API+'test?limit=50'), list(range(107)))
        self.assertEqual(attempts, {0: 1, 50: 2, 100: 2})

    def test_permanently_empty_page_stops_after_three_attempts(self):
        calls = []
        def get(url):
            calls.append(url); return self.page(0, 507, [])
        with self.assertRaisesRegex(sync.SyncError, 'Inventory: incomplete page at offset 0'):
            sync.pages(get, sync.API+'test?limit=50', 'Inventory')
        self.assertEqual(calls, [sync.API+'test?limit=50'] * 3)
        self.assertEqual(self.sleep.call_args_list, [call(2), call(4)])

    def test_total_change_during_retry_or_between_pages_stops(self):
        for first in (self.page(0, 100, []), self.page(0, 100)):
            responses = iter([first, self.page(0 if not first['items'] else 50, 101)])
            with self.assertRaisesRegex(sync.SyncError, 'changed during reading'):
                sync.pages(lambda _: next(responses), sync.API+'test?limit=50')

    def test_missing_skipped_repeated_and_foreign_next_pages_stop(self):
        for next_url in (None, sync.API+'test?limit=50&offset=100',
                         sync.API+'test?limit=50', 'https://example.com/steal'):
            first = self.page(0, 100); first['next'] = next_url; calls = []
            def get(url):
                calls.append(url); return first
            with self.assertRaises(sync.SyncError):
                sync.pages(get, sync.API+'test?limit=50')
            self.assertEqual(len(calls), 1)

    def test_wrong_page_metadata_and_excess_items_stop(self):
        for changes in ({'offset': 50}, {'limit': 20}, {'total': True}, {'total': -1},
                        {'items': None}, {'items': list(range(51))}, {'next': False}):
            with self.subTest(changes=changes):
                with self.assertRaises(sync.SyncError):
                    sync.pages(lambda _: {**self.page(0, 50), **changes}, sync.API+'test?limit=50')
        page = self.page(0, 50); del page['offset']
        with self.assertRaises(sync.SyncError):
            sync.pages(lambda _: page, sync.API+'test?limit=50')

    def test_genuinely_empty_list_is_valid(self):
        self.assertEqual(sync.pages(lambda _: self.page(0, 0), sync.API+'test?limit=50'), [])
        self.sleep.assert_not_called()

    def test_request_errors_are_not_hidden_by_page_retries(self):
        def get(_):
            raise sync.SyncError('Spotify returned HTTP 401')
        with self.assertRaisesRegex(sync.SyncError, 'HTTP 401'):
            sync.pages(get, sync.API+'test?limit=50')
        self.sleep.assert_not_called()

    def test_recovered_page_still_requires_stable_playlist_snapshot(self):
        playlist = {'name': 'October 2026', 'id': 'A'*22, 'owner': {'id': 'ben'}, 'snapshot_id': 'before'}
        counts = {'metadata': 0, 'items': 0}
        def get(url, **kwargs):
            if url == sync.API+'me': return {'id': 'ben'}
            if url.startswith(sync.API+'me/playlists'):
                return self.page(0, 1, [playlist])
            if '/items?' in url:
                counts['items'] += 1
                return self.page(0, 1, [] if counts['items'] == 1 else [None])
            counts['metadata'] += 1
            return {**playlist, 'snapshot_id': 'before' if counts['metadata'] == 1 else 'after'}
        with patch.object(sync, 'request_json', side_effect=get):
            with self.assertRaisesRegex(sync.SyncError, 'October 2026 changed during reading'):
                sync.fetch_snapshot({'regular_playlists': []}, 'synthetic', dt.date(2026, 10, 14))
        self.assertEqual(counts, {'metadata': 2, 'items': 2})

    def test_rollover_current_month_and_previous_month_grace(self):
        cfg = {'regular_playlists': ['Soul & Disco revival'], 'previous_month_grace_days': 7}
        def p(name, owner='ben'):
            return {'name': name, 'id': 'A'*22, 'owner': {'id': owner}}
        playlists = [p('Soul_&_Disco_revival_'), p('January 2027'), p('December 2026'), p('January 2027','other')]
        selected, missing = sync.targets(playlists, cfg, dt.date(2027,1,1), 'ben')
        self.assertEqual([s[0] for s in selected], ['Soul & Disco revival','January 2027','December 2026'])
        self.assertEqual(missing, [])
        selected, _ = sync.targets(playlists, cfg, dt.date(2027,1,8), 'ben')
        self.assertEqual(len(selected), 2)

    def test_missing_month_reported_but_missing_regular_stops(self):
        cfg = {'regular_playlists': ['Brasil']}
        p = {'name':'Brasil','id':'B'*22,'owner':{'id':'ben'}}
        self.assertEqual(sync.targets([p],cfg,dt.date(2026,10,2),'ben')[1], ['October 2026'])
        with self.assertRaises(sync.SyncError):
            sync.targets([],cfg,dt.date(2026,10,2),'ben')

    def test_duplicate_names_stop(self):
        cfg = {'regular_playlists':['Brasil']}
        p = {'name':'Brasil','id':'B'*22,'owner':{'id':'ben'}}
        with self.assertRaises(sync.SyncError):
            sync.targets([p,p],cfg,dt.date(2026,9,22),'ben')

    def test_pinned_id_resolves_duplicates_and_survives_rename(self):
        cfg = {'regular_playlists':['Brasil'],'playlist_ids':{'Brasil':'B'*22}}
        playlists=[{'name':'Renamed Brasil','id':'B'*22,'owner':{'id':'ben'}},
                   {'name':'Brasil','id':'C'*22,'owner':{'id':'ben'}}]
        selected,_=sync.targets(playlists,cfg,dt.date(2026,9,22),'ben')
        self.assertEqual(selected[0][1]['id'],'B'*22)
        with self.assertRaises(sync.SyncError):
            sync.targets(playlists[1:],cfg,dt.date(2026,9,22),'ben')

    def test_existing_history_preserved_new_metadata_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'archive';root.mkdir()
            for name in ('playlist-import.py','build.py'):
                shutil.copy2(ROOT/name,root/name)
            for name in ('guest.js','dealer.js','design-pass.css'):
                (root/name).write_text('/* test module */')
            old = {'sid':'A'*22,'a':'Artist','t':'Kept song','al':'Old album','r':1973,'c':['Brazilian'],
                   'n':1,'pc':700,'p1':90,'vy':1,'did':'discogs-id','vb':'Soulful','tp':123.4,'da':202001}
            data = [old, {'sid':'C'*22,'a':'Removed from Spotify','t':'Keep in archive','c':['Jazz'],'n':1,'pc':12}]
            html = '<script>const DATA='+json.dumps(data)+'; var DIGGING={"months":[]};</script>'
            html += '<script id="guest-js"></script><script id="dealer-js"></script><style id="design-pass"></style>'
            (root/'index.html').write_text(html)
            ledger = {'Brasil':{'A'*22:'2020-01'},'Older Dance':{'C'*22:'2021-02'}}
            (root/'add-ledger.json').write_text(json.dumps(ledger))
            (root/'guest-art.json').write_text('{}')
            existing = {'sid':'A'*22,'a':'Artist','t':'Kept song','al':'Different album','rd':'2000','addedAt':'2026-09-22T09:00:00Z'}
            new = {'sid':'B'*22,'a':'New artist','t':'A </script> title','al':'New album','rd':'1977-02-01',
                   'duration':123000,'addedAt':'2026-09-21T09:00:00Z','art':'https://i.scdn.co/image/test'}
            snapshot = {'date':'2026-09-22','missing_monthly':[], 'playlists':[
                {'name':'Brasil','total':2,'skipped':{},'tracks':[existing,new]},
                {'name':'September 2026','total':1,'skipped':{},'tracks':[dict(new,addedAt='2026-09-22T09:00:00Z')]}]}
            stage = Path(folder)/'first'
            report = sync.prepare(root,snapshot,stage)
            updated,_,_ = sync.read_data((stage/'index.html').read_text())
            self.assertEqual(report['tracks_added'],1)
            self.assertEqual(updated[:2],data)
            self.assertEqual(updated[2]['n'],2)
            self.assertEqual(updated[2]['addedAt'],'2026-09-21T09:00:00Z')
            self.assertEqual(updated[2]['r'],1977)
            self.assertEqual(updated[2]['c'],['Brazilian'])
            self.assertNotIn('A </script> title',(stage/'index.html').read_text())
            self.assertEqual(json.loads((stage/'add-ledger.json').read_text())['Brasil']['A'*22],'2020-01')
            self.assertFalse((stage/'gigs-data.json').exists())
            for name in report['changed_files']:
                (root/name).parent.mkdir(exist_ok=True,parents=True)
                shutil.copy2(stage/name,root/name)
            second = sync.prepare(root,snapshot,Path(folder)/'second')
            self.assertEqual(second['tracks_added'],0)
            self.assertEqual(second['changed_files'],[])

    def test_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private/auth.json'
            sync.private_json(path,{'fixture':'synthetic'})
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)


if __name__ == '__main__':
    unittest.main()
