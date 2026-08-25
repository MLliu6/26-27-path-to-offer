#!/usr/bin/env python3
import json
import shutil
import sys
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

CAMPUS_URL = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
EXPERIENCED_URL = "https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple"
EXPERIENCED_HOME = "https://zhaopin.kuaishou.cn/recruit/e/"
PROJECTS = {
    "fulltime_2027": "20271779425607",
    "retention_intern_2027": "20271772783534",
}
PAGES = (1, 13, 23)
SENSITIVE_HEADER_PARTS = ("cookie", "auth", "token", "secret", "key", "signature", "sign")


def scalar_meta(value: Any, prefix: str = "root", depth: int = 0) -> dict[str, Any]:
    out = {}
    if depth > 4:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            low = str(key).lower()
            if not isinstance(child, (dict, list)) and any(x in low for x in ("total", "count", "page", "size", "num")):
                out[path] = child
            elif isinstance(child, (dict, list)):
                out.update(scalar_meta(child, path, depth + 1))
    return out


def rows_from(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        rows = result.get("list")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def summarize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"kind": type(payload).__name__}
    result = payload.get("result")
    rows = rows_from(result)
    return {
        "code": payload.get("code"),
        "message": payload.get("message"),
        "meta": scalar_meta(result),
        "count": len(rows),
        "ids": [str(x.get("id") or x.get("code") or "") for x in rows[:10]],
        "names": [str(x.get("name") or "") for x in rows[:10]],
        "locations": [str(x.get("workLocationCode") or "") for x in rows[:10]],
    }


def safe_headers(headers: dict[str, str]) -> dict[str, str]:
    result = {}
    for key, value in headers.items():
        low = key.lower()
        if any(part in low for part in SENSITIVE_HEADER_PARTS):
            continue
        if low.startswith("sec-ch-"):
            continue
        result[low] = value[:300]
    return dict(sorted(result.items()))


def fetch_campus(project: str, page: int) -> dict[str, Any]:
    response = requests.post(
        CAMPUS_URL,
        json={"recruitSubProjectCodes": [project], "pageSize": 10, "pageNum": page},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 Path-to-Offer public recruitment regression"},
    )
    response.raise_for_status()
    payload = response.json()
    summary = summarize_payload(payload)
    summary["page"] = page
    return summary


def fetch_experienced(nature: str) -> dict[str, Any]:
    params = {"pageNum": 1, "pageSize": 10, "positionNatureCode": nature}
    if nature == "C001":
        params["recruitProject"] = "socialr"
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*", "Referer": EXPERIENCED_HOME})
    warm = session.get(EXPERIENCED_HOME, timeout=20)
    response = session.get(EXPERIENCED_URL, params=params, timeout=20)
    result = {"nature": nature, "warm_status": warm.status_code, "status": response.status_code, "url": response.url, "cookie_names": sorted(session.cookies.keys())}
    try:
        result.update(summarize_payload(response.json()))
    except Exception:
        result["body"] = " ".join(response.text.split())[:500]
    return result


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def probe_browser() -> dict[str, Any]:
    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="zh-CN")

        def on_response(response):
            if "positions/simple" not in response.url:
                return
            item = {"url": response.url, "status": response.status, "safe_headers": safe_headers(response.request.headers)}
            try:
                item.update(summarize_payload(response.json()))
            except Exception:
                pass
            captured.append(item)

        page.on("response", on_response)
        try:
            page.goto("https://zhaopin.kuaishou.cn/recruit/e/#/official/social/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            nav = page.locator("a").evaluate_all("els => els.map(e => ({text:(e.innerText||e.textContent||'').trim(), href:e.href})).filter(x => x.text || x.href)")
            nav = [x for x in nav if any(k in (x.get('text') or '') for k in ('社会招聘','日常实习','校园招聘'))]
            social_initial = [x for x in captured if "positionNatureCode=C001" in x.get("url", "") and x.get("code") == 0]

            # Let the official app itself switch route; capture its C002 request context.
            before = len(captured)
            daily = page.get_by_text("日常实习", exact=True)
            daily.first.click(timeout=5000)
            time.sleep(5)
            daily_new = captured[before:]

            return {
                "nav": nav,
                "social_url": "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/",
                "daily_url": page.url,
                "daily_title": page.title(),
                "social_success": social_initial[:4],
                "daily_success": [x for x in daily_new if "positionNatureCode=C002" in x.get("url", "") and x.get("code") == 0][:4],
                "browser_cookie_names": sorted({c["name"] for c in page.context.cookies()}),
            }
        finally:
            browser.close()


def main() -> int:
    for label, project in PROJECTS.items():
        print(json.dumps({label: {"project": project, "pages": [fetch_campus(project, page) for page in PAGES]}}, ensure_ascii=False))
    print(json.dumps({"experienced_social_requests": fetch_experienced("C001")}, ensure_ascii=False))
    print(json.dumps({"daily_intern_requests": fetch_experienced("C002")}, ensure_ascii=False))
    print(json.dumps({"browser_request_context": probe_browser()}, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
