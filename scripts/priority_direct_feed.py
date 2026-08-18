#!/usr/bin/env python3
"""Build the small high-priority employer-direct browser feed.

The nationwide catalogue is intentionally deeper and slower. This file powers a
separate ten-minute loop for employer-owned public sources, currently PDD plus
the already proven Meituan and Tencent adapters. The browser loads this feed
before the broader China catalogue and deduplicates on the canonical job URL.

Each source fails independently. When a source is temporarily unavailable, its
last valid rows are preserved from the previous priority feed instead of being
replaced by an empty result. No login, CAPTCHA bypass, private credential or
stealth automation is used.
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
    url = clean(job.get("apply_url") or job.get("notice_url"))
    pdd = position_key_from_url(url)
    if pdd:
        return pdd
    if url:
        return f"url:{url.lower().rstrip('/')}"
    return "|".join([
        clean(job.get("company")).lower(),
        clean(job.get("role")).lower(),
        clean(job.get("location")).lower(),
    ])


def canonical_compact(row: dict[str, Any]) -> str:
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
    return [x for x in rows if isinstance(x, dict) and clean(x.get("c")) and clean(x.get("r"))]


def collect_legacy_direct() -> list[tuple[str, str, Callable[[dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]], dict[str, Any]]]:
    try:
        cfg = json.loads(DIRECT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for source in cfg.get("sources", []):
        if not isinstance(source, dict) or not source.get("enabled", True):
            continue
        adapter = clean(source.get("adapter"))
        if adapter not in {"meituan", "tencent"}:
            continue
        fn = LEGACY_DIRECT_ADAPTERS.get(adapter)
        if fn:
            out.append((f"direct-official:{adapter}", clean(source.get("company")) or adapter, fn, source))
    return out


def source_of_compact(row: dict[str, Any]) -> str:
    return clean(row.get("s"))


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    old = previous_rows()
    old_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in old:
        old_by_source.setdefault(source_of_compact(row), []).append(row)

    source_runs: list[dict[str, Any]] = []
    fresh_by_source: dict[str, list[dict[str, Any]]] = {}

    # PDD is intentionally independent of the legacy adapter registry because it
    # has exact-position seeds and stronger completeness gates.
    try:
        jobs, diagnostics = collect_pdd()
        if not jobs:
            raise RuntimeError("zero concrete PDD jobs")
        if not diagnostics.get("seed_gate_ok"):
            raise RuntimeError(f"exact-position seed failed: {diagnostics.get('seeds')}")
        rows = [encoded for job in jobs for encoded in [encode(job)] if encoded]
        fresh_by_source["direct-official:pdd"] = rows
        source_runs.append({
            "name": "pdd-direct-official",
            "label": "拼多多校园招聘官网 · 全量自主直连",
            "url": "https://careers.pddglobalhr.com/campus/grad",
            "ok": True,
            "count": len(rows),
            "preserved_previous": False,
            "diagnostics": diagnostics,
            "error": "",
        })
    except Exception as exc:
        kept = old_by_source.get("direct-official:pdd", [])
        fresh_by_source["direct-official:pdd"] = kept
        source_runs.append({
            "name": "pdd-direct-official",
            "label": "拼多多校园招聘官网 · 全量自主直连",
            "url": "https://careers.pddglobalhr.com/campus/grad",
            "ok": bool(kept),
            "count": len(kept),
            "preserved_previous": bool(kept),
            "diagnostics": {},
            "error": f"{type(exc).__name__}: {short(exc, 260)}",
        })

    for source_id, company, fn, config in collect_legacy_direct():
        try:
            jobs, diagnostics = fn(config)
            rows = [encoded for job in jobs for encoded in [encode(job)] if encoded]
            if not rows:
                raise RuntimeError("zero concrete jobs")
            fresh_by_source[source_id] = rows
            source_runs.append({
                "name": source_id.replace("direct-official:", "") + "-direct-official",
                "label": f"{company}招聘官网 · 自主直连",
                "url": clean(config.get("official_url")),
                "ok": True,
                "count": len(rows),
                "preserved_previous": False,
                "diagnostics": diagnostics,
                "error": "",
            })
        except Exception as exc:
            kept = old_by_source.get(source_id, [])
            fresh_by_source[source_id] = kept
            source_runs.append({
                "name": source_id.replace("direct-official:", "") + "-direct-official",
                "label": f"{company}招聘官网 · 自主直连",
                "url": clean(config.get("official_url")),
                "ok": bool(kept),
                "count": len(kept),
                "preserved_previous": bool(kept),
                "diagnostics": {},
                "error": f"{type(exc).__name__}: {short(exc, 260)}",
            })

    # Preserve any previous source not managed by this version. This makes the
    # format forward-compatible with future direct adapters.
    for source_id, rows in old_by_source.items():
        if source_id and source_id not in fresh_by_source:
            fresh_by_source[source_id] = rows

    merged: dict[str, dict[str, Any]] = {}
    for source_id in sorted(fresh_by_source, key=lambda x: (x != "direct-official:pdd", x)):
        for row in fresh_by_source[source_id]:
            key = canonical_compact(row)
            if key and key not in merged:
                merged[key] = row

    rows = list(merged.values())
    exact_id = "5e4eb6f3-294f-491b-9d39-42895eed98c3"
    exact = [x for x in rows if exact_id in clean(x.get("z") or x.get("u") or x.get("n"))]
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
    print(json.dumps({"priority_jobs": len(rows), "exact_pdd_position_ok": exact_ok, "sources": [(x["name"], x["count"], x["preserved_previous"]) for x in source_runs]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
