#!/usr/bin/env python3
"""
One-off: tag the 112 tracks imported 2026-07-01 ("Playlists 2026-07-01")
with crates + vibes, assigned by ear/knowledge (same approach as
patch-tag-new-jun2026.py). Tracks already holding real crates from the
playlist mapping keep them; this merges crates in and fills empty vibes.
Skips deliberately left tracks (unknowns stay Uncategorized).
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

# sid: ([crates to merge], vibe)  — vibe '' = leave as is
TAGS = {
'7eGKbOhLhUGPGOtyEgnRhc': (['Hip Hop'], 'Chill'),                        # Bush Babees/Mos Def - The Love Song
'601TwN56ul71lEzt0hpA4N': (['Hip Hop','Jazz'], 'Soulful'),               # Guru/Erykah Badu - Plenty (jazz-rap dual)
'7i3uts4oif6heuRteCA0GV': (['Afro & World','House'], 'Groover'),         # Ismael Miranda/Joe Claussell
'spotify:local:Ladyhawke:Ladyhawke:Paris+Is+Burning:229': (['Indie & Rock'], 'Feel Good'),
'2TN9AzxcKsNkOIfbHOxipD': (['House','Disco & Boogie'], 'Groover'),       # D'Swing - Dream It (nu disco)
'0J935C9lkKcr1qPMWdk7pf': (['House'], 'Peak Time'),                      # Serious A - Diagonal Wave
'3aN98BUq8ictAeeb2UshaH': (['Indie & Rock'], 'Groover'),                 # Pearl & The Oysters - Lights Out
'6rRsvY4R2gM902KqjlPEHc': (['Jazz'], 'Soulful'),                         # STREETON/David Kayode
'6zZVbIL3XxvJ1sPLi52d2P': (['Jazz','Soul & R&B'], 'Soulful'),            # Audrey Powne - Broken Record
'3Bk6FqMdbOgAb9L8IaRUrO': (['Jazz','Funk'], 'Groover'),                  # Detroit Rising/Kaidi Tatham
'5hNsW0rhB86uj234uq3O0I': (['House'], 'Groover'),                        # Souldynamic - Equatoriale
'5BgFocmbca3IrmCpotjrXe': (['House','Jazz'], 'Groover'),                 # Kokoroko/musclecars remix (remix rule: dance crate)
'4x3ycJCIZiVMMsNlzsj2Cr': (['Soul & R&B'], 'Feel Good'),                 # The CJP Band - We Must Believe
'04k3l4ziEySpRlfKcnjmBA': (['Brazilian'], 'Sunshine'),                   # Curió Curió
'23T156dMcEz78BKQLUg0D6': (['Brazilian','Jazz'], 'Sunshine'),            # Dana and Alden/Marcos Valle - El Gaucho
'1kU5bxz2l6h5DyJxRYfXlP': (['Brazilian','Jazz'], 'Soulful'),             # Moyses Dos Santos
'5ceg5YYj7lux4FYdggnwsc': (['Electronic'], 'Ambient'),                   # Pye Corner Audio/Andy Bell
'3yfDT5djAWPFl5XpdplQcN': (['Afro & World'], 'Deep & Mellow'),           # Mad Professor dub
'10u9dzRjXnJNBoX6G8o9C9': (['Downtempo'], 'Ambient'),                    # Satoshi & Makoto
'7gtRdli8g0WIwLUSb7IY1t': (['Afro & World','House'], 'Groover'),         # Auntie Flo - Havana City
'6BUBXBwzQyk8S6f5JNdFXB': (['Soul & R&B'], 'Soulful'),                   # Zaska/Melina Malone
'0TlrHY8bUSpdolyX7pAWZf': (['House'], 'Groover'),                        # Akio Nagase - Creation Dub (acid house)
'0pyf8CPNPg7sK1kravJakS': (['Disco & Boogie'], 'Sunshine'),              # Don Laka/Prins Thomas edit
'6y29TaHBtVgC1toWoNnzmi': (['Jazz','House'], 'Groover'),                 # Bård Berg/James Girling
'3rYcRzz27T43kIjxb4hfHw': (['Soul & R&B'], 'Soulful'),                   # DVYN - In My Face
'3fB7N49ncsnENPMPLcDIDa': (['Jazz'], 'Instrumental Journey'),            # Richard Spaven
'29Obf0yYT5cppVWJLx9iu0': (['House'], 'Peak Time'),                      # Sounds Of Blackness - Frankie Knuckles mix
'3ym53HMEh5vKDS1ob7csgD': (['House','Disco & Boogie'], 'Sunshine'),      # Ben Gomori/Lauer
'6HT4DoI7GeMCrCDkmDbx6F': (['Jazz','Afro & World'], 'Instrumental Journey'), # Kelan Phil Cohran
'2WaV7wTVJjuOL4YNGxMpiU': (['Soul & R&B'], 'Chill'),                     # Flwr Chyld - Squeeze
'5a8H8e910AEJMf7gRPwVdF': (['Jazz','Afro & World'], 'Feel Good'),        # TRYPL - It's Coffee Time (latin jazz)
'4TcAobnLHB1kpV7erjqRSk': (['Jazz'], 'Feel Good'),                       # Malcolm Strachan - Step On It
'5edykchexKmpba2pdWs7Q9': (['Jazz'], 'Feel Good'),                       # Malcolm Strachan - Leave It All Behind
'3ezKmeFvq0TZ0nExFgrEf4': (['Funk'], 'Feel Good'),                       # MIA - Crime of Passion
'63O1XLEgaKfixF1559yeVa': (['Disco & Boogie'], 'Peak Time'),             # Camomilla/Whodamanny (italo)
'3AaS76Tumildq0wUe953YA': (['Funk','Soul & R&B'], 'Soulful'),            # Orgone/Fanny Franklin
'010RTvypvqNnv2I9TNJpBv': (['Indie & Rock'], 'Chill'),                   # Asara - With Love (bedroom pop)
'4Vp4adMpDPHcOwaKgyatFd': (['House'], 'Groover'),                        # Slxm Sol/LEGZDINA
'5ZCFbzZ8c1xAyyJhFdWH56': (['Indie & Rock'], 'Deep & Mellow'),           # Bedouine
'3Y200fbm7rCPesSiQYs7iE': (['Jazz'], 'Instrumental Journey'),            # Hill Collective (free jazz)
'4YsjP5uA3MBqJqj8s5Tt33': (['Jazz','House'], 'Feel Good'),               # Kyoto Jazz Massive - Samba Fusion Mix
'08NXZbmhDroOdEDOdvud7K': (['Brazilian'], 'Sunshine'),                   # Tiago Caetano/Céline Dessberg
'2djscOrpVy72m3643ug6nR': (['House','Disco & Boogie'], 'Peak Time'),     # Gerry Read - All Day
'5uZ7sIe129iw7KdgjPFaon': (['Brazilian'], 'Deep & Mellow'),              # MOMO. - Tranquilo
'4KfGOzIoWxlInD9SC5shSZ': (['Jazz'], 'Ambient'),                         # Nomieye/Rosie Turton
'1yaZAY2LyK4sH0PVr1cxcm': (['House','Disco & Boogie'], 'Peak Time'),     # Gerry Read - Golden Gallows
'7El9vBkHMM6ZzwHoPWdfF6': (['Jazz'], 'Instrumental Journey'),            # Your Brother's Keeper/Gary Bartz
'3F65puHG77k51mq6zNshku': ([], 'Groover'),                               # Luis Radio - Bazaar (House already)
'1q7C1SUl4wr3mtMazaa8Qs': (['House','Afro & World'], 'Groover'),         # Fatso 98/MDU aka TRP (3-step)
'1cgWOpTpDlrEQIRFAEm4yP': (['House'], 'Soulful'),                        # Jamie Woon - Shy One Remix (uk funky)
'1hfkbhZahXqwpLNXCXgsnt': (['Jazz'], 'Feel Good'),                       # Scrimshire
'6FYXuK9HekUj9y5QhFwgVS': (['Afro & World'], 'Sunshine'),                # Charlie's Roots - Calypso Zest
'0woMqHUiDdrHIHyamnen5n': (['House','Disco & Boogie'], 'Feel Good'),     # Dirty Channels - Semliki
'33E2bU4xRVvjuc6Y4dtk5k': (['Jazz','Funk'], 'Groover'),                  # Nate Smith/Kiefer/CARRTOONS - PEARL
'4Y720XaoVNVsoL1oNz1tAg': (['Jazz'], 'Deep & Mellow'),                   # Tom Furse Digs (library jazz)
'0UD514lKUYatjWSWhBhmcd': (['House'], 'Groover'),                        # Kerri Chandler - Kerriousity
'0rOtqQ5JBmyIKo9e0Bnc7k': (['Disco & Boogie'], 'Groover'),               # Mar De Novo - Over There
'1F1OWM6IeFXhJjnkLxJUur': (['Brazilian'], 'Deep & Mellow'),              # Slowdown - Sonho do Brasil (bossa)
'4lNtlaHFwPIuuvLWomfsxl': (['House'], 'Feel Good'),                      # Gayance/Antonio Dal Bó
'10ymfiNPHEc4XiOEyEkjd8': (['House'], 'Groover'),                        # Coflo - Won't Help It
'19sUISWZTlmr7VqKQLxKHv': (['House'], 'Groover'),                        # Coflo - Tell No Lies
'5QdQkKe4i62RftaExcQWvW': (['Jazz','Downtempo'], 'Instrumental Journey'),# Ancient Infinity Orchestra
'3jFr11QhgSAKaCqWTaI1Xo': (['House'], 'Peak Time'),                      # Scarlett O'Malley - The Dominator
'7LHd6sdK5Bro4f8EmprNAj': (['Afro & World'], 'Soulful'),                 # Johnny Clarke (lovers rock)
'5yIrCxFsYzWrSabeER5H06': (['Afro & World'], 'Soulful'),                 # Sandra Cross (lovers rock)
'4COxL75DuHhxGc8NxKa5Gj': (['Afro & World'], 'Deep & Mellow'),           # Aisha - Can You Feel It (dub)
'4QlxeQt20tRW86ruJHmyq8': (['Downtempo'], 'Groover'),                    # CHO CO PA... Dub Mix
'1PZ4HJqll1SJoLZPWIeRZG': (['Jazz','Electronic'], 'Ambient'),            # Akusmi/Daniel Brandt - Anima
'2u65kbmukMDOmAKnazdVDL': (['Brazilian'], 'Deep & Mellow'),              # Flávio Vasconcelos
'77B1TRhddJIof16KwS7IJd': (['Brazilian','Jazz'], 'Instrumental Journey'),# Marcelo Cabral/Sophia Chablau
'3ZYTerFILQDm1s9E4mfnIa': (['Downtempo'], 'Ambient'),                    # Robin Katz - The Moon (Hypnos)
'4TGLF83XeKnXgkquxXqxMf': (['Brazilian'], 'Chill'),                      # Ítallo - dorinana (new mpb)
'0yeURxDXfCeHCkecSj8b4H': (['Brazilian'], 'Chill'),                      # Ítallo/Tori - janeiro
'09Hcyt1ej9jnaWUSMvuHZ1': (['Brazilian','House'], 'Groover'),            # Pedro Mizutani
'0fn5lPwY76I7zIGg1EkRGY': (['Brazilian','House'], 'Peak Time'),          # MDA GROOVES - Brazuca Chic
'4Gb79xDPd1qUu6Rm8YCTbB': ([], 'Deep & Mellow'),                         # Groovecat/Miguel Migs (House already)
'0Kyk0oYgO8XEp27vJVIsGE': (['House'], 'Groover'),                        # Intr0beatz
'4kWxDgdXj2FB0pdInkBsP8': (['House','Jazz'], 'Groover'),                 # Henna Onna - Shibuya Oiran
'309KZCVpPVTYP3Eq2TRmRn': (['House'], 'Groover'),                        # Mr. G - That Special Place
'6dFMGoaI7TTDEyfbks3GBW': (['Disco & Boogie','Funk'], 'Feel Good'),      # Powerline - Brand New Remix (Mr Bongo)
'6FEoUAivWp39e4DPzHKeYs': (['Jazz'], 'Instrumental Journey'),            # Sven Wunder - Harmonica and...
'5bbs3ZFOj0UKhqqWt5gNHM': (['Jazz'], 'Instrumental Journey'),            # Sven Wunder - Jazz At Night
'5nZR6YRCKvYCXchMDpuIJ7': (['Jazz'], 'Ambient'),                         # Matthew Halsall - Water Street
'31ttUjNlj72yDf0JnddIRd': (['Jazz'], 'Instrumental Journey'),            # Sven Wunder - Natura Morta
'6W6iCHIlyiYq2oAWBrT3tt': (['Jazz'], 'Ambient'),                         # Matthew Halsall - Calder Shapes
'70hfEabX0GHnUMhintCbmx': (['Jazz'], 'Instrumental Journey'),            # Sven Wunder - Take a Break
'2qnBvk9wvOo4xMRAYR8fkX': (['Downtempo'], 'Ambient'),                    # Synergetic Voice Orchestra
'1DWwj8fpmVNQMHdK3SFdz0': (['Funk'], 'Feel Good'),                       # EWF - Faces
'23ldJVNXlsoWkTJ5YvWTiB': (['Afro & World'], 'Groover'),                 # Yassine Nana - Fatma
'0o9rzRmUNOQtVIN4V8vm1k': ([], 'Groover'),                               # Sanullim - Don't Go
'5QRpwwrmTOvMRGQHZiH1ft': ([], 'Peak Time'),                             # El Coco
'2NGWAXh6sisNpVHIAAlME0': ([], 'Sunshine'),                              # Minako Yoshida (city pop)
'7lxmaHXxi5Qid6w2iITsk2': ([], 'Feel Good'),                             # Loose Ends - Magic Touch
'2uh4xWYmi6FRaoZqmj8SaF': ([], 'Instrumental Journey'),                  # Love Unlimited Orchestra - Satin Soul
'7IIROrpimRPTQY0Xue5g2x': (['Afro & World','Soul & R&B'], 'Soulful'),    # Devon Russell - Darker Than Blue
'74YZpOmeeWAq0nFhmCiIHn': (['Soul & R&B'], 'Deep & Mellow'),             # Jorge Santana
'4m7qS1uHe7M0R9GcLVFB1n': (['Soul & R&B'], 'Soulful'),                   # Lisa Stansfield - Big Thing
'6GlqJG2mnJIL9dhVHku4JV': (['Afro & World'], 'Groover'),                 # Johnny Osbourne - Truth and Rights
'02UqF7ZCIvdORQrW2iijbg': (['Disco & Boogie'], 'Sunshine'),              # Gyratory Allstars remix
'42SoWrrncUjW7BXZutONZA': (['Hip Hop'], 'Chill'),                        # Illa J/Debi Nova (Yancey Boys)
'2W1wZG52PIlXihmHnNXE1G': (['Jazz','Hip Hop'], 'Groover'),               # Charlie Hunter/Mos Def - Creole
'3nYbDXMGIjKonGt3Lfpcbz': (['Jazz'], 'Soulful'),                         # [re:jazz]/Jhelisa - Inner City Life
'7n8mrMNDk5jLfTiiR79Znx': (['Brazilian','House'], 'Groover'),            # Natures Plan/Marc Mac - Broken Samba
'1HkdwtP9b0IPCediccZVtH': ([], 'Peak Time'),                             # Quincy Jones - Stomp (House kept: remix rule)
'0Jrt22NVunw9cWwHDhD5zo': ([], 'Groover'),                               # Slave - MAW Remix (House kept: remix rule)
'2iKOc0YdnY4jlJxzZvuFac': ([], 'Peak Time'),                             # CeCe Peniston/Silk Hurley
'42IDW44xRBucgRjQJU3R4q': ([], 'Soulful'),                               # Matthew Bandy/Josh Milan - Wish
'0b1nISgkOwwFkyvIp6A5KL': ([], 'Peak Time'),                             # Helen Sharpe/Ron Allen
'2GusVb7GpPoaEvPqpa89Ks': (['Disco & Boogie'], 'Groover'),               # DJ P-SOL - One of a Kind
# Deliberately left Uncategorized (can't place confidently):
# Joseph - Three O'Clock; Jaime Rosso - Walk; Khadija - Good
}

def parse_data(html):
    s = html.index('const DATA=') + len('const DATA=')
    depth = 0; in_str = False; esc = False; i = s
    while i < len(html):
        c = html[i]
        if esc: esc = False; i += 1; continue
        if c == '\\' and in_str: esc = True; i += 1; continue
        if c == '"': in_str = not in_str; i += 1; continue
        if not in_str:
            if c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0: return json.loads(html[s:i+1]), s, i+1
        i += 1

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)

valid_crates = set()
valid_vibes = set()
for t in DATA:
    for c in (t.get('c') or []): valid_crates.add(c)
    if t.get('vb'): valid_vibes.add(t['vb'])

for sid, (crates, vibe) in TAGS.items():
    for c in crates: assert c in valid_crates, f"bad crate {c}"
    if vibe: assert vibe in valid_vibes, f"bad vibe {vibe!r}"

by_sid = {t.get('sid'): t for t in DATA}
touched = 0; missing = []
for sid, (crates, vibe) in TAGS.items():
    t = by_sid.get(sid)
    if not t:
        missing.append(sid); continue
    cur = set(t.get('c') or []) - {'Uncategorized', 'Uncategorised'}
    cur |= set(crates)
    t['c'] = sorted(cur) if cur else ['Uncategorized']
    if vibe and not t.get('vb'):
        t['vb'] = vibe
    touched += 1

print(f"Tagged {touched} tracks; {len(missing)} sids not found: {missing}")
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
with open(ARCHIVE, 'w') as f:
    f.write(html[:ds] + new_json + html[de:])
print("Saved.")
