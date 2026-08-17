#!/usr/bin/env python3
"""Scan the current nationwide NCSS student-job catalogue without keywords.

The NCSS public search UI supports an unfiltered "全部" job view. Its anonymous
JSON endpoint accepts an empty `jobName`, so this scanner walks that same public
catalogue in bounded parallel page batches. This is the broad domestic discovery
layer that prevents Path to Offer from knowing only companies present in a few
GitHub lists or hand-written adapters.

Only recently published/updated rows are retained by default. A row is *not*
labelled 2027 unless the visible row itself says 2027/27届; otherwise it remains
`年份待确认`. Employer-owned sources still outrank NCSS in ranking/provenance.

No login, CAPTCHA bypass, proxy rotation, stealth automation or authenticated
state is used.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, utc_now
from scripts.ncss_public_harvester import fetch_page, normalize, identity, session

MAX_ROWS = max(1000, min(20000, int(os.getenv("PTO_NCSS_ALL_MAX_ROWS", "12000"))))
PAGE_SIZE = 20
MAX_PAGES = max(50, min(1000, (MAX_ROWS + PAGE_SIZE - 1) // PAGE_SIZE))
BATCH = max(4, min(20, int(os.getenv("PTO_NCSS_ALL_BATCH", "12"))))
WORKERS = max(4, min(20, int(os.getenv("PTO_NCSS_ALL_WORKERS", "12"))))
RECENT_CUTOFF = datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp() * 1000


def is_recent(row: dict[str, Any]) -> bool:
    try:
        ts = float(row.get("updateDate") or row.get("publishDate") or 0)
        return ts >= RECENT_CUTOFF
    except Exception:
        return False


def fetch_number(page: int):
    s = session()
    rows = fetch_page(s, "", page, PAGE_SIZE)
    return page, rows


def scan() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    pages_scanned = 0
    raw_rows = 0
    short_page = None
    errors: list[str] = []
    start = 1
    while start <= MAX_PAGES and len(kept) < MAX_ROWS:
        pages = list(range(start, min(MAX_PAGES + 1, start + BATCH)))
        results: dict[int, list[dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(pages))) as pool:
            futs = {pool.submit(fetch_number, p): p for p in pages}
            for fut in as_completed(futs):
                p = futs[fut]
                try:
                    resolved, rows = fut.result()
                    results[resolved] = rows
                except Exception as exc:
                    errors.append(f"page {p}: {type(exc).__name__}: {clean(exc)[:120]}")
                    results[p] = []
        stop = False
        for p in sorted(results):
            rows = results[p]
            pages_scanned += 1
            raw_rows += len(rows)
            if not rows:
                short_page = p
                stop = True
                break
            for row in rows:
                if not is_recent(row):
                    continue
                job = normalize(row, explicit_query=False)
                if job:
                    # This mode is intentionally broader than the campus-keyword
                    # scanner. Keep explicit 2027 rows as such, but label all
                    # other rows honestly as current public student-platform jobs.
                    if not clean(job.get("graduation")):
                        job["source"] = "ncss-public:current-all"
                        job["source_label"] = "国家大学生就业服务平台 · 当前公开岗位"
                        job["batch"] = "当前公开岗位·年份待确认"
                        tags = [x for x in (job.get("tags") or []) if x != "国家大学生就业服务平台"]
                        job["tags"] = ["NCSS", "当前公开岗位", "年份待确认", *tags]
                    kept[identity(job)] = job
                    if len(kept) >= MAX_ROWS:
                        stop = True
                        break
            if len(rows) < PAGE_SIZE:
                short_page = p
                stop = True
                break
            if stop:
                break
        if stop:
            break
        start += BATCH

    companies = {clean(j.get("company")) for j in kept.values() if clean(j.get("company"))}
    beijing = sum(1 for j in kept.values() if "北京" in clean(j.get("location")))
    state_owned = sum(1 for j in kept.values() if "国有企业" in clean(j.get("company_type")))
    explicit_2027 = sum(1 for j in kept.values() if clean(j.get("graduation")) == "2027届")
    return list(kept.values()), {
        "max_rows": MAX_ROWS,
        "pages_scanned": pages_scanned,
        "raw_rows": raw_rows,
        "short_page": short_page,
        "unique_rows": len(kept),
        "unique_companies": len(companies),
        "beijing_rows": beijing,
        "state_owned_rows": state_owned,
        "explicit_2027_rows": explicit_2027,
        "errors_sample": errors[:20],
    }


def main() -> int:
    fresh, diag = scan()
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("ncss_recent_all.py must run before compact_feed.py")
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if isinstance(job, dict) and clean(job.get("company")) and clean(job.get("role")):
            merged[identity(job)] = job
    for job in fresh:
        key = identity(job)
        if key not in merged:
            merged[key] = job
    out = dict(payload)
    out["schema_version"] = 3
    out["generated_at"] = utc_now()
    out["jobs"] = list(merged.values())
    JOBS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "ncss-current-all",
        "label": "国家大学生就业服务平台 · 当前全国岗位",
        "url": "https://www.ncss.cn/student/jobs/index.html",
        "ok": bool(fresh),
        "count": len(fresh),
        "error": "" if fresh else "NCSS public all-jobs scan returned no recent rows",
        "diagnostics": diag,
    }
    sources = [s for s in status.get("sources", []) if not isinstance(s, dict) or s.get("name") != group["name"]]
    sources.insert(0, group)
    status["sources"] = sources
    status["catalog_count"] = len(out["jobs"])
    status["generated_at"] = utc_now()
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NCSS current-all:", diag, "merged=", len(out["jobs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
