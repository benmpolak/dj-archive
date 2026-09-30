import importlib.util
import unittest
from unittest.mock import patch
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
    def test_same_night_from_ra_and_venue_feed_shown_once(self):
        a = {n: {'name': n} for n in ['Che Wax', 'Groove Collective', 'I. JORDAN']}
        row = lambda artist, venue, title, source, co=(): {'artist': a[artist], 'co': [a[c] for c in co], 'date': '2026-11-20',
                                                           'venue': venue, 'title': title, 'source': source}
        rows = [row('Che Wax', 'EartH Kitchen', 'Balearic London x Che Wax', 'RA'),
                row('Che Wax', 'EartH', 'Che Wax', 'EartH'),                                   # same night, other feed
                row('Groove Collective', 'EartH', 'Che Wax', 'EartH', co=['Che Wax']),          # adds an artist
                row('I. JORDAN', 'Village Underground', 'I. JORDAN (Live)', 'RA'),
                row('I. JORDAN', 'The Jazz Cafe', 'I. JORDAN', 'JazzCafe')]                     # different venue
        self.assertEqual([(r['source'], r['venue']) for r in g.drop_repeat_nights(rows)],
                         [('RA', 'EartH Kitchen'), ('EartH', 'EartH'), ('RA', 'Village Underground'), ('JazzCafe', 'The Jazz Cafe')])
        self.assertEqual(g.drop_repeat_nights(rows)[1]['artist']['name'], 'Groove Collective')
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

    def test_ronnies_fetch_verifies_lineup_and_requests_booking_fragment(self):
        base = 'https://www.ronniescotts.co.uk/find-a-show'
        detail = base + '/actual-show'
        listing = f"""<div class="listing"><h2 class="listing__title">Kendrick Lamar night</h2>
        <button id="id-1234">Book</button><a href="{detail}">Details</a></div>"""
        lineup = '<h3>Line-up</h3><p>CHE WAX – decks</p></div>'
        drawer = """<div class="performance-option has-standard">
        <h2 class="performance-option__heading">Thursday 17th September, 2026</h2>
        <h3>Show Starts</h3><p>18:20</p></div>"""
        artists = {g.normalize(n): {'name':n, 'tracks':2, 'plays':10, 'max_da':202609}
                   for n in ['Kendrick Lamar', 'Che Wax']}
        def fetch(url, **kwargs):
            if url == base:
                return listing
            if url == detail:
                return lineup
            if url == base + '?id=1234&ajax=1':
                self.assertEqual(kwargs['extra_headers']['X-Requested-With'], 'XMLHttpRequest')
                return drawer
            self.fail('Unexpected URL: ' + url)
        with patch.object(g, 'http_get', side_effect=fetch), patch.object(g, 'load_artists', return_value=artists):
            events = g.fetch_ronnies()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['names'], ['CHE WAX'])
        self.assertEqual(events[0]['date'], '2026-09-17')
        self.assertEqual(events[0]['start'], '18:20')
        self.assertTrue(events[0]['lineup_verified'])

    def test_ronnies_preserves_real_url_and_booking_id(self):
        html = """<div class="listing"><h2 class="listing__title">A Quartet &amp; Guests</h2>
        <button id="id-1234">Book Now</button>
        <a href="https://www.ronniescotts.co.uk/find-a-show/different-slug">Find out more</a></div>"""
        self.assertEqual(g.ronnies_listings(html), [{'title':'A Quartet & Guests', 'id':'1234',
            'url':'https://www.ronniescotts.co.uk/find-a-show/different-slug'}])

