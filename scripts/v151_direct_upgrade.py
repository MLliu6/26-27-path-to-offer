#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    print('updated', rel)


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'missing patch anchor: {label}')
    return text.replace(old, new)


# ---- UI / appearance -------------------------------------------------------
app = read('app.js')
app = replace_required(
    app,
    'style="--sw:${p[0]}"',
    'style="--sw:${p[1]};background:${p[1]}"',
    'real palette color in base swatch',
)
write('app.js', app)

v06 = read('enhancements-v06.js')
# Remove the old green-charcoal flash before the v1.5 neutral stylesheet loads.
neutral_map = {
    '#101512':'#111113', '#171d1a':'#19191c', '#202823':'#222226', '#99a69e':'#aaaab7', '#2c3630':'#36363e',
    '#141a17':'#18181b', '#1b221e':'#202025', '#1c241f':'#232328', '#344038':'#393942', '#121815':'#151518',
    '#263029':'#2b2b31', '#0e1511':'#111113', '#34423a':'#3a3a43', '#1a211d':'#1e1e22', '#1d2520':'#222226',
    'rgba(3,7,5,.64)':'rgba(0,0,0,.64)', 'rgba(25,32,28,.95)':'rgba(25,25,28,.95)'
}
for a,b in neutral_map.items():
    v06 = v06.replace(a,b)
# Better affordance: selected accent remains obvious and accessible.
v06 = v06.replace(
    "b.classList.toggle('selected',i===saved);b.setAttribute('aria-label',`主题色 ${p[0]}`);b.title=p[0];",
    "b.classList.toggle('selected',i===saved);b.setAttribute('aria-pressed',String(i===saved));b.setAttribute('aria-label',`主题色 ${p[0]}`);b.title=`${p[0]} · 点击立即预览`;"
)
v06 = v06.replace("small.innerHTML='Accent <b id=\"activeThemeName\"></b> · 自动保存';", "small.innerHTML='Accent <b id=\"activeThemeName\"></b> · 点击颜色立即预览并自动保存';")
write('enhancements-v06.js', v06)

css = read('workspace-v15.css')
css = replace_required(
    css,
    '--v15-link:#365dcc;--v15-danger:#b53d49;--v15-focus:#6f8aee;--v15-control:#e8e8ed',
    '--v15-link:color-mix(in srgb,var(--accent-strong) 86%,#274b9e 14%);--v15-danger:#b53d49;--v15-focus:color-mix(in srgb,var(--accent-strong) 76%,#7a8bc6 24%);--v15-control:color-mix(in srgb,var(--surface-2) 78%,var(--accent) 22%);--v15-accent-soft:color-mix(in srgb,var(--surface) 84%,var(--accent) 16%);--v15-accent-border:color-mix(in srgb,var(--line) 55%,var(--accent-strong) 45%)',
    'semantic accent variables',
)
css = css.replace(
    '--v15-link:#a4b8ff;--v15-danger:#ffacb4;--v15-control:#2b2b31',
    '--v15-link:color-mix(in srgb,var(--accent) 76%,#ffffff 24%);--v15-danger:#ffacb4;--v15-control:color-mix(in srgb,#2b2b31 76%,var(--accent) 24%);--v15-accent-soft:color-mix(in srgb,var(--surface) 82%,var(--accent) 18%);--v15-accent-border:color-mix(in srgb,var(--line) 50%,var(--accent) 50%)'
)
css = css.replace(
    'html body :is(.nav-item.active,.seg.active){background:var(--v15-control)!important;color:var(--text)!important}',
    'html body :is(.nav-item.active,.seg.active){background:var(--v15-control)!important;color:var(--text)!important;box-shadow:inset 0 -2px 0 var(--accent-strong)!important}'
)
css = css.replace(
    'html body .brand-mark{background:var(--text)!important;color:var(--surface)!important;box-shadow:none}',
    'html body .brand-mark{background:var(--accent-strong)!important;color:#fff!important;box-shadow:none}'
)
css = css.replace(
    'html body :is(.btn.primary){background:#4264ce!important;border-color:#4264ce!important;color:white!important}',
    'html body :is(.btn.primary){background:var(--accent-strong)!important;border-color:var(--accent-strong)!important;color:#fff!important;box-shadow:0 4px 14px color-mix(in srgb,var(--accent) 24%,transparent)}'
)
css += '''\n/* v1.5.1: palette affects actions and selection, never neutral page surfaces. */\nhtml body #themeBtn:has(+ *){}\nhtml body .theme-popover .swatch.selected{box-shadow:0 0 0 2px var(--surface),0 0 0 4px var(--accent-strong)!important;transform:translateY(-1px)}\nhtml body .appearance-control button.active{background:var(--v15-accent-soft)!important;color:var(--text)!important;box-shadow:inset 0 0 0 1px var(--v15-accent-border)!important}\nhtml body :is(.match-score.high,.signal-chip,.quality-badge){border-color:var(--v15-accent-border)!important}\nhtml body .market-card:hover{border-color:var(--v15-accent-border)!important}\nhtml body :is(.btn.ghost,.icon-btn):hover{border-color:var(--v15-accent-border)!important}\n'''
write('workspace-v15.css', css)

