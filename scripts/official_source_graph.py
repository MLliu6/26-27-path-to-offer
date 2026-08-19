#!/usr/bin/env python3
"""Build a self-expanding graph of employer-owned recruiting sources.

The graph starts from reviewed official registries, then learns additional
company/application domains already observed in normalized job rows. Aggregator,
university and government evidence may discover a URL, but only employer-owned
career pages or explicit employer ATS tenants enter this graph.

This script does not crawl the web itself. It produces a deduplicated, auditable
catalogue that the bounded sampler can rotate through over time.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS = DATA / "jobs.json"
OUT = DATA / "official_source_catalog.json"
REGISTRIES = [
    ROOT / "sources" / "priority_official_sources.json",
    ROOT / "sources" / "official_source_registry_v12.json",
]

EXCLUDED_HOSTS = {
    "github.com", "raw.githubusercontent.com", "job.ncss.cn", "www.ncss.cn",
    "nowcoder.com", "www.nowcoder.com", "bosszhipin.com", "www.zhipin.com",
    "liepin.com", "www.liepin.com", "51job.com", "www.51job.com",
    "zhaopin.com", "www.zhaopin.com", "offerjack.cn", "www.offerjack.cn",
    "gitee.com", "mp.weixin.qq.com", "weixin.qq.com",
}
EXCLUDED_SUFFIXES = (".edu.cn", ".gov.cn")
ATS_HOST_HINTS = ("jobs.feishu.cn", "zhiye.com", "mokahr.com", "mokahr.com.cn", "smartrecruiters.com", "greenhouse.io", "lever.co", "ashbyhq.com", "recruitee.com")
CAREER_HINT = re.compile(r"career|careers|campus|recruit|recruitment|job|jobs|join|talent|zhaopin|hr|招聘|校招", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_url(value: Any) -> str:
    text = clean(value)
    if not text.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower().strip(".")
        if not host or host in EXCLUDED_HOSTS or host.endswith(EXCLUDED_SUFFIXES):
            return ""
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip("/") or "/", "", "", ""))
    except Exception:
        return ""


def source_key(company: str, url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "/").strip("/").split("/")[:2]
    tenant = "/".join(path) if any(hint in host for hint in ATS_HOST_HINTS) else ""
    return f"{clean(company).lower()}|{host}|{tenant}"


def add(rows: dict[str, dict[str, Any]], *, company: Any, url: Any, category: Any = "", priority: Any = 50, origin: str, modes: Any = None, contact: Any = "") -> None:
    company_name = clean(company)
    target = canonical_url(url)
    if not company_name or not target:
        return
    host = (urlparse(target).hostname or "").lower()
    if origin == "observed-job" and not (CAREER_HINT.search(target) or any(hint in host for hint in ATS_HOST_HINTS)):
        return
    key = source_key(company_name, target)
    existing = rows.get(key)
    candidate = {
        "company": company_name,
        "category": clean(category),
        "url": target,
        "host": host,
        "priority": max(1, min(100, int(priority or 50))),
        "origin": origin,
        "modes": modes if isinstance(modes, list) else [],
        "contact": clean(contact),
    }
    if not existing or candidate["priority"] > existing.get("priority", 0):
        rows[key] = {**(existing or {}), **candidate}
    else:
        existing.setdefault("origins", [])
        if origin not in existing["origins"]:
            existing["origins"].append(origin)


def load_registries(rows: dict[str, dict[str, Any]]) -> None:
    for path in REGISTRIES:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("watch", []):
            if isinstance(item, dict):
                add(rows, company=item.get("company"), url=item.get("url"), category=item.get("category"), priority=95, origin="priority-registry")
        for item in payload.get("sources", []):
            if isinstance(item, dict):
                add(rows, company=item.get("company"), url=item.get("url"), category=item.get("category"), priority=item.get("priority", 70), origin="reviewed-registry", modes=item.get("modes"), contact=item.get("contact"))
        for item in payload.get("career_spiders", []):
            if isinstance(item, dict):
                add(rows, company=item.get("company"), url=item.get("start_url"), category=item.get("company_type"), priority=100, origin="career-spider")


def job_value(job: dict[str, Any], compact_key: str, verbose_key: str) -> Any:
    return job.get(compact_key) if compact_key in job else job.get(verbose_key)


def learn_from_jobs(rows: dict[str, dict[str, Any]]) -> int:
    try:
        payload = json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:
        return 0
    learned = 0
    for job in payload.get("jobs", []):
        if not isinstance(job, dict):
            continue
        company = job_value(job, "c", "company")
        source_label = clean(job_value(job, "x", "source_label"))
        source = clean(job_value(job, "s", "source"))
        for url in [job_value(job, "u", "apply_url"), job_value(job, "n", "notice_url")]:
            before = len(rows)
            direct = "官网" in source_label or "企业官方" in source_label or source.startswith(("direct-official:", "ats:", "china-official"))
            add(rows, company=company, url=url, category=job_value(job, "h", "industry"), priority=78 if direct else 42, origin="observed-job")
            if len(rows) > before:
                learned += 1
    return learned


def previous_health() -> dict[str, Any]:
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {row.get("key"): row.get("health") for row in old.get("sources", []) if isinstance(row, dict) and row.get("key") and row.get("health")}


def main() -> int:
    rows: dict[str, dict[str, Any]] = {}
    load_registries(rows)
    learned = learn_from_jobs(rows)
    health = previous_health()
    sources = []
    for key, row in rows.items():
        item = {"key": key, **row}
        if key in health:
            item["health"] = health[key]
        sources.append(item)
    sources.sort(key=lambda item: (-int(item.get("priority", 0)), item.get("company", ""), item.get("host", "")))
    payload = {
        "version": 1,
        "generated_at": now(),
        "source_count": len(sources),
        "learned_from_jobs": learned,
        "sources": sources,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"official_sources": len(sources), "learned_from_jobs": learned}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
