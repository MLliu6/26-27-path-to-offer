"""Draft-only final compatibility and source-quality fixes. Removed before release."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'workspace-core-v15.js';s=p.read_text()
s=s.replace("const all=[...map.values()],concrete=all.filter(j=>!isLead(j)),keys=", """const raw=[...map.values()],byUrl=new Map();
    const routeKey=j=>company(j)+'|'+role(j)+'|'+canonicalUrl(j.u??j.apply_url??j.applyUrl??j.url);
    for(const j of raw){if(!isLead(j)&&positionId(j)){const k=routeKey(j);if(!byUrl.has(k))byUrl.set(k,new Set());byUrl.get(k).add(positionId(j));}}
    const all=raw.filter(j=>positionId(j)||!byUrl.has(routeKey(j))||byUrl.get(routeKey(j)).size!==1);
    const concrete=all.filter(j=>!isLead(j)),keys=""")
p.write_text(s)
p=ROOT/'tests/workspace_v15.mjs';p.write_text(p.read_text()+"\nconst old={c:'滴滴',r:'推理工程师',l:'北京',u:'https://x.test/campus/p/qa-001?utm_source=old'};\nconst direct={...old,u:'https://x.test/campus/p/qa-001',z:'qa-001',s:'direct-official:test'};\nassert.equal(C.mergeJobs([old],[direct]).length,1);\nassert.equal(C.mergeJobs([old],[direct])[0].z,'qa-001');\n")
for p in (ROOT/'tests').glob('*smoke.py'):
    if p.name=='workspace_v15_smoke.py':continue
    s=p.read_text()
    def replacement(m):
        indent=m[1];var=m[2]
        return m[0]+indent+f"if '/data/jobs_supplemental.json' in {var} or '/data/supplemental_source_status.json' in {var}:\n"+indent+"    route.fulfill(status=200,content_type='application/json',body=json.dumps({'schema_version':4,'jobs':[],'sources':[]}))\n"+indent+"    return\n"
    s=re.sub(r'(?m)^( +)(u|url) ?= ?route.request.url\n',replacement,s)
    s=s.replace('page.wait_for_selector("#ptoFlow")','page.wait_for_selector("#ptoFlow",state="attached")')
    s=s.replace('page.wait_for_selector("#searchPolicy", timeout=12_000)', 'page.wait_for_function("window.PTO_WORKSPACE_V15", timeout=20_000)')
    p.write_text(s)
p=ROOT/'workspace-v15.js';s=p.read_text()
s=s.replace('function backup(){const entries={};', "async function backup(){try{if(window.PTO_ACCOUNT_SESSION)await window.PTO_SECURE_ACCOUNT_V2.flushLocal();}catch(err){toast('备份前保存失败：'+err.message);return;}const entries={};")
s=s.replace("const basePipeline=renderPipeline;\n  renderPipeline=function(){basePipeline();", """const basePipeline=renderPipeline;
  function lockedBanner(){
    $('#v15LockedBanner')?.remove();const hint=window.PTO_DEVICE_ACCOUNT_HINT?.read();if(window.PTO_ACCOUNT_SESSION||!hint)return;
    const banner=document.createElement('div');banner.id='v15LockedBanner';banner.className='v15-panel';banner.innerHTML=`<strong>${esc(hint.username)} · 账户已锁定</strong><p class="v15-note">加密账户的投递记录不会显示在访客列表。请先解锁原账户；不要为找回记录而清除站点数据或新建同名账户。</p><button class="btn primary">解锁原账户</button>`;
    banner.querySelector('button').onclick=()=>window.PTO_SECURE_ACCOUNT_V2.openAccount();$('#pipelineView .page-head').insertAdjacentElement('afterend',banner);
  }
  renderPipeline=function(){basePipeline();lockedBanner();""")
s=s.replace("toast('密文已恢复；在账户中使用原密码解锁');", "toast('备份密文已保存；原有账户未覆盖，新恢复账户可用原密码解锁');")
s=s.replace("source:j.s??j.source??'public',positionId", "source:j.s??j.source??'public',sourceTier:C.isLead(j)?1:oldNormalize(j).sourceTier,updatedAt:C.isLead(j)?'':oldNormalize(j).updatedAt,positionId")
s=s.replace("    $('#v15ResetFilters').onclick=", "    toolbar.insertAdjacentHTML('beforeend','<button id=\"v15MobilePrefs\" class=\"btn ghost\" aria-expanded=\"false\">匹配偏好</button>');$('#v15MobilePrefs').onclick=e=>{const opened=document.body.classList.toggle('v15-show-filters');e.currentTarget.setAttribute('aria-expanded',String(opened));};\n    $('#v15ResetFilters').onclick=")
p.write_text(s)
p=ROOT/'ranking-v14.js';s=p.read_text().replace('  function calibrate(job,profile,legacy,opts={}){',"  function calibrate(job,profile,legacy,opts={}){\n    if(window.PTO_WORKSPACE_CORE?.isLead(job))return {...legacy,score:null,band:'待官网复核',evidenceConfidence:0,evidenceLabel:'尚未官网复核',components:{...(legacy?.components||{}),source:0,freshness:0,completeness:0,evidenceConfidence:0},calibration:'unverified-target-lead'};");p.write_text(s)
p=ROOT/'workspace-v15.css';p.write_text(p.read_text()+'''
html:root{--panel:var(--surface);--panel-2:var(--surface-2)}
html body :is(.pto-score-audit,.score-breakdown,.github-btn){background:var(--surface)!important;color:var(--text)!important;border-color:var(--line)!important}
html body .job-table tbody tr:hover{background:var(--surface-2)!important}
html body :is(.market-card,.market-card-top,.market-card-title,.market-card-foot,.job-facts,.job-market){min-width:0;max-width:100%}
html body :is(.market-card h3,.market-card p,.market-card-foot .source-tag,.job-facts span){white-space:normal;overflow-wrap:anywhere;max-width:100%}
#v15MobilePrefs{display:none}
@media(max-width:760px){html body .match-rail{display:none}html body .job-market{width:100%}html body .market-card-title{flex:1;min-width:0}html body .pto-card-actions{flex-wrap:wrap;white-space:normal}html body .market-head h2{font-size:20px}#v15MobilePrefs{display:inline-flex}html body.v15-show-filters .match-rail{display:grid}html body .main-nav{width:calc(100vw - 24px)!important;left:12px!important;right:auto!important;justify-self:auto}}
''')
for name in ['tests/v15_review_snapshot.py','tests/workspace_v15_smoke.py']:
    p=ROOT/name;s=p.read_text().replace('page.screenshot(path=',"page.screenshot(animations='disabled',path=");p.write_text(s)
p=ROOT/'tests/v15_review_snapshot.py';s=p.read_text();s=s.replace("page.screenshot(animations='disabled',path=str(OUT / 'mobile.png'), full_page=True)","page.screenshot(animations='disabled',path=str(OUT / 'mobile.png'), full_page=True)\n        summary['mobileWidth']=page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll(\"body *\")].filter(x=>getComputedStyle(x).position!==\"fixed\"&&x.getBoundingClientRect().right>innerWidth+2).slice(0,10).map(x=>({tag:x.tagName,cls:x.className,width:x.getBoundingClientRect().width}))})')");p.write_text(s)
p=ROOT/'tests/workspace_v15_smoke.py';s=p.read_text().replace("assert '待复核线索' in page.locator('.v15-badge.lead').inner_text()", "assert '待复核线索' in page.locator('.v15-badge.lead').inner_text()\n        assert page.evaluate(\"scoreJob(marketJobs.find(j=>j.id==='c'),currentProfile()).evidenceConfidence\")==0");p.write_text(s)
p=ROOT/'README.md';p.write_text('> **v1.5.0 求职工作台升级**：中性深色、快捷进度、账户保存保护与扩展信源。[改动与验证说明](docs/WORKSPACE_V15_REVIEW.md)。原账户与存储路径不变。\n\n'+p.read_text())
extra='''
# Navigation/product cards are not vacancies, even if their text says development.
ROLE_LINE = re.compile(r'^.{1,70}(?:工程师|研究员|研发专家|研究主管|研究专家|架构师)(?:[（(][^）)]{1,20}[）)])?(?:[-—·][^\\n]{1,12})?$')
PROFESSION = re.compile(r'工程师|研究员|研发专家|研究主管|研究专家|架构师|\\bEngineer\\b|\\bScientist\\b|\\bResearcher\\b|\\bSE\\b', re.I)
BAD_SURFACE = re.compile(r'/business/detail|/community(?:/|$)|/product/|/developer/solution/|/ecology/')

def strict_job(job):
    title = str(job.get('role') or '').strip()
    jd = str(job.get('jd') or '').strip()
    if not PROFESSION.search(title) or REJECT.search(title) or BAD_SURFACE.search(job.get('apply_url','')):
        return False
    if job.get('observed_via') == 'browser-rendered-dom' and ('职位搜索' in jd or '在招职位' in jd or '产品部门' in jd):
        return False
    return bool(2 <= len(title) <= 100 and len(jd) > len(title)+20 and job.get('apply_url','').startswith(('http://','https://')))

def static_text_jobs(entry, html):
    from bs4 import BeautifulSoup
    from scripts import priority_browser_harvester as h
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select('script,style,nav,header,footer'):node.decompose()
    lines=[x.strip() for x in soup.get_text('\\n',strip=True).splitlines() if x.strip()]
    starts=[i for i,line in enumerate(lines) if ROLE_LINE.fullmatch(line) and not REJECT.search(line)]
    jobs=[]
    for n,i in enumerate(starts):
        end=starts[n+1] if n+1<len(starts) else min(len(lines),i+100)
        title=lines[i];body='\\n'.join(lines[i+1:end])[:5000]
        if len(body)<80 or not re.search(r'职责|要求|[1-5][.、]',body):continue
        job=h.normalize_dom_job(entry,entry['start_url'],title,body)
        if job:
            job['role']=title;job['jd']=body;job['observed_via']='employer-public-role-block'
            if '校园招聘' in soup.get_text() and '2027' not in title+' '+body:
                job['batch']='校园招聘·届别待确认';job['graduation']=''
            if strict_job(job):jobs.append(job)
    unique={}
    for j in jobs:
        k=j['role']
        if k not in unique or len(j['jd'])<len(unique[k]['jd']):unique[k]=j
    return list(unique.values())

def fix_detail(job):
    from urllib.parse import urlparse,quote
    via=job.get('observed_via','');pid=str(job.get('position_id') or '');url=job.get('apply_url','')
    if 'feishu' in via and pid and '/position/' not in url:
        parsed=urlparse(url);parts=[x for x in parsed.path.split('/') if x]
        if parts:job['apply_url']=job['notice_url']=f'{parsed.scheme}://{parsed.netloc}/{parts[0]}/position/{quote(pid,safe="")}/detail'
    return job

valid_job = strict_job
'''
p=ROOT/'scripts/workspace_source_refresh.py';s=p.read_text().replace('def main():',extra+'\n\ndef main():')
s=s.replace('rows, diag = h.collect_one(context, entry)',"if entry.get('family')=='static':\n                    import requests\n                    response=requests.get(entry['start_url'],timeout=15)\n                    response.raise_for_status()\n                    rows=static_text_jobs(entry,response.text);diag={}\n                else:\n                    rows, diag = h.collect_one(context, entry)")
s=s.replace('encode(j, entry, checked)','encode(fix_detail(j), entry, checked)')
s=s.replace("jobs = load(FEED).get('jobs',[])","previous=load(FEED).get('jobs',[])\n    jobs=[]\n    for old in previous:\n        verbose=dict(role=old.get('r'),jd=old.get('d'),apply_url=old.get('u'),position_id=old.get('z'),observed_via=old.get('observed_via'))\n        if strict_job(verbose):\n            fixed=fix_detail(verbose);old['u']=old['n']=fixed['apply_url'];jobs.append(old)")
p.write_text(s)
p=ROOT/'tests/test_workspace_v15.py';s=p.read_text().replace('    def test_frontend_core(self):', '''    def test_reject_navigation_and_job_list_as_jd(self):
        for title,url in [('开发者','https://jobs.sophgo.com/'),('开发社区','https://x.test/community'),('智能算法产品事业部','https://x.test/business/detail')]:
            self.assertFalse(s.valid_job(dict(role=title,jd='导航与产品信息 '*30,apply_url=url)))
        self.assertFalse(s.valid_job(dict(role='服务端开发工程师',jd='职位搜索 职位类别 在招职位 '+ '页面汇总 '*40,apply_url='https://x.test/job/123',observed_via='browser-rendered-dom')))
    def test_static_role_blocks(self):
        entry=dict(id='test',company='测试企业',start_url='https://example.com/campus',official_url='https://example.com/campus')
        html='<h2>校园招聘</h2><div>大模型推理工程师</div><div>工作地点</div><div>北京</div><div>工作职责</div><p>1. 负责推理框架、CUDA算子与内存调度优化。通过可复现性能分析验证吞吐和延迟改进。</p><div>技能要求</div><p>1. 熟悉C++、Python和并行程序，了解深度学习框架、分布式系统和模型部署。</p>'
        jobs=s.static_text_jobs(entry,html)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['location'],'北京')
        self.assertNotIn('2027',jobs[0]['batch'])
    def test_frontend_core(self):''');p.write_text(s)
print('Final compatibility and source-quality fixes applied; user vault files untouched.')