# Prevent delayed resume-profile enrichment from wiping a search/threshold the user
# already changed while parsing was finishing.
e13 = read('enhancements-v13.js')
old = """    const beforeId=typeof currentProfile==='function'?currentProfile()?.id||'':'';\n    const beforeLocations=[...(state.preferences?.targetLocations||[])];\n    setTimeout(()=>{\n      const current=typeof currentProfile==='function'?currentProfile():null;\n      if(!current||current.id===beforeId)return;\n      rebuildProfile(current);resetResumeDerivedPrefs(beforeLocations);saveState(false);renderAll();\n    },220);"""
new = """    const beforeId=typeof currentProfile==='function'?currentProfile()?.id||'':'';\n    const beforeLocations=[...(state.preferences?.targetLocations||[])];\n    const controlBefore={search:$('#jobSearch')?.value||'',threshold:$('#scoreThreshold')?.value||'',fresh:!!$('#freshOnly')?.checked};\n    setTimeout(()=>{\n      const current=typeof currentProfile==='function'?currentProfile():null;\n      if(!current||current.id===beforeId)return;\n      const controlNow={search:$('#jobSearch')?.value||'',threshold:$('#scoreThreshold')?.value||'',fresh:!!$('#freshOnly')?.checked};\n      const userTouched=controlNow.search!==controlBefore.search||controlNow.threshold!==controlBefore.threshold||controlNow.fresh!==controlBefore.fresh;\n      rebuildProfile(current);resetResumeDerivedPrefs(beforeLocations);\n      if(userTouched){\n        if($('#jobSearch'))$('#jobSearch').value=controlNow.search;\n        if($('#scoreThreshold'))$('#scoreThreshold').value=controlNow.threshold;\n        if($('#scoreThresholdLabel'))$('#scoreThresholdLabel').textContent=controlNow.threshold;\n        if($('#freshOnly'))$('#freshOnly').checked=controlNow.fresh;\n      }\n      saveState(false);renderAll();\n    },220);"""
if old in e13:
    e13 = e13.replace(old,new)
else:
    print('warning: delayed profile anchor already changed')
write('enhancements-v13.js', e13)

# Source panel: make every reviewed official URL directly clickable.
wv = read('workspace-v15.js')
wv = wv.replace("stylesheet.href='workspace-v15.css?v=1.5.0'", "stylesheet.href='workspace-v15.css?v=1.5.1'")
wv = wv.replace("version:'1.5.0'", "version:'1.5.1'")
wv = wv.replace(
    "<div><strong>${esc(s.company)}</strong><small>${esc(s.checked_at||'尚未检查')}",
    "<div><strong>${s.official_url?`<a class=\"text-btn\" href=\"${esc(s.official_url)}\" target=\"_blank\" rel=\"noopener\">${esc(s.company)} ↗</a>`:esc(s.company)}</strong><small>${esc(s.checked_at||'尚未检查')}"
)
wv = wv.replace(
    "${groups.map(s=>`<div class=\"v15-source-row\"><strong>${esc(s.label||s.name)}</strong><span>${s.ok?'正常':'异常'} · ${Number(s.count||0)} 条</span></div>`).join('')}",
    "${groups.map(s=>`<div class=\"v15-source-row\"><strong>${s.url?`<a class=\"text-btn\" href=\"${esc(s.url)}\" target=\"_blank\" rel=\"noopener\">${esc(s.label||s.name)} ↗</a>`:esc(s.label||s.name)}</strong><span>${s.ok?'正常':'异常'} · ${Number(s.count||0)} 条</span></div>`).join('')}"
)
write('workspace-v15.js', wv)

