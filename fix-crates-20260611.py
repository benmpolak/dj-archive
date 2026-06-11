#!/usr/bin/env python3
"""Fix context-inherited crate/genre errors found 2026-06-11 (The xx in Jazz, Paul Simon
in House, trip-hop acts in Hip Hop, dub-techno acts in Afro & World, etc.).

Rule: for each corrected artist, ORIGINAL tracks move to their home crate(s) and get a
clean artist-level genre string; tracks titled as remixes/mixes stay where they are —
an A-Trak or Carl Craig mix belongs in the dance crate it was filed under.
Also strips the junk '&country' genre fragment (Discogs 'Folk, World, & Country' split bug).
"""
import json, os, re, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

def parse_data(html):
    m = re.search(r'const DATA=', html)
    ds = html.index('[', m.end()-1)
    depth=0; ins=False; esc=False; i=ds
    while i < len(html):
        c=html[i]
        if esc: esc=False; i+=1; continue
        if c=='\\' and ins: esc=True; i+=1; continue
        if c=='"': ins=not ins; i+=1; continue
        if not ins:
            if c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: return json.loads(html[ds:i+1]), ds, i+1
        i+=1

# artist -> (home crates, new genre string or None to keep)
FIX = {
  # indie/rock acts smeared into Jazz/House/Disco by playlist-context inheritance
  'The xx': (['Indie & Rock'], 'indie pop, dream pop, indietronica'),
  'Local Natives': (['Indie & Rock'], 'indie rock'),
  'Whitney': (['Indie & Rock'], 'indie folk, indie rock'),
  'Kurt Vile': (['Indie & Rock'], 'indie rock, lo-fi'),
  'The Orielles': (['Indie & Rock'], 'indie pop, jangle pop'),
  'King Krule': (['Indie & Rock'], None),
  'James Vincent McMorrow': (['Indie & Rock'], 'indie folk, alt r&b'),
  'Big Thief': (['Indie & Rock'], 'indie folk, indie rock'),
  'Angelo De Augustine': (['Indie & Rock'], 'indie folk'),
  'The Tallest Man On Earth': (['Indie & Rock'], 'indie folk, folk'),
  'The Smile': (['Indie & Rock'], None),
  'Tennis': (['Indie & Rock'], 'indie pop'),
  'Nick Mulvey': (['Indie & Rock'], 'indie folk, singer-songwriter'),
  'Villagers': (['Indie & Rock'], 'indie folk'),
  'Kevin Morby': (['Indie & Rock'], 'indie rock, indie folk'),
  'Dent May': (['Indie & Rock'], 'indie pop'),
  'Empire Of The Sun': (['Indie & Rock'], 'electropop, indie dance'),
  'The Whitest Boy Alive': (['Indie & Rock'], 'indie pop, indie dance'),
  'Midlake': (['Indie & Rock'], 'folk rock, indie rock'),
  'Talking Heads': (['Indie & Rock'], None),
  'White Lies': (['Indie & Rock'], None),
  'Late of the Pier': (['Indie & Rock'], None),
  'Summer Camp': (['Indie & Rock'], None),
  'Yeah Yeah Yeahs': (['Indie & Rock'], None),
  'Django Django': (['Indie & Rock'], 'art rock, indie dance, psychedelic pop'),
  'HAIM': (['Indie & Rock'], 'pop rock, indie pop'),
  'Jagwar Ma': (['Indie & Rock'], 'neo-psychedelia, indie dance, madchester'),
  'Broken Bells': (['Indie & Rock'], 'indie pop, indie rock'),
  'Arctic Monkeys': (['Indie & Rock'], None),
  'Yard Act': (['Indie & Rock'], None),
  'Metronomy': (['Indie & Rock'], None),
  'Paul Simon': (['Indie & Rock'], 'singer-songwriter, folk rock, worldbeat'),
  'Alabama Shakes': (['Indie & Rock'], 'southern rock, blues rock, soul rock'),
  '!!!': (['Indie & Rock'], 'dance-punk, indie dance'),
  'The Strokes': (['Indie & Rock'], None),
  'Fontaines D.C.': (['Indie & Rock'], None),
  # soul/r&b acts
  'Rhye': (['Soul & R&B'], 'alternative r&b, sophisti-pop'),
  'Dornik': (['Soul & R&B'], 'alternative r&b, uk r&b'),
  'NxWorries': (['Soul & R&B'], 'neo soul, alternative r&b, hip hop'),
  'Kelis': (['Soul & R&B'], 'r&b, alternative r&b'),
  'Gabriels': (['Soul & R&B'], 'soul, gospel soul'),
  'Rosie Lowe': (['Soul & R&B'], 'alternative r&b, uk soul'),
  'Soul II Soul': (['Soul & R&B'], 'uk soul, new jack swing'),
  'Steve Lacy': (['Soul & R&B'], 'alternative r&b, indie soul'),
  'Kali Uchis': (['Soul & R&B'], 'alternative r&b, neo soul, latin pop'),
  'Lulu James': (['Soul & R&B'], 'alternative r&b, electronic soul'),
  'The Stepkids': (['Soul & R&B'], 'psychedelic soul'),
  'Jai Paul': (['Soul & R&B'], 'alternative r&b, electronic'),
  'SAULT': (['Soul & R&B'], 'soul, funk, r&b, uk soul'),
  'Erykah Badu': (['Soul & R&B'], None),
  'Anderson .Paak': (['Soul & R&B'], None),
  # hip hop
  'Mac Miller': (['Hip Hop'], 'hip hop, rap'),
  'Sampa the Great': (['Hip Hop'], 'hip hop, neo soul'),
  'The Streets': (['Hip Hop'], 'uk garage, uk hip hop'),
  'Little Simz': (['Hip Hop'], None),
  'RJD2': (['Hip Hop', 'Downtempo'], 'instrumental hip hop, downtempo, plunderphonics'),
  'De La Soul': (['Hip Hop', 'Jazz'], None),
  # trip hop / downtempo wrongly in Hip Hop
  'Zero 7': (['Downtempo'], None),
  'Air': (['Downtempo'], None),
  'Röyksopp': (['Downtempo'], None),
  'Groove Armada': (['Downtempo'], None),
  'Moby': (['Downtempo'], None),
  'Massive Attack': (['Downtempo'], None),
  'Mark Barrott': (['Downtempo'], 'balearic, ambient, downtempo'),
  'Delorean': (['Downtempo'], None),
  'Star Slinger': (['Downtempo'], None),
  # electronic acts wrongly in Afro & World (dub-techno / uk-bass) or elsewhere
  'Mount Kimbie': (['Electronic'], None),
  'Jamie xx': (['Electronic'], None),
  'James Blake': (['Electronic'], None),
  'K-Lone': (['Electronic'], 'uk garage, dub techno, electronic'),
  'Linkwood': (['Electronic'], None),
  'Maribou State': (['Electronic'], 'electronic, chillwave, indie electronic'),
  'Thom Yorke': (['Electronic'], None),
  'Flume': (['Electronic'], None),
  'Fatboy Slim': (['Electronic'], None),
  'The Avalanches': (['Electronic'], None),
  'Cashmere Cat': (['Electronic'], None),
  'FKJ': (['Electronic'], 'french electronic, future funk, jazz-pop'),
  'Photay': (['Electronic'], 'electronic, idm'),
  'DJ Koze': (['Electronic', 'House'], 'microhouse, electronic, house'),
  # the rest
  'Cesária Evora': (['Afro & World'], 'morna, cape verdean'),
  'Sinkane': (['Afro & World'], 'afro-pop, funk rock'),
  'Bokani Dyer': (['Jazz'], 'south african jazz, contemporary jazz'),
  'Di Melo': (['Brazilian'], 'brazilian funk, soul, mpb'),
  'Basement Jaxx': (['House'], 'uk house, house'),
  'Hayden James': (['House'], 'house, deep house'),
  'Michael Jackson': (['Disco & Boogie'], None),
  'Gil Scott-Heron & Brian Jackson': (['Jazz', 'Funk'], 'jazz funk, soul, spoken word'),
}

