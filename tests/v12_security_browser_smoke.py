#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE='http://127.0.0.1:8000'
EMPTY={'schema_version':4,'generated_at':'2026-08-18T00:00:00Z','jobs':[]}
STATUS={'generated_at':'2026-08-18T00:00:00Z','catalog_count':0,'sources':[{'name':'direct-test','label':'企业招聘官网 · 自主直连','url':'https://example.com','ok':True,'count':123,'error':''}]}
STATE={
    'schemaVersion':2,
    'jobs':[{'id':'job-1','company':'拼多多','department':'基础平台','role':'AI Infra研发工程师','location':'上海','salary':'','direction':'AI Infra','priority':'B','status':'applied','statusDate':'2026-08-18','url':'https://careers.pddglobalhr.com/','jd':'vLLM GPU 分布式系统','resumeVersion':'AI Infra版','prepUrl':'','notes':'','matchAtSave':88,'timeline':[{'status':'applied','date':'2026-08-18'}]}],
    'reviews':[],
    'resumes':[{'id':'cv-1','name':'AI Infra版','fileName':'resume.txt','rawText':'PRIVATE RESUME TEXT vLLM CUDA','profileVersion':5,'signals':{'primaryDirection':'AI Infra / 大模型推理系统','directions':['AI Infra / 大模型推理系统'],'skills':['vllm','cuda']}}],
    'activeResumeId':'cv-1','assets':[],'decisions':{},'preferences':{'targetLocations':['北京'],'targetDirections':['AI Infra / 大模型推理系统']}
}


def browser_path():
    for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
        path=shutil.which(name)
        if path:return path
    raise RuntimeError('Chrome/Chromium unavailable')


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page()
        page.add_init_script(f"localStorage.setItem('pathToOffer.v0.2',{json.dumps(json.dumps(STATE,ensure_ascii=False))});")

        def route_handler(route):
            url=route.request.url
            if '/data/jobs_priority.json' in url or '/data/jobs_cn.json' in url or '/data/jobs.json' in url:
                route.fulfill(status=200,content_type='application/json',body=json.dumps(EMPTY,ensure_ascii=False))
            elif '/data/priority_source_status.json' in url or '/data/source_status.json' in url:
                route.fulfill(status=200,content_type='application/json',body=json.dumps(STATUS,ensure_ascii=False))
            elif url.startswith('https://cdn.jsdelivr.net/'):
                route.abort()
            else:
                route.continue_()
        page.route('**/*',route_handler)
        page.goto(BASE,wait_until='domcontentloaded')
        page.wait_for_function("() => window.PTO_SECURE_ACCOUNT_V2 && window.PTO_V12_RENDERFIX_READY && document.querySelector('#githubLoginBtn').textContent.includes('账户')",timeout=20000)

        # Priority B remains text; company avatar is the first company character.
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector('.job-card .company-avatar')
        card=page.locator('.job-card').first
        assert card.locator('.company-avatar').inner_text()=='拼'
        assert '优先 B' in card.inner_text()
        assert card.locator('.company-avatar').inner_text()!='B'

        # Account UI is local-first and remote defaults to a user-owned vault repo.
        page.locator('#githubLoginBtn').click()
        page.wait_for_selector('.account-modal')
        modal=page.locator('.account-modal').inner_text()
        assert '本机加密账户' in modal and '跨设备 GitHub 加密仓库' in modal
        assert 'path-to-offer-vault' in modal and '零明文原则' in modal
        page.locator('#secureLocalUser').fill('candidate-one')
        page.locator('#secureLocalPass').fill('candidate-one-very-strong-password')
        page.locator('#secureLocalCreate').click()
        page.wait_for_function("() => window.PTO_ACCOUNT_SESSION && window.PTO_ACCOUNT_SESSION.username==='candidate-one'",timeout=10000)
        page.wait_for_function("() => Object.keys(localStorage).some(key => key.startsWith('pto.secure.local.v2.'))",timeout=10000)

        # Plain app state is removed and account payload is opaque ciphertext.
        storage=page.evaluate("Object.fromEntries(Object.entries(localStorage))")
        assert 'pathToOffer.v0.2' not in storage
        secure=[v for k,v in storage.items() if k.startswith('pto.secure.local.v2.')]
        assert secure and all('PRIVATE RESUME TEXT' not in value and '拼多多' not in value for value in secure)
        assert all('ciphertext' in value and 'AES-GCM-256' in value for value in secure)

        # Source details are visually gated and blurred before admin verification.
        page.locator('button.nav-item[data-view="discover"]').click()
        page.locator('#openSourcePanel').click()
        page.wait_for_selector('.admin-source-gate')
        assert '管理员信息已雾化' in page.locator('.admin-source-gate').inner_text()
        assert page.locator('.admin-source-blur').count()==1
        page.locator('#closeModal').click()

        # Local account can be exited and unlocked again with the same credentials.
        page.locator('#githubLoginBtn').click()
        page.locator('#secureLogout').click()
        page.locator('#githubLoginBtn').click()
        page.locator('#secureLocalUser').fill('candidate-one')
        page.locator('#secureLocalPass').fill('candidate-one-very-strong-password')
        page.locator('#secureLocalUnlock').click()
        page.wait_for_function("() => window.PTO_ACCOUNT_SESSION && window.PTO_ACCOUNT_SESSION.username==='candidate-one'",timeout=10000)
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector('.job-card .company-avatar')
        assert '拼多多' in page.locator('.job-card').first.inner_text()
        assert page.locator('.company-avatar').first.inner_text()=='拼'

        context.close();browser.close()
    print('Path to Offer v1.2.2 security browser smoke: PASS')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
