#!/usr/bin/env python3
"""Public-job aggregation for Path to Offer.

Design constraints:
- Public, unauthenticated sources only.
- Respect robots.txt when present.
- No CAPTCHA/login/anti-bot bypass.
- One polite fetch per page per scheduled run.
- Preserve the previous feed when every source fails, so a temporary outage does not erase data.

The OfferJack adapter is an independent black-box compatibility adapter for the site's
publicly rendered/indexable job table. It does not copy private source code or use hidden
credentials. If the public markup changes, the adapter fails closed and records the error.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = ROOT / "sources"
JOBS_PATH = DATA / "jobs.json"
STATUS_PATH = DATA / "source_status.json"
CUSTOM_PATH = SOURCES / "custom_urls.json"
USER_AGENT = "PathToOfferBot/0.2 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = 30
MAX_PER_SOURCE = int(os.getenv("PTO_MAX_PER_SOURCE", "20000"))


@dataclass
class SourceResult:
    name: str
    label: str
    url: str
    ok: bool
    count: int = 0
    error: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(clean(x).lower() for x in parts if x)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]


def safe_public_url(url: str) -> bool:
    try:
        u = urlparse(url)
        if u.scheme not in {"http", "https"} or not u.hostname:
            return False
        host = u.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return False
        try:
            for info in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(info[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
        except socket.gaierror:
            pass
        return True
    except Exception:
        return False


def robots_allows(session: requests.Session, url: str) -> tuple[bool, str]:
    u = urlparse(url)
    robots_url = f"{u.scheme}://{u.netloc}/robots.txt"
    try:
        r = session.get(robots_url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.status_code == 404:
            return True, "robots.txt absent"
        if r.status_code in {401, 403}:
            return False, f"robots unavailable ({r.status_code})"
        if r.status_code >= 500:
            return False, f"robots server error ({r.status_code})"
        if not r.ok:
            return True, f"robots unspecified ({r.status_code})"
        rp = RobotFileParser(robots_url)
        rp.parse(r.text.splitlines())
        return rp.can_fetch(USER_AGENT, url), "robots.txt checked"
    except requests.RequestException as exc:
        return False, f"robots check failed: {type(exc).__name__}"


def fetch_public(session: requests.Session, url: str) -> requests.Response:
    if not safe_public_url(url):
        raise RuntimeError("source URL is not a public HTTP(S) address")
    allowed, why = robots_allows(session, url)
    if not allowed:
        raise RuntimeError(f"automatic access not allowed: {why}")
    r = session.get(
        url,
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        },
    )
    if r.status_code in {401, 403, 429}:
        raise RuntimeError(f"source requires authorization or throttled ({r.status_code}); no bypass attempted")
    r.raise_for_status()
    if any(x in r.text.lower() for x in ["captcha", "验证码", "请登录后", "login required"]):
        raise RuntimeError("source presented a login/CAPTCHA gate; no bypass attempted")
    return r


HEADER_ALIASES = {
    "updated_at": ["更新时间", "更新日期", "日期"],
    "company": ["企业名称", "公司名称", "企业", "公司"],
    "batch": ["招聘批次", "批次"],
    "company_type": ["企业性质", "公司性质", "性质"],
    "industry": ["行业"],
    "location": ["工作地点", "地点", "城市"],
    "role": ["职位", "岗位", "招聘岗位"],
    "graduation": ["毕业年份", "届别", "毕业时间"],
    "education": ["学历", "学历要求"],
    "notice_url": ["公告链接", "公告", "详情"],
    "apply_url": ["投递地址", "投递链接", "申请链接", "投递"],
}


def map_headers(headers: list[str]) -> dict[str, int]:
    mapped: dict[str, int] = {}
    for idx, header in enumerate(headers):
        h = clean(header)
        for key, aliases in HEADER_ALIASES.items():
            if key not in mapped and any(a in h for a in aliases):
                mapped[key] = idx
    return mapped


def link_from_cell(cell, base: str) -> str:
    a = cell.find("a", href=True) if cell else None
    if not a:
        return ""
    href = clean(a.get("href"))
    if not href or href.startswith(("javascript:", "#")):
        return ""
    return urljoin(base, href)


def parse_offerjack_tables(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        header_cells = table.find_all("th")
        if not header_cells:
            first = table.find("tr")
            header_cells = first.find_all(["th", "td"]) if first else []
        headers = [clean(c.get_text(" ", strip=True)) for c in header_cells]
        mapping = map_headers(headers)
        if "company" not in mapping or "role" not in mapping:
            continue
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            def value(key: str) -> str:
                idx = mapping.get(key)
                return clean(cells[idx].get_text(" ", strip=True)) if idx is not None and idx < len(cells) else ""
            company, role = value("company"), value("role")
            if not company or not role or company in {"企业名称", "公司名称"}:
                continue
            notice_cell = cells[mapping["notice_url"]] if mapping.get("notice_url") is not None and mapping["notice_url"] < len(cells) else None
            apply_cell = cells[mapping["apply_url"]] if mapping.get("apply_url") is not None and mapping["apply_url"] < len(cells) else None
            job = {
                "source": "offerjack",
                "source_label": "OfferJack · 公开页面",
                "source_url": base_url,
                "updated_at": value("updated_at"),
                "company": company,
                "department": "",
                "role": role,
                "location": value("location"),
                "salary": "",
                "batch": value("batch"),
                "company_type": value("company_type"),
                "industry": value("industry"),
                "graduation": value("graduation"),
                "education": value("education"),
                "notice_url": link_from_cell(notice_cell, base_url),
                "apply_url": link_from_cell(apply_cell, base_url),
                "jd": role,
                "tags": [],
            }
            job["id"] = stable_id(job["source"], company, role, job["location"], job["apply_url"] or job["notice_url"])
            jobs.append(job)
            if len(jobs) >= MAX_PER_SOURCE:
                return jobs
    return jobs


COMPANY_KEYS = ["企业名称", "公司名称", "company", "companyName", "company_name", "employer"]
ROLE_KEYS = ["职位", "岗位", "position", "positionName", "job", "jobName", "title"]


def first_key(d: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key in d and isinstance(d[key], (str, int, float)):
            return clean(d[key])
    return ""


def recursive_records(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        company, role = first_key(obj, COMPANY_KEYS), first_key(obj, ROLE_KEYS)
        if company and role:
            yield obj
        for value in obj.values():
            yield from recursive_records(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from recursive_records(value)


def parse_embedded_json(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for script in soup.find_all("script"):
        raw = script.string or script.get_text(strip=True)
        if not raw or len(raw) < 20:
            continue
        if script.get("type") != "application/json" and script.get("id") not in {"__NEXT_DATA__", "__NUXT_DATA__"}:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        for rec in recursive_records(obj):
            company, role = first_key(rec, COMPANY_KEYS), first_key(rec, ROLE_KEYS)
            location = first_key(rec, ["工作地点", "location", "city", "workPlace", "workplace"])
            apply_url = first_key(rec, ["投递地址", "applyUrl", "apply_url", "url", "jobUrl"])
            job = {
                "source":"offerjack","source_label":"OfferJack · 公开页面","source_url":base_url,
                "updated_at":first_key(rec,["更新时间","updatedAt","updated_at","date"]),
                "company":company,"department":first_key(rec,["部门","department"]),"role":role,"location":location,
                "salary":first_key(rec,["薪资","salary"]),"batch":first_key(rec,["招聘批次","batch"]),
                "company_type":first_key(rec,["企业性质","companyType","company_type"]),"industry":first_key(rec,["行业","industry"]),
                "graduation":first_key(rec,["毕业年份","graduation","graduateYear"]),"education":first_key(rec,["学历","education"]),
                "notice_url":first_key(rec,["公告链接","noticeUrl","detailUrl"]),"apply_url":apply_url,
                "jd":first_key(rec,["jd","description","岗位描述","职位描述"]) or role,"tags":[],
            }
            job["id"] = stable_id("offerjack",company,role,location,apply_url)
            if job["id"] not in seen:
                seen.add(job["id"]); jobs.append(job)
            if len(jobs) >= MAX_PER_SOURCE:
                return jobs
    return jobs


def offerjack_adapter(session: requests.Session) -> tuple[list[dict[str, Any]], SourceResult]:
    url = "https://www.offerjack.cn/"
    result = SourceResult("offerjack", "OfferJack · 公开页面", url, False)
    try:
        r = fetch_public(session, url)
        jobs = parse_offerjack_tables(r.text, url)
        if not jobs:
            jobs = parse_embedded_json(r.text, url)
        if not jobs:
            raise RuntimeError("public page fetched, but no compatible job records were found")
        result.ok = True; result.count = len(jobs)
        return jobs, result
    except Exception as exc:
        result.error = clean(exc)[:260]
        return [], result


def map_generic_job(rec: dict[str, Any], source_name: str, label: str, source_url: str) -> dict[str, Any] | None:
    company, role = first_key(rec, COMPANY_KEYS), first_key(rec, ROLE_KEYS)
    if not company or not role:
        return None
    job = {
        "source":source_name,"source_label":label,"source_url":source_url,
        "updated_at":first_key(rec,["updated_at","updatedAt","date","publishDate"]),
        "company":company,"department":first_key(rec,["department","部门"]),"role":role,
        "location":first_key(rec,["location","city","workplace","工作地点"]),
        "salary":first_key(rec,["salary","薪资"]),"batch":first_key(rec,["batch","招聘批次"]),
        "company_type":first_key(rec,["company_type","companyType","企业性质"]),"industry":first_key(rec,["industry","行业"]),
        "graduation":first_key(rec,["graduation","graduateYear","毕业年份"]),"education":first_key(rec,["education","学历"]),
        "notice_url":first_key(rec,["notice_url","noticeUrl","detailUrl"]),
        "apply_url":first_key(rec,["apply_url","applyUrl","url","jobUrl"]),
        "jd":first_key(rec,["jd","description","职位描述","岗位描述"]) or role,
        "tags":rec.get("tags",[]) if isinstance(rec.get("tags",[]),list) else [],
    }
    job["id"] = stable_id(source_name,company,role,job["location"],job["apply_url"] or job["notice_url"])
    return job


def custom_json_adapters(session: requests.Session) -> tuple[list[dict[str, Any]], list[SourceResult]]:
    if not CUSTOM_PATH.exists():
        return [], []
    cfg=json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
    all_jobs: list[dict[str, Any]]=[]; results: list[SourceResult]=[]
    for idx, item in enumerate(cfg.get("json_feeds", [])):
        if not item.get("enabled", True):
            continue
        url=clean(item.get("url")); name=clean(item.get("name")) or f"json_{idx+1}"; label=clean(item.get("label")) or name
        sr=SourceResult(name,label,url,False)
        try:
            r=fetch_public(session,url); payload=r.json(); records=payload.get("jobs",[]) if isinstance(payload,dict) else payload
            if not isinstance(records,list): raise RuntimeError("JSON feed must be a list or {jobs:[...]}")
            jobs=[x for rec in records if isinstance(rec,dict) for x in [map_generic_job(rec,name,label,url)] if x]
            sr.ok=True;sr.count=len(jobs);all_jobs.extend(jobs[:MAX_PER_SOURCE])
        except Exception as exc:
            sr.error=clean(exc)[:260]
        results.append(sr)
    return all_jobs, results


def dedupe(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key=job.get("id") or stable_id(job.get("source",""),job.get("company",""),job.get("role",""),job.get("location",""))
        old=chosen.get(key)
        if not old or len(clean(job.get("jd"))) > len(clean(old.get("jd"))):
            chosen[key]=job
    return list(chosen.values())


def load_previous() -> list[dict[str, Any]]:
    try:
        payload=json.loads(JOBS_PATH.read_text(encoding="utf-8"));return payload.get("jobs",[])
    except Exception:
        return []


def main() -> int:
    DATA.mkdir(parents=True,exist_ok=True); SOURCES.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    jobs: list[dict[str, Any]]=[]; statuses: list[SourceResult]=[]
    oj_jobs, oj_status=offerjack_adapter(session); jobs.extend(oj_jobs);statuses.append(oj_status)
    custom_jobs, custom_status=custom_json_adapters(session);jobs.extend(custom_jobs);statuses.extend(custom_status)
    jobs=dedupe(jobs)
    previous=load_previous()
    if not jobs and previous:
        jobs=previous
        for s in statuses:
            if not s.ok and not s.error:
                s.error="refresh failed; previous cached jobs retained"
    now=utc_now()
    jobs.sort(key=lambda j:(clean(j.get("updated_at")),clean(j.get("company")),clean(j.get("role"))),reverse=True)
    JOBS_PATH.write_text(json.dumps({"schema_version":1,"generated_at":now,"jobs":jobs},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    STATUS_PATH.write_text(json.dumps({"generated_at":now,"sources":[asdict(s) for s in statuses]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"aggregated {len(jobs)} jobs; sources="+", ".join(f"{s.name}:{'ok' if s.ok else 'fail'}:{s.count}" for s in statuses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
