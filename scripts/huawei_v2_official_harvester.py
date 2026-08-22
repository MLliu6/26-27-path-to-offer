#!/usr/bin/env python3
"""Huawei 2027 campus jobs from the current public Huawei Careers API.

Huawei migrated the legacy ``reccampportal/portal5`` site to ``/cn``. The new
public graduate list calls a recruitmentPosition API that returns concrete job
rows, but the gateway may return an empty payload to a bare HTTP client. This
collector therefore tries the lightweight public request first and, when Huawei
requires its normal browser context, opens the anonymous official careers page
with system Chrome and performs the same public fetch from that page origin.

No login, resume upload, CAPTCHA handling, private cookies, proxy rotation or
access-control bypass is used.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from typing import Any
from urllib.parse import urlencode

import requests

API_BASE = "https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/getJobPage"
HW_APP_ID = "app_000000035886"
LIST_URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
TIMEOUT = 25
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
    raise RuntimeError("Chrome/Chromium unavailable for Huawei public browser collector")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN",
        "Content-Type": "application/json",
        "Origin": "https://career.huawei.com",
        "Referer": "https://career.huawei.com/",
        "X-HW-ID": HW_APP_ID,
    })
    return session


def request_body(page: int, page_size: int) -> dict[str, Any]:
    return {
        "curPage": page,
        "pageSize": page_size,
        "jobType": "CR",
        "recruitmentType": ["FRESH_GRADUATE"],
    }


def _request_page(session: requests.Session, page: int, page_size: int) -> dict[str, Any]:
    url = f"{API_BASE}?{urlencode({'X-HW-ID': HW_APP_ID})}"
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = session.post(url, json=request_body(page, page_size), timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Huawei getJobPage returned non-object JSON")
            return payload
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(str(last) if last else "Huawei getJobPage failed")


def _job_url(row: dict[str, Any]) -> str:
    # The new Huawei SPA renders cards without stable anonymous <a> detail URLs.
    # Keep the current official list as navigation target; position_id is the
    # exact Huawei jobId and keeps every real position independently addressable
    # inside Path to Offer.
    return LIST_URL


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
    jd_parts = []
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
    url = _job_url(row)
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
        "notice_url": url,
        "apply_url": url,
        "jd": jd[:5000],
        "tags": ["官方招聘", "华为", "2027校园招聘", scenario] + ([category] if category else []),
        "observed_via": "employer-public-browser-api",
        "position_id": job_id,
    }
    job["id"] = stable_id("华为", role, location, job_id)
    return job


def _consume_payload(payload: Any, jobs: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
    if not isinstance(payload, dict):
        return 0, 0, 0
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return 0, 0, 0
    page_vo = data.get("pageVO") or {}
    total_rows = int(page_vo.get("totalRows") or 0) if isinstance(page_vo, dict) else 0
    total_pages = int(page_vo.get("totalPages") or 0) if isinstance(page_vo, dict) else 0
    rows = data.get("result") or []
    if not isinstance(rows, list):
        return total_rows, total_pages, 0
    added = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        job = normalize_huawei_job(row)
        if job:
            jobs[job["position_id"]] = job
            added += 1
    return total_rows, total_pages, len(rows)


def _collect_http(page_size: int, max_pages: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    session = _session()
    prime_status = 0
    prime_error = ""
    try:
        response = session.get(
            LIST_URL,
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Content-Type": "text/plain"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        prime_status = response.status_code
        response.raise_for_status()
    except Exception as exc:
        prime_error = f"{type(exc).__name__}: {clean(exc)[:180]}"

    jobs: dict[str, dict[str, Any]] = {}
    total_rows = total_pages = pages_ok = 0
    for page in range(1, max_pages + 1):
        payload = _request_page(session, page, page_size)
        reported, pages, row_count = _consume_payload(payload, jobs)
        total_rows = reported or total_rows
        total_pages = pages or total_pages
        if not row_count:
            break
        pages_ok += 1
        if total_pages and page >= total_pages:
            break
        if row_count < page_size:
            break
        time.sleep(0.08)
    return list(jobs.values()), {
        "transport": "http-public-api",
        "prime_status": prime_status,
        "prime_error": prime_error,
        "pages_ok": pages_ok,
        "total_reported": total_rows,
        "total_pages": total_pages,
    }


def _collect_browser(page_size: int, max_pages: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Import lazily so syntax/unit users of the module do not need Playwright.
    from playwright.sync_api import sync_playwright

    jobs: dict[str, dict[str, Any]] = {}
    total_rows = total_pages = pages_ok = 0
    final_url = LIST_URL
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=browser_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        page = context.new_page()
        try:
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            page.wait_for_timeout(2500)
            final_url = page.url
            for page_no in range(1, max_pages + 1):
                result = page.evaluate(
                    """async ({endpoint, appId, body}) => {
                      const url = `${endpoint}?X-HW-ID=${encodeURIComponent(appId)}`;
                      const response = await fetch(url, {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                          'Accept': 'application/json,text/plain,*/*',
                          'Accept-Language': 'zh-CN',
                          'Content-Type': 'application/json',
                          'X-HW-ID': appId
                        },
                        body: JSON.stringify(body)
                      });
                      const text = await response.text();
                      return {status: response.status, ok: response.ok, text};
                    }""",
                    {"endpoint": API_BASE, "appId": HW_APP_ID, "body": request_body(page_no, page_size)},
                )
                if not isinstance(result, dict) or not result.get("ok"):
                    raise RuntimeError(f"Huawei browser API HTTP {result}")
                payload = json.loads(result.get("text") or "{}")
                reported, pages, row_count = _consume_payload(payload, jobs)
                total_rows = reported or total_rows
                total_pages = pages or total_pages
                if not row_count:
                    break
                pages_ok += 1
                if total_pages and page_no >= total_pages:
                    break
                if row_count < page_size:
                    break
                page.wait_for_timeout(90)
        finally:
            context.close()
            browser.close()
    return list(jobs.values()), {
        "transport": "browser-page-public-api",
        "final_url": final_url,
        "pages_ok": pages_ok,
        "total_reported": total_rows,
        "total_pages": total_pages,
    }


def collect_huawei(page_size: int = 10, max_pages: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # page_size=10 deliberately mirrors the public page exactly; current live
    # catalogue reports 69 jobs / 7 pages.
    page_size = max(1, min(50, int(page_size)))
    max_pages = max(1, min(30, int(max_pages)))
    http_jobs: list[dict[str, Any]] = []
    http_diag: dict[str, Any] = {}
    try:
        http_jobs, http_diag = _collect_http(page_size, max_pages)
    except Exception as exc:
        http_diag = {"transport": "http-public-api", "error": f"{type(exc).__name__}: {clean(exc)[:220]}"}

    if http_jobs:
        jobs, diag = http_jobs, http_diag
        fallback_used = False
    else:
        jobs, diag = _collect_browser(page_size, max_pages)
        fallback_used = True

    diagnostics = {
        "endpoint": API_BASE,
        **diag,
        "http_probe": http_diag,
        "browser_fallback_used": fallback_used,
        "page_size": page_size,
        "unique_jobs": len(jobs),
        "ai_infra_present": any(clean(j.get("role")) == "AI Infra工程师" for j in jobs),
        "beijing_jobs": sum(1 for j in jobs if "北京" in clean(j.get("location"))),
    }
    return jobs, diagnostics


if __name__ == "__main__":
    jobs, diagnostics = collect_huawei()
    print(diagnostics)
    for job in jobs[:10]:
        print(job["position_id"], job["role"], job["location"], job["department"])
