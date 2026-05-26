#!/usr/bin/env python3
"""Pull ACCURATE current marketplace value per release via the live marketplace/stats
endpoint (the /releases/{id} lowest_price is stale). lowest current asking (GBP) +
num_for_sale. Anonymous, rate-limited ~25/min, checkpointed to discogs-values.csv."""
import csv, json, os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'benmpolak-collection-20260411-0944.csv')
OUT = os.path.join(HERE, 'discogs-values.csv')
UA = 'DJArchiveValuation/1.0 +https://benmpolak.github.io/dj-archive'

rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
done = {}
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT)):
        done[r['release_id']] = r
print(f"{len(rows)} releases; {len(done)} already fetched", flush=True)

fields = ['release_id','artist','title','year','format','lowest_gbp','num_for_sale']
def write_all():
    with open(OUT,'w',newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for rid,rec in done.items(): w.writerow(rec)

for row in rows:
    rid = row.get('release_id','').strip()
    if not rid or rid in done: continue
    url = f"https://api.discogs.com/marketplace/stats/{rid}?curr_abbr=GBP"
    lp, nfs = '', ''
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                d = json.loads(resp.read())
            nfs = d.get('num_for_sale', '')
            lpobj = d.get('lowest_price')
            lp = lpobj.get('value') if isinstance(lpobj, dict) and lpobj.get('value') is not None else ''
            break
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(60); continue
            elif e.code == 404: break
            else: time.sleep(5)
        except Exception:
            time.sleep(5)
    done[rid] = {'release_id':rid,'artist':row.get('Artist',''),'title':row.get('Title',''),
                 'year':row.get('Released',''),'format':row.get('Format',''),
                 'lowest_gbp':lp,'num_for_sale':nfs}
    if len(done) % 20 == 0:
        write_all(); print(f"  fetched {len(done)}/{len(rows)}", flush=True)
    time.sleep(2.5)

write_all()
print(f"DONE. {len(done)} releases written to {os.path.basename(OUT)}", flush=True)
