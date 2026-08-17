#!/usr/bin/env python3
"""Compact normalized public jobs into global and China-first browser feeds.

The crawler keeps descriptive fields for maintainability. The browser receives a
short-key schema. `jobs.json` remains the auditable global catalogue; `jobs_cn.json`
is the default product feed and contains domestic/China-located jobs only, ordered
so Beijing, first-tier cities, campus/graduate roles and China-official sources are
available without transferring tens of thousands of irrelevant overseas records.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.aggregate_jobs import DATA, JOBS_PATH, STATUS_PATH, clean

MAX_PREVIEW = max(160, int(os.getenv("PTO_BROWSER_JD_CHARS", "220")))
MAX_ROWS = max(1000, int(os.getenv("PTO_MAX_CATALOG", "60000")))
MAX_CN_ROWS = max(1000, int(os.getenv("PTO_MAX_CN_CATALOG", "30000")))
CN_PATH = DATA / "jobs_cn.json"

RETIRED_SOURCE_STATUS = {"offerjack", "gank-public-search"}
CN_CITIES = (
    "北京","上海","深圳","广州","杭州","南京","苏州","成都","武汉","西安","天津","重庆",
    "长沙","合肥","无锡","厦门","青岛","济南","宁波","东莞","珠海","佛山","大连","沈阳","郑州","福州",
)
FIRST_TIER = {"北京","上海","深圳","广州","杭州"}
OVERSEAS = re.compile(r"海外|美国|加拿大|英国|德国|法国|欧洲|新加坡|日本|韩国|澳大利亚|印度|poland|germany|france|london|new york|san francisco|singapore|tokyo|india|united states|canada", re.I)
CAMPUS = re.compile(r"校招|校园招聘|应届|毕业生|实习|实习生|new\s*grad|graduate|campus|intern", re.I)
TECH = re.compile(r"ai|llm|vlm|vla|大模型|多模态|推理|cuda|gpu|kernel|算子|量化|ptq|编译器|compiler|runtime|npu|芯片|hpc|高性能|分布式|后端|算法|机器学习|深度学习|计算机视觉|嵌入式|机器人", re.I)

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


def encode_jobs(jobs: list[Any], max_rows: int = MAX_ROWS) -> list[dict[str, Any]]:
    encoded = [row for job in jobs if isinstance(job, dict) for row in [encode_job(job)] if row]
    return encoded[:max_rows]


def verbose_location(job: dict[str, Any]) -> str:
    return clean(job.get("location") or job.get("l"))


def verbose_source(job: dict[str, Any]) -> str:
    return clean(job.get("source") or job.get("x") or job.get("source_label"))


def is_domestic(job: dict[str, Any]) -> bool:
    loc = verbose_location(job)
    src = verbose_source(job)
    if OVERSEAS.search(loc):
        return False
    if src.startswith("china-official") or "中国企业官方招聘" in src:
        return True
    if any(city in loc for city in CN_CITIES):
        return True
    return bool(re.search(r"(?:中国|china|\bcn\b)", loc, re.I))


def domestic_priority(job: dict[str, Any]) -> tuple[int, str, str]:
    loc = verbose_location(job)
    src = verbose_source(job)
    role = clean(job.get("role") or job.get("r"))
    jd = clean(job.get("jd") or job.get("d"))
    score = 0
    if src.startswith("china-official") or "中国企业官方招聘" in src:
        score += 80
    if "北京" in loc:
        score += 60
    elif any(c in loc for c in FIRST_TIER):
        score += 35
    if CAMPUS.search(" ".join((role, jd, clean(job.get("batch") or job.get("b")), clean(job.get("graduation") or job.get("g"))))):
        score += 30
    if TECH.search(role):
        score += 18
    if clean(job.get("apply_url") or job.get("u")):
        score += 8
    updated = clean(job.get("updated_at") or job.get("t"))
    return (-score, updated, clean(job.get("company") or job.get("c")))


def clean_status(status: dict[str, Any]) -> dict[str, Any]:
    out = dict(status or {})
    sources = out.get("sources", [])
    if isinstance(sources, list):
        out["sources"] = [s for s in sources if not isinstance(s, dict) or s.get("name") not in RETIRED_SOURCE_STATUS]
    out["retired_sources"] = sorted(RETIRED_SOURCE_STATUS)
    return out


def write_feed(path: Path, generated: Any, rows: list[dict[str, Any]]) -> int:
    payload = {"schema_version": 4, "generated_at": generated, "jobs": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return path.stat().st_size


def main() -> int:
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    generated = payload.get("generated_at") if isinstance(payload, dict) else None

    global_encoded = encode_jobs(jobs, MAX_ROWS)
    global_bytes = write_feed(JOBS_PATH, generated, global_encoded)

    domestic_verbose = [j for j in jobs if isinstance(j, dict) and is_domestic(j)]
    domestic_verbose.sort(key=domestic_priority)
    cn_encoded = encode_jobs(domestic_verbose, MAX_CN_ROWS)
    cn_bytes = write_feed(CN_PATH, generated, cn_encoded)

    raw_status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    status = clean_status(raw_status)
    status["catalog_count"] = len(global_encoded)
    status["cn_catalog_count"] = len(cn_encoded)
    status["feed_schema"] = 4
    status["browser_jd_chars"] = MAX_PREVIEW
    status["feed_bytes"] = global_bytes
    status["cn_feed_bytes"] = cn_bytes
    status["catalog_cap"] = MAX_ROWS
    status["cn_catalog_cap"] = MAX_CN_ROWS
    status["default_product_feed"] = "data/jobs_cn.json"
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"compact feeds: global={len(global_encoded)}/{global_bytes}B cn={len(cn_encoded)}/{cn_bytes}B jd_chars={MAX_PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
