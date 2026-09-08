#!/usr/bin/env python3
from __future__ import annotations
import json,re,shutil,time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

TARGETS={
 'cmb':'https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1',
 'sgcc':'https://zhaopin.sgcc.com.cn/sgcchr/static/search.html',
 'xiaomi':'https://xiaomi.jobs.f.mioffice.cn/campus',
}
HINT=re.compile(r'job|position|post|recruit|search|list|bullet|unit|campus|school',re.I)
TITLE_KEYS={'title','jobname','job_name','jobtitle','job_title','positionname','position_name','postname','post_name','name'}

def chrome():
 for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
  p=shutil.which(n)
  if p:return p
 raise SystemExit('no chrome')

def shape(x,depth=0):
 if depth>2:return type(x).__name__
 if isinstance(x,dict):return {str(k):shape(v,depth+1) for k,v in list(x.items())[:18]}
 if isinstance(x,list):return [shape(x[0],depth+1)] if x else []
 return type(x).__name__

def candidates(x,out,path='root',depth=0):
 if depth>8:return
 if isinstance(x,dict):
  low={str(k).lower():v for k,v in x.items()}
  title=next((str(low[k]) for k in TITLE_KEYS if k in low and isinstance(low[k],(str,int,float))), '')
  if title and len(title.strip())>2 and re.search(r'工程师|研发|开发|算法|技术|数据|产品|运营|金融|管理|客户|研究|实习|管培|电气|电力|计算机|通信|软件|硬件|安全',title,re.I):
   out.append({'path':path,'title':title[:100],'keys':list(x.keys())[:25]})
  for k,v in x.items():candidates(v,out,f'{path}.{k}',depth+1)
 elif isinstance(x,list):
  for i,v in enumerate(x[:100]):candidates(v,out,f'{path}[{i}]',depth+1)

def main():
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=chrome(),args=['--no-sandbox','--disable-dev-shm-usage'])
  for name,url in TARGETS.items():
   ctx=browser.new_context(locale='zh-CN');page=ctx.new_page();seen=[]
   def on_response(r):
    try:
     ct=(r.headers.get('content-type') or '').lower()
     if ('json' not in ct and not HINT.search(r.url)) or len(seen)>=80:return
     item={'url':r.url,'status':r.status,'ct':ct[:80]}
     if 'json' in ct:
      payload=r.json();cand=[];candidates(payload,cand);item['shape']=shape(payload);item['candidates']=cand[:8]
     seen.append(item)
    except Exception as e:
     pass
   page.on('response',on_response)
   try:
    page.goto(url,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(7000)
    # scroll/click only benign search/list navigation controls; never login/apply.
    for txt in ('搜索','查询','职位列表','校园招聘'):
     try:
      loc=page.get_by_text(txt,exact=True).first
      if loc.is_visible():loc.click(timeout=1200);page.wait_for_timeout(2200)
     except Exception:pass
    body=page.locator('body').inner_text(timeout=3000)[:2500]
    print('PROBE',name,json.dumps({'final_url':page.url,'title':page.title(),'body':body,'responses':seen},ensure_ascii=False))
   except Exception as e:
    print('PROBE_ERROR',name,type(e).__name__,str(e)[:300],json.dumps(seen,ensure_ascii=False))
   ctx.close()
  browser.close()
if __name__=='__main__':main()
