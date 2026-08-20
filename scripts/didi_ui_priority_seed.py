#!/usr/bin/env python3
"""Seed the ten-minute feed from DiDi's employer-owned public UI.

The fast lane intentionally scans the active social-recruiting list only. That
public route is verified to emit concrete job XHRs on hosted runners and makes
DiDi searchable within a predictable budget. Campus/intern/overseas discovery
remains enabled in the deeper employer crawl, where longer route probing cannot
cause the next ten-minute refresh to cancel the current one.

Previously verified DiDi rows from non-social scopes are retained. The current
social window is replaced atomically on every successful fast refresh so route
or position-key changes cannot make the same live social jobs accumulate across
runs.
"""
from __future__ import annotations

import json
import os

os.environ["PTO_DIDI_BROWSER_MAX_PAGES"] = os.getenv("PTO_DIDI_PRIORITY_MAX_PAGES", "6")

from scripts.aggregate_jobs import clean
import scripts.didi_browser_ui_harvester as didi_ui
from scripts.priority_direct_feed import OUT, STATUS, canonical_compact, encode, now

# The browser module imports SCOPES from didi_official_harvester. Never mutate
# that shared list in place: doing so silently narrows the deep first-party
# collector to social-only for every later caller in the same Python process.
# Rebind only this module's view for the fast lane instead.
didi_ui.SCOPES = [scope for scope in didi_ui.SCOPES if scope.get("slug") == "social"]


def is_didi_social_row(row: dict) -> bool:
    """Return True only for DiDi rows that belong to the fast social window."""
    if clean(row.get("s")) != "direct-official:didi":
        return False
    batch = clean(row.get("b")).lower()
    if batch and ("社会" in batch or "社招" in batch or "social" in batch):
        return True
    url = clean(row.get("u") or row.get("n")).lower()
    return "/social/" in url


def merge_priority_rows(previous: list[dict], encoded: list[dict]) -> dict[str, dict]:
    """Replace the old DiDi social window while preserving every other scope."""
    merged: dict[str, dict] = {}
    for row in previous:
        if is_didi_social_row(row):
            continue
        key = canonical_compact(row)
        if key:
            merged[key] = row
    for row in encoded:
        key = canonical_compact(row)
        if key:
            merged[key] = row
    return merged


def main() -> int:
    jobs, diagnostics = didi_ui.collect_didi_via_ui()
    encoded = [row for job in jobs for row in [encode(job)] if row]
    previous: list[dict] = []
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
        previous = [row for row in payload.get("jobs", []) if isinstance(row, dict)]
    except Exception:
        pass

    merged = merge_priority_rows(previous, encoded)

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
