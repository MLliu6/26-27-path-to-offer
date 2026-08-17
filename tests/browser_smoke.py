#!/usr/bin/env python3
"""Headless browser smoke test for Path to Offer's critical user journey.

The job/source network requests are intercepted with deterministic fixtures so the test
checks front-end behavior rather than external crawler availability. No mock records are
shipped in the product; these fixtures live only inside CI.
"""
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

JOBS = {
    "schema_version": 2,
    "generated_at": "2026-08-16T07:00:00Z",
    "jobs": [
        {
            "id": "jd-old",
            "source": "browser-fixture",
            "source_label": "Browser QA fixture",
            "company": "京东",
            "role": "技术方向 / AI Infra / 软件研发",
            "location": "北京 全国",
            "industry": "互联网",
            "batch": "实习",
            "graduation": "2027届",
            "updated_at": "2026-03-10",
            "jd": "AI Infra 大模型推理 CUDA 软件研发",
            "apply_url": "https://zhaopin.jd.com/",
        },
        {
            "id": "tx-fresh",
            "source": "browser-fixture",
            "source_label": "Browser QA fixture",
            "company": "腾讯",
            "role": "AI Infra / 多模态 / 软件开发",
            "location": "深圳",
            "industry": "互联网/人工智能",
            "batch": "校招",
            "graduation": "2027届",
            "updated_at": "2026-08-15",
            "jd": "vLLM CUDA KV Cache 多模态大模型推理",
        },
    ],
}
STATUS = {
    "generated_at": "2026-08-16T07:00:00Z",
    "catalog_count": 2,
    "sources": [{"name": "qa", "label": "Browser QA", "url": "fixture://jobs", "ok": True, "count": 2, "error": ""}],
}


