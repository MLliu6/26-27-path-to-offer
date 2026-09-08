#!/usr/bin/env python3
import json, shutil
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8000'
EMPTY=json.dumps({'schema_version':4,'generated_at':'2026-09-08T00:00:00Z','jobs':[]})
STATUS=json.dumps({'generated_at':'2026-09-08T00:00:00Z','catalog_count':0,'sources':[]})
def browser_path():
    for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        p=shutil.which(n)
        if p:return p
    raise RuntimeError('browser missing')
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':1200,'height':800})
    def route(r):
        u=r.request.url
        if '/data/' in u and u.endswith('.json') or '/data/' in u and '.json?' in u:
            if 'source_status' in u:r.fulfill(status=200,content_type='application/json',body=STATUS)
            else:r.fulfill(status=200,content_type='application/json',body=EMPTY)
        elif u.startswith('https://cdn.jsdelivr.net/'):r.abort()
        else:r.continue_()
    page.route('**/*',route)
    page.goto(BASE,wait_until='domcontentloaded')
    page.wait_for_function('window.PTO_WORKSPACE_V15',timeout=20000)
    page.locator('#themeBtn').click();page.wait_for_selector('#themePopover.show')
    def snap(tag):
        print('THEME_DIAG',tag,page.evaluate("""()=>({accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),strong:getComputedStyle(document.documentElement).getPropertyValue('--accent-strong').trim(),inline:document.documentElement.getAttribute('style'),v151:!!window.PTO_V151_PALETTE,idx:document.documentElement.dataset.accentIndex,btn:getComputedStyle(document.querySelector('.btn.primary')).backgroundColor,caption:document.querySelector('#activeThemeName')?.textContent,onclick:String(document.querySelector('[data-theme=\"3\"]')?.onclick).slice(0,220)})"""))
    snap('before')
    page.locator('[data-theme="3"]').click()
    page.wait_for_timeout(50)
    snap('after-click')
    print('THEME_DIAG direct-return',page.evaluate('window.PTO_V151_PALETTE && window.PTO_V151_PALETTE.paint(3)'))
    page.wait_for_timeout(20)
    snap('after-direct')
    b.close()
