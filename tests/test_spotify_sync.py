import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spotify_sync', ROOT / 'spotify_sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SpotifySyncTests(unittest.TestCase):
    def test_all_pages_including_past_100(self):
        def get(url):
            offset = int(url.rsplit('=', 1)[1])
            return {'total': 125, 'items': list(range(offset, min(offset+50, 125))),
                    'next': sync.API + 'test?offset=' + str(offset+50) if offset+50 < 125 else None}
        self.assertEqual(sync.pages(get, sync.API+'test?offset=0'), list(range(125)))

    def test_truncated_or_foreign_pagination_stops(self):
        for page in ({'total': 101, 'items': list(range(100)), 'next': None},
                     {'total': 2, 'items': [1], 'next': 'https://example.com/steal'},
                     {'total': 2, 'items': [1], 'next': sync.API+'x'}):
            with self.assertRaises(sync.SyncError):
                sync.pages(lambda _: page, sync.API+'x')

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
