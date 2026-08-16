#!/usr/bin/env python3
"""Build Path to Offer's China-first *campus-official* catalogue.

The previous v0.7 prototype reused a generic company-career adapter set. Live
adversarial review caught an important semantic bug: several of those adapters
were explicitly social/experienced portals, so a domestic row was not enough
evidence that it belonged in a campus-recruiting product.

This implementation uses @ha7ch/job-pro's unified `--scope campus` contract as a
runtime adapter library. The package exposes one client per Chinese employer and
routes the request to that employer's own public careers API / public ATS tenant.
We pin the package version in CI. Third-party Liepin fallback adapters and the
international-only HoYoverse board are excluded from this catalogue.

For every eligible company we execute:

    job-pro <company> all --scope campus --compact

An adapter that cannot prove/query a campus channel fails or is skipped instead
of silently leaking social jobs. Successful source refreshes replace that
company's previous cache so closed positions disappear; only a failed source is
allowed to retain its last known campus snapshot.

No credentials, login sessions, CAPTCHA solving, proxy rotation or submit APIs
are used. This job is read-only job discovery. Application links point back to
the employer's own campus/careers surface.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now
from scripts.merge_public_tables import merge_catalog

JOBPRO_BIN = os.getenv("PTO_JOBPRO_BIN", "job-pro")
JOBPRO_VERSION = os.getenv("PTO_JOBPRO_VERSION", "1.2.1")
MAX_WORKERS = max(2, min(12, int(os.getenv("PTO_JOBPRO_WORKERS", "6"))))
SOURCE_TIMEOUT = max(15, min(180, int(os.getenv("PTO_JOBPRO_TIMEOUT", "75"))))
MAX_CATALOG = max(1000, int(os.getenv("PTO_CHINA_MAX_CATALOG", "25000")))
MAX_PAGES = max(5, min(100, int(os.getenv("PTO_JOBPRO_MAX_PAGES", "60"))))

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
    r"Ireland|Portugal|Romania|Hungary|Czech|Austria|Belgium|Thailand|Indonesia)\b",
    re.I,
)
SENIOR = re.compile(
    r"(?:资深|高级专家|首席|总监|负责人|技术专家|架构师|研究专家|主任|"
    r"\b(?:senior|staff|principal|lead|director|head|architect|distinguished)\b)",
    re.I,
)

EXCLUDED_FAMILY_TOKENS = ("liepin", "smartrecruiters", "greenhouse / lever (intl arm)")
EXCLUDED_COMPANIES = {"hoyoverse", "hikvision", "cicc", "cainiao", "webank"}

NAME_OVERRIDES = {
    "tencent": "腾讯", "bytedance": "字节跳动", "alibaba": "阿里巴巴", "meituan": "美团",
    "xiaohongshu": "小红书", "jd": "京东", "kuaishou": "快手", "xiaomi": "小米", "baidu": "百度",
    "netease": "网易", "didi": "滴滴", "bilibili": "哔哩哔哩", "pdd": "拼多多", "nio": "蔚来",
    "huawei": "华为", "weibo": "微博", "mihoyo": "米哈游", "pingan": "平安", "sensetime": "商汤",
    "trip": "携程", "unitree": "宇树科技", "byd": "比亚迪", "antgroup": "蚂蚁集团", "liauto": "理想汽车",
    "moonshot": "月之暗面", "zhipu": "智谱AI", "iqiyi": "爱奇艺", "megvii": "旷视", "agibot": "智元机器人",
    "deepseek": "DeepSeek", "zerooneai": "零一万物", "galaxyuniversal": "银河通用", "stepfun": "阶跃星辰",
    "baichuan": "百川智能", "xpeng": "小鹏汽车", "iflytek": "科大讯飞", "sf": "顺丰", "geely": "吉利",
    "horizonrobotics": "地平线", "cambricon": "寒武纪", "oppo": "OPPO", "vivo": "vivo", "minimax": "MiniMax",
}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def parse_json_stdout(text: str) -> Any:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    raise RuntimeError(f"no JSON payload in command output: {(text or '')[-240:]}")


def run_cli(args: list[str], timeout: int = SOURCE_TIMEOUT) -> tuple[Any, str]:
    proc = subprocess.run(
        [JOBPRO_BIN, *args], text=True, capture_output=True, timeout=timeout,
        check=False, env={**os.environ, "NO_COLOR": "1"},
    )
    if proc.returncode != 0:
        msg = clean((proc.stderr or proc.stdout)[-600:])
        raise RuntimeError(msg or f"exit code {proc.returncode}")
    return parse_json_stdout(proc.stdout), proc.stderr


def company_directory() -> list[dict[str, str]]:
    payload, _ = run_cli(["list", "--compact"], timeout=30)
    if not isinstance(payload, list):
        raise RuntimeError("job-pro list --compact returned a non-list payload")
    out: list[dict[str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        key, family = clean(row.get("key")), clean(row.get("family"))
        if not key or key in EXCLUDED_COMPANIES:
            continue
        if any(token in family.lower() for token in EXCLUDED_FAMILY_TOKENS):
            continue
        out.append({"key": key, "family": family, "source": clean(row.get("source")), "label": clean(row.get("label"))})
    return out


def company_name(spec: dict[str, str]) -> str:
    if spec["key"] in NAME_OVERRIDES:
        return NAME_OVERRIDES[spec["key"]]
    tail = spec.get("label", "").split("/")[-1].split("—")[0].strip()
    return tail or spec["key"]


def source_url(spec: dict[str, str]) -> str:
    raw = clean(spec.get("source"))
    if not raw:
        return ""
    first = raw.split("+")[0].strip()
    return first if first.startswith("http") else f"https://{first}"


def geo_kind(location: str) -> str:
    loc = clean(location)
    if not loc:
        return "unknown"
    if any(x.lower() in loc.lower() for x in CHINA_GEO):
        return "china"
    if FOREIGN_ONLY.search(loc):
        return "foreign"
    return "unknown"


def source_key(job: dict[str, Any]) -> str:
    source = clean(job.get("source"))
    prefix = "china-campus:jobpro:"
    return source[len(prefix):] if source.startswith(prefix) else ""


def old_v07_job(job: dict[str, Any]) -> bool:
    return bool(source_key(job)) and "校园招聘" in clean(job.get("batch"))


def normalize_position(spec: dict[str, str], raw: dict[str, Any]) -> dict[str, Any] | None:
    title = clean(raw.get("title") or raw.get("position") or raw.get("name"))
    if not title or SENIOR.search(title):
        return None
    location = clean(raw.get("work_cities") or raw.get("location") or raw.get("workCities"))
    if geo_kind(location) == "foreign":
        return None
    post_id = clean(raw.get("post_id") or raw.get("postId") or raw.get("id"))
    apply_url = clean(raw.get("apply_url") or raw.get("applyUrl") or raw.get("url"))
    if apply_url and not apply_url.startswith(("http://", "https://")):
        apply_url = ""
    portal = source_url(spec)
    company = company_name(spec)
    project = clean(raw.get("project") or raw.get("project_name"))
    recruit_label = clean(raw.get("recruit_label") or raw.get("recruitLabel"))
    bgs = clean(raw.get("bgs") or raw.get("department") or raw.get("direction"))
    batch_parts = [x for x in ("校园招聘", project, recruit_label) if x]
    batch = " · ".join(dict.fromkeys(batch_parts))
    description = clean(raw.get("description") or raw.get("jd"))
    requirements = clean(raw.get("requirements") or raw.get("request"))
    jd = " ".join(x for x in (title, project, recruit_label, bgs, description, requirements) if x) or title
    url = apply_url or portal
    job = {
        "source": f"china-campus:jobpro:{spec['key']}",
        "source_label": f"企业校园招聘官网 · {company}",
        "source_url": portal,
        "updated_at": clean(raw.get("updated_at") or raw.get("publish_time") or raw.get("publishDate")),
        "company": company, "department": bgs or project, "role": title, "location": location,
        "salary": clean(raw.get("salary")), "batch": batch, "company_type": "", "industry": "",
        "graduation": "应届 / 校招", "education": clean(raw.get("education") or raw.get("degree_required")),
        "notice_url": url, "apply_url": url, "jd": jd[:1600],
        "tags": ["校园招聘", "企业官网", spec.get("family", "")],
        "observed_via": f"job-pro@{JOBPRO_VERSION}:scope-campus", "external_id": post_id,
    }
    job["id"] = stable_id(company, title, location, url or post_id)
    return job


def fetch_company(spec: dict[str, str]) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any]]:
    payload, _ = run_cli([spec["key"], "all", "--scope", "campus", "--page-size", "100", "--max-pages", str(MAX_PAGES), "--compact"])
    if not isinstance(payload, dict):
        raise RuntimeError("non-object response")
    if payload.get("ok") is False:
        raise RuntimeError(clean(payload.get("message")) or "upstream returned ok:false")
    rows = payload.get("positions")
    if not isinstance(rows, list):
        rows = payload.get("jobs") or payload.get("results") or []
    if not isinstance(rows, list):
        raise RuntimeError(f"positions payload has unexpected type: {type(rows).__name__}")
    normalized = [j for raw in rows if isinstance(raw, dict) for j in [normalize_position(spec, raw)] if j]
    return spec, normalized, {
        "reported_total": payload.get("total"), "reported_fetched": payload.get("fetched"),
        "truncated": bool(payload.get("truncated")), "raw_rows": len(rows), "kept_rows": len(normalized),
    }


def rank(job: dict[str, Any]) -> tuple[Any, ...]:
    loc, role = clean(job.get("location")), clean(job.get("role"))
    beijing, tier1 = "北京" in loc, any(city in loc for city in TIER1)
    tech = bool(re.search(r"(?:算法|研发|开发|工程师|研究|Infra|CUDA|GPU|大模型|AI|芯片|编译|系统|后端|前端|测试|数据|硬件)", role, re.I))
    return (1 if beijing else 0, 1 if tier1 else 0, 1 if tech else 0, clean(job.get("updated_at")), clean(job.get("company")), role)


def main() -> int:
    directory = company_directory()
    old_payload = load_json(JOBS_PATH, {"jobs": []})
    old_jobs = old_payload.get("jobs", []) if isinstance(old_payload, dict) else []
    old_by_company: dict[str, list[dict[str, Any]]] = {}
    for job in old_jobs if isinstance(old_jobs, list) else []:
        if isinstance(job, dict) and old_v07_job(job):
            old_by_company.setdefault(source_key(job), []).append(job)

    fresh: list[dict[str, Any]] = []
    retained_failure_cache: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    success_keys: set[str] = set()
    failures: list[str] = []
    skipped_scope: list[str] = []
    foreign_filtered = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_company, spec): spec for spec in directory}
        for fut in as_completed(futures):
            spec, key = futures[fut], futures[fut]["key"]
            try:
                resolved, rows, diag = fut.result()
                success_keys.add(key); fresh.extend(rows)
                statuses.append({"key": key, "company": company_name(resolved), "family": resolved["family"], "source": resolved["source"], "ok": True, "count": len(rows), **diag})
            except Exception as exc:
                msg = clean(exc)[:260]
                if "does not support --scope campus" in msg:
                    skipped_scope.append(key)
                else:
                    failures.append(f"{key}: {msg}")
                cached = old_by_company.get(key, []); retained_failure_cache.extend(cached)
                statuses.append({"key": key, "company": company_name(spec), "family": spec["family"], "source": spec["source"], "ok": False, "count": len(cached), "retained_cache": len(cached), "error": msg})

    combined = merge_catalog([*fresh, *retained_failure_cache])
    cleaned: list[dict[str, Any]] = []
    for job in combined:
        if geo_kind(clean(job.get("location"))) == "foreign":
            foreign_filtered += 1; continue
        if SENIOR.search(clean(job.get("role"))):
            continue
        cleaned.append(job)
    cleaned.sort(key=rank, reverse=True); cleaned = cleaned[:MAX_CATALOG]

    now = utc_now()
    JOBS_PATH.write_text(json.dumps({"schema_version": 3, "generated_at": now, "jobs": cleaned}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    beijing = sum("北京" in clean(j.get("location")) for j in cleaned)
    tier1 = sum(any(city in clean(j.get("location")) for city in TIER1) for j in cleaned)
    linked = sum(bool(clean(j.get("apply_url"))) for j in cleaned)
    companies_in_catalog = len({clean(j.get("company")) for j in cleaned if clean(j.get("company"))})
    family_counts = Counter(s["family"] for s in statuses if s.get("ok"))
    company_counts = sorted(((s["company"], int(s.get("count") or 0)) for s in statuses if s.get("ok")), key=lambda x: x[1], reverse=True)

    source_status = {
        "name": "china-campus-company-official", "label": "中国企业校园招聘官网联邦",
        "url": "https://www.npmjs.com/package/@ha7ch/job-pro", "ok": bool(cleaned), "count": len(cleaned),
        "error": "" if cleaned else (failures[0] if failures else "no campus jobs returned"),
        "diagnostics": {
            "adapter_library": f"@ha7ch/job-pro@{JOBPRO_VERSION}", "scope": "campus",
            "directory_official_candidates": len(directory), "companies_ok": len(success_keys), "companies_in_catalog": companies_in_catalog,
            "companies_skipped_by_scope": sorted(skipped_scope), "companies_failed": len(failures),
            "fresh_rows": len(fresh), "retained_failure_cache": len(retained_failure_cache),
            "beijing_count": beijing, "tier1_count": tier1, "direct_link_count": linked,
            "direct_link_ratio": round(linked / max(1, len(cleaned)), 4), "foreign_rows_filtered": foreign_filtered,
            "family_counts": dict(family_counts), "top_companies": company_counts[:35],
            "company_status": sorted(statuses, key=lambda s: (not bool(s.get("ok")), s.get("company", ""))),
            "failures_sample": failures[:25], "excluded_third_party": sorted(EXCLUDED_COMPANIES),
            "policy": "employer public campus scope only; third-party fallback, social scope, credentials, CAPTCHA/proxy/access-control bypass excluded",
        },
    }
    status_out = {
        "generated_at": now, "catalog_count": len(cleaned), "catalog_mode": "china-campus-official", "catalog_cap": MAX_CATALOG,
        "sources": [source_status],
        "china_focus": {
            "beijing_count": beijing, "tier1_count": tier1, "campus_proven_count": len(cleaned),
            "company_official_count": len(cleaned), "companies_in_catalog": companies_in_catalog,
            "direct_link_ratio": round(linked / max(1, len(cleaned)), 4), "foreign_count": 0,
        },
        "adapter_library": {"name": "@ha7ch/job-pro", "version": JOBPRO_VERSION, "scope": "campus"},
    }
    STATUS_PATH.write_text(json.dumps(status_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"china campus official: directory={len(directory)} ok={len(success_keys)} skipped_scope={len(skipped_scope)} fresh={len(fresh)} cached={len(retained_failure_cache)} catalog={len(cleaned)} companies={companies_in_catalog} beijing={beijing} tier1={tier1} linked={linked} bytes_precompact={JOBS_PATH.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
