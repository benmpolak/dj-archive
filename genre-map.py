#!/usr/bin/env python3
"""
Genre -> super-genre mapping for the DJ Archive.

The 645 micro-genre tags collapse into the same 12-13 buckets as the
crates, so browsing/stats can use one coarse vocabulary. Explicit map
first (hand-curated, covers the high-count genres), keyword rules for
the tail.

Run modes:
  python3 genre-map.py            # coverage report + unmapped list
  python3 genre-map.py --review   # write genre-mapping-review.md for red-pen
"""
import json, re, sys
from collections import Counter, defaultdict

BUCKETS = ['Jazz','Funk','Soul & R&B','Disco & Boogie','House','Electronic',
           'Downtempo','Hip Hop','Brazilian','Afro & World','Reggae & Dub',
           'Indie & Rock']

# --- Explicit map: hand decisions where keywords would get it wrong ---
EXPLICIT = {
    # Jazz family
    'jazz':'Jazz','nu jazz':'Jazz','acid jazz':'Jazz','indie jazz':'Jazz',
    'jazz fusion':'Jazz','soul jazz':'Jazz','hard bop':'Jazz','free jazz':'Jazz',
    'experimental jazz':'Jazz','contemporary jazz':'Jazz','bebop':'Jazz',
    'smooth jazz':'Jazz','cool jazz':'Jazz','vocal jazz':'Jazz','jazz ballads':'Jazz',
    'jazz funk':'Jazz','jazz-funk':'Jazz','jazz pop':'Jazz','spiritual jazz':'Jazz',
    'latin jazz':'Jazz','afro-cuban jazz':'Jazz','modal jazz':'Jazz','post-bop':'Jazz',
    'ambient jazz':'Jazz','jazz beats':'Downtempo','jazz house':'House',
    'jazz rap':'Hip Hop','brazilian jazz':'Brazilian',
    # Funk
    'funk':'Funk','funk / soul':'Funk','p funk':'Funk','funk rock':'Funk',
    'go-go':'Funk','afro funk':'Afro & World','liquid funk':'Electronic',
    'uk funky':'House',
    # Soul & R&B
    'soul':'Soul & R&B','r&b':'Soul & R&B','neo soul':'Soul & R&B',
    'classic soul':'Soul & R&B','alternative r&b':'Soul & R&B',
    'northern soul':'Soul & R&B','motown':'Soul & R&B','retro soul':'Soul & R&B',
    'uk r&b':'Soul & R&B','philly soul':'Soul & R&B','quiet storm':'Soul & R&B',
    'indie soul':'Soul & R&B','contemporary r&b':'Soul & R&B','gospel':'Soul & R&B',
    # Disco & Boogie
    'disco':'Disco & Boogie','nu disco':'Disco & Boogie','boogie':'Disco & Boogie',
    'post-disco':'Disco & Boogie','italo disco':'Disco & Boogie',
    'hi-nrg':'Disco & Boogie','yacht rock':'Disco & Boogie','aor':'Disco & Boogie',
    'disco house':'House','funky house':'House',
    # House
    'house':'House','deep house':'House','lo-fi house':'House',
    'chicago house':'House','acid house':'House','french house':'House',
    'latin house':'House','afro house':'House','indie dance':'House',
    'dance':'House','uk garage':'Electronic','garage house':'House',
    'tech house':'House','minimal house':'House','soulful house':'House',
    # Electronic
    'electronic':'Electronic','idm':'Electronic','breakbeat':'Electronic',
    'jungle':'Electronic','drum and bass':'Electronic','techno':'Electronic',
    'big beat':'Electronic','electronica':'Electronic','experimental':'Electronic',
    'electropop':'Electronic','synth pop':'Indie & Rock','electro':'Electronic',
    'bass music':'Electronic','dubstep':'Electronic',
    # Downtempo
    'downtempo':'Downtempo','trip hop':'Downtempo','chillwave':'Downtempo',
    'lo-fi beats':'Downtempo','ambient':'Downtempo','balearic':'Downtempo',
    'chillout':'Downtempo',
    # Hip Hop
    'hip hop':'Hip Hop','east coast hip hop':'Hip Hop','old school hip hop':'Hip Hop',
    'experimental hip hop':'Hip Hop','west coast hip hop':'Hip Hop',
    'boom bap':'Hip Hop','instrumental hip hop':'Hip Hop','uk hip hop':'Hip Hop',
    'rap':'Hip Hop','conscious hip hop':'Hip Hop',
    # Brazilian
    'mpb':'Brazilian','new mpb':'Brazilian','bossa nova':'Brazilian',
    'samba':'Brazilian','brazilian':'Brazilian','brazilian boogie':'Brazilian',
    'tropicalia':'Brazilian','forro':'Brazilian','baile funk':'Brazilian',
    # Afro & World
    'afrobeat':'Afro & World','latin':'Afro & World','world':'Afro & World',
    'highlife':'Afro & World','salsa':'Afro & World','son cubano':'Afro & World',
    'afropop':'Afro & World','cumbia':'Afro & World','soukous':'Afro & World',
    'ethio-jazz':'Afro & World','desert blues':'Afro & World','afro-cuban':'Afro & World',
    # Reggae & Dub
    'reggae':'Reggae & Dub','lovers rock':'Reggae & Dub','dub':'Reggae & Dub',
    'rocksteady':'Reggae & Dub','roots reggae':'Reggae & Dub','ska':'Reggae & Dub',
    'dancehall':'Reggae & Dub',
    # Indie & Rock (incl folk/pop/songwriter)
    'indie rock':'Indie & Rock','indie':'Indie & Rock','rock':'Indie & Rock',
    'britpop':'Indie & Rock','indie pop':'Indie & Rock','folk':'Indie & Rock',
    'indie folk':'Indie & Rock','singer-songwriter':'Indie & Rock',
    'art rock':'Indie & Rock','dream pop':'Indie & Rock',
    'neo-psychedelic':'Indie & Rock','baroque pop':'Indie & Rock',
    'post-punk':'Indie & Rock','art pop':'Indie & Rock','modern indie':'Indie & Rock',
    'alt rock':'Indie & Rock','classic rock':'Indie & Rock','pop':'Indie & Rock',
    'psychedelic rock':'Indie & Rock','garage rock':'Indie & Rock',
    'shoegaze':'Indie & Rock','new wave':'Indie & Rock','soft rock':'Indie & Rock',
    # Tail fixes
    'cha cha cha':'Afro & World','mambo':'Afro & World','bolero':'Afro & World',
    'merengue':'Afro & World','timba':'Afro & World','champeta':'Afro & World',
    'chicha':'Afro & World','african':'Afro & World','hiplife':'Afro & World',
    'fado':'Afro & World','fusion':'Jazz','modal':'Jazz','big band':'Jazz',
    'doo-wop':'Soul & R&B','broken beat':'Electronic','ragga':'Reggae & Dub',
    'madchester':'Indie & Rock','new rave':'Indie & Rock','baggy':'Indie & Rock',
    'slowcore':'Indie & Rock','southern gothic':'Indie & Rock',
    'shibuya-kei':'Indie & Rock','pagode':'Brazilian','axé':'Brazilian',
    'forró':'Brazilian','forró tradicional':'Brazilian','brega':'Brazilian',
    'lounge':'Downtempo','exotica':'Downtempo','ballroom vogue':'House',
    'plunderphonics':'Electronic','post-dubstep':'Electronic',
    'footwork':'Electronic','baltimore club':'Electronic',
    'sample-based':'Hip Hop',
    # Data junk / fragments
    '& country':None,   # parsing fragment — fix at source
    'spoken word':None,'stage & screen':None,'soundtrack':None,
}

