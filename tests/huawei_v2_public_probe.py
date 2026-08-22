#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
API_TOKEN = "/recruitmentPosition/pub/getJobPage"


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def main() -> int:
    rows_by_page = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="zh-CN")
        page = context.new_page()

        def on_response(response):
            if API_TOKEN not in response.url:
                return
            try:
                payload = response.json()
                data = payload.get("data") or {}
                pvo = data.get("pageVO") or {}
                rows = data.get("result") or []
                current = int(pvo.get("curPage") or 0)
                if current and isinstance(rows, list):
                    rows_by_page[current] = rows
                    print("CAPTURE_PAGE", current, "ROWS", len(rows), "TOTAL", pvo.get("totalRows"), "PAGES", pvo.get("totalPages"))
            except Exception as exc:
                print("CAPTURE_ERROR", type(exc).__name__, str(exc))

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(8000)

        print("PAGINATION_CANDIDATES", json.dumps(page.evaluate("""() => {
          const out=[];
          for(const el of document.querySelectorAll('body *')){
            const text=(el.innerText||el.textContent||'').trim();
            if(!/^[1-7]$/.test(text))continue;
            const rect=el.getBoundingClientRect();
            if(rect.width<2||rect.height<2)continue;
            let node=el, chain=[];
            for(let i=0;i<4&&node;i++,node=node.parentElement){
              chain.push({tag:node.tagName, cls:String(node.className||''), id:node.id||'', text:(node.innerText||node.textContent||'').trim().slice(0,120), role:node.getAttribute&&node.getAttribute('role'), aria:node.getAttribute&&node.getAttribute('aria-label')});
            }
            out.push({n:text,tag:el.tagName,cls:String(el.className||''),chain});
          }
          return out.slice(0,120);
        }"""), ensure_ascii=False))

        for target in range(2, 8):
            if target in rows_by_page:
                continue
            clicked = page.evaluate("""n => {
              const nodes=Array.from(document.querySelectorAll('body *')).filter(el=>{
                const text=(el.innerText||el.textContent||'').trim();
                if(text!==String(n))return false;
                const r=el.getBoundingClientRect();
                if(r.width<2||r.height<2)return false;
                const cs=getComputedStyle(el);
                return el.tagName==='LI'||el.tagName==='A'||el.tagName==='BUTTON'||cs.cursor==='pointer'||(el.parentElement&&getComputedStyle(el.parentElement).cursor==='pointer');
              });
              nodes.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height);
              const el=nodes[0];
              if(!el)return {ok:false,count:nodes.length};
              el.click();
              return {ok:true,count:nodes.length,tag:el.tagName,cls:String(el.className||'')};
            }""", target)
            print("CLICK_PAGE", target, json.dumps(clicked, ensure_ascii=False))
            page.wait_for_timeout(1800)

        print("FINAL_PAGES", sorted(rows_by_page), "TOTAL_ROWS_CAPTURED", sum(len(v) for v in rows_by_page.values()))
        for pno in sorted(rows_by_page):
            print("PAGE_ROLES", pno, [r.get("jobName") for r in rows_by_page[pno]])
        context.close(); browser.close()
    return 0 if len(rows_by_page) >= 7 and sum(len(v) for v in rows_by_page.values()) >= 60 else 2


if __name__ == "__main__":
    raise SystemExit(main())
