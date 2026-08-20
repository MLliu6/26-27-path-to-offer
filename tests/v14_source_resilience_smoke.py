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


def compact_jobs():
    return {
        'schema_version':4,
        'generated_at':'2026-08-21T00:30:00+08:00',
        'jobs':[
            {'i':'a','c':'甲公司','r':'材料研发工程师','l':'北京','b':'2027届校园招聘','g':'2027届','e':'硕士','t':'2026-08-20','q':7,'x':'企业官网直连','u':'https://example.invalid/a','d':'材料研发 XRD SEM 热处理 工艺优化'},
            {'i':'b','c':'乙公司','r':'财务会计岗','l':'北京','b':'2027届校园招聘','g':'2027届','e':'本科及以上','t':'2026-08-20','q':5,'x':'权威招聘公告','n':'https://example.invalid/b-notice','d':'财务核算 预算管理 会计 财务报表'},
            {'i':'c','c':'丙公司','r':'软件研发工程师','l':'上海','b':'2027届校园招聘','g':'2027届','e':'本科及以上','t':'2026-08-20','q':4,'x':'国家就业平台','u':'https://example.invalid/c','d':'软件研发 Python C++'},
        ]
    }


def main():
    domestic=json.dumps(compact_jobs(),ensure_ascii=False)
    status=json.dumps({'generated_at':'2026-08-21T00:30:00+08:00','catalog_count':3,'sources':[{'name':'domestic-fixture','label':'国内公开源','ok':True,'count':3}]},ensure_ascii=False)
    flags={'fail_all':False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()

        def route(route):
            url=route.request.url
            if '/data/jobs_cn.json' in url:
                if flags['fail_all']: route.fulfill(status=503,body='down')
                else: route.fulfill(status=200,content_type='application/json',body=domestic)
            elif '/data/jobs_priority.json' in url:
                route.fulfill(status=503,body='priority down')
            elif '/data/priority_source_status.json' in url:
                route.fulfill(status=503,body='priority status down')
            elif '/data/source_status.json' in url:
                if flags['fail_all']: route.fulfill(status=503,body='status down')
                else: route.fulfill(status=200,content_type='application/json',body=status)
            elif '/data/jobs.json' in url and flags['fail_all']:
                route.fulfill(status=503,body='fallback down')
            elif url.startswith('https://cdn.jsdelivr.net/'):
                route.abort()
            else:
                route.continue_()

        page.route('**/*',route)
        page.goto(BASE,wait_until='domcontentloaded')
        page.wait_for_function("window.PTO_PRODUCT_V14 && window.PTO_FEED_RUNTIME && window.PTO_FEED_RUNTIME.state === 'degraded'",timeout=30000)
        page.wait_for_function("document.querySelector('#marketCount') && document.querySelector('#marketCount').textContent.replace(/,/g,'') === '3'",timeout=30000)
        health=page.locator('#feedHealth').inner_text()
        assert '部分信源降级' in health,health
        assert '3 岗位' in health,health
        assert page.locator('a.pto-source-open').count()>=1,'notice-only role must still expose one clickable recruitment source'

        # A manual refresh may lose every remote source. The product must retain
        # the already usable catalogue instead of turning the job market blank.
        flags['fail_all']=True
        page.locator('#refreshFeedBtn').click()
        page.wait_for_function("window.PTO_FEED_RUNTIME.usedPrevious === true",timeout=30000)
        assert page.locator('#marketCount').inner_text().replace(',','')=='3'
        health2=page.locator('#feedHealth').inner_text()
        assert '已保留上一版数据' in health2,health2
        assert '部分信源降级' in health2,health2
        assert page.locator('.market-card').count()==3
        context.close();browser.close()
    print('Path to Offer v1.4 source resilience smoke: PASS')
    return 0

if __name__=='__main__':raise SystemExit(main())