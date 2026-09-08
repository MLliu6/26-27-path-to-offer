#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def patch_text(path, fn):
    p=ROOT/path
    old=p.read_text(encoding='utf-8')
    new=fn(old)
    if new!=old:
        p.write_text(new,encoding='utf-8')
        print('patched',path)

def patch_config(text):
    text=text.replace("version: '1.5.0'","version: '1.5.1'")
    text=text.replace("buildVersion: '1.5.0-neutral-workspace'","buildVersion: '1.5.1-theme-source-sync'")
    return text

def patch_index(text):
    return text.replace('styles.css?v=1.5.0','styles.css?v=1.5.1').replace('workspace-v15.css?v=1.5.0','workspace-v15.css?v=1.5.1').replace('config.js?v=1.5.0','config.js?v=1.5.1').replace('app.js?v=1.5.0','app.js?v=1.5.1')

def patch_css(text):
    marker='/* v1.5.1 accent controls */'
    if marker in text:return text
    return text+'''\n\n/* v1.5.1 accent controls */\nhtml:root{--v151-accent:var(--accent-strong,#5268d9);--v151-accent-soft:var(--accent-soft,#edf0ff);--v151-focus:color-mix(in srgb,var(--v151-accent) 55%,white)}\nhtml body .btn.primary{background:var(--v151-accent)!important;border-color:var(--v151-accent)!important}\nhtml body :is(.text-btn,.eyebrow){color:var(--v151-accent)!important}\nhtml body :is(button,a,input,select,textarea,[tabindex]):focus-visible{outline-color:var(--v151-focus)!important}\nhtml body .market-card:hover{border-color:var(--v151-accent)!important}\nhtml body :is(.nav-item.active,.seg.active){border-color:color-mix(in srgb,var(--v151-accent) 30%,var(--line))!important}\n.v151-theme-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 0 12px}.v151-swatch{display:flex;align-items:center;gap:8px;min-height:38px;padding:7px 9px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text)}.v151-swatch i{width:16px;height:16px;border-radius:50%;background:var(--swatch);box-shadow:inset 0 0 0 1px #0002}.v151-swatch.active{border-color:var(--v151-accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--v151-accent) 18%,transparent)}.v151-appearance{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.v151-appearance button{min-height:36px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text)}.v151-appearance button.active{border-color:var(--v151-accent);background:var(--v151-accent-soft)}\n'''

def patch_workspace_js(text):
    marker='/* v1.5.1 working theme controls */'
    if marker in text:return text
    return text+'''\n\n/* v1.5.1 working theme controls */\n(function(){\n  const KEY='pto.ui.theme.v151';\n  const palettes={\n    blue:{name:'蓝',accent:'#6f82e8',strong:'#5268d9',soft:'#edf0ff'},\n    violet:{name:'紫',accent:'#9478d8',strong:'#7457bf',soft:'#f2edff'},\n    slate:{name:'石墨',accent:'#7e8794',strong:'#5e6875',soft:'#eef0f3'},\n    rose:{name:'玫瑰',accent:'#d47b92',strong:'#b85c76',soft:'#fbeef2'},\n    amber:{name:'琥珀',accent:'#c59a55',strong:'#9c7535',soft:'#fbf3e5'},\n    sage:{name:'灰绿',accent:'#8eaa9d',strong:'#66877a',soft:'#edf3f0'}\n  };\n  let saved={palette:'blue',appearance:'system'};try{saved={...saved,...JSON.parse(localStorage.getItem(KEY)||'{}')}}catch(_){}\n  const root=document.documentElement;\n  function effectiveAppearance(v){return v==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):v}\n  function apply(){\n    const p=palettes[saved.palette]||palettes.blue;\n    root.style.setProperty('--accent',p.accent);root.style.setProperty('--accent-strong',p.strong);root.style.setProperty('--accent-soft',p.soft);\n    root.dataset.appearance=effectiveAppearance(saved.appearance);\n    try{localStorage.setItem(KEY,JSON.stringify(saved))}catch(_){}\n    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',root.dataset.appearance==='dark'?'#111113':'#f5f5f7');\n  }\n  function render(){\n    const pop=document.querySelector('#themePopover');if(!pop)return;\n    pop.innerHTML='<p><strong>外观与强调色</strong></p><div class="v151-appearance">'+[['light','浅色'],['dark','深色'],['system','跟随系统']].map(([k,n])=>`<button data-v151-appearance="${k}" class="${saved.appearance===k?'active':''}">${n}</button>`).join('')+'</div><div class="v151-theme-grid">'+Object.entries(palettes).map(([k,p])=>`<button class="v151-swatch ${saved.palette===k?'active':''}" data-v151-palette="${k}" style="--swatch:${p.strong}"><i></i><span>${p.name}</span></button>`).join('')+'</div><small>背景保持中性黑灰；这里只改变强调色。设置仅保存在本机。</small>';\n    pop.querySelectorAll('[data-v151-palette]').forEach(b=>b.onclick=e=>{e.stopPropagation();saved.palette=b.dataset.v151Palette;apply();render();});\n    pop.querySelectorAll('[data-v151-appearance]').forEach(b=>b.onclick=e=>{e.stopPropagation();saved.appearance=b.dataset.v151Appearance;apply();render();});\n  }\n  function openTheme(e){e?.preventDefault();e?.stopImmediatePropagation();const pop=document.querySelector('#themePopover');if(!pop)return;render();const opening=!pop.classList.contains('open');pop.classList.toggle('open',opening);pop.style.display=opening?'block':'none';}\n  addEventListener('load',()=>{apply();const btn=document.querySelector('#themeBtn');if(btn){btn.title='外观与强调色';btn.addEventListener('click',openTheme,true);}render();});\n  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change',()=>{if(saved.appearance==='system')apply();});\n  document.addEventListener('click',e=>{const pop=document.querySelector('#themePopover');if(pop?.classList.contains('open')&&!e.target.closest('#themePopover')&&!e.target.closest('#themeBtn')){pop.classList.remove('open');pop.style.display='none';}},true);\n})();\n'''