config = read('config.js')
config = config.replace("version: '1.5.0'", "version: '1.5.1'", 1).replace("buildVersion: '1.5.0-neutral-workspace'", "buildVersion: '1.5.1-theme-source-sync'", 1)
write('config.js', config)

index = read('index.html')
index = index.replace('?v=1.5.0', '?v=1.5.1')
write('index.html', index)

# ---- Source coverage -------------------------------------------------------
reg_path = ROOT / 'sources/workspace_sources_v15.json'
reg = json.loads(reg_path.read_text(encoding='utf-8'))
entries = [e for e in reg.get('sources',[]) if isinstance(e,dict)]
by_id = {e.get('id'):e for e in entries}

def upsert(e):
    e = dict(e)
    eid = e['id']
    if eid in by_id:
        by_id[eid].update(e)
    else:
        entries.append(e); by_id[eid]=e

# High-value current Xiaomi surfaces: general opportunities + top internship.
upsert({"id":"supplemental-xiaomi-campus","company":"小米","family":"browser","start_url":"https://hr.xiaomi.com/website/opportunities.html","official_url":"https://hr.xiaomi.com/website/campus.html","api_hosts":["hr.xiaomi.com"],"max_pages":6,"priority":99,"always_refresh":True})
upsert({"id":"supplemental-xiaomi-topintern","company":"小米","family":"feishu","start_url":"https://xiaomi.jobs.f.mioffice.cn/topintern","official_url":"https://hr.xiaomi.com/website/top-talent.html","api_hosts":["xiaomi.jobs.f.mioffice.cn"],"max_pages":6,"priority":98,"always_refresh":True})
if 'supplemental-xiaomi' in by_id: by_id['supplemental-xiaomi']['always_refresh']=True

# CMB's current public 2027 landing and a concrete CMB Network Technology list.
upsert({"id":"supplemental-cmb-campus-mobile","company":"招商银行","family":"browser","start_url":"https://cmb-recruitment-mobile.paas.cmbchina.com/positionSchool","official_url":"https://career.cmbchina.com/campus/home","api_hosts":["cmb-recruitment-mobile.paas.cmbchina.com","career.cmbchina.com"],"click_labels":["马上投递","应届生招聘","职位列表"],"max_pages":8,"priority":99,"always_refresh":True})
upsert({"id":"supplemental-cmb-network-tech","company":"招银网络科技","family":"bank","start_url":"https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1","official_url":"https://career.cmbchina.com/campus/home","api_hosts":["career.cmbchina.com"],"max_pages":8,"priority":98,"always_refresh":True})

# Promote already-reviewed employer ATS entries from the existing production browser registry.
priority_registry = json.loads((ROOT/'sources/priority_browser_sources.json').read_text(encoding='utf-8'))
promote = {
    '中国航天科技集团','中国电子科技集团','中国船舶集团','中国华能集团','中国海洋石油集团','中国建材集团',
    '中国联通','交通银行','招商银行'
}
for src in priority_registry.get('sources',[]):
    if not isinstance(src,dict) or src.get('company') not in promote:
        continue
    item = dict(src)
    item['id'] = 'supplemental-reviewed-' + str(src.get('id') or re.sub(r'\W+','-',src['company'])).strip('-')
    item['max_pages'] = min(10, max(4, int(src.get('max_pages') or 4)))
    item['priority'] = max(96, int(src.get('priority') or 0))
    item['always_refresh'] = src.get('company') in {'中国航天科技集团','招商银行'}
    upsert(item)

# Promote reviewed watch-only portals for broad state-owned/bank coverage; zero jobs stays zero.
watch_allow = {'国家电网','中国移动','中国工商银行','中国建设银行','中国银行','中国石油','中国石化'}
try:
    po = json.loads((ROOT/'sources/priority_official_sources.json').read_text(encoding='utf-8'))
