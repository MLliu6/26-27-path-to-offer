#!/usr/bin/env python3
"""Nationwide 2027/new-grad discovery from 国家大学生就业服务平台 (NCSS).

The public job-search page calls an unauthenticated JSON endpoint:
  GET /student/jobs/jobslist/ajax/?jobName=...&offset=N&limit=M...

This adapter uses that same public surface. It gives Path to Offer a broad China
campus sensor across SOEs, banks, private companies and startups without relying
on a third-party GitHub list. Employer-owned recruiting rows still outrank NCSS
in the product when both exist.

Two collection modes are used:
1. broad explicit-2027 queries (2027 / 27届), where rows are safe to label 2027;
2. priority-employer queries, retaining recent rows only when their visible job
   title carries campus/new-grad/intern semantics. If 2027 is not explicit, the
   graduation year remains blank rather than being invented.

No login, session cookie, CAPTCHA bypass, proxy rotation or anti-bot evasion is
used. NCSS rows link to the public NCSS job detail page as the notice URL. They
are not mislabeled as employer-direct application URLs.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / "sources" / "priority_official_sources.json"
API = "https://www.ncss.cn/student/jobs/jobslist/ajax/"
INDEX = "https://www.ncss.cn/student/jobs/index.html"
DETAIL = "https://job.ncss.cn/student/jobs/{job_id}/detail.html"
UA = "PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = 20
PAGE_SIZE = max(20, min(100, int(os.getenv("PTO_NCSS_PAGE_SIZE", "100"))))
MAX_EXPLICIT = max(1000, min(30000, int(os.getenv("PTO_NCSS_MAX_EXPLICIT", "15000"))))
MAX_PAGES_PER_PRIORITY = max(1, min(5, int(os.getenv("PTO_NCSS_PRIORITY_PAGES", "2"))))
MAX_PRIORITY_COMPANIES = max(10, min(120, int(os.getenv("PTO_NCSS_PRIORITY_COMPANIES", "80"))))
MAX_WORKERS = max(2, min(16, int(os.getenv("PTO_NCSS_WORKERS", "10"))))
EXPLICIT_2027 = re.compile(r"2027|27\s*届", re.I)
CAMPUS = re.compile(r"校园招聘|校招|应届|毕业生|实习|管培|秋招|提前批|new\s*grad|graduate|campus|intern", re.I)
TECH = re.compile(r"人工智能|AI|大模型|算法|软件|计算机|信息科技|金融科技|芯片|编译|CUDA|GPU|NPU|机器人|自动驾驶|研发|开发|测试|嵌入式|数据|网络安全|云计算", re.I)
RECENT_CUTOFF = datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp() * 1000


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Referer": INDEX,
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def fetch_page(s: requests.Session, query: str, page: int, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
    params = {
        "jobName": query,
        "industrySectors": "",
        "memberLevel": "",
        "recruitType": "",
        "offset": str(page),
        "limit": str(limit),
        "keyUnits": "",
        "sourcesName": "0",
        "sourcesType": "",
        "_": str(int(time.time() * 1000)),
    }
    r = s.get(API + "?" + urlencode(params), timeout=TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    rows = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
    return [x for x in rows if isinstance(x, dict)]


def iso_ms(value: Any) -> str:
    try:
        n = float(value)
        if n > 10_000_000_000:
            n /= 1000.0
        return datetime.fromtimestamp(n, tz=timezone.utc).date().isoformat()
    except Exception:
        return ""


def salary(row: dict[str, Any]) -> str:
    low, high = row.get("lowMonthPay"), row.get("highMonthPay")
    try:
        lo = float(low) if low is not None else None
        hi = float(high) if high is not None else None
    except Exception:
        return ""
    if lo is None and hi is None:
        return ""
    def fmt(x: float) -> str:
        return str(int(x)) if float(x).is_integer() else f"{x:g}"
    if lo is not None and hi is not None:
        return f"{fmt(lo)}-{fmt(hi)}K/月"
    return f"{fmt(lo if lo is not None else hi)}K/月"


def normalize(row: dict[str, Any], *, explicit_query: bool) -> dict[str, Any] | None:
    company = clean(row.get("recName"))
    role = clean(row.get("jobName"))
    job_id = clean(row.get("jobId"))
    if not company or not role or not job_id:
        return None
    visible = " ".join([role, clean(row.get("major")), clean(row.get("recTags"))])
    explicit = bool(EXPLICIT_2027.search(visible)) or explicit_query
    detail = DETAIL.format(job_id=job_id)
    degree = clean(row.get("degreeName"))
    major = clean(row.get("major"))
    scale = clean(row.get("recScale"))
    prop = clean(row.get("recProperty"))
    heads = clean(row.get("headCount"))
    tags = clean(row.get("recTags"))
    jd_parts = [
        major and f"专业：{major}",
        degree and f"学历：{degree}",
        heads and f"招聘人数：{heads}",
        scale and f"企业规模：{scale}",
        tags and f"企业标签：{tags}",
    ]
    batch = "2027校园招聘" if explicit else ("校园/实习招聘·年份待确认" if CAMPUS.search(role) else "公开招聘")
    job = {
        "source": "ncss-public:2027",
        "source_label": "国家大学生就业服务平台 · 2027招聘",
        "source_url": INDEX,
        "updated_at": iso_ms(row.get("updateDate") or row.get("publishDate")),
        "company": company,
        "department": "",
        "role": role,
        "location": clean(row.get("areaCodeName")),
        "salary": salary(row),
        "batch": batch,
        "company_type": prop,
        "industry": "",
        "graduation": "2027届" if explicit else "",
        "education": degree,
        "notice_url": detail,
        "apply_url": "",
        "jd": "；".join(x for x in jd_parts if x) or role,
        "tags": ["NCSS", "国家大学生就业服务平台"] + (["2027"] if explicit else []) + (["技术相关"] if TECH.search(visible) else []),
        "observed_via": "ncss-public-json-api",
    }
    job["id"] = stable_id(company, role, job["location"], detail)
    return job


def broad_2027() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    s = session()
    jobs: dict[str, dict[str, Any]] = {}
    query_counts: dict[str, int] = {}
    page_counts: dict[str, int] = {}
    for query in ["2027", "27届"]:
        pages = 0
        while len(jobs) < MAX_EXPLICIT:
            page = pages + 1
            rows = fetch_page(s, query, page)
            pages += 1
            if not rows:
                break
            for row in rows:
                job = normalize(row, explicit_query=True)
                if job:
                    jobs[job["notice_url"]] = job
            if len(rows) < PAGE_SIZE or pages * PAGE_SIZE >= MAX_EXPLICIT:
                break
            time.sleep(0.08)
        query_counts[query] = len(jobs)
        page_counts[query] = pages
    return list(jobs.values()), {"query_counts": query_counts, "page_counts": page_counts, "explicit_unique": len(jobs)}


def priority_names() -> list[str]:
    try:
        cfg = json.loads(PRIORITY.read_text(encoding="utf-8"))
    except Exception:
        return []
    names = []
    for row in cfg.get("watch", []):
        if isinstance(row, dict):
            name = clean(row.get("company"))
            if name and name not in names:
                names.append(name)
    return names[:MAX_PRIORITY_COMPANIES]


def priority_query(company: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    s = session()
    kept: dict[str, dict[str, Any]] = {}
    raw = 0
    for page in range(1, MAX_PAGES_PER_PRIORITY + 1):
        try:
            rows = fetch_page(s, company, page, min(PAGE_SIZE, 50))
        except Exception as exc:
            return company, list(kept.values()), {"raw": raw, "kept": len(kept), "error": f"{type(exc).__name__}: {clean(exc)[:120]}"}
        raw += len(rows)
        if not rows:
            break
        for row in rows:
            role = clean(row.get("jobName"))
            published = row.get("updateDate") or row.get("publishDate") or 0
            try:
                recent = float(published) >= RECENT_CUTOFF
            except Exception:
                recent = False
            explicit = bool(EXPLICIT_2027.search(role))
            campus = bool(CAMPUS.search(role))
            # Explicit 2027 is always retained. For current priority employers,
            # a recent campus/intern-titled row is useful discovery but its year
            # stays blank unless the visible row itself says 2027.
            if not explicit and not (recent and campus):
                continue
            job = normalize(row, explicit_query=False)
            if job:
                kept[job["notice_url"]] = job
        if len(rows) < min(PAGE_SIZE, 50):
            break
        time.sleep(0.05)
    return company, list(kept.values()), {"raw": raw, "kept": len(kept), "error": ""}


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(job.get("company")).lower(),
        clean(job.get("role")).lower(),
        clean(job.get("location")).lower(),
        clean(job.get("notice_url") or job.get("apply_url")).lower(),
    )


def main() -> int:
    explicit, broad_diag = broad_2027()
    priority_jobs: list[dict[str, Any]] = []
    pdiag: dict[str, Any] = {}
    names = priority_names()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(priority_query, name): name for name in names}
        for fut in as_completed(futs):
            company = futs[fut]
            try:
                resolved, rows, diag = fut.result()
                priority_jobs.extend(rows)
                pdiag[resolved] = diag
            except Exception as exc:
                pdiag[company] = {"raw": 0, "kept": 0, "error": f"{type(exc).__name__}: {clean(exc)[:120]}"}

    fresh_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in [*explicit, *priority_jobs]:
        fresh_map[identity(job)] = job
    fresh = list(fresh_map.values())

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("ncss_public_harvester.py must run before compact_feed.py")
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if isinstance(job, dict) and clean(job.get("company")) and clean(job.get("role")):
            merged[identity(job)] = job
    # NCSS is discovery evidence. Never overwrite an employer-direct row with a
    # national-platform duplicate merely because both mention the same job.
    for job in fresh:
        key = identity(job)
        if key not in merged:
            merged[key] = job
    out = dict(payload)
    out["schema_version"] = 3
    out["generated_at"] = utc_now()
    out["jobs"] = list(merged.values())
    JOBS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    target_counts = {}
    for company in names:
        n = sum(1 for j in fresh if company in clean(j.get("company")))
        if n:
            target_counts[company] = n
    tech_bj = sum(1 for j in fresh if "北京" in clean(j.get("location")) and TECH.search(" ".join([clean(j.get("role")), clean(j.get("jd"))])))
    state_owned = sum(1 for j in fresh if re.search(r"国有企业|机关/事业单位", clean(j.get("company_type"))))

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "ncss-2027-public",
        "label": "国家大学生就业服务平台 · 2027岗位",
        "url": INDEX,
        "ok": bool(fresh),
        "count": len(fresh),
        "error": "" if fresh else "public NCSS query returned no retained rows",
        "diagnostics": {
            **broad_diag,
            "priority_queries": len(names),
            "priority_companies_with_rows": len(target_counts),
            "priority_company_counts": sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[:40],
            "beijing_technical_rows": tech_bj,
            "state_owned_rows": state_owned,
            "priority_query_diagnostics": pdiag,
            "detail_url_pattern": "https://job.ncss.cn/student/jobs/{jobId}/detail.html",
        },
    }
    sources = [s for s in status.get("sources", []) if not isinstance(s, dict) or s.get("name") != group["name"]]
    sources.insert(0, group)
    status["sources"] = sources
    status["catalog_count"] = len(out["jobs"])
    status["generated_at"] = utc_now()
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"NCSS 2027: explicit={len(explicit)} priority={len(priority_jobs)} unique={len(fresh)} merged={len(out['jobs'])} Beijing-tech={tech_bj} state-owned={state_owned}")
    print("NCSS priority companies:", sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[:30])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
