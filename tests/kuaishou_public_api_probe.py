#!/usr/bin/env python3
import json
import shutil
import sys
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

CAMPUS_URL = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
PROJECTS = {
    "fulltime_2027": "20271779425607",
    "retention_intern_2027": "20271772783534",
}
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
        if any(part in low for part in SENSITIVE_HEADER_PARTS) or low.startswith("sec-ch-"):
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
    summary = summarize_payload(response.json())
    summary["page"] = page
    return summary


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def successful_response(response) -> dict[str, Any] | None:
    if "positions/simple" not in response.url:
        return None
    try:
        summary = summarize_payload(response.json())
    except Exception:
        return None
    if summary.get("code") not in (0, "0", 200, "200"):
        return None
    return {"url": response.url, "status": response.status, "safe_headers": safe_headers(response.request.headers), **summary}


def wait_job_response(page, *, nature: str, page_num: int, action, timeout: int = 12000) -> dict[str, Any]:
    def predicate(response):
        if "positions/simple" not in response.url or f"positionNatureCode={nature}" not in response.url:
            return False
        try:
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            return payload.get("code") in (0, "0", 200, "200") and isinstance(result, dict) and int(result.get("pageNum") or 0) == page_num
        except Exception:
            return False

    with page.expect_response(predicate, timeout=timeout) as info:
        action()
    item = successful_response(info.value)
    if not item:
        raise RuntimeError(f"no successful {nature} page {page_num} response")
    return item


def set_hash_page(page, route: str, nature: str, page_num: int) -> dict[str, Any]:
    target = f"{route}?pageNum={page_num}&workLocationCode=domestic"
    return wait_job_response(
        page,
        nature=nature,
        page_num=page_num,
        action=lambda: page.evaluate("url => { location.hash = url.split('#')[1]; }", target),
    )


def probe_browser() -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        try:
            social_route = "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/"
            page.goto(social_route, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            nav = page.locator("a").evaluate_all("els => els.map(e => ({text:(e.innerText||e.textContent||'').trim(), href:e.href})).filter(x => x.text || x.href)")
            nav = [x for x in nav if any(k in (x.get('text') or '') for k in ('社会招聘','日常实习','校园招聘'))]

            social_pages = {}
            for n in (2, 50, 140):
                social_pages[str(n)] = set_hash_page(page, "#/official/social/", "C001", n)

            # Navigate by the official visible link, then exercise hash pagination in the same SPA.
            daily = page.get_by_text("日常实习", exact=True)
            first_daily = wait_job_response(page, nature="C002", page_num=1, action=lambda: daily.first.click(timeout=5000))
            daily_route = page.url
            daily_pages = {"1": first_daily}
            for n in (2, 50, 111):
                daily_pages[str(n)] = set_hash_page(page, "#/official/trainee/", "C002", n)

            # Verify the actual public detail route through UI navigation; do not infer it.
            page.evaluate("url => { location.hash = url.split('#')[1]; }", "#/official/trainee/?pageNum=1&workLocationCode=domestic")
            time.sleep(3)
            body_before = page.url
            detail_url = ""
            detail_title = ""
            # The job title is rendered in a table. Click the first row/title-like link if available.
            links = page.locator("a")
            for i in range(min(links.count(), 80)):
                href = links.nth(i).get_attribute("href") or ""
                text = " ".join((links.nth(i).inner_text(timeout=1000) or "").split())
                if text and ("job-info" in href or (len(text) >= 4 and text not in {"社会招聘","日常实习","校园招聘","关于快手","注册/登录"})):
                    try:
                        links.nth(i).click(timeout=3000)
                        time.sleep(2)
                        if "job-info" in page.url:
                            detail_url = page.url
                            detail_title = page.title()
                            break
                        page.go_back(wait_until="domcontentloaded", timeout=10000)
                    except Exception:
                        continue

            return {
                "nav": nav,
                "social_pages": social_pages,
                "daily_route": daily_route,
                "daily_pages": daily_pages,
                "daily_detail": {"before": body_before, "url": detail_url, "title": detail_title},
                "browser_cookie_names": sorted({c["name"] for c in page.context.cookies()}),
            }
        finally:
            browser.close()


def main() -> int:
    for label, project in PROJECTS.items():
        print(json.dumps({label: {"project": project, "pages": [fetch_campus(project, page) for page in (1, 13, 23)]}}, ensure_ascii=False))
    print(json.dumps({"experienced_spa_pagination": probe_browser()}, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