def add_workspace_sources():
    path=ROOT/'sources/workspace_sources_v15.json';data=json.loads(path.read_text(encoding='utf-8'))
    rows=data.setdefault('sources',[]);ids={x.get('id') for x in rows}
    additions=[
      {"id":"supplemental-xiaomi-campus","company":"小米","family":"browser","start_url":"https://hr.xiaomi.com/website/campus.html","official_url":"https://hr.xiaomi.com/website/campus.html","api_hosts":["hr.xiaomi.com"],"max_pages":6,"priority":99},
      {"id":"supplemental-cmb-campus","company":"招商银行","family":"browser","start_url":"https://cmb-recruitment-mobile.paas.cmbchina.com/positionSchool","official_url":"https://career.cmbchina.com/campus/home","api_hosts":["cmb-recruitment-mobile.paas.cmbchina.com","cmb-recruitment-pc.paas.cmbchina.com","career.cmbchina.com"],"max_pages":8,"priority":99},
      {"id":"supplemental-sgcc-campus","company":"国家电网","family":"browser","start_url":"https://zhaopin.sgcc.com.cn/","official_url":"https://zhaopin.sgcc.com.cn/","api_hosts":["zhaopin.sgcc.com.cn"],"max_pages":8,"priority":99},
      {"id":"supplemental-spacechina-campus","company":"中国航天科技集团","family":"browser","start_url":"https://spacechina.iguopin.com/job-campus","official_url":"https://spacechina.iguopin.com/job-campus","api_hosts":["spacechina.iguopin.com","gp-api.iguopin.com"],"max_pages":10,"priority":99}
    ]
    for row in additions:
        if row['id'] not in ids:rows.append(row)
    data['version']=2
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('workspace sources',len(rows))

def add_registry_sources():
    path=ROOT/'sources/official_source_registry_v12.json';data=json.loads(path.read_text(encoding='utf-8'))
    rows=data.setdefault('sources',[]);companies={str(x.get('company','')) for x in rows}
    additions=[
      {"company":"招商银行","category":"银行/金融科技","url":"https://career.cmbchina.com/campus/home","priority":98},
      {"company":"国家电网","category":"中央企业/能源/数字化","url":"https://zhaopin.sgcc.com.cn/","priority":98},
      {"company":"中国航天科技集团","category":"中央企业/航天/科研","url":"https://spacechina.iguopin.com/job-campus","priority":98}
    ]
    for row in additions:
        if row['company'] not in companies:rows.append(row)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

patch_text('config.js',patch_config)
patch_text('index.html',patch_index)
patch_text('workspace-v15.css',patch_css)
patch_text('workspace-v15.js',patch_workspace_js)
add_workspace_sources();add_registry_sources()
print('v1.5.1 patch complete')
