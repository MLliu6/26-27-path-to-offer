#!/usr/bin/env python3
"""Read Kuaishou's anonymous public campus-position API with real pagination."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from scripts.aggregate_jobs import clean, stable_id

CAMPUS_API = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
DEFAULT_PAGE_SIZE = 50
MAX_PAGES = 80
CITY_MAP = {
    "beijing": "北京", "Beijing": "北京",
    "shanghai": "上海", "Shanghai": "上海",
    "Guangzhou": "广州", "guangzhou": "广州",
    "Shenzhen": "深圳", "shenzhen": "深圳",
    "Hangzhou": "杭州", "hangzhou": "杭州",
    "suzhou": "苏州", "Suzhou": "苏州",
    "Wuhan": "武汉", "wuhan": "武汉",
    "Chengdu": "成都", "chengdu": "成都",
}


def response_result(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Kuaishou API returned a non-object payload")
    code = payload.get("code")
    if code not in (0, 200, "0", "200", None):
        raise RuntimeError(f"Kuaishou API code={code!r}: {clean(payload.get('message'))[:180]}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Kuaishou API response has no result object")
    return result


def rows_from(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("list")
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def location_of(row: dict[str, Any]) -> str:
    names: list[str] = []
    values = row.get("workLocationDicts")
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            name = clean(item.get("name")) or CITY_MAP.get(clean(item.get("code")), "")
            if name and name not in names:
                names.append(name)
    if not names:
        raw = clean(row.get("workLocationCode"))
        for part in raw.replace("，", ",").replace("/", ",").split(","):
            name = CITY_MAP.get(part.strip(), part.strip())
            if name and name not in names:
                names.append(name)
    return "/".join(names[:8])


def timestamp_text(value: Any) -> str:
    if isinstance(value, (int, float)) and value > 10_000_000_000:
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
    return clean(value)[:20]


def normalize_job(config: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    company = clean(config.get("company")) or "快手"
    role = clean(row.get("name"))
    position_id = clean(row.get("id") or row.get("code"))
    if not role or not position_id:
        return None
    location = location_of(row)
    description = clean(row.get("description"))
    demand = clean(row.get("positionDemand"))
    jd = "\n".join(x for x in (description, demand) if x)[:8000] or role
    batch = clean(config.get("batch")) or "2027校园招聘"
    template = clean(config.get("detail_url_template"))
    if template.startswith(("http://", "https://")) and "{id}" in template:
        apply_url = template.replace("{id}", quote(position_id, safe=""))
    else:
        apply_url = clean(config.get("start_url") or config.get("official_url"))
    updated = timestamp_text(row.get("releaseTime") or row.get("updateTime"))
    source_id = clean(config.get("id"))
    tags = ["企业官网/官方ATS", "官方公开API", batch]
    if "/job-info/" in apply_url:
        tags.append("官方职位详情")
    job = {
        "source": f"direct-official:browser:{source_id}",
        "source_label": f"{company}招聘官网 · 官方公开 API",
        "source_url": clean(config.get("official_url") or config.get("start_url")),
        "updated_at": updated,
        "company": company,
        "department": clean(row.get("departmentName")),
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": clean(config.get("company_type")),
        "industry": "",
        "graduation": "2027届" if "2027" in batch or "27届" in batch else "",
        "education": "",
        "notice_url": apply_url,
        "apply_url": apply_url,
        "jd": jd,
        "tags": tags,
        "observed_via": "official-public-api",
        "position_id": position_id,
    }
    job["id"] = stable_id(company, role, location, position_id)
    return job


def harvest_campus(config: dict[str, Any], session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    project = clean(config.get("api_project_code"))
    if not project:
        raise RuntimeError(f"{clean(config.get('id'))}: missing api_project_code")
    page_size = max(10, min(100, int(config.get("api_page_size") or DEFAULT_PAGE_SIZE)))
    client = session or requests.Session()
    client.headers.update({"User-Agent": "Mozilla/5.0 Path-to-Offer public recruitment collector"})
    jobs: dict[str, dict[str, Any]] = {}
    total = 0
    pages = 1
    pages_read = 0
    for page in range(1, MAX_PAGES + 1):
        response = client.post(
            CAMPUS_API,
            json={"recruitSubProjectCodes": [project], "pageSize": page_size, "pageNum": page},
            timeout=20,
        )
        result = response_result(response)
        rows = rows_from(result)
        pages_read += 1
        total = max(total, int(result.get("total") or 0))
        response_pages = int(result.get("pages") or 0)
        pages = max(pages, response_pages or math.ceil(total / page_size) or 1)
        for row in rows:
            job = normalize_job(config, row)
            if job:
                jobs[job["position_id"]] = job
        if page >= pages or not rows:
            break
    values = list(jobs.values())
    diagnostics = {
        "transport": "official-public-api",
        "endpoint": CAMPUS_API,
        "project_code": project,
        "reported_total": total,
        "page_size": page_size,
        "pages_reported": pages,
        "pages_read": pages_read,
        "unique_jobs": len(values),
        "complete": bool(total and len(values) == total),
    }
    if total and len(values) != total:
        raise RuntimeError(f"{clean(config.get('id'))}: expected {total} positions, collected {len(values)}")
    return values, diagnostics


def harvest(config: dict[str, Any], session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adapter = clean(config.get("adapter"))
    if adapter == "kuaishou-campus-api":
        return harvest_campus(config, session=session)
    raise RuntimeError(f"unsupported Kuaishou adapter: {adapter or '<empty>'}")
