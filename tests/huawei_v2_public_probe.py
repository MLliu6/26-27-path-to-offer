#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
HINT = re.compile(r"job|position|recruit|career|campus|search|list", re.I)


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
        ident = next((value.get(k) for k in value if str(k).lower() in {"id","jobid","job_id","positionid","position_id","code"}), None)
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
                if "huawei.com" not in (parsed.hostname or ""):
                    return
                if "json" not in ctype and not HINT.search(response.url):
                    return
                record = {"url": response.url, "status": response.status, "ctype": ctype, "resource": response.request.resource_type}
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if isinstance(payload, (dict, list)):
                    rows = []
                    for path, row in walk(payload):
                        rows.append({"path": path, "keys": list(row.keys())[:40], "sample": {k: row.get(k) for k in list(row.keys())[:20]}})
                        if len(rows) >= 4:
                            break
                    record["top_keys"] = list(payload.keys())[:40] if isinstance(payload, dict) else [f"list:{len(payload)}"]
                    record["jobish"] = rows
                captures.append(record)
            except Exception as exc:
                captures.append({"handler_error": f"{type(exc).__name__}: {exc}"})

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(9000)
        for fraction in (0.35, 0.7, 1.0):
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{fraction})")
            page.wait_for_timeout(1200)

        links = page.eval_on_selector_all("a[href]", "els => els.slice(0,2500).map(a=>({text:(a.innerText||a.textContent||'').trim(),href:a.href})).filter(x=>x.text||/job|position|recruit/i.test(x.href))")
        body = page.locator("body").inner_text()[:12000]
        print("FINAL_URL", page.url)
        print("TITLE", page.title())
        print("BODY_SAMPLE", json.dumps(body[:4000], ensure_ascii=False))
        print("LINK_SAMPLE", json.dumps(links[:80], ensure_ascii=False))
        print("CAPTURES", json.dumps(captures[:80], ensure_ascii=False))
        useful = [x for x in captures if x.get("jobish")]
        print("USEFUL_COUNT", len(useful))
        context.close(); browser.close()
    return 0 if useful or links else 2


if __name__ == "__main__":
    raise SystemExit(main())
