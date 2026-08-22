#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
HINT = re.compile(r"job|position|recruit|career|campus|search|list|detail", re.I)


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def walk(value, path="root", depth=0):
    if depth > 10:
        return
    if isinstance(value, dict):
        keys = {str(k).lower() for k in value}
        title = next((value.get(k) for k in value if str(k).lower() in {"title","jobname","job_name","jobtitle","job_title","positionname","position_name","name"}), None)
        ident = next((value.get(k) for k in value if str(k).lower() in {"id","jobid","job_id","positionid","position_id","advertisementsintegrationid","advertisementid","code"}), None)
        if title and (ident or any(HINT.search(k) for k in keys)):
            yield path, value
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                yield from walk(v, f"{path}.{k}", depth + 1)
    elif isinstance(value, list):
        for i, v in enumerate(value[:3000]):
            if isinstance(v, (dict, list)):
                yield from walk(v, f"{path}[{i}]", depth + 1)


def main() -> int:
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        page = context.new_page()

        def on_response(response):
            try:
                parsed = urlparse(response.url)
                ctype = (response.headers.get("content-type") or "").lower()
                host = (parsed.hostname or "").lower()
                if "huawei.com" not in host:
                    return
                if "json" not in ctype and not HINT.search(response.url):
                    return
                req = response.request
                record = {
                    "url": response.url,
                    "status": response.status,
                    "ctype": ctype,
                    "resource": req.resource_type,
                    "method": req.method,
                    "post_data": req.post_data,
                }
                try:
                    headers = req.all_headers()
                except Exception:
                    headers = req.headers or {}
                record["request_headers"] = {k.lower(): v for k, v in headers.items() if k.lower() in {"content-type","x-hw-id","origin","referer","accept-language"}}
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if isinstance(payload, (dict, list)):
                    rows = []
                    for path, row in walk(payload):
                        rows.append({"path": path, "keys": list(row.keys())[:60], "sample": {k: row.get(k) for k in list(row.keys())[:55]}})
                        if len(rows) >= 4:
                            break
                    record["top_keys"] = list(payload.keys())[:40] if isinstance(payload, dict) else [f"list:{len(payload)}"]
                    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                        data = payload["data"]
                        record["data_keys"] = list(data.keys())[:50]
                        page_vo = data.get("pageVO") if isinstance(data.get("pageVO"), dict) else {}
                        record["page_vo"] = page_vo
                    record["jobish"] = rows
                captures.append(record)
            except Exception as exc:
                captures.append({"handler_error": f"{type(exc).__name__}: {exc}"})

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(8500)

        useful_before = [x for x in captures if x.get("jobish")]
        print("LIST_USEFUL", json.dumps(useful_before[:10], ensure_ascii=False))

        target = page.get_by_text("AI Infra工程师", exact=True)
        print("TARGET_COUNT", target.count())
        if target.count():
            try:
                info = target.first.evaluate("""el => {
                  let node=el;
                  const chain=[];
                  for(let i=0;i<7 && node;i++,node=node.parentElement){
                    chain.push({tag:node.tagName,cls:node.className||'',id:node.id||'',href:node.href||'',role:node.getAttribute&&node.getAttribute('role'),data:Object.fromEntries(Array.from(node.attributes||[]).filter(a=>a.name.startsWith('data-')).map(a=>[a.name,a.value]))});
                  }
                  return chain;
                }""")
                print("TARGET_CHAIN", json.dumps(info, ensure_ascii=False))
            except Exception as exc:
                print("TARGET_CHAIN_ERROR", type(exc).__name__, str(exc))

            before_pages = len(context.pages)
            try:
                target.first.click(timeout=5000)
                page.wait_for_timeout(6000)
            except Exception as exc:
                print("CLICK_ERROR", type(exc).__name__, str(exc))
            print("PAGES_AFTER_CLICK", len(context.pages), "BEFORE", before_pages)
            for idx, pg in enumerate(context.pages):
                print("PAGE", idx, pg.url, pg.title())
                try:
                    print("PAGE_BODY", idx, json.dumps(pg.locator('body').inner_text()[:3500], ensure_ascii=False))
                except Exception:
                    pass

        useful_after = [x for x in captures if x.get("jobish") or ("detail" in x.get("url", "").lower())]
        print("AFTER_USEFUL", json.dumps(useful_after[-20:], ensure_ascii=False))
        context.close(); browser.close()
    return 0 if useful_before else 2


if __name__ == "__main__":
    raise SystemExit(main())
