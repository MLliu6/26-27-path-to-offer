#!/usr/bin/env python3
"""Diagnostic probe for the public NCSS job-search frontend.

Used while developing the NCSS adapter: open the public 2027 search page in the
same system Chrome used by CI and print same-origin JSON/XHR endpoints. No login
or authenticated state is created. The probe is not part of the production feed.
"""
from __future__ import annotations

import re
import shutil
import time
from playwright.sync_api import sync_playwright

URL="https://www.ncss.cn/student/jobs/index.html?jobName=2027"


def browser_path():
    for name in ("google-chrome","google-chrome-stable","chromium","chromium-browser"):
        p=shutil.which(name)
        if p:return p
    raise RuntimeError("Chrome/Chromium not available")


def main():
    seen=set()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=["--no-sandbox","--disable-dev-shm-usage"])
        ctx=browser.new_context(viewport={"width":1360,"height":900},locale="zh-CN")
        page=ctx.new_page()
        def on_response(resp):
            u=resp.url
            if "ncss.cn" not in u or u in seen:return
            ctype=(resp.headers.get("content-type") or "").lower()
            if not ("json" in ctype or re.search(r"/(api|job|position|search|query|list)",u,re.I)):return
            seen.add(u)
            snippet=""
            try:
                body=resp.text()
                if len(body)<=2_000_000:snippet=re.sub(r"\s+"," ",body)[:1200]
            except Exception as exc:snippet=f"<body unavailable: {type(exc).__name__}>"
            print("NCSS_RESPONSE",resp.status,ctype,u,"SNIP",snippet,flush=True)
        page.on("response",on_response)
        page.goto(URL,wait_until="domcontentloaded",timeout=45000)
        page.wait_for_timeout(12000)
        print("NCSS_TITLE",page.title(),flush=True)
        print("NCSS_VISIBLE",re.sub(r"\s+"," ",page.locator("body").inner_text())[:3000],flush=True)
        inputs=page.locator("input")
        for i in range(min(inputs.count(),12)):
            el=inputs.nth(i)
            try:print("NCSS_INPUT",i,el.get_attribute("placeholder"),el.get_attribute("name"),el.get_attribute("class"),flush=True)
            except Exception:pass
        ctx.close();browser.close()
    return 0

if __name__=="__main__":raise SystemExit(main())
