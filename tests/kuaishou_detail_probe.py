from __future__ import annotations

import json
from playwright.sync_api import sync_playwright

TARGETS = [
    ("campus", "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs"),
    ("social", "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/"),
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN")
        for label, url in TARGETS:
            page = context.new_page()
            observed = []

            def on_response(response):
                u = response.url
                if any(x in u.lower() for x in ("position", "job", "recruit")):
                    observed.append((response.status, u))

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            print("TARGET", label, "START", url)
            print("FINAL", page.url)
            locator = page.get_by_text("查看职位", exact=True)
            print("VIEW_COUNT", locator.count())
            for i in range(min(locator.count(), 4)):
                item = locator.nth(i)
                try:
                    meta = item.evaluate(
                        """el => {
                            let n=el;
                            for(let i=0;i<5 && n;i++,n=n.parentElement){
                                if(n.tagName==='A' || n.getAttribute('href')) return {tag:n.tagName,href:n.href||n.getAttribute('href')||'',html:n.outerHTML.slice(0,900)};
                            }
                            return {tag:el.tagName,href:'',html:el.outerHTML.slice(0,900)};
                        }"""
                    )
                    print("VIEW_META", i, json.dumps(meta, ensure_ascii=False))
                except Exception as exc:
                    print("VIEW_META_ERROR", i, type(exc).__name__, str(exc)[:200])
            if locator.count():
                try:
                    locator.first.click(timeout=5000)
                    page.wait_for_timeout(2000)
                    print("AFTER_CLICK", page.url)
                    print("AFTER_BODY", json.dumps(page.locator("body").inner_text()[:1800], ensure_ascii=False))
                except Exception as exc:
                    print("CLICK_ERROR", type(exc).__name__, str(exc)[:300])
            print("OBSERVED", json.dumps(observed[-40:], ensure_ascii=False))
            page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
