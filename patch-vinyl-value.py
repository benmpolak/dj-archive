#!/usr/bin/env python3
"""Inject `var VINYLVAL={total,n,items[]}` (top 100 by lowest Discogs asking price)
before MONTHLY, for the Most Valuable Vinyl stats panel."""
import csv, json, os, shutil, datetime, re

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
SRC = os.path.join(HERE, 'discogs-values.csv')

def price(r):
    try: return float(r['lowest_gbp'])
    except: return -1

rows = [r for r in csv.DictReader(open(SRC))]
priced = sorted([r for r in rows if price(r) >= 0], key=price, reverse=True)
total = round(sum(price(r) for r in priced))
items = [{'a':r['artist'],'t':r['title'],'p':round(price(r),2),
          'n':int(r['num_for_sale'] or 0),'id':r['release_id']} for r in priced[:100]]
VINYLVAL = {'total':total,'n':len(priced),'items':items}

html = open(ARCHIVE).read()
inject = 'var VINYLVAL=' + json.dumps(VINYLVAL, separators=(',',':'), ensure_ascii=False) + ';'
if 'var VINYLVAL=' in html:
    html = re.sub(r'var VINYLVAL=\{.*?\};', inject, html, count=1, flags=re.S)
else:
    html = html.replace('var MONTHLY={', inject+'\n'+'var MONTHLY={', 1)

shutil.copy(ARCHIVE, os.path.join(HERE, f"_backup-pre-vinylval-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"))
open(ARCHIVE,'w').write(html)
print(f"injected VINYLVAL: top {len(items)} of {len(priced)} priced, floor total £{total:,}")
