#!/usr/bin/env python3
"""DiDi browser-UI fallback collector.

GitHub-hosted runners sometimes receive an interception payload when the DiDi
JSON endpoint is called directly, while the employer's public React UI obtains
the same anonymous list successfully. This module therefore drives the public
recruiting UI itself and records the list responses produced by normal page
navigation. It does not log in, replay user cookies, solve CAPTCHA, spoof a
private API credential, rotate proxies, or bypass access controls.

The collector enumerates every visible page for social, campus, internship and
overseas scopes. List rows are sufficient to make positions searchable and to
retain the employer-owned application URL; richer detail can be supplied by the
normal direct adapter whenever its detail transport is available.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, utc_now
from scripts.didi_official_harvester import (
    BASE,
    LIST_ENDPOINT,
    SCOPES,
    merge_catalog,
    normalize,
)

MAX_PAGES = max(2, min(120, int(os.getenv("PTO_DIDI_BROWSER_MAX_PAGES", "80"))))
NAV_TIMEOUT = max(8_000, min(45_000, int(os.getenv("PTO_DIDI_BROWSER_TIMEOUT_MS", "22000"))))


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable for DiDi UI collector")


def list_response_matches(url: str, scope_code: str) -> bool:
    return LIST_ENDPOINT in url and f"recruitType={scope_code}" in url


def payload_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    meta = payload.get("meta") or {}
    if isinstance(meta, dict) and meta.get("code") not in (None, 0, "0"):
        raise RuntimeError(clean(meta.get("message")) or f"DiDi upstream code {meta.get('code')}")
    data = payload.get("data") or {}
    rows = data.get("items") or data.get("list") or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def response_payload(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"DiDi UI list response is not JSON: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("DiDi UI list response is not an object")
    return payload


def route_for(scope: dict[str, str], page_no: int) -> str:
    return f"{BASE}/{scope['slug']}/list/{page_no}"


def navigate_for_list(page: Page, scope: dict[str, str], page_no: int) -> tuple[list[dict[str, Any]], str]:
    code = scope["code"]
    target = route_for(scope, page_no)
    try:
        with page.expect_response(lambda response: list_response_matches(response.url, code), timeout=NAV_TIMEOUT) as pending:
            page.goto(target, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        response = pending.value
        return payload_rows(response_payload(response)), page.url
    except PlaywrightTimeoutError:
        if page_no != 1:
            raise

    # Some deployments expose the scope only through the navigation on the root
    # page. Fall back to a normal user click for page 1, then use the resolved
    # route for later pages.
    page.goto(BASE, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    page.wait_for_timeout(500)
    candidates = page.get_by_text(scope["label"], exact=True)
    if candidates.count() == 0:
        raise RuntimeError(f"DiDi public UI did not expose navigation label {scope['label']}")
    with page.expect_response(lambda response: list_response_matches(response.url, code), timeout=NAV_TIMEOUT) as pending:
        candidates.first.click()
    response = pending.value
    return payload_rows(response_payload(response)), page.url


def collect_scope(page: Page, scope: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    page_signatures: set[tuple[str, ...]] = set()
    sizes: list[int] = []
    errors: list[str] = []
    resolved_routes: list[str] = []

    for page_no in range(1, MAX_PAGES + 1):
        try:
            rows, resolved = navigate_for_list(page, scope, page_no)
        except PlaywrightTimeoutError:
            errors.append(f"timeout page={page_no}")
            break
        except Exception as exc:
            if page_no == 1:
                raise
            errors.append(f"page={page_no}: {type(exc).__name__}: {clean(exc)[:180]}")
            break
        resolved_routes.append(resolved)
        if not rows:
            break
        ids = tuple(clean(row.get("jdId") or row.get("id") or row.get("jdNo")) for row in rows)
        if ids and ids in page_signatures:
            errors.append(f"repeated page signature at page={page_no}")
            break
        if ids:
            page_signatures.add(ids)
        sizes.append(len(rows))
        new_count = 0
        for raw in rows:
            jd_id = clean(raw.get("jdId") or raw.get("id"))
            role = clean(raw.get("jobName") or raw.get("title"))
            if not jd_id or not role:
                continue
            item = dict(raw)
            item["_scope"] = scope
            job = normalize(item)
            if job:
                if jd_id not in jobs:
                    new_count += 1
                jobs[jd_id] = job
        if not new_count:
            errors.append(f"page={page_no}: no new jobs")
            break
        # The public UI currently uses 16 rows per page. A shorter page is the
        # normal final page and does not depend on the unreliable `total` field.
        if len(rows) < 16:
            break

    return list(jobs.values()), {
        "scope": scope["label"],
        "code": scope["code"],
        "pages": len(sizes),
        "unique": len(jobs),
        "observed_page_sizes": sizes,
        "resolved_routes": resolved_routes[:4],
        "errors": errors[:10],
    }


def collect_didi_via_ui() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_jobs: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=browser_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1365, "height": 900}, locale="zh-CN")
        page = context.new_page()
        try:
            for scope in SCOPES:
                try:
                    rows, diag = collect_scope(page, scope)
                    diagnostics.append(diag)
                    for job in rows:
                        all_jobs[clean(job.get("position_id"))] = job
                except Exception as exc:
                    diagnostics.append({
                        "scope": scope["label"],
                        "code": scope["code"],
                        "pages": 0,
                        "unique": 0,
                        "errors": [f"{type(exc).__name__}: {clean(exc)[:220]}"],
                    })
        finally:
            context.close()
            browser.close()

    if not all_jobs:
        raise RuntimeError(f"DiDi public UI yielded zero jobs: {diagnostics}")
    batches: dict[str, int] = {}
    for job in all_jobs.values():
        batch = clean(job.get("batch")) or "未分类"
        batches[batch] = batches.get(batch, 0) + 1
    return list(all_jobs.values()), {
        "transport": "browser-ui-navigation",
        "official_url": BASE,
        "list_endpoint_observed": LIST_ENDPOINT,
        "unique_jobs": len(all_jobs),
        "batches": sorted(batches.items(), key=lambda item: (-item[1], item[0])),
        "scopes": diagnostics,
    }


def main() -> int:
    jobs, diagnostics = collect_didi_via_ui()
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("didi_browser_ui_harvester.py must run before compact_feed.py")
    merged = merge_catalog(existing if isinstance(existing, list) else [], jobs)
    output = dict(payload) if isinstance(payload, dict) else {}
    output.update({"schema_version": 3, "generated_at": utc_now(), "jobs": merged})
    JOBS_PATH.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "didi-direct-official",
        "label": "滴滴招聘官网 · 浏览器自主直连",
        "url": BASE,
        "ok": True,
        "count": len(jobs),
        "error": "",
        "diagnostics": diagnostics,
    }
    sources = [source for source in status.get("sources", []) if not isinstance(source, dict) or source.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(merged), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"didi_browser_jobs": len(jobs), "batches": diagnostics["batches"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