# --- Keyword fallback for the tail (checked in order, first hit wins) ---
RULES = [
    (r'bossa|samba|mpb|brazil|tropicalia|forro', 'Brazilian'),
    (r'reggae|dub(?!step)|ska|riddim', 'Reggae & Dub'),
    (r'hip hop|rap|boom bap|drill|grime', 'Hip Hop'),
    (r'house|garage(?! rock)', 'House'),
    (r'jazz|bop|swing', 'Jazz'),
    (r'soul|r&b|motown|gospel|doo wop', 'Soul & R&B'),
    (r'disco|boogie', 'Disco & Boogie'),
    (r'funk(?!y house)', 'Funk'),
    (r'afro|latin|salsa|cuban|world|highlife|cumbia|ethio|calypso|haitian|zouk|gnawa|rai\b|bhangra|tropical', 'Afro & World'),
    (r'downtempo|trip hop|ambient|chill|lo-?fi|balearic', 'Downtempo'),
    (r'techno|electro|idm|jungle|drum and bass|dnb|breakbeat|bass|synthwave|glitch|leftfield|dance', 'Electronic'),
    (r'rock|indie|punk|pop|folk|songwriter|psych|wave|gaze|metal|country|blues|americana|acoustic', 'Indie & Rock'),
]

def map_genre(g):
    g = g.strip().lower()
    if g in EXPLICIT:
        return EXPLICIT[g]
    for pat, bucket in RULES:
        if re.search(pat, g):
            return bucket
    return None

def load_data():
    html = open('index.html').read()
    s = html.index('const DATA=') + len('const DATA=')
    depth=0; instr=False; esc=False; i=s
    while True:
        c = html[i]
        if esc: esc=False
        elif c=='\\' and instr: esc=True
        elif c=='"': instr = not instr
        elif not instr:
            if c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: break
        i+=1
    return json.loads(html[s:i+1])

def main():
    DATA = load_data()
    counts = Counter()
    for t in DATA:
        for g in (t.get('g') or '').split(','):
            g = g.strip().lower()
            if g: counts[g] += 1

    mapped = defaultdict(list)
    unmapped = []
    total = sum(counts.values())
    covered = 0
    for g, n in counts.most_common():
        b = map_genre(g)
        if b:
            mapped[b].append((g, n)); covered += n
        elif g in EXPLICIT:  # explicit None = deliberate junk
            covered += n
        else:
            unmapped.append((g, n))

    print(f'{len(counts)} distinct genres, {total} tag instances')
    print(f'coverage: {covered}/{total} = {100*covered/total:.1f}%')
    print(f'unmapped: {len(unmapped)} genres, {sum(n for _,n in unmapped)} instances')

    if '--review' in sys.argv:
        with open('genre-mapping-review.md', 'w') as f:
            f.write('# Genre mapping — for review\n\n')
            f.write('Rule: every micro-genre collapses to one of the 12 crate-level buckets ')
            f.write('(plus Reggae & Dub, which has no crate — shout if it should fold into Afro & World).\n')
            f.write('Cross anything out and write the right bucket next to it.\n\n')
            for b in BUCKETS:
                items = sorted(mapped.get(b, []), key=lambda x: -x[1])
                f.write(f'## {b} ({sum(n for _,n in items)} tags)\n\n')
                f.write(', '.join(f'{g} ({n})' for g, n in items) + '\n\n')
            f.write(f'## Unmapped ({len(unmapped)} genres)\n\n')
            f.write(', '.join(f'{g} ({n})' for g, n in sorted(unmapped, key=lambda x:-x[1])) + '\n')
        print('wrote genre-mapping-review.md')
    else:
        print('\ntop unmapped:')
        for g, n in sorted(unmapped, key=lambda x:-x[1])[:40]:
            print(f'{n:6d}  {g}')

if __name__ == '__main__':
    main()
