#!/usr/bin/env python3
"""
One-off: tag the 117 tracks imported 2026-06-09 with crates + vibes
(hand-assigned by ear/knowledge), strip the '& country' junk genre
fragment archive-wide (Discogs 'Folk, World, & Country' comma-split),
and backfill missing album/year via Spotify search.

Usage: SPOTIFY_CLIENT_SECRET=xxx python3 patch-tag-new-jun2026.py
"""
import json, os, re, sys, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CID = '16c7847eda6740e3a02fd2d334bc803a'

# sid: ([crates], vibe)
TAGS = {
'2RdEjF3YgyMorL87zokCPf': (['Disco & Boogie'], 'Feel Good'),          # Another Taste - Into The Night
'02SOhOwBuyI2KuphYzQLqq': (['Soul & R&B'], 'Soulful'),                # Fire Water - Twilight
'2JG4IB3NbFFkzBUqp5IZBO': (['Jazz'], 'Instrumental Journey'),         # Resavoir - Memories of Dreams
'7wfzUFCxieKcbQ0ESX0jXK': (['Soul & R&B'], 'Soulful'),                # Leroy Hutson - Trust My Heart
'3iY4XSXdobrQowOedmptpK': (['Jazz'], 'Instrumental Journey'),         # Work Money Death - Brother Earl
'70nS54MJFb5rQVVOfGSSUo': (['Jazz'], 'Instrumental Journey'),         # MdCL - Horses OST
'6a6b2AkbbacK5f0KRFXqqu': (['Jazz'], 'Deep & Mellow'),                # Blue Earth Sound - Lover's Rock
'4lFTujJbK8oaIXlAOwZ9Xy': (['Jazz'], 'Deep & Mellow'),                # Blue Earth Sound - Half & Half
'4Jyn773RMejK4QkJa2w18T': (['Disco & Boogie'], 'Feel Good'),          # Jeroboam - See The Light
'4Tf7IW0WioSsChyDMy5EIJ': (['Downtempo', 'Hip Hop'], 'Chill'),        # FloFilz - Atelier
'7tnUYUOMmT6JQXWkVMLuAv': (['House'], 'Groover'),                     # Red Rack'Em - Secret Banger
'3MnDs1gRXCMCUgBXBITKj5': (['House'], 'Groover'),                     # Coflo - Jambala
'3ydklsO5ykXCVFb8iSEKEC': (['House'], 'Peak Time'),                   # Louie Vega - One Dream
'5dc0ODIlUrlXMf8D95F30T': (['House', 'Afro & World'], 'Groover'),     # Boricuba - Puertorro
'0adIBPfUdFtCT2cEuHt0px': (['Jazz'], 'Instrumental Journey'),         # Payton/Butcher Brown - Pursuance
'1Ju8hG7pNcfatD7EQiFUM0': (['Jazz'], 'Deep & Mellow'),                # MADELEINE/Marysia Osu
'55blUYxq9atyfCwtxvWvLG': (['Jazz'], 'Deep & Mellow'),                # Tara Clerkin Trio - Lazy Daisy
'5VeTGJ0UQ4Fa9YgaN6evBb': (['House'], 'Deep & Mellow'),               # Mr. Fingers - April Rain
'6ahoTO4YWtXB58biFkHllu': (['House'], 'Groover'),                     # Ron Trent - Electric Jungle
'2Dle2v6GO7kGCWOdGkzmKi': (['Brazilian', 'Jazz'], 'Sunshine'),        # Brazilian Spirit
'1XLCwiOZqIBLOObrWxBJaE': (['Soul & R&B', 'Disco & Boogie'], 'Soulful'),  # Patchwork Inc/Lynda Dawn
'2MpOzMBxlxrT0DuVxs65tK': (['Soul & R&B'], 'Soulful'),                # Sugar Bear - What About Me Girl
'1EUyHxXSbB3zFFF8iBsUtO': (['House'], 'Groover'),                     # Frits Wentink
'2ck5LysJdg1BbMqaLzr0XT': (['Indie & Rock'], 'Deep & Mellow'),        # Aldous Harding - Coats
'6TUuFqjLr75UKlKiR1HimR': (['House'], 'Groover'),                     # Sum of Its Parts - Hello High
'7aRIYgVbrwcEchpN7wQIQf': (['Soul & R&B'], 'Soulful'),                # Mica Paris
'7ME1spM3HTTbFRGxNm6F3I': (['Jazz'], 'Instrumental Journey'),         # Sultan Stevenson - El Roi
'0slTpNHblTjQ5qr3ji8FUx': (['Jazz'], 'Soulful'),                      # Collettivo Immaginario - Vento Eterno
'7khl86Ck9I8TD0Kj3PnfKB': (['Indie & Rock'], 'Deep & Mellow'),        # Doves - Lean Into The Wind
'0BqmqZkDutBZetCYQm1bzw': (['Funk'], 'Groover'),                      # Sure Fire Soul Ensemble - Gemini
'5rffvBl5fCAGCW6hdTZ3q9': (['Jazz', 'Afro & World'], 'Feel Good'),    # Kokoroko - Sweetie
'3sOEXZbg80FPnSBIvhy9Qz': (['Jazz'], 'Soulful'),                      # Allysha Joy/Finn Rees - Murmuring
'6NOyNWrvfwkLujsf3GM1Mb': (['Funk', 'Disco & Boogie'], 'Feel Good'),  # Psychic Mirrors - Charlene II
'7BNnvW8MBSBR3BjgfGy8fa': (['Downtempo'], 'Ambient'),                 # Kuniyuki - Open Window
'4XjaJ35W8w9Fj404LgUvA8': (['Downtempo', 'Hip Hop'], 'Chill'),        # FloFilz/Kuroda
'2Ef5pvpE2zVFqAQWm6eK59': (['Soul & R&B'], 'Feel Good'),              # CJP Band - You and Me and the Music
'5F3i7IC2tyDXPffQmsqOlc': (['House'], 'Groover'),                     # Kourtesis/Daphni - Unidos
'1TWz6EODmucHiVAt9nT1JX': (['Brazilian', 'Soul & R&B'], 'Sunshine'),  # El Michels/Roge - Magica
'6mMXWQDmEvFDUhaXXvMfCC': (['Soul & R&B'], 'Soulful'),                # Yazmin Lacey - Teal Dreams
'6MGDifi2vBHgHLpqCUmX16': (['Soul & R&B'], 'Deep & Mellow'),          # El Michels/Clairo - Anticipate
'03GiaAHNWoEXKgAi9eFz21': (['Jazz'], 'Deep & Mellow'),                # Blue Earth Sound - On the Court
'69NtJs5EuK2aZOrlpkOkK8': (['Disco & Boogie'], 'Feel Good'),          # Another Taste/Arp Frique - Peace Call
'1OWepP1RjA1iFz6hRJVzHu': (['Soul & R&B'], 'Deep & Mellow'),          # Eddie Chacon - Lay Low
'3TBcLm9UivNqbzGkYFaA5T': (['Indie & Rock'], 'Deep & Mellow'),        # Doves - Saint Teresa
'5xGo1MzhQn0LddjOz5NfN5': (['Jazz'], 'Groover'),                      # EJT/Kassa Overall - It's Okay
'1EUerWe5DJvtIT97ofvTcx': (['Electronic'], 'Groover'),                # Kaidi Tatham - So Happy
'7F1pxaP8lAkEtG3ETqXZuL': (['Jazz'], 'Instrumental Journey'),         # MdCL - heart
'5bSJLs4dQBrTBbIHfNFYuX': (['Jazz'], 'Instrumental Journey'),         # Sultan Stevenson - Purpose
'5pziINPfppwxfoBkCQ1uDJ': (['Jazz'], 'Groover'),                      # Don Glori - Brown Eyes
'4Kp6PKl4GKxtIvcrD3S9cJ': (['Indie & Rock'], 'Deep & Mellow'),        # Doves - A Drop In The Ocean
'5pa4nSXGhO0zWTJDLICAKy': (['Soul & R&B'], 'Deep & Mellow'),          # Eddie Chacon - Let The Devil In
'6HPjnl2sZKK2v6YmqOUwSh': (['Jazz'], 'Instrumental Journey'),         # Sultan Stevenson
'6Ywv2CceCNc96SFkqbCJ4I': (['Electronic'], 'Groover'),                # Gibin/Kaidi - Strength in Numbers
'6LC2huAiqbfCp5wLDs6geT': (['Funk'], 'Groover'),                      # Sure Fire - Las Olas
'5MEOB4iiBH6iSNL0dOfQ31': (['Soul & R&B'], 'Sunshine'),               # Eddie Chacon - Good Sun
'5DzTAh6gkAqw4VioPHuLXw': (['Brazilian'], 'Sunshine'),                # Samba De Flora
'2tbDr90KoG4ZFyI5StbI39': (['Jazz'], 'Groover'),                      # EJT - Wanna Die
'25wN2qVeNNvBWIXDwYLME2': (['Jazz'], 'Groover'),                      # Zeitgeist FEE - Just One Bump
'33gYM6ZfRWstTCvdLfbIl5': (['Soul & R&B'], 'Soulful'),                # Jessie Ware - Wildest Moments
'6D6OAmHtfrohw1lH3ISgps': (['House'], 'Deep & Mellow'),               # Alex Kassian - Body Singer
'1hzOoLaNKK7cVpNKnpwZs8': (['Jazz'], 'Instrumental Journey'),         # Sven Wunder - Daybreak
'3aWWdmdsBva7kiOnacL4tf': (['Jazz', 'Afro & World'], 'Feel Good'),    # Kokoroko - Just Can't Wait
'6A65Ym6B8M1mWEz14cdNRi': (['Soul & R&B'], 'Sunshine'),               # Marla Kether - Morning Light
'2w30W8DtzFfUAqakTaeV78': (['Disco & Boogie'], 'Sunshine'),           # Nu Genea - Scialla
'6T8BO4rFC9mRXASSioFFvc': (['Jazz'], 'Deep & Mellow'),                # Okonski - Axes
'5nwMTvSdLRXfj9mOXPNP7h': (['Soul & R&B'], 'Chill'),                  # Sparklmami - fajas
'0Pq0mOdgFXTezl6mMt8a39': (['Brazilian', 'Jazz'], 'Sunshine'),        # Deodato - San Juan Sunset
'2qQZT88SgU10wNn59XIAzg': (['Downtempo'], 'Chill'),                   # Slim./Merryn Jeann
'5cL9apuZP2KhE9C5fZwFbo': (['Soul & R&B', 'Disco & Boogie'], 'Soulful'),  # Glenda Mcleod
'0UlC3u4AysiMgEDqpoigXB': (['Jazz'], 'Sunshine'),                     # ventoux^ - In Brasil
'243nAji1iUHiGkcKWjyFyD': (['Jazz'], 'Deep & Mellow'),                # Okonski/Cochemea - Flying
'177No3z2IF2FVeUA5IvJe6': (['House'], 'Groover'),                     # Alex Nut/SOIP - The Message
'71tZq2cxfuMaE1KkS9mjj7': (['Electronic'], 'Groover'),                # MJK - Late To Camberwell
'1EYKFRSKHCIqro04NtlG70': (['Electronic'], 'Groover'),                # Zed Bias/MJK - Keep On Livin'
'6awfvw5ybmxUT8tv7EaJjr': (['Soul & R&B', 'Funk'], 'Soulful'),        # 1619 Bad Ass Band
'0ajcBeNXFmjucpy4Kt6Nnw': (['House'], 'Groover'),                     # D Wynn - Use Me
'3OhPxSKeQotvgquG6dTWCP': (['Soul & R&B'], 'Chill'),                  # Sparklmami - grounded
'2K5JOg7XsDfBr7cIkvOz8t': (['Jazz'], 'Deep & Mellow'),                # TCT - Ups & Downs
'4XPC8S3jNd7m54H9tAgBwq': (['Jazz'], 'Deep & Mellow'),                # Rachel Kitchlew - Spook
'67mVuqjqUtSi86fFjshoom': (['Electronic'], 'Groover'),                # IZCO - Wonderluv
'4ixXjZRzQm4mIJg0L4oK9S': (['Soul & R&B'], 'Feel Good'),              # S. Fidelity/Jerome Thomas
'1eekygIiUM17kmal26mT56': (['Downtempo'], 'Chill'),                   # The Offline/Koralle
'1Y5Iq070TALg3wFy5igJw4': (['House'], 'Soulful'),                     # Studio Apartment - Flight
'7u5a7COMP2zqzYSFjmKsDa': (['Funk'], 'Instrumental Journey'),         # Puccio Roelens - Slip Back
'61HwloDTTfO6JkdZogaDjD': (['House'], 'Feel Good'),                   # Close Counters/Crackazat
'1Sl9j3iGrrCJgTV6CRoHI5': (['Downtempo', 'Hip Hop'], 'Chill'),        # FloFilz/Matt Wilde
'3HDruqpn5X2qvzJdHnqgpq': (['Jazz', 'Funk'], 'Groover'),              # Roy Ayers - Mystic Voyage
'6pRB7l61iswaH1jUlzEcrx': (['House', 'Brazilian'], 'Sunshine'),       # Midan - Cachasamba
'7ekhXZLBmHJWBDZ5JoioDF': (['Jazz'], 'Groover'),                      # Don Glori - Power
'4MqRMWWM518FViRvEbo0Gl': (['Jazz'], 'Groover'),                      # Don Glori - Ron Song
'4Lm16xRBk71F4BJ3w9XQAB': (['Brazilian', 'Jazz'], 'Sunshine'),        # Azymuth - Arabuta
'1cAeCysIh2Qd9H2mK1xe9p': (['House'], 'Deep & Mellow'),               # Hidden Spheres - Surrender Love
'43ktcnyJxM6XidVbKZpG13': (['Downtempo'], 'Deep & Mellow'),           # Spartacus (Nishihara rmx)
'09Btkoj4YIm36KVJqomiCE': (['Jazz'], 'Deep & Mellow'),                # BBNG/V.C.R - Found A Light
'41op4mtzsiSC6AIOmEepGg': (['Funk'], 'Feel Good'),                    # Plunky/Oneness Of Juju
'0ODz72aWsdWhKqgEmJYZ7Q': (['House'], 'Sunshine'),                    # Sampology - Morning Sun
'3i6GcEPDKsyChS4mkLFj1z': (['Soul & R&B'], 'Feel Good'),              # Divine Earth/Princess Nokia
'4KoXpA59hGJ4W7rpZzdsXm': (['Jazz', 'Afro & World'], 'Deep & Mellow'),# Kokoroko - Closer To Me
'4dYosmoU0IaYIHysWOvR9Z': (['Indie & Rock'], 'Deep & Mellow'),        # Doves - Cally
'7AaHNhB05A2yPXRSpeABJS': (['Soul & R&B'], 'Chill'),                  # Yaya Bey - raisins
'4RszGlnuRLgy4vkWixsBv5': (['Jazz'], 'Instrumental Journey'),         # Circling Sun - Flora and Fauna
'0edG7kXOUCRKekOSofl4Un': (['Soul & R&B'], 'Feel Good'),              # DJ Harrison/Yaya Bey - Stay Ready
'2ujKNljJhqbkTGMHWrJIhQ': (['Jazz'], 'Instrumental Journey'),         # Matthew Halsall
'7AVLgpaYZMSwyOLXATjET8': (['House'], 'Groover'),                     # Daphni/Caribou - Waiting So Long
'1wYmASn0HbMV8ANEGVwNxc': (['Soul & R&B'], 'Soulful'),                # Brooke Combe
'7gHLUnqivM9ArDog4Uutal': (['Indie & Rock'], 'Deep & Mellow'),        # Doves - Spirit Of Your Friend
'0iPRaGu0MkIfLHRjFfWedg': (['Soul & R&B'], 'Soulful'),                # Yazmin Lacey/TYSON - Water
'67SwYMxINP9xEqh8rNjQzF': (['Funk'], 'Groover'),                      # Zaimie - Black Velvet
'4cjVWyjOj5O8RD76xVx9cx': (['Brazilian'], 'Deep & Mellow'),           # Sessa - Nome de Deus
'3JH0EDQ4BvQaKiCFWfOhi5': (['Downtempo'], 'Deep & Mellow'),           # Da Lata - The Lonely City
'3NpJgGsYYpzhRdTmLnhJTk': (['House'], 'Groover'),                     # Toribio/musclecars - Be Honest
'2xMkMpcSyYI19Af3TXCGSy': (['House'], 'Groover'),                     # Session Victim/Eo
'6zQatNmJoxrWfgzxVYYxLj': (['Disco & Boogie'], 'Feel Good'),          # Another Taste - Run Into Love
'4jgHhVVSSpIWNoEXWfd0oG': (['Brazilian'], 'Sunshine'),                # Ana Frango Eletrico/Marcos Valle
'3fJoN6gAwCEaRKoJPlxCOt': (['House'], 'Groover'),                     # Roland Clark/musclecars
'6LdIS1qUJYXBms7rAcKQ3z': (['Soul & R&B'], 'Soulful'),                # Yazmin Lacey - Wallpaper
'3hxax15bX4YjgMEDhcDGYc': (['Jazz'], 'Deep & Mellow'),                # Matt Wilde - Everyday Words
}

