#!/usr/bin/env python3
"""Build the production China-first campus/early-career job catalogue.

Path to Offer v0.7 deliberately stops treating a 60k global ATS dump as the
primary candidate experience.  The product is aimed first at China campus / new
grad / internship recruiting, especially Beijing and other tier-one cities.

This collector executes the pinned Hiring-Radar *company-local* adapters only:
self-hosted company career APIs plus Feishu Hire, Beisen and Moka public company
career portals.  Moka is accepted here because the public website response ships
the decryption key in the anonymous response and the browser performs the same
client-side transform; no account, cookie, CAPTCHA solving, proxy rotation or
access-control bypass is used.

The previous compact catalogue may be expanded before this script runs.  We keep
only domestic/China-relevant rows from that cache, merge fresh official-company
rows, prefer direct company URLs over aggregator URLs, remove obvious senior or
foreign-only roles from the campus default pool, and publish measured diagnostics.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, utc_now
from scripts.federated_harvester import GroupStatus, load_radar, normalize_row
from scripts.merge_public_tables import canonical_key, merge_catalog

ROOT = Path(__file__).resolve().parents[1]
MAX_WORKERS = max(4, min(28, int(os.getenv("PTO_CHINA_COMPANY_WORKERS", "18"))))
MAX_CATALOG = max(2000, int(os.getenv("PTO_CHINA_MAX_CATALOG", "25000")))

TIER1 = ("北京", "上海", "深圳", "广州", "杭州")
CHINA_GEO = (
    "中国", "北京", "上海", "深圳", "广州", "杭州", "南京", "苏州", "成都", "武汉", "西安", "天津", "重庆",
    "长沙", "合肥", "无锡", "厦门", "青岛", "济南", "宁波", "东莞", "珠海", "佛山", "大连", "沈阳", "郑州",
    "福州", "昆明", "南昌", "南宁", "贵阳", "太原", "石家庄", "哈尔滨", "长春", "乌鲁木齐", "兰州",
    "海口", "三亚", "香港", "澳门", "台北", "河北", "河南", "山东", "山西", "陕西", "四川", "湖北",
    "湖南", "安徽", "江苏", "浙江", "福建", "广东", "广西", "江西", "辽宁", "吉林", "黑龙江", "云南",
    "贵州", "海南", "内蒙古", "宁夏", "新疆", "西藏", "China", "PRC",
)
FOREIGN_ONLY = re.compile(
    r"\b(?:United States|USA|US|Canada|United Kingdom|UK|Germany|France|Netherlands|Poland|Spain|Italy|Sweden|"
    r"Norway|Finland|Denmark|Switzerland|Australia|New Zealand|Japan|Korea|Singapore|India|Brazil|Mexico|Israel|"
    r"Ireland|Portugal|Romania|Hungary|Czech|Austria|Belgium)\b",
    re.I,
)
EARLY = re.compile(
    r"(?:校招|校园招聘|应届|应届生|毕业生|实习|实习生|管培|培训生|见习|新卒|2026\s*届|2027\s*届|2028\s*届|"
    r"\bnew\s*grad\b|\bgraduate\b|\bcampus\b|\bintern(?:ship)?\b|\bearly\s*career\b|\bentry[ -]?level\b|\btrainee\b)",
    re.I,
)
SOCIAL = re.compile(r"(?:社招|社会招聘|experienced\s*hire|lateral\s*hire)", re.I)
SENIOR = re.compile(
    r"(?:资深|高级专家|首席|总监|负责人|技术专家|架构师|研究专家|主任|经理岗|"
    r"\b(?:senior|staff|principal|lead|director|head|architect|distinguished)\b)",
    re.I,
)

DIRECT_COMPANY = {
    "bytedance": "字节跳动", "tencent": "腾讯", "netease": "网易", "jd": "京东", "baidu": "百度", "unitree": "宇树科技",
}
DIRECT_PORTAL = {
    "bytedance": "https://jobs.bytedance.com/campus",
    "tencent": "https://join.qq.com/",
    "jd": "https://zhaopin.jd.com/web/job/job_info_list/3",
    "baidu": "https://talent.baidu.com/",
}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def adapter_family(spec: dict[str, Any]) -> str:
    args = [str(x) for x in (spec.get("args") or [])]
    first = args[0].lower() if args else ""
    if "feishu.py" in first:
        return "feishu"
    if "moka.py" in first:
        return "moka"
    if "beisen.py" in first:
        return "beisen"
    return "direct"


def company_hint(key: str, spec: dict[str, Any]) -> str:
    args = [str(x) for x in (spec.get("args") or [])]
    family = adapter_family(spec)
    if family == "feishu" and len(args) >= 3:
        return args[2]
    if family == "moka" and len(args) >= 4:
        return args[3]
    if family == "beisen" and len(args) >= 3:
        return args[2]
    return DIRECT_COMPANY.get(key, key)


def portal_for(key: str, spec: dict[str, Any]) -> str:
    args = [str(x) for x in (spec.get("args") or [])]
    family = adapter_family(spec)
    if family == "feishu" and len(args) >= 2:
        host_path = args[1].strip().strip("/")
        return f"https://{host_path}"
    if family == "moka" and len(args) >= 3:
        return f"https://app.mokahr.com/social-recruitment/{args[1]}/{args[2]}"
    if family == "beisen" and len(args) >= 2:
        return f"https://{args[1]}.zhiye.com"
    return DIRECT_PORTAL.get(key, "")


def all_company_specs(radar) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for key, spec in sorted(radar.LOCAL_PARSERS.items()):
        args = " ".join(str(x) for x in (spec.get("args") or [])).lower()
        if any(token in args for token in (
            "feishu.py", "moka.py", "beisen.py", "bytedance.py", "tencent.py", "netease.py", "jd.py", "baidu.py", "unitree.py"
        )):
            out.append((key, spec))
    return out


def source_is_company_official(job: dict[str, Any]) -> bool:
    source = clean(job.get("source")).lower()
    label = clean(job.get("source_label")).lower()
    return source.startswith("china-company:") or source.startswith("china-official:") or "官方招聘" in label or "公司官网" in label


def geo_kind(location: str) -> str:
    loc = clean(location)
    if not loc:
        return "unknown"
    if any(x.lower() in loc.lower() for x in CHINA_GEO):
        return "china"
    if FOREIGN_ONLY.search(loc):
        return "foreign"
    # Chinese text without an explicit city is more likely a domestic location
    # than an overseas English-only location; keep it as unknown, not China.
    return "unknown"


def career_kind(job: dict[str, Any]) -> str:
    role = clean(job.get("role"))
    text = " ".join(clean(job.get(k)) for k in ("role", "batch", "graduation", "education", "jd"))[:1800]
    if EARLY.search(text):
        return "early"
    if SOCIAL.search(clean(job.get("batch"))):
        return "social"
    if SENIOR.search(role):
        return "senior"
    return "unknown"


def eligible(job: dict[str, Any], *, official: bool = False) -> tuple[bool, str]:
    geo = geo_kind(clean(job.get("location")))
    career = career_kind(job)
    if geo == "foreign":
        return False, "foreign"
    if career == "social":
        return False, "social"
    if career == "senior":
        return False, "senior"
    # Company-official feeds are allowed to keep an unknown career label when
    # the job is domestic.  Many Chinese career sites omit an explicit "校招"
    # token on each row even when the portal/batch is campus-oriented.
    if official and geo in {"china", "unknown"}:
        return True, career
    # Non-company supplemental rows need a positive campus signal or China geo.
    if career == "early" or geo == "china":
        return True, career
    return False, "irrelevant"


def fetch_company(radar, item: tuple[str, dict[str, Any]]) -> tuple[str, str, str, str, list[dict[str, Any]]]:
    key, spec = item
    hint = company_hint(key, spec)
    family = adapter_family(spec)
    portal = portal_for(key, spec)
    rows, _ = radar.fetch_local(spec, name=key, keyword="")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        job = normalize_row(row, source=f"china-company:{family}:{key}", label=f"公司官网 · {hint}", company_hint=hint)
        if not job:
            continue
        if not clean(job.get("apply_url")) and portal:
            job["apply_url"] = portal
        if not clean(job.get("notice_url")) and portal:
            job["notice_url"] = portal
        job["source_url"] = clean(job.get("apply_url") or job.get("notice_url") or portal)
        ok, _ = eligible(job, official=True)
        if ok:
            normalized.append(job)
    return key, hint, family, portal, normalized


def sort_key(job: dict[str, Any]) -> tuple[Any, ...]:
    loc = clean(job.get("location"))
    early = career_kind(job) == "early"
    beijing = "北京" in loc
    tier1 = any(c in loc for c in TIER1)
    official = source_is_company_official(job)
    direct = bool(clean(job.get("apply_url") or job.get("notice_url")))
    return (
        1 if early else 0,
        1 if beijing else 0,
        1 if tier1 else 0,
        1 if official else 0,
        1 if direct else 0,
        clean(job.get("updated_at")), clean(job.get("company")), clean(job.get("role")),
    )


def main() -> int:
    radar = load_radar()
    specs = all_company_specs(radar)
    existing_payload = load_json(JOBS_PATH, {"jobs": []})
    existing = existing_payload.get("jobs", []) if isinstance(existing_payload, dict) else []

    retained_existing: list[dict[str, Any]] = []
    filtered = Counter()
    for job in existing if isinstance(existing, list) else []:
        if not isinstance(job, dict):
            continue
        ok, reason = eligible(job, official=source_is_company_official(job))
        if ok:
            retained_existing.append(job)
        else:
            filtered[reason] += 1

    jobs: list[dict[str, Any]] = []
    failures: list[str] = []
    company_counts: dict[str, int] = {}
    family_counts: Counter[str] = Counter()
    portals: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_company, radar, item): item[0] for item in specs}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                _, company, family, portal, rows = fut.result()
                company_counts[company] = len(rows)
                family_counts[family] += len(rows)
                if portal:
                    portals[company] = portal
                jobs.extend(rows)
            except Exception as exc:
                failures.append(f"{key}: {type(exc).__name__}: {clean(exc)[:150]}")

    # Prefer fresh official-company identity/links even if an older cached row has
    # a longer JD body from another source.
    official_by_key = {canonical_key(j): j for j in jobs}
    merged = merge_catalog([*retained_existing, *jobs])
    for job in merged:
        official = official_by_key.get(canonical_key(job))
        if official:
            for field in ("source", "source_label", "source_url", "apply_url", "notice_url"):
                if clean(official.get(field)):
                    job[field] = official[field]
        elif not clean(job.get("apply_url")):
            portal = portals.get(clean(job.get("company")), "")
            if portal:
                job["apply_url"] = portal
                job["notice_url"] = clean(job.get("notice_url")) or portal

    merged.sort(key=sort_key, reverse=True)
    merged = merged[:MAX_CATALOG]
    now = utc_now()
    JOBS_PATH.write_text(json.dumps({"schema_version": 3, "generated_at": now, "jobs": merged}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    beijing = sum("北京" in clean(j.get("location")) for j in merged)
    tier1 = sum(any(c in clean(j.get("location")) for c in TIER1) for j in merged)
    early = sum(career_kind(j) == "early" for j in merged)
    official_count = sum(source_is_company_official(j) for j in merged)
    linked = sum(bool(clean(j.get("apply_url") or j.get("notice_url"))) for j in merged)
    ok_companies = sum(v > 0 for v in company_counts.values())
    status_row = GroupStatus(
        name="china-company-official",
        label="中国企业官网招聘 · 校招/初阶优先",
        url="https://github.com/simonlin1212/Hiring-Radar",
        ok=bool(jobs), count=len(jobs),
        error="" if jobs else (failures[0] if failures else "no company-official jobs returned"),
        diagnostics={
            "adapters_attempted": len(specs),
            "companies_with_jobs": ok_companies,
            "companies_zero_or_failed": len(specs) - ok_companies,
            "adapter_rows": dict(family_counts),
            "fresh_official_rows": len(jobs),
            "retained_domestic_cache": len(retained_existing),
            "catalog_count": len(merged),
            "beijing_count": beijing,
            "tier1_count": tier1,
            "early_signal_count": early,
            "company_official_count": official_count,
            "direct_link_count": linked,
            "direct_link_ratio": round(linked / max(1, len(merged)), 4),
            "filtered_previous": dict(filtered),
            "top_companies": sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:30],
            "failures_sample": failures[:30],
            "policy": "company-official public career surfaces; no credentials/CAPTCHA/proxy or access-control bypass",
        },
    )

    status = load_json(STATUS_PATH, {"sources": []})
    retired = {
        "china-official-federation", "official-ats-discovery", "public-remote-boards", "offerjack", "gank-public-search",
    }
    sources = [s for s in status.get("sources", []) if isinstance(s, dict) and s.get("name") not in retired | {status_row.name}]
    sources.insert(0, asdict(status_row))
    out_status = {
        "generated_at": now,
        "catalog_count": len(merged),
        "catalog_mode": "china-campus-first",
        "catalog_cap": MAX_CATALOG,
        "sources": sources,
        "retired_sources": sorted(retired),
        "china_focus": {
            "beijing_count": beijing,
            "tier1_count": tier1,
            "early_signal_count": early,
            "company_official_count": official_count,
            "direct_link_ratio": round(linked / max(1, len(merged)), 4),
        },
    }
    STATUS_PATH.write_text(json.dumps(out_status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"china official campus: adapters={len(specs)} companies_ok={ok_companies} fresh={len(jobs)} "
        f"catalog={len(merged)} beijing={beijing} tier1={tier1} early={early} linked={linked}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
