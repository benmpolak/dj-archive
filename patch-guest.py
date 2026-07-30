#!/usr/bin/env python3
"""Inject the guest layer (guest.js) into index.html (re-runnable).
Source lives in guest.js; injected as <script id="guest-js"> before </body>
so it runs after every other script. Styling lives in design-pass.css
(run patch-design.py after editing that)."""
import re

with open('guest.js') as f:
    js = f.read()

with open('index.html') as f:
    html = f.read()

block = '<script id="guest-js">\n' + js + '\n</script>\n'

if '<script id="guest-js">' in html:
    html = re.sub(r'<script id="guest-js">.*?</script>\n', lambda m: block,
                  html, count=1, flags=re.S)
    action = 'replaced'
else:
    html = html.replace('</body>', block + '</body>', 1)
    action = 'inserted'

with open('index.html', 'w') as f:
    f.write(html)
print(f'guest-js {action} ({len(js):,} bytes)')
