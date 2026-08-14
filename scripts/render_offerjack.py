#!/usr/bin/env python3
"""Rendered-browser fallback for OfferJack's public job surface.

This module observes the same public page and public browser responses a normal visitor
receives. It does not authenticate, bypass CAPTCHA/anti-bot controls, spoof a privileged
session, or call undiscovered private endpoints directly.

Strategy, in order:
1. Inspect public XHR/fetch JSON delivered to the page and normalize object-shaped jobs.
2. Recognize conservative table-shaped JSON payloads when rows clearly look like jobs.
3. Parse the rendered public HTML table.
4. Follow the public "next page" control serially when present to recover more than the
   first visible page. No parallel page hammering is used.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from playwright.sync_api import Page, Response, sync_playwright

from scripts.aggregate_jobs import (
    JOBS_PATH,
    STATUS_PATH,
    clean,
    dedupe,
    map_generic_job,
    parse_offerjack_tables,
    recursive_records,
    stable_id,
    utc_now,
)

URL = "https://www.offerjack.cn/"
MAX_JSON_RESPONSES = 80
MAX_RECORDS = int(os.getenv("PTO_MAX_PER_SOURCE", "20000"))
MAX_PUBLIC_PAGES = int(os.getenv("PTO_OFFERJACK_MAX_PAGES", "600"))
DATE_RE = re.compile(r"20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2})?")


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


def source_entry(status: dict[str, Any]) -> dict[str, Any] | None:
    return next((s for s in status.get("sources", []) if s.get("name") == "offerjack"), None)


def is_offerjack_sufficient(status: dict[str, Any]) -> bool:
    entry = source_entry(status)
    return bool(entry and entry.get("ok") and int(entry.get("count") or 0) >= 100)


def upsert_status(
    status: dict[str, Any], *, ok: bool, count: int, error: str = "", diagnostics: dict[str, Any] | None = None
) -> None:
    sources = status.setdefault("sources", [])
    entry = next((s for s in sources if s.get("name") == "offerjack"), None)
    payload = {
        "name": "offerjack",
        "label": "OfferJack · 公开页面",
        "url": URL,
        "ok": ok,
        "count": count,
        "error": error,
    }
    if diagnostics:
        payload["diagnostics"] = diagnostics
    if entry is None:
        sources.append(payload)
    else:
        entry.clear()
        entry.update(payload)
    status["generated_at"] = utc_now()


def looks_like_job(job: dict[str, Any]) -> bool:
    company = clean(job.get("company"))
    role = clean(job.get("role"))
    if not company or not role:
        return False
    header_markers = {"企业名称", "公司名称", "职位", "岗位", "工作地点", "招聘批次"}
    if company in header_markers or role in header_markers:
        return False
    if "企业名称" in company or "搜索点" in company:
        return False
    if role in {"职位", "招聘岗位"}:
        return False
    return True


def record_from_json(obj: Any, response_url: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for rec in recursive_records(obj):
        job = map_generic_job(rec, "offerjack", "OfferJack · 公开页面", URL)
        if not job or not looks_like_job(job):
            continue
        job["observed_via"] = "browser-json"
        job["observed_response_host"] = urlparse(response_url).netloc
        jobs.append(job)
        if len(jobs) >= MAX_RECORDS:
            break
    return jobs


def iter_lists(obj: Any) -> Iterable[list[Any]]:
    if isinstance(obj, list):
        yield obj
        for item in obj:
            yield from iter_lists(item)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from iter_lists(value)


def scalar_text(value: Any) -> str:
    if isinstance(value, (str, int, float)):
        return clean(value)
    if isinstance(value, dict):
        for key in ("text", "label", "name", "value", "title", "url", "href"):
            if key in value and isinstance(value[key], (str, int, float)):
                return clean(value[key])
    return ""


def record_from_tabular_json(obj: Any, response_url: str) -> list[dict[str, Any]]:
    """Conservatively recognize arrays matching the public table's visible column order.

    A row is accepted only when the first cell looks like a date, company and role are
    non-empty, and there are at least eight cells. This avoids interpreting unrelated
    analytics/config arrays as jobs.
    """
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in iter_lists(obj):
        if len(candidate) < 3 or not all(isinstance(row, (list, tuple)) for row in candidate[: min(3, len(candidate))]):
            continue
        for row in candidate:
            if not isinstance(row, (list, tuple)) or len(row) < 8:
                continue
            cells = [scalar_text(v) for v in row]
            if not DATE_RE.search(cells[0] or ""):
                continue
            company = cells[1] if len(cells) > 1 else ""
            role = cells[6] if len(cells) > 6 else ""
            if not company or not role or "企业名称" in company or role == "职位":
                continue
            job = {
                "source": "offerjack",
                "source_label": "OfferJack · 公开页面",
                "source_url": URL,
                "updated_at": cells[0],
                "company": company,
                "department": "",
                "role": role,
                "location": cells[5] if len(cells) > 5 else "",
                "salary": "",
                "batch": cells[2] if len(cells) > 2 else "",
                "company_type": cells[3] if len(cells) > 3 else "",
                "industry": cells[4] if len(cells) > 4 else "",
                "graduation": cells[7] if len(cells) > 7 else "",
                "education": "",
                "notice_url": cells[8] if len(cells) > 8 and str(cells[8]).startswith("http") else "",
                "apply_url": cells[9] if len(cells) > 9 and str(cells[9]).startswith("http") else "",
                "jd": role,
                "tags": [],
                "observed_via": "browser-json-table",
                "observed_response_host": urlparse(response_url).netloc,
            }
            job["id"] = stable_id("offerjack", company, role, job["location"], job["apply_url"] or job["notice_url"])
            if job["id"] not in seen and looks_like_job(job):
                seen.add(job["id"])
                jobs.append(job)
                if len(jobs) >= MAX_RECORDS:
                    return jobs
    return jobs


def json_shape(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        keys = [str(k) for k in list(obj.keys())[:30]]
        child = None
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                child = {"key": str(key), "shape": json_shape(value)}
                break
        return {"type": "object", "keys": keys, "first_container": child}
    if isinstance(obj, list):
        sample = obj[0] if obj else None
        return {"type": "array", "length": len(obj), "item": json_shape(sample) if sample is not None else None}
    return {"type": type(obj).__name__}


def clean_dom_jobs(html: str) -> list[dict[str, Any]]:
    jobs = []
    for job in parse_offerjack_tables(html, URL):
        if not looks_like_job(job):
            continue
        job["observed_via"] = "rendered-dom"
        jobs.append(job)
    return jobs


def find_next_locator(page: Page):
    selectors = [
        'button:has-text("下一页")',
        'a:has-text("下一页")',
        'button:has-text("下页")',
        'a:has-text("下页")',
        '[aria-label*="Next" i]',
        '[aria-label*="下一"]',
        '[title*="下一"]',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count():
            return locator.last
    return None


def locator_disabled(locator) -> bool:
    try:
        if locator.is_disabled():
            return True
    except Exception:
        pass
    try:
        disabled = locator.get_attribute("disabled")
        aria_disabled = locator.get_attribute("aria-disabled")
        klass = (locator.get_attribute("class") or "").lower()
        return disabled is not None or aria_disabled == "true" or "disabled" in klass
    except Exception:
        return False


def collect_public_pages(page: Page, diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_page_signatures: set[str] = set()
    pages = 0
    while pages < MAX_PUBLIC_PAGES and len(collected) < MAX_RECORDS:
        html = page.content()
        page_jobs = clean_dom_jobs(html)
        signature = "|".join(j.get("id", "") for j in page_jobs[:3]) or clean(page.locator("body").inner_text()[:500])
        if signature in seen_page_signatures:
            break
        seen_page_signatures.add(signature)
        collected.extend(page_jobs)
        pages += 1

        nxt = find_next_locator(page)
        if nxt is None or locator_disabled(nxt):
            break
        before = signature
        try:
            nxt.scroll_into_view_if_needed(timeout=2_000)
            nxt.click(timeout=4_000)
            page.wait_for_timeout(450)
            # Give server-side grids a little more time, but do not loop on a frozen page.
            for _ in range(5):
                new_jobs = clean_dom_jobs(page.content())
                after = "|".join(j.get("id", "") for j in new_jobs[:3])
                if after and after != before:
                    break
                page.wait_for_timeout(250)
            else:
                break
        except Exception as exc:
            diagnostics["pagination_stop"] = f"{type(exc).__name__}: {clean(exc)[:160]}"
            break

    diagnostics["dom_pages_collected"] = pages
    diagnostics["dom_records_before_dedupe"] = len(collected)
    diagnostics["pagination_cap"] = MAX_PUBLIC_PAGES
    return collected


def main() -> int:
    status = load_json(STATUS_PATH, {"generated_at": None, "sources": []})
    if is_offerjack_sufficient(status):
        print("OfferJack lightweight adapter already returned a substantial feed; rendered fallback skipped.")
        return 0

    executable = chrome_path()
    if not executable:
        upsert_status(status, ok=False, count=0, error="render fallback unavailable: Chrome not found on runner")
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    observed_jobs: list[dict[str, Any]] = []
    response_urls: list[str] = []
    response_errors: list[str] = []
    response_shapes: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {"renderer": Path(executable).name}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=executable,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            locale="zh-CN",
            viewport={"width": 1440, "height": 1000},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/150 Safari/537.36 PathToOfferBrowser/0.2",
        )
        page = context.new_page()

        def on_response(response: Response) -> None:
            if len(response_urls) >= MAX_JSON_RESPONSES:
                return
            req_type = response.request.resource_type
            ctype = response.headers.get("content-type", "").lower()
            if req_type not in {"xhr", "fetch"} or "json" not in ctype:
                return
            response_urls.append(response.url)
            try:
                obj = response.json()
                observed_jobs.extend(record_from_json(obj, response.url))
                observed_jobs.extend(record_from_tabular_json(obj, response.url))
                if len(response_shapes) < 12:
                    parsed = urlparse(response.url)
                    response_shapes.append({"path": parsed.path, "shape": json_shape(obj)})
            except Exception as exc:
                if len(response_errors) < 8:
                    response_errors.append(f"{urlparse(response.url).path}: {type(exc).__name__}")

        page.on("response", on_response)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(8_000)
            diagnostics["title"] = clean(page.title())[:160]
            diagnostics["table_count"] = page.locator("table").count()
            diagnostics["body_chars"] = len(page.locator("body").inner_text(timeout=10_000))
            diagnostics["json_responses"] = len(response_urls)
            diagnostics["json_response_hosts"] = sorted({urlparse(u).netloc for u in response_urls})[:12]
            diagnostics["json_shapes"] = response_shapes
            if response_errors:
                diagnostics["json_parse_notes"] = response_errors[:8]

            if len(observed_jobs) < MAX_RECORDS:
                observed_jobs.extend(collect_public_pages(page, diagnostics))

            body_prefix = page.locator("body").inner_text(timeout=10_000)[:2200]
            if not observed_jobs and any(x in body_prefix.lower() for x in ["captcha", "验证码", "请登录后"]):
                diagnostics["gate"] = "login-or-captcha"
        except Exception as exc:
            diagnostics["navigation_error"] = f"{type(exc).__name__}: {clean(exc)[:220]}"
        finally:
            browser.close()

    observed_jobs = [j for j in dedupe([j for j in observed_jobs if looks_like_job(j)]) if looks_like_job(j)][:MAX_RECORDS]
    feed = load_json(JOBS_PATH, {"schema_version": 1, "generated_at": None, "jobs": []})
    existing = [j for j in feed.get("jobs", []) if j.get("source") != "offerjack"]

    if observed_jobs:
        merged = dedupe(existing + observed_jobs)
        feed = {"schema_version": 1, "generated_at": utc_now(), "jobs": merged}
        JOBS_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        upsert_status(status, ok=True, count=len(observed_jobs), diagnostics=diagnostics)
        print(f"OfferJack rendered fallback recovered {len(observed_jobs)} jobs")
    else:
        error = "rendered public page produced no compatible job records"
        if response_errors:
            error += "; JSON parse notes: " + ", ".join(response_errors[:4])
        upsert_status(status, ok=False, count=0, error=error, diagnostics=diagnostics)
        print(error)

    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
