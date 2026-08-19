#!/usr/bin/env python3
"""Seed the fast priority feed from DiDi's public browser UI collector.

The ten-minute lane is intentionally bounded so one deep employer cannot occupy
or cancel the next scheduled refresh. The two-hour deep catalogue keeps the
larger traversal budget. The priority lane still checks every recruitment scope
and enough pages to make DiDi immediately searchable while preserving prior
validated DiDi rows when the live surface temporarily shrinks.
"""
from __future__ import annotations

import json
import os

# This must be set before importing the browser collector because that module
# resolves its traversal budget at import time. Operators may override it with
# PTO_DIDI_PRIORITY_MAX_PAGES, but the default is intentionally small enough for
# a ten-minute schedule.
os.environ["PTO_DIDI_BROWSER_MAX_PAGES"] = os.getenv("PTO_DIDI_PRIORITY_MAX_PAGES", "12")

from scripts.aggregate_jobs import clean
from scripts.didi_browser_ui_harvester import BASE, collect_didi_via_ui
from scripts.priority_direct_feed import OUT, STATUS, canonical_compact, encode, now


def main() -> int:
    jobs, diagnostics = collect_didi_via_ui()
    encoded = [row for job in jobs for row in [encode(job)] if row]
    previous: list[dict] = []
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
        previous = [row for row in payload.get("jobs", []) if isinstance(row, dict)]
    except Exception:
        pass

    # Preserve previously verified DiDi rows that are outside the bounded fast
    # window. Fresh rows replace matching canonical URLs, so the fast feed grows
    # toward full coverage instead of oscillating between page windows.
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
    group = {
        "name": "didi-direct-official",
        "label": "滴滴招聘官网 · 浏览器自主直连",
        "url": BASE,
        "ok": True,
        "count": len([row for row in merged.values() if clean(row.get("s")) == "direct-official:didi"]),
        "fresh_count": len(encoded),
        "preserved_previous": any(clean(row.get("s")) == "direct-official:didi" for row in previous),
        "diagnostics": {**diagnostics, "priority_page_budget": int(os.environ["PTO_DIDI_BROWSER_MAX_PAGES"])},
        "error": "",
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
    print(json.dumps({"didi_priority_rows": group["count"], "fresh": len(encoded), "page_budget": group["diagnostics"]["priority_page_budget"], "batches": diagnostics.get("batches")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
