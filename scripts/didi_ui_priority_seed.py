#!/usr/bin/env python3
"""Seed the ten-minute feed from DiDi's employer-owned public UI.

The fast lane intentionally scans the active social-recruiting list only. That
public route is verified to emit concrete job XHRs on hosted runners and makes
DiDi searchable within a predictable budget. Campus/intern/overseas discovery
remains enabled in the deeper employer crawl, where longer route probing cannot
cause the next ten-minute refresh to cancel the current one.

Previously verified DiDi rows are retained, so every fast run adds/replaces the
current front window without deleting jobs discovered by the deep pass.
"""
from __future__ import annotations

import json
import os

os.environ["PTO_DIDI_BROWSER_MAX_PAGES"] = os.getenv("PTO_DIDI_PRIORITY_MAX_PAGES", "6")

from scripts.aggregate_jobs import clean
import scripts.didi_browser_ui_harvester as didi_ui
from scripts.priority_direct_feed import OUT, STATUS, canonical_compact, encode, now

# The broad collector still owns all four scopes. Only this fast lane narrows the
# active traversal to the route proven to return a real public job list quickly.
didi_ui.SCOPES[:] = [scope for scope in didi_ui.SCOPES if scope.get("slug") == "social"]


def main() -> int:
    jobs, diagnostics = didi_ui.collect_didi_via_ui()
    encoded = [row for job in jobs for row in [encode(job)] if row]
    previous: list[dict] = []
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
        previous = [row for row in payload.get("jobs", []) if isinstance(row, dict)]
    except Exception:
        pass

    merged: dict[str, dict] = {}
    for row in previous:
        key = canonical_compact(row)
        if key:
            merged[key] = row
    for row in encoded:
        key = canonical_compact(row)
        if key:
            merged[key] = row

    generated = now()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema_version": 4, "generated_at": generated, "jobs": list(merged.values())}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = {}
    try:
        status = json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception:
        pass
    didi_rows = [row for row in merged.values() if clean(row.get("s")) == "direct-official:didi"]
    group = {
        "name": "didi-direct-official",
        "label": "滴滴招聘官网 · 浏览器自主直连",
        "url": didi_ui.BASE,
        "ok": bool(didi_rows),
        "count": len(didi_rows),
        "fresh_count": len(encoded),
        "preserved_previous": len(didi_rows) > len(encoded),
        "diagnostics": {
            **diagnostics,
            "priority_mode": "social-first",
            "priority_page_budget": int(os.environ["PTO_DIDI_BROWSER_MAX_PAGES"]),
            "deep_scan_scopes": ["social", "campus", "intern", "overseas"],
        },
        "error": "" if didi_rows else "public UI returned zero concrete jobs",
    }
    sources = [source for source in status.get("sources", []) if not isinstance(source, dict) or source.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({
        "generated_at": generated,
        "catalog_count": len(merged),
        "refresh_class": "priority-employer-direct",
        "nominal_interval_minutes": 10,
        "sources": sources,
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"didi_priority_rows": len(didi_rows), "fresh": len(encoded), "mode": "social-first", "page_budget": group["diagnostics"]["priority_page_budget"], "batches": diagnostics.get("batches")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
