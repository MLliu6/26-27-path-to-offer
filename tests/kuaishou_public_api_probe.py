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
    result = payload.get("result")
    rows = rows_from(result)
    return {
        "page": page,
        "meta": scalar_meta(result),
        "count": len(rows),
        "ids": [str(x.get("id") or x.get("code") or "") for x in rows],
        "names": [str(x.get("name") or "") for x in rows[:3]],
    }


def fetch_experienced(nature: str, page: int = 1) -> dict[str, Any]:
    params = {"pageNum": page, "pageSize": 10, "positionNatureCode": nature}
    if nature == "C001":
        params["recruitProject"] = "socialr"
    response = requests.get(
        EXPERIENCED_URL,
        params=params,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 Path-to-Offer public recruitment regression"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") not in (0, 200, "0", "200", None):
        raise RuntimeError(f"unexpected response: {payload!r}")
    result = payload.get("result")
    rows = rows_from(result)
    return {
        "nature": nature,
        "page": page,
        "meta": scalar_meta(result),
        "count": len(rows),
        "ids": [str(x.get("id") or x.get("code") or "") for x in rows],
        "names": [str(x.get("name") or "") for x in rows[:8]],
        "locations": [str(x.get("workLocationCode") or "") for x in rows[:8]],
    }


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def probe_route(route: str) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        try:
            page.goto(route, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            hrefs = page.locator("a").evaluate_all("els => els.map(e => e.href).filter(Boolean)")
            links = [x for x in hrefs if "job-info" in x][:10]
            before = page.url
            clicked = ""
            if not links:
                candidates = page.get_by_text("查看职位", exact=False)
                if candidates.count():
                    try:
                        candidates.first.click(timeout=5000)
                        time.sleep(2)
                        clicked = page.url
                    except Exception:
                        pass
            return {
                "requested": route,
                "final_url": before,
                "title": page.title(),
                "job_links": links,
                "clicked_url": clicked,
                "body": " ".join(page.locator("body").inner_text(timeout=5000).split())[:1000],
            }
        finally:
            browser.close()


def main() -> int:
    report = {}
    for label, project in PROJECTS.items():
        pages = [fetch_campus(project, page) for page in PAGES]
        report[label] = {"project": project, "pages": pages}
        print(json.dumps({label: report[label]}, ensure_ascii=False))

    for label, nature in (("experienced_social", "C001"), ("daily_intern", "C002")):
        data = fetch_experienced(nature, 1)
        print(json.dumps({label: data}, ensure_ascii=False))

    for label, route in (
        ("social_route", "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/"),
        ("daily_intern_route", "https://zhaopin.kuaishou.cn/recruit/e/#/official/intern/"),
    ):
        print(json.dumps({label: probe_route(route)}, ensure_ascii=False))

    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
