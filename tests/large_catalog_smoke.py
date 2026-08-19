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
    empty_priority=json.dumps({'schema_version':4,'generated_at':'2026-08-16T10:00:00Z','jobs':[]},ensure_ascii=False)
    status=json.dumps({'generated_at':'2026-08-16T10:00:00Z','catalog_count':COUNT,'cn_catalog_count':COUNT,'catalog_target':10000,'sources':[{'name':'fixture','label':'fixture','ok':True,'count':COUNT}]},ensure_ascii=False)
    priority_status=json.dumps({'generated_at':'2026-08-16T10:00:00Z','catalog_count':0,'sources':[]},ensure_ascii=False)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()
        def route(route):
            u=route.request.url
            if '/data/jobs_priority.json' in u:route.fulfill(status=200,content_type='application/json',body=empty_priority)
            elif '/data/jobs_cn.json' in u or '/data/jobs.json' in u:route.fulfill(status=200,content_type='application/json',body=payload)
            elif '/data/priority_source_status.json' in u:route.fulfill(status=200,content_type='application/json',body=priority_status)
            elif '/data/source_status.json' in u:route.fulfill(status=200,content_type='application/json',body=status)
            elif u.startswith('https://cdn.jsdelivr.net/'):route.abort()
            else:route.continue_()
        page.route('**/*',route)
        start=time.perf_counter();page.goto(BASE,wait_until='domcontentloaded')
        page.wait_for_function(f"document.querySelector('#marketCount') && document.querySelector('#marketCount').textContent.replace(/,/g,'') === '{COUNT}'",timeout=120000)
        page.wait_for_selector('#marketPager',timeout=30000)
        elapsed=time.perf_counter()-start
        cards=page.locator('.market-card')
        assert cards.count()<=60, f'unbounded card render: {cards.count()}'
        assert page.locator('#coverageChip').count()==1

        search=page.locator('#jobSearch');t0=time.perf_counter();search.fill('京东')
        page.wait_for_function("document.querySelector('#marketCount').textContent.replace(/,/g,'') === '3'",timeout=30000)
        search_elapsed=time.perf_counter()-t0
        assert page.locator('.market-card').count()==3
        assert all('京东' in page.locator('.market-card').nth(i).inner_text() for i in range(3))
        if elapsed>45:
            print(f'WARN: 60k initial load is slow on this runner: {elapsed:.2f}s')
        if search_elapsed>12:
            print(f'WARN: 60k exact search is slow on this runner: {search_elapsed:.2f}s')
        context.close();browser.close()
    print(f'Path to Offer 60k smoke: PASS load={elapsed:.2f}s search={search_elapsed:.2f}s payload={len(payload)} bytes')
    return 0

if __name__=='__main__':raise SystemExit(main())
