#!/usr/bin/env python3
"""Expand the browser source registry from the current official-job catalogue.

The manually curated registry handles important employers and known career home
pages. This layer derives additional employer-owned / official-ATS domains from
already observed canonical jobs, groups them by company, and feeds a bounded,
sharded browser scan. The registry can therefore grow with the product instead
of requiring every company to be hard-coded by hand.

The generated registry is temporary. Only concrete normalized jobs and aggregate
source health are persisted; discovery candidates are rebuilt each run from the
latest catalogue and curated source files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.aggregate_jobs import JOBS_PATH, clean
from scripts import browser_official_harvester as browser

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "sources" / "browser_official_sources.json"
TEMP = Path(os.getenv("PTO_RUNTIME_BROWSER_REGISTRY", "/tmp/path-to-offer-browser-sources.json"))
MAX_DYNAMIC = max(100, min(10_000, int(os.getenv("PTO_DYNAMIC_EMPLOYER_SOURCES", "5000"))))

EXCLUDED_HOSTS = {
    "github.com", "raw.githubusercontent.com", "offerjack.cn", "www.offerjack.cn",
    "ncss.cn", "www.ncss.cn", "job.ncss.cn", "nowcoder.com", "www.nowcoder.com",
    "zhipin.com", "www.zhipin.com", "bosszhipin.com", "51job.com", "www.51job.com",
    "liepin.com", "www.liepin.com", "lagou.com", "www.lagou.com", "gitee.com",
    "mp.weixin.qq.com", "weixin.qq.com", "douyin.com", "xiaohongshu.com",
}
UNIVERSITY_HINT = re.compile(r"(?:career|job|jy|jobcareer)\.[^.]+\.(?:edu\.cn|edu)$|\.edu\.cn$", re.I)
OFFICIAL_SOURCE = re.compile(r"direct-official|china-official|priority-official|企业官方|招聘官网|官方招聘|official ats|feishu|beisen|moka|greenhouse|ashby|lever|smartrecruiters|recruitee|breezy|personio", re.I)
CAREER_URL = re.compile(r"job|jobs|career|careers|recruit|recruitment|campus|join|talent|position|招聘|职位|岗位|人才", re.I)


def safe_id(company: str, host: str) -> str:
    digest = hashlib.sha256(f"{company}\0{host}".encode()).hexdigest()[:12]
    return f"dynamic-{digest}"


def host_allowed(host: str) -> bool:
    value = host.lower().strip(".")
    if not value or value in EXCLUDED_HOSTS or UNIVERSITY_HINT.search(value):
        return False
    if value.endswith((".gov.cn", ".edu.cn")):
        return False
    return True


def candidate_url(job: dict[str, Any]) -> str:
    values = [job.get("apply_url"), job.get("notice_url"), job.get("source_url")]
    ranked = sorted((clean(value) for value in values if clean(value)), key=lambda url: (not bool(CAREER_URL.search(url)), len(url)))
    for url in ranked:
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and host_allowed(parsed.hostname or ""):
            return url
    return ""


def trusted(job: dict[str, Any]) -> bool:
    blob = " ".join(clean(job.get(key)) for key in ("source", "source_label", "observed_via", "source_url"))
    return bool(OFFICIAL_SOURCE.search(blob))


def derive_dynamic(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for job in jobs:
        if not isinstance(job, dict) or not trusted(job):
            continue
        company = clean(job.get("company"))
        if not company:
            continue
        url = candidate_url(job)
        if not url:
            continue
        host = (urlparse(url).hostname or "").lower()
        if not host_allowed(host):
            continue
        key = (company, host)
        group = groups.setdefault(key, {
            "id": safe_id(company, host),
            "company": company,
            "company_type": clean(job.get("company_type")),
            "start_urls": [],
            "allowed_hosts": [host],
            "always": False,
            "discovered_job_count": 0,
            "campus_signal_count": 0,
        })
        group["discovered_job_count"] += 1
        blob = " ".join(clean(job.get(field)) for field in ("role", "batch", "graduation", "jd"))
        if re.search(r"2026|2027|26届|27届|校招|校园招聘|应届|实习|campus|graduate|intern", blob, re.I):
            group["campus_signal_count"] += 1
        if url not in group["start_urls"] and len(group["start_urls"]) < 3:
            group["start_urls"].append(url)
        if not group["company_type"]:
            group["company_type"] = clean(job.get("company_type"))
    rows = list(groups.values())
    rows.sort(key=lambda row: (-row["campus_signal_count"], -row["discovered_job_count"], row["company"], row["id"]))
    return rows[:MAX_DYNAMIC]


def main() -> int:
    static = json.loads(STATIC.read_text(encoding="utf-8"))
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"jobs": []}
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    if jobs and isinstance(jobs[0], dict) and "c" in jobs[0]:
        raise RuntimeError("browser_official_scale.py must run after expand_feed.py and before compact_feed.py")
    dynamic = derive_dynamic([job for job in jobs if isinstance(job, dict)])
    existing_ids = {clean(row.get("id")) for row in static.get("sources", []) if isinstance(row, dict)}
    existing_pairs = {(clean(row.get("company")), (urlparse(clean((row.get("start_urls") or [""])[0])).hostname or "").lower()) for row in static.get("sources", []) if isinstance(row, dict) and row.get("start_urls")}
    additions = [row for row in dynamic if row["id"] not in existing_ids and (row["company"], row["allowed_hosts"][0]) not in existing_pairs]
    runtime = dict(static)
    runtime["runtime_generated"] = True
    runtime["dynamic_source_count"] = len(additions)
    runtime["sources"] = [*static.get("sources", []), *additions]
    TEMP.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    browser.REGISTRY = TEMP
    print(json.dumps({"curated": len(static.get("sources", [])), "dynamic": len(additions), "runtime_total": len(runtime["sources"]), "sample": [(row["company"], row["allowed_hosts"][0], row["discovered_job_count"]) for row in additions[:20]]}, ensure_ascii=False))
    return browser.main()


if __name__ == "__main__":
    raise SystemExit(main())
