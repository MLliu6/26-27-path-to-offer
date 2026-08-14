#!/usr/bin/env python3
"""Rendered-browser fallback for OfferJack's public job surface.

This runs only when the requests-based adapter could not recover jobs. It observes the
same public page and public network responses a normal browser receives; it does not
authenticate, bypass CAPTCHA/anti-bot controls, spoof sessions, or call undiscovered
private endpoints directly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Response, sync_playwright

from scripts.aggregate_jobs import (
    JOBS_PATH,
    STATUS_PATH,
    clean,
    dedupe,
    map_generic_job,
    parse_offerjack_tables,
    recursive_records,
    utc_now,
)

URL = "https://www.offerjack.cn/"
MAX_JSON_RESPONSES = 40
MAX_RECORDS = int(os.getenv("PTO_MAX_PER_SOURCE", "20000"))


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


def is_offerjack_ok(status: dict[str, Any]) -> bool:
    return any(s.get("name") == "offerjack" and s.get("ok") for s in status.get("sources", []))


def upsert_status(status: dict[str, Any], *, ok: bool, count: int, error: str = "", diagnostics: dict[str, Any] | None = None) -> None:
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
        entry.clear(); entry.update(payload)
    status["generated_at"] = utc_now()


def record_from_json(obj: Any, response_url: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for rec in recursive_records(obj):
        job = map_generic_job(rec, "offerjack", "OfferJack · 公开页面", URL)
        if not job:
            continue
        # Preserve the observed public response as provenance without teaching the
        # crawler to call that endpoint outside the browser session.
        job["observed_via"] = "browser-json"
        job["observed_response_host"] = urlparse(response_url).netloc
        jobs.append(job)
        if len(jobs) >= MAX_RECORDS:
            break
    return jobs


def main() -> int:
    status = load_json(STATUS_PATH, {"generated_at": None, "sources": []})
    if is_offerjack_ok(status):
        print("OfferJack static adapter already succeeded; rendered fallback skipped.")
        return 0

    executable = chrome_path()
    if not executable:
        upsert_status(status, ok=False, count=0, error="render fallback unavailable: Chrome not found on runner")
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    observed_jobs: list[dict[str, Any]] = []
    response_urls: list[str] = []
    response_errors: list[str] = []
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
            except Exception as exc:
                if len(response_errors) < 8:
                    response_errors.append(f"{urlparse(response.url).netloc}: {type(exc).__name__}")

        page.on("response", on_response)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(8_000)
            diagnostics["title"] = clean(page.title())[:160]
            diagnostics["table_count"] = page.locator("table").count()
            diagnostics["body_chars"] = len(page.locator("body").inner_text(timeout=10_000))
            diagnostics["json_responses"] = len(response_urls)
            diagnostics["json_response_hosts"] = sorted({urlparse(u).netloc for u in response_urls})[:12]
            html = page.content()
            if len(observed_jobs) < MAX_RECORDS:
                dom_jobs = parse_offerjack_tables(html, URL)
                for job in dom_jobs:
                    job["observed_via"] = "rendered-dom"
                observed_jobs.extend(dom_jobs)
            # A public login/CAPTCHA gate is a stop condition, not something to evade.
            body_prefix = page.locator("body").inner_text(timeout=10_000)[:2200]
            if not observed_jobs and any(x in body_prefix.lower() for x in ["captcha", "验证码", "请登录后"]):
                diagnostics["gate"] = "login-or-captcha"
        except Exception as exc:
            diagnostics["navigation_error"] = f"{type(exc).__name__}: {clean(exc)[:220]}"
        finally:
            browser.close()

    observed_jobs = dedupe(observed_jobs)[:MAX_RECORDS]
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
