#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URLS = [
    "https://campus.kuaishou.cn/#/campus/jobs",
    "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs",
    "https://zhaopin.kuaishou.cn/#/official/social/",
    "https://zhaopin.kuaishou.cn/#/official/intern/",
]
LEGACY_API = "https://zhaopin.kuaishou.cn/recruit/api/job/list?page=1&pageSize=50&workCity=&jobType="
HINT = re.compile(r"job|position|recruit|career|campus|intern|social|list|search|query", re.I)


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def walk(value, path="root", depth=0):
    if depth > 9:
        return
    if isinstance(value, dict):
        keys = {str(k).lower() for k in value}
        title = next((value.get(k) for k in value if str(k).lower() in {"jobname","job_name","jobtitle","job_title","positionname","position_name","title","name"}), None)
        ident = next((value.get(k) for k in value if str(k).lower() in {"jobid","job_id","positionid","position_id","id","code"}), None)
        if title and (ident or any(HINT.search(k) for k in keys)):
            yield path, value
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                yield from walk(v, f"{path}.{k}", depth + 1)
    elif isinstance(value, list):
        for i, v in enumerate(value[:3000]):
            if isinstance(v, (dict, list)):
                yield from walk(v, f"{path}[{i}]", depth + 1)


def summarize_payload(payload):
    if not isinstance(payload, (dict, list)):
        return {"kind": type(payload).__name__}
    rows = []
    for path, row in walk(payload):
        rows.append({"path": path, "keys": list(row.keys())[:70], "sample": {k: row.get(k) for k in list(row.keys())[:40]}})
        if len(rows) >= 8:
            break
    return {
        "top_keys": list(payload.keys())[:50] if isinstance(payload, dict) else [f"list:{len(payload)}"],
        "jobish": rows,
    }


def main() -> int:
    all_useful = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="zh-CN")

        try:
            r = context.request.get(LEGACY_API, timeout=20000)
            raw = r.text()
            try:
                payload = json.loads(raw)
            except Exception:
                payload = None
            print("LEGACY_API", r.status, r.headers.get("content-type"), json.dumps(summarize_payload(payload), ensure_ascii=False), raw[:500])
            if isinstance(payload, (dict, list)) and summarize_payload(payload).get("jobish"):
                all_useful.append({"url": LEGACY_API, **summarize_payload(payload)})
        except Exception as exc:
            print("LEGACY_API_ERROR", type(exc).__name__, str(exc)[:300])

        for start in URLS:
            page = context.new_page()
            captures = []

            def on_response(response):
                try:
                    host = urlparse(response.url).hostname or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    if "kuaishou" not in host and "ssrcdn" not in host:
                        return
                    if "json" not in ctype and not HINT.search(response.url):
                        return
                    record = {
                        "url": response.url,
                        "status": response.status,
                        "ctype": ctype,
                        "resource": response.request.resource_type,
                        "method": response.request.method,
                        "post_data": response.request.post_data,
                    }
                    try:
                        payload = response.json()
                    except Exception:
                        payload = None
                    if isinstance(payload, (dict, list)):
                        record.update(summarize_payload(payload))
                    captures.append(record)
                except Exception as exc:
                    captures.append({"handler_error": f"{type(exc).__name__}: {exc}"})

            page.on("response", on_response)
            try:
                page.goto(start, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(8000)
                # Click obvious job/recruit tabs if this route resolved back to a shell.
                for label in ("应届招聘", "实习招聘", "社会招聘", "日常实习", "校园招聘"):
                    try:
                        loc = page.get_by_text(label, exact=True)
                        if loc.count() and loc.first.is_visible():
                            loc.first.click(timeout=1500)
                            page.wait_for_timeout(3500)
                    except Exception:
                        pass
                for frac in (0.4, 0.8, 1.0):
                    page.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{frac})")
                    page.wait_for_timeout(800)
                print("START", start)
                print("FINAL_URL", page.url)
                print("TITLE", page.title())
                print("BODY", json.dumps(page.locator("body").inner_text()[:9000], ensure_ascii=False))
                useful = [x for x in captures if x.get("jobish")]
                print("USEFUL", json.dumps(useful[:30], ensure_ascii=False))
                print("CANDIDATE_NETWORK", json.dumps([x for x in captures if HINT.search(x.get("url", ""))][:100], ensure_ascii=False))
                all_useful.extend(useful)
            except Exception as exc:
                print("PAGE_ERROR", start, type(exc).__name__, str(exc)[:300])
            finally:
                page.close()
        context.close(); browser.close()
    print("USEFUL_COUNT", len(all_useful))
    return 0 if all_useful else 2


if __name__ == "__main__":
    raise SystemExit(main())
