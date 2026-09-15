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

class JazzVenueParsers(unittest.TestCase):
    def test_blue_note_attractions_not_title_or_description(self):
        html = """<title>Stevie Wonder celebration</title><h1>Stevie Wonder</h1>
        <div class='col-7 artist-bio-wrap '><div class='inner'>
        <h3>Che Wax &amp; Friends</h3><p>Inspired by Kendrick Lamar</p></div></div>
        <div class="artist-bio-wrap"><div><h3>Groove Collective</h3></div></div>"""
        self.assertEqual(g.bluenote_performers(html), ['Che Wax & Friends', 'Groove Collective'])
        self.assertEqual(g.bluenote_performers('<h1>Kendrick Lamar</h1>'), [])

    def test_ronnies_html_lineup_excludes_related_artist(self):
        html = """<h1>Music of Kendrick Lamar</h1><div>
        <h3 class="performance-info__heading">Line-up</h3>
        <p>CHE WAX – decks<br>I. JORDAN – keyboards</p></div>
        <h2>Related shows</h2><p>KENDRICK LAMAR – vocals</p>"""
        self.assertEqual(g.ronnies_performers(html), ['CHE WAX', 'I. JORDAN'])

    def test_ronnies_reader_lineup_stops_at_end_of_section(self):
        markdown = """# Tribute to Kendrick Lamar
### Line-up

CHE WAX – decks
I. JORDAN – keyboards

Times and Tickets

KENDRICK LAMAR – mentioned in the review
"""
        self.assertEqual(g.ronnies_performers(markdown), ['CHE WAX', 'I. JORDAN'])
        self.assertEqual(g.ronnies_performers('Title: Just a moment...\n403 Forbidden'), [])

    def test_ronnies_exact_dates_and_first_show_start(self):
        blocks = []
        for day, start in [('Wednesday 16th September, 2026', '21:30'),
                           ('Wednesday 16th September, 2026', '18:30'),
                           ('Wednesday 7th October, 2026', '19:00')]:
            blocks.append(f"""<div id="x" class="performance-option has-standard">
            <h2 class="performance-option__heading">{day}<span>17:30</span></h2>
            <h3>Doors Open</h3><p>17:30</p><h3>Show Starts</h3><p>{start}</p></div>""")
        self.assertEqual(g.ronnies_dates(''.join(blocks)),
                         {'2026-09-16': '18:30', '2026-10-07': '19:00'})
        self.assertEqual(g.ronnies_dates('Wed 16 Sept - Wed 7 Oct 2026'), {})

    def test_ronnies_preserves_real_url_and_booking_id(self):
        html = """<div class="listing"><h2 class="listing__title">A Quartet &amp; Guests</h2>
        <button id="id-1234">Book Now</button>
        <a href="https://www.ronniescotts.co.uk/find-a-show/different-slug">Find out more</a></div>"""
        self.assertEqual(g.ronnies_listings(html), [{'title':'A Quartet & Guests', 'id':'1234',
            'url':'https://www.ronniescotts.co.uk/find-a-show/different-slug'}])

if __name__=='__main__':unittest.main()