def parse_data(html):
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
    return json.loads(html[s:i+1]), s, i+1

def api_get(url, token):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

html = open(os.path.join(HERE, 'index.html')).read()
DATA, ds, de = parse_data(html)

tagged = vibed = decountried = 0
for t in DATA:
    sid = t.get('sid','')
    if sid in TAGS:
        crates, vibe = TAGS[sid]
        merged = (set(t.get('c') or []) | set(crates)) - {'Uncategorized','Uncategorised'}
        t['c'] = sorted(merged)
        tagged += 1
        if not t.get('vb'):
            t['vb'] = vibe; vibed += 1
    g = t.get('g') or ''
    if '& country' in g:
        parts = [p.strip() for p in g.split(',') if p.strip() and p.strip() != '& country']
        t['g'] = ', '.join(parts); decountried += 1

print(f'tagged crates on {tagged}, vibes on {vibed}, cleaned "& country" from {decountried}')

# Backfill missing album/year on the recent imports via search
secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
if secret:
    body = urllib.parse.urlencode({'grant_type':'client_credentials',
        'client_id':CID,'client_secret':secret}).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=body,
        headers={'Content-Type':'application/x-www-form-urlencoded'})
    token = json.load(urllib.request.urlopen(req))['access_token']
    fixed = 0
    for t in DATA:
        if t.get('sid') not in TAGS: continue
        if t.get('al') and t.get('r'): continue
        q = urllib.parse.quote(f"{t['t']} {t['a'].split(',')[0]}")
        try:
            d = api_get(f'https://api.spotify.com/v1/search?q={q}&type=track&limit=5', token)
        except Exception:
            continue
        for c in (d.get('tracks') or {}).get('items') or []:
            if not c: continue
            if c.get('name','').strip().lower() == t['t'].strip().lower():
                alb = c.get('album') or {}
                if not t.get('al'): t['al'] = alb.get('name','')
                if not t.get('r'):
                    m = re.match(r'^(\d{4})', alb.get('release_date') or '')
                    if m: t['r'] = int(m.group(1))
                fixed += 1
                break
        time.sleep(0.3)
    print(f'backfilled album/year on {fixed}')
else:
    print('no secret -> skipping album/year backfill')

open(os.path.join(HERE,'index.html'),'w').write(
    html[:ds] + json.dumps(DATA, separators=(',',':'), ensure_ascii=False) + html[de:])
print('saved')
