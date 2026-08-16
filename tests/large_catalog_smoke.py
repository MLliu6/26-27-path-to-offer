#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from playwright.sync_api import sync_playwright

BASE='http://127.0.0.1:8000'
COUNT=60000


def browser_path():
    for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        p=shutil.which(name)
        if p:return p
    raise RuntimeError('Chrome/Chromium unavailable')


def feed():
    jobs=[]
    for i in range(COUNT):
        company='京东' if i in (777,17777,37777) else f'企业{i%1200:04d}'
        role='大模型推理系统工程师' if i%19==0 else ('CUDA算子工程师' if i%23==0 else f'软件研发工程师 {i%70}')
        jobs.append({'id':f'job-{i}','company':company,'role':role,'location':'北京' if i%2==0 else '上海','updated_at':'2026-08-15','apply_url':f'https://example.invalid/{i}','jd':'vLLM CUDA KV Cache PagedAttention' if i%19==0 else '软件研发 Python C++'})
    return {'schema_version':3,'generated_at':'2026-08-16T10:00:00Z','jobs':jobs}


def main():
    payload=json.dumps(feed(),ensure_ascii=False,separators=(',',':'))
    status=json.dumps({'generated_at':'2026-08-16T10:00:00Z','catalog_count':COUNT,'catalog_target':10000,'sources':[{'name':'fixture','label':'fixture','ok':True,'count':COUNT}]},ensure_ascii=False)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()
        def route(route):
            u=route.request.url
            if '/data/jobs.json' in u:route.fulfill(status=200,content_type='application/json',body=payload)
            elif '/data/source_status.json' in u:route.fulfill(status=200,content_type='application/json',body=status)
            elif u.startswith('https://cdn.jsdelivr.net/'):route.abort()
            else:route.continue_()
        page.route('**/*',route)
        start=time.perf_counter();page.goto(BASE,wait_until='domcontentloaded')
        # `marketJobs` is a top-level lexical `let`, intentionally not a window
        # global. Wait on the primary user-visible result count to prove the real
        # 60k feed passed through the post-enhancement renderer.
        page.wait_for_function(f"document.querySelector('#marketCount') && document.querySelector('#marketCount').textContent.replace(/,/g,'') === '{COUNT}'",timeout=35000)
        page.wait_for_selector('#marketPager',timeout=15000)
        elapsed=time.perf_counter()-start
        cards=page.locator('.market-card')
        assert cards.count()<=60, f'unbounded card render: {cards.count()}'
        assert page.locator('#coverageChip').count()==1

        search=page.locator('#jobSearch');t0=time.perf_counter();search.fill('京东')
        page.wait_for_function("document.querySelector('#marketCount').textContent.replace(/,/g,'') === '3'",timeout=5000)
        search_elapsed=time.perf_counter()-t0
        assert page.locator('.market-card').count()==3
        assert all('京东' in page.locator('.market-card').nth(i).inner_text() for i in range(3))
        # v0.7's precomputed retrieval index measured 0.89 s on this 60k Chrome
        # fixture in GitHub Actions. Keep generous CI headroom while preventing a
        # regression back to the old ~4.5 s exact-search path.
        assert elapsed<10, f'60k initial load too slow in CI: {elapsed:.2f}s'
        assert search_elapsed<3, f'60k exact search too slow in CI: {search_elapsed:.2f}s'
        context.close();browser.close()
    print(f'Path to Offer 60k smoke: PASS load={elapsed:.2f}s search={search_elapsed:.2f}s payload={len(payload)} bytes')
    return 0

if __name__=='__main__':raise SystemExit(main())
