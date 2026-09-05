#!/usr/bin/env python3
import json
import shutil
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright


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


def rows_from(payload: Any) -> list[dict[str, Any]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get("list") if isinstance(result, dict) else None
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def summarize(response) -> dict[str, Any]:
    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else {}
    rows = rows_from(payload)
    return {
        "url": response.url,
        "status": response.status,
        "code": payload.get("code"),
        "meta": scalar_meta(result),
        "count": len(rows),
        "ids": [str(x.get("id") or x.get("code") or "") for x in rows],
        "names": [str(x.get("name") or "") for x in rows],
    }


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome unavailable")


def wait_page(page, nature: str, page_num: int, action):
    def ok(response):
        if "positions/simple" not in response.url or f"positionNatureCode={nature}" not in response.url or "workLocationCode=" in response.url:
            return False
        try:
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            return payload.get("code") in (0, "0", 200, "200") and isinstance(result, dict) and int(result.get("pageNum") or 0) == page_num
        except Exception:
            return False
    with page.expect_response(ok, timeout=15000) as info:
        action()
    return summarize(info.value)


def set_hash(page, value: str):
    page.evaluate("value => { location.hash = value; }", value)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chrome(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        try:
            first = wait_page(
                page, "C002", 1,
                lambda: page.goto("https://zhaopin.kuaishou.cn/recruit/e/#/official/trainee/?pageNum=1", wait_until="domcontentloaded", timeout=30000),
            )
            page2 = wait_page(page, "C002", 2, lambda: set_hash(page, "/official/trainee/?pageNum=2"))
            last = wait_page(page, "C002", 111, lambda: set_hash(page, "/official/trainee/?pageNum=111"))

            # Validate the detail-route convention against a concrete public row,
            # rather than assuming the social-recruiting route also applies here.
            position_id = first["ids"][1] if len(first["ids"]) > 1 else first["ids"][0]
            role = first["names"][1] if len(first["names"]) > 1 else first["names"][0]
            candidate = f"https://zhaopin.kuaishou.cn/recruit/e/#/official/trainee/job-info/{position_id}"
            page.goto(candidate, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            body = " ".join(page.locator("body").inner_text(timeout=5000).split())
            detail = {
                "candidate": candidate,
                "final_url": page.url,
                "title": page.title(),
                "position_id": position_id,
                "role": role,
                "role_present": role in body,
                "body": body[:1200],
            }
            print(json.dumps({
                "trainee_unfiltered": {"page1": first, "page2": page2, "page111": last},
                "detail_route": detail,
            }, ensure_ascii=False))
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
