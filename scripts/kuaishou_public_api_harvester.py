#!/usr/bin/env python3
"""Harvest Kuaishou public recruiting catalogues without authentication.

Campus projects expose a stable anonymous JSON API and use direct HTTP pagination.
Experienced/social and daily-intern pages require the employer's own public SPA to
initiate the same anonymous XHR, so those catalogues are paged by changing the
public hash route inside one real Chrome context and observing the SPA responses.
No applicant API, login, CAPTCHA bypass, private cookie export or request-signature
reproduction is used.
"""
from __future__ import annotations

import math
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from scripts.aggregate_jobs import clean, stable_id

CAMPUS_API = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
EXPERIENCED_API_MARKER = "/recruit/e/api/v1/open/positions/simple"
DEFAULT_PAGE_SIZE = 50
MAX_PAGES = 80
MAX_EXPERIENCED_PAGES = max(20, min(220, int(os.getenv("PTO_KUAISHOU_MAX_PAGES", "180"))))
EXPERIENCED_PAGE_TIMEOUT_MS = max(4_000, min(20_000, int(os.getenv("PTO_KUAISHOU_PAGE_TIMEOUT_MS", "9000"))))
CITY_MAP = {
    "beijing": "北京", "Beijing": "北京",
    "shanghai": "上海", "Shanghai": "上海",
    "Guangzhou": "广州", "guangzhou": "广州",
    "Shenzhen": "深圳", "shenzhen": "深圳",
    "Hangzhou": "杭州", "hangzhou": "杭州",
    "suzhou": "苏州", "Suzhou": "苏州",
    "Wuhan": "武汉", "wuhan": "武汉",
    "Chengdu": "成都", "chengdu": "成都",
    "Tianjin": "天津", "tianjin": "天津",
    "Nanjing": "南京", "nanjing": "南京",
    "XiAn": "西安", "xian": "西安", "Xian": "西安",
    "Chongqing": "重庆", "chongqing": "重庆",
    "Shenyang": "沈阳", "shenyang": "沈阳",
    "Yantai": "烟台", "yantai": "烟台",
    "huaian": "淮安", "HuaiAn": "淮安",
    "chengmai": "澄迈", "Chengmai": "澄迈",
    "tongren": "铜仁", "Tongren": "铜仁",
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
            code = part.strip()
            name = CITY_MAP.get(code, CITY_MAP.get(code.lower(), code))
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


def normalize_job(config: dict[str, Any], row: dict[str, Any], *, transport: str = "official-public-api") -> dict[str, Any] | None:
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
    public_api = transport == "official-public-api"
    tags = ["企业官网/官方ATS", "官方公开API" if public_api else "真实浏览器公开XHR", batch]
    if "/job-info/" in apply_url:
        tags.append("官方职位详情")
    job = {
        "source": f"direct-official:browser:{source_id}",
        "source_label": f"{company}招聘官网 · {'官方公开 API' if public_api else '真实浏览器公开 XHR'}",
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
        "observed_via": transport,
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
        "coverage_ratio": 1.0 if total and len(values) == total else (len(values) / total if total else 0.0),
    }
    if total and len(values) != total:
        raise RuntimeError(f"{clean(config.get('id'))}: expected {total} positions, collected {len(values)}")
    return values, diagnostics


def chrome_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable for Kuaishou public SPA")


def experienced_payload(response, *, nature: str, page_num: int, unfiltered: bool = True) -> dict[str, Any] | None:
    if EXPERIENCED_API_MARKER not in response.url or f"positionNatureCode={nature}" not in response.url:
        return None
    if unfiltered and "workLocationCode=" in response.url:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    result = payload.get("result") if isinstance(payload, dict) else None
    if payload.get("code") not in (0, "0", 200, "200") or not isinstance(result, dict):
        return None
    if int(result.get("pageNum") or 0) != page_num:
        return None
    return result


def experienced_hash(route_fragment: str, page_num: int) -> str:
    fragment = "/" + route_fragment.strip("/") + "/"
    return f"{fragment}?pageNum={int(page_num)}"


def _load_experienced_page(page, config: dict[str, Any], page_num: int, *, initial: bool = False) -> dict[str, Any]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    nature = clean(config.get("position_nature_code"))
    route_fragment = clean(config.get("route_fragment"))
    start_url = clean(config.get("start_url"))
    if not nature or not route_fragment or not start_url:
        raise RuntimeError(f"{clean(config.get('id'))}: incomplete experienced-browser config")

    def predicate(response):
        return experienced_payload(response, nature=nature, page_num=page_num) is not None

    def attempt(full_reload: bool):
        with page.expect_response(predicate, timeout=EXPERIENCED_PAGE_TIMEOUT_MS) as info:
            if full_reload:
                base = start_url.split("#", 1)[0]
                target = f"{base}#{experienced_hash(route_fragment, page_num)}"
                page.goto(target, wait_until="domcontentloaded", timeout=30_000)
            else:
                target_hash = experienced_hash(route_fragment, page_num)
                page.evaluate("value => { location.hash = value; }", target_hash)
        result = experienced_payload(info.value, nature=nature, page_num=page_num)
        if result is None:
            raise RuntimeError(f"{clean(config.get('id'))}: invalid public XHR page {page_num}")
        return result

    try:
        return attempt(initial)
    except PlaywrightTimeoutError:
        # A full public-page reload is a safe fallback if a hash transition was
        # coalesced by the SPA or a single XHR was lost. No request is forged.
        return attempt(True)


def harvest_experienced_browser(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    started = time.monotonic()
    nature = clean(config.get("position_nature_code"))
    if nature not in {"C001", "C002"}:
        raise RuntimeError(f"{clean(config.get('id'))}: unsupported position_nature_code={nature!r}")
    jobs: dict[str, dict[str, Any]] = {}
    totals_seen: list[int] = []
    pages_seen: list[int] = []
    page_size_seen: list[int] = []
    pages_read = 0
    boundary_duplicates = 0
    previous_ids: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=chrome_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 820}, locale="zh-CN")
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "media", "font"} else route.continue_())
        try:
            result = _load_experienced_page(page, config, 1, initial=True)
            total = int(result.get("total") or 0)
            pages = int(result.get("pages") or 0)
            page_size = int(result.get("pageSize") or 10) or 10
            if total < 1 or pages < 1:
                raise RuntimeError(f"{clean(config.get('id'))}: empty/invalid public catalogue metadata")
            if pages > MAX_EXPERIENCED_PAGES:
                raise RuntimeError(f"{clean(config.get('id'))}: {pages} pages exceed safe cap {MAX_EXPERIENCED_PAGES}")

            for page_num in range(1, pages + 1):
                current = result if page_num == 1 else _load_experienced_page(page, config, page_num)
                pages_read += 1
                rows = rows_from(current)
                current_ids = {clean(row.get("id") or row.get("code")) for row in rows if clean(row.get("id") or row.get("code"))}
                if previous_ids and (previous_ids & current_ids):
                    boundary_duplicates += len(previous_ids & current_ids)
                previous_ids = current_ids
                totals_seen.append(int(current.get("total") or 0))
                pages_seen.append(int(current.get("pages") or 0))
                page_size_seen.append(int(current.get("pageSize") or page_size) or page_size)
                for row in rows:
                    job = normalize_job(config, row, transport="official-browser-ui-xhr")
                    if job:
                        jobs[job["position_id"]] = job

            # The catalogue is live and new roles are inserted near the front.
            # Re-read page 1 once so a role posted during the sweep is not lost
            # because the subsequent pages shifted by one position.
            refreshed_first = _load_experienced_page(page, config, 1)
            totals_seen.append(int(refreshed_first.get("total") or 0))
            for row in rows_from(refreshed_first):
                job = normalize_job(config, row, transport="official-browser-ui-xhr")
                if job:
                    jobs[job["position_id"]] = job
        finally:
            context.close()
            browser.close()

    values = list(jobs.values())
    reported_start = totals_seen[0] if totals_seen else 0
    reported_end = totals_seen[-1] if totals_seen else reported_start
    reported_max = max(totals_seen) if totals_seen else 0
    reported_min = min(x for x in totals_seen if x > 0) if any(x > 0 for x in totals_seen) else 0
    denominator = reported_max or reported_end or reported_start
    coverage_ratio = len(values) / denominator if denominator else 0.0
    dynamic_delta = reported_max - reported_min if reported_min else 0
    # Exact equality is expected for a stable catalogue. For a live catalogue,
    # a tiny over/under count can occur when jobs are opened/closed mid-sweep;
    # 99.5% is the fail-closed threshold and diagnostics expose the delta.
    complete = bool(denominator and coverage_ratio >= 0.995)
    diagnostics = {
        "transport": "browser-ui-navigation+xhr-observation",
        "endpoint_marker": EXPERIENCED_API_MARKER,
        "position_nature_code": nature,
        "route_fragment": clean(config.get("route_fragment")),
        "reported_total_start": reported_start,
        "reported_total_end": reported_end,
        "reported_total_max": reported_max,
        "reported_total_min": reported_min,
        "reported_total": reported_end,
        "dynamic_total_delta": dynamic_delta,
        "page_size": max(page_size_seen) if page_size_seen else 10,
        "pages_reported": max(pages_seen) if pages_seen else 0,
        "pages_read": pages_read,
        "unique_jobs": len(values),
        "boundary_duplicates": boundary_duplicates,
        "coverage_ratio": round(coverage_ratio, 6),
        "complete": complete,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "cookie_values_exported": False,
        "request_signature_reproduced": False,
    }
    if not complete:
        raise RuntimeError(
            f"{clean(config.get('id'))}: live catalogue coverage {len(values)}/{denominator}="
            f"{coverage_ratio:.4f} below 0.995"
        )
    return values, diagnostics


def harvest(config: dict[str, Any], session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adapter = clean(config.get("adapter"))
    if adapter == "kuaishou-campus-api":
        return harvest_campus(config, session=session)
    if adapter == "kuaishou-experienced-browser":
        return harvest_experienced_browser(config)
    raise RuntimeError(f"unsupported Kuaishou adapter: {adapter or '<empty>'}")
