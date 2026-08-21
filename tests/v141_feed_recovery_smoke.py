#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from playwright.sync_api import sync_playwright

BASE='http://127.0.0.1:8000'


def browser_path():
    for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        path=shutil.which(name)
        if path:return path
    raise RuntimeError('Chrome/Chromium unavailable')


def fallback_feed():
    return {
        'schema_version':4,
        'generated_at':'2026-08-21T07:30:00+00:00',
        'catalog_count':2,
        'jobs':[
            {'i':'recovered-infra','c':'恢复测试科技','r':'AI Infra研发工程师','l':'北京','b':'2027届校园招聘','g':'2027届','e':'硕士','t':'2026-08-21','q':7,'x':'企业官网直连','u':'https://example.invalid/infra','d':'AI Infra vLLM CUDA 分布式推理系统'},
            {'i':'recovered-material','c':'恢复材料公司','r':'材料研发工程师','l':'北京','b':'2027届校园招聘','g':'2027届','e':'硕士','t':'2026-08-21','q':6,'x':'企业官方招聘源','u':'https://example.invalid/material','d':'材料研发 XRD SEM 工艺优化'},
        ]
    }


def main():
    fallback=json.dumps(fallback_feed(),ensure_ascii=False)
    domestic_status=json.dumps({
        'generated_at':'2026-08-21T07:30:00+00:00',
        'catalog_count':60000,
        'sources':[{'name':'domestic-live','label':'全国岗位联邦','ok':True,'count':60000}]
    },ensure_ascii=False)
    priority_status=json.dumps({
        'generated_at':'2026-08-21T07:31:00+00:00',
        'catalog_count':2649,
        'sources':[{'name':'priority-live','label':'重点企业官网快线','ok':True,'count':2649}]
    },ensure_ascii=False)
    flags={'fail_fallback':False}

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()

        def route(route):
            url=route.request.url
            if '/data/jobs_cn.json' in url:
                route.fulfill(status=503,body='catalog timeout fixture')
            elif '/data/jobs_priority.json' in url:
                route.fulfill(status=503,body='priority timeout fixture')
            elif '/data/priority_source_status.json' in url:
                route.fulfill(status=200,content_type='application/json',body=priority_status)
            elif '/data/source_status.json' in url:
                route.fulfill(status=200,content_type='application/json',body=domestic_status)
            elif '/data/jobs.json' in url:
                if flags['fail_fallback']:route.fulfill(status=503,body='fallback down')
                else:route.fulfill(status=200,content_type='application/json',body=fallback)
            elif url.startswith('https://cdn.jsdelivr.net/'):
                route.abort()
            else:
                route.continue_()

        page.route('**/*',route)
        page.goto(BASE,wait_until='domcontentloaded')
        page.wait_for_function("window.PTO_V141_FEED_READY === true",timeout=30000)
        page.wait_for_function("window.PTO_FEED_RUNTIME.jobsLoaded === 2",timeout=30000)

        runtime=page.evaluate('window.PTO_FEED_RUNTIME')
        assert runtime['expectedCatalogCount']==60000,runtime
        assert runtime['fallbackUsed'] is True,runtime
        assert runtime['catalogRecovered'] is True,runtime
        assert runtime['state']=='degraded',runtime
        assert page.locator('#marketCount').inner_text().replace(',','')=='2'
        assert '岗位聚合源目前是空的' not in page.locator('body').inner_text()

        # Match the user-reported interaction: explicit `infra` search must still
        # retrieve the recovered catalogue rather than showing a false empty pool.
        page.locator('#jobSearch').fill('infra')
        page.locator('.market-card[data-market-id="recovered-infra"]').wait_for(timeout=8000)
        assert 'AI Infra研发工程师' in page.locator('.market-card[data-market-id="recovered-infra"]').inner_text()

        # Once one catalogue has been recovered, even a later total outage must
        # keep that last-good list on screen.
        page.locator('#jobSearch').fill('')
        flags['fail_fallback']=True
        page.locator('#refreshFeedBtn').click()
        page.wait_for_function("window.PTO_FEED_RUNTIME.usedPrevious === true",timeout=30000)
        assert page.locator('#marketCount').inner_text().replace(',','')=='2'
        assert page.locator('.market-card').count()==2
        assert '岗位聚合源目前是空的' not in page.locator('body').inner_text()

        policy=page.evaluate('window.PTO_FEED_V141')
        assert policy['bodyTimeoutMs']['catalog']>=30000,policy
        assert policy['headerTimeoutMs']['catalog']>7000,policy
        context.close();browser.close()

    print('Path to Offer v1.4.1 feed recovery smoke: PASS')
    return 0

if __name__=='__main__':raise SystemExit(main())