REMIX = re.compile(r'remix|\bmix\b|rework|refix|\bedit\b|beedle', re.I)

html = open(ARCHIVE).read()
DATA, ds, de = parse_data(html)

changed_crates = 0; changed_genres = 0; kept_remix = 0
per_artist = {}
for t in DATA:
    a = t['a'].split(';')[0].strip()
    if a not in FIX: continue
    home, g = FIX[a]
    if REMIX.search(t.get('t') or ''):
        kept_remix += 1
        continue
    if t.get('c') != home:
        t['c'] = list(home); changed_crates += 1
        per_artist[a] = per_artist.get(a, 0) + 1
    if g and t.get('g') != g:
        t['g'] = g; changed_genres += 1

# junk genre fragment from Discogs 'Folk, World, & Country'
country_fixed = 0
for t in DATA:
    g = t.get('g') or ''
    if '& country' in g:
        g = g.replace('folk, world, & country', 'folk, world').replace(', & country', '').replace('& country', '').strip(' ,')
        t['g'] = re.sub(r',\s*,', ',', g)
        country_fixed += 1

bak = os.path.join(HERE, f"_backup-pre-cratefix-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
open(ARCHIVE,'w').write(html[:ds] + new_json + html[de:])
print(f"crates fixed on {changed_crates} tracks across {len(per_artist)} artists")
print(f"genre strings replaced on {changed_genres} tracks; remix-titled left alone: {kept_remix}")
print(f"'& country' junk cleaned on {country_fixed} tracks")
for a, n in sorted(per_artist.items(), key=lambda x: -x[1])[:20]:
    print(f"   {n:3} {a}")
print(f"backup: {os.path.basename(bak)}")
