#!/usr/bin/env python3
"""Collect priority campus records through Gank Interview's public search UI.

This adapter deliberately behaves like a normal anonymous browser user:
- load the public campus page;
- type a configured query into the page's visible search box;
- submit through Enter / the visible Search button;
- parse only the public table rendered back to the browser.

It does NOT call private endpoints, carry authentication, reveal gated announcement/apply
links, bypass CAPTCHA/rate limits, or mutate hidden request parameters. The configured
queries are finite and the adapter sleeps between them. Existing catalog data is retained
when the page changes or an individual query yields no public row.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, utc_now
from scripts.merge_public_tables import merge_catalog, parse_table_source

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "sources" / "gank_priority_queries.json"
DEFAULT_URL = "https://www.gankinterview.cn/campus"


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def chrome_path() -> str | None:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    for candidate in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if Path(candidate).exists():
            return candidate
    return None


def locate_search(page: Page):
    candidates = [
        'input[placeholder*="搜索公司"]',
        'input[placeholder*="岗位"]',
        'input[placeholder*="公司"]',
        'input[placeholder*="Search company"]',
        'input[placeholder*="company"]',
        'input[placeholder*="role"]',
    ]
    for selector in candidates:
        loc = page.locator(selector)
        if loc.count() and loc.first.is_visible():
            return loc.first
    # Last-resort visible text input whose placeholder describes more than one search field.
    for i in range(page.locator('input[type="text"], input:not([type])').count()):
        loc = page.locator('input[type="text"], input:not([type])').nth(i)
        try:
            placeholder = (loc.get_attribute("placeholder") or "").lower()
            if loc.is_visible() and any(k in placeholder for k in ("公司", "岗位", "company", "role")):
                return loc
        except Exception:
            continue
    return None


def click_search_if_present(page: Page) -> bool:
    for label in ("搜索", "Search"):
        loc = page.get_by_role("button", name=label, exact=False)
        if loc.count() and loc.first.is_visible():
            loc.first.click()
            return True
    return False


def query_matches(job: dict[str, Any], query: str) -> bool:
    q = clean(query).lower()
    if not q:
        return False
    hay = " ".join(
        clean(job.get(k)).lower()
        for k in ("company", "role", "location", "industry", "graduation", "batch", "jd")
    )
    aliases = {
        "jd": ("京东", "jd"),
        "京东": ("京东", "jd"),
        "阿里": ("阿里", "alibaba", "淘天", "阿里云"),
        "字节跳动": ("字节", "bytedance", "tiktok"),
        "腾讯": ("腾讯", "tencent"),
    }
    terms = aliases.get(q, (q,))
    return any(term.lower() in hay for term in terms)


def run_query(page: Page, base_url: str, query: str, delay_ms: int) -> list[dict[str, Any]]:
    search = locate_search(page)
    if search is None:
        raise RuntimeError("public campus search input not found")
    search.fill(query)
    search.press("Enter")
    page.wait_for_timeout(delay_ms)

    jobs = parse_table_source(
        page.content(),
        name="gank-public-search",
        label="Gank Interview · 公开搜索",
        url=base_url,
    )
    matched = [j for j in jobs if query_matches(j, query)]
    if matched:
        return matched

    # Some page versions use a visible button rather than submit-on-enter.
    if click_search_if_present(page):
        page.wait_for_timeout(delay_ms)
        jobs = parse_table_source(
            page.content(),
            name="gank-public-search",
            label="Gank Interview · 公开搜索",
            url=base_url,
        )
        matched = [j for j in jobs if query_matches(j, query)]
    return matched


def write_status(status: dict[str, Any], *, ok: bool, count: int, diagnostics: dict[str, Any], error: str = "") -> None:
    sources = [s for s in status.get("sources", []) if isinstance(s, dict) and s.get("name") != "gank-public-search"]
    sources.append({
        "name": "gank-public-search",
        "label": "Gank Interview · 公开搜索",
        "url": DEFAULT_URL,
        "ok": ok,
        "count": count,
        "error": error,
        "diagnostics": diagnostics,
    })
    status["sources"] = sources
    status["generated_at"] = utc_now()


def main() -> int:
    config = load_json(CONFIG, {})
    queries = [clean(q) for q in config.get("queries", []) if clean(q)]
    base_url = clean(config.get("source")) or DEFAULT_URL
    delay_ms = max(400, min(3000, int(config.get("delay_ms", 700))))
    feed = load_json(JOBS_PATH, {"schema_version": 2, "jobs": []})
    status = load_json(STATUS_PATH, {"generated_at": None, "sources": []})
    existing = feed.get("jobs", []) if isinstance(feed, dict) else []
    executable = chrome_path()
    diagnostics: dict[str, Any] = {"mode": "visible-public-search-ui", "queries_configured": len(queries), "query_counts": {}}

    if not executable:
        write_status(status, ok=False, count=0, diagnostics=diagnostics, error="Chrome/Chromium not available")
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Gank public search skipped: browser not available")
        return 0

    collected: list[dict[str, Any]] = []
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1800)
            if "/auth/" in page.url or "login" in page.url.lower():
                raise RuntimeError("public campus page redirected to authentication; no bypass attempted")
            if locate_search(page) is None:
                raise RuntimeError("public campus page loaded but search input was not available")
            diagnostics["resolved_url"] = page.url
            for query in queries:
                try:
                    rows = run_query(page, base_url, query, delay_ms)
                    diagnostics["query_counts"][query] = len(rows)
                    for row in rows:
                        row["discovery_query"] = query
                    collected.extend(rows)
                except Exception as exc:
                    failures.append(f"{query}: {type(exc).__name__}: {clean(exc)[:100]}")
                    diagnostics["query_counts"][query] = -1
                    # If a search unexpectedly navigated away, return to the public page before continuing.
                    try:
                        page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
                        page.wait_for_timeout(1000)
                    except Exception:
                        break
        except Exception as exc:
            failures.append(f"setup: {type(exc).__name__}: {clean(exc)[:180]}")
        finally:
            browser.close()

    merged = merge_catalog([*(existing if isinstance(existing, list) else []), *collected])
    now = utc_now()
    merged.sort(key=lambda j: (clean(j.get("updated_at")), clean(j.get("company")), clean(j.get("role"))), reverse=True)
    JOBS_PATH.write_text(json.dumps({"schema_version": 2, "generated_at": now, "jobs": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    diagnostics["browser"] = Path(executable).name
    diagnostics["records_this_run"] = len(collected)
    diagnostics["unique_catalog_total"] = len(merged)
    diagnostics["failed_queries"] = failures[:12]
    ok = bool(collected)
    error = "" if ok else (failures[0] if failures else "public search returned no matching rows")
    write_status(status, ok=ok, count=len(collected), diagnostics=diagnostics, error=error)
    status["catalog_count"] = len(merged)
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Gank public search: collected={len(collected)} unique_total={len(merged)} failures={len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
