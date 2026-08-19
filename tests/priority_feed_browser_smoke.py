#!/usr/bin/env python3
"""Browser regression for the ten-minute employer-direct priority feed."""
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
EXACT_ID = "5e4eb6f3-294f-491b-9d39-42895eed98c3"
EXACT_URL = f"https://careers.pddglobalhr.com/campus/grad/detail?positionId={EXACT_ID}"
DIDI_URL = "https://talent.didiglobal.com/social/p/58333"

PRIORITY = {
    "schema_version": 4,
    "generated_at": "2026-08-19T05:40:00Z",
    "jobs": [
        {
            "i": "pdd-exact-ai-infra",
            "c": "拼多多",
            "r": "AI Infra研发工程师",
            "l": "上海",
            "u": EXACT_URL,
            "n": EXACT_URL,
            "d": "大模型训练与推理基础设施研发，vLLM、PyTorch、GPU、RDMA、NVLink、分布式系统、C/C++、Python。",
            "t": "2026-05-08",
            "b": "2027届校园招聘 · 技术专场",
            "g": "2027届",
            "e": "硕士/博士",
            "y": "民营/互联网",
            "h": "互联网/电商/人工智能",
            "m": "技术",
            "x": "拼多多校园招聘官网 · 自主直连",
            "q": 7,
            "s": "direct-official:pdd",
            "z": EXACT_ID,
        },
        {
            "i": "didi-public-58333",
            "c": "滴滴",
            "r": "商务合作经理-越南",
            "l": "北京市",
            "u": DIDI_URL,
            "n": DIDI_URL,
            "d": "滴滴招聘官网公开职位，ABC平台，销售与客户服务。",
            "t": "2026-08-19",
            "b": "社会招聘",
            "y": "民营/互联网/出行",
            "h": "互联网/出行/人工智能",
            "m": "ABC平台",
            "x": "滴滴招聘官网 · 浏览器自主直连",
            "q": 7,
            "s": "direct-official:didi",
            "z": "58333",
        },
    ],
}
DOMESTIC = {
    "schema_version": 4,
    "generated_at": "2026-08-18T15:00:00Z",
    "jobs": [{
        "i": "generic-pdd-campaign",
        "c": "拼多多",
        "r": "研发类",
        "l": "上海",
        "n": "https://careers.pddglobalhr.com/campus/grad",
        "d": "2027校园招聘提前批，研发类、产品类、数据算法类。",
        "b": "2027校招提前批",
        "g": "2027届",
        "x": "重点企业 2027 招聘源",
        "q": 5,
    }],
}
PRIORITY_STATUS = {
    "generated_at": "2026-08-19T05:40:00Z",
    "catalog_count": 2,
    "nominal_interval_minutes": 10,
    "exact_pdd_position_ok": True,
    "sources": [
        {"name": "pdd-direct-official", "label": "拼多多校园招聘官网 · 全量自主直连", "url": "https://careers.pddglobalhr.com/campus/grad", "ok": True, "count": 24, "preserved_previous": False, "error": ""},
        {"name": "didi-direct-official", "label": "滴滴招聘官网 · 浏览器自主直连", "url": "https://talent.didiglobal.com/", "ok": True, "count": 16, "preserved_previous": False, "error": ""},
    ],
}
DOMESTIC_STATUS = {
    "generated_at": "2026-08-18T15:00:00Z",
    "catalog_count": 1,
    "sources": [{"name": "qa-domestic", "label": "全国深度联邦", "ok": True, "count": 1, "error": ""}],
}


def browser_path() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium not available")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        def route_handler(route):
            url = route.request.url
            if "/data/jobs_priority.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(PRIORITY, ensure_ascii=False))
            elif "/data/jobs_cn.json" in url or "/data/jobs.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(DOMESTIC, ensure_ascii=False))
            elif "/data/priority_source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(PRIORITY_STATUS, ensure_ascii=False))
            elif "/data/source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(DOMESTIC_STATUS, ensure_ascii=False))
            elif url.startswith("https://cdn.jsdelivr.net/"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_function("() => window.PTO_PRIORITY_FEED_READY === true && window.PTO_V12_RENDERFIX_READY === true", timeout=20_000)
        page.wait_for_selector("#priorityFeedChip")
        assert "10 min" in page.locator("#priorityFeedChip").inner_text()

        # Exact PDD first-party position remains searchable and reaches the
        # employer-owned detail URL.
        page.locator("#jobSearch").fill("AI Infra研发工程师")
        exact = page.locator('.market-card[data-market-id="pdd-exact-ai-infra"]')
        exact.wait_for(timeout=8_000)
        assert "拼多多" in exact.inner_text() and "AI Infra研发工程师" in exact.inner_text()
        assert page.locator('.market-card[data-market-id="generic-pdd-campaign"]').count() == 0
        page.locator('.market-card[data-market-id="pdd-exact-ai-infra"] [data-open-detail="pdd-exact-ai-infra"]').click()
        page.wait_for_selector("#marketJobDetail:not(.hidden)")
        detail = page.locator("#marketJobDetail").inner_text()
        assert "vLLM" in detail and "分布式系统" in detail
        assert page.locator(f'#marketJobDetail a[href="{EXACT_URL}"]').count() >= 1
        page.locator("#closeDrawer").click()

        # Regression for the user's production report: a concrete DiDi row from
        # the ten-minute first-party feed must be discoverable by company search.
        page.locator("#jobSearch").fill("滴滴")
        didi = page.locator('.market-card[data-market-id="didi-public-58333"]')
        didi.wait_for(timeout=8_000)
        assert "滴滴" in didi.inner_text()
        page.locator('.market-card[data-market-id="didi-public-58333"] [data-open-detail="didi-public-58333"]').click()
        page.wait_for_selector("#marketJobDetail:not(.hidden)")
        assert page.locator(f'#marketJobDetail a[href="{DIDI_URL}"]').count() >= 1
        page.locator("#closeDrawer").click()

        # v1.2 intentionally hides detailed source diagnostics behind the admin
        # gate. The old test expected the raw source list and therefore failed
        # after the privacy UX was correctly implemented.
        page.locator("#openSourcePanel").click()
        page.wait_for_selector(".admin-source-gate")
        gate = page.locator(".admin-source-gate").inner_text()
        assert "管理员信息已雾化" in gate
        assert page.locator(".admin-source-blur").count() == 1
        blurred = page.locator(".admin-source-blur").inner_text()
        assert "拼多多校园招聘官网" in blurred and "滴滴招聘官网" in blurred

        context.close()
        browser.close()
    print("Path to Offer priority direct-feed browser smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