except Exception:
    po = {}
watch_rows=[]
def walk(v):
    if isinstance(v,dict):
        if v.get('company') and (v.get('url') or v.get('start_url')): watch_rows.append(v)
        for x in v.values(): walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(po)
seen_watch=set()
for src in watch_rows:
    company=str(src.get('company') or '').strip()
    if company not in watch_allow or company in seen_watch: continue
    seen_watch.add(company)
    url=str(src.get('url') or src.get('start_url') or '').strip()
    if not url.startswith('http'): continue
    upsert({"id":"supplemental-watch-"+re.sub(r'[^a-z0-9]+','-',company.lower()).strip('-')[:24],"company":company,"family":"browser","start_url":url,"official_url":url,"api_hosts":[re.sub(r'^www\.','',re.sub(r'^https?://','',url).split('/')[0])],"max_pages":5,"priority":96,"always_refresh":company in {'国家电网','中国移动'}})

# Explicit State Grid official platform if the watch registry did not provide a usable row.
upsert({"id":"supplemental-state-grid","company":"国家电网","family":"browser","start_url":"https://zhaopin.sgcc.com.cn/","official_url":"https://zhaopin.sgcc.com.cn/","api_hosts":["zhaopin.sgcc.com.cn"],"click_labels":["招聘公告","搜索职位","单位一览"],"max_pages":6,"priority":99,"always_refresh":True})

reg['version'] = max(2,int(reg.get('version') or 1))
reg['sources'] = entries
reg_path.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('workspace source count',len(entries))

collector = read('scripts/workspace_source_refresh.py')
collector = re.sub(
    r"TITLE = re\.compile\([^\n]+\)",
    "TITLE = re.compile(r'工程师|研究员|开发|架构师|设计师|管培生|培养生|数据科学家|(?:信息|科技|技术|研发|软件|数据|人工智能|AI).{0,8}岗|Engineer|Developer|Scientist', re.I)",
    collector,
    count=1,
)
collector = collector.replace(
"""def select(entries, now=None, full=False):\n    ordered = sorted(entries, key=lambda e: e['id'])\n    if full:\n        return ordered\n    size = 6\n    shards = max(1, (len(ordered) + size - 1) // size)\n    idx = int((time.time() if now is None else now) // 7200) % shards\n    return ordered[idx * size:(idx + 1) * size]\n""",
"""def select(entries, now=None, full=False):\n    ordered = sorted(entries, key=lambda e: e['id'])\n    if full:\n        return ordered\n    always = [e for e in ordered if e.get('always_refresh')]\n    rotating = [e for e in ordered if not e.get('always_refresh')]\n    size = 6\n    shards = max(1, (len(rotating) + size - 1) // size)\n    idx = int((time.time() if now is None else now) // 3600) % shards\n    selected = [*always, *rotating[idx * size:(idx + 1) * size]]\n    seen=set(); out=[]\n    for e in selected:\n        if e['id'] in seen: continue\n        seen.add(e['id']); out.append(e)\n    return out\n"""
)
collector = collector.replace(
    "return bool(2 <= len(title) <= 100 and TITLE.search(title) and not REJECT.search(title)",
    "return bool(2 <= len(title) <= 100 and TITLE.search(title) and not REJECT.search(title) and not re.search(r'事业部$|部门$|中心$|业务技术|职位列表|岗位列表', title)"
)
write('scripts/workspace_source_refresh.py', collector)

