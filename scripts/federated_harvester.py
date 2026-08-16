#!/usr/bin/env python3
"""Federated official-job harvester for Path to Offer v0.6.

This layer exists because a useful candidate product cannot depend on a 70-row
aggregator cache.  It federates *public, unauthenticated* employer/ATS surfaces
and normalizes them into the same static catalogue consumed by GitHub Pages.

Collection strategy
-------------------
1. Reuse a pinned MIT-licensed Hiring-Radar checkout at runtime for its tested
   public ATS / Chinese-career-site adapters.  We intentionally skip Moka
   adapters because their client-side encrypted payload path is outside this
   project's conservative public-surface boundary.
2. Run all safe Chinese official/ATS seeds (direct company APIs, Feishu Hire,
   Beisen) concurrently.
3. Use public 2027 job-list repositories only as *board discovery documents*:
   extract outgoing official ATS URLs, then query Greenhouse/Ashby/Lever/
   SmartRecruiters/Recruitee/Breezy/BambooHR/Personio directly.  Their job rows
   are never copied into our catalogue.
4. Pull the public remote job boards supported by Hiring-Radar.
5. Merge with the existing catalogue, source-independently deduplicate, retain
   provenance, truncate catalogue JD text for browser performance, and expose
   measured source health.

Security / access boundary
--------------------------
- no account credentials, cookies, CAPTCHA solving, proxy rotation, stealth or
  anti-bot bypass;
- no replay of endpoints that reject anonymous access;
- fixed public discovery documents and official ATS hosts only;
- Moka encrypted/obfuscated adapters are skipped;
- every source fails independently; a source outage never erases other data.

The harvester targets breadth, not a promise of literally every job on the
internet.  `data/source_status.json` is the source of truth for measured live
coverage on each run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from scripts.aggregate_jobs import DATA, JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now
from scripts.merge_public_tables import merge_catalog

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "sources" / "federated_sources.json"
RADAR_DIR = Path(os.getenv("PTO_HIRING_RADAR_DIR", "/tmp/hiring-radar"))
MAX_WORKERS = max(2, min(24, int(os.getenv("PTO_FEDERATED_WORKERS", "12"))))
MAX_JD_CHARS = max(200, int(os.getenv("PTO_CATALOG_JD_CHARS", "1400")))
MAX_CATALOG = max(1000, int(os.getenv("PTO_MAX_CATALOG", "60000")))
HTTP_TIMEOUT = 25
UA = "PathToOfferBot/0.6 (+https://github.com/MLliu6/26-27-path-to-offer)"


@dataclass
class GroupStatus:
    name: str
    label: str
    url: str
    ok: bool
    count: int = 0
    error: str = ""
    diagnostics: dict[str, Any] | None = None


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_radar():
    path = RADAR_DIR / "hiring_radar.py"
    if not path.exists():
        raise RuntimeError(f"pinned Hiring-Radar checkout missing: {path}")
    spec = importlib.util.spec_from_file_location("pto_hiring_radar", path)
    if not spec or not spec.loader:
        raise RuntimeError("cannot load Hiring-Radar module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._load_company_seeds()
    return module


def compact_text(value: Any, limit: int = MAX_JD_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def normalize_row(row: dict[str, Any], *, source: str, label: str, company_hint: str = "") -> dict[str, Any] | None:
    role = clean(row.get("title") or row.get("role") or row.get("position"))
    company = clean(row.get("company") or row.get("company_name") or company_hint)
    if not role or not company:
        return None
    location = clean(row.get("location") or row.get("city"))
    url = clean(row.get("apply_url") or row.get("url"))
    updated = clean(row.get("date_updated") or row.get("date") or row.get("updated_at"))
    # Hiring-Radar exposes a formatter for epoch / ISO dates. Keep failure local.
    try:
        updated = RADAR._fmt_date(updated)  # type: ignore[name-defined]
    except Exception:
        updated = updated[:10] if len(updated) >= 10 else updated
    job = {
        "source": source,
        "source_label": label,
        "source_url": url,
        "updated_at": updated,
        "company": company,
        "department": clean(row.get("dept") or row.get("department") or row.get("team")),
        "role": role,
        "location": location,
        "salary": clean(row.get("comp") or row.get("salary")),
        "batch": clean(row.get("type") or row.get("batch")),
        "company_type": "",
        "industry": "",
        "graduation": "",
        "education": "",
        "notice_url": url,
        "apply_url": url,
        "jd": compact_text(row.get("jd") or row.get("description") or role),
        "tags": [],
        "observed_via": "official-public-federation",
    }
    job["id"] = stable_id(company, role, location, url)
    return job


def safe_local_specs(radar) -> list[tuple[str, dict[str, Any]]]:
    """All direct/Feishu/Beisen local parsers, explicitly excluding Moka."""
    out: list[tuple[str, dict[str, Any]]] = []
    for key, spec in sorted(radar.LOCAL_PARSERS.items()):
        args = " ".join(str(x) for x in (spec.get("args") or []))
        if "moka.py" in args.lower():
            continue
        if not any(token in args.lower() for token in (
            "feishu.py", "beisen.py", "bytedance.py", "tencent.py", "netease.py",
            "jd.py", "baidu.py", "unitree.py"
        )):
            continue
        out.append((key, spec))
    return out


def infer_company_hint(spec: dict[str, Any], key: str) -> str:
    args = [str(x) for x in (spec.get("args") or [])]
    # Generic Feishu/Beisen parsers receive the human company name as arg 3/2.
    if args and "feishu.py" in args[0] and len(args) >= 3:
        return args[2]
    if args and "beisen.py" in args[0] and len(args) >= 3:
        return args[2]
    direct = {"bytedance":"字节跳动", "tencent":"腾讯", "netease":"网易", "jd":"京东", "baidu":"百度", "unitree":"宇树科技"}
    return direct.get(key, key)


def collect_china_official(radar) -> tuple[list[dict[str, Any]], GroupStatus]:
    specs = safe_local_specs(radar)
    jobs: list[dict[str, Any]] = []
    failures: list[str] = []
    company_counts: dict[str, int] = {}

    def worker(item: tuple[str, dict[str, Any]]):
        key, spec = item
        rows, src = radar.fetch_local(spec, name=key, keyword="")
        hint = infer_company_hint(spec, key)
        norm = [j for r in rows for j in [normalize_row(r, source=f"china-official:{key}", label=f"官方招聘 · {hint}", company_hint=hint)] if j]
        return key, hint, norm, src

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(worker, item): item[0] for item in specs}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                _, hint, rows, _ = fut.result()
                company_counts[hint] = len(rows)
                jobs.extend(rows)
            except Exception as exc:
                failures.append(f"{key}: {type(exc).__name__}: {clean(exc)[:120]}")

    ok_companies = sum(1 for n in company_counts.values() if n > 0)
    status = GroupStatus(
        name="china-official-federation",
        label="中国企业官方招聘 / Feishu / Beisen",
        url="https://github.com/simonlin1212/Hiring-Radar",
        ok=bool(jobs), count=len(jobs),
        error="" if jobs else (failures[0] if failures else "no public jobs returned"),
        diagnostics={
            "adapters_attempted": len(specs),
            "companies_with_jobs": ok_companies,
            "companies_zero_or_failed": len(specs) - ok_companies,
            "top_companies": sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:20],
            "failures_sample": failures[:20],
            "moka_skipped": True,
        },
    )
    return jobs, status


def strip_markdown(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return clean(value).strip(" |-:")


def discover_board_specs(config: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    """Extract official ATS board identities from public discovery documents.

    We do not ingest their job rows.  A line containing an official ATS URL is
    only used to learn the employer name and public board slug; the official
    ATS is queried independently afterwards.
    """
    found: dict[tuple[str, str], dict[str, str]] = {}
    failures: list[str] = []
    session = requests.Session()
    headers = {"User-Agent": UA, "Accept": "text/plain,text/markdown,*/*"}
    for src in config.get("ats_discovery_documents", []):
        url = clean(src.get("url")) if isinstance(src, dict) else clean(src)
        if not url:
            continue
        try:
            r = session.get(url, timeout=HTTP_TIMEOUT, headers=headers)
            r.raise_for_status()
            for line in r.text.splitlines():
                urls = re.findall(r"https?://[^\s)<>\]]+", line)
                if not urls:
                    continue
                cells = [strip_markdown(x) for x in line.split("|") if strip_markdown(x)]
                company_hint = cells[0][:80] if cells else ""
                for raw in urls:
                    raw = raw.rstrip(".,;\"'")
                    try:
                        u = urlparse(raw)
                        host = (u.hostname or "").lower()
                        parts = [p for p in u.path.split("/") if p]
                        kind = slug = ""
                        if host in {"boards.greenhouse.io","job-boards.greenhouse.io","boards.eu.greenhouse.io","job-boards.eu.greenhouse.io"} and parts:
                            kind, slug = "greenhouse", parts[0]
                        elif host == "jobs.ashbyhq.com" and parts:
                            kind, slug = "ashby", parts[0]
                        elif host == "jobs.lever.co" and parts:
                            kind, slug = "lever", parts[0]
                        elif host == "jobs.smartrecruiters.com" and parts:
                            kind, slug = "smartrecruiters", parts[0]
                        elif host.endswith(".recruitee.com"):
                            kind, slug = "recruitee", host.split(".")[0]
                        elif host.endswith(".breezy.hr"):
                            kind, slug = "breezy", host.split(".")[0]
                        elif host.endswith(".bamboohr.com"):
                            kind, slug = "bamboohr", host.split(".")[0]
                        elif ".jobs.personio." in host:
                            kind, slug = "personio", host.split(".jobs.personio.")[0]
                        if not kind or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", slug):
                            continue
                        key = (kind, slug.lower())
                        old = found.get(key)
                        if old is None or (not old.get("company") and company_hint):
                            found[key] = {"kind":kind, "slug":slug, "company":company_hint or slug, "discovered_from":url}
                    except Exception:
                        continue
        except Exception as exc:
            failures.append(f"{url}: {type(exc).__name__}: {clean(exc)[:120]}")
    cap = int(config.get("max_discovered_boards", 700))
    return list(found.values())[:cap], failures


def fetch_board(radar, spec: dict[str, str]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    kind, slug, company = spec["kind"], spec["slug"], spec.get("company") or spec["slug"]
    fn_map: dict[str, Callable[[str], tuple[list[dict[str, Any]], str]]] = {
        "greenhouse": radar.fetch_greenhouse,
        "ashby": radar.fetch_ashby,
        "lever": radar.fetch_lever,
        "smartrecruiters": radar.fetch_smartrecruiters,
        "recruitee": radar.fetch_recruitee,
        "breezy": radar.fetch_breezy,
        "bamboohr": radar.fetch_bamboohr,
        "personio": radar.fetch_personio,
    }
    rows, _ = fn_map[kind](slug)
    label = f"Official ATS · {kind.title()} · {company}"
    norm = [j for r in rows for j in [normalize_row(r, source=f"ats:{kind}:{slug}", label=label, company_hint=company)] if j]
    return spec, norm


def collect_discovered_ats(radar, config: dict[str, Any]) -> tuple[list[dict[str, Any]], GroupStatus]:
    specs, discovery_failures = discover_board_specs(config)
    jobs: list[dict[str, Any]] = []
    failures: list[str] = []
    successes: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(fetch_board, radar, spec): spec for spec in specs}
        for fut in as_completed(futs):
            spec = futs[fut]
            try:
                resolved, rows = fut.result()
                if rows:
                    successes.append((f"{resolved['kind']}:{resolved['slug']}", len(rows)))
                    jobs.extend(rows)
            except Exception as exc:
                failures.append(f"{spec['kind']}:{spec['slug']}: {type(exc).__name__}: {clean(exc)[:100]}")
    status = GroupStatus(
        name="official-ats-discovery",
        label="全球官方 ATS 联邦",
        url="https://github.com/speedyapply/2027-SWE-College-Jobs",
        ok=bool(jobs), count=len(jobs),
        error="" if jobs else ((failures or discovery_failures or ["no ATS boards discovered"])[0]),
        diagnostics={
            "boards_discovered": len(specs),
            "boards_with_jobs": len(successes),
            "top_boards": sorted(successes, key=lambda x:x[1], reverse=True)[:20],
            "discovery_failures": discovery_failures[:10],
            "fetch_failures_sample": failures[:20],
            "policy": "discovery documents provide only ATS identities; catalogue rows come from official ATS APIs",
        },
    )
    return jobs, status


def collect_remote_boards(radar) -> tuple[list[dict[str, Any]], GroupStatus]:
    jobs: list[dict[str, Any]] = []
    failures: list[str] = []
    counts: dict[str, int] = {}
    for name, fn in radar._BOARD_ALL:
        try:
            rows, _ = fn()
            normalized = [j for r in rows for j in [normalize_row(r, source=f"remote-board:{name}", label=f"Public board · {name}")] if j]
            counts[name] = len(normalized)
            jobs.extend(normalized)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {clean(exc)[:120]}")
    return jobs, GroupStatus(
        name="public-remote-boards", label="公开远程招聘板", url="", ok=bool(jobs), count=len(jobs),
        error="" if jobs else (failures[0] if failures else "no rows"),
        diagnostics={"counts":counts, "failures":failures[:10]},
    )


def compact_catalog(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = merge_catalog(jobs)
    for j in merged:
        j["jd"] = compact_text(j.get("jd"), MAX_JD_CHARS)
        # Avoid provenance arrays exploding after broad source overlap.
        if isinstance(j.get("source_labels"), list): j["source_labels"] = j["source_labels"][:6]
        if isinstance(j.get("source_urls"), list): j["source_urls"] = j["source_urls"][:6]
    merged.sort(key=lambda j:(clean(j.get("updated_at")), clean(j.get("company")), clean(j.get("role"))), reverse=True)
    return merged[:MAX_CATALOG]


def write_outputs(new_jobs: list[dict[str, Any]], statuses: list[GroupStatus]) -> None:
    old_feed = load_json(JOBS_PATH, {"jobs":[]})
    old_jobs = old_feed.get("jobs",[]) if isinstance(old_feed,dict) else []
    combined = compact_catalog([*(old_jobs if isinstance(old_jobs,list) else []), *new_jobs])
    now = utc_now()
    # Minified catalogue is materially smaller at 10k–60k rows and loads faster
    # from GitHub Pages.  Source health remains pretty-printed for auditing.
    JOBS_PATH.write_text(json.dumps({"schema_version":3,"generated_at":now,"jobs":combined}, ensure_ascii=False, separators=(",",":"))+"\n", encoding="utf-8")

    old_status = load_json(STATUS_PATH, {"sources":[]})
    replace = {s.name for s in statuses}
    sources = [s for s in old_status.get("sources",[]) if isinstance(s,dict) and s.get("name") not in replace]
    sources.extend(asdict(s) for s in statuses)
    STATUS_PATH.write_text(json.dumps({
        "generated_at":now,
        "catalog_count":len(combined),
        "catalog_target":10000,
        "sources":sources,
        "federation":{
            "hiring_radar_commit": os.getenv("PTO_HIRING_RADAR_COMMIT", "f49ec607e4cb89091a9447c9f527e43d0afdc6a4"),
            "jd_chars_per_record":MAX_JD_CHARS,
            "catalog_cap":MAX_CATALOG,
        },
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"federated catalogue: {len(combined)} rows; added/raw={len(new_jobs)}")


def main() -> int:
    global RADAR
    DATA.mkdir(parents=True, exist_ok=True)
    config = load_json(CONFIG_PATH, {})
    try:
        RADAR = load_radar()
    except Exception as exc:
        print(f"federated harvester unavailable: {exc}", file=sys.stderr)
        return 0

    jobs: list[dict[str, Any]] = []
    statuses: list[GroupStatus] = []
    for collector in (
        lambda: collect_china_official(RADAR),
        lambda: collect_discovered_ats(RADAR, config),
        lambda: collect_remote_boards(RADAR),
    ):
        try:
            rows, status = collector(); jobs.extend(rows); statuses.append(status)
            print(f"{status.name}: {'ok' if status.ok else 'fail'} {status.count}")
        except Exception as exc:
            statuses.append(GroupStatus("federation-internal","Federated harvester","",False,0,clean(exc)[:200]))

    write_outputs(jobs, statuses)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
