"""Bounded review snapshot. Never packages vaults, credentials or browser state."""
import functools
import http.server
import json
import shutil
import threading
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('/tmp/pto-v15-review')
OUT.mkdir(parents=True, exist_ok=True)
# Only public application assets and published recruitment feeds. No localStorage,
# storage_state, vault files, private application records, cookies or tokens.
with zipfile.ZipFile(OUT / 'public-app.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in ROOT.rglob('*'):
        rel = p.relative_to(ROOT)
        if not p.is_file() or any(x.startswith('.') or 'vault' in x.lower() for x in rel.parts[:-1]):
            continue
        if len(rel.parts) == 1 and p.suffix in ('.js', '.css', '.html', '.md'):
            z.write(p, str(rel))
        elif rel.parts[0] in ('scripts', 'sources', 'tests', 'data', 'docs') and p.suffix in ('.py', '.json', '.js', '.mjs', '.md'):
            z.write(p, str(rel))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
errors = []
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(9000)
        page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)
        summary = page.evaluate('''() => ({version:window.PTO_CONFIG, title:document.title, text:document.body.innerText.slice(0,14000), bodyColor:getComputedStyle(document.body).backgroundColor, htmlData:{...document.documentElement.dataset}, bodyData:{...document.body.dataset}, runtime:window.PTO_FEED_RUNTIME, scripts:[...document.scripts].map(s=>s.src)})''')
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT / 'mobile.png'), full_page=True)
        summary['errors'] = errors
        (OUT / 'snapshot.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        browser.close()
finally:
    server.shutdown()
