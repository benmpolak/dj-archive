#!/usr/bin/env python3
"""
One-off: tag the 16 vinyl tracks imported 2026-08-24 (Discogs export
benmpolak-collection-20260824-1545.csv — Jumani 45, Melodies International
Ariwa Sounds comp, Ron Trent Electric Jungle 12").
Ariwa comp came in as Afro & World from Discogs genres — it's Mad Professor's
label: Reggae & Dub. Keyed by (artist, title) from index 17305 onward.
Re-runnable: idempotent.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
START = 17305

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

# (artist, title) -> (crates REPLACE, vibe)
TAGS = {
    ("Jumani", "We Can Work It Out"): (['Soul & R&B'], 'Soulful'),
    ("Jumani", "Give Me Your Love"): (['Soul & R&B'], 'Soulful'),
    ("Sgt. Pepper", "Wake Up"): (['Reggae & Dub'], 'Groover'),
    ("Mad Professor;Joe Ariwa;Horace Andy", "Non Violence Dub"): (['Reggae & Dub'], 'Deep & Mellow'),
    ("U-Roy", "Old School Music"): (['Reggae & Dub'], 'Groover'),
    ("Kofi", "Didn't I"): (['Reggae & Dub'], 'Soulful'),           # lovers rock
    ("Sandra Cross", "Can't Let Dub Go"): (['Reggae & Dub'], 'Soulful'),
    ("Mad Professor;Mafia & Fluxy", "6 Million Dub"): (['Reggae & Dub'], 'Deep & Mellow'),
    ("Ariwa Posse;Abel Miller", "Everytime I See My Baby"): (['Reggae & Dub'], 'Soulful'),
    ("Kofi", "Losing Time For Love"): (['Reggae & Dub'], 'Soulful'),
    ("Aisha", "Can You Feel It (1990)"): (['Reggae & Dub'], 'Deep & Mellow'),
    ("Sister Nancy", "Live The Life You Love"): (['Reggae & Dub'], 'Groover'),
    ("Queen Omega", "Rocking & Popping"): (['Reggae & Dub'], 'Groover'),
    ("Ranking Ann", "Liberated Woman"): (['Reggae & Dub'], 'Groover'),
    ("Ron Trent Ft. Angel Luis Figueroa And Pablo Color", "Electric Jungle (Main)"): (['House'], 'Groover'),
    ("Ron Trent Ft. Angel Luis Figueroa And Pablo Color", "Electric Jungle (The Suite)"): (['House'], 'Deep & Mellow'),
}

with open(ARCHIVE) as f:
    html = f.read()
DATA, ds, de = parse_data(html)
print(f"{len(DATA)} tracks loaded")

n = 0; unmatched = dict(TAGS)
for t in DATA[START:]:
    key = (t['a'], t['t'])
    if key not in TAGS:
        continue
    crates, vb = TAGS[key]
    if t.get('c') != crates: t['c'] = crates; n += 1
    if vb and not t.get('vb'): t['vb'] = vb
    unmatched.pop(key, None)

print(f"updated: {n}")
if unmatched:
    print("WARNING — tags that matched nothing:")
    for k in unmatched: print("  ", k)

new_json = json.dumps(DATA, separators=(',', ':'), ensure_ascii=False)
with open(ARCHIVE, 'w') as f:
    f.write(html[:ds] + new_json + html[de:])
print("Saved.")