def browser_path() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium not available on CI runner")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()

        def route_handler(route):
            url = route.request.url
            if "/data/jobs_cn.json" in url or "/data/jobs.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(JOBS, ensure_ascii=False))
            elif "/data/source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(STATUS, ensure_ascii=False))
            elif url.startswith("https://cdn.jsdelivr.net/"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_selector("#searchPolicy", timeout=12_000)

        # 1. Direct search works before a resume and ignores recommendation controls.
        page.locator("#scoreThreshold").evaluate("el => { el.value='95'; el.dispatchEvent(new Event('input',{bubbles:true})); }")
        page.locator("#freshOnly").check()
        page.locator("#jobSearch").fill("京东")
        jd_card = page.locator('.market-card[data-market-id="jd-old"]')
        jd_card.wait_for()
        assert "京东" in jd_card.inner_text()

        # Regression for the production overlap screenshot: the 4-step flow must
        # live inside the right-hand job market, never as a third grid child that
        # pushes cards into the 205px MATCH CONTROL rail.
        page.wait_for_selector("#ptoFlow")
        assert page.locator("#ptoFlow").evaluate("el => el.parentElement.classList.contains('job-market')")
        rail_box = page.locator(".match-rail").bounding_box()
        market_box = page.locator(".job-market").bounding_box()
        card_box = jd_card.bounding_box()
        assert rail_box and market_box and card_box
        assert market_box["x"] >= rail_box["x"] + rail_box["width"] + 8, (rail_box, market_box)
        assert market_box["width"] > 700, market_box
        assert card_box["width"] > 300, card_box

        # Explicit affordances must actually open a rich detail view and expose
        # the canonical external application action instead of relying on a vague
        # whole-card click target.
        page.locator('.market-card[data-market-id="jd-old"] [data-open-detail="jd-old"]').click()
        page.wait_for_selector("#marketJobDetail:not(.hidden)")
        detail_text = page.locator("#marketJobDetail").inner_text()
        assert "JOB DESCRIPTION" in detail_text
        assert "官网投递" in detail_text
        assert page.locator('#marketJobDetail a[href="https://zhaopin.jd.com/"]').count() >= 1
        page.locator("#closeDrawer").click()

        # 2. Create a v4 profile through the real paste-resume UI.
        page.locator("#jobSearch").fill("")
        page.locator("#pasteResumeBtn").click()
        resume = "2027届硕士。LLM serving，大模型推理系统，vLLM、PagedAttention、KV Cache、prefill、decode、continuous batching、NCCL、CUDA，做过显存管理与调度优化。"
        page.locator("#resumePasteText").fill(resume)
        page.locator("#resumePasteName").fill("AI Infra QA")
        page.locator("#parsePastedResume").click()
        page.wait_for_selector("#profileIntelligence:not(.hidden)")
        profile_text = page.locator("#profileIntelligence").inner_text()
        assert "AI Infra / 大模型推理系统" in profile_text
        assert "vllm" in profile_text.lower()

        # 3. Enhanced profile inspector is actually bound after the dynamic patch loads.
        page.locator("#inspectProfileBtn").click()
        page.wait_for_selector(".profile-inspector")
        assert "画像引擎 v4" in page.locator(".profile-inspector").inner_text()
        assert "DIRECTION EVIDENCE" in page.locator(".profile-inspector").inner_text()
        page.locator("#closeModal").click()

        # 4. Repeat the user-reported 京东 failure after profile creation.
        page.locator("#scoreThreshold").evaluate("el => { el.value='95'; el.dispatchEvent(new Event('input',{bubbles:true})); }")
        page.locator("#freshOnly").check()
        page.locator("#jobSearch").fill("京东")
        page.locator('.market-card[data-market-id="jd-old"]').wait_for()

        # v0.9 scoring must expose its eight-dimensional explanation in the
        # actual detail drawer rather than returning an opaque 99-style badge.
        page.locator('.market-card[data-market-id="jd-old"] [data-open-detail="jd-old"]').click()
        page.wait_for_selector(".pto-score-audit")
        audit = page.locator(".pto-score-audit").inner_text()
        assert "匹配评分明细" in audit and "方向 / 30" in audit and "来源可信度 / 7" in audit
        page.locator("#closeDrawer").click()

        # 5. Shortlist -> pipeline; use the visible card action, not the hidden table duplicate.
        page.locator('.market-card[data-market-id="jd-old"] [data-save-job="jd-old"]').click()
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector(".job-card")
        card = page.locator(".job-card").first
        assert "京东" in card.inner_text()

        # 6. Open record, move to applied, save, and verify the dated pipeline stage.
        card.click()
        page.wait_for_selector("#jobForm:not(.hidden)")
        page.locator('#jobForm select[name="status"]').select_option("applied")
        page.locator('#jobForm button[type="submit"]').click()
        page.wait_for_selector('.kanban-col[data-stage="applied"] .job-card')
        assert "京东" in page.locator('.kanban-col[data-stage="applied"] .job-card').inner_text()

        # 7. Resume library retained the parsed version.
        page.locator('button.nav-item[data-view="library"]').click()
        assert "AI Infra QA" in page.locator("#resumeList").inner_text()

        # 8. Interview memory TXT import.
        page.locator('button.nav-item[data-view="reviews"]').click()
        page.locator("#reviewImport").set_input_files({
            "name": "jd-interview.txt",
            "mimeType": "text/plain",
            "buffer": b"Q: KV Cache?\nA: memory reuse and serving tradeoffs.\nImprove: explain scheduler boundary.",
        })
        page.wait_for_selector(".review-card")
        assert "jd-interview" in page.locator(".review-card").first.inner_text()

        # 9. Insights reflect only records created by this walkthrough.
        page.locator('button.nav-item[data-view="insights"]').click()
        metric = page.locator("#metricGrid").inner_text()
        assert "已选择" in metric and "1" in metric

        # 10. Export and theme controls are live.
        with page.expect_download(timeout=5_000) as dl:
            page.locator("#exportBtn").click()
        assert dl.value.suggested_filename.startswith("path-to-offer-")
        page.locator("#themeBtn").click()
        page.wait_for_selector("#themePopover.show")
        page.locator('[data-theme="1"]').click()
        accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        assert accent.lower() == "#9db4c5"

        page.locator('button.nav-item[data-view="discover"]').click()

        # A monitored priority employer with zero current rows must not look like
        # an unknown company. The product should expose the official source and
        # explicitly distinguish “under monitoring” from a fabricated job result.
        page.locator("#jobSearch").fill("中石油")
        page.wait_for_selector("#ptoSourceFallback")
        fallback = page.locator("#ptoSourceFallback").inner_text()
        assert "中国石油" in fallback and "官方招聘源已纳入雷达" in fallback
        assert page.locator('#ptoSourceFallback a[href="https://zhaopin.cnpc.com.cn/"]').count() == 1

        # Source-health panel remains accessible.
        page.locator("#openSourcePanel").click()
        page.wait_for_selector(".source-modal")
        assert "Browser QA" in page.locator(".source-modal").inner_text()
        page.locator("#closeModal").click()

        # Mobile sanity: critical action does not depend on hover and the flow
        # remains structurally inside the market column.
        mobile = context.new_page()
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.route("**/*", route_handler)
        mobile.goto(BASE, wait_until="domcontentloaded")
        mobile.wait_for_selector("#searchPolicy", timeout=12_000)
        mobile.locator("#jobSearch").fill("京东")
        mobile.locator('.market-card[data-market-id="jd-old"]').wait_for()
        assert mobile.locator('.market-card[data-market-id="jd-old"] [data-save-job="jd-old"]').is_visible()
        assert mobile.locator("#ptoFlow").evaluate("el => el.parentElement.classList.contains('job-market')")
        mobile.close()

        context.close(); browser.close()
    print("Path to Offer browser smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
