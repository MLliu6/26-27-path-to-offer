#!/usr/bin/env python3
"""Live acceptance for employer-scoped public IGuopin jobs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts import priority_browser_harvester as harvester
from scripts import priority_browser_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_browser_sources.json"


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = [x for x in registry.get("sources", []) if isinstance(x, dict) and x.get("family") == "iguopin"]
    assert len(sources) >= 8, len(sources)
    by_id = {x.get("id"): x for x in sources}
    entry = by_id["spacechina-iguopin"]

    runtime.install()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1365, "height": 900}, locale="zh-CN")
        try:
            jobs, diagnostics = harvester.collect_one(context, entry)
        finally:
            context.close()
            browser.close()

    assert diagnostics.get("iguopin_tenant_only") is True, diagnostics
    assert len(jobs) >= 5, {"jobs": jobs[:3], "diagnostics": diagnostics}
    assert all(j.get("observed_via") == "browser-public-iguopin-tenant-list" for j in jobs), jobs[:3]
    assert all(str(j.get("tenant_id") or "").isdigit() for j in jobs), jobs[:3]
    assert len({str(j.get("tenant_id")) for j in jobs}) == 1
    assert all(j.get("parent_company") == "中国航天科技集团" for j in jobs)
    assert any(j.get("company") and j.get("company") != "中国航天科技集团" for j in jobs)
    assert any(j.get("graduation") == "2027届" for j in jobs)
    assert any("北京" in str(j.get("location")) for j in jobs)
    assert all("https://job.iguopin.com/job/detail?id=" in str(j.get("apply_url")) for j in jobs)
    print(json.dumps({
        "jobs": len(jobs),
        "tenant": jobs[0].get("tenant_id"),
        "sample": [{"company": j.get("company"), "role": j.get("role"), "location": j.get("location")} for j in jobs[:4]],
        "diagnostics": diagnostics,
    }, ensure_ascii=False))
    print("IGuopin employer production runtime: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