class AllyPallyParser(unittest.TestCase):
    LISTING = """
    <p class="dates uc"><strong>23 Oct 2026</strong></p>
    <a href="https://www.alexandrapalace.com/whats-on/kendrick-night/" class="event_target"><h3>Kendrick Lamar&#8217;s Night</h3></a>
    <p class="dates uc"><strong>26 - 27 Feb 2027</strong></p>
    <a href="https://www.alexandrapalace.com/whats-on/groove-run/" class="event_target"><h3>Groove Collective</h3></a>
    <p class="dates uc"><strong>3 Oct 2026</strong></p>
    <a href="https://www.alexandrapalace.com/whats-on/darts/" class="event_target"><h3>Kendrick Lamar</h3></a>"""

    @staticmethod
    def dice(day, performers, venue='Alexandra Palace', status='https://schema.org/EventScheduled'):
        ld = {'@type':'MusicEvent','name':'Kendrick Lamar','startDate':f'{day}T18:30:00+01:00',
              'eventStatus':status,'location':{'@type':'Place','name':venue},
              'performer':[{'@type':'PerformingGroup','name':n} for n in performers]}
        return f'<script type="application/ld+json">{g.json.dumps(ld)}</script>'

    def fetch(self, url, **kwargs):
        pages = {
            'https://www.alexandrapalace.com/whats-on/': self.LISTING,
            # own JSON-LD has no performer; only the DICE link carries the bill
            'https://www.alexandrapalace.com/whats-on/kendrick-night/':
                '<h1>Kendrick Lamar</h1><a href="https://link.dice.fm/venue/alexandra-palace">DICE</a>'
                '<a href="https://link.dice.fm/abc123">Tickets</a>',
            'https://www.alexandrapalace.com/whats-on/groove-run/': '<a href="https://link.dice.fm/bundle1">Tickets</a>',
            'https://www.alexandrapalace.com/whats-on/darts/': '<h1>Kendrick Lamar</h1><a href="https://tickets.example/x">Tickets</a>',
            'https://link.dice.fm/abc123': self.dice('2026-10-23', ['Che Wax', 'I. JORDAN']),
            'https://link.dice.fm/bundle1': '<a href="/event/night1">Fri</a><a href="https://dice.fm/event/night2">Sat</a>'
                                            '<a href="/event/elsewhere">Other venue</a>',
            'https://dice.fm/event/night1': self.dice('2027-02-26', ['Groove Collective']),
            'https://dice.fm/event/night2': self.dice('2027-02-27', ['Groove Collective']),
            'https://dice.fm/event/elsewhere': self.dice('2027-02-28', ['Groove Collective'], venue='Roundhouse'),
        }
        if url not in pages:
            self.fail('Unexpected URL: ' + url)
        return pages[url]

    def events(self):
        with patch.object(g, 'http_get', side_effect=self.fetch):
            return {(e['url'].rsplit('/', 2)[-2], e['date']): e for e in g.fetch_allypally()}

    def test_performers_come_from_dice_not_title(self):
        ev = self.events()[('kendrick-night', '2026-10-23')]
        self.assertEqual(ev['names'], ['Che Wax', 'I. JORDAN'])
        self.assertEqual((ev['title'], ev['start'], ev['venue']), ('Kendrick Lamar’s Night', '18:30', 'Alexandra Palace'))
        self.assertTrue(ev['lineup_verified'])
        artists = {g.normalize(n): {'name':n,'tracks':20,'plays':100,'max_da':202608} for n in ['Kendrick Lamar','Che Wax']}
        self.assertEqual(g.match_event(ev, artists), {'che wax':'lineup'})

    def test_bundle_nights_each_listed_and_other_venues_dropped(self):
        runs = sorted(d for slug, d in self.events() if slug == 'groove-run')
        self.assertEqual(runs, ['2027-02-26', '2027-02-27'])

    def test_listing_without_dice_lineup_stays_unverified(self):
        ev = self.events()[('darts', '2026-10-03')]
        self.assertEqual(ev['names'], [])
        self.assertFalse(ev.get('lineup_verified'))
        self.assertEqual(g.match_event(ev, {'kendrick lamar': {'name':'Kendrick Lamar','tracks':20,'plays':100,'max_da':202608}}), {})

    def test_dice_cancelled_status_is_kept_for_exclusion(self):
        shows = g.dice_shows(self.dice('2026-10-23', ['Che Wax'], status='https://schema.org/EventCancelled'))
        self.assertTrue(g.is_cancelled(shows[0]))
        self.assertEqual(g.dice_shows('<script type="application/ld+json">{"@type":"WebSite"}</script>'), [])

