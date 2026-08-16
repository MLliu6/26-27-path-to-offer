#!/usr/bin/env python3
"""Expand Path to Offer's compact browser transport feed back to crawler records.

Why this exists
---------------
The production site publishes schema-v4 rows with short keys so 60k jobs remain
practical on GitHub Pages. The crawler/dedupe layer intentionally uses readable
field names. A scheduled refresh must therefore expand the previous compact feed
*before* trying to preserve/merge it; otherwise a temporary upstream outage could
turn a healthy 60k cache into only the handful of rows collected by a supplement.

The transform is intentionally loss-aware: compact source class becomes
`source_label`, the canonical official URL is restored, and all matching/search
fields are reconstructed. Full verbose provenance cannot be recreated from the
compact transport, but it is not needed to preserve a previously published job.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.aggregate_jobs import JOBS_PATH, clean

MAP = {
    "i":"id", "c":"company", "r":"role", "l":"location",
    "u":"apply_url", "n":"notice_url", "d":"jd", "t":"updated_at",
    "b":"batch", "g":"graduation", "e":"education", "p":"salary",
    "y":"company_type", "h":"industry", "m":"department",
}


def expand_job(job: dict[str, Any]) -> dict[str, Any] | None:
    if "company" in job and "role" in job:
        return dict(job) if clean(job.get("company")) and clean(job.get("role")) else None
    if not clean(job.get("c")) or not clean(job.get("r")):
        return None
    out = {long: job.get(short, "") for short, long in MAP.items()}
    out["source"] = "previous-compact"
    out["source_label"] = clean(job.get("x")) or "上一轮公开招聘缓存"
    out["source_url"] = clean(job.get("u") or job.get("n"))
    out["tags"] = []
    out["observed_via"] = "previous-compact-cache"
    return out


def expand_payload(payload: dict[str, Any]) -> dict[str, Any]:
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    expanded = [row for job in jobs if isinstance(job, dict) for row in [expand_job(job)] if row]
    return {
        "schema_version": 3,
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "jobs": expanded,
    }


def main() -> int:
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 4:
        print(f"expand feed: schema={payload.get('schema_version')} already crawler-readable; no change")
        return 0
    expanded = expand_payload(payload)
    JOBS_PATH.write_text(json.dumps(expanded, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"expand feed: {len(expanded['jobs'])} compact rows restored for refresh merging")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
