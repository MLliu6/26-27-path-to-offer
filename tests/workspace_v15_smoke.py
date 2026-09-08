"""Synthetic-only preservation and interaction regression. Never reads a real vault."""
import functools
import http.server
import json
import shutil
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/tmp/pto-v15-review');OUT.mkdir(exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
STATE={'schemaVersion':2,'jobs':[
    dict(id='j1',company='回归示例 A',role='AI Infra工程师',location='北京',priority='A',status='applied',statusDate='2026-09-01',timeline=[dict(status='applied',date='2026-09-01')],notes='PRESERVE ORIGINAL NOTES',resumeVersion='Original CV'),
    dict(id='j2',company='回归示例 B',role='编译器工程师',location='北京',priority='B',status='interview1',statusDate='2026-09-02',timeline=[dict(status='applied',date='2026-08-30'),dict(status='interview1',date='2026-09-02')])],
    'resumes':[dict(id='r1',name='Original CV',rawText='SYNTHETIC PRIVATE RESUME',uploadedAt='2026-09-01',signals={'skills':['cuda','vllm'],'directions':['AI Infra / 大模型推理系统']})],
    'activeResumeId':'r1','reviews':[],'assets':[],'decisions':{},'preferences':{'targetLocations':['北京'],'targetDirections':[]}}
JOBS={'schema_version':4,'jobs':[
    dict(i='a',c='回归企业',r='推理工程师',l='北京',u='https://example.com/#/job/11111111',z='11111111',s='direct-official:test',q=7,d='CUDA 推理系统 vLLM',b='2027校园招聘'),
    dict(i='b',c='回归企业',r='推理工程师',l='北京',u='https://example.com/#/job/22222222',z='22222222',s='direct-official:test',q=7,d='CUDA 推理系统 vLLM',b='2027校园招聘'),
    dict(i='c',c='待核验示例',r='算子工程师',l='北京',u='https://example.org/',s='curated-target:20260903',q=6,b='2027目标岗位·待官网实时复核')]}
