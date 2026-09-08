#!/usr/bin/env python3
from __future__ import annotations
import json,re,shutil
from playwright.sync_api import sync_playwright

URL='https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1'

def chrome():
 for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
  p=shutil.which(n)
  if p:return p
 raise SystemExit('no chrome')

def main():
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=chrome(),args=['--no-sandbox','--disable-dev-shm-usage'])
  ctx=browser.new_context(locale='zh-CN');page=ctx.new_page();requests=[];samples=[]
  def req(r):
   if 'campusRecruitmentWebsite/job/' in r.url:
    requests.append({'url':r.url,'method':r.method,'post_data':(r.post_data or '')[:4000]})
  def resp(r):
   if '/job/getList' not in r.url:return
   try:
    payload=r.json();body=payload.get('body') or {};data=body.get('data') or []
    samples.extend(data[:3])
    print('CMB_RESPONSE',json.dumps({'total':body.get('total'),'sample':data[:3]},ensure_ascii=False)[:16000])
   except Exception as e:print('CMB_RESPONSE_ERROR',type(e).__name__,str(e))
  page.on('request',req);page.on('response',resp)
  page.goto(URL,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(9000)
  print('CMB_REQUESTS',json.dumps(requests,ensure_ascii=False))
  print('CMB_PAGE',json.dumps({'url':page.url,'body':page.locator('body').inner_text()[:3500]},ensure_ascii=False))
  ctx.close();browser.close()
if __name__=='__main__':main()
