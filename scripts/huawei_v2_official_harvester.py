#!/usr/bin/env python3
"""Huawei 2027 campus jobs from the current public Huawei Careers page.

Huawei's current `/cn` careers site exposes concrete graduate positions through
its own public `getJobPage` XHR. On hosted runners the gateway returns an empty
payload to bare/replayed HTTP calls, while the normal anonymous page XHR returns
the live catalogue. Production therefore follows the site exactly: open the
public graduate page, observe its native XHR, and use the visible pagination UI
to collect subsequent pages.

No login, resume upload, CAPTCHA handling, private-cookie replay, proxy rotation
or access-control bypass is used.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import time
from typing import Any

API_BASE = "https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/getJobPage"
API_PATH = "/recruitmentPosition/pub/getJobPage"
HW_APP_ID = "app_000000035886"
LIST_URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
NAV_TIMEOUT_MS = 45_000


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(clean(value).lower() for value in parts if value)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable for Huawei public collector")


def normalize_huawei_job(row: dict[str, Any]) -> dict[str, Any] | None:
    role = clean(row.get("jobName") or row.get("jobNameNew"))
    job_id = clean(row.get("jobId") or row.get("advertisementsIntegrationId") or row.get("advertisementId"))
    if not role or not job_id:
        return None

    location = clean(row.get("workPlace") or row.get("jobArea") or row.get("cityName") or row.get("jobAddress"))
    department = clean(row.get("deptName") or row.get("firstDeptName") or row.get("deptNameCn"))
    category = clean(row.get("categoryName") or row.get("jobFamilyName") or row.get("jobFamClsCodeName"))
    updated = clean(row.get("lastUpdateDate") or row.get("releaseDate"))[:10]
    scenario = clean(row.get("scenarioName")) or "应届生"

    jd_parts: list[str] = []
    if department:
        jd_parts.append(f"招聘部门：{department}")
    if category:
        jd_parts.append(f"岗位类别：{category}")
    desc = clean(row.get("jobDesc") or row.get("mainBusiness"))
    requirement = clean(row.get("jobRequire"))
    if desc:
        jd_parts.append(desc)
    if requirement:
        jd_parts.append(requirement)
    jd = "\n".join(jd_parts) or role

    # The current SPA does not expose a stable anonymous per-card <a> URL.
    # Keep Huawei's official current list as navigation target and preserve the
    # exact Huawei jobId as position_id so every job stays independently keyed.
    job = {
        "source": "direct-official:huawei-v2",
        "source_label": "华为校园招聘官网 · 新版公开职位",
        "source_url": LIST_URL,
        "updated_at": updated,
        "company": "华为",
        "department": department,
        "role": role,
        "location": location,
        "salary": "",
        "batch": "2027校园招聘",
        "company_type": "民营/ICT/科技",
        "industry": "ICT/AI/芯片/云计算",
        "graduation": "2027届",
        "education": clean(row.get("degree")),
        "notice_url": LIST_URL,
        "apply_url": LIST_URL,
        "jd": jd[:5000],
        "tags": ["官方招聘", "华为", "2027校园招聘", scenario] + ([category] if category else []),
        "observed_via": "employer-public-native-xhr",
        "position_id": job_id,
    }
    job["id"] = stable_id("华为", role, location, job_id)
    return job


def _click_page_number(page, target: int) -> dict[str, Any]:
    """Click Huawei's native numbered pager, with a generic fallback."""
    return page.evaluate(
        """n => {
          let candidates=Array.from(document.querySelectorAll('li.pager-item-pager-pc,li.pager-item-active-pc'))
            .filter(el => (el.innerText||el.textContent||'').trim()===String(n));
          if(!candidates.length){
            candidates=Array.from(document.querySelectorAll('body *')).filter(el=>{
              const text=(el.innerText||el.textContent||'').trim();
              if(text!==String(n))return false;
              const r=el.getBoundingClientRect();
              if(r.width<2||r.height<2)return false;
              const cs=getComputedStyle(el);
              const pcs=el.parentElement?getComputedStyle(el.parentElement):null;
              return el.tagName==='LI'||el.tagName==='A'||el.tagName==='BUTTON'||
                     cs.cursor==='pointer'||(pcs&&pcs.cursor==='pointer');
            });
          }
          candidates.sort((a,b)=>{
            const ar=a.getBoundingClientRect(), br=b.getBoundingClientRect();
            return ar.width*ar.height-br.width*br.height;
          });
          const el=candidates[0];
          if(!el)return {ok:false,count:0};
          el.scrollIntoView({block:'center'});
          el.click();
          return {ok:true,count:candidates.length,tag:el.tagName,cls:String(el.className||'')};
        }""",
        target,
    )