# Scheduled production refresh: persistent, read-only employer crawling + data commit.
prod_workflow = '''name: refresh-workspace-official-sources\n\non:\n  workflow_dispatch:\n  schedule:\n    - cron: '23 * * * *'\n  push:\n    branches: [main]\n    paths:\n      - 'sources/workspace_sources_v15.json'\n      - 'scripts/workspace_source_refresh.py'\n      - '.github/workflows/refresh-workspace-sources.yml'\n\npermissions:\n  contents: write\n\nconcurrency:\n  group: refresh-workspace-official-sources\n  cancel-in-progress: false\n\njobs:\n  refresh:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 24\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          ref: main\n      - uses: actions/setup-python@v6\n        with:\n          python-version: '3.12'\n      - name: Install crawler dependencies\n        run: python -m pip install --disable-pip-version-check requests==2.32.5 beautifulsoup4==4.13.4 playwright\n      - name: Refresh core and rotating official sources\n        env:\n          PTO_V15_FULL: ${{ github.event_name == 'workflow_dispatch' && '1' || '0' }}\n        run: PYTHONPATH=. python scripts/workspace_source_refresh.py\n      - name: Validate source truthfulness\n        run: |\n          python - <<'PY'\n          import json\n          from pathlib import Path\n          status=json.loads(Path('data/supplemental_source_status.json').read_text(encoding='utf-8'))\n          ids={x.get('id') for x in status.get('sources',[]) if isinstance(x,dict)}\n          for needed in ['supplemental-xiaomi','supplemental-cmb-campus-mobile','supplemental-state-grid','supplemental-reviewed-spacechina-iguopin']:\n              assert needed in ids, (needed,len(ids))\n          assert all(not (x.get('ok') and not x.get('count')) for x in status.get('sources',[]) if isinstance(x,dict))\n          print('registered',status.get('registered_sources'),'catalog',status.get('catalog_count'),'fresh',status.get('fresh_count'))\n          PY\n      - name: Commit refreshed public job data\n        run: |\n          if git diff --quiet -- data/jobs_supplemental.json data/supplemental_source_status.json; then\n            echo 'No supplemental source changes.'\n            exit 0\n          fi\n          git config user.name 'path-to-offer-bot'\n          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'\n          git add data/jobs_supplemental.json data/supplemental_source_status.json\n          git commit -m 'data: refresh high-value official employer sources'\n          git pull --rebase origin main\n          git push origin HEAD:main\n'''
write('.github/workflows/refresh-workspace-sources.yml', prod_workflow)

# Theme regression: visible accent must really change a primary action and persist.
theme = read('tests/theme_smoke.py')
theme = theme.replace(
    "assert all(c not in {\"rgba(0, 0, 0, 0)\",\"transparent\"} for c in colors)\n\n        # Accent previews",
    "assert all(c not in {\"rgba(0, 0, 0, 0)\",\"transparent\"} for c in colors)\n        before_primary=page.locator('.btn.primary').first.evaluate(\"el => getComputedStyle(el).backgroundColor\")\n\n        # Accent previews"
)
theme = theme.replace(
    "assert \"Lavender\" in page.locator(\"#activeThemeName\").inner_text()\n        assert page.locator(\"#themePopover\").evaluate",
    "assert \"Lavender\" in page.locator(\"#activeThemeName\").inner_text()\n        after_primary=page.locator('.btn.primary').first.evaluate(\"el => getComputedStyle(el).backgroundColor\")\n        assert after_primary != before_primary, (before_primary,after_primary)\n        assert page.locator(\"#themePopover\").evaluate"
)
theme = theme.replace(
    "assert page.locator('button[data-appearance-choice=\"dark\"]').evaluate(\"el => el.classList.contains('active')\")",
    "assert page.locator('button[data-appearance-choice=\"dark\"]').evaluate(\"el => el.classList.contains('active')\")\n        assert page.locator('.swatch.selected').get_attribute('data-theme')=='3'"
)
write('tests/theme_smoke.py', theme)

# Update stale CI version gates so the new release does not stay red for old assertions.
for path in (ROOT/'.github/workflows').glob('*.yml'):
    if path.name in {'v151-direct-upgrade.yml'}: continue
    text=path.read_text(encoding='utf-8')
    original=text
    text=text.replace("version: '1.4.2'", "version: '1.5.1'")
    text=text.replace("buildVersion: '1.4.2-target-coverage'", "buildVersion: '1.5.1-theme-source-sync'")
    text=text.replace("version:\\s*'1\\.4\\.2'", "version:\\s*'1\\.5\\.1'")
    text=text.replace('Path to Offer v1.4.2 product invariants', 'Path to Offer v1.5.1 product invariants')
    text=text.replace('Path to Offer v1.4.2 universal matching and target-coverage checks passed.', 'Path to Offer v1.5.1 universal matching and target-coverage checks passed.')
    if text!=original:
        path.write_text(text,encoding='utf-8'); print('updated',path.relative_to(ROOT))

print('v1.5.1 patch complete; no account/vault file was modified.')
