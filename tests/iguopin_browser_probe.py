#!/usr/bin/env python3
"""Live browser probe for public IGuopin employer recruiting tenants.

The test deliberately observes only requests emitted by anonymous public career
pages. It is a PR acceptance probe, not a scraper: the output records enough
request/response shape to keep the production adapter tenant-scoped instead of
mistakenly assigning a national IGuopin feed to one SOE.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_browser_sources.json"
DEFAULT_IDS = "spacechina-iguopin,cssc-iguopin,cetc-iguopin,chng-iguopin"


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def rows_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    value = payload.get("data", payload)
    if isinstance(value, dict):
        for key in ("list", "rows", "items", "jobs", "results"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        nested = value.get("data")
        if isinstance(nested, dict):
            return rows_from_payload({"data": nested})
    return []


def safe_headers(request) -> dict[str, str]:
    try:
        headers = request.all_headers()
    except Exception:
        headers = getattr(request, "headers", {}) or {}
    keep = {}
    for key, value in headers.items():
        lower = str(key).lower()
        if lower in {"subsite", "device", "version", "content-type", "origin", "referer"}:
            keep[lower] = str(value)
    return keep


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    all_iguopin = [row for row in registry.get("sources", []) if isinstance(row, dict) and row.get("family") == "iguopin"]
    assert len(all_iguopin) >= 8, f"expected broad IGuopin registry, got {len(all_iguopin)}"
    by_id = {row.get("id"): row for row in all_iguopin}
    assert "spacechina-iguopin" in by_id
    selected_ids = [x.strip() for x in os.getenv("PTO_IGUOPIN_PROBE_IDS", DEFAULT_IDS).split(",") if x.strip()]
    selected = [by_id[x] for x in selected_ids if x in by_id]
    assert selected, selected_ids

    summaries = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1365, "height": 900}, locale="zh-CN")
        try:
            for entry in selected:
                page = context.new_page()
                observed = []

                def on_response(response):
                    try:
                        parsed = urlparse(response.url)
                        if (parsed.hostname or "").lower() != "gp-api.iguopin.com":
                            return
                        if "/api/jobs/" not in parsed.path:
                            return
                        payload = response.json()
                        rows = rows_from_payload(payload)
                        samples = []
                        for row in rows[:4]:
                            samples.append({
                                "job_id": row.get("job_id") or row.get("jobId") or row.get("id"),
                                "job_name": row.get("job_name") or row.get("jobName") or row.get("name") or row.get("title"),
                                "company_name": row.get("company_name") or row.get("companyName") or row.get("company"),
                                "education": row.get("education_cn") or row.get("education"),
                                "district_list": row.get("district_list") or row.get("districtList"),
                            })
                        observed.append({
                            "url": response.url,
                            "status": response.status,
                            "method": response.request.method,
                            "headers": safe_headers(response.request),
                            "post_data": (response.request.post_data or "")[:1800],
                            "row_count": len(rows),
                            "samples": samples,
                            "payload_keys": list(payload.keys())[:20] if isinstance(payload, dict) else [],
                        })
                    except Exception as exc:
                        observed.append({"url": response.url, "error": f"{type(exc).__name__}: {exc}"})

                page.on("response", on_response)
                nav_error = ""
                try:
                    page.goto(entry["start_url"], wait_until="domcontentloaded", timeout=35_000)
                    page.wait_for_timeout(5000)
                    for fraction in (0.5, 1.0):
                        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{fraction})")
                        page.wait_for_timeout(900)
                except Exception as exc:
                    nav_error = f"{type(exc).__name__}: {exc}"
                try:
                    body = page.locator("body").inner_text(timeout=3000)[:1200]
                except Exception:
                    body = ""
                summary = {
                    "id": entry["id"],
                    "company": entry["company"],
                    "start_url": entry["start_url"],
                    "final_url": page.url,
                    "nav_error": nav_error,
                    "api_responses": observed[:12],
                    "job_rows": sum(int(x.get("row_count") or 0) for x in observed),
                    "body_sample": body,
                }
                summaries.append(summary)
                print(json.dumps(summary, ensure_ascii=False))
                page.close()
        finally:
            context.close()
            browser.close()

    spacechina = next(x for x in summaries if x["id"] == "spacechina-iguopin")
    assert spacechina["api_responses"], f"spacechina public page emitted no IGuopin jobs API response: {spacechina}"
    assert any((x.get("status") or 0) == 200 for x in spacechina["api_responses"]), spacechina
    assert sum(x["job_rows"] for x in summaries) > 0, {"message": "selected IGuopin employer pages exposed no concrete jobs", "summaries": summaries}
    print("IGuopin employer public-request probe: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
