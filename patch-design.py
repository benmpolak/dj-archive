#!/usr/bin/env python3
"""Inject the design-pass override stylesheet into index.html (re-runnable).
Source lives in design-pass.css; injected as <style id="design-pass"> before </body>
so it cascades after every other rule."""
import re, shutil, datetime

with open('design-pass.css') as f:
    css = f.read()

with open('index.html') as f:
    html = f.read()

block = '<style id="design-pass">\n' + css + '\n</style>\n'

if '<style id="design-pass">' in html:
    html = re.sub(r'<style id="design-pass">.*?</style>\n', lambda m: block, html, count=1, flags=re.S)
    action = 'replaced'
else:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy('index.html', f'_backup-pre-design-{stamp}.html')
    html = html.replace('</body>', block + '</body>', 1)
    action = 'inserted'

with open('index.html', 'w') as f:
    f.write(html)
print(f'design-pass {action} ({len(css):,} bytes)')
