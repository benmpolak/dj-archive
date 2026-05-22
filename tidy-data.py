#!/usr/bin/env python3
"""One pass: merge Uncategorised spelling, dedupe exact artist+title, auto-assign
crates (from genre) and vibe (from audio features) to orphaned tracks. Conservative —
leaves anything ambiguous alone."""
import json, os, shutil
from datetime import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')

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
print(f"start: {len(DATA)} tracks")

UNCAT = {'Uncategorized', 'Uncategorised'}

# --- 1) normalize the Uncategorised spelling ---
for t in DATA:
    if t.get('c'):
        t['c'] = sorted({('Uncategorized' if c in UNCAT else c) for c in t['c']})

# --- 2) dedupe exact (first-artist, title), keep richest, merge crates/tags ---
def score(t):
    sid = str(t.get('sid',''))
    return (1 if len(sid)==22 else 0, 1 if t.get('vy') else 0,
            len([c for c in (t.get('c') or []) if c!='Uncategorized']),
            len(t.get('tags') or []))
groups = defaultdict(list)
for idx,t in enumerate(DATA):
    a = (t.get('a','').split(';')[0].strip().lower())
    k = (a, t.get('t','').strip().lower())
    if a and k[1]:
        groups[k].append(idx)
drop = set()
for k, idxs in groups.items():
    if len(idxs) < 2: continue
    idxs.sort(key=lambda i: score(DATA[i]), reverse=True)
    keep = idxs[0]
    kc = set(DATA[keep].get('c') or [])
    kt = set(DATA[keep].get('tags') or [])
    for i in idxs[1:]:
        kc |= set(DATA[i].get('c') or [])
        kt |= set(DATA[i].get('tags') or [])
        drop.add(i)
    kc -= {'Uncategorized'} if (kc - {'Uncategorized'}) else set()
    DATA[keep]['c'] = sorted(kc) if kc else ['Uncategorized']
    DATA[keep]['tags'] = sorted(kt)
DATA = [t for i,t in enumerate(DATA) if i not in drop]
print(f"deduped: removed {len(drop)} -> {len(DATA)} tracks")

# --- 3) auto-assign crates from genre (priority order; first match wins) ---
CRATE_RULES = [
    ('Jazz',          ['jazz','bebop','bop','swing','big band','fusion']),
    ('Brazilian',     ['samba','bossa','mpb','pagode','forro','forró','tropical','brazil','brasil','baile']),
    ('Afro & World',  ['afrobeat','afro','highlife','afropop','ethio','latin','salsa','cumbia','mambo','son ','reggae','dub','world','calypso','soca','rumba']),
    ('Hip Hop',       ['hip hop','hip-hop','rap','trip hop','trip-hop','boom bap']),
    ('Disco & Boogie',['disco','boogie','italo']),
    ('House',         ['house','garage','techno','acid','tech ','deep house']),
    ('Electronic',    ['electronic','electro','idm','breakbeat','drum and bass','dnb','jungle','dubstep','edm','synth','ambient electronic']),
    ('Funk',          ['funk','go-go','p-funk']),
    ('Soul & R&B',    ['soul','r&b','rnb','motown','gospel','doo-wop']),
    ('Downtempo',     ['downtempo','balearic','lounge','chillout','chill-out']),
    ('Indie & Rock',  ['rock','indie','folk','psych','pop','alternative','singer-songwriter','garage rock']),
]
def crate_from_genre(g):
    g = (g or '').lower()
    if not g: return None
    for crate, kws in CRATE_RULES:
        for kw in kws:
            if kw in g: return crate
    return None

# --- vibe from audio features (maps onto existing vocabulary) ---
def vibe_from_features(t):
    e=float(t.get('e') or 0); v=float(t.get('v') or 0); tp=float(t.get('tp') or 0); ins=float(t.get('ins') or 0)
    if e<0.35 and ins>=0.55: return 'Ambient'
    if e>=0.7 and tp>=120 and v>=0.45: return 'Peak Time'
    if ins>=0.6: return 'Instrumental Journey'
    if v>=0.7 and e>=0.5: return 'Sunshine'
    if v<0.35 and e<0.55: return 'Dark & Moody'
    if e<0.45: return 'Deep & Mellow'
    if v>=0.6: return 'Feel Good'
    if e>=0.55: return 'Groover'
    return 'Chill'

crate_set=0; vibe_set=0
for t in DATA:
    cur = [c for c in (t.get('c') or []) if c!='Uncategorized']
    if not cur:
        cr = crate_from_genre(t.get('g'))
        if cr:
            t['c'] = [cr]; crate_set+=1
    if not str(t.get('vb','')).strip():
        t['vb'] = vibe_from_features(t); vibe_set+=1
print(f"auto-crate assigned: {crate_set}")
print(f"auto-vibe assigned:  {vibe_set}")

# --- save ---
bak = os.path.join(HERE, f"_backup-pre-tidy-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
open(ARCHIVE,'w').write(html[:ds] + new_json + html[de:])
print(f"saved. backup: {os.path.basename(bak)}")
print(f"final: {len(DATA)} tracks")
