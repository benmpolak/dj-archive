#!/usr/bin/env python3
"""Remove the 'Jazz for Dan' tag from all tracks and the tag filter chip from the UI."""
import json, re, os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
TAG = 'Jazz for Dan'

def parse_data(html):
    data_start = html.index('const DATA=') + len('const DATA=')
    depth = 0; in_str = False; escape = False; i = data_start
    while i < len(html):
        c = html[i]
        if escape: escape = False; i += 1; continue
        if c == '\\' and in_str: escape = True; i += 1; continue
        if c == '"': in_str = not in_str; i += 1; continue
        if not in_str:
            if c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0: return json.loads(html[data_start:i+1]), data_start, i+1
        i += 1

with open(ARCHIVE) as f:
    html = f.read()

# backup
bak = os.path.join(HERE, f"_backup-pre-removejfd-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
print("backup ->", os.path.basename(bak))

DATA, ds, de = parse_data(html)
stripped = 0
for t in DATA:
    tags = t.get('tags') or []
    if TAG in tags:
        t['tags'] = [x for x in tags if x != TAG]
        stripped += 1
print(f"tracks stripped of tag: {stripped}")

new_json = json.dumps(DATA, separators=(',',':'), ensure_ascii=False)
html = html[:ds] + new_json + html[de:]

# remove the static filter chip for this tag
before = html.count(TAG)
html = re.sub(r'<div class="chip tag-chip" data-tag="Jazz for Dan">.*?</div>', '', html)
after = html.count(TAG)
print(f"'Jazz for Dan' string occurrences: {before} -> {after}")

with open(ARCHIVE, 'w') as f:
    f.write(html)
print("saved.")
