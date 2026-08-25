#!/usr/bin/env python3
import json
import shutil
import sys
import time
from typing import Any
from urllib.parse import urlencode

import requests
from playwright.sync_api import sync_playwright

CAMPUS_URL = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
EXPERIENCED_URL = "https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple"
EXPERIENCED_HOME = "https://zhaopin.kuaishou.cn/recruit/e/"
PROJECTS = {
    "fulltime_2027": "20271779425607",
    "retention_intern_2027": "20271772783534",
}
PAGES = (1, 7, 8, 13, 23)


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
        for key in ("list", "rows", "records", "positions", "data"):
            rows = result.get(key)
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


def fetch_campus(project: str, page: int) -> dict[str, Any]:
    response = requests.post(
        CAMPUS_URL,
        json={"recruitSubProjectCodes": [project], "pageSize": 10, "pageNum": page},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 Path-to-Offer public recruitment regression"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") not in (0, 200, "0", "200", None):
        raise RuntimeError(f"unexpected response: {payload!r}")
    summary = summarize_payload(payload)
    summary["page"] = page
    return summary


def fetch_experienced(nature: str, page: int = 1) -> dict[str, Any]:
    params = {"pageNum": page, "pageSize": 10, "positionNatureCode": nature}
    if nature == "C001":
        params["recruitProject"] = "socialr"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://zhaopin.kuaishou.cn/recruit/e/",
    })
    warm = session.get(EXPERIENCED_HOME, timeout=20)
    response = session.get(EXPERIENCED_URL, params=params, timeout=20)
    result = {
        "nature": nature,
        "page": page,
        "warm_status": warm.status_code,
        "status": response.status_code,
        "url": response.url,
        "cookies": sorted(session.cookies.keys()),
    }
    try:
        result.update(summarize_payload(response.json()))
    except Exception:
        result["body"] = " ".join(response.text.split())[:700]
    return result


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def browser_fetch(page, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    return page.evaluate(
        """async (url) => {
          const r = await fetch(url, {credentials:'include', headers:{Accept:'application/json, text/plain, */*'}});
          let body = null;
          try { body = await r.json(); } catch (_) { body = {text:(await r.text()).slice(0,500)}; }
          return {status:r.status, url:r.url, body};
        }""",
        f"{EXPERIENCED_URL}?{query}",
    )


def probe_browser() -> dict[str, Any]:
    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="zh-CN")

        def on_response(response):
            if "positions/simple" not in response.url:
                return
            item = {"url": response.url, "status": response.status, "request_headers": {k: v for k, v in response.request.headers.items() if k.lower() in {"accept", "referer", "origin", "content-type", "channelcode", "channel-code"}}}
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
            nav = [x for x in nav if any(k in (x.get('text') or '') for k in ('社会招聘','日常实习','校园招聘','职位')) or 'official' in (x.get('href') or '')][:40]

            direct = {}
            for label, params in (
                ("social_10", {"pageNum":1,"pageSize":10,"positionNatureCode":"C001","recruitProject":"socialr"}),
                ("social_100", {"pageNum":1,"pageSize":100,"positionNatureCode":"C001","recruitProject":"socialr"}),
                ("intern_10", {"pageNum":1,"pageSize":10,"positionNatureCode":"C002"}),
                ("intern_100", {"pageNum":1,"pageSize":100,"positionNatureCode":"C002"}),
            ):
                raw = browser_fetch(page, params)
                direct[label] = {"status": raw.get("status"), "url": raw.get("url"), **summarize_payload(raw.get("body"))}

            daily_click = {"found": False, "url": "", "xhr": []}
            daily = page.get_by_text("日常实习", exact=True)
            if daily.count():
                daily_click["found"] = True
                before = len(captured)
                try:
                    daily.first.click(timeout=5000)
                    time.sleep(5)
                    daily_click["url"] = page.url
                    daily_click["title"] = page.title()
                    daily_click["body"] = " ".join(page.locator("body").inner_text(timeout=5000).split())[:1200]
                    daily_click["xhr"] = captured[before:][:10]
                    rows = page.locator("body").inner_text(timeout=5000).splitlines()
                    visible = [x.strip() for x in rows if x.strip()]
                    daily_click["visible_lines"] = visible[:80]
                except Exception as exc:
                    daily_click["error"] = f"{type(exc).__name__}: {exc}"

            return {
                "social_final_url": "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/",
                "nav": nav,
                "direct_browser_fetch": direct,
                "daily_click": daily_click,
                "captured_xhr": captured[:20],
            }
        finally:
            browser.close()


def main() -> int:
    for label, project in PROJECTS.items():
        pages = [fetch_campus(project, page) for page in PAGES]
        print(json.dumps({label: {"project": project, "pages": pages}}, ensure_ascii=False))

    for label, nature in (("experienced_social_requests", "C001"), ("daily_intern_requests", "C002")):
        print(json.dumps({label: fetch_experienced(nature, 1)}, ensure_ascii=False))

    print(json.dumps({"experienced_browser": probe_browser()}, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
