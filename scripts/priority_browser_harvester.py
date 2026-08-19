#!/usr/bin/env python3
"""Browser-observed first-party/official-ATS job harvester.

This collector is the reusable counterpart to the DiDi browser collector.  It
opens only anonymous employer-owned career pages or the public ATS destinations
linked by those employers, watches the same XHR/fetch responses a normal browser
receives, and falls back to rendered job/detail links when an ATS does not expose
plain JSON.

It deliberately does *not* log in, replay private cookies, solve CAPTCHAs, rotate
proxies, decrypt protected payloads, or bypass access controls.  Every company is
isolated: a blocked/empty refresh preserves that company's last validated rows
rather than failing the whole catalogue refresh.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_browser_sources.json"
NAV_TIMEOUT = max(8_000, min(60_000, int(os.getenv("PTO_PRIORITY_BROWSER_TIMEOUT_MS", "26000"))))
MAX_JSON_BYTES = max(200_000, min(8_000_000, int(os.getenv("PTO_PRIORITY_BROWSER_MAX_JSON_BYTES", "4000000"))))
MAX_JD = max(800, min(8000, int(os.getenv("PTO_PRIORITY_BROWSER_JD_CHARS", "5000"))))

API_HINT_RE = re.compile(r"(?:job|jobs|position|positions|post|posts|recruit|career|vacan|search|list|campus|apply)", re.I)
ROLE_RE = re.compile(
    r"(?:工程师|算法|研发|开发|编译|编译器|软件|芯片|GPU|CUDA|推理|大模型|多模态|VLM|VLA|"
    r"机器人|强化学习|运动控制|系统|架构|性能|测试|验证|安全|研究员|研究|实习|产品经理|运营|销售)",
    re.I,
)
JOB_FIELD_RE = re.compile(r"(?:job|position|post|recruit|career|vacan|duty|require|qualif|responsib|description)", re.I)
GENERIC_ROLE_RE = re.compile(
    r"^(?:校园招聘|社会招聘|实习招聘|加入我们|人才招聘|招聘职位|职位列表|岗位列表|立即申请|申请|详情|"
    r"查看详情|更多|more|next|上一页|下一页|首页|返回|校招|社招|实习)$",
    re.I,
)
CITY_RE = re.compile(
    r"北京|上海|深圳|广州|杭州|南京|成都|武汉|西安|苏州|合肥|无锡|天津|重庆|长沙|厦门|青岛|济南|宁波|"
    r"东莞|珠海|佛山|嘉兴|常州|保定|烟台|全国|海外|新加坡|香港|吉隆坡"
)

TITLE_KEYS = (
    "jobname", "job_name", "jobtitle", "job_title", "positionname", "position_name", "positiontitle",
    "position_title", "postname", "post_name", "posttitle", "post_title", "recruitpostname", "recruit_post_name",
    "recruitpositionname", "recruit_position_name", "title",
)
ID_KEYS = (
    "jobid", "job_id", "jdid", "jd_id", "positionid", "position_id", "postid", "post_id", "recruitpostid",
    "recruit_post_id", "recruitpositionid", "recruit_position_id", "id", "code",
)
URL_KEYS = (
    "applyurl", "apply_url", "detailurl", "detail_url", "joburl", "job_url", "positionurl", "position_url",
    "posturl", "post_url", "shareurl", "share_url", "url", "href",
)
LOCATION_KEYS = (
    "location", "locations", "locationname", "location_name", "city", "cities", "cityname", "city_name",
    "workcity", "work_city", "workplace", "work_place", "worklocation", "work_location",
)
DEPARTMENT_KEYS = (
    "department", "departmentname", "department_name", "dept", "team", "jobcategory", "job_category",
    "category", "categoryname", "category_name",
)
JD_KEYS = (
    "description", "jobdescription", "job_description", "responsibility", "responsibilities", "requirement",
    "requirements", "qualification", "qualifications", "duty", "duties", "content", "jobduty", "jobrequirement",
)
UPDATED_KEYS = ("updatedat", "updated_at", "updatetime", "update_time", "publishtime", "publish_time", "refreshtime", "refresh_time")


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable for priority browser collector")


def flat_text(value: Any, limit: int = 600) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return clean(value)[:limit]
    if isinstance(value, dict):
        preferred = []
        for key in ("name", "label", "title", "value", "text", "cityName", "locationName"):
            if key in value:
                text = flat_text(value.get(key), limit)
                if text:
                    preferred.append(text)
        if preferred:
            return "/".join(dict.fromkeys(preferred))[:limit]
        parts = [flat_text(v, limit) for v in list(value.values())[:8]]
        return "/".join(x for x in parts if x)[:limit]
    if isinstance(value, (list, tuple, set)):
        parts = [flat_text(v, limit) for v in list(value)[:20]]
        return "/".join(dict.fromkeys(x for x in parts if x))[:limit]
    return clean(value)[:limit]


def lower_map(row: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    return {str(k).replace("-", "_").lower(): (str(k), v) for k, v in row.items()}


def first_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    mapping = lower_map(row)
    for key in keys:
        hit = mapping.get(key.lower())
        if hit is not None and hit[1] not in (None, "", [], {}):
            return hit[1]
    return None


def looks_like_role(value: str, *, strict: bool = False) -> bool:
    text = clean(value)
    if not (2 <= len(text) <= 140) or GENERIC_ROLE_RE.fullmatch(text):
        return False
    if text.isdigit() or re.fullmatch(r"[\W_]+", text):
        return False
    return bool(ROLE_RE.search(text)) if strict else True


def json_candidate(row: dict[str, Any], path: str = "") -> bool:
    mapping = lower_map(row)
    title = flat_text(first_value(row, TITLE_KEYS), 180)
    if not looks_like_role(title):
        # `name` is too generic to be a global title key; only use it when the
        # structural object path (not the request URL) is clearly job-shaped.
        name = flat_text(row.get("name"), 180)
        if not looks_like_role(name):
            return False
        jobish = bool(JOB_FIELD_RE.search(path)) or any(JOB_FIELD_RE.search(key) for key in mapping)
        if not jobish:
            return False
        title = name
    jobish_keys = sum(1 for key in mapping if JOB_FIELD_RE.search(key))
    has_id = first_value(row, ID_KEYS) not in (None, "")
    has_url = first_value(row, URL_KEYS) not in (None, "")
    location = first_value(row, LOCATION_KEYS) not in (None, "")
    # Avoid mistaking tiny metadata/name objects for jobs.
    return bool(has_id or has_url or location or jobish_keys >= 2 or JOB_FIELD_RE.search(path))


def walk_json(value: Any, path: str = "root", depth: int = 0) -> Iterable[tuple[dict[str, Any], str]]:
    if depth > 12:
        return
    if isinstance(value, dict):
        if json_candidate(value, path):
            yield value, path
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                yield from walk_json(child, f"{path}.{key}", depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value[:5000]):
            if isinstance(child, (dict, list)):
                yield from walk_json(child, f"{path}[{index}]", depth + 1)


def title_from_json(row: dict[str, Any], path: str = "") -> str:
    title = flat_text(first_value(row, TITLE_KEYS), 180)
    if looks_like_role(title):
        return title
    name = flat_text(row.get("name"), 180)
    return name if (looks_like_role(name) and JOB_FIELD_RE.search(path)) else ""


def location_from_text(text: str) -> str:
    cities = []
    for city in CITY_RE.findall(clean(text)):
        if city not in cities:
            cities.append(city)
    return "/".join(cities[:6])


def normalize_json_job(entry: dict[str, Any], row: dict[str, Any], path: str, response_url: str, page_url: str) -> dict[str, Any] | None:
    company = clean(entry.get("company"))
    role = title_from_json(row, path)
    if not company or not role:
        return None
    location = flat_text(first_value(row, LOCATION_KEYS), 180) or location_from_text(flat_text(row, 1200))
    department = flat_text(first_value(row, DEPARTMENT_KEYS), 180)
    raw_url = flat_text(first_value(row, URL_KEYS), 1200)
    apply_url = urljoin(response_url or page_url or entry.get("start_url", ""), raw_url) if raw_url else clean(page_url or entry.get("start_url"))
    if not apply_url.startswith(("http://", "https://")):
        apply_url = clean(entry.get("start_url"))
    jd_parts = []
    for key in JD_KEYS:
        value = first_value(row, (key,))
        text = flat_text(value, 2200)
        if text and text not in jd_parts:
            jd_parts.append(text)
    jd = clean("\n".join(jd_parts))[:MAX_JD] or role
    position_id = flat_text(first_value(row, ID_KEYS), 220)
    updated = flat_text(first_value(row, UPDATED_KEYS), 80)[:20]
    signal = " ".join([role, jd, flat_text(row, 1000)])
    batch = "2027校园招聘" if ("2027" in signal or "27届" in signal) else clean(entry.get("batch")) or "公开招聘"
    job = {
        "source": f"direct-official:browser:{clean(entry.get('id'))}",
        "source_label": f"{company}招聘官网 · 浏览器自主直连",
        "source_url": clean(entry.get("official_url") or entry.get("start_url")),
        "updated_at": updated,
        "company": company,
        "department": department,
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": clean(entry.get("company_type")),
        "industry": "",
        "graduation": "2027届" if "2027" in batch else "",
        "education": "",
        "notice_url": apply_url,
        "apply_url": apply_url,
        "jd": jd,
        "tags": ["企业官网/官方ATS", "浏览器公开请求", batch],
        "observed_via": "browser-public-xhr",
        "position_id": position_id,
    }
    job["id"] = stable_id(company, role, location, position_id or apply_url)
    return job


def dom_role(text: str, block: str) -> str:
    text = clean(text)
    if looks_like_role(text, strict=True):
        return text[:140]
    # Detail buttons often have generic text; recover a nearby job title from
    # the rendered card without inventing one.
    candidates = re.split(r"[\n|｜•·]+|(?<=\S)\s{2,}", clean(block))
    for candidate in candidates[:20]:
        candidate = clean(candidate).strip(" -—–|｜:：")
        if looks_like_role(candidate, strict=True):
            return candidate[:140]
    match = ROLE_RE.search(clean(block))
    if match:
        start = max(0, match.start() - 28)
        end = min(len(clean(block)), match.end() + 45)
        fragment = clean(block)[start:end].strip(" -—–|｜:：")
        if looks_like_role(fragment):
            return fragment[:140]
    return ""


def normalize_dom_job(entry: dict[str, Any], href: str, text: str, block: str) -> dict[str, Any] | None:
    role = dom_role(text, block)
    company = clean(entry.get("company"))
    if not company or not role:
        return None
    location = location_from_text(block)
    signal = f"{role} {block}"
    batch = "2027校园招聘" if ("2027" in signal or "27届" in signal) else clean(entry.get("batch")) or "公开招聘"
    job = {
        "source": f"direct-official:browser:{clean(entry.get('id'))}",
        "source_label": f"{company}招聘官网 · 浏览器自主直连",
        "source_url": clean(entry.get("official_url") or entry.get("start_url")),
        "updated_at": "",
        "company": company,
        "department": "",
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": clean(entry.get("company_type")),
        "industry": "",
        "graduation": "2027届" if "2027" in batch else "",
        "education": "",
        "notice_url": href,
        "apply_url": href,
        "jd": clean(block)[:MAX_JD] or role,
        "tags": ["企业官网/官方ATS", "浏览器渲染岗位", batch],
        "observed_via": "browser-rendered-dom",
    }
    job["id"] = stable_id(company, role, location, href)
    return job


def job_identity(job: dict[str, Any]) -> str:
    source = clean(job.get("source"))
    pid = clean(job.get("position_id"))
    if source and pid:
        return f"{source}:{pid}".lower()
    url = clean(job.get("apply_url") or job.get("notice_url")).rstrip("/").lower()
    if url:
        return f"url:{url}|{clean(job.get('role')).lower()}"
    return "|".join([clean(job.get("company")).lower(), clean(job.get("role")).lower(), clean(job.get("location")).lower()])


@dataclass
class Capture:
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    json_responses: int = 0
    json_candidates: int = 0
    response_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dom_links_seen: int = 0
    pages_advanced: int = 0

    def add(self, job: dict[str, Any] | None) -> None:
        if not job:
            return
        key = job_identity(job)
        if key and key not in self.jobs:
            self.jobs[key] = job


def response_handler(entry: dict[str, Any], page: Page, capture: Capture, response) -> None:
    try:
        url = response.url
        ctype = (response.headers.get("content-type") or "").lower()
        if "json" not in ctype and not API_HINT_RE.search(url):
            return
        length = response.headers.get("content-length") or ""
        if length.isdigit() and int(length) > MAX_JSON_BYTES:
            return
        if response.request.resource_type not in {"xhr", "fetch", "document", "other"}:
            return
        payload = response.json()
        if not isinstance(payload, (dict, list)):
            return
        capture.json_responses += 1
        if len(capture.response_urls) < 30 and url not in capture.response_urls:
            capture.response_urls.append(url)
        seen = 0
        # Keep structural JSON paths independent of the endpoint URL.  An API
        # URL such as `/job/list` must not make every nested `{id,name}` filter
        # option look job-shaped merely because the request path contains job.
        for row, path in walk_json(payload, path="root"):
            seen += 1
            capture.add(normalize_json_job(entry, row, path, url, page.url))
            if seen >= 2500:
                break
        capture.json_candidates += seen
    except Exception as exc:
        if len(capture.errors) < 20:
            capture.errors.append(f"response {type(exc).__name__}: {clean(exc)[:160]}")


def rendered_links(page: Page) -> list[dict[str, str]]:
    try:
        return page.eval_on_selector_all(
            "a[href]",
            """els => els.slice(0, 3500).map(a => {
              let node=a, block='';
              for(let i=0;i<5 && node;i++,node=node.parentElement){
                const t=(node.innerText||node.textContent||'').trim();
                if(t.length>=4 && t.length<=1800) block=t;
                if(t.length>=25 && t.length<=900) break;
              }
              return {href:a.href||'', text:(a.innerText||a.textContent||'').trim(), block:block};
            })""",
        )
    except Exception:
        return []


def collect_dom(entry: dict[str, Any], page: Page, capture: Capture) -> int:
    before = len(capture.jobs)
    for item in rendered_links(page):
        href = clean(item.get("href"))
        text = clean(item.get("text"))
        block = clean(item.get("block"))
        if not href.startswith(("http://", "https://")):
            continue
        if GENERIC_ROLE_RE.fullmatch(text) and not ROLE_RE.search(block):
            continue
        if not (API_HINT_RE.search(href) or ROLE_RE.search(text) or ROLE_RE.search(block)):
            continue
        capture.dom_links_seen += 1
        capture.add(normalize_dom_job(entry, href, text, block))
    return len(capture.jobs) - before


def safe_click_labels(page: Page, labels: list[str], capture: Capture) -> None:
    for label in labels[:4]:
        try:
            locator = page.get_by_text(label, exact=True)
            if locator.count() == 0 or not locator.first.is_visible():
                continue
            old = page.url
            locator.first.click(timeout=2500)
            page.wait_for_timeout(800)
            capture.pages_advanced += int(page.url != old)
        except Exception as exc:
            if len(capture.errors) < 20:
                capture.errors.append(f"click {label}: {type(exc).__name__}: {clean(exc)[:120]}")


def click_next(page: Page) -> bool:
    selectors = [
        "button:has-text('下一页')", "a:has-text('下一页')", "button:has-text('Next')", "a:has-text('Next')",
        "button[aria-label*='next' i]", "a[aria-label*='next' i]", ".ant-pagination-next:not(.ant-pagination-disabled)",
        ".el-pagination .btn-next:not([disabled])", "li[class*='next']:not([class*='disabled']) a",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 3)):
                item = locator.nth(index)
                if item.is_visible() and item.is_enabled():
                    item.click(timeout=2500)
                    page.wait_for_timeout(850)
                    return True
        except Exception:
            continue
    return False


def collect_one(context: BrowserContext, entry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    capture = Capture()
    page = context.new_page()
    page.on("response", lambda response: response_handler(entry, page, capture, response))
    start = clean(entry.get("start_url"))
    max_pages = max(1, min(20, int(entry.get("max_pages") or 6)))
    final_url = start
    try:
        page.goto(start, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(1000)
        final_url = page.url
        labels = [clean(x) for x in (entry.get("click_labels") or []) if clean(x)]
        if labels:
            safe_click_labels(page, labels, capture)
        stable_rounds = 0
        for _ in range(max_pages):
            before = len(capture.jobs)
            # Exercise lazy/infinite lists without simulating hidden behavior.
            for fraction in (0.45, 0.8, 1.0):
                try:
                    page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {fraction})")
                    page.wait_for_timeout(450)
                except Exception:
                    pass
            collect_dom(entry, page, capture)
            after = len(capture.jobs)
            stable_rounds = stable_rounds + 1 if after == before else 0
            if click_next(page):
                capture.pages_advanced += 1
                stable_rounds = 0
                continue
            if stable_rounds >= 2:
                break
            # One extra lazy-load cycle is useful even without a paginator.
            page.wait_for_timeout(650)
        collect_dom(entry, page, capture)
    except PlaywrightTimeoutError as exc:
        capture.errors.append(f"navigation timeout: {clean(exc)[:180]}")
    except Exception as exc:
        capture.errors.append(f"{type(exc).__name__}: {clean(exc)[:220]}")
    finally:
        try:
            final_url = page.url or final_url
        except Exception:
            pass
        page.close()
    jobs = list(capture.jobs.values())
    diagnostics = {
        "start_url": start,
        "final_url": final_url,
        "unique_jobs": len(jobs),
        "json_responses": capture.json_responses,
        "json_candidates": capture.json_candidates,
        "dom_links_seen": capture.dom_links_seen,
        "pages_advanced": capture.pages_advanced,
        "observed_endpoints": capture.response_urls[:20],
        "errors": capture.errors[:15],
        "transport": "browser-public-ui-xhr-dom",
    }
    return jobs, diagnostics


def previous_by_source(existing: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for job in existing:
        if not isinstance(job, dict):
            continue
        source = clean(job.get("source"))
        if source.startswith("direct-official:browser:"):
            result.setdefault(source, []).append(job)
    return result


def merge(existing: list[dict[str, Any]], fresh_by_source: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    managed = set(fresh_by_source)
    out: dict[str, dict[str, Any]] = {}
    for job in existing:
        if not isinstance(job, dict) or not clean(job.get("company")) or not clean(job.get("role")):
            continue
        if clean(job.get("source")) in managed:
            continue
        out[job_identity(job)] = job
    for jobs in fresh_by_source.values():
        for job in jobs:
            out[job_identity(job)] = job
    return list(out.values())


def main() -> int:
    config = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = [x for x in config.get("sources", []) if isinstance(x, dict) and x.get("enabled", True)]
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version": 3, "jobs": []}
    existing = payload.get("jobs", []) if isinstance(payload, dict) else []
    if existing and isinstance(existing[0], dict) and "c" in existing[0]:
        raise RuntimeError("priority_browser_harvester.py must run before compact_feed.py")
    previous = previous_by_source(existing if isinstance(existing, list) else [])
    fresh_by_source: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []

    try:
        executable = browser_path()
    except Exception as exc:
        executable = ""
        browser_error = f"{type(exc).__name__}: {clean(exc)[:180]}"
    else:
        browser_error = ""

    if executable:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
            try:
                for entry in entries:
                    source = f"direct-official:browser:{clean(entry.get('id'))}"
                    try:
                        jobs, diagnostics = collect_one(context, entry)
                        if jobs:
                            fresh_by_source[source] = jobs
                            results.append({
                                "id": entry.get("id"), "company": entry.get("company"), "ok": True, "count": len(jobs),
                                "preserved_previous": False, "official_url": entry.get("official_url"), "diagnostics": diagnostics, "error": "",
                            })
                        else:
                            kept = previous.get(source, [])
                            fresh_by_source[source] = kept
                            results.append({
                                "id": entry.get("id"), "company": entry.get("company"), "ok": bool(kept), "count": len(kept),
                                "fresh_count": 0, "preserved_previous": bool(kept), "official_url": entry.get("official_url"),
                                "diagnostics": diagnostics, "error": "zero concrete browser jobs; previous rows preserved" if kept else "zero concrete browser jobs",
                            })
                    except Exception as exc:
                        kept = previous.get(source, [])
                        fresh_by_source[source] = kept
                        results.append({
                            "id": entry.get("id"), "company": entry.get("company"), "ok": bool(kept), "count": len(kept),
                            "fresh_count": 0, "preserved_previous": bool(kept), "official_url": entry.get("official_url"),
                            "diagnostics": {}, "error": f"{type(exc).__name__}: {clean(exc)[:220]}",
                        })
            finally:
                context.close()
                browser.close()
    else:
        for entry in entries:
            source = f"direct-official:browser:{clean(entry.get('id'))}"
            kept = previous.get(source, [])
            fresh_by_source[source] = kept
            results.append({
                "id": entry.get("id"), "company": entry.get("company"), "ok": bool(kept), "count": len(kept),
                "fresh_count": 0, "preserved_previous": bool(kept), "official_url": entry.get("official_url"),
                "diagnostics": {}, "error": browser_error,
            })

    merged = merge(existing if isinstance(existing, list) else [], fresh_by_source)
    output = dict(payload) if isinstance(payload, dict) else {}
    output.update({"schema_version": 3, "generated_at": utc_now(), "jobs": merged})
    JOBS_PATH.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    fresh_total = sum((row.get("diagnostics") or {}).get("unique_jobs", 0) for row in results)
    group = {
        "name": "priority-browser-official",
        "label": "重点企业招聘官网/官方 ATS · 浏览器公开请求巡检",
        "url": "",
        "ok": any(row.get("ok") for row in results),
        "count": sum(row.get("count", 0) for row in results),
        "fresh_count": fresh_total,
        "error": "" if any(row.get("ok") for row in results) else (browser_error or "all priority browser sources returned zero jobs"),
        "diagnostics": {
            "transport": "real-browser-public-ui-xhr-dom",
            "target_count": len(entries),
            "fresh_companies": sum(1 for row in results if (row.get("diagnostics") or {}).get("unique_jobs", 0) > 0),
            "sources": results,
        },
    }
    sources = [s for s in status.get("sources", []) if not isinstance(s, dict) or s.get("name") != group["name"]]
    sources.insert(0, group)
    status.update({"sources": sources, "catalog_count": len(merged), "generated_at": utc_now()})
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "priority_browser_jobs": group["count"], "fresh_jobs": fresh_total,
        "sources": [(r.get("company"), r.get("count"), r.get("preserved_previous", False), (r.get("diagnostics") or {}).get("json_responses", 0)) for r in results],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
