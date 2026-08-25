#!/usr/bin/env python3
"""Run one bounded shard of the expanded public recruitment-domain catalogue."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CATALOG = DATA / "recruit_domain_catalog.json"
STATUS = DATA / "source_status.json"
JOBS = DATA / "jobs.json"
OVERRIDES = ROOT / "sources" / "recruit_domain_overrides.json"


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def stable_order(entry: dict[str, Any]) -> tuple[str, str]:
    raw = f"{clean(entry.get('company')).lower()}|{clean(entry.get('start_url')).lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest(), raw


def parse_force() -> set[str]:
    raw = os.getenv("PTO_RECRUIT_SWEEP_FORCE_COMPANIES", "")
    return {clean(x) for x in raw.replace("，", ",").split(",") if clean(x)}


def select(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sweepable = [x for x in entries if isinstance(x, dict) and x.get("sweep_enabled", True) and clean(x.get("start_url"))]
    ordered = sorted(sweepable, key=stable_order)
    force = parse_force()
    forced = [x for x in ordered if clean(x.get("company")) in force]
    non_forced = [x for x in ordered if clean(x.get("company")) not in force]

    max_targets = max(1, min(40, int(os.getenv("PTO_RECRUIT_SWEEP_MAX_TARGETS", "16"))))
    shard_count = max(1, math.ceil(len(non_forced) / max_targets)) if non_forced else 1
    raw_index = os.getenv("PTO_RECRUIT_SWEEP_SHARD_INDEX", "").strip()
    if raw_index:
        shard_index = int(raw_index) % shard_count
        shard_mode = "explicit"
    else:
        shard_index = int(time.time() // 3600) % shard_count
        shard_mode = "clock-hour"
    start = shard_index * max_targets
    normal = non_forced[start : start + max_targets]

    selected: list[dict[str, Any]] = []
    seen = set()
    for entry in [*forced, *normal]:
        key = clean(entry.get("id")) or clean(entry.get("start_url"))
        if key and key not in seen:
            selected.append(entry)
            seen.add(key)

    return selected, {
        "catalog_sweepable": len(sweepable),
        "max_targets": max_targets,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "shard_mode": shard_mode,
        "forced_companies": sorted(force),
        "forced_targets": len(forced),
        "selected_targets": len(selected),
    }


def override_configs() -> dict[str, dict[str, Any]]:
    payload = load(OVERRIDES)
    result = {}
    for item in payload.get("sources", []) or []:
        if isinstance(item, dict) and clean(item.get("id")):
            result[clean(item.get("id"))] = item
    return result


def detail_templates() -> dict[str, str]:
    result: dict[str, str] = {}
    for source_id, item in override_configs().items():
        template = clean(item.get("detail_url_template"))
        if template.startswith(("http://", "https://")) and "{id}" in template:
            result[source_id] = template
    return result


def enrich_detail_links(selected: list[dict[str, Any]]) -> int:
    templates = detail_templates()
    selected_ids = {clean(x.get("id")) for x in selected if isinstance(x, dict) and clean(x.get("id"))}
    active = {source_id: template for source_id, template in templates.items() if source_id in selected_ids}
    if not active or not JOBS.exists():
        return 0

    payload = load(JOBS)
    rows = payload.get("jobs", [])
    if not isinstance(rows, list):
        return 0
    changed = 0
    for job in rows:
        if not isinstance(job, dict):
            continue
        source = clean(job.get("source"))
        prefix = "direct-official:browser:"
        if not source.startswith(prefix):
            continue
        source_id = source[len(prefix):]
        template = active.get(source_id)
        position_id = clean(job.get("position_id"))
        if not template or not position_id:
            continue
        url = template.replace("{id}", quote(position_id, safe=""))
        if not url.startswith(("http://", "https://")):
            continue
        if clean(job.get("apply_url")) == url and clean(job.get("notice_url")) == url:
            continue
        job["apply_url"] = url
        job["notice_url"] = url
        tags = job.get("tags") if isinstance(job.get("tags"), list) else []
        if "官方职位详情" not in tags:
            tags.append("官方职位详情")
        job["tags"] = tags
        changed += 1
    if changed:
        JOBS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def harvest_reviewed_api(selected: list[dict[str, Any]], h: Any) -> tuple[list[dict[str, Any]], int]:
    configs = override_configs()
    chosen = []
    for entry in selected:
        source_id = clean(entry.get("id"))
        config = configs.get(source_id) or {}
        if clean(config.get("adapter")).startswith("kuaishou-"):
            chosen.append(config)
    if not chosen:
        return [], 0

    from scripts import kuaishou_public_api_harvester as k

    payload = load(JOBS)
    existing = [x for x in payload.get("jobs", []) if isinstance(x, dict)]
    retired = {
        "direct-official:browser:recruit-kuaishou-campus",
        "direct-official:browser:recruit-kuaishou-campus-2027-a",
        "direct-official:browser:recruit-kuaishou-campus-2027-b",
        "direct-official:browser:recruit-kuaishou-intern-2027-a",
        "direct-official:browser:recruit-kuaishou-intern-2027-b",
    }
    existing = [job for job in existing if clean(job.get("source")) not in retired]
    fresh_by_source: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []
    fresh_total = 0
    for config in chosen:
        source_id = clean(config.get("id"))
        source = f"direct-official:browser:{source_id}"
        previous = [job for job in existing if clean(job.get("source")) == source]
        try:
            jobs, diagnostics = k.harvest(config)
            fresh_by_source[source] = jobs
            fresh_total += len(jobs)
            results.append({
                "id": source_id,
                "company": config.get("company"),
                "ok": bool(jobs),
                "count": len(jobs),
                "fresh_count": len(jobs),
                "preserved_previous": False,
                "official_url": config.get("official_url"),
                "diagnostics": diagnostics,
                "error": "" if jobs else "zero public API jobs",
            })
        except Exception as exc:
            fresh_by_source[source] = previous
            results.append({
                "id": source_id,
                "company": config.get("company"),
                "ok": bool(previous),
                "count": len(previous),
                "fresh_count": 0,
                "preserved_previous": bool(previous),
                "official_url": config.get("official_url"),
                "diagnostics": {"transport": "official-public-api"},
                "error": f"{type(exc).__name__}: {clean(exc)[:220]}",
            })

    merged = h.merge(existing, fresh_by_source)
    output = dict(payload)
    output.update({"schema_version": 3, "generated_at": h.utc_now(), "jobs": merged})
    JOBS.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return results, fresh_total


def main() -> int:
    catalog = load(CATALOG)
    entries = [x for x in (catalog.get("sources") or []) if isinstance(x, dict)]
    if not entries:
        raise RuntimeError("recruit domain catalogue is empty; run recruit_domain_expander.py first")
    selected, meta = select(entries)
    if not selected:
        print(json.dumps({**meta, "message": "empty shard"}, ensure_ascii=False))
        return 0

    from scripts import priority_browser_harvester as h

    configs = override_configs()
    api_ids = {
        clean(entry.get("id"))
        for entry in selected
        if clean((configs.get(clean(entry.get("id"))) or {}).get("adapter")).startswith("kuaishou-")
    }
    browser_selected = [entry for entry in selected if clean(entry.get("id")) not in api_ids]

    previous_status = load(STATUS)
    previous_priority = next(
        (x for x in previous_status.get("sources", []) if isinstance(x, dict) and x.get("name") == "priority-browser-official"),
        None,
    )

    runtime = Path(tempfile.gettempdir()) / "pto-recruit-domain-sweep.json"
    runtime.write_text(json.dumps({
        "version": 1,
        "policy": "Auto-expanded reviewed employer recruiting surfaces; public browser UI/XHR/DOM only.",
        "sources": browser_selected,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    h.REGISTRY = runtime
    h.NAV_TIMEOUT = max(7_000, min(20_000, int(os.getenv("PTO_RECRUIT_SWEEP_TIMEOUT_MS", "14000"))))
    rc = h.main()
    api_results, api_fresh_total = harvest_reviewed_api(selected, h)
    detail_link_updates = enrich_detail_links(selected)

    status = load(STATUS)
    groups = [x for x in status.get("sources", []) if isinstance(x, dict)]
    generated = next((x for x in groups if x.get("name") == "priority-browser-official"), None)
    groups = [x for x in groups if x.get("name") != "priority-browser-official" and x.get("name") != "recruit-domain-sweep"]
    if generated:
        generated = dict(generated)
        generated["name"] = "recruit-domain-sweep"
        generated["label"] = "招聘域名图谱 · 轮转真实浏览器/审核公开 API 巡检"
        generated["count"] = int(generated.get("count") or 0) + sum(int(x.get("count") or 0) for x in api_results)
        generated["fresh_count"] = int(generated.get("fresh_count") or 0) + api_fresh_total
        if api_results:
            generated["ok"] = bool(generated.get("ok")) or any(x.get("ok") for x in api_results)
        diag = dict(generated.get("diagnostics") or {})
        diag.update(meta)
        diag["transport"] = "real-browser-public-ui-xhr-dom+reviewed-official-public-api" if api_results else diag.get("transport")
        diag["sources"] = [*(diag.get("sources") or []), *api_results]
        diag["reviewed_api_sources"] = len(api_results)
        diag["reviewed_api_fresh_jobs"] = api_fresh_total
        diag["detail_links_enriched"] = detail_link_updates
        diag["selected"] = [
            {"id": x.get("id"), "company": x.get("company"), "start_url": x.get("start_url"), "origin": x.get("origin")}
            for x in selected
        ]
        diag["catalog_total"] = int(catalog.get("source_count") or len(entries))
        generated["diagnostics"] = diag
        groups.insert(0, generated)
    if previous_priority:
        groups.insert(0, previous_priority)
    status["sources"] = groups
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        **meta,
        "selected_companies": [x.get("company") for x in selected],
        "browser_targets": len(browser_selected),
        "reviewed_api_targets": len(api_results),
        "reviewed_api_fresh_jobs": api_fresh_total,
        "shared_harvester_rc": rc,
        "fresh_jobs": (generated or {}).get("fresh_count", 0),
        "retained_jobs": (generated or {}).get("count", 0),
        "detail_links_enriched": detail_link_updates,
    }, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
