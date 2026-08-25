#!/usr/bin/env python3
"""Expand reviewed employer recruiting URLs into a browser-sweep catalogue.

This is deliberately a discovery/normalization layer, not a job fabricator.
Only employer-owned recruiting surfaces or reviewed public ATS tenants already
present in Path to Offer's registries/source graph are promoted. Concrete jobs
still have to be observed by the browser harvester.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
DATA = ROOT / "data"
OUT = DATA / "recruit_domain_catalog.json"
GRAPH = DATA / "official_source_catalog.json"

INPUTS = [
    SOURCES / "official_source_registry_v12.json",
    SOURCES / "priority_official_sources.json",
    SOURCES / "priority_browser_sources.json",
    SOURCES / "emerging_compute_browser_sources.json",
    SOURCES / "huawei_browser_source.json",
    SOURCES / "external_discovered_sources.json",
    SOURCES / "moka_public_sources.json",
    SOURCES / "recruit_domain_overrides.json",
    GRAPH,
]
OVERRIDES = SOURCES / "recruit_domain_overrides.json"

CAREER_RE = re.compile(
    r"(?:^|[.\-_/])(?:zhaopin|campus(?:hr)?|career(?:s)?|jobs?|hr|talent|recruit(?:ment)?|join(?:us)?|hire|hiring)(?:[.\-_/]|$)|招聘|校招|社招",
    re.I,
)
ATS_HINTS = (
    "jobs.feishu.cn", "zhiye.com", "mokahr.com", "mokahr.com.cn", "hotjob.cn",
    "iguopin.com", "smartrecruiters.com", "greenhouse.io", "lever.co", "ashbyhq.com",
    "recruitee.com", "workdayjobs.com", "myworkdayjobs.com", "successfactors.com",
)
EXCLUDED_HOSTS = {
    "www.zhipin.com", "zhipin.com", "www.zhaopin.com", "zhaopin.com", "www.liepin.com", "liepin.com",
    "www.51job.com", "51job.com", "www.nowcoder.com", "nowcoder.com", "job.ncss.cn", "www.ncss.cn",
    "mp.weixin.qq.com", "weixin.qq.com", "github.com", "raw.githubusercontent.com", "gitee.com",
}
STATIC_RE = re.compile(r"\.(?:js|css|png|jpe?g|gif|svg|webp|woff2?|ttf|map|ico)(?:$|[?#])", re.I)
PRIVATE_ROUTE_RE = re.compile(r"(?:^|/)(?:login|signin|register|signup|offer|accept-offer|resume/upload|user/info)(?:/|$)", re.I)

# These companies already have a dedicated live adapter or reviewed priority
# browser adapter. Keep them in the catalogue for coverage visibility, but do
# not duplicate their production jobs through the generic sweep.
DEDICATED_COMPANIES = {"滴滴", "美团", "腾讯", "拼多多", "华为", "Shopee（深圳虾皮信息科技有限公司）"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def iter_items(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("sources", "watch", "career_spiders"):
        rows = payload.get(key) or []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row


def url_of(item: dict[str, Any]) -> str:
    for key in ("start_url", "url", "official_url", "career_url"):
        value = clean(item.get(key))
        if value.startswith(("http://", "https://")):
            return value
    return ""


def normalize_url(value: str) -> str:
    value = clean(value)
    if not value.startswith(("http://", "https://")) or STATIC_RE.search(value):
        return ""
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower().strip(".")
        if not host or host in EXCLUDED_HOSTS or host.endswith((".edu.cn", ".gov.cn")):
            return ""
        # Keep query/hash because many Chinese recruiting SPAs encode the actual
        # list route there; only strip obvious tracking fragments from path.
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, parsed.fragment))
    except Exception:
        return ""


def is_recruit_surface(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    signal = f"{host}{parsed.path}#{parsed.fragment}"
    if any(hint in host for hint in ATS_HINTS):
        return True
    if not CAREER_RE.search(signal):
        return False
    # Login/user shells are not recruiting sources unless a separate job/campus
    # signal is also present in the URL.
    if PRIVATE_ROUTE_RE.search(parsed.path) and not re.search(r"job|campus|career|recruit|zhaopin", signal, re.I):
        return False
    return True


def stable_id(company: str, url: str) -> str:
    digest = hashlib.sha1(f"{company.lower()}|{url.lower()}".encode("utf-8")).hexdigest()[:12]
    return f"auto-recruit-{digest}"


def explicit_browser_companies() -> set[str]:
    companies = set(DEDICATED_COMPANIES)
    for name in ("priority_browser_sources.json", "emerging_compute_browser_sources.json", "huawei_browser_source.json"):
        for item in iter_items(load(SOURCES / name)):
            company = clean(item.get("company"))
            if company and item.get("enabled", True) is not False:
                companies.add(company)
    return companies


def company_key(company: str) -> str:
    return re.sub(r"[\s（）()·•._-]+", "", clean(company)).lower()


def candidate_from(item: dict[str, Any], origin: str, *, force_sweep: bool = False) -> dict[str, Any] | None:
    company = clean(item.get("company"))
    url = normalize_url(url_of(item))
    if not company or not is_recruit_surface(url):
        return None
    parsed = urlparse(url)
    priority = max(1, min(100, int(item.get("priority") or 70)))
    entry = {
        "id": clean(item.get("id")) or stable_id(company, url),
        "company": company,
        "category": clean(item.get("category") or item.get("company_type")),
        "company_type": clean(item.get("company_type")),
        "start_url": url,
        "url": url,
        "official_url": clean(item.get("official_url")) or url,
        "priority": priority,
        "modes": item.get("modes") if isinstance(item.get("modes"), list) else ["browser-public-ui"],
        "max_pages": max(1, min(12, int(item.get("max_pages") or 4))),
        "origin": origin,
        "host": (parsed.hostname or "").lower(),
        "click_labels": [clean(x) for x in (item.get("click_labels") or []) if clean(x)][:8],
        "api_hosts": [clean(x).lower() for x in (item.get("api_hosts") or []) if clean(x)][:8],
        "extra_hosts": [clean(x).lower() for x in (item.get("extra_hosts") or []) if clean(x)][:8],
        "evidence": clean(item.get("evidence") or item.get("note")),
        "sweep_enabled": True,
    }
    if not entry["api_hosts"]:
        entry["api_hosts"] = [entry["host"]]
    if not force_sweep and company in explicit_browser_companies():
        entry["sweep_enabled"] = False
        entry["handled_by"] = "dedicated-or-priority-adapter"
    return entry


def dedupe_key(entry: dict[str, Any]) -> str:
    parsed = urlparse(entry["start_url"])
    # Keep distinct campus/social SPA fragments for the same employer while
    # deduplicating trailing slash/query noise.
    fragment = (parsed.fragment or "").rstrip("/").lower()
    path = (parsed.path or "/").rstrip("/").lower()
    return f"{company_key(entry['company'])}|{entry['host']}|{path}|{fragment}"


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    override_keys: set[str] = set()

    # Reviewed overrides win and are always sweepable; this is where a shell
    # homepage is replaced by its real public list route (e.g. Kuaishou).
    for item in iter_items(load(OVERRIDES)):
        entry = candidate_from(item, "reviewed-override", force_sweep=True)
        if entry:
            key = dedupe_key(entry)
            rows[key] = entry
            override_keys.add(f"{company_key(entry['company'])}|{entry['host']}")

    for path in INPUTS:
        if path == OVERRIDES:
            continue
        payload = load(path)
        origin = f"registry:{path.name}" if path.parent == SOURCES else "official-source-graph"
        for item in iter_items(payload):
            entry = candidate_from(item, origin)
            if not entry:
                continue
            company_host = f"{company_key(entry['company'])}|{entry['host']}"
            if company_host in override_keys:
                continue
            key = dedupe_key(entry)
            old = rows.get(key)
            if old is None or int(entry.get("priority", 0)) > int(old.get("priority", 0)):
                rows[key] = entry

    entries = list(rows.values())
    entries.sort(key=lambda x: (-int(x.get("priority", 0)), x.get("company", ""), x.get("host", ""), x.get("start_url", "")))
    sweepable = [x for x in entries if x.get("sweep_enabled")]
    hosts = Counter(x.get("host") for x in entries)
    ats = Counter(next((hint for hint in ATS_HINTS if hint in x.get("host", "")), "employer-owned") for x in entries)
    meta = {
        "source_count": len(entries),
        "sweepable_count": len(sweepable),
        "dedicated_count": len(entries) - len(sweepable),
        "host_count": len(hosts),
        "top_hosts": hosts.most_common(20),
        "families": ats.most_common(),
        "input_files": [str(p.relative_to(ROOT)) for p in INPUTS if p.exists()],
    }
    return entries, meta


def promote_to_graph(entries: list[dict[str, Any]]) -> int:
    graph = load(GRAPH)
    sources = [x for x in (graph.get("sources") or []) if isinstance(x, dict)]
    by_key = {clean(x.get("key")): x for x in sources if clean(x.get("key"))}
    added = 0
    for entry in entries:
        key = f"{company_key(entry['company'])}|{entry['host']}|recruit-domain"
        current = by_key.get(key)
        item = {
            "key": key,
            "company": entry["company"],
            "category": entry.get("category", ""),
            "url": entry["start_url"],
            "host": entry["host"],
            "priority": entry.get("priority", 70),
            "origin": "recruit-domain-expander",
            "modes": ["browser-public-ui-xhr-dom"],
            "contact": "",
            "sweep_enabled": bool(entry.get("sweep_enabled")),
        }
        if current:
            # Never erase health collected by the official-source sampler.
            item = {**current, **item, **({"health": current["health"]} if current.get("health") else {})}
        else:
            added += 1
        by_key[key] = item
    merged = list(by_key.values())
    merged.sort(key=lambda item: (-int(item.get("priority", 0)), item.get("company", ""), item.get("host", ""), item.get("url", "")))
    graph.update({
        "generated_at": now(),
        "source_count": len(merged),
        "recruit_domain_promoted": len(entries),
        "sources": merged,
    })
    DATA.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> int:
    entries, meta = build()
    promoted_new = promote_to_graph(entries) if GRAPH.exists() else 0
    payload = {
        "version": 1,
        "generated_at": now(),
        **meta,
        "promoted_new_graph_nodes": promoted_new,
        "sources": entries,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**meta, "promoted_new_graph_nodes": promoted_new}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
