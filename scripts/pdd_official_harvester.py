#!/usr/bin/env python3
"""First-party Pinduoduo campus-position adapter.

PDD's public campus frontend calls anonymous JSON endpoints on the employer-owned
`careers.pddglobalhr.com` origin. This adapter enumerates every public graduate
and internship row, enriches graduate rows with the public detail endpoint, and
merges canonical employer-direct jobs into Path to Offer.

The public endpoint currently clamps a requested page size of 100 to ten rows.
Pagination therefore stops on the reported total / accumulated rows, never on
`len(rows) < requested_page_size`; the latter was the concrete reason only the
first ten graduate jobs were initially retained.

User-reported official job URLs are stored as live-resolved seeds. A seed is not
trusted by declaration: its stable position UUID must still resolve through the
employer's own public endpoint and its title must match the expected position.

No login, account cookie, CAPTCHA solving, proxy rotation, stealth automation or
access-control bypass is used.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "sources" / "official_position_seeds.json"
BASE = "https://careers.pddglobalhr.com"
LIST_GRAD = f"{BASE}/api/careers/api/recruit/position/list"
LIST_INTERN = f"{BASE}/api/careers/api/recruit/position/train/list"
DETAIL_GRAD = f"{BASE}/api/careers/api/recruit/position/detail"
DETAIL_INTERN_CANDIDATES = [
    f"{BASE}/api/careers/api/recruit/position/train/detail",
    f"{BASE}/api/careers/api/recruit/position/detail/train",
]
OFFICIAL_GRAD = f"{BASE}/campus/grad"
OFFICIAL_INTERN = f"{BASE}/campus/intern"
UA = "PathToOfferBot/1.1 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = max(8, min(45, int(os.getenv("PTO_PDD_TIMEOUT", "22"))))
PAGE_SIZE = max(10, min(100, int(os.getenv("PTO_PDD_PAGE_SIZE", "100"))))
MAX_PAGES = max(2, min(30, int(os.getenv("PTO_PDD_MAX_PAGES", "12"))))
MAX_JD = max(1200, min(12000, int(os.getenv("PTO_PDD_JD_CHARS", "7000"))))


def compact(value: Any, limit: int = MAX_JD) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def iso_date(value: Any) -> str:
    try:
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc).date().isoformat()
    except Exception:
        text = clean(value)
        match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text)
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}" if match else ""


def public_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": OFFICIAL_GRAD,
    })
    return session


def post_json(session: requests.Session, url: str, body: dict[str, Any]) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = session.post(url, json=body, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("success") is False:
                message = payload.get("errorMsg") if isinstance(payload, dict) else payload
                raise RuntimeError(compact(message, 220) or "invalid payload")
            return payload
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(str(last) if last else "PDD request failed")


def result_object(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("result")
    return value if isinstance(value, dict) else {}


def labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = clean(item.get("name") if isinstance(item, dict) else item)
        if text and text not in out:
            out.append(text)
    return out


def detail_url(position_id: str, scope: str) -> str:
    page = "intern" if scope == "intern" else "grad"
    return f"{BASE}/campus/{page}/detail?positionId={position_id}"


def fetch_detail(session: requests.Session, position_id: str, scope: str) -> dict[str, Any]:
    if scope == "grad":
        try:
            return result_object(post_json(session, DETAIL_GRAD, {"id": position_id, "t": None}))
        except Exception:
            return {}
    for endpoint in DETAIL_INTERN_CANDIDATES:
        try:
            row = result_object(post_json(session, endpoint, {"id": position_id, "t": None}))
            if row:
                return row
        except Exception:
            continue
    return {}


def merge_row(list_row: dict[str, Any], detail_row: dict[str, Any]) -> dict[str, Any]:
    out = dict(list_row)
    for key, value in detail_row.items():
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def normalize(row: dict[str, Any], scope: str) -> dict[str, Any] | None:
    position_id = clean(row.get("id") or row.get("positionId"))
    role = clean(row.get("name") or row.get("positionName") or row.get("title"))
    if not position_id or not role:
        return None

    location = clean(row.get("workLocationName") or row.get("workLocation") or row.get("location"))
    category = clean(row.get("jobName") or row.get("job") or row.get("categoryName"))
    recruit_type = clean(row.get("recruitTypeName") or row.get("batchName"))
    graduation = clean(row.get("graduationYear"))
    if graduation and not graduation.endswith("届"):
        graduation = f"{graduation}届"
    batch = f"{graduation or '校园'}{'实习生招聘' if scope == 'intern' else '校园招聘'}"
    if recruit_type:
        batch += f" · {recruit_type}"

    duties = clean(row.get("jobDuty") or row.get("responsibility") or row.get("description"))
    requirements = clean(row.get("serveRequirement") or row.get("jobRequirement") or row.get("requirement"))
    bonus = clean(row.get("bonus"))
    jd_parts = [
        category and f"职位类别：{category}",
        recruit_type and f"招聘项目：{recruit_type}",
        duties and f"岗位职责：{duties}",
        requirements and f"任职要求：{requirements}",
        bonus and f"加分项：{bonus}",
    ]
    url = detail_url(position_id, scope)
    row_labels = labels(row.get("labelList"))
    job = {
        "source": "direct-official:pdd",
        "source_label": "拼多多校园招聘官网 · 自主直连",
        "source_url": OFFICIAL_INTERN if scope == "intern" else OFFICIAL_GRAD,
        "updated_at": iso_date(row.get("releaseTime") or row.get("updateTime")),
        "company": "拼多多",
        "department": category,
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": "民营/互联网",
        "industry": "互联网/电商/人工智能",
        "graduation": graduation,
        "education": clean(row.get("education") or row.get("educationName")),
        "notice_url": url,
        "apply_url": url,
        "jd": compact("；".join(part for part in jd_parts if part) or role),
        "tags": ["企业官网", "拼多多", "校园招聘", category, recruit_type, *row_labels],
        "observed_via": "employer-public-json-api",
        "position_id": position_id,
        "scope": scope,
    }
    job["tags"] = [value for index, value in enumerate(job["tags"]) if value and value not in job["tags"][:index]]
    job["id"] = stable_id(job["company"], role, location, position_id)
    return job


def enumerate_scope(session: requests.Session, scope: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint = LIST_INTERN if scope == "intern" else LIST_GRAD
    jobs: dict[str, dict[str, Any]] = {}
    pages = 0
    raw = 0
    total = 0
    errors: list[str] = []
    seen_pages: set[tuple[str, ...]] = set()
    observed_page_sizes: list[int] = []

    for page in range(1, MAX_PAGES + 1):
        payload = post_json(session, endpoint, {"page": page, "pageSize": PAGE_SIZE, "t": None})
        result = result_object(payload)
        rows = result.get("list") or []
        try:
            total = int(result.get("total") or result.get("count") or total or 0)
        except Exception:
            pass
        pages += 1
        if not isinstance(rows, list) or not rows:
            break

        page_ids = tuple(clean(row.get("id") or row.get("positionId")) for row in rows if isinstance(row, dict))
        if page_ids and page_ids in seen_pages:
            errors.append(f"pagination repeated page {page}; stopped to avoid an infinite loop")
            break
        if page_ids:
            seen_pages.add(page_ids)
        observed_page_sizes.append(len(rows))
        raw += len(rows)

        for raw_row in rows:
            if not isinstance(raw_row, dict):
                continue
            position_id = clean(raw_row.get("id") or raw_row.get("positionId"))
            detail: dict[str, Any] = {}
            if position_id:
                try:
                    detail = fetch_detail(session, position_id, scope)
                except Exception as exc:
                    errors.append(f"{position_id}: {type(exc).__name__}: {compact(exc, 120)}")
            job = normalize(merge_row(raw_row, detail), scope)
            if job:
                jobs[job["position_id"]] = job

        # PDD currently returns ten rows even when pageSize=100. Accumulated raw
        # rows and the API's own total are the only safe completion condition.
        if total and raw >= total:
            break
        time.sleep(0.08)

    return list(jobs.values()), {
        "scope": scope,
        "pages": pages,
        "raw": raw,
        "reported_total": total,
        "unique": len(jobs),
        "requested_page_size": PAGE_SIZE,
        "observed_page_sizes": observed_page_sizes,
        "detail_errors": errors[:20],
    }


def load_seeds() -> list[dict[str, Any]]:
    try:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [row for row in payload.get("positions", []) if isinstance(row, dict) and clean(row.get("adapter")) == "pdd"]


def resolve_seeds(session: requests.Session, existing: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for seed in load_seeds():
        position_id = clean(seed.get("position_id"))
        scope = clean(seed.get("scope")) or "grad"
        if not position_id:
            continue
        job = existing.get(position_id)
        error = ""
        if not job:
            try:
                detail = fetch_detail(session, position_id, scope)
                job = normalize(detail, scope) if detail else None
            except Exception as exc:
                error = f"{type(exc).__name__}: {compact(exc, 180)}"
        expected = clean(seed.get("expected_title"))
        title_ok = bool(job and (not expected or expected.lower() in clean(job.get("role")).lower()))
        diagnostics.append({
            "position_id": position_id,
            "expected_title": expected,
            "found": bool(job),
            "title_ok": title_ok,
            "resolved_title": clean(job.get("role")) if job else "",
            "url": clean(seed.get("url")),
            "error": error,
        })
        if job:
            existing[position_id] = job
            resolved.append(job)
    return resolved, diagnostics


def collect_pdd(session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    active_session = session or public_session()
    jobs: dict[str, dict[str, Any]] = {}
    scope_diagnostics: list[dict[str, Any]] = []
    for scope in ("grad", "intern"):
        rows, diagnostics = enumerate_scope(active_session, scope)
        scope_diagnostics.append(diagnostics)
        for job in rows:
            jobs[job["position_id"]] = job
    _, seed_diagnostics = resolve_seeds(active_session, jobs)

    categories: dict[str, int] = {}
    for job in jobs.values():
        category = clean(job.get("department")) or "未分类"
        categories[category] = categories.get(category, 0) + 1
    diagnostics = {
        "official_url": OFFICIAL_GRAD,
        "list_endpoints": [LIST_GRAD, LIST_INTERN],
        "scopes": scope_diagnostics,
        "unique_jobs": len(jobs),
        "categories": sorted(categories.items(), key=lambda item: (-item[1], item[0])),
        "seeds": seed_diagnostics,
        "seed_gate_ok": all(row.get("found") and row.get("title_ok") for row in seed_diagnostics) if seed_diagnostics else True,
    }
    return list(jobs.values()), diagnostics


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(job.get("company")).lower(),
        clean(job.get("role")).lower(),
        clean(job.get("location")).lower(),
        clean(job.get("position_id") or job.get("apply_url") or job.get("notice_url")).lower(),
    )


def merge_catalog(existing: Iterable[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if not isinstance(job, dict):
            continue
        if clean(job.get("source")).lower() == "direct-official:pdd":
            continue
        if clean(job.get("company")) and clean(job.get("role")):
            merged[identity(job)] = job
    for job in fresh:
        merged[identity(job)] = job
    return list(merged.values())


def main() -> int:
    jobs, diagnostics = collect_pdd()
    if not jobs:
        raise RuntimeError("PDD public API returned zero concrete positions; preserving the previous catalogue")
    if not diagnostics.get("seed_gate_ok"):
        raise RuntimeError(f"PDD exact-position seed gate failed: {diagnostics.get('seeds')}")

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("pdd_official_harvester.py must run before compact_feed.py")
    merged = merge_catalog(existing if isinstance(existing, list) else [], jobs)
    out = dict(payload) if isinstance(payload, dict) else {}
    out.update({"schema_version": 3, "generated_at": utc_now(), "jobs": merged})
    JOBS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "pdd-direct-official",
        "label": "拼多多校园招聘官网 · 全量自主直连",
        "url": OFFICIAL_GRAD,
        "ok": True,
        "count": len(jobs),
        "error": "",
        "diagnostics": diagnostics,
    }
    sources = [source for source in status.get("sources", []) if not isinstance(source, dict) or source.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(merged), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdd_jobs": len(jobs), "seed_gate_ok": diagnostics.get("seed_gate_ok"), "categories": diagnostics.get("categories")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
