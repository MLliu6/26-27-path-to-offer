#!/usr/bin/env python3
"""Recover OfferJack's public paginated job feed by replaying the request a browser receives.

This is a black-box public-surface adapter. It first visits https://www.offerjack.cn/ in a
normal headless browser, waits until the page itself requests a JSON response whose data
contains job records, then replays that same unauthenticated request template serially for
subsequent public pages. It does not guess private endpoints, authenticate, bypass CAPTCHA,
evade rate limits, or reuse privileged credentials.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import Request, Response, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, dedupe, stable_id, utc_now

URL = "https://www.offerjack.cn/"
MAX_RECORDS = int(os.getenv("PTO_MAX_PER_SOURCE", "20000"))
MAX_PAGES = int(os.getenv("PTO_OFFERJACK_API_MAX_PAGES", "1000"))
TARGET_PAGE_SIZE = int(os.getenv("PTO_OFFERJACK_PAGE_SIZE", "200"))
PAGE_KEYS = ("current", "page", "pageNum", "pageNo", "pageNumber")
SIZE_KEYS = ("size", "pageSize", "limit")
SENSITIVE_KEYS = ("authorization", "cookie", "token", "secret", "key")


@dataclass
class Template:
    method: str
    url: str
    post_data: str | None
    headers: dict[str, str]
    first_payload: dict[str, Any]


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def chrome_path() -> str | None:
    for candidate in (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def is_offer_payload(obj: Any) -> bool:
    try:
        records = obj["data"]["records"]
        return isinstance(records, list) and bool(records) and isinstance(records[0], dict) and {
            "enterpriseName",
            "position",
        }.issubset(records[0].keys())
    except Exception:
        return False


def safe_headers(request: Request) -> dict[str, str]:
    allowed = {"accept", "accept-language", "content-type", "referer", "origin", "user-agent"}
    out = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in allowed and not any(s in lower for s in SENSITIVE_KEYS):
            out[lower] = value
    return out


def normalize_link(value: Any) -> str:
    text = clean(value)
    return text if text.startswith(("http://", "https://")) else ""


def normalize_time(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    return text[:10] if len(text) >= 10 and text[4:5] == "-" else text


def map_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    company = clean(rec.get("enterpriseName"))
    role = clean(rec.get("position"))
    if not company or not role:
        return None
    location = clean(rec.get("workLocation"))
    notice = normalize_link(rec.get("announcementLink"))
    apply_url = normalize_link(rec.get("deliveryAddress"))
    updated = normalize_time(rec.get("updateTime") or rec.get("createTime"))
    job = {
        "source": "offerjack",
        "source_label": "OfferJack · 公开数据",
        "source_url": URL,
        "source_record_id": clean(rec.get("id")),
        "serial_number": clean(rec.get("serialNumber")),
        "updated_at": updated,
        "company": company,
        "department": "",
        "role": role,
        "location": location,
        "salary": "",
        "batch": clean(rec.get("recruitmentBatch")),
        "company_type": clean(rec.get("enterpriseNature")),
        "industry": clean(rec.get("industry")),
        "graduation": clean(rec.get("graduationYear")),
        "education": "",
        "deadline": normalize_time(rec.get("deadline")),
        "notice_url": notice,
        "apply_url": apply_url,
        "jd": role,
        "tags": [],
        "observed_via": "public-browser-api",
    }
    job["id"] = stable_id("offerjack", company, role, location, apply_url or notice or job["source_record_id"])
    return job


def parse_form(text: str | None) -> tuple[str, Any]:
    if not text:
        return "none", None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return "json", obj
    except Exception:
        pass
    pairs = parse_qsl(text, keep_blank_values=True)
    if pairs:
        return "form", dict(pairs)
    return "raw", text


def mutate_paging(template: Template, page: int, size: int | None = None) -> tuple[str, str | None, str]:
    """Return (url, body, body_kind), changing only observed pagination fields."""
    parsed = urlparse(template.url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_changed = False
    for key in PAGE_KEYS:
        if key in query:
            query[key] = str(page)
            query_changed = True
            break
    if size:
        for key in SIZE_KEYS:
            if key in query:
                query[key] = str(size)
                query_changed = True
                break
    url = urlunparse(parsed._replace(query=urlencode(query, doseq=True))) if query_changed else template.url

    kind, body = parse_form(template.post_data)
    if isinstance(body, dict):
        page_changed = False
        for key in PAGE_KEYS:
            if key in body:
                body[key] = page
                page_changed = True
                break
        if size:
            for key in SIZE_KEYS:
                if key in body:
                    body[key] = size
                    break
        if not query_changed and not page_changed:
            raise RuntimeError("observed request template has no recognizable public page parameter")
        if kind == "json":
            return url, json.dumps(body, ensure_ascii=False, separators=(",", ":")), kind
        if kind == "form":
            return url, urlencode(body), kind
    elif not query_changed:
        raise RuntimeError("observed request template has no replayable public pagination parameters")
    return url, template.post_data, kind


def page_metadata(payload: dict[str, Any]) -> dict[str, int]:
    data = payload.get("data") or {}
    def num(key: str, default: int = 0) -> int:
        try:
            return int(data.get(key) or default)
        except Exception:
            return default
    return {"total": num("total"), "size": num("size"), "current": num("current", 1), "pages": num("pages", 1)}


def write_status(*, ok: bool, count: int, diagnostics: dict[str, Any], error: str = "") -> None:
    status = load_json(STATUS_PATH, {"generated_at": None, "sources": []})
    entry = next((s for s in status.setdefault("sources", []) if s.get("name") == "offerjack"), None)
    payload = {
        "name": "offerjack",
        "label": "OfferJack · 公开页面/API",
        "url": URL,
        "ok": ok,
        "count": count,
        "error": error,
        "diagnostics": diagnostics,
    }
    if entry is None:
        status["sources"].append(payload)
    else:
        entry.clear(); entry.update(payload)
    status["generated_at"] = utc_now()
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    executable = chrome_path()
    if not executable:
        print("OfferJack API adapter skipped: Chrome not found")
        return 0

    template: Template | None = None
    diagnostics: dict[str, Any] = {"adapter": "observed-public-api", "renderer": Path(executable).name}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        def on_response(response: Response) -> None:
            nonlocal template
            if template is not None:
                return
            ctype = response.headers.get("content-type", "").lower()
            if response.request.resource_type not in {"xhr", "fetch"} or "json" not in ctype:
                return
            try:
                obj = response.json()
            except Exception:
                return
            if not is_offer_payload(obj):
                return
            req = response.request
            template = Template(
                method=req.method.upper(),
                url=req.url,
                post_data=req.post_data,
                headers=safe_headers(req),
                first_payload=obj,
            )

        page.on("response", on_response)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(8_000)
            if template is None:
                write_status(ok=False, count=0, error="public browser did not observe a replayable job-feed response", diagnostics=diagnostics)
                browser.close(); return 0

            meta = page_metadata(template.first_payload)
            diagnostics.update({
                "observed_path": urlparse(template.url).path,
                "method": template.method,
                "initial_total": meta["total"],
                "initial_size": meta["size"],
                "initial_pages": meta["pages"],
            })
            body_kind, body_obj = parse_form(template.post_data)
            diagnostics["request_body_kind"] = body_kind
            diagnostics["query_keys"] = sorted(dict(parse_qsl(urlparse(template.url).query, keep_blank_values=True)).keys())
            diagnostics["body_keys"] = sorted(body_obj.keys()) if isinstance(body_obj, dict) else []

            all_jobs = [j for rec in (template.first_payload.get("data", {}).get("records") or []) if isinstance(rec, dict) for j in [map_record(rec)] if j]

            # Try a larger page size only by mutating a pagination field that the public page already sent.
            effective_size = meta["size"] or 20
            first_payload = template.first_payload
            if TARGET_PAGE_SIZE > effective_size:
                try:
                    url, body, kind = mutate_paging(template, 1, TARGET_PAGE_SIZE)
                    kwargs: dict[str, Any] = {"method": template.method, "headers": template.headers, "timeout": 30_000}
                    if body is not None:
                        kwargs["data"] = body
                    replay = context.request.fetch(url, **kwargs)
                    if replay.status == 200:
                        candidate = replay.json()
                        if is_offer_payload(candidate) and page_metadata(candidate)["size"] >= effective_size:
                            first_payload = candidate
                            meta = page_metadata(candidate)
                            effective_size = meta["size"] or effective_size
                            all_jobs = [j for rec in (candidate.get("data", {}).get("records") or []) if isinstance(rec, dict) for j in [map_record(rec)] if j]
                except Exception as exc:
                    diagnostics["page_size_probe"] = f"{type(exc).__name__}: {clean(exc)[:160]}"

            diagnostics["effective_size"] = effective_size
            diagnostics["effective_pages"] = meta["pages"]
            pages_to_fetch = min(meta["pages"] or 1, MAX_PAGES)
            diagnostics["page_cap"] = MAX_PAGES

            for page_no in range(2, pages_to_fetch + 1):
                if len(all_jobs) >= MAX_RECORDS:
                    diagnostics["record_cap_reached"] = True
                    break
                try:
                    url, body, kind = mutate_paging(template, page_no, effective_size)
                    kwargs = {"method": template.method, "headers": template.headers, "timeout": 30_000}
                    if body is not None:
                        kwargs["data"] = body
                    replay = context.request.fetch(url, **kwargs)
                    if replay.status in {401, 403, 429}:
                        diagnostics["stopped_status"] = replay.status
                        break
                    if replay.status != 200:
                        diagnostics["stopped_status"] = replay.status
                        break
                    payload = replay.json()
                    if not is_offer_payload(payload):
                        diagnostics["stopped_reason"] = f"page {page_no} no longer matched public job schema"
                        break
                    records = payload.get("data", {}).get("records") or []
                    if not records:
                        break
                    all_jobs.extend(j for rec in records if isinstance(rec, dict) for j in [map_record(rec)] if j)
                    if page_no % 25 == 0:
                        time.sleep(0.35)
                    else:
                        time.sleep(0.06)
                except Exception as exc:
                    diagnostics["stopped_reason"] = f"page {page_no}: {type(exc).__name__}: {clean(exc)[:160]}"
                    break

            browser.close()
        except Exception as exc:
            try:
                browser.close()
            except Exception:
                pass
            write_status(ok=False, count=0, error=f"public API adapter failed: {type(exc).__name__}", diagnostics={**diagnostics, "detail": clean(exc)[:220]})
            return 0

    all_jobs = dedupe(all_jobs)[:MAX_RECORDS]
    diagnostics["records_collected"] = len(all_jobs)
    diagnostics["coverage_ratio"] = round(len(all_jobs) / meta["total"], 4) if meta["total"] else None

    feed = load_json(JOBS_PATH, {"schema_version": 1, "generated_at": None, "jobs": []})
    non_offerjack = [j for j in feed.get("jobs", []) if j.get("source") != "offerjack"]
    if all_jobs:
        merged = dedupe(non_offerjack + all_jobs)
        JOBS_PATH.write_text(json.dumps({"schema_version": 1, "generated_at": utc_now(), "jobs": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_status(ok=True, count=len(all_jobs), diagnostics=diagnostics)
        print(f"OfferJack observed public API: {len(all_jobs)}/{meta['total'] or '?'} records")
    else:
        write_status(ok=False, count=0, error="observed public API returned no normalized jobs", diagnostics=diagnostics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
