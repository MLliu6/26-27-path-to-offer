#!/usr/bin/env python3
"""Browser acceptance for Path to Offer's real candidate journey.

Network job feeds are deterministic CI fixtures only. The product ships no mock
jobs. This test specifically protects the user-reported failure mode: upload a
resume, obtain China/Beijing-biased recommendations, open a job detail, reach the
company's official application URL, save it, and continue the pipeline.
"""
from __future__ import annotations

import json
import shutil
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

JOBS = {
    "schema_version": 2,
    "generated_at": "2026-08-17T00:30:00Z",
    "jobs": [
        {
            "id": "jd-ai",
            "source": "china-company:direct:jd",
            "source_label": "公司官网 · 京东",
            "company": "京东",
            "department": "基础架构",
            "role": "大模型推理系统工程师",
            "location": "北京",
            "industry": "互联网/人工智能",
            "batch": "2027校园招聘",
            "graduation": "2027届",
            "education": "硕士",
            "updated_at": "2026-08-16",
            "jd": "负责 vLLM SGLang KV Cache PagedAttention CUDA NCCL 大模型推理系统与显存优化",
            "apply_url": "https://zhaopin.jd.com/web/job/job_detail/123",
        },
        {
            "id": "tx-ai",
            "source": "china-company:direct:tencent",
            "source_label": "公司官网 · 腾讯",
            "company": "腾讯",
            "role": "AI Infra 软件研发工程师",
            "location": "深圳",
            "batch": "校园招聘",
            "graduation": "2027届",
            "updated_at": "2026-08-15",
            "jd": "LLM serving CUDA KV Cache 多机多卡推理",
            "apply_url": "https://join.qq.com/post.html?pid=1",
        },
        {
            "id": "wrong-product",
            "source": "china-company:direct:fixture",
            "source_label": "公司官网 · 某科技",
            "company": "某科技",
            "role": "AI 产品经理",
            "location": "北京",
            "batch": "校园招聘",
            "graduation": "2027届",
            "updated_at": "2026-08-16",
            "jd": "与研发沟通 vLLM CUDA KV Cache，负责产品规划、市场和商业化",
            "apply_url": "https://example.com/campus/product",
        },
        {
            "id": "foreign-ai",
            "source": "ats:greenhouse:fixture",
            "source_label": "Official ATS",
            "company": "Foreign AI Corp",
            "role": "LLM Inference Engineer",
            "location": "Singapore",
            "batch": "New Grad",
            "updated_at": "2026-08-16",
            "jd": "vLLM CUDA KV Cache PagedAttention",
            "apply_url": "https://example.com/singapore",
        },
    ],
}
STATUS = {
    "generated_at": "2026-08-17T00:30:00Z",
    "catalog_count": 4,
    "catalog_mode": "china-campus-first",
    "china_focus": {"beijing_count": 2, "tier1_count": 3, "company_official_count": 3, "direct_link_ratio": 1.0},
    "sources": [{"name": "china-company-official", "label": "中国企业官网招聘 · 校招/初阶优先", "url": "fixture://official", "ok": True, "count": 3, "error": ""}],
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
            if "/data/jobs.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(JOBS, ensure_ascii=False))
            elif "/data/source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(STATUS, ensure_ascii=False))
            elif url.startswith("https://cdn.jsdelivr.net/"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_selector("#geoQuickFilters", timeout=12_000)

        # 1. Direct retrieval works before resume and is not blocked by match controls.
        page.locator("#scoreThreshold").evaluate("el => { el.value='95'; el.dispatchEvent(new Event('input',{bubbles:true})); }")
        page.locator("#freshOnly").check()
        page.locator("#jobSearch").fill("京东")
        jd_card = page.locator('.market-card[data-market-id="jd-ai"]')
        jd_card.wait_for()
        assert "京东" in jd_card.inner_text()
        assert jd_card.locator('[data-open-job="jd-ai"]').is_visible()
        assert jd_card.locator('a.official-apply').get_attribute('href').startswith('https://zhaopin.jd.com/')

        # 2. The details action is explicit and the drawer exposes an official apply CTA.
        jd_card.locator('[data-open-job="jd-ai"]').click()
        page.wait_for_selector('#marketJobDetail:not(.hidden)')
        detail_apply = page.locator('#detailApply')
        assert detail_apply.is_visible()
        assert detail_apply.get_attribute('href') == 'https://zhaopin.jd.com/web/job/job_detail/123'
        assert '完整 JD' in page.locator('#marketJobDetail').inner_text()
        page.locator('#closeDrawer').click()

        # 3. Upload an actual TXT resume through the file-input path (not a test-only API).
        resume = """刘同学\n2027届硕士\n专业技能\nC++ Python CUDA Triton vLLM SGLang NCCL\n实习经历\n负责 LLM Serving、KV Cache、PagedAttention、prefill/decode、显存管理和通信优化。\n项目经历\nCUDA GEMM Tensor Core 算子优化。\n"""
        page.locator('#resumeImport').set_input_files({"name":"AI-Infra-2027.txt","mimeType":"text/plain","buffer":resume.encode('utf-8')})
        page.wait_for_selector('#profileIntelligence:not(.hidden)', timeout=10_000)
        profile_text = page.locator('#profileIntelligence').inner_text()
        assert 'AI Infra / 大模型推理系统' in profile_text
        assert 'vllm' in profile_text.lower()

        # 4. Upload -> recommendation is continuous, domestic/tier-1 by default,
        #    foreign noise is absent, and title-level product mismatch is suppressed.
        page.locator('#scoreThreshold').evaluate("el => { el.value='28'; el.dispatchEvent(new Event('input',{bubbles:true})); }")
        page.locator('#freshOnly').uncheck()
        page.locator('#jobSearch').fill('')
        page.locator('[data-geo-mode="tier1"]').click()
        page.wait_for_selector('.market-card[data-market-id="jd-ai"]')
        visible = page.locator('.market-card').all_inner_texts()
        joined = '\n'.join(visible)
        assert 'Singapore' not in joined and 'Foreign AI Corp' not in joined
        assert 'AI 产品经理' not in joined
        assert '京东' in joined and '腾讯' in joined

        # 5. Beijing quick filter produces a coherent Beijing-only recommendation set.
        page.locator('[data-geo-mode="beijing"]').click()
        page.wait_for_selector('.market-card[data-market-id="jd-ai"]')
        assert all('北京' in text for text in page.locator('.market-card').all_inner_texts())

        # 6. Inspectable section-aware resume profile remains available.
        page.locator('#inspectProfileBtn').click()
        page.wait_for_selector('.profile-inspector')
        inspector = page.locator('.profile-inspector').inner_text()
        assert 'DIRECTION EVIDENCE' in inspector and 'SECTION-AWARE PARSING' in inspector
        page.locator('#closeModal').click()

        # 7. Job detail -> shortlist -> pipeline preserves the official apply link.
        page.locator('.market-card[data-market-id="jd-ai"] [data-open-job="jd-ai"]').click()
        page.locator('#detailPromote').click()
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector('.job-card')
        card = page.locator('.job-card').first
        assert '京东' in card.inner_text()
        card.click()
        page.wait_for_selector('#jobForm:not(.hidden)')
        quick = page.locator('.pipeline-quick-actions')
        assert quick.is_visible()
        assert quick.locator('a').get_attribute('href') == 'https://zhaopin.jd.com/web/job/job_detail/123'
        assert quick.locator('[data-mark-applied]').is_visible()
        quick.locator('[data-mark-applied]').click()
        page.wait_for_selector('.kanban-col[data-stage="applied"] .job-card')
        assert '京东' in page.locator('.kanban-col[data-stage="applied"] .job-card').inner_text()

        # 8. Resume library retained the parsed version.
        page.locator('button.nav-item[data-view="library"]').click()
        assert 'AI-Infra-2027' in page.locator('#resumeList').inner_text()

        # 9. Interview memory TXT import still works.
        page.locator('button.nav-item[data-view="reviews"]').click()
        page.locator('#reviewImport').set_input_files({
            "name": "jd-interview.txt",
            "mimeType": "text/plain",
            "buffer": b"Q: KV Cache?\nA: memory reuse and serving tradeoffs.\nImprove: explain scheduler boundary.",
        })
        page.wait_for_selector('.review-card')
        assert 'jd-interview' in page.locator('.review-card').first.inner_text()

        # 10. Export/theme/source-health controls remain functional after v0.7.
        page.locator('button.nav-item[data-view="insights"]').click()
        assert '已选择' in page.locator('#metricGrid').inner_text()
        with page.expect_download(timeout=5_000) as dl:
            page.locator('#exportBtn').click()
        assert dl.value.suggested_filename.startswith('path-to-offer-')
        page.locator('#themeBtn').click(); page.wait_for_selector('#themePopover.show')
        page.locator('[data-theme="1"]').click()
        accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        assert accent.lower() == '#9db4c5'
        page.locator('button.nav-item[data-view="discover"]').click()
        page.locator('#openSourcePanel').click(); page.wait_for_selector('.source-modal')
        source_text=page.locator('.source-modal').inner_text()
        assert '企业自己的公开招聘系统' in source_text and '北京' in source_text
        page.locator('#closeModal').click()

        # Mobile: visible detail/apply/save actions do not depend on hover.
        mobile = context.new_page(); mobile.set_viewport_size({"width":390,"height":844}); mobile.route('**/*',route_handler)
        mobile.goto(BASE,wait_until='domcontentloaded'); mobile.wait_for_selector('#geoQuickFilters',timeout=12_000)
        mobile.locator('#jobSearch').fill('京东'); mobile.locator('.market-card[data-market-id="jd-ai"]').wait_for()
        assert mobile.locator('.market-card[data-market-id="jd-ai"] [data-open-job="jd-ai"]').is_visible()
        assert mobile.locator('.market-card[data-market-id="jd-ai"] a.official-apply').is_visible()
        mobile.close()

        context.close(); browser.close()
    print('Path to Offer v0.7 China-first browser journey: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
