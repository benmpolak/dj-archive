#!/usr/bin/env python3
"""Make the Plays column always visible (don't hide it on narrow screens) and bolder."""
import os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'index.html')
html = open(ARCHIVE).read()

before = html.count(".col-bpm,.col-pc,")
# stop hiding col-pc wherever it was grouped with col-bpm's responsive hides
html = html.replace(".col-bpm,.col-pc,", ".col-bpm,")
# bolder, slightly larger column
assert html.count(".col-pc{width:4%;font-family:'JetBrains Mono',monospace;font-size:0.72em;text-align:right;color:var(--accent)}") == 1
html = html.replace(
  ".col-pc{width:4%;font-family:'JetBrains Mono',monospace;font-size:0.72em;text-align:right;color:var(--accent)}",
  ".col-pc{width:5%;font-family:'JetBrains Mono',monospace;font-size:0.82em;text-align:right;color:var(--accent);font-weight:700}")

bak = os.path.join(HERE, f"_backup-pre-pcvis-{datetime.now():%Y%m%d-%H%M%S}.html")
shutil.copy(ARCHIVE, bak)
open(ARCHIVE,'w').write(html)
print(f"un-hid col-pc in {before} responsive rule(s); column now bold + always visible.")
print("backup:", os.path.basename(bak))
