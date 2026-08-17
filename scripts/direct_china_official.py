#!/usr/bin/env python3
"""First-party China employer crawler for Path to Offer.

This module is intentionally independent from the broader federation adapters.
It queries employers' own anonymous recruiting APIs and merges the resulting
canonical job rows into the readable catalogue before the browser compaction
step.  Third-party lists may help us discover an official endpoint, but the job
row stored here is produced from the employer's public recruiting surface.

Current adapters:
- Meituan: zhaopin.meituan.com public JSON API, campus/intern modes.
- Tencent: careers.tencent.com public JSON API.

No account cookies, login sessions, CAPTCHA solving, proxy rotation or anti-bot
bypass are used. Each source fails independently and previous catalogue rows are
kept when an upstream source is temporarily unavailable.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "sources" / "domestic_direct_sources.json"
UA = "PathToOfferBot/0.8 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = 25
MAX_JD_CHARS = max(600, int(os.getenv("PTO_DIRECT_JD_CHARS", "5000")))


def compact(value: Any, limit: int = MAX_JD_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def names(value: Any) -> str:
    if not isinstance(value, list):
        return clean(value)
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            v = item
        elif isinstance(item, dict):
            v = item.get("name") or item.get("label") or item.get("value") or ""
        else:
            v = ""
        v = clean(v)
        if v and v not in out:
            out.append(v)
    return "/".join(out)


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except Exception:
            return ""
    text = str(value).strip()
    m = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return text[:10] if re.match(r"20\d{2}-\d{2}-\d{2}", text) else ""


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    return s


def request_json(s: requests.Session, method: str, url: str, **kwargs) -> Any:
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = s.request(method, url, timeout=TIMEOUT, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(str(last) if last else "request failed")


def meituan(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    api = "https://zhaopin.meituan.com/api/official/job/getJobList"
    company = config.get("company") or "美团"
    page_size = max(20, min(100, int(config.get("page_size") or 100)))
    max_pages = max(1, min(60, int(config.get("max_pages") or 40)))
    codes = [str(x) for x in (config.get("job_type_codes") or ["1", "2"])]
    s = session()
    jobs: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {"endpoint": api, "job_type_counts": {}, "page_size": page_size}

    for code in codes:
        total = 0
        collected = 0
        for page_no in range(1, max_pages + 1):
            body = {
                "page": {"pageNo": page_no, "pageSize": page_size},
                "keywords": "",
                "jobShareType": "1",
                "jobType": [{"code": code, "subCode": []}],
                "cityList": [], "department": [], "jfJgList": [],
                "typeCode": [], "specialCode": [],
            }
            payload = request_json(s, "POST", api, json=body, headers={"Content-Type": "application/json"})
            data = payload.get("data") or {}
            rows = data.get("list") or []
            page = data.get("page") or {}
            total = int(page.get("totalCount") or total or 0)
            if not isinstance(rows, list) or not rows:
                break
            for p in rows:
                if not isinstance(p, dict):
                    continue
                role = clean(p.get("name"))
                job_id = clean(p.get("jobUnionId"))
                if not role or not job_id:
                    continue
                location = names(p.get("cityList"))
                department = names(p.get("department"))
                detail = f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={job_id}&jobShareType=1&highlightType=campus"
                batch = "校园招聘" if code == "1" else ("实习/校园专项" if code == "2" else "社会招聘")
                jd = "\n".join(x for x in [
                    department and f"部门：{department}",
                    clean(p.get("jobFamily")) and f"岗位族：{clean(p.get('jobFamily'))}",
                    clean(p.get("jobDuty")),
                    clean(p.get("jobRequirement")),
                ] if x)
                job = {
                    "source": "direct-official:meituan",
                    "source_label": "美团校园招聘官网",
                    "source_url": config.get("official_url") or "https://zhaopin.meituan.com/web/campus",
                    "updated_at": iso_date(p.get("refreshTime") or p.get("firstPostTime")),
                    "company": company,
                    "department": department,
                    "role": role,
                    "location": location,
                    "salary": "",
                    "batch": batch,
                    "company_type": config.get("company_type") or "民营/互联网",
                    "industry": "互联网/生活服务",
                    "graduation": clean(p.get("graduateYear") or p.get("graduationYear")),
                    "education": clean(p.get("education") or p.get("educationName")),
                    "notice_url": detail,
                    "apply_url": detail,
                    "jd": compact(jd or role),
                    "tags": ["官方招聘", "美团", batch],
                    "observed_via": "employer-public-api",
                }
                job["id"] = stable_id(company, role, location, detail)
                jobs[job_id] = job
                collected += 1
            if total and page_no * page_size >= total:
                break
            time.sleep(0.35)
        diagnostics["job_type_counts"][code] = {"total_reported": total, "rows_seen": collected}
    diagnostics["unique_jobs"] = len(jobs)
    return list(jobs.values()), diagnostics


def tencent(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    api = "https://careers.tencent.com/tencentcareer/api/post/Query"
    company = config.get("company") or "腾讯"
    page_size = max(20, min(100, int(config.get("page_size") or 100)))
    max_pages = max(1, min(40, int(config.get("max_pages") or 20)))
    s = session()
    jobs: dict[str, dict[str, Any]] = {}
    total = 0
    for page_no in range(1, max_pages + 1):
        params = {
            "timestamp": str(int(time.time() * 1000)), "keyword": "",
            "pageIndex": str(page_no), "pageSize": str(page_size), "language": "zh-cn",
        }
        payload = request_json(s, "GET", f"{api}?{urlencode(params)}")
        data = payload.get("Data") or {}
        rows = data.get("Posts") or []
        total = int(data.get("Count") or total or 0)
        if not isinstance(rows, list) or not rows:
            break
        for p in rows:
            if not isinstance(p, dict):
                continue
            role = clean(p.get("RecruitPostName"))
            post_id = clean(p.get("PostId"))
            detail = clean(p.get("PostURL")) or (f"https://careers.tencent.com/jobdesc.html?postId={post_id}" if post_id else "")
            if not role or not detail:
                continue
            location = "-".join(x for x in [clean(p.get("CountryName")), clean(p.get("LocationName"))] if x)
            department = clean(p.get("BGName"))
            category = clean(p.get("CategoryName"))
            responsibility = clean(p.get("Responsibility"))
            requirement = clean(p.get("Requirement"))
            batch_signal = " ".join(str(p.get(k) or "") for k in ("RecruitPostTypeName", "PostTypeName", "CategoryName", "RecruitPostName"))
            batch = "校园招聘" if re.search(r"校招|应届|毕业生|实习|campus|graduate", batch_signal, re.I) else ""
            jd = "\n".join(x for x in [department and f"BG：{department}", category and f"类别：{category}", responsibility, requirement] if x)
            job = {
                "source": "direct-official:tencent",
                "source_label": "腾讯招聘官网",
                "source_url": config.get("official_url") or "https://careers.tencent.com/search.html",
                "updated_at": iso_date(p.get("LastUpdateTime")),
                "company": company,
                "department": department,
                "role": role,
                "location": location,
                "salary": "",
                "batch": batch,
                "company_type": config.get("company_type") or "民营/互联网",
                "industry": "互联网/科技",
                "graduation": "",
                "education": "",
                "notice_url": detail,
                "apply_url": detail,
                "jd": compact(jd or role),
                "tags": ["官方招聘", "腾讯"] + ([batch] if batch else []),
                "observed_via": "employer-public-api",
            }
            job["id"] = stable_id(company, role, location, detail)
            jobs[detail] = job
        if total and page_no * page_size >= total:
            break
        time.sleep(0.18)
    return list(jobs.values()), {"endpoint": api, "total_reported": total, "unique_jobs": len(jobs)}


ADAPTERS = {"meituan": meituan, "tencent": tencent}


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(job.get("company")).lower(), clean(job.get("role")).lower(),
        clean(job.get("location")).lower(), clean(job.get("apply_url") or job.get("notice_url")).lower(),
    )


def merge_catalog(existing: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if isinstance(job, dict) and clean(job.get("company")) and clean(job.get("role")):
            merged[identity(job)] = job
    for job in fresh:
        key = identity(job)
        old = merged.get(key)
        if old is None:
            merged[key] = job
            continue
        # Prefer the direct employer row when it has a richer JD/direct URL.
        if str(job.get("source", "")).startswith("direct-official:"):
            out = dict(old)
            for k, v in job.items():
                if v not in (None, "", [], {}):
                    out[k] = v
            merged[key] = out
    return list(merged.values())


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("direct_china_official.py must run before compact_feed.py")

    fresh: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    for src in cfg.get("sources", []):
        if not isinstance(src, dict) or not src.get("enabled", True):
            continue
        adapter = clean(src.get("adapter"))
        fn = ADAPTERS.get(adapter)
        if not fn:
            source_results.append({"id": src.get("id"), "company": src.get("company"), "ok": False, "count": 0, "error": f"unsupported adapter: {adapter}"})
            continue
        try:
            jobs, diag = fn(src)
            fresh.extend(jobs)
            source_results.append({"id": src.get("id"), "company": src.get("company"), "official_url": src.get("official_url"), "ok": True, "count": len(jobs), "diagnostics": diag})
            print(f"direct official {src.get('company')}: {len(jobs)}")
        except Exception as exc:
            source_results.append({"id": src.get("id"), "company": src.get("company"), "official_url": src.get("official_url"), "ok": False, "count": 0, "error": f"{type(exc).__name__}: {clean(exc)[:240]}"})
            print(f"direct official {src.get('company')}: FAILED {type(exc).__name__}: {clean(exc)[:160]}")

    merged = merge_catalog(existing if isinstance(existing, list) else [], fresh)
    out = dict(payload) if isinstance(payload, dict) else {}
    out["schema_version"] = 3
    out["generated_at"] = utc_now()
    out["jobs"] = merged
    JOBS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "direct-china-official",
        "label": "国内企业招聘官网 · 自主直连",
        "url": "",
        "ok": any(x.get("ok") and x.get("count", 0) > 0 for x in source_results),
        "count": len(fresh),
        "error": "",
        "diagnostics": {"registry": "sources/domestic_direct_sources.json", "sources": source_results},
    }
    sources = [s for s in status.get("sources", []) if not isinstance(s, dict) or s.get("name") != group["name"]]
    sources.insert(0, group)
    status["sources"] = sources
    status["catalog_count"] = len(merged)
    status["generated_at"] = utc_now()
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"direct official merged: fresh={len(fresh)} catalog={len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
