#!/usr/bin/env python3
"""Pull current marketplace value for each release in the Discogs collection CSV.
For each release_id: lowest current asking price (GBP) + number for sale.
Anonymous API, rate-limited ~25/min, checkpointed to discogs-values.csv so reruns resume."""
import csv, json, os, time, urllib.request, sys

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

for i, row in enumerate(rows):
    rid = row.get('release_id','').strip()
    if not rid or rid in done: continue
    url = f"https://api.discogs.com/releases/{rid}?curr_abbr=GBP"
    lp, nfs = '', ''
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                d = json.loads(resp.read())
            lp = d.get('lowest_price') if d.get('lowest_price') is not None else ''
            nfs = d.get('num_for_sale', '')
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(60); continue
            elif e.code == 404:
                break
            else:
                time.sleep(5)
        except Exception:
            time.sleep(5)
    done[rid] = {'release_id':rid,'artist':row.get('Artist',''),'title':row.get('Title',''),
                 'year':row.get('Released',''),'format':row.get('Format',''),
                 'lowest_gbp':lp,'num_for_sale':nfs}
    if (len(done)) % 20 == 0:
        write_all(); print(f"  fetched {len(done)}/{len(rows)}", flush=True)
    time.sleep(2.5)

write_all()
print(f"DONE. {len(done)} releases written to {os.path.basename(OUT)}", flush=True)
