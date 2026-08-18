#!/usr/bin/env python3
"""Browser acceptance for privacy/account/admin/avatar behavior."""
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE="http://127.0.0.1:8000"
ADMIN_PASSWORD="PTO-Sources-7Kq9-R2mV-2027"

STATE={
    "schemaVersion":2,
    "jobs":[{
        "id":"pipeline-pdd","company":"拼多多","department":"技术","role":"AI Infra研发工程师","location":"上海",
        "salary":"","direction":"AI Infra / 大模型推理系统","priority":"B","status":"applied","statusDate":"2026-08-18",
        "url":"https://careers.pddglobalhr.com/campus/grad/detail?positionId=5e4eb6f3-294f-491b-9d39-42895eed98c3",
        "jd":"vLLM CUDA 分布式训练与推理基础设施","resumeVersion":"","prepUrl":"","notes":"",
        "timeline":[{"status":"applied","date":"2026-08-18"}],
    }],
    "reviews":[],"resumes":[],"activeResumeId":None,"assets":[],"decisions":{},
    "preferences":{"targetLocations":[],"targetDirections":[]},
}
JOBS={"schema_version":4,"generated_at":"2026-08-18T12:00:00Z","jobs":[]}
STATUS={"generated_at":"2026-08-18T12:00:00Z","catalog_count":0,"sources":[{"name":"qa","label":"QA Source","url":"fixture://qa","ok":True,"count":13,"error":""}]}
PSTATUS={"generated_at":"2026-08-18T12:01:00Z","catalog_count":0,"nominal_interval_minutes":10,"sources":[]}


def browser_path():
    for candidate in ("google-chrome","google-chrome-stable","chromium","chromium-browser"):
        path=shutil.which(candidate)
        if path:return path
    raise RuntimeError("Chrome/Chromium not available")


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=["--no-sandbox","--disable-dev-shm-usage"])
        context=browser.new_context(viewport={"width":1440,"height":1000},accept_downloads=True)
        page=context.new_page()
        page.add_init_script(f"localStorage.setItem('pathToOffer.v0.2', {json.dumps(json.dumps(STATE,ensure_ascii=False))});")

        def route(route):
            url=route.request.url
            if "/data/jobs_priority.json" in url: route.fulfill(status=200,content_type="application/json",body=json.dumps(JOBS))
            elif "/data/jobs_cn.json" in url or "/data/jobs.json" in url: route.fulfill(status=200,content_type="application/json",body=json.dumps(JOBS))
            elif "/data/priority_source_status.json" in url: route.fulfill(status=200,content_type="application/json",body=json.dumps(PSTATUS))
            elif "/data/source_status.json" in url: route.fulfill(status=200,content_type="application/json",body=json.dumps(STATUS))
            elif url.startswith("https://cdn.jsdelivr.net/"): route.abort()
            else: route.continue_()

        page.route("**/*",route)
        page.goto(BASE,wait_until="domcontentloaded")
        page.wait_for_selector("#ptoAccountOverlay",timeout=15_000)

        # Pipeline company icon must be the company initial, not priority B.
        page.locator('button.nav-item[data-view="pipeline"]').click()
        card=page.locator('.job-card').first
        card.wait_for()
        initial=card.locator('[title="拼多多"]')
        initial.wait_for()
        assert initial.inner_text().strip()=="拼"
        assert initial.get_attribute("aria-label")=="拼多多 首字标识"

        # Account creation migrates current local state into an encrypted vault.
        page.locator("#githubLoginBtn").click()
        page.wait_for_selector("#ptoAccountOverlay:not(.hidden)")
        assert "跨设备同步：尚未配置" in page.locator(".pto-sync-state").inner_text()
        page.locator("#ptoAccountName").fill("qa-candidate")
        page.locator("#ptoAccountPassword").fill("Strong-QA-Password-2027")
        page.locator("#ptoAccountUnlock").click()
        page.wait_for_function("() => document.querySelector('#githubLoginText').textContent.includes('已解锁')",timeout=15_000)
        assert page.evaluate("localStorage.getItem('pathToOffer.v0.2')") is None
        vault_keys=page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('pto.vault.v1.'))")
        assert len(vault_keys)==1
        envelope=json.loads(page.evaluate("localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith('pto.vault.v1.')))") or "{}")
        assert envelope.get("state",{}).get("cipher") and "AI Infra研发工程师" not in json.dumps(envelope,ensure_ascii=False)

        # Lock and unlock the same account/password; migrated pipeline data returns.
        page.locator("#githubLoginBtn").click()
        page.locator("#ptoAccountLock").click()
        page.wait_for_function("() => document.querySelector('#githubLoginText').textContent.includes('解锁')")
        page.locator("#githubLoginBtn").click()
        page.locator("#ptoAccountPassword").fill("Strong-QA-Password-2027")
        page.locator("#ptoAccountUnlock").click()
        page.wait_for_function("() => document.querySelector('#githubLoginText').textContent.includes('已解锁')",timeout=15_000)
        page.locator('button.nav-item[data-view="pipeline"]').click()
        assert "AI Infra研发工程师" in page.locator('.job-card').first.inner_text()

        # Source health is fogged and password-gated.
        page.locator('button.nav-item[data-view="discover"]').click()
        page.locator("#openSourcePanel").click()
        page.wait_for_selector("#ptoAdminGate:not(.hidden)")
        assert page.evaluate("document.documentElement.classList.contains('pto-admin-fog')")
        page.locator("#ptoAdminPassword").fill("wrong")
        page.locator("#ptoAdminUnlock").click()
        assert "密码不正确" in page.locator(".pto-admin-error").inner_text()
        page.locator("#ptoAdminPassword").fill(ADMIN_PASSWORD)
        page.locator("#ptoAdminUnlock").click()
        page.wait_for_selector(".source-modal")
        assert "QA Source" in page.locator(".source-modal").inner_text()
        assert not page.evaluate("document.documentElement.classList.contains('pto-admin-fog')")
        page.locator("#closeModal").click()

        # Resume diagnostics are explicit, redacted and downloaded—not uploaded.
        page.locator("#pasteResumeBtn").click()
        resume="张三 13800138000 zhangsan@example.com 2027届硕士。专业技能：vLLM CUDA NCCL。实习经历：大模型推理系统、KV Cache、PagedAttention。"
        page.locator("#resumePasteText").fill(resume)
        page.locator("#resumePasteName").fill("QA Resume")
        page.locator("#parsePastedResume").click()
        page.locator("#inspectProfileBtn").click()
        page.wait_for_selector("#exportResumeDiagnostic")
        with page.expect_download(timeout=8_000) as download_info:
            page.locator("#exportResumeDiagnostic").click()
        download=download_info.value
        path=download.path()
        payload=json.loads(open(path,"r",encoding="utf-8").read())
        text=json.dumps(payload,ensure_ascii=False)
        assert "13800138000" not in text and "zhangsan@example.com" not in text and "张三" not in text
        assert "[PHONE]" in text and "[EMAIL]" in text
        assert payload["schema"]=="path-to-offer.resume-diagnostic.v1"

        context.close();browser.close()
    print("Path to Offer privacy/account/admin/avatar smoke: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
