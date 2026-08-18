#!/usr/bin/env python3
"""Browser regression for v1.2 privacy/account/admin interaction changes."""
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
EMPTY_FEED = {"schema_version": 4, "generated_at": "2026-08-19T00:00:00Z", "jobs": []}
STATUS = {
    "generated_at": "2026-08-19T00:00:00Z",
    "catalog_count": 0,
    "sources": [
        {"name": "didi-direct-official", "label": "滴滴招聘官网 · 全量自主直连", "url": "https://talent.didiglobal.com/", "ok": True, "count": 321, "error": ""},
        {"name": "official-source-graph", "label": "企业招聘官网图谱 · 轮转自主抓取", "url": "", "ok": True, "count": 17, "error": ""},
    ],
}
PRIORITY_STATUS = {
    "generated_at": "2026-08-19T00:00:00Z",
    "catalog_count": 0,
    "nominal_interval_minutes": 10,
    "sources": [],
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
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()

        def route_handler(route):
            url = route.request.url
            if "/data/jobs_priority.json" in url or "/data/jobs_cn.json" in url or "/data/jobs.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(EMPTY_FEED, ensure_ascii=False))
            elif "/data/priority_source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(PRIORITY_STATUS, ensure_ascii=False))
            elif "/data/source_status.json" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(STATUS, ensure_ascii=False))
            elif url.startswith("https://cdn.jsdelivr.net/"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_function("() => !!window.PTO_ACCOUNT_UI && window.PTO_ENHANCEMENTS_READY === true", timeout=20_000)

        # Add a real pipeline record with the default B priority. The visual
        # monogram must come from the company, not from the priority value.
        page.locator("#addJobBtn").click()
        page.locator('#jobForm input[name="company"]').fill("辉羲智能")
        page.locator('#jobForm input[name="role"]').fill("AI 芯片软件栈工程师")
        page.locator('#jobForm input[name="location"]').fill("北京")
        page.locator('#jobForm button[type="submit"]').click()
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector(".job-card")
        assert page.locator(".company-avatar").first.inner_text() == "辉"
        assert "优先 B" in page.locator(".job-priority-badge").first.inner_text()

        # The detailed source panel must start in a blurred admin-gated state.
        page.locator('button.nav-item[data-view="discover"]').click()
        page.locator("#openSourcePanel").click()
        page.wait_for_selector("#adminSourcePassword")
        assert page.locator(".admin-source-blur").count() == 1
        assert "管理员信息已雾化" in page.locator("#quickModal").inner_text()
        page.locator("#closeModal").click()

        # Create a local encrypted account from current state, leave it, and
        # unlock it again with the same credentials. Plain legacy storage must
        # not hold the active account state.
        page.locator("#githubLoginBtn").click()
        page.locator("#localAccountName").fill("qa-candidate")
        page.locator("#localAccountPassword").fill("strong-password-2027")
        page.locator("#localCreate").click()
        page.wait_for_function("() => window.PTO_ACCOUNT_SESSION?.username === 'qa-candidate'", timeout=12_000)
        assert page.evaluate("localStorage.getItem('pathToOffer.v0.2')") is None
        page.locator("#githubLoginBtn").click()
        page.locator("#accountLogout").click()
        page.wait_for_function("() => !window.PTO_ACCOUNT_SESSION")
        page.locator('button.nav-item[data-view="pipeline"]').click()
        assert page.locator(".job-card").count() == 0

        page.locator("#githubLoginBtn").click()
        page.locator("#localAccountName").fill("qa-candidate")
        page.locator("#localAccountPassword").fill("strong-password-2027")
        page.locator("#localLogin").click()
        page.wait_for_function("() => window.PTO_ACCOUNT_SESSION?.username === 'qa-candidate'", timeout=12_000)
        page.locator('button.nav-item[data-view="pipeline"]').click()
        page.wait_for_selector(".job-card")
        assert "辉羲智能" in page.locator(".job-card").first.inner_text()

        # Resume parsing is audited locally. The browser can show and download
        # exactly what it extracted without committing plaintext to GitHub.
        page.locator('button.nav-item[data-view="discover"]').click()
        page.locator("#pasteResumeBtn").click()
        resume = "2027届硕士，实习负责 vLLM、CUDA、KV Cache、大模型推理系统和 AI 芯片 Runtime；项目包含 Triton 算子优化。"
        page.locator("#resumePasteText").fill(resume)
        page.locator("#resumePasteName").fill("AI Infra QA")
        page.locator("#parsePastedResume").click()
        page.wait_for_selector("#profileIntelligence:not(.hidden)")
        page.locator("#inspectProfileBtn").click()
        page.wait_for_selector("#privacyAuditBox")
        page.locator("#viewParsedText").click()
        page.wait_for_selector(".parsed-text-view")
        assert "vLLM" in page.locator(".parsed-text-view").inner_text()
        page.locator("#closeModal").click()
        page.locator("#inspectProfileBtn").click()
        page.wait_for_selector("#downloadResumeAudit")
        with page.expect_download(timeout=8_000) as download:
            page.locator("#downloadResumeAudit").click()
        assert download.value.suggested_filename.startswith("resume-parse-audit-")

        context.close()
        browser.close()
    print("Path to Offer v1.2 local-vault/admin/avatar browser smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
