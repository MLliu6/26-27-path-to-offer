#!/usr/bin/env python3
"""Promote user-reviewed target employer portals into source catalogues.

This is a source-discovery layer only. It does not claim that any specific role
is open. Employer portals remain eligible for the existing anonymous browser
sweep; companies already served by dedicated first-party adapters stay visible
in the graph but are not redundantly swept here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "user_target_positions_20260903.json"
RECRUIT = DATA / "recruit_domain_catalog.json"
GRAPH = DATA / "official_source_catalog.json"

DEDICATED = {"滴滴", "美团", "腾讯", "拼多多", "华为", "Shopee", "Shopee（深圳虾皮信息科技有限公司）", "快手"}
EXCLUDED_HOSTS = {"www.zhipin.com", "zhipin.com", "www.zhaopin.com", "zhaopin.com", "www.liepin.com", "liepin.com", "www.51job.com", "51job.com", "www.nowcoder.com", "nowcoder.com"}


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and bool(host) and host not in EXCLUDED_HOSTS
    except Exception:
        return False


def source_id(company: str, url: str) -> str:
    return "target-" + hashlib.sha1(f"{company}|{url}".encode("utf-8")).hexdigest()[:12]


def recruit_key(row: dict[str, Any]) -> tuple[str, str]:
    return clean(row.get("company")).lower(), clean(row.get("start_url") or row.get("url")).rstrip("/").lower()


def main() -> int:
    manifest = load(MANIFEST)
    target_entries: list[dict[str, Any]] = []
    for target in manifest.get("targets") or []:
        if not isinstance(target, dict):
            continue
        company = clean(target.get("company"))
        url = clean(target.get("portal_url"))
        if not company or not valid_url(url):
            continue
        host = (urlparse(url).hostname or "").lower()
        target_entries.append({
            "id": source_id(company, url),
            "company": company,
            "category": "2027目标岗位来源",
            "company_type": "",
            "start_url": url,
            "url": url,
            "official_url": url,
            "priority": 96,
            "modes": ["browser-public-ui", "target-coverage-audit"],
            "max_pages": 8,
            "origin": "user-target-20260903",
            "host": host,
            "evidence": "User-curated employer-owned recruiting entry from the 2026-09-03 target list; role availability is separately audited.",
            "sweep_enabled": company not in DEDICATED,
            **({"handled_by": "dedicated-or-priority-adapter"} if company in DEDICATED else {}),
        })

    recruit = load(RECRUIT)
    rows = [x for x in (recruit.get("sources") or []) if isinstance(x, dict)]
    merged = {recruit_key(x): x for x in rows if recruit_key(x) != ("", "")}
    for entry in target_entries:
        key = recruit_key(entry)
        old = merged.get(key)
        merged[key] = {**(old or {}), **entry}
    out_rows = list(merged.values())
    out_rows.sort(key=lambda x: (-int(x.get("priority") or 0), clean(x.get("company")), clean(x.get("host"))))
    recruit.update({
        "source_count": len(out_rows),
        "sweepable_count": sum(1 for x in out_rows if x.get("sweep_enabled", True)),
        "target_source_count": len(target_entries),
        "target_manifest": str(MANIFEST.relative_to(ROOT)),
        "sources": out_rows,
    })
    RECRUIT.write_text(json.dumps(recruit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    graph = load(GRAPH)
    graph_rows = [x for x in (graph.get("sources") or []) if isinstance(x, dict)]
    by_key = {clean(x.get("key")): x for x in graph_rows if clean(x.get("key"))}
    for entry in target_entries:
        key = f"target|{entry['company']}|{entry['host']}|20260903"
        old = by_key.get(key) or {}
        by_key[key] = {
            **old,
            "key": key,
            "company": entry["company"],
            "category": entry["category"],
            "url": entry["start_url"],
            "host": entry["host"],
            "priority": entry["priority"],
            "origin": "user-target-20260903",
            "modes": entry["modes"],
            "sweep_enabled": entry["sweep_enabled"],
        }
    graph_rows = list(by_key.values())
    graph_rows.sort(key=lambda x: (-int(x.get("priority") or 0), clean(x.get("company")), clean(x.get("host"))))
    graph.update({"source_count": len(graph_rows), "target_source_count": len(target_entries), "sources": graph_rows})
    GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "target_sources": len(target_entries),
        "target_sweepable": sum(1 for x in target_entries if x.get("sweep_enabled")),
        "recruit_catalog": len(out_rows),
        "official_graph": len(graph_rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
