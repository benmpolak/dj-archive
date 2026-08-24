#!/usr/bin/env python3
"""
One-off: tag the 78 tracks imported 2026-08-24 ("Playlists 2026-08-24",
Exportify CSVs incl. July_2026 + August_2026 monthlies) with crates + vibes,
assigned by ear/knowledge — same approach as tag-new-20260730.py.
Keyed by (artist, title) on tracks from index 17227 onward.
Unknowns (Chenayder, Love Spells, John Silas, Standing Circle, Mike kee,
Producer's Workshop Ensemble) deliberately left Uncategorized.
Re-runnable: idempotent.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
START = 17227  # first track appended in the 2026-08-24 session

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

# (artist, title) -> (crates, vibe). None crates = keep existing.
TAGS = {
    # crate-playlist imports: crates already right, just vibes
    ("Mondo Grosso", "SOUFFLES H"): (None, 'Groover'),                     # jazzy Shibuya house classic
    ("IZ;Diz;Pepé Bradock", "Mouth - Brad Peep's Remix For Friends"): (None, 'Deep & Mellow'),
    ("The Salsoul Orchestra", "It’s Good For The Soul"): (None, 'Feel Good'),
    ("Louie Vega;Elements Of Life;Raul Midón;Josh Milan;Kiko Navarro", "Sunshine (I Can Fly) - Kiko Navarro Extended Remix"): (None, 'Feel Good'),
    ("Sandra Sá", "Olhos Coloridos"): (None, 'Sunshine'),                  # 1982 samba-soul anthem
    ("Rosa Maria", "Rio da Felicidade"): (None, 'Sunshine'),
    ("El Dragón Criollo;Nelson Y Sus Estrellas;El Palmas", "María la Bella"): (None, 'Sunshine'),
    ("Cortijo y Kako y sus Tambores", "Qué Le Pasó"): (None, 'Groover'),   # street rumba
    ("Ladyhawke", "Paris Is Burning"): (None, 'Feel Good'),
    ("Erb", "The Weekend - Vocal Mix"): (None, 'Feel Good'),
    ("BRS", "Clubtronic"): (None, 'Groover'),
    ("Glenn Underground", "Play Play Play"): (None, 'Deep & Mellow'),

    # monthlies: crates + vibes
    ("Marco Benevento;Lizzie Steiner", "Miss Neptune"): (['Jazz'], 'Instrumental Journey'),
    ("Donae'o;Omar;Lemar;House Gospel Choir", "Nights Like This"): (['House'], 'Feel Good'),  # UK funky gospel lift
    ("Children of Zeus;Anieszka", "Water & Vibes"): (['Soul & R&B'], 'Soulful'),
    ("Kerri Chandler", "You Are In My System (feat. Troy Denari) - Original Deluxe"): (['House'], 'Deep & Mellow'),
    ("Isaiah Collier", "Landscape Of Dreams"): (['Jazz'], 'Instrumental Journey'),  # Chicago spiritual jazz
    ("Azekel;Céline Dessberg", "Moon & I"): (['Downtempo'], 'Chill'),
    ("Baby Rose", "The Reason"): (['Soul & R&B'], 'Soulful'),
    ("Michi;Mndsgn", "Memmy (Recuerdo) (Mndsgn RMX)"): (['Downtempo'], 'Chill'),
    ("54 Ultra", "Tell Me"): (['Soul & R&B'], 'Chill'),                    # lo-fi indie soul
    ("Gan Gemi", "Forever Now pt. 2"): (['Jazz'], 'Ambient'),
    ("Nechazz", "Love The Way You Make Me Feel"): (['House'], 'Deep & Mellow'),  # jazz-house
    ("DJ SWISHERMAN", "I'm a Good Woman"): (['House'], 'Peak Time'),       # afterhours pump
    ("Thee Sacred Souls;Victor Axelrod", "Waiting on the Right Time"): (['Reggae & Dub', 'Soul & R&B'], 'Soulful'),  # Axelrod rocksteady version
    ("Richard Rogers", "(I'll Be Your) Dreamlover - Marley Marl Vocal Mix"): (['House'], 'Feel Good'),  # 90s NY house
    ("ReKaB", "Its Not For Some People"): (['Electronic'], 'Deep & Mellow'),
    ("TRANCEFELD", "Love Song"): (['Electronic'], 'Deep & Mellow'),
    ("DÜK;FLAT 22", "Yoru no Groove"): (['House'], 'Groover'),
    ("Vince Watson;Cee ElAssaad", "Eminesence - Cee ElAssaad Remix"): (['House'], 'Deep & Mellow'),
    ("Jason Dungan;Johan Carøe;Blue Lake", "Mornings with Rita"): (['Jazz'], 'Ambient'),
    ("Kokoroko;Bruno Berle", "Closer To Me (Bruno Berle Remix)"): (['Brazilian', 'Jazz'], 'Sunshine'),
    ("Don Glori", "Sundancer"): (['Jazz'], 'Groover'),                     # Melbourne jazz fusion
    ("Inta-City;Kon", "Runnin' Outta Time - Kon's Got It Together Flip"): (['Disco & Boogie'], 'Feel Good'),
    ("Max Sinàl;Sio", "Counting Stars"): (['House'], 'Deep & Mellow'),
    ("Finn Rees", "Another Spring"): (['Jazz'], 'Instrumental Journey'),
    ("JIM", "MY DREAMS ARE STRANGE"): (['Indie & Rock'], 'Sunshine'),      # Jim Baron balearic
    ("Dana and Alden", "Napa 86"): (['Jazz'], 'Chill'),
    ("Children of Zeus;Knucks", "Before We Drown"): (['Hip Hop', 'Soul & R&B'], 'Soulful'),
    ("Nate Smith;Kiefer;CARRTOONS;Kenny Beats", "PATCHWORK"): (['Jazz'], 'Groover'),
    ("Camille Munn", "Get Down"): (['House', 'Soul & R&B'], 'Groover'),    # UK funky x neo soul
    ("IZCO", "Komodo"): (['Electronic'], 'Peak Time'),                     # UKG/jungle
    ("The Womack Sisters", "If You Want Me"): (['Soul & R&B'], 'Soulful'),
    ("megiapa", "on the spaceway (frfr)"): (['Downtempo'], 'Chill'),
    ("Balaphonic;Robin Dewhurst", "Dew Drops"): (['Jazz'], 'Instrumental Journey'),
    ("Luke Alessi", "After Five"): (['House'], 'Deep & Mellow'),
    ("Okvsho", "Rio Sihl"): (['Jazz'], 'Chill'),
    ("Okvsho;FloFilz;Melodiesinfonie", "sl.wm.ed."): (['Jazz'], 'Chill'),
    ("Àbáse", "Bolgár Táncok / Bulgarian Dances"): (['Jazz'], 'Groover'),  # Budapest jazz-beats
    ("Juicy J", "Expect the Unexpected"): (['Hip Hop'], 'Dark & Moody'),
    ("Kiefer;Tony Stone;Erick the Architect;CARRTOONS", "NewLevels NewDevils (feat. Tony Stone, Erick the Architect, CARRTOONS)"): (['Jazz', 'Hip Hop'], 'Chill'),
    ("Alvin Cobb Jr.;Katie Ernst;Julius Tucker;Aaron Day", "Not Too Far Away"): (['Jazz'], 'Soulful'),
    ("Norman Connors", "Love from the Sun"): (['Jazz', 'Soul & R&B'], 'Soulful'),
    ("Cleo Sol", "Their Smiles Are Not the Same"): (['Soul & R&B'], 'Soulful'),
    ("Lenny Fontana;Jasmine Lovett", "If You Want Me - Club Mix"): (['House'], 'Feel Good'),
    ("Guiding Star Orchestra", "Trials"): (['Reggae & Dub'], 'Deep & Mellow'),
    ("Jon E.", "One More Time"): (['Jazz'], 'Chill'),                      # street-soul nu jazz
    ("Jon E.;Roxanne Myles", "We Can Make It"): (['Jazz'], 'Soulful'),
    ("Jon E.", "Day n Night"): (['Jazz'], 'Chill'),
    ("Camille Munn;Samtheman", "Unity"): (['House', 'Soul & R&B'], 'Groover'),
    ("Takuro Okada", "Portrait of Yanagi"): (['Jazz'], 'Ambient'),
    ("Takuro Okada", "Sunrise"): (['Jazz'], 'Ambient'),
    ("MacZito", "What You Gonna Do"): (['House'], 'Deep & Mellow'),
    ("The Matthew Rivera Untet;ArinMaya", "rain"): (['Jazz', 'Soul & R&B'], 'Soulful'),
    ("Venna;JVCK JAMES;JADA;EMIL;Marco Bernardis", "June's Cry"): (['Jazz', 'Soul & R&B'], 'Soulful'),
    ("Dj Laurel", "Deeper"): (['Disco & Boogie'], 'Groover'),              # nu-disco edit
    ("Marla Kether;Sofia Grant", "Reverse"): (['Soul & R&B'], 'Groover'),  # street-soul bass
    ("Richard Spaven;Wildchild", "Finders"): (['Jazz', 'Hip Hop'], 'Chill'),
    ("Davina Stone;Mad Professor", "Silly Wasn't I"): (['Reggae & Dub'], 'Soulful'),  # lovers rock
    ("Donald Byrd", "Lansana's Priestess"): (['Jazz'], 'Groover'),         # adds Jazz to playlist crates
    ("Valéria;Delfonic", "Marcação - Delfonic Edit"): (['Brazilian', 'Disco & Boogie'], 'Sunshine'),
    ("Juicy Fruits", "O Shi E Te A Ge Ru"): (['Disco & Boogie'], 'Feel Good'),  # 1984 city pop
    # Chenayder, Love Spells, Standing Circle, Mike kee, John Silas,
    # Producer's Workshop Ensemble — couldn't place, left Uncategorized
}

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)
print(f"{len(DATA)} tracks loaded")

vibes_set = 0; crates_set = 0; unmatched = dict(TAGS)
for t in DATA[START:]:
    key = (t['a'], t['t'])
    if key not in TAGS:
        continue
    crates, vb = TAGS[key]
    if crates:
        merged = sorted(set(c for c in t.get('c', []) if c != 'Uncategorized') | set(crates))
        if merged != t.get('c'): t['c'] = merged; crates_set += 1
    if vb and not t.get('vb'): t['vb'] = vb; vibes_set += 1
    unmatched.pop(key, None)

print(f"vibes set: {vibes_set}, crate updates: {crates_set}")
if unmatched:
    print("WARNING — tags that matched nothing:")
    for k in unmatched: print("  ", k)

new_json = json.dumps(DATA, separators=(',', ':'), ensure_ascii=False)
with open(ARCHIVE, 'w') as f:
    f.write(html[:ds] + new_json + html[de:])
print("Saved.")
