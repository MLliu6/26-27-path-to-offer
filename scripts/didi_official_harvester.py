#!/usr/bin/env python3
"""First-party DiDi recruiting adapter.

DiDi's employer-owned recruiting frontend exposes anonymous public list and job
detail endpoints. This adapter enumerates every observed recruitment scope,
continues pagination until an empty/repeated page (the upstream `total` field is
currently unreliable), enriches each row from the public detail endpoint, and
normalizes concrete employer-direct jobs for Path to Offer.

The adapter covers social, campus, internship and overseas scopes when the
corresponding public endpoint returns rows. It never creates a row from a portal
name alone. No login, account cookie, CAPTCHA solving, proxy rotation, stealth
automation or access-control bypass is used.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import requests

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

BASE = "https://talent.didiglobal.com"
LIST_ENDPOINT = f"{BASE}/recruit-portal-service/api/job/front/list"
DETAIL_ENDPOINT = f"{BASE}/recruit-portal-service/api/job/front/view/{{jd_id}}"
TYPE_ENDPOINT = f"{BASE}/recruit-portal-service/api/job/jdpublish/confirm/listJdTypes"
LOCATION_ENDPOINT = f"{BASE}/recruit-portal-service/api/job/job_locations"
UA = "PathToOfferBot/1.2 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = max(8, min(45, int(os.getenv("PTO_DIDI_TIMEOUT", "22"))))
PAGE_SIZE = max(16, min(100, int(os.getenv("PTO_DIDI_PAGE_SIZE", "100"))))
MAX_PAGES = max(2, min(160, int(os.getenv("PTO_DIDI_MAX_PAGES", "80"))))
DETAIL_WORKERS = max(2, min(20, int(os.getenv("PTO_DIDI_DETAIL_WORKERS", "10"))))
MAX_JD = max(800, min(14000, int(os.getenv("PTO_DIDI_JD_CHARS", "7000"))))

# The numeric route IDs are visible in DiDi's public URL/API contract. Rows are
# retained only when the corresponding list endpoint actually returns jobs.
SCOPES = [
    {"code": "1", "slug": "social", "label": "社会招聘"},
    {"code": "2", "slug": "campus", "label": "校园招聘"},
    {"code": "3", "slug": "intern", "label": "实习生招聘"},
    {"code": "4", "slug": "overseas", "label": "海外招聘"},
]


def compact(value: Any, limit: int = MAX_JD) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def public_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Referer": f"{BASE}/social/list/1",
        "Origin": BASE,
    })
    return session


def get_json(session: requests.Session, url: str) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("invalid JSON payload")
            meta = payload.get("meta") or {}
            code = meta.get("code") if isinstance(meta, dict) else 0
            if code not in (None, 0, "0"):
                raise RuntimeError(compact(meta.get("message"), 220) or f"upstream code {code}")
            return payload
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(str(last) if last else "DiDi request failed")


def parse_date(value: Any) -> str:
    text = clean(value)
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return ""


def infer_graduation(text: str) -> str:
    match = re.search(r"(20(?:2[4-9]|3\d))\s*届", text)
    if match:
        return f"{match.group(1)}届"
    window = re.search(r"(20(?:2[4-9]|3\d))[.年/-]\d{1,2}[^。；;\n]{0,30}(?:毕业|获得|学位)", text)
    return f"{window.group(1)}届" if window else ""


def infer_education(text: str) -> str:
    lower = text.lower()
    if "博士" in text or "phd" in lower:
        return "博士"
    if "硕士" in text or "研究生" in text or "master" in lower:
        return "硕士"
    if "本科" in text or "学士" in text or "bachelor" in lower:
        return "本科"
    if "大专" in text or "专科" in text:
        return "大专"
    return ""


def detail_url(jd_id: str, scope: dict[str, str]) -> str:
    return f"{BASE}/{scope['slug']}/p/{jd_id}"


def list_scope(session: requests.Session, scope: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    page_signatures: set[tuple[str, ...]] = set()
    page_sizes: list[int] = []
    errors: list[str] = []
    reported_total = 0
    pages = 0
    for page in range(1, MAX_PAGES + 1):
        query = urlencode({"page": page, "recruitType": scope["code"], "size": PAGE_SIZE})
        payload = get_json(session, f"{LIST_ENDPOINT}?{query}")
        data = payload.get("data") or {}
        rows = data.get("items") or data.get("list") or []
        try:
            reported_total = max(reported_total, int(data.get("total") or 0))
        except Exception:
            pass
        pages += 1
        if not isinstance(rows, list) or not rows:
            break
        signature = tuple(clean(row.get("jdId") or row.get("id") or row.get("jdNo")) for row in rows if isinstance(row, dict))
        if signature and signature in page_signatures:
            errors.append(f"repeated page signature at page={page}")
            break
        if signature:
            page_signatures.add(signature)
        page_sizes.append(len(rows))
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            jd_id = clean(raw.get("jdId") or raw.get("id"))
            role = clean(raw.get("jobName") or raw.get("title"))
            if jd_id and role:
                row = dict(raw)
                row["_scope"] = scope
                jobs[jd_id] = row
        if reported_total and len(jobs) >= reported_total:
            break
        time.sleep(0.04)
    return list(jobs.values()), {
        "scope": scope["label"], "code": scope["code"], "pages": pages,
        "reported_total": reported_total, "unique": len(jobs),
        "observed_page_sizes": page_sizes, "errors": errors[:10],
    }


def fetch_detail(jd_id: str) -> dict[str, Any]:
    session = public_session()
    payload = get_json(session, DETAIL_ENDPOINT.format(jd_id=jd_id))
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def merge_detail(raw: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw)
    for key, value in detail.items():
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def normalize(raw: dict[str, Any]) -> dict[str, Any] | None:
    scope = raw.get("_scope") if isinstance(raw.get("_scope"), dict) else SCOPES[0]
    jd_id = clean(raw.get("jdId") or raw.get("id"))
    role = clean(raw.get("jobName") or raw.get("title"))
    if not jd_id or not role:
        return None
    department = clean(raw.get("deptName") or raw.get("department"))
    location = clean(raw.get("workArea") or raw.get("location"))
    category = clean(raw.get("jobTypeName") or raw.get("jobType"))
    duties = clean(raw.get("jobDesc") or raw.get("jobDuty") or raw.get("description"))
    qualification = clean(raw.get("qualification") or raw.get("jobQualification") or raw.get("requirement"))
    recruit_code = clean(raw.get("recruitType")) or scope["code"]
    matched_scope = next((item for item in SCOPES if item["code"] == recruit_code), scope)
    batch = matched_scope["label"]
    jd = compact("；".join(part for part in [
        department and f"部门：{department}", category and f"职位类别：{category}",
        duties and f"岗位职责：{duties}", qualification and f"任职要求：{qualification}",
    ] if part) or role)
    blob = " ".join([role, jd, batch])
    url = detail_url(jd_id, matched_scope)
    job = {
        "source": "direct-official:didi",
        "source_label": "滴滴招聘官网 · 全量自主直连",
        "source_url": f"{BASE}/{matched_scope['slug']}/list/{matched_scope['code']}",
        "updated_at": parse_date(raw.get("refreshTime") or raw.get("publishTime") or raw.get("createTime")),
        "company": "滴滴",
        "department": department,
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": "民营/互联网/出行",
        "industry": "互联网/出行/人工智能",
        "graduation": infer_graduation(blob),
        "education": infer_education(blob),
        "notice_url": url,
        "apply_url": url,
        "jd": jd,
        "tags": ["企业官网", "滴滴", batch, category, department],
        "observed_via": "employer-public-json-api",
        "position_id": jd_id,
        "scope": matched_scope["slug"],
    }
    job["tags"] = [value for index, value in enumerate(job["tags"]) if value and value not in job["tags"][:index]]
    job["id"] = stable_id(job["company"], role, location, jd_id)
    return job


def collect_didi(session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    active = session or public_session()
    raw_jobs: dict[str, dict[str, Any]] = {}
    scope_diagnostics = []
    for scope in SCOPES:
        rows, diagnostics = list_scope(active, scope)
        scope_diagnostics.append(diagnostics)
        for row in rows:
            raw_jobs[clean(row.get("jdId") or row.get("id"))] = row

    details: dict[str, dict[str, Any]] = {}
    detail_errors: list[str] = []
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
        futures = {pool.submit(fetch_detail, jd_id): jd_id for jd_id in raw_jobs}
        for future in as_completed(futures):
            jd_id = futures[future]
            try:
                details[jd_id] = future.result()
            except Exception as exc:
                detail_errors.append(f"{jd_id}: {type(exc).__name__}: {compact(exc, 160)}")

    jobs: dict[str, dict[str, Any]] = {}
    categories: dict[str, int] = {}
    batches: dict[str, int] = {}
    for jd_id, raw in raw_jobs.items():
        job = normalize(merge_detail(raw, details.get(jd_id, {})))
        if not job:
            continue
        jobs[jd_id] = job
        categories[job["department"] or "未分类"] = categories.get(job["department"] or "未分类", 0) + 1
        batches[job["batch"]] = batches.get(job["batch"], 0) + 1

    diagnostics = {
        "official_url": BASE,
        "list_endpoint": LIST_ENDPOINT,
        "detail_endpoint": DETAIL_ENDPOINT,
        "scopes": scope_diagnostics,
        "unique_jobs": len(jobs),
        "detail_success": len(details),
        "detail_errors": detail_errors[:30],
        "departments": sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:30],
        "batches": sorted(batches.items(), key=lambda item: (-item[1], item[0])),
    }
    return list(jobs.values()), diagnostics


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(job.get("company")).lower(), clean(job.get("role")).lower(),
        clean(job.get("location")).lower(), clean(job.get("position_id") or job.get("apply_url")).lower(),
    )


def merge_catalog(existing: Iterable[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if not isinstance(job, dict):
            continue
        if clean(job.get("source")).lower() == "direct-official:didi":
            continue
        if clean(job.get("company")) and clean(job.get("role")):
            merged[identity(job)] = job
    for job in fresh:
        merged[identity(job)] = job
    return list(merged.values())


def main() -> int:
    jobs, diagnostics = collect_didi()
    if not jobs:
        raise RuntimeError("DiDi public recruiting API returned zero concrete positions; preserving previous catalogue")
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("didi_official_harvester.py must run before compact_feed.py")
    merged = merge_catalog(existing if isinstance(existing, list) else [], jobs)
    payload = dict(payload) if isinstance(payload, dict) else {}
    payload.update({"schema_version": 3, "generated_at": utc_now(), "jobs": merged})
    JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {"name": "didi-direct-official", "label": "滴滴招聘官网 · 全量自主直连", "url": BASE, "ok": True, "count": len(jobs), "error": "", "diagnostics": diagnostics}
    sources = [source for source in status.get("sources", []) if not isinstance(source, dict) or source.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(merged), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"didi_jobs": len(jobs), "batches": diagnostics["batches"], "details": diagnostics["detail_success"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
