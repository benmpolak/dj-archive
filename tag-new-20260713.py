#!/usr/bin/env python3
"""
One-off: tag the tracks imported 2026-07-13 (16 Discogs vinyl releases +
"Playlists 2026-07-13") with crates + vibes, assigned by ear/knowledge —
same approach as tag-new-20260701.py. Keyed by (artist, title) on tracks
from index 17062 onward. Vinyl-import tracks mostly keep their Discogs-mapped
crates and just get vibes; playlist Uncategorized tracks get crates too.
Unknowns (Juzu, Sons of Sevilla) deliberately left Uncategorized.
Re-runnable: idempotent.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
START = 17062  # first track appended in the 2026-07-13 session

def parse_data(html):
    s = html.index('const DATA=') + len('const DATA=')
    d = 0; ins = False; esc = False; i = s
    while i < len(html):
        c = html[i]
        if esc: esc = False; i += 1; continue
        if c == '\\' and ins: esc = True; i += 1; continue
        if c == '"': ins = not ins; i += 1; continue
        if not ins:
            if c == '[': d += 1
            elif c == ']':
                d -= 1
                if d == 0: return json.loads(html[s:i+1]), s, i+1
        i += 1

# --- Album-level vibes for the vinyl imports (crates already mapped from Discogs) ---
# album substring -> vibe
ALBUM_VIBES = {
    'The Other Side':                     'Sunshine',              # Seu Jorge — warm MPB
    'Find Your Way':                      'Deep & Mellow',         # Illusions & Nathan Haines — balearic jazz-funk
    'Terra Em Trasse':                    'Sunshine',              # Nicola Conte bossa
    'Music Is My Sanctuary':              'Instrumental Journey',  # Gary Bartz — spiritual latin jazz
    'Barely Breaking Even':               'Groover',               # Universal Robot Band boogie anthem
    'Cuban Boxset':                       'Groover',               # DJ Koco cuban funk 45s
    'A La Memoria Del Muerto':            'Feel Good',             # salsa
    'I Want Your Love':                   'Groover',               # James Mason jazz-funk boogie
    'Feel Like Jumping':                  'Feel Good',             # rocksteady
    'No No No / Ghetto Organ':            'Deep & Mellow',         # Dawn Penn / Jackie Mittoo
    'Another Taste II':                   'Feel Good',             # modern boogie
    'Mali':                               'Groover',               # Shy One deep house
    'Jorge Ben':                          'Sunshine',              # 1969 samba-soul classic
    'Somewhere Good':                     'Ambient',               # Tara Clerkin Trio
    'Remixed With Love':                  'Feel Good',             # Dave Lee disco remixes
}
# per-track vibe overrides within vinyl imports
TRACK_VIBES = {
    ("Jon Cutler;E-Man", "It's Yours (Original Distant Music Mix)"): 'Peak Time',
    ("Fonda Rae", "Living In Ecstasy (The Groove Mix)"): 'Groover',
    ("Fonda Rae", "Living In Ecstasy (JC's Ecstasy Dub)"): 'Groover',
    ("The Return", "New Day (Original)"): 'Groover',
}
# crate corrections on vinyl imports
CRATE_FIXES = {
    'Somewhere Good': (['Downtempo', 'Electronic', 'Jazz'], None),  # drop Indie & Rock (Discogs "Pop")
}

# --- Playlist imports: (artist, title) -> (crates, vibe). None crates = keep. ---
PLIST_TAGS = {
    ("HUGEL;SOLTO (FR)", "Jamaican (Bam Bam)"): (['House'], 'Peak Time'),
    ("Michi;Mndsgn", "Emotions (feat. Mndsgn)"): (['Soul & R&B'], 'Sunshine'),
    ("Jimetta Rose", "Ebb & Flow"): (['Soul & R&B', 'Jazz'], 'Soulful'),
    ("Ubunto", "O Vento Part. As Ganhadeiras de Itapuã"): (['Brazilian'], 'Sunshine'),
    ("Moses Boyd", "Say Yeah"): (['Jazz'], 'Groover'),
    ("Scrimshire;Dwight Trible;Amanda Whiting;Idris Rahman", "Asleep, A Dream"): (['Jazz'], 'Instrumental Journey'),
    ("Crucchi Gang;Fai Baba", "Cambiato"): (['Disco & Boogie'], 'Sunshine'),
    ("Sarah Tandy", "Hyperjazz"): (['Jazz'], 'Groover'),
    ("JIM;Edie Baron", "LOVE OVER GOLD"): (['Soul & R&B', 'Downtempo'], 'Chill'),
    ("JIM", "KEEPS ME WARM"): (['Soul & R&B', 'Downtempo'], 'Chill'),
    ("Céline Dessberg", "l'histoire de ta vie"): (['Downtempo'], 'Ambient'),
    ("Jerome Derradji", "Never"): (['House'], 'Groover'),
    ("Children of Zeus", "Weed & Rum"): (['Soul & R&B', 'Hip Hop'], 'Chill'),
    ("Down To The Bone;Natasha Watts", "Shining"): (['Jazz', 'Funk'], 'Feel Good'),
    ("Osamu Fukuzawa;Jackson Mathod;edbl", "Lavender"): (['Jazz', 'Downtempo'], 'Chill'),
    ("Mark Barrott", "Variation (ii)"): (['Downtempo'], 'Ambient'),
    ("I Am An Instrument", "Wonder, Wander"): (['Jazz', 'Downtempo'], 'Ambient'),
    ("Session Victim;Kenneth Scott", "Dream Theory"): (['House'], 'Deep & Mellow'),
    ("Andre Solomko", "Summer 79"): (['Soul & R&B'], 'Sunshine'),
    ("Curió Curió", "Amor Doente"): (['Brazilian'], 'Sunshine'),
    ("Lau Ro", "Simplesmente"): (['Brazilian'], 'Sunshine'),
    ("Alex Attias;Georgia Anne Muldrow;Kid K.", "I Wanna Know - Stephane Attias Energy Dub"): (['House', 'Soul & R&B'], 'Groover'),
    ("Quiet Village", "Till The Doctor Gets Back - Extended"): (['Disco & Boogie', 'Downtempo'], 'Deep & Mellow'),
    ("Talking Drums", "Fashionable Whale"): (['Disco & Boogie', 'Afro & World'], 'Groover'),
    ("Angela Johnson;Joaquin \"Joe\" Claussell;Brian Bacchus", "Inclusion - The Soul Feast Cosmic Arts Dub"): (['House', 'Soul & R&B'], 'Groover'),
    ("Greg Henderson;Rome Jefferies", "Never Too Late (To Find A Love)"): (['Disco & Boogie'], 'Groover'),
    ("Lewis Daniel;ROMderful", "Gaslight - ROMderful Remix"): (['Soul & R&B'], 'Chill'),
    ("Orchestra Mambo International", "Olufina"): (['Afro & World', 'Jazz'], 'Groover'),
    ("Yukihiro Fukutomi", "SPEAK"): (None, 'Groover'),
    ("Move D", "To the Disco ‘77"): (None, 'Deep & Mellow'),
    ("Delano Smith;Jimpster;Diamondancer", "A Message For The DJ - Jimpster Red Light Remix"): (None, 'Deep & Mellow'),
    ("Jamie 3:26;Cratebug", "Hit It N Quit It"): (None, 'Peak Time'),
    ("Oliver Dollar", "Doin' Ya Thang"): (None, 'Groover'),
    ("Johnny Fiasco", "Kalimba"): (None, 'Groover'),
    ("Rick Wade", "Can't You See"): (None, 'Deep & Mellow'),
    ("Black Science Orchestra;Alison David", "Sunshine - Sunset Mix"): (None, 'Sunshine'),
}

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)
print(f"{len(DATA)} tracks loaded")

vibes_set = 0; crates_set = 0; unmatched = dict(PLIST_TAGS)
for t in DATA[START:]:
    key = (t['a'], t['t'])
    if key in PLIST_TAGS:
        crates, vb = PLIST_TAGS[key]
        if crates:
            merged = sorted(set(c for c in t.get('c', []) if c != 'Uncategorized') | set(crates))
            if merged != t.get('c'): t['c'] = merged; crates_set += 1
        if vb and not t.get('vb'): t['vb'] = vb; vibes_set += 1
        unmatched.pop(key, None)
        continue
    if t.get('vy'):
        for alsub, (crates, _) in CRATE_FIXES.items():
            if alsub in (t.get('al') or ''):
                if t.get('c') != crates: t['c'] = list(crates); crates_set += 1
        vb = TRACK_VIBES.get(key)
        if not vb:
            for alsub, v in ALBUM_VIBES.items():
                if alsub in (t.get('al') or ''):
                    vb = v; break
        if vb and not t.get('vb'): t['vb'] = vb; vibes_set += 1

print(f"vibes set: {vibes_set}, crate updates: {crates_set}")
if unmatched:
    print("WARNING — playlist tags that matched nothing:")
    for k in unmatched: print("  ", k)

new_json = json.dumps(DATA, separators=(',', ':'), ensure_ascii=False)
with open(ARCHIVE, 'w') as f:
    f.write(html[:ds] + new_json + html[de:])
print("Saved.")
