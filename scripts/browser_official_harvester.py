#!/usr/bin/env python3
"""Browser-observed first-party career-site harvester.

Many Chinese employers publish jobs through JavaScript applications whose public
HTML contains no rows until the browser calls an employer-owned JSON endpoint.
This adapter observes those anonymous public responses, recursively recognizes
job-shaped records, parses JSON-LD/Next.js payloads, and follows a small bounded
set of public career links.

The registry is sharded across runs so the source graph can grow without trying
to open thousands of companies in one GitHub Actions job. Explicit priority
sources (currently 滴滴、银河通用、辉羲智能) run every cycle; the remainder rotate.
All concrete job types are retained. Campus/2027/intern signals are labelled and
ranked later, rather than filtering out social or non-technical positions.

No login, cookie replay, CAPTCHA solving, proxy rotation, stealth browser or
access-control bypass is used. A monitored source that yields no concrete row is
reported as zero; it is never converted into a fabricated position.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urldefrag

from playwright.sync_api import Browser, Page, Response, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "browser_official_sources.json"
TIMEOUT_MS = max(12_000, min(90_000, int(os.getenv("PTO_BROWSER_SOURCE_TIMEOUT_MS", "45000"))))
SOURCES_PER_RUN = max(1, min(30, int(os.getenv("PTO_BROWSER_SOURCES_PER_RUN", "10"))))
RUN_NUMBER = max(0, int(os.getenv("PTO_BROWSER_SOURCE_RUN", "0") or 0))
MAX_PAGES_PER_SOURCE = max(1, min(12, int(os.getenv("PTO_BROWSER_PAGES_PER_SOURCE", "5"))))
MAX_JD = max(800, min(9000, int(os.getenv("PTO_BROWSER_OFFICIAL_JD_CHARS", "5000"))))
MAX_JSON_BYTES = max(200_000, min(8_000_000, int(os.getenv("PTO_BROWSER_JSON_BYTES", "3000000"))))

TITLE_KEYS = (
    "title", "name", "jobName", "positionName", "postName", "jobTitle", "job_title",
    "positionTitle", "recruitPostName", "recruitPositionName", "RecruitPostName",
)
ID_KEYS = ("id", "jobId", "job_id", "positionId", "position_id", "postId", "PostId", "code")
LOCATION_KEYS = (
    "location", "city", "cityName", "workLocation", "workLocationName", "address",
    "LocationName", "locations", "workPlace", "jobLocation",
)
CATEGORY_KEYS = ("category", "categoryName", "jobCategory", "jobCategoryName", "jobName", "department", "departmentName", "BGName")
DESCRIPTION_KEYS = (
    "description", "jobDescription", "jobDuty", "responsibility", "Responsibility",
    "duties", "content", "detail", "jobContent", "positionDescription",
)
REQUIREMENT_KEYS = (
    "requirement", "requirements", "jobRequirement", "serveRequirement", "qualification",
    "qualifications", "Requirement", "positionRequirement", "jobQualifications",
)
URL_KEYS = ("url", "jobUrl", "jobURL", "applyUrl", "applyURL", "detailUrl", "postUrl", "PostURL", "href", "link")
DATE_KEYS = ("releaseTime", "publishTime", "publishedAt", "updateTime", "updatedAt", "LastUpdateTime", "date")
BATCH_KEYS = ("batch", "batchName", "recruitTypeName", "jobTypeName", "projectName", "campusType")
EDUCATION_KEYS = ("education", "educationName", "degree", "degreeName", "qualificationName")
GENERIC_TITLES = {
    "招聘", "招聘职位", "职位", "岗位", "加入我们", "校园招聘", "社会招聘", "实习生招聘",
    "技术", "产品", "职能", "运营", "设计", "市场", "营销", "全部职位", "职位类别",
    "home", "jobs", "careers", "career", "join us", "job list",
}
JOB_MARKERS = re.compile(r"岗位职责|工作职责|职位描述|任职要求|任职资格|岗位要求|工作内容|job\s*description|responsibilit|qualification|requirement", re.I)
CAREER_LINK = re.compile(r"job|jobs|position|positions|career|careers|recruit|recruitment|campus|join|talent|招聘|职位|岗位|人才|加入", re.I)
CAMPUS = re.compile(r"2026|2027|26届|27届|校招|校园招聘|应届|毕业生|实习|intern|campus|new\s*grad|graduate", re.I)
SOCIAL = re.compile(r"社招|社会招聘|experienced|社会人才", re.I)
SKIP_EXT = re.compile(r"\.(?:jpg|jpeg|png|gif|svg|webp|pdf|zip|rar|7z|mp4|mp3|css|js|ico|woff2?)(?:\?|$)", re.I)


def compact(value: Any, limit: int = MAX_JD) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def first_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""


def scalar(value: Any) -> str:
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("label") or value.get("value") or value.get("text"))
    if isinstance(value, list):
        values = [scalar(item) for item in value]
        return "/".join(dict.fromkeys(item for item in values if item))
    return ""


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) or str(value).isdigit():
        try:
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc).date().isoformat()
        except Exception:
            return ""
    text = scalar(value)
    match = re.search(r"(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return ""


def browser_path() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium not available")


def normalize_url(value: str, base: str) -> str:
    text = clean(value)
    if not text or text.lower().startswith(("javascript:", "mailto:", "tel:")):
        return ""
    try:
        url, _ = urldefrag(urljoin(base, text))
        return url if urlparse(url).scheme in {"http", "https"} else ""
    except Exception:
        return ""


def allowed_url(url: str, source: dict[str, Any]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    allowed = [str(x).lower() for x in source.get("allowed_hosts", [])]
    return any(host == item or host.endswith("." + item) for item in allowed)


def batch_from(row: dict[str, Any], blob: str) -> tuple[str, str]:
    explicit = scalar(first_value(row, BATCH_KEYS))
    graduation = scalar(row.get("graduationYear") or row.get("graduation") or row.get("gradYear"))
    year_match = re.search(r"20(?:2[4-9]|3\d)|2[4-9]届", f"{graduation} {blob}")
    if graduation and not graduation.endswith("届") and re.fullmatch(r"20\d{2}", graduation):
        graduation += "届"
    elif not graduation and year_match:
        token = year_match.group(0)
        graduation = token if token.endswith("届") else f"{token}届"
    if explicit:
        batch = explicit
    elif CAMPUS.search(blob):
        batch = "校园/实习招聘"
    elif SOCIAL.search(blob):
        batch = "社会招聘"
    else:
        batch = "公开招聘"
    return batch, graduation


def normalize_candidate(row: dict[str, Any], source: dict[str, Any], page_url: str, observed_url: str, origin: str) -> dict[str, Any] | None:
    title = scalar(first_value(row, TITLE_KEYS))
    title = re.sub(r"\s*[-|｜]\s*(?:招聘|校园招聘|社会招聘).*$", "", title).strip()
    if not (2 <= len(title) <= 140) or title.lower() in GENERIC_TITLES:
        return None

    position_id = scalar(first_value(row, ID_KEYS))
    location = scalar(first_value(row, LOCATION_KEYS))
    category = scalar(first_value(row, CATEGORY_KEYS))
    description = scalar(first_value(row, DESCRIPTION_KEYS))
    requirement = scalar(first_value(row, REQUIREMENT_KEYS))
    explicit_url = scalar(first_value(row, URL_KEYS))
    detail_url = normalize_url(explicit_url, page_url)
    template = clean(source.get("detail_url_template"))
    if not detail_url and template and position_id:
        detail_url = template.replace("{id}", position_id)
    if not detail_url:
        detail_url = page_url

    evidence = sum(bool(value) for value in (position_id, location, description, requirement, explicit_url, category))
    text_blob = " ".join((title, category, description, requirement, scalar(first_value(row, BATCH_KEYS))))
    if evidence < 2 and not JOB_MARKERS.search(text_blob):
        return None
    if not (description or requirement or location or position_id):
        return None

    batch, graduation = batch_from(row, text_blob)
    education = scalar(first_value(row, EDUCATION_KEYS))
    updated_at = iso_date(first_value(row, DATE_KEYS))
    company = clean(source.get("company"))
    source_id = clean(source.get("id"))
    jd_parts = [
        category and f"职位类别：{category}",
        description and f"岗位职责：{description}",
        requirement and f"任职要求：{requirement}",
    ]
    job = {
        "source": f"direct-official:browser:{source_id}",
        "source_label": f"{company}招聘官网 · 浏览器自主发现",
        "source_url": clean(source.get("start_urls", [page_url])[0]),
        "updated_at": updated_at,
        "company": company,
        "department": category,
        "role": title,
        "location": location,
        "salary": scalar(row.get("salary") or row.get("salaryName")),
        "batch": batch,
        "company_type": clean(source.get("company_type")),
        "industry": clean(source.get("industry")),
        "graduation": graduation,
        "education": education,
        "notice_url": detail_url,
        "apply_url": detail_url,
        "jd": compact("；".join(part for part in jd_parts if part) or text_blob),
        "tags": ["企业官网", "浏览器自主发现", batch, category],
        "observed_via": origin,
        "observed_response": observed_url,
        "position_id": position_id,
    }
    job["tags"] = [item for index, item in enumerate(job["tags"]) if item and item not in job["tags"][:index]]
    job["id"] = stable_id(company, title, location, position_id or detail_url)
    return job


def walk_json(value: Any, source: dict[str, Any], page_url: str, observed_url: str, jobs: dict[str, dict[str, Any]], depth: int = 0) -> None:
    if depth > 9:
        return
    if isinstance(value, dict):
        candidate = normalize_candidate(value, source, page_url, observed_url, "employer-public-browser-json")
        if candidate:
            jobs[candidate["id"]] = candidate
        for child in value.values():
            if isinstance(child, (dict, list)):
                walk_json(child, source, page_url, observed_url, jobs, depth + 1)
    elif isinstance(value, list):
        for child in value[:5000]:
            if isinstance(child, (dict, list)):
                walk_json(child, source, page_url, observed_url, jobs, depth + 1)


def parse_json_scripts(page: Page, source: dict[str, Any], jobs: dict[str, dict[str, Any]]) -> int:
    count_before = len(jobs)
    scripts = page.locator('script[type="application/ld+json"],script#__NEXT_DATA__,script[type="application/json"]')
    for index in range(min(scripts.count(), 80)):
        text = scripts.nth(index).text_content() or ""
        if not text or len(text.encode("utf-8", errors="ignore")) > MAX_JSON_BYTES:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        walk_json(payload, source, page.url, page.url, jobs)
    return len(jobs) - count_before


def parse_dom_links(page: Page, source: dict[str, Any], jobs: dict[str, dict[str, Any]]) -> tuple[int, list[str]]:
    count_before = len(jobs)
    follow: list[str] = []
    anchors = page.locator("a[href]")
    for index in range(min(anchors.count(), 1200)):
        anchor = anchors.nth(index)
        href = normalize_url(anchor.get_attribute("href") or "", page.url)
        if not href or SKIP_EXT.search(href) or not allowed_url(href, source):
            continue
        label = compact(anchor.inner_text() or anchor.get_attribute("title") or "", 180)
        signal = f"{label} {href}"
        if CAREER_LINK.search(signal) and href not in follow:
            follow.append(href)
        if not (2 <= len(label) <= 120) or label.lower() in GENERIC_TITLES:
            continue
        if not CAREER_LINK.search(href):
            continue
        try:
            context_text = compact(anchor.locator("xpath=ancestor-or-self::*[self::li or self::article or self::section or self::div][1]").inner_text(), 1400)
        except Exception:
            context_text = label
        if not (JOB_MARKERS.search(context_text) or CAMPUS.search(context_text) or re.search(r"北京|上海|深圳|广州|杭州|南京|成都|武汉|西安|苏州", context_text)):
            continue
        candidate = normalize_candidate({"title": label, "description": context_text, "url": href}, source, page.url, page.url, "employer-public-browser-dom")
        if candidate:
            jobs[candidate["id"]] = candidate
    return len(jobs) - count_before, follow


def observe_source(browser: Browser, source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
    page = context.new_page()
    jobs: dict[str, dict[str, Any]] = {}
    responses_seen = 0
    json_responses = 0
    errors: list[str] = []
    visited: set[str] = set()
    queue = deque((url, 0) for url in source.get("start_urls", []) if clean(url))

    def on_response(response: Response) -> None:
        nonlocal responses_seen, json_responses
        responses_seen += 1
        ctype = (response.headers.get("content-type") or "").lower()
        if "json" not in ctype or not allowed_url(response.url, source):
            return
        try:
            body = response.body()
            if len(body) > MAX_JSON_BYTES:
                return
            payload = json.loads(body.decode("utf-8", errors="replace"))
            json_responses += 1
            walk_json(payload, source, page.url or response.url, response.url, jobs)
        except Exception as exc:
            errors.append(f"response {response.url}: {type(exc).__name__}: {compact(exc, 120)}")

    page.on("response", on_response)
    while queue and len(visited) < MAX_PAGES_PER_SOURCE:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            page.wait_for_timeout(3500)
            for _ in range(4):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
            parse_json_scripts(page, source, jobs)
            _, follow = parse_dom_links(page, source, jobs)
            if depth < 1:
                for link in follow[: max(0, MAX_PAGES_PER_SOURCE - len(visited) - len(queue))]:
                    if link not in visited:
                        queue.append((link, depth + 1))
        except Exception as exc:
            errors.append(f"page {url}: {type(exc).__name__}: {compact(exc, 180)}")
    context.close()
    return list(jobs.values()), {
        "pages_visited": len(visited),
        "responses_seen": responses_seen,
        "json_responses": json_responses,
        "unique_jobs": len(jobs),
        "visited_sample": list(visited)[:12],
        "errors": errors[:20],
    }


def registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def selected_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    all_sources = [source for source in config.get("sources", []) if isinstance(source, dict) and source.get("start_urls")]
    always = [source for source in all_sources if source.get("always")]
    rotating = [source for source in all_sources if not source.get("always")]
    rotating.sort(key=lambda source: hashlib.sha256(clean(source.get("id")).encode()).hexdigest())
    budget = max(0, min(SOURCES_PER_RUN, int(config.get("sources_per_run") or SOURCES_PER_RUN)) - len(always))
    if not rotating or budget <= 0:
        return always[:SOURCES_PER_RUN]
    start = (RUN_NUMBER * budget) % len(rotating)
    selected = [rotating[(start + offset) % len(rotating)] for offset in range(min(budget, len(rotating)))]
    return always + selected


def identity(job: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(job.get("company")).lower(),
        clean(job.get("role")).lower(),
        clean(job.get("location")).lower(),
        clean(job.get("position_id") or job.get("apply_url") or job.get("notice_url")).lower(),
    )


def merge_catalog(existing: list[dict[str, Any]], fresh_by_source: dict[str, list[dict[str, Any]]], successful_nonempty: set[str]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for job in existing:
        if not isinstance(job, dict) or not clean(job.get("company")) or not clean(job.get("role")):
            continue
        source = clean(job.get("source"))
        if source in successful_nonempty:
            continue
        merged[identity(job)] = job
    for rows in fresh_by_source.values():
        for job in rows:
            merged[identity(job)] = job
    return list(merged.values())


def main() -> int:
    config = registry()
    selected = selected_sources(config)
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("browser_official_harvester.py must run before compact_feed.py")

    fresh_by_source: dict[str, list[dict[str, Any]]] = {}
    successful_nonempty: set[str] = set()
    results: list[dict[str, Any]] = []
    executable = browser_path()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
        for source in selected:
            source_id = clean(source.get("id"))
            source_key = f"direct-official:browser:{source_id}"
            started = time.time()
            try:
                rows, diagnostics = observe_source(browser, source)
                fresh_by_source[source_key] = rows
                if rows:
                    successful_nonempty.add(source_key)
                results.append({
                    "id": source_id,
                    "company": source.get("company"),
                    "url": source.get("start_urls", [""])[0],
                    "ok": True,
                    "count": len(rows),
                    "elapsed_seconds": round(time.time() - started, 2),
                    "diagnostics": diagnostics,
                    "error": "",
                })
                print(f"browser official {source.get('company')}: {len(rows)} jobs / {diagnostics.get('json_responses')} json responses")
            except Exception as exc:
                results.append({
                    "id": source_id,
                    "company": source.get("company"),
                    "url": source.get("start_urls", [""])[0],
                    "ok": False,
                    "count": 0,
                    "elapsed_seconds": round(time.time() - started, 2),
                    "diagnostics": {},
                    "error": f"{type(exc).__name__}: {compact(exc, 240)}",
                })
                print(f"browser official {source.get('company')}: FAILED {type(exc).__name__}: {compact(exc, 140)}")
        browser.close()

    merged = merge_catalog(existing if isinstance(existing, list) else [], fresh_by_source, successful_nonempty)
    out = dict(payload) if isinstance(payload, dict) else {}
    out.update({"schema_version": 3, "generated_at": utc_now(), "jobs": merged})
    JOBS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group = {
        "name": "browser-official-career-sites",
        "label": "企业招聘官网 · 浏览器自主发现网络",
        "url": "",
        "ok": any(row.get("ok") for row in results),
        "count": sum(row.get("count", 0) for row in results),
        "error": "",
        "diagnostics": {
            "registry": "sources/browser_official_sources.json",
            "registered_sources": len(config.get("sources", [])),
            "selected_sources": len(selected),
            "run_number": RUN_NUMBER,
            "sources": results,
        },
    }
    sources = [row for row in status.get("sources", []) if not isinstance(row, dict) or row.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(merged), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected": [row.get("company") for row in selected], "fresh_jobs": group["count"], "catalog": len(merged)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
