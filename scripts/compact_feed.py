#!/usr/bin/env python3
"""Compact normalized public jobs into global and China-first browser feeds.

The browser transport keeps a short provenance tier (`q`) separately from the
human-readable source label (`x`). Matching can therefore distinguish employer-
direct jobs from NCSS/university discovery without guessing provenance from a
translated label after compaction.
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
CN_CITIES = ("北京","上海","深圳","广州","杭州","南京","苏州","成都","武汉","西安","天津","重庆","长沙","合肥","无锡","厦门","青岛","济南","宁波","东莞","珠海","佛山","大连","沈阳","郑州","福州")
FIRST_TIER = {"北京","上海","深圳","广州","杭州"}
OVERSEAS = re.compile(r"海外|美国|加拿大|英国|德国|法国|欧洲|新加坡|日本|韩国|澳大利亚|印度|poland|germany|france|london|new york|san francisco|singapore|tokyo|india|united states|canada", re.I)
CAMPUS = re.compile(r"2027|27届|校招|校园招聘|应届|毕业生|实习|实习生|new\s*grad|graduate|campus|intern", re.I)
TECH = re.compile(r"ai|llm|vlm|vla|大模型|多模态|推理|cuda|gpu|kernel|算子|量化|ptq|编译器|compiler|runtime|npu|芯片|hpc|高性能|分布式|后端|算法|机器学习|深度学习|计算机视觉|嵌入式|机器人|软件|信息科技|金融科技|网络安全|云计算", re.I)
FIELDS = [("i","id"),("c","company"),("r","role"),("l","location"),("u","apply_url"),("n","notice_url"),("d","jd"),("t","updated_at"),("b","batch"),("g","graduation"),("e","education"),("p","salary"),("y","company_type"),("h","industry"),("m","department")]


def compact_text(value: Any, limit: int = MAX_PREVIEW) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def source_class(job: dict[str, Any]) -> str:
    source = clean(job.get("source")).lower(); label = clean(job.get("source_label"))
    if source.startswith("direct-official:"): return label[:40] if label else "企业招聘官网 · 自主直连"
    if source.startswith("priority-official:") or source.startswith("priority-campaign:"): return label[:40] if label else "重点企业 2027 招聘源"
    if source.startswith("ncss-public:"): return "国家大学生就业服务平台 · 2027招聘"
    if source.startswith("campus-discovery:university"): return label[:40] if label else "高校就业网 · 2027招聘发现"
    if source.startswith("priority-discovery:sasac") or source.startswith("priority-official:soe-directory"): return label[:40] if label else "央企官方招聘发现"
    if source.startswith("china-official"): return "中国企业官方招聘"
    if source.startswith("ats:"): return "企业官方 ATS"
    if source.startswith("remote-board"): return "公开远程招聘板"
    return label[:40] if label else "公开招聘来源"


def source_tier(job: dict[str, Any]) -> int:
    existing = job.get("q")
    if isinstance(existing, (int, float)):
        return max(1, min(7, int(existing)))
    source = clean(job.get("source")).lower(); label = clean(job.get("source_label") or job.get("x")).lower()
    blob = source + " " + label
    if source.startswith("direct-official:") or "自主直连" in blob or "招聘官网" in blob: return 7
    if source.startswith("priority-official:") or source.startswith("china-official") or source.startswith("ats:") or "企业官方招聘" in blob or "企业官方 ats" in blob: return 6
    if source.startswith("priority-campaign:"): return 5
    if source.startswith("priority-discovery:sasac") or source.startswith("priority-official:soe-directory") or "国资委" in blob: return 5
    if source.startswith("ncss-public:") or "国家大学生就业" in blob: return 4
    if source.startswith("campus-discovery:university") or "高校就业网" in blob: return 3
    return 1


def encode_job(job: dict[str, Any]) -> dict[str, Any] | None:
    if "c" in job and "r" in job:
        row = dict(job)
        if row.get("d"): row["d"] = compact_text(row["d"])
        row["q"] = source_tier(row)
        return row if clean(row.get("c")) and clean(row.get("r")) else None
    if not clean(job.get("company")) or not clean(job.get("role")): return None
    out: dict[str, Any] = {}
    for short, long in FIELDS:
        value = job.get(long)
        if long == "jd": value = compact_text(value)
        if isinstance(value, str): value = clean(value)
        if value not in (None, "", [], {}): out[short] = value
    out["x"] = source_class(job); out["q"] = source_tier(job)
    return out


def encode_jobs(jobs: list[Any], max_rows: int = MAX_ROWS) -> list[dict[str, Any]]:
    return [row for job in jobs if isinstance(job, dict) for row in [encode_job(job)] if row][:max_rows]


def verbose_location(job: dict[str, Any]) -> str: return clean(job.get("location") or job.get("l"))
def verbose_source(job: dict[str, Any]) -> str: return clean(job.get("source") or job.get("x") or job.get("source_label"))


def is_domestic(job: dict[str, Any]) -> bool:
    loc = verbose_location(job); src = verbose_source(job).lower()
    if OVERSEAS.search(loc): return False
    prefixes = ("direct-official:","priority-official:","priority-campaign:","priority-discovery:","ncss-public:","campus-discovery:university","china-official")
    if src.startswith(prefixes) or "中国企业官方招聘" in src or "招聘官网" in src or "国家大学生就业" in src or "高校就业网" in src: return True
    if any(city in loc for city in CN_CITIES): return True
    return bool(re.search(r"(?:中国|china|\bcn\b)", loc, re.I))


def source_priority(src: str) -> int:
    s = src.lower()
    if s.startswith("direct-official:") or "招聘官网" in s: return 145
    if s.startswith("priority-official:"): return 135
    if s.startswith("priority-campaign:"): return 110
    if s.startswith("china-official") or "中国企业官方招聘" in s: return 95
    if s.startswith("ncss-public:") or "国家大学生就业" in s: return 80
    if s.startswith("priority-discovery:sasac") or "国资委" in s: return 72
    if s.startswith("campus-discovery:university") or "高校就业网" in s: return 65
    if s.startswith("ats:") or "企业官方 ats" in s: return 55
    return 0


def domestic_priority(job: dict[str, Any]) -> tuple[int, str, str]:
    loc=verbose_location(job); src=verbose_source(job); role=clean(job.get("role") or job.get("r")); jd=clean(job.get("jd") or job.get("d")); batch=clean(job.get("batch") or job.get("b")); graduation=clean(job.get("graduation") or job.get("g")); score=source_priority(src)
    if "北京" in loc: score += 65
    elif any(c in loc for c in FIRST_TIER): score += 38
    if CAMPUS.search(" ".join((role,jd,batch,graduation))): score += 35
    if "2027" in role+jd+batch+graduation or "27届" in role+jd+batch+graduation: score += 18
    if TECH.search(role): score += 22
    elif TECH.search(jd): score += 9
    if clean(job.get("apply_url") or job.get("u")): score += 8
    elif clean(job.get("notice_url") or job.get("n")): score += 3
    updated=clean(job.get("updated_at") or job.get("t")); return (-score,updated,clean(job.get("company") or job.get("c")))


def global_priority(job: dict[str, Any]) -> tuple[int, str]:
    src=verbose_source(job); campus_blob=" ".join((clean(job.get("role")),clean(job.get("batch")),clean(job.get("graduation"))))
    return (-(source_priority(src)+(20 if CAMPUS.search(campus_blob) else 0)),clean(job.get("updated_at")))


def clean_status(status: dict[str, Any]) -> dict[str, Any]:
    out=dict(status or {}); sources=out.get("sources",[])
    if isinstance(sources,list): out["sources"]=[s for s in sources if not isinstance(s,dict) or s.get("name") not in RETIRED_SOURCE_STATUS]
    out["retired_sources"]=sorted(RETIRED_SOURCE_STATUS); return out


def write_feed(path: Path, generated: Any, rows: list[dict[str, Any]]) -> int:
    payload={"schema_version":4,"generated_at":generated,"jobs":rows}; path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8"); return path.stat().st_size


def main() -> int:
    payload=json.loads(JOBS_PATH.read_text(encoding="utf-8")); jobs=payload.get("jobs",[]) if isinstance(payload,dict) else []; generated=payload.get("generated_at") if isinstance(payload,dict) else None
    global_verbose=sorted([j for j in jobs if isinstance(j,dict)],key=global_priority); global_encoded=encode_jobs(global_verbose,MAX_ROWS); global_bytes=write_feed(JOBS_PATH,generated,global_encoded)
    domestic_verbose=[j for j in jobs if isinstance(j,dict) and is_domestic(j)]; domestic_verbose.sort(key=domestic_priority); cn_encoded=encode_jobs(domestic_verbose,MAX_CN_ROWS); cn_bytes=write_feed(CN_PATH,generated,cn_encoded)
    raw_status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}; status=clean_status(raw_status)
    status.update({"catalog_count":len(global_encoded),"cn_catalog_count":len(cn_encoded),"feed_schema":4,"browser_jd_chars":MAX_PREVIEW,"feed_bytes":global_bytes,"cn_feed_bytes":cn_bytes,"catalog_cap":MAX_ROWS,"cn_catalog_cap":MAX_CN_ROWS,"default_product_feed":"data/jobs_cn.json","source_tier_key":"q"})
    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"compact feeds: global={len(global_encoded)}/{global_bytes}B cn={len(cn_encoded)}/{cn_bytes}B jd_chars={MAX_PREVIEW}"); return 0


if __name__ == "__main__": raise SystemExit(main())
