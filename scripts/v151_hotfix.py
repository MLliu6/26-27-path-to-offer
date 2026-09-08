#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# The v0.6 closure can still resolve the global applyTheme binding differently
# across loading orders. Make swatch clicks paint the variables explicitly.
p=ROOT/'enhancements-v06.js'
s=p.read_text(encoding='utf-8')
old="b.onclick=()=>{applyTheme(i);localStorage.setItem(THEME_KEY,String(i));repairSwatches(i);const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=p[0];};"
new="b.onclick=()=>{const chosen=palettes[i]||palettes[0],root=document.documentElement,actual=actualAppearance();baseApplyTheme(i);root.style.setProperty('--accent-base',chosen[1]);root.style.setProperty('--accent',chosen[1]);root.style.setProperty('--accent-strong',actual==='dark'?chosen[1]:chosen[2]);root.style.setProperty('--accent-soft',actual==='dark'?hexToRgba(chosen[1],.15):chosen[3]);root.style.setProperty('--accent-wash',hexToRgba(chosen[1],actual==='dark'?.075:.055));localStorage.setItem(THEME_KEY,String(i));repairSwatches(i);const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=chosen[0];};"
if old not in s:
    raise RuntimeError('theme click anchor missing')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')

# Restore all reviewed watch-only employers with collision-free IDs. The first
# bootstrap intentionally never invents vacancies; these entries only register
# official public surfaces and remain zero-row until concrete roles are observed.
rp=ROOT/'sources/workspace_sources_v15.json'
reg=json.loads(rp.read_text(encoding='utf-8'))
entries=[e for e in reg.get('sources',[]) if isinstance(e,dict) and e.get('id')!='supplemental-watch-']
by={e.get('id'):e for e in entries}
allow={'国家电网','中国移动','中国工商银行','中国建设银行','中国银行','中国石油','中国石化'}
po=json.loads((ROOT/'sources/priority_official_sources.json').read_text(encoding='utf-8'))
rows=[]
def walk(v):
    if isinstance(v,dict):
        if v.get('company') and (v.get('url') or v.get('start_url')): rows.append(v)
        for x in v.values(): walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(po)
seen=set()
for src in rows:
    company=str(src.get('company') or '').strip()
    if company not in allow or company in seen: continue
    seen.add(company)
    url=str(src.get('url') or src.get('start_url') or '').strip()
    if not url.startswith('http'): continue
    host=url.split('://',1)[-1].split('/',1)[0].removeprefix('www.')
    eid='supplemental-watch-'+hashlib.sha1(company.encode('utf-8')).hexdigest()[:12]
    item={'id':eid,'company':company,'family':'browser','start_url':url,'official_url':url,'api_hosts':[host],'max_pages':5,'priority':96,'always_refresh':company in {'国家电网','中国移动'}}
    if eid in by: by[eid].update(item)
    else: entries.append(item); by[eid]=item
reg['sources']=entries
rp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('v1.5.1 hotfix applied; registered watch employers:',sorted(seen))
