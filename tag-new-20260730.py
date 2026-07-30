#!/usr/bin/env python3
"""
One-off: tag the 47 tracks imported 2026-07-30 ("Playlists 2026-07-30",
Exportify CSVs incl. June_2026 + July_2026 monthlies) with crates + vibes,
assigned by ear/knowledge — same approach as tag-new-20260713.py.
Keyed by (artist, title) on tracks from index 17174 onward.
Unknowns (Devin Dare) deliberately left Uncategorized.
Re-runnable: idempotent.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
START = 17174  # first track appended in the 2026-07-30 session

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
    ("Manu Dibango", "Big Blow"): (None, 'Groover'),                       # afro-disco anthem
    ("Clive Zanda", "Ogun"): (None, 'Instrumental Journey'),               # Guadeloupe gwo-ka jazz
    ("Castanheiro", "Este Samba É Meu"): (None, 'Sunshine'),
    ("Bebeto", "A Beleza É Você Menina"): (None, 'Sunshine'),              # samba-soul
    ("Iz;Diz;Pépé Bradock", "Mouth - Brad Peeps Remix For Friends"): (None, 'Deep & Mellow'),
    ("Solu Music;KimBlee;Grant Nelson", "Fade - Grant Nelson Big Room Extended Remix"): (None, 'Feel Good'),
    ("Aly-Us", "Follow Me (Club Mix)"): (None, 'Feel Good'),               # unity anthem
    ("D.J. Rogers", "Joy from You"): (None, 'Soulful'),                    # gospel soul

    # monthlies: crates + vibes
    ("Folamour;Léon Phal;Flavia Coelho", "Zoubi"): (['House', 'Jazz'], 'Sunshine'),
    ("Bruno Berle", "Amor Inteiro"): (['Brazilian'], 'Sunshine'),          # gentle new MPB
    ("Blu;Exile;Blu & Exile;Rome Streetz;ICECOLDBISHOP", "Crumbs"): (['Hip Hop'], 'Chill'),
    ("Atjazz;Fred Everything", "L'arrivée"): (['House'], 'Deep & Mellow'),
    ("Marco Benevento", "Houdini"): (['Jazz'], 'Instrumental Journey'),    # piano jam
    ("Gayance;Waahli;Jarreau Vandal", "Podjab"): (['House'], 'Groover'),   # Montreal broken house
    ("Lulina;Ana Frango Elétrico", "Outras Vezes"): (['Brazilian'], 'Sunshine'),
    ("Scrimshire;Jake Telford", "My Land Is Your Land, Your Sky Is My Sky"): (['Jazz', 'Downtempo'], 'Chill'),
    ("Bruno Pernadas", "Spaceway 70"): (['Jazz'], 'Instrumental Journey'), # Lisbon art-jazz
    ("Mistura Pura", "A Rã - Tropical Rework"): (['Brazilian'], 'Sunshine'),
    ("Maffa;The Vito Tones;Laroye", "Night to Remeber - Laroye Moody Dub"): (['House'], 'Deep & Mellow'),
    ("Raffy Bushman", "Time For Us"): (['Jazz'], 'Instrumental Journey'),  # UK jazz piano
    ("Alvin Cobb Jr.;Katie Ernst;Julius Tucker;Aaron Day;Sage Ross;Sam Thousand;Quentin Coaxum", "Don’t Know What to Do"): (['Jazz', 'Soul & R&B'], 'Soulful'),
    ("Wonky Logic;Vanessa Rani", "Underneath The Same Sky (feat. Vanessa Rani)"): (['Jazz', 'Funk'], 'Soulful'),
    ("Ghost Funk Orchestra", "Ocotillo"): (['Funk'], 'Groover'),           # psych-funk
    ("LOVEFOXY", "Business First"): (['House'], 'Peak Time'),              # hard house
    ("Creative Power", "Special Love"): (['Disco & Boogie'], 'Groover'),   # boogie
    ("Yazmin Lacey", "Summer Haze"): (['Soul & R&B'], 'Sunshine'),
    ("Dana and Alden", "Summer Nights"): (['Jazz'], 'Sunshine'),           # lo-fi jazz brothers
    ("Dinner Party;Terrace Martin;Robert Glasper;Kamasi Washington;Phoelix;9th Wonder", "If It Ain't Broke (Love Wins) (feat. Phoelix & 9th Wonder)"): (['Jazz', 'Soul & R&B'], 'Soulful'),
    ("Nate Smith;Kiefer;CARRTOONS;Kenny Beats", "EYE LEVEL"): (['Jazz', 'Funk'], 'Groover'),
    ("Synthear", "Mediterranea"): (['Jazz', 'Funk'], 'Sunshine'),          # balearic acid jazz
    ("Sofie Birch", "Miarai"): (['Downtempo', 'Electronic'], 'Ambient'),
    ("megiapa", "Open Your Eyes"): (['Downtempo'], 'Dark & Moody'),        # trip hop
    ("DJ Spen;Tasha LaRae;Hugo C", "When I Needed You Most - Hugo C Praise Party Mix"): (['House'], 'Feel Good'),  # gospel house
    ("Alex Nut;Steve Spacek", "Bright"): (['Soul & R&B', 'Electronic'], 'Groover'),  # Eglo broken soul
    ("Mansour Shuaibu", "We Have Got It"): (['Afro & World', 'Disco & Boogie'], 'Feel Good'),  # Nigerian boogie
    ("Curió Curió", "Tô Chegando"): (['Brazilian'], 'Sunshine'),
    ("Curió Curió", "Canto de Calma"): (['Brazilian'], 'Chill'),
    ("Curió Curió", "Amizade"): (['Brazilian'], 'Chill'),
    ("Bruise", "People Dance"): (['House'], 'Groover'),
    ("Jimmy Blanche", "Misik a Moun a Kaz"): (['Afro & World'], 'Feel Good'),  # Guadeloupe kadans
    ("Josh da Costa", "Skygirl"): (['Indie & Rock'], 'Chill'),             # dream pop
    ("DJ Soch", "Let Me Tell You - Power Mix"): (['House'], 'Groover'),
    ("Hill Collective", "Fire In Orbit"): (['Jazz'], 'Instrumental Journey'),  # free jazz
    ("Cornell Campbell", "Be Thankful"): (['Afro & World'], 'Chill'),      # rocksteady; no Reggae & Dub crate
    ("Jiro Inagaki and His Soul Media", "ブリーズ"): (['Jazz', 'Funk'], 'Groover'),  # J-jazz funk
    ("Christian Prommer;Adriano Prestel", "Tin Man - A Rainer Trueby Mix"): (['House'], 'Deep & Mellow'),
    # Devin Dare "Saved" — couldn't place, left Uncategorized
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
