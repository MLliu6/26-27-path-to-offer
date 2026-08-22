#!/usr/bin/env python3
"""Huawei 2027 campus jobs from the current public Huawei Careers API.

The legacy ``reccampportal/portal5`` site now redirects to ``/cn`` and should not
be treated as the job source. The current public graduate list calls Huawei's
anonymous recruitmentPosition API. This adapter reproduces only that normal
public request: no login, resume upload, cookies, CAPTCHA or private endpoint.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any
from urllib.parse import urlencode

import requests

API_BASE = "https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/getJobPage"
HW_APP_ID = "app_000000035886"
LIST_URL = "https://career.huawei.com/cn/campus-recruitment-job-list?recruitmentType=FRESH_GRADUATE"
TIMEOUT = 25


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(clean(value).lower() for value in parts if value)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]


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


def _request_page(session: requests.Session, page: int, page_size: int) -> dict[str, Any]:
    url = f"{API_BASE}?{urlencode({'X-HW-ID': HW_APP_ID})}"
    body = {
        "curPage": page,
        "pageSize": page_size,
        "jobType": "CR",
        "recruitmentType": ["FRESH_GRADUATE"],
    }
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = session.post(url, json=body, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Huawei getJobPage returned non-object JSON")
            if payload.get("status") not in (None, 0, "0", 200, "200", "success", "SUCCESS") and not payload.get("data"):
                raise RuntimeError(f"Huawei API status={payload.get('status')} errors={payload.get('errors')}")
            return payload
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(str(last) if last else "Huawei getJobPage failed")


def _job_url(row: dict[str, Any]) -> str:
    # The new Huawei site renders SPA cards without stable anonymous <a> detail
    # URLs. Keep the current official list as navigation target; position_id is
    # the exact Huawei jobId and preserves one identity per real position.
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
        "source_label": "华为校园招聘官网 · 公开职位API",
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
        "observed_via": "employer-public-api",
        "position_id": job_id,
    }
    job["id"] = stable_id("华为", role, location, job_id)
    return job


def collect_huawei(page_size: int = 10, max_pages: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # page_size=10 deliberately mirrors the public page request exactly.
    page_size = max(1, min(50, int(page_size)))
    max_pages = max(1, min(30, int(max_pages)))
    session = _session()
    jobs: dict[str, dict[str, Any]] = {}
    total_rows = 0
    total_pages = 0
    pages_ok = 0
    for page in range(1, max_pages + 1):
        payload = _request_page(session, page, page_size)
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            break
        page_vo = data.get("pageVO") or {}
        if isinstance(page_vo, dict):
            total_rows = int(page_vo.get("totalRows") or total_rows or 0)
            total_pages = int(page_vo.get("totalPages") or total_pages or 0)
        rows = data.get("result") or []
        if not isinstance(rows, list) or not rows:
            break
        pages_ok += 1
        for row in rows:
            if not isinstance(row, dict):
                continue
            job = normalize_huawei_job(row)
            if job:
                jobs[job["position_id"]] = job
        if total_pages and page >= total_pages:
            break
        if len(rows) < page_size:
            break
        time.sleep(0.12)
    diagnostics = {
        "endpoint": API_BASE,
        "transport": "public-huawei-careers-api",
        "page_size": page_size,
        "pages_ok": pages_ok,
        "total_reported": total_rows,
        "total_pages": total_pages,
        "unique_jobs": len(jobs),
        "ai_infra_present": any(clean(j.get("role")) == "AI Infra工程师" for j in jobs.values()),
        "beijing_jobs": sum(1 for j in jobs.values() if "北京" in clean(j.get("location"))),
    }
    return list(jobs.values()), diagnostics


if __name__ == "__main__":
    jobs, diagnostics = collect_huawei()
    print(diagnostics)
    for job in jobs[:10]:
        print(job["position_id"], job["role"], job["location"], job["department"])
