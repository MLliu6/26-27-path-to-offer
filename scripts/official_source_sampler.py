#!/usr/bin/env python3
"""Bounded rotating crawler over the employer-owned source graph.

The graph may contain hundreds or thousands of company career surfaces. A single
run deliberately samples a bounded subset, always includes the highest-priority
sources, and rotates through the remainder over time. Concrete rows are emitted
only from JSON-LD JobPosting objects or pages that contain both job-duty and
qualification evidence. Portal reachability alone never creates a fake job.

The crawler stays on the registered employer host, follows a small number of
career-looking links, observes robots.txt when available, uses a descriptive user
agent, and never logs in, solves CAPTCHAs or bypasses access controls.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "official_source_catalog.json"
UA = "PathToOfferBot/1.2 (+https://github.com/MLliu6/26-27-path-to-offer; public-career-source-audit)"
TIMEOUT = max(6, min(30, int(os.getenv("PTO_OFFICIAL_SITE_TIMEOUT", "13"))))
SAMPLE_SITES = max(8, min(80, int(os.getenv("PTO_OFFICIAL_SAMPLE_SITES", "30"))))
PAGES_PER_SITE = max(1, min(12, int(os.getenv("PTO_OFFICIAL_PAGES_PER_SITE", "5"))))
WORKERS = max(2, min(16, int(os.getenv("PTO_OFFICIAL_SITE_WORKERS", "8"))))
MAX_JD = max(800, min(10000, int(os.getenv("PTO_OFFICIAL_SITE_JD_CHARS", "5000"))))

CAREER_RE = re.compile(r"career|careers|campus|graduate|intern|recruit|recruitment|job|jobs|position|join|talent|招聘|校招|实习|职位|岗位|人才|加入", re.I)
DUTY_RE = re.compile(r"岗位职责|工作职责|职位职责|职位描述|工作内容|job\s*(?:description|responsibilit)", re.I)
QUAL_RE = re.compile(r"任职要求|任职资格|职位要求|岗位要求|基本要求|qualifications?|requirements?", re.I)
YEAR_RE = re.compile(r"2027|27届|2026[-—–]?2027|校园招聘|校招|应届|毕业生|graduate|campus|intern|实习", re.I)
GENERIC_TITLE = re.compile(r"^(招聘|招聘职位|职位列表|岗位列表|人才招聘|校园招聘|社会招聘|实习生招聘|加入我们|careers?|jobs?|positions?|join us)[\s|｜_-]*$", re.I)
SKIP_EXT = re.compile(r"\.(?:jpg|jpeg|png|gif|svg|webp|pdf|zip|rar|7z|mp4|mp3|css|js|ico|woff2?)(?:\?|$)", re.I)
LOCATION_RE = re.compile(r"(?:工作地点|办公地点|职位地点|地点|location)\s*[:：]\s*([^,，。；;|｜]{2,40})", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact(value: Any, limit: int = MAX_JD) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def session() -> requests.Session:
    active = requests.Session()
    active.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/ld+json,application/json;q=0.9,*/*;q=0.4"})
    return active


def allowed_by_robots(active: requests.Session, url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = active.get(robots_url, timeout=min(8, TIMEOUT))
        if response.status_code >= 400:
            return True, f"robots HTTP {response.status_code}"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return parser.can_fetch(UA, url), "robots parsed"
    except Exception as exc:
        return True, f"robots unavailable: {type(exc).__name__}"


def jsonld_objects(value: Any):
    if isinstance(value, dict):
        if value.get("@type") == "JobPosting" or (isinstance(value.get("@type"), list) and "JobPosting" in value.get("@type")):
            yield value
        for child in value.values():
            yield from jsonld_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from jsonld_objects(child)


def text_value(value: Any) -> str:
    if isinstance(value, str):
        return clean(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("value") or value.get("addressLocality") or "")
    if isinstance(value, list):
        return "/".join(filter(None, [text_value(item) for item in value]))
    return clean(value)


def job_from_jsonld(obj: dict[str, Any], source: dict[str, Any], page_url: str) -> dict[str, Any] | None:
    role = text_value(obj.get("title") or obj.get("name"))
    if not role or GENERIC_TITLE.match(role):
        return None
    organization = obj.get("hiringOrganization") or {}
    company = text_value(organization.get("name") if isinstance(organization, dict) else organization) or clean(source.get("company"))
    location = text_value(obj.get("jobLocation"))
    if isinstance(obj.get("jobLocation"), list):
        location = "/".join(filter(None, [text_value(item.get("address") if isinstance(item, dict) else item) for item in obj.get("jobLocation")]))
    elif isinstance(obj.get("jobLocation"), dict):
        location = text_value(obj["jobLocation"].get("address") or obj["jobLocation"])
    description = text_value(obj.get("description"))
    qualification = text_value(obj.get("qualifications") or obj.get("skills") or obj.get("experienceRequirements"))
    apply_url = clean(obj.get("url") or obj.get("sameAs")) or page_url
    date = clean(obj.get("datePosted"))[:10]
    blob = " ".join([role, description, qualification])
    batch = "2027/校园招聘" if YEAR_RE.search(blob) else "公开招聘"
    job = {
        "source": f"direct-official:graph:{source.get('host')}",
        "source_label": f"{company}招聘官网 · 结构化岗位",
        "source_url": source.get("url"), "updated_at": date,
        "company": company, "department": "", "role": role, "location": location,
        "salary": text_value(obj.get("baseSalary")), "batch": batch,
        "company_type": clean(source.get("category")), "industry": clean(obj.get("industry") or source.get("category")),
        "graduation": "2027届" if "2027" in blob or "27届" in blob else "", "education": text_value(obj.get("educationRequirements")),
        "notice_url": page_url, "apply_url": apply_url,
        "jd": compact("；".join(part for part in [description, qualification] if part) or role),
        "tags": ["企业官网", "JSON-LD JobPosting", batch], "observed_via": "employer-jsonld",
    }
    job["id"] = stable_id(company, role, location, apply_url)
    return job


def page_title(soup: BeautifulSoup, text: str, company: str) -> str:
    for selector in ["h1", "h2", "title"]:
        element = soup.find(selector)
        if not element:
            continue
        title = clean(element.get_text(" ", strip=True))
        title = re.sub(rf"^{re.escape(company)}\s*[-|｜:]?\s*", "", title).strip()
        title = re.sub(r"\s*[-|｜].*(招聘|career|公司|官网).*$", "", title, flags=re.I).strip()
        if 2 <= len(title) <= 110 and not GENERIC_TITLE.match(title):
            return title
    match = re.search(r"(?:岗位|职位)(?:名称)?\s*[:：]\s*([^,，。；;]{2,80})", text)
    return clean(match.group(1)) if match else ""


def job_from_page(soup: BeautifulSoup, text: str, source: dict[str, Any], page_url: str) -> dict[str, Any] | None:
    if not DUTY_RE.search(text) or not QUAL_RE.search(text) or len(text) < 220:
        return None
    company = clean(source.get("company"))
    role = page_title(soup, text, company)
    if not role or GENERIC_TITLE.match(role) or len(role) > 110:
        return None
    location_match = LOCATION_RE.search(text)
    location = clean(location_match.group(1)) if location_match else ""
    batch = "2027/校园招聘" if YEAR_RE.search(text[:5000]) else "公开招聘"
    job = {
        "source": f"direct-official:graph:{source.get('host')}",
        "source_label": f"{company}招聘官网 · 自主发现",
        "source_url": source.get("url"), "updated_at": "",
        "company": company, "department": "", "role": role, "location": location,
        "salary": "", "batch": batch, "company_type": clean(source.get("category")), "industry": clean(source.get("category")),
        "graduation": "2027届" if "2027" in text or "27届" in text else "", "education": "",
        "notice_url": page_url, "apply_url": page_url, "jd": compact(text),
        "tags": ["企业官网", "有界自主抓取", batch], "observed_via": "bounded-official-source-graph",
    }
    job["id"] = stable_id(company, role, location, page_url)
    return job


def crawl_source(source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    active = session()
    start = clean(source.get("url"))
    host = (urlparse(start).hostname or "").lower()
    allowed, robots_note = allowed_by_robots(active, start)
    if not allowed:
        return [], {"company": source.get("company"), "url": start, "ok": False, "status": "robots-disallow", "pages": 0, "jobs": 0, "robots": robots_note, "errors": []}
    queue = [(start, 0, 100)]
    seen: set[str] = set()
    queued = {start}
    jobs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    status_code = 0
    year_signal = False
    while queue and len(seen) < PAGES_PER_SITE:
        queue.sort(key=lambda item: -item[2])
        url, depth, _ = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            response = active.get(url, timeout=TIMEOUT, allow_redirects=True)
            status_code = response.status_code
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if content_type and "html" not in content_type:
                continue
            response.encoding = response.apparent_encoding or response.encoding
            soup = BeautifulSoup(response.text, "html.parser")
            text = clean(soup.get_text(" ", strip=True))
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {compact(exc, 130)}")
            continue
        year_signal = year_signal or bool(YEAR_RE.search(text[:6000]))
        for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            try:
                payload = json.loads(script.string or script.get_text() or "")
            except Exception:
                continue
            for obj in jsonld_objects(payload):
                job = job_from_jsonld(obj, source, response.url)
                if job:
                    jobs[job["id"]] = job
        page_job = job_from_page(soup, text, source, response.url)
        if page_job:
            jobs[page_job["id"]] = page_job
        if depth >= 2:
            continue
        links = []
        for anchor in soup.find_all("a", href=True):
            href, _ = urldefrag(urljoin(response.url, anchor.get("href", "")))
            parsed = urlparse(href)
            target_host = (parsed.hostname or "").lower()
            if parsed.scheme not in {"http", "https"} or target_host != host or href in seen or href in queued or SKIP_EXT.search(href):
                continue
            label = clean(anchor.get_text(" ", strip=True))
            signal = f"{label} {href}"
            if not CAREER_RE.search(signal):
                continue
            priority = 30 + (30 if re.search(r"position|job|职位|岗位", signal, re.I) else 0) + (20 if YEAR_RE.search(signal) else 0)
            links.append((href, depth + 1, priority))
            queued.add(href)
        links.sort(key=lambda item: -item[2])
        queue.extend(links[: max(0, PAGES_PER_SITE - len(seen))])
        time.sleep(0.08)
    health = {
        "company": source.get("company"), "url": start, "ok": bool(status_code and status_code < 400),
        "status": "jobs-found" if jobs else ("reachable-no-concrete-job" if status_code and status_code < 400 else "request-failed"),
        "http_status": status_code, "pages": len(seen), "jobs": len(jobs), "year_signal": year_signal,
        "robots": robots_note, "checked_at": now(), "errors": errors[:8],
    }
    return list(jobs.values()), health


def load_graph() -> dict[str, Any]:
    return json.loads(GRAPH.read_text(encoding="utf-8"))


def select_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(sources) <= SAMPLE_SITES:
        return sources
    mandatory = [source for source in sources if int(source.get("priority", 0)) >= 98]
    mandatory = mandatory[: min(len(mandatory), max(8, SAMPLE_SITES // 2))]
    mandatory_keys = {source.get("key") for source in mandatory}
    remainder = [source for source in sources if source.get("key") not in mandatory_keys]
    epoch = int(time.time() // 7200)
    start = (epoch * max(1, SAMPLE_SITES - len(mandatory))) % max(1, len(remainder))
    rotated = remainder[start:] + remainder[:start]
    return mandatory + rotated[: max(0, SAMPLE_SITES - len(mandatory))]


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (clean(job.get("company")).lower(), clean(job.get("role")).lower(), clean(job.get("location")).lower(), clean(job.get("apply_url") or job.get("notice_url")).lower())


def main() -> int:
    graph = load_graph()
    all_sources = [source for source in graph.get("sources", []) if isinstance(source, dict) and source.get("url")]
    selected = select_sources(all_sources)
    fresh: list[dict[str, Any]] = []
    health_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(crawl_source, source): source for source in selected}
        for future in as_completed(futures):
            source = futures[future]
            try:
                jobs, health = future.result()
                fresh.extend(jobs)
                health_rows.append({"key": source.get("key"), **health})
            except Exception as exc:
                health_rows.append({"key": source.get("key"), "company": source.get("company"), "url": source.get("url"), "ok": False, "status": "crawler-error", "pages": 0, "jobs": 0, "checked_at": now(), "errors": [f"{type(exc).__name__}: {compact(exc, 180)}"]})

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    existing = payload.get("jobs", [])
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("official_source_sampler.py must run before compact_feed.py")
    merged = {identity(job): job for job in existing if isinstance(job, dict) and clean(job.get("company")) and clean(job.get("role"))}
    for job in fresh:
        merged[identity(job)] = job
    payload.update({"schema_version": 3, "generated_at": utc_now(), "jobs": list(merged.values())})
    JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    health_by_key = {row.get("key"): row for row in health_rows if row.get("key")}
    for source in graph.get("sources", []):
        if source.get("key") in health_by_key:
            source["health"] = health_by_key[source["key"]]
    graph.update({"generated_at": now(), "last_sample_size": len(selected), "last_sample_jobs": len(fresh), "last_sample_at": now()})
    GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    ok_count = sum(1 for row in health_rows if row.get("ok"))
    group = {
        "name": "official-source-graph", "label": "企业招聘官网图谱 · 轮转自主抓取", "url": "",
        "ok": ok_count > 0, "count": len(fresh), "error": "",
        "diagnostics": {"catalog_sources": len(all_sources), "sampled": len(selected), "reachable": ok_count, "concrete_jobs": len(fresh), "sites": health_rows},
    }
    sources = [row for row in status.get("sources", []) if not isinstance(row, dict) or row.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(payload["jobs"]), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog_sources": len(all_sources), "sampled": len(selected), "reachable": ok_count, "jobs": len(fresh)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