class EarthParser(unittest.TestCase):
    def fetch(self, url, **kwargs):
        pages = {
            'https://earthackney.co.uk/events/':
                '<a href="https://earthackney.co.uk/events/kendrick-lamar-night-9th-oct-earth-london-tickets-abc123/">x</a>'
                '<a href="https://earthackney.co.uk/events/kendrick-lamar-night-9th-oct-earth-london-tickets-abc123/">dup</a>'
                '<a href="https://earthackney.co.uk/events/groove-collective-12th-nov-earth-london-tickets-zzz999/">y</a>',
            'https://dice.fm/event/abc123': AllyPallyParser.dice('2027-10-09', ['Che Wax'], venue='EartH'),
            'https://dice.fm/event/zzz999': AllyPallyParser.dice('2026-11-12', ['Groove Collective'], venue='Somewhere Else'),
        }
        if url not in pages:
            self.fail('Unexpected URL: ' + url)
        return pages[url]

    def test_dice_code_in_url_supplies_bill_title_and_year(self):
        with patch.object(g, 'http_get', side_effect=self.fetch):
            events = g.fetch_earth()
        self.assertEqual(len(events), 2)
        ev, other = events
        self.assertEqual((ev['date'], ev['start'], ev['title'], ev['names']), ('2027-10-09', '18:30', 'Kendrick Lamar', ['Che Wax']))
        self.assertTrue(ev['lineup_verified'])
        artists = {g.normalize(n): {'name':n,'tracks':20,'plays':100,'max_da':202608} for n in ['Kendrick Lamar','Che Wax','Groove Collective']}
        self.assertEqual(g.match_event(ev, artists), {'che wax':'lineup'})
        self.assertEqual((other['names'], other.get('lineup_verified')), ([], None))
        self.assertEqual(g.match_event(other, artists), {})

class BarbicanParser(unittest.TestCase):
    @staticmethod
    def people(title, rows):
        items = ''.join(f'<li> <span class="label-value-list__label"> {a} </span>&nbsp; '
                        f'<span class="label-value-list__value"> {b} </span> </li>' for a, b in rows)
        return (f'<div class="related-people"> <h3 class="related-people__title">{title}</h3> '
                f'<div class="label-value-list"><ul class="label-value-list__list">{items}</ul></div></div>')

    def test_only_performers_lists_count(self):
        html = (self.people('', [('Kendrick Lamar', 'laser programming')])            # untitled, nothing before it
                + self.people('Programme', [('Kendrick Lamar', 'Composition No. 1')])  # composers
                + self.people('', [('Kendrick Lamar', 'Song 2')])                      # continues Programme
                + self.people('Performers', [('Che Wax', ''), ('Groove Collective', 'band')])
                + self.people('', [('I. JORDAN', 'keys')])                             # continues Performers
                + self.people('Creative Team', [('Music by Kendrick Lamar', '')])
                + self.people('Cast', [('Kendrick Lamar', 'Hamlet')]))
        self.assertEqual(g.barbican_performers(html), ['Che Wax', 'Groove Collective', 'I. JORDAN'])

    def test_film_credits_are_role_first(self):
        html = self.people('Performers', [('Directed &amp; Performed by', 'Che Wax'), ('Composed by', 'Kendrick Lamar'),
                                          ('Performed by', 'Groove Collective'), ('Conductor', 'I. JORDAN')])
        self.assertEqual(g.barbican_performers(html), ['Che Wax', 'Groove Collective'])

    def test_event_date_from_byline_not_related_cards(self):
        page = ('<h1><span>Ed O&#039;Brien</span></h1><div class="event-byline"><span class="event-byline__date">'
                '<time datetime="2026-10-16T19:30:00Z">Fri 16 Oct 2026, 19:30</time></span></div>'
                '<div class="promo-card__date"><time datetime="2026-09-01T16:00:00Z">Tue 1 Sep</time></div>')
        with patch.object(g, 'http_get', return_value=page):
            ev = g.barbican_event('https://www.barbican.org.uk/whats-on/2026/event/ed')
        self.assertEqual((ev['date'], ev['start'], ev['title']), ('2026-10-16', '', "Ed O'Brien"))
        self.assertEqual((ev['names'], ev['lineup_verified']), ([], False))
        with patch.object(g, 'http_get', return_value=page + self.people('Performers', [('Che Wax', '')])):
            self.assertTrue(g.barbican_event('https://www.barbican.org.uk/whats-on/2026/event/ed')['lineup_verified'])

if __name__=='__main__':unittest.main()