STATUS={'generated_at':'2026-09-08T00:00:00Z','catalog_count':3,'sources':[dict(name='ok',ok=True,count=2),dict(name='fail',ok=False,count=0)]}
errors=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'),args=['--no-sandbox'])
        ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script("if(!sessionStorage.getItem('synthetic-seeded')){localStorage.setItem('pathToOffer.v0.2',"+json.dumps(json.dumps(STATE))+ ");sessionStorage.setItem('synthetic-seeded','1');}")
        def route(r):
            url=r.request.url
            if '/data/' in url:
                val={'jobs':[]} if 'supplemental' in url else STATUS if 'status' in url else JOBS
                r.fulfill(status=200,content_type='application/json',body=json.dumps(val))
            elif url.startswith('https:'):r.abort()
            else:r.continue_()
        page.route('**/*',route)
        page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
        page.wait_for_function('window.PTO_WORKSPACE_V15 && window.PTO_PRIORITY_FEED_READY',timeout=25000)
        page.wait_for_timeout(400)
        assert not errors,errors
        assert page.evaluate('marketJobs.length')==3
        assert '部分来源' in page.locator('#feedHealth').inner_text()
        page.locator('#jobSearch').fill('推理工程师');page.wait_for_timeout(250)
        assert page.locator('#jobMarketCards .market-card').count()==2
        page.locator('#v15Evidence').select_option('leads');page.locator('#jobSearch').fill('');page.wait_for_timeout(250)
        assert page.locator('#jobMarketCards .market-card').count()==1
        assert '待复核线索' in page.locator('.v15-badge.lead').inner_text()
        page.locator('#v15ResetFilters').click()
        page.screenshot(path=str(OUT/'v15-discover-light.png'))
        page.evaluate("document.documentElement.dataset.appearance='dark'")
        rgb=page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert rgb=='rgb(17, 17, 19)',rgb
        page.screenshot(path=str(OUT/'v15-discover-dark.png'))
        page.locator('[data-view="pipeline"]').click()
        page.locator('[data-quick-update="j1"]').first.click()
        page.locator('#v15Update [name=status]').select_option('interview1')
        page.locator('#v15Update [name=note]').fill('确认一面时间')
        page.locator('#v15Update [name=followUpAt]').fill('2026-09-10')
        page.locator('#v15Update button[type=submit],#v15Update .btn.primary').click()
        assert page.evaluate("state.jobs.find(j=>j.id==='j1').notes")=='PRESERVE ORIGINAL NOTES'
        assert page.evaluate("state.jobs.find(j=>j.id==='j1').timeline.length")==2
        page.locator('#v15Undo button').click()
        assert page.evaluate("state.jobs.find(j=>j.id==='j1').timeline.length")==1
        page.screenshot(path=str(OUT/'v15-pipeline-dark.png'))
        page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'v15-mobile.png'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),page.evaluate('document.documentElement.scrollWidth')
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#githubLoginBtn').click();page.locator('#secureLocalUser').fill('preservation-fixture')
        password='SYNTHETIC-only-test-password-2026'
        page.locator('#secureLocalPass').fill(password);page.locator('#secureLocalResume').check();page.locator('#secureLocalCreate').click()
        page.wait_for_function("window.PTO_ACCOUNT_SESSION?.username==='preservation-fixture' && !PTO_SECURE_ACCOUNT_V2.pending()",timeout=15000)
        page.wait_for_function("!document.querySelector('#quickModal').classList.contains('show')")
        page.evaluate("state.jobs[0].notes='LATEST PENDING WRITE';saveState(false)")
        page.locator('#githubLoginBtn').click();page.locator('#secureLogout').click()
        page.wait_for_function("!window.PTO_ACCOUNT_SESSION && document.querySelector('#githubLoginBtn').textContent.includes('已锁定')",timeout=15000)
        page.reload(wait_until='domcontentloaded');page.wait_for_function('window.PTO_WORKSPACE_V15',timeout=25000)
        page.wait_for_function("document.querySelector('#githubLoginBtn').textContent.includes('preservation-fixture')")
        page.locator('#githubLoginBtn').click();assert page.locator('#secureLocalUser').input_value()=='preservation-fixture'
        before=page.evaluate("JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('pto.secure.local.v2.'))))")
        page.locator('#secureLocalPass').fill('incorrect-but-long-password');page.locator('#secureLocalUnlock').click();page.wait_for_timeout(600)
        assert page.evaluate('!window.PTO_ACCOUNT_SESSION')
        assert page.evaluate("JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('pto.secure.local.v2.'))))")==before
        page.locator('#secureLocalPass').fill(password);page.locator('#secureLocalUnlock').click()
        page.wait_for_function("window.PTO_ACCOUNT_SESSION && !PTO_SECURE_ACCOUNT_V2.pending()",timeout=15000)
        recovered=page.evaluate('({jobs:state.jobs,resumes:state.resumes,preferences:state.preferences})')
        assert recovered['jobs'][0]['notes']=='LATEST PENDING WRITE'
        assert recovered['resumes'][0]['rawText']=='SYNTHETIC PRIVATE RESUME'
        assert recovered['jobs'][1]['timeline']==STATE['jobs'][1]['timeline']
        local=page.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
        assert password not in local and 'LATEST PENDING WRITE' not in local and 'SYNTHETIC PRIVATE RESUME' not in local
        assert 'pto.secure.snapshots.v15.' in local
        page.wait_for_function("!document.querySelector('#quickModal').classList.contains('show')")
        page.locator('[data-view="pipeline"]').click()
        with page.expect_download() as download:page.locator('#v15Backup').click()
        assert 'encrypted' in download.value.suggested_filename
        fresh=browser.new_context();freshpage=fresh.new_page();freshpage.route('**/*',route)
        freshpage.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded');freshpage.wait_for_function('window.PTO_WORKSPACE_V15',timeout=25000)
        assert 'preservation-fixture' not in freshpage.locator('#githubLoginBtn').inner_text()
        assert not errors,errors
        (OUT/'v15-test-result.json').write_text(json.dumps({'passed':True,'account_fixture':'synthetic only','console_errors':errors,'checks':['neutral dark','mobile overflow','exact job identity','lead filtering','quick update','undo','timeline preservation','resume preservation','flush on logout','reload account hint','wrong password non-destructive','no plaintext secrets','encrypted backups','new device isolation']},ensure_ascii=False,indent=2))
        browser.close()
finally:server.shutdown()
print('v1.5 workspace browser and preservation regression: PASS')
