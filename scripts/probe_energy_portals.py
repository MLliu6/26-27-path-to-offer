#!/usr/bin/env python3
"""One-off diagnostic probe for CNPC/Sinopec public recruiting frontends."""
from __future__ import annotations
import re, shutil
from playwright.sync_api import sync_playwright

TARGETS=[('CNPC','https://zhaopin.cnpc.com.cn/'),('SINOPEC','https://job.sinopec.com/')]

def browser_path():
    for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        p=shutil.which(n)
        if p:return p
    raise RuntimeError('Chrome unavailable')

def main():
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        for name,url in TARGETS:
            ctx=b.new_context(viewport={'width':1360,'height':900},locale='zh-CN',ignore_https_errors=False)
            page=ctx.new_page();seen=set()
            def response(resp):
                u=resp.url
                if u in seen:return
                c=(resp.headers.get('content-type') or '').lower()
                if not ('json' in c or re.search(r'api|job|position|recruit|search|query|list|campus|graduate',u,re.I)):return
                seen.add(u);snippet=''
                try:
                    txt=resp.text()
                    if len(txt)<2_000_000:snippet=re.sub(r'\s+',' ',txt)[:900]
                except Exception as exc:snippet=f'<{type(exc).__name__}>'
                print(name,'RESP',resp.status,c,u,'SNIP',snippet,flush=True)
            page.on('response',response)
            try:
                page.goto(url,wait_until='domcontentloaded',timeout=50000);page.wait_for_timeout(12000)
                print(name,'TITLE',page.title(),flush=True)
                print(name,'BODY',re.sub(r'\s+',' ',page.locator('body').inner_text())[:3500],flush=True)
                for i in range(min(page.locator('a').count(),120)):
                    a=page.locator('a').nth(i)
                    try:
                        t=(a.inner_text() or '').strip();h=a.get_attribute('href') or ''
                        if re.search(r'招聘|校园|毕业|岗位|职位|job|campus|graduate',t+' '+h,re.I):print(name,'LINK',t[:100],h[:300],flush=True)
                    except Exception:pass
            except Exception as exc:print(name,'ERROR',type(exc).__name__,str(exc),flush=True)
            ctx.close()
        b.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
