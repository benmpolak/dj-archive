import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('gigs',Path(__file__).resolve().parents[1]/'gigs-fetch.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

class GigRules(unittest.TestCase):
    def setUp(self):
        self.artists={g.normalize(n):{'name':n,'tracks':20,'plays':100,'max_da':202608,'the':False} for n in ['Kendrick Lamar','Che Wax','Groove Collective','I. JORDAN']}
    def event(self,**kw):
        return dict(title='Mixed by Che Wax: Kendrick Lamar & Gil Scott Heron',names=['Che Wax'],lineup_verified=True,**kw)
    def test_title_mention_never_qualifies(self):
        self.assertEqual(g.match_event(self.event(),self.artists),{'che wax':'lineup'})
    def test_scraped_title_is_not_a_lineup(self):
        self.assertEqual(g.match_event({'title':'Kendrick Lamar','names':['Kendrick Lamar']},self.artists),{})
    def test_no_substring_artist_match(self):
        self.assertEqual(g.match_event({'title':'Beirut Groove Collective','names':['Beirut Groove Collective'],'lineup_verified':True},self.artists),{})
    def test_cancellation_is_excluded_even_with_artist(self):
        self.assertEqual(g.match_event({'title':'[CANCELLED] I. JORDAN','names':['I. JORDAN'],'lineup_verified':True},self.artists),{})
        self.assertEqual(g.match_event(self.event(status='EventCancelled'),self.artists),{})
    def test_schema_performers_only(self):
        self.assertEqual(g.performer_names([{'@type':'Person','name':'Che Wax'}]),['Che Wax'])
        self.assertEqual(g.performer_names(None),[])
    def test_cached_title_match_cannot_return(self):
        saved={'artist':'Kendrick Lamar','how':'title','source':'RA','title':'Kendrick night','date':'2099-01-01'}
        self.assertEqual(g.hydrate_saved_matches({'matches':[saved]},self.artists),[])
    def test_old_mislabeled_venue_title_is_rejected(self):
        saved={'artist':'Kendrick Lamar','how':'lineup','source':'OpenAir','title':'Kendrick Lamar','date':'2099-01-01'}
        self.assertEqual(g.hydrate_saved_matches({'matches':[saved]},self.artists),[])
    def test_coartists_need_individual_evidence(self):
        saved={'artist':'Che Wax','how':'lineup','source':'RA','title':'Che Wax night','date':'2099-01-01','co':['Kendrick Lamar']}
        rows=g.hydrate_saved_matches({'matches':[saved]},self.artists)
        self.assertEqual(rows[0]['co'],[])
    def test_explicit_performer_cannot_be_faked_by_title(self):
        saved={'artist':'Kendrick Lamar','how':'lineup','source':'RA','title':'Kendrick night','date':'2099-01-01','performers':['Che Wax']}
        self.assertEqual(g.hydrate_saved_matches({'matches':[saved]},self.artists),[])

if __name__=='__main__':unittest.main()