def collect_huawei(max_pages: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    max_pages = max(1, min(30, int(max_pages)))
    jobs: dict[str, dict[str, Any]] = {}
    captured_pages: set[int] = set()
    total_rows = 0
    total_pages = 0
    response_count = 0
    errors: list[str] = []
    click_log: list[dict[str, Any]] = []
    final_url = LIST_URL

    def consume_response(response) -> None:
        nonlocal total_rows, total_pages, response_count
        if API_PATH not in response.url:
            return
        try:
            payload = response.json()
            data = payload.get("data") or {}
            if not isinstance(data, dict):
                return
            page_vo = data.get("pageVO") or {}
            rows = data.get("result") or []
            if not isinstance(page_vo, dict) or not isinstance(rows, list) or not rows:
                return
            current = int(page_vo.get("curPage") or 0)
            total_rows = int(page_vo.get("totalRows") or total_rows or 0)
            total_pages = int(page_vo.get("totalPages") or total_pages or 0)
            response_count += 1
            if current:
                captured_pages.add(current)
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                job = normalize_huawei_job(raw)
                if job:
                    jobs[job["position_id"]] = job
        except Exception as exc:
            if len(errors) < 12:
                errors.append(f"response {type(exc).__name__}: {clean(exc)[:180]}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=browser_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="zh-CN")
        page = context.new_page()
        page.on("response", consume_response)
        try:
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            final_url = page.url

            # Let Huawei's own component issue page 1. The response callback is
            # the source of truth; we never replay or synthesize its XHR.
            deadline = time.time() + 14
            while 1 not in captured_pages and time.time() < deadline:
                page.wait_for_timeout(250)
            if 1 not in captured_pages:
                raise RuntimeError("Huawei page loaded but native page-1 getJobPage XHR was not observed")

            wanted_pages = min(max_pages, total_pages or 1)
            for target in range(2, wanted_pages + 1):
                if target in captured_pages:
                    continue
                try:
                    result = _click_page_number(page, target)
                except Exception as exc:
                    result = {"ok": False, "error": f"{type(exc).__name__}: {clean(exc)[:120]}"}
                click_log.append({"page": target, **(result if isinstance(result, dict) else {"result": clean(result)})})
                if not isinstance(result, dict) or not result.get("ok"):
                    raise RuntimeError(f"Huawei native pagination button {target} not found: {result}")

                deadline = time.time() + 7
                while target not in captured_pages and time.time() < deadline:
                    page.wait_for_timeout(180)
                if target not in captured_pages:
                    raise RuntimeError(f"Huawei page {target} click produced no native getJobPage response")
        finally:
            context.close()
            browser.close()

    diagnostics = {
        "endpoint": API_BASE,
        "transport": "browser-native-ui-xhr",
        "final_url": final_url,
        "pages_ok": len(captured_pages),
        "captured_pages": sorted(captured_pages),
        "response_count": response_count,
        "total_reported": total_rows,
        "total_pages": total_pages,
        "unique_jobs": len(jobs),
        "ai_infra_present": any(clean(j.get("role")) == "AI Infra工程师" for j in jobs.values()),
        "beijing_jobs": sum(1 for j in jobs.values() if "北京" in clean(j.get("location"))),
        "clicks": click_log,
        "errors": errors,
    }
    return list(jobs.values()), diagnostics


if __name__ == "__main__":
    jobs, diagnostics = collect_huawei()
    print(diagnostics)
    for job in jobs[:10]:
        print(job["position_id"], job["role"], job["location"], job["department"])
