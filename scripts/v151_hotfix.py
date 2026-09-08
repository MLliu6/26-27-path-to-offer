#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# The legacy theme stack has both direct handlers and older listeners. Keep the
# existing control compatible, then install one final v1.5.1 palette painter
# after all legacy handlers have run. It only changes accent variables: neutral
# light/dark surfaces remain neutral.
p=ROOT/'enhancements-v06.js'
s=p.read_text(encoding='utf-8')
old="b.onclick=()=>{applyTheme(i);localStorage.setItem(THEME_KEY,String(i));repairSwatches(i);const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=p[0];};"
new="b.onclick=()=>{const chosen=palettes[i]||palettes[0],root=document.documentElement,actual=actualAppearance();baseApplyTheme(i);root.style.setProperty('--accent-base',chosen[1]);root.style.setProperty('--accent',chosen[1]);root.style.setProperty('--accent-strong',actual==='dark'?chosen[1]:chosen[2]);root.style.setProperty('--accent-soft',actual==='dark'?hexToRgba(chosen[1],.15):chosen[3]);root.style.setProperty('--accent-wash',hexToRgba(chosen[1],actual==='dark'?.075:.055));localStorage.setItem(THEME_KEY,String(i));repairSwatches(i);const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=chosen[0];};"
if old not in s:
    raise RuntimeError('theme click anchor missing')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')

wv=ROOT/'workspace-v15.js'
w=wv.read_text(encoding='utf-8')
marker='PTO_V151_FINAL_PALETTE'
if marker not in w:
    w += r'''

/* PTO_V151_FINAL_PALETTE: final accent owner; backgrounds stay neutral. */
(function(){
  'use strict';
  if(typeof palettes==='undefined'||typeof THEME_KEY==='undefined')return;
  const hexToRgba=(hex,a)=>{const m=String(hex||'').replace('#','');if(!/^[0-9a-f]{6}$/i.test(m))return `rgba(151,180,167,${a})`;const n=parseInt(m,16);return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;};
  const dark=()=>document.documentElement.dataset.appearance==='dark';
  const paint=index=>{
    const i=Number.isFinite(Number(index))&&palettes[Number(index)]?Number(index):0;
    const p=palettes[i]||palettes[0],root=document.documentElement;
    root.dataset.accentIndex=String(i);
    root.style.setProperty('--accent-base',p[1]);
    root.style.setProperty('--accent',p[1]);
    root.style.setProperty('--accent-strong',dark()?p[1]:p[2]);
    root.style.setProperty('--accent-soft',dark()?hexToRgba(p[1],.16):p[3]);
    root.style.setProperty('--accent-wash',hexToRgba(p[1],dark()?.08:.055));
    const caption=document.querySelector('#activeThemeName');if(caption)caption.textContent=p[0];
    document.querySelectorAll('.swatch').forEach((b,n)=>{b.classList.toggle('selected',n===i);b.setAttribute('aria-pressed',String(n===i));});
    return i;
  };
  const saved=()=>{const n=Number(localStorage.getItem(THEME_KEY)||0);return palettes[n]?n:0;};
  // Document-bubble runs after older target listeners, so the user's choice is
  // the final paint operation even on browsers retaining the legacy handler.
  document.addEventListener('click',event=>{
    const swatch=event.target?.closest?.('.swatch[data-theme]');
    if(swatch){const i=Number(swatch.dataset.theme);localStorage.setItem(THEME_KEY,String(i));paint(i);return;}
    if(event.target?.closest?.('[data-appearance-choice]'))queueMicrotask(()=>paint(saved()));
  });
  paint(saved());
  new MutationObserver(()=>paint(saved())).observe(document.documentElement,{attributes:true,attributeFilter:['data-appearance']});
  window.PTO_V151_PALETTE={paint,saved};
})();
'''
    wv.write_text(w,encoding='utf-8')

# Restore all reviewed watch-only employers with collision-free IDs. These
# entries register official public surfaces; zero rows remain zero until a
# concrete vacancy is observed, so no announcement/navigation page becomes a job.
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
