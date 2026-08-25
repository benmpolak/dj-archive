#!/usr/bin/env python3
"""Tag the 4 tracks imported from the 25 Aug playlist CSVs (vibes by ear)."""
import json, os, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

TAGS = {
    '3VGRvSjWd1dssTbjg5RE60': 'Soulful',    # Josh Milan - I Will Wait (Honeycomb Vocal)
    '42e0qhlpWGgNz5Jjp7laQq': 'Peak Time',  # Mateo & Matos / KOT - The Real Thing
    '7aRzXcBwNHsO3fgyG4DPwJ': 'Feel Good',  # Janice McClain - Smack Dab In the Middle
    '4PouQ1twZgKiVBHhzeIJ5O': 'Feel Good',  # Leon Patillo - Saved (gospel boogie)
}

def parse_data(html):
    ds = html.index('const DATA=') + len('const DATA=')
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

html = open(ARCHIVE).read()
DATA, ds, de = parse_data(html)
n=0
for t in DATA:
    vb = TAGS.get(t.get('sid'))
    if vb and not t.get('vb'):
        t['vb']=vb; n+=1
bak = os.path.join(HERE, f"_backup-pre-tag20260825-{datetime.datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html[:ds] + json.dumps(DATA, separators=(',',':'), ensure_ascii=False) + html[de:])
print(f"tagged {n} tracks")
