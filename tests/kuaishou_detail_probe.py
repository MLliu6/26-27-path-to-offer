from __future__ import annotations

import json
from playwright.sync_api import sync_playwright

TARGETS = [
    ("campus", "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs"),
    ("social", "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/"),
]


def first_job(payload):
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    rows = result.get("list")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    if row.get("id") and row.get("name"):
        return {"id": row.get("id"), "name": str(row.get("name"))}
    return None


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN")
        for label, url in TARGETS:
            page = context.new_page()
            observed = []
            api_first = []

            def on_response(response):
                u = response.url
                if any(x in u.lower() for x in ("position", "job", "recruit")):
                    observed.append((response.status, u))
                if "/positions/simple" in u and response.status == 200:
                    try:
                        item = first_job(response.json())
                        if item and item not in api_first:
                            api_first.append(item)
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            print("TARGET", label, "START", url)
            print("FINAL", page.url)
            print("API_FIRST", json.dumps(api_first[:4], ensure_ascii=False))
            if label == "campus":
                locator = page.get_by_text("查看职位", exact=True)
                print("VIEW_COUNT", locator.count())
                if locator.count():
                    locator.first.click(timeout=5000)
                    page.wait_for_timeout(1800)
                    print("AFTER_CLICK", page.url)
            elif api_first:
                name = api_first[-1]["name"]
                locator = page.get_by_text(name, exact=True)
                print("ROLE", json.dumps(name, ensure_ascii=False), "COUNT", locator.count())
                if locator.count():
                    try:
                        print("ROLE_META", json.dumps(locator.first.evaluate("el=>({tag:el.tagName,html:el.outerHTML.slice(0,1200)})"), ensure_ascii=False))
                        locator.first.click(timeout=5000)
                        page.wait_for_timeout(1800)
                        print("AFTER_CLICK", page.url)
                        print("AFTER_BODY", json.dumps(page.locator("body").inner_text()[:1600], ensure_ascii=False))
                    except Exception as exc:
                        print("CLICK_ERROR", type(exc).__name__, str(exc)[:300])
            print("OBSERVED", json.dumps(observed[-50:], ensure_ascii=False))
            page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
