#!/usr/bin/env python3
"""Inject THE DEALER into index.html as a single <script> before </body>.
Re-runnable: replaces the existing dealer block if present. Source lives in dealer.js."""
import re, shutil, sys, datetime

with open('dealer.js') as f:
    js = f.read()

with open('index.html') as f:
    html = f.read()

block = '<script id="dealer-js">\n' + js + '\n</script>\n'

if '<script id="dealer-js">' in html:
    html = re.sub(r'<script id="dealer-js">.*?</script>\n', lambda m: block, html, count=1, flags=re.S)
    action = 'replaced'
else:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy('index.html', f'_backup-pre-dealer-{stamp}.html')
    html = html.replace('</body>', block + '</body>', 1)
    action = 'inserted'

with open('index.html', 'w') as f:
    f.write(html)
print(f'dealer block {action} ({len(js):,} bytes)')
