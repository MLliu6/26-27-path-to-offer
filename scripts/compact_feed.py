#!/usr/bin/env python3
"""Compact the normalized public catalogue for browser delivery.

The crawler operates on descriptive field names for maintainability. Shipping the
same verbose schema for 60k jobs costs tens of megabytes in repeated JSON keys and
provenance strings. This final publishing pass keeps the information needed for
search, matching, shortlist and job-detail preview but encodes each row with short
keys. The official apply/notice URL remains the canonical full job detail.

This is a transport representation only; source-health stays verbose/auditable.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean

# 220 chars was selected from a live 60k acceptance run: 360-char previews still
# produced a ~40.9 MB payload. The official apply URL remains the full JD source.
MAX_PREVIEW = max(160, int(os.getenv("PTO_BROWSER_JD_CHARS", "220")))

# These experimental scrapers are no longer part of the production refresh once
# the official federation is active. Keeping their stale failures in source health
# would make a healthy 60k catalogue look broken.
RETIRED_SOURCE_STATUS = {"offerjack", "gank-public-search"}

# Transport schema v4. Keep this map mirrored by market-v06.js.
FIELDS = [
    ("i", "id"), ("c", "company"), ("r", "role"), ("l", "location"),
    ("u", "apply_url"), ("n", "notice_url"), ("d", "jd"), ("t", "updated_at"),
    ("b", "batch"), ("g", "graduation"), ("e", "education"), ("p", "salary"),
    ("y", "company_type"), ("h", "industry"), ("m", "department"),
]


def compact_text(value: Any, limit: int = MAX_PREVIEW) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def source_class(job: dict[str, Any]) -> str:
    source = clean(job.get("source")).lower()
    if source.startswith("china-official"):
        return "中国企业官方招聘"
    if source.startswith("ats:"):
        return "企业官方 ATS"
    if source.startswith("remote-board"):
        return "公开远程招聘板"
    label = clean(job.get("source_label"))
    return label[:40] if label else "公开招聘来源"


def encode_job(job: dict[str, Any]) -> dict[str, Any] | None:
    # Idempotence: tolerate an already compact row.
    if "c" in job and "r" in job:
        row = dict(job)
        if row.get("d"):
            row["d"] = compact_text(row["d"])
        return row if clean(row.get("c")) and clean(row.get("r")) else None
    if not clean(job.get("company")) or not clean(job.get("role")):
        return None
    out: dict[str, Any] = {}
    for short, long in FIELDS:
        value = job.get(long)
        if long == "jd":
            value = compact_text(value)
        if isinstance(value, str):
            value = clean(value)
        if value not in (None, "", [], {}):
            out[short] = value
    out["x"] = source_class(job)
    return out


def clean_status(status: dict[str, Any]) -> dict[str, Any]:
    out = dict(status or {})
    sources = out.get("sources", [])
    if isinstance(sources, list):
        out["sources"] = [s for s in sources if not isinstance(s, dict) or s.get("name") not in RETIRED_SOURCE_STATUS]
    out["retired_sources"] = sorted(RETIRED_SOURCE_STATUS)
    return out


def main() -> int:
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    encoded = [row for job in jobs if isinstance(job, dict) for row in [encode_job(job)] if row]
    generated = payload.get("generated_at") if isinstance(payload, dict) else None
    output = {"schema_version": 4, "generated_at": generated, "jobs": encoded}
    JOBS_PATH.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    raw_status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    status = clean_status(raw_status)
    status["catalog_count"] = len(encoded)
    status["feed_schema"] = 4
    status["browser_jd_chars"] = MAX_PREVIEW
    status["feed_bytes"] = JOBS_PATH.stat().st_size
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"compact feed: rows={len(encoded)} bytes={JOBS_PATH.stat().st_size} jd_chars={MAX_PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
