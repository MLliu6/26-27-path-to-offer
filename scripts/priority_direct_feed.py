#!/usr/bin/env python3
"""Build the fast employer-direct browser feed.

This stage refreshes inexpensive proven public employer APIs and ATS surfaces:
PDD, Shopee/Moka, Meituan and Tencent. DiDi is deliberately not queried here:
GitHub-hosted runners may intercept its direct HTTP transport, so the immediately
following `didi_ui_priority_seed.py` drives DiDi's public UI instead.

Each source fails independently and preserves its last valid rows. No login,
applicant API, CAPTCHA bypass or user cookie is used.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from scripts.aggregate_jobs import clean
from scripts.direct_china_official import CONFIG_PATH as DIRECT_CONFIG_PATH
from scripts.direct_china_official import ADAPTERS as LEGACY_DIRECT_ADAPTERS
from scripts.moka_public_harvester import fetch_company as fetch_moka_company, load_priority_specs as load_moka_priority_specs
from scripts.pdd_official_harvester import collect_pdd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "jobs_priority.json"
STATUS = DATA / "priority_source_status.json"
MAX_JD = max(500, min(5000, int(os.getenv("PTO_PRIORITY_JD_CHARS", "1800"))))


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def short(value: Any, limit: int = MAX_JD) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def position_key_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        pid = (query.get("positionId") or query.get("position_id") or [""])[0]
        if pid:
            return f"pdd:{pid.lower()}"
    except Exception:
        pass
    return ""


def canonical_verbose(job: dict[str, Any]) -> str:
    position_id = clean(job.get("position_id"))
    source = clean(job.get("source"))
    if position_id and source:
        return f"{source}:{position_id}".lower()
    url = clean(job.get("apply_url") or job.get("notice_url"))
    pdd = position_key_from_url(url)
    if pdd:
        return pdd
    if url:
        return f"url:{url.lower().rstrip('/')}"
    return "|".join([
        clean(job.get("company")).lower(), clean(job.get("role")).lower(), clean(job.get("location")).lower(),
    ])


def canonical_compact(row: dict[str, Any]) -> str:
    position_id = clean(row.get("z"))
    source = clean(row.get("s"))
    if position_id and source:
        return f"{source}:{position_id}".lower()
    url = clean(row.get("u") or row.get("n"))
    pdd = position_key_from_url(url)
    if pdd:
        return pdd
    if url:
        return f"url:{url.lower().rstrip('/')}"
    return "|".join([clean(row.get("c")).lower(), clean(row.get("r")).lower(), clean(row.get("l")).lower()])


def encode(job: dict[str, Any]) -> dict[str, Any] | None:
    company = clean(job.get("company"))
    role = clean(job.get("role"))
    if not company or not role:
        return None
    source = clean(job.get("source")) or "direct-official:unknown"
    out: dict[str, Any] = {
        "i": clean(job.get("id")) or canonical_verbose(job),
        "c": company,
        "r": role,
        "x": clean(job.get("source_label")) or "企业招聘官网 · 自主直连",
        "q": 7,
        "s": source,
    }
    mapping = {
        "l": "location", "u": "apply_url", "n": "notice_url", "t": "updated_at",
        "b": "batch", "g": "graduation", "e": "education", "p": "salary",
        "y": "company_type", "h": "industry", "m": "department",
    }
    for short_key, long_key in mapping.items():
        value = clean(job.get(long_key))
        if value:
            out[short_key] = value
    jd = short(job.get("jd"))
    if jd:
        out["d"] = jd
    position_id = clean(job.get("position_id"))
    if position_id:
        out["z"] = position_id
    return out


def previous_rows() -> list[dict[str, Any]]:
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict) and clean(row.get("c")) and clean(row.get("r"))]


def collect_legacy_direct() -> list[tuple[str, str, Callable[[dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]], dict[str, Any]]]:
    try:
        config = json.loads(DIRECT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for source in config.get("sources", []):
        if not isinstance(source, dict) or not source.get("enabled", True):
            continue
        adapter = clean(source.get("adapter"))
        if adapter not in {"meituan", "tencent"}:
            continue
        function = LEGACY_DIRECT_ADAPTERS.get(adapter)
        if function:
            out.append((f"direct-official:{adapter}", clean(source.get("company")) or adapter, function, source))
    return out


def source_of_compact(row: dict[str, Any]) -> str:
    return clean(row.get("s"))


def record_special_source(*, source_id: str, name: str, label: str, url: str, collector, old_by_source, fresh_by_source, source_runs, validator=None) -> None:
    try:
        jobs, diagnostics = collector()
        if not jobs:
            raise RuntimeError("zero concrete jobs")
        if validator:
            validator(jobs, diagnostics)
        rows = [encoded for job in jobs for encoded in [encode(job)] if encoded]
        fresh_by_source[source_id] = rows
        source_runs.append({"name": name, "label": label, "url": url, "ok": True, "count": len(rows), "preserved_previous": False, "diagnostics": diagnostics, "error": ""})
    except Exception as exc:
        kept = old_by_source.get(source_id, [])
        fresh_by_source[source_id] = kept
        source_runs.append({"name": name, "label": label, "url": url, "ok": bool(kept), "count": len(kept), "preserved_previous": bool(kept), "diagnostics": {}, "error": f"{type(exc).__name__}: {short(exc, 260)}"})


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    old = previous_rows()
    old_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in old:
        old_by_source.setdefault(source_of_compact(row), []).append(row)

    source_runs: list[dict[str, Any]] = []
    fresh_by_source: dict[str, list[dict[str, Any]]] = {}

    def validate_pdd(jobs, diagnostics):
        if not diagnostics.get("seed_gate_ok"):
            raise RuntimeError(f"exact-position seed failed: {diagnostics.get('seeds')}")

    record_special_source(
        source_id="direct-official:pdd", name="pdd-direct-official",
        label="拼多多校园招聘官网 · 全量自主直连", url="https://careers.pddglobalhr.com/campus/grad",
        collector=collect_pdd, validator=validate_pdd, old_by_source=old_by_source,
        fresh_by_source=fresh_by_source, source_runs=source_runs,
    )

    # Moka priority sources are employer-owned public career tenants. Unlike the
    # broad federation, this short list runs every ten minutes so user-reported
    # omissions such as Shopee become regression failures instead of anecdotes.
    for spec in load_moka_priority_specs():
        key = clean(spec.get("key")) or clean(spec.get("org"))
        source_id = "direct-official:shopee" if key == "shopee" else f"direct-official:moka:{key}"
        company = clean(spec.get("company")) or key
        record_special_source(
            source_id=source_id,
            name=f"{key}-direct-official",
            label=f"{company}招聘官网 · Moka公开直连",
            url=clean(spec.get("official_url")),
            collector=lambda spec=spec: fetch_moka_company(spec),
            old_by_source=old_by_source,
            fresh_by_source=fresh_by_source,
            source_runs=source_runs,
        )

    for source_id, company, function, config in collect_legacy_direct():
        try:
            jobs, diagnostics = function(config)
            rows = [encoded for job in jobs for encoded in [encode(job)] if encoded]
            if not rows:
                raise RuntimeError("zero concrete jobs")
            fresh_by_source[source_id] = rows
            source_runs.append({"name": source_id.replace("direct-official:", "") + "-direct-official", "label": f"{company}招聘官网 · 自主直连", "url": clean(config.get("official_url")), "ok": True, "count": len(rows), "preserved_previous": False, "diagnostics": diagnostics, "error": ""})
        except Exception as exc:
            kept = old_by_source.get(source_id, [])
            fresh_by_source[source_id] = kept
            source_runs.append({"name": source_id.replace("direct-official:", "") + "-direct-official", "label": f"{company}招聘官网 · 自主直连", "url": clean(config.get("official_url")), "ok": bool(kept), "count": len(kept), "preserved_previous": bool(kept), "diagnostics": {}, "error": f"{type(exc).__name__}: {short(exc, 260)}"})

    # DiDi and future specialist browser sources are carried forward untouched;
    # their dedicated browser stage runs immediately afterwards.
    for source_id, rows in old_by_source.items():
        if source_id and source_id not in fresh_by_source:
            fresh_by_source[source_id] = rows

    source_order = {"direct-official:pdd": 0, "direct-official:shopee": 1, "direct-official:didi": 2, "direct-official:meituan": 3, "direct-official:tencent": 4}
    merged: dict[str, dict[str, Any]] = {}
    for source_id in sorted(fresh_by_source, key=lambda value: (source_order.get(value, 99), value)):
        for row in fresh_by_source[source_id]:
            key = canonical_compact(row)
            if key and key not in merged:
                merged[key] = row

    rows = list(merged.values())
    exact_id = "5e4eb6f3-294f-491b-9d39-42895eed98c3"
    exact = [row for row in rows if exact_id in clean(row.get("z") or row.get("u") or row.get("n"))]
    exact_ok = bool(exact and "ai infra" in clean(exact[0].get("r")).lower())
    if not exact_ok and not old:
        raise RuntimeError("exact PDD AI Infra position is missing and no previous valid priority feed exists")

    generated = now()
    OUT.write_text(json.dumps({"schema_version": 4, "generated_at": generated, "jobs": rows}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    status = {
        "generated_at": generated,
        "catalog_count": len(rows),
        "refresh_class": "priority-employer-direct",
        "nominal_interval_minutes": 10,
        "exact_pdd_position_id": exact_id,
        "exact_pdd_position_ok": exact_ok,
        "sources": source_runs,
    }
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"priority_jobs": len(rows), "exact_pdd_position_ok": exact_ok, "sources": [(row["name"], row["count"], row["preserved_previous"]) for row in source_runs]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
