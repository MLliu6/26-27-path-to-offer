#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE='http://127.0.0.1:8000'
STATE={
    'schemaVersion':2,
    'jobs':[{
        'id':'timeline-job',
        'company':'腾讯',
        'role':'后台开发工程师',
        'location':'北京',
        'salary':'',
        'direction':'后端 / 分布式系统',
        'priority':'A',
        'status':'assessment',
        'statusDate':'2026-08-30',
        'url':'https://careers.tencent.com/',
        'jd':'后台服务与分布式系统研发',
        'resumeVersion':'',
        'prepUrl':'',
        'notes':'',
        'matchAtSave':91,
        'timeline':[
            {'status':'discovered','date':'2026-08-10'},
            {'status':'wishlist','date':'2026-08-12'},
            {'status':'preparing','date':'2026-08-15'},
            {'status':'applied','date':'2026-08-18'},
            {'status':'assessment','date':'2026-08-30'},
        ],
    }],
    'reviews':[],
    'resumes':[],
    'activeResumeId':None,
    'assets':[],
    'decisions':{},
    'preferences':{'targetLocations':[],'targetDirections':[]},
}
EMPTY_JOBS={'schema_version':4,'generated_at':'2026-08-21T00:00:00Z','jobs':[]}
STATUS={'generated_at':'2026-08-21T00:00:00Z','catalog_count':0,'sources':[]}


def browser_path():
    for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        path=shutil.which(name)
        if path:return path
    raise RuntimeError('Chrome/Chromium unavailable')


def main():
    state_json=json.dumps(STATE,ensure_ascii=False,separators=(',',':'))
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()
        page.add_init_script(f"localStorage.setItem('pathToOffer.v0.2', {json.dumps(state_json)});")

        def route(route):
            url=route.request.url
            if '/data/jobs_priority.json' in url or '/data/jobs_cn.json' in url or '/data/jobs.json' in url:
                route.fulfill(status=200,content_type='application/json',body=json.dumps(EMPTY_JOBS,ensure_ascii=False))
            elif '/data/priority_source_status.json' in url or '/data/source_status.json' in url:
                route.fulfill(status=200,content_type='application/json',body=json.dumps(STATUS,ensure_ascii=False))
            elif url.startswith('https://cdn.jsdelivr.net/'):
                route.abort()
            else:
                route.continue_()
        page.route('**/*',route)
        page.goto(BASE,wait_until='domcontentloaded')
        page.wait_for_function('() => !!window.PTO_PIPELINE_TIMELINE_V14',timeout=20000)
        page.locator('button.nav-item[data-view="pipeline"]').click()

        card=page.locator('.job-card[data-job-id="timeline-job"]')
        timeline=card.locator('.pipeline-mini-timeline')
        timeline.wait_for(timeout=8000)
        text=timeline.inner_text()
        assert '状态轨迹' in text
        assert '已投递' in text and '8/18' in text, text
        assert '测评' in text and '8/30' in text, text
        assert timeline.locator('.pipeline-timeline-ellipsis').count()==1
        current=timeline.locator('.pipeline-timeline-node.current')
        assert current.get_attribute('data-timeline-status')=='assessment'
        assert '测评' in current.inner_text()

        # The mini timeline must update immediately after a real status edit.
        card.click()
        page.wait_for_selector('#jobForm:not(.hidden)')
        page.locator('#jobForm select[name="status"]').select_option('interview1')
        page.locator('#jobForm input[name="statusDate"]').fill('2026-09-05')
        page.locator('#jobForm button[type="submit"]').click()
        updated=page.locator('.job-card[data-job-id="timeline-job"] .pipeline-mini-timeline')
        updated.wait_for(timeout=8000)
        updated_text=updated.inner_text()
        assert '一面' in updated_text and '9/5' in updated_text, updated_text
        assert updated.locator('.pipeline-timeline-node.current').get_attribute('data-timeline-status')=='interview1'
        assert updated.locator('.pipeline-timeline-node').count()<=4

        context.close();browser.close()
    print('Path to Offer v1.4 kanban timeline smoke: PASS')
    return 0

if __name__=='__main__':raise SystemExit(main())