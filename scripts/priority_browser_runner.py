#!/usr/bin/env python3
"""Install reviewed public-ATS/page adapters, then run the browser harvester.

The generic collector intentionally keeps a conservative field vocabulary so
filter metadata cannot be mistaken for jobs. This runner adds reviewed schema
aliases for ATS families observed in employer public UI traffic, rejects known
metadata-only JSON objects/endpoints, isolates JSON parsing to the registered
ATS host, gives Feishu Hire's public `job_post_list` a direct-row adapter, and
keeps a browser fallback for employer pages whose *current document* is itself
a job detail. It does not add another transport or bypass any access control.
"""
from __future__ import annotations

import re
from urllib.parse import quote, urlparse

from scripts import priority_browser_harvester as h


EXTRA_TITLE_KEYS = (
    "jobadname", "job_ad_name", "jobadtitle", "job_ad_title",
)
EXTRA_ID_KEYS = (
    "jobadid", "job_ad_id", "jobadcode", "job_ad_code",
)
EXTRA_LOCATION_KEYS = (
    "detailaddress", "detail_address", "joblocation", "job_location",
    "joblocations", "job_locations", "worklocations", "work_locations",
)
EXTRA_DEPARTMENT_KEYS = (
    "kind", "jobkind", "job_kind", "jobfamily", "job_family",
)
EXTRA_JD_KEYS = (
    "jobaddescription", "job_ad_description", "jobadrequirement", "job_ad_requirement",
    "jobadresponsibility", "job_ad_responsibility", "workcontent", "work_content",
)
EXTRA_UPDATED_KEYS = (
    "postdate", "post_date", "modifiedtime", "modified_time", "createdtime", "created_time",
)

DUTY_RE = re.compile(r"岗位职责|工作职责|职位职责|职位描述|工作内容|responsibilit|job\s*description", re.I)
QUAL_RE = re.compile(r"任职要求|任职资格|职位要求|岗位要求|基本要求|qualifications?|requirements?", re.I)
NOISE_HEADING_RE = re.compile(r"^(?:recruitment|招聘|招聘信息|人才招聘|加入我们|校园招聘|社会招聘)$", re.I)
BRACKET_META_RE = re.compile(r"^[〖【\[]\s*(?:全职|实习|校招|社招)(?:[-—–/|｜]\s*)?([^〗】\]]{0,24})[〗】\]]\s*", re.I)
PREFIX_META_RE = re.compile(r"^(?:全职|实习|校招|社招)(?:[-—–/|｜]\s*)?(?:(?:北京|上海|深圳|广州|杭州|合肥|南京|苏州|成都)\s*)?", re.I)
META_PATH_RE = re.compile(r"(?:^|[.\[_-])(?:filters?|facets?|options?|settings?|config|dictionary|dictionaries)(?:$|[.\[\]_-])", re.I)
JOBISH_KEY_RE = re.compile(r"(?:job|position|post|recruit|career|vacan)", re.I)
FEISHU_METADATA_PATH_RE = re.compile(
    r"^/api/v1/(?:config/job/filters(?:/|$)|common/setting(?:/|$)|user/mobile/login_status(?:/|$)|ip/location(?:/|$)|csrf/token(?:/|$))",
    re.I,
)
FEISHU_JOB_POSTS_PATH_RE = re.compile(r"^/api/v1/search/job/posts(?:/|$)", re.I)


def extend(existing, extra):
    return tuple(dict.fromkeys([*existing, *extra]))


def normalize_heading(raw: str) -> str:
    candidate = h.clean(raw).strip(" -—–|｜:：")
    candidate = BRACKET_META_RE.sub("", candidate)
    candidate = candidate.strip(" -—–|｜:：[]【】〖〗")
    candidate = PREFIX_META_RE.sub("", candidate).strip(" -—–|｜:：[]【】〖〗")
    return candidate


def trusted_response_host(entry, response_url: str) -> bool:
    """Accept JSON only from the registered ATS host or explicit API hosts."""
    try:
        start_host = (urlparse(h.clean(entry.get("start_url"))).hostname or "").lower()
        response_host = (urlparse(h.clean(response_url)).hostname or "").lower()
    except Exception:
        return False
    if not start_host or not response_host:
        return False
    allowed = {start_host}
    for value in entry.get("api_hosts") or []:
        host = h.clean(value).lower().strip().strip(".")
        if host:
            allowed.add(host)
    return response_host in allowed


def is_feishu_entry(entry) -> bool:
    try:
        return (urlparse(h.clean(entry.get("start_url"))).hostname or "").lower().endswith("jobs.feishu.cn")
    except Exception:
        return False


def mark_feishu_job_posts(capture) -> None:
    """Record that a concrete Feishu public job-list response was parsed."""
    setattr(capture, "_feishu_job_post_responses", int(getattr(capture, "_feishu_job_post_responses", 0)) + 1)


def has_feishu_job_posts(capture) -> bool:
    """Return whether the authoritative Feishu job-list endpoint has responded."""
    return int(getattr(capture, "_feishu_job_post_responses", 0)) > 0


def feishu_job_rows(payload) -> list[dict]:
    """Return only direct Feishu Hire position rows, never their nested metadata."""
    if not isinstance(payload, dict):
        return []
    if payload.get("code") not in (None, 0, "0"):
        return []
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return []
    rows = data.get("job_post_list") or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def feishu_portal_path(entry) -> str:
    try:
        parts = [part for part in urlparse(h.clean(entry.get("start_url"))).path.split("/") if part]
    except Exception:
        return ""
    if not parts:
        return ""
    # Public Feishu portals use the first path component as `website-path`, e.g.
    # /huixi, /zhipucampus, /campusrecruitment, /379481.
    return parts[0]


def normalize_feishu_job(entry, row: dict, response_url: str, page_url: str):
    company = h.clean(entry.get("company"))
    role = h.clean(row.get("title"))
    position_id = h.clean(row.get("id"))
    if not company or not position_id or not h.looks_like_role(role):
        return None

    city_list = row.get("city_list") or []
    cities = []
    if isinstance(city_list, list):
        for city in city_list:
            name = h.clean(city.get("name")) if isinstance(city, dict) else h.clean(city)
            if name and name not in cities:
                cities.append(name)
    location = "/".join(cities[:8]) or h.location_from_text(h.flat_text(row, 1800))

    job_function = row.get("job_function") or {}
    department = h.clean(job_function.get("name")) if isinstance(job_function, dict) else ""
    recruit_type = row.get("recruit_type") or {}
    recruit_name = h.clean(recruit_type.get("name")) if isinstance(recruit_type, dict) else ""

    description = h.clean(row.get("description"))
    requirement = h.clean(row.get("requirement"))
    jd = "\n".join(part for part in (description, requirement) if part)[: h.MAX_JD] or role
    signal = " ".join([role, recruit_name, jd])
    entry_batch = h.clean(entry.get("batch"))
    batch = "2027校园招聘" if (
        "2027" in signal or "27届" in signal or "2027" in entry_batch or "27届" in entry_batch
    ) else (recruit_name or entry_batch or "公开招聘")

    parsed = urlparse(h.clean(entry.get("start_url")) or page_url or response_url)
    portal_path = feishu_portal_path(entry)
    if parsed.scheme in {"http", "https"} and parsed.netloc and portal_path:
        detail = f"{parsed.scheme}://{parsed.netloc}/{portal_path}/position/{quote(position_id, safe='')}/detail"
    else:
        detail = h.clean(page_url or entry.get("start_url"))

    job = {
        "source": f"direct-official:browser:{h.clean(entry.get('id'))}",
        "source_label": f"{company}招聘官网 · 飞书公开职位",
        "source_url": h.clean(entry.get("official_url") or entry.get("start_url")),
        "updated_at": h.clean(row.get("publish_time"))[:20],
        "company": company,
        "department": department,
        "role": role[:140],
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": h.clean(entry.get("company_type")),
        "industry": h.clean(entry.get("category")),
        "graduation": "2027届" if "2027" in batch else "",
        "education": "",
        "notice_url": detail,
        "apply_url": detail,
        "jd": jd,
        "tags": ["企业官网/官方ATS", "飞书公开职位", batch],
        "observed_via": "browser-public-feishu-job-list",
        "position_id": position_id,
    }
    job["id"] = h.stable_id(company, role, location, position_id)
    return job


def page_job_from_text(entry, page_url: str, headings, body: str):
    """Normalize one public employer page only when it is clearly a job detail."""
    company = h.clean(entry.get("company"))
    body = h.clean(body)
    if not company or not page_url.startswith(("http://", "https://")):
        return None
    if len(body) < 180 or not DUTY_RE.search(body) or not QUAL_RE.search(body):
        return None

    role = ""
    for raw in headings or []:
        candidate = normalize_heading(raw)
        if NOISE_HEADING_RE.fullmatch(candidate):
            continue
        if h.looks_like_role(candidate, strict=True):
            role = candidate[:140]
            break
    if not role:
        snippets = re.split(r"(?:职位描述|岗位职责|工作职责|任职资格|任职要求)", body[:1800], maxsplit=1)
        prefix = snippets[0] if snippets else body[:900]
        candidates = re.split(r"[|｜•·]+|\s{2,}", prefix)
        for candidate in candidates[-20:]:
            candidate = normalize_heading(candidate)
            if h.looks_like_role(candidate, strict=True):
                role = candidate[:140]
                break
    if not role:
        return None

    location = h.location_from_text(" ".join([h.clean(" ".join(headings or [])), body[:2500]]))
    batch = "2027校园招聘" if ("2027" in body or "27届" in body) else h.clean(entry.get("batch")) or "公开招聘"
    source = f"direct-official:browser:{h.clean(entry.get('id'))}"
    job = {
        "source": source,
        "source_label": f"{company}招聘官网 · 浏览器岗位详情",
        "source_url": h.clean(entry.get("official_url") or entry.get("start_url")),
        "updated_at": "",
        "company": company,
        "department": "",
        "role": role,
        "location": location,
        "salary": "",
        "batch": batch,
        "company_type": h.clean(entry.get("company_type")),
        "industry": h.clean(entry.get("category")),
        "graduation": "2027届" if "2027" in batch else "",
        "education": "",
        "notice_url": page_url,
        "apply_url": page_url,
        "jd": body[: h.MAX_JD],
        "tags": ["企业官网", "浏览器岗位详情", batch],
        "observed_via": "browser-current-job-page",
        "position_id": "",
    }
    job["id"] = h.stable_id(company, role, location, page_url)
    return job


def current_page_job(entry, page):
    try:
        snapshot = page.evaluate(
            """() => ({
              url: location.href,
              headings: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,16).map(x => (x.innerText||x.textContent||'').trim()),
              body: (document.body && (document.body.innerText||document.body.textContent) || '').trim()
            })"""
        )
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    return page_job_from_text(entry, h.clean(snapshot.get("url")), snapshot.get("headings") or [], snapshot.get("body") or "")


def install() -> None:
    h.TITLE_KEYS = extend(h.TITLE_KEYS, EXTRA_TITLE_KEYS)
    h.ID_KEYS = extend(h.ID_KEYS, EXTRA_ID_KEYS)
    h.LOCATION_KEYS = extend(h.LOCATION_KEYS, EXTRA_LOCATION_KEYS)
    h.DEPARTMENT_KEYS = extend(h.DEPARTMENT_KEYS, EXTRA_DEPARTMENT_KEYS)
    h.JD_KEYS = extend(h.JD_KEYS, EXTRA_JD_KEYS)
    h.UPDATED_KEYS = extend(h.UPDATED_KEYS, EXTRA_UPDATED_KEYS)

    base_candidate = h.json_candidate

    def guarded_json_candidate(row, path=""):
        if not base_candidate(row, path):
            return False
        normalized_path = h.clean(path).lower()
        if META_PATH_RE.search(normalized_path):
            return False

        strong_title_keys = tuple(key for key in h.TITLE_KEYS if key.lower() not in {"title"})
        strong_title = h.flat_text(h.first_value(row, strong_title_keys), 180)
        if h.looks_like_role(strong_title):
            return True

        generic_title = h.flat_text(h.first_value(row, ("title",)), 180) or h.flat_text(row.get("name"), 180)
        if not h.looks_like_role(generic_title):
            return False

        mapping = h.lower_map(row)
        jobish_keys = sum(1 for key in mapping if JOBISH_KEY_RE.search(key))
        path_jobish = bool(JOBISH_KEY_RE.search(normalized_path))
        has_location = h.first_value(row, h.LOCATION_KEYS) not in (None, "", [], {})
        has_url = h.first_value(row, h.URL_KEYS) not in (None, "", [], {})
        has_jd = h.first_value(row, h.JD_KEYS) not in (None, "", [], {})
        has_payload_signal = has_location or has_url or has_jd or jobish_keys >= 2
        return bool(path_jobish or has_payload_signal)

    h.json_candidate = guarded_json_candidate

    base_response_handler = h.response_handler

    def guarded_response_handler(entry, page, capture, response):
        if not trusted_response_host(entry, response.url):
            return
        try:
            parsed = urlparse(response.url)
            host = (parsed.hostname or "").lower()
            path = parsed.path or ""
            if host.endswith("jobs.feishu.cn"):
                if FEISHU_METADATA_PATH_RE.search(path):
                    return
                if FEISHU_JOB_POSTS_PATH_RE.search(path):
                    payload = response.json()
                    rows = feishu_job_rows(payload)
                    capture.json_responses += 1
                    mark_feishu_job_posts(capture)
                    if len(capture.response_urls) < 30 and response.url not in capture.response_urls:
                        capture.response_urls.append(response.url)
                    # Once the official list response exists, remove any page/DOM
                    # fallback rows that may have been captured before its XHR.
                    capture.jobs = {
                        key: value for key, value in capture.jobs.items()
                        if value.get("observed_via") not in {"browser-rendered-dom", "browser-current-job-page"}
                    }
                    for row in rows:
                        capture.json_candidates += 1
                        capture.add(normalize_feishu_job(entry, row, response.url, page.url))
                    return
        except Exception as exc:
            if len(capture.errors) < 20:
                capture.errors.append(f"feishu response {type(exc).__name__}: {h.clean(exc)[:160]}")
            return
        return base_response_handler(entry, page, capture, response)

    h.response_handler = guarded_response_handler

    base_normalize = h.normalize_json_job

    def normalize_json_job(entry, row, path, response_url, page_url):
        job = base_normalize(entry, row, path, response_url, page_url)
        if not job:
            return None
        position_id = h.clean(job.get("position_id"))
        template = h.clean(entry.get("detail_url_template"))
        if position_id and template:
            detail = template.replace("{position_id}", quote(position_id, safe=""))
            if detail.startswith(("http://", "https://")):
                job["apply_url"] = detail
                job["notice_url"] = detail
                job["id"] = h.stable_id(job.get("company"), job.get("role"), job.get("location"), position_id)
        salary = h.flat_text(h.first_value(row, ("salary", "salaryrange", "salary_range")), 160)
        if salary:
            job["salary"] = salary
        return job

    h.normalize_json_job = normalize_json_job

    base_collect_dom = h.collect_dom

    def collect_dom(entry, page, capture):
        before = len(capture.jobs)
        # Generic same-host JSON responses must not disable the fallback. Only a
        # successfully parsed Feishu `job/posts` response is authoritative.
        if is_feishu_entry(entry) and has_feishu_job_posts(capture):
            return 0
        capture.add(current_page_job(entry, page))
        base_collect_dom(entry, page, capture)
        return len(capture.jobs) - before

    h.collect_dom = collect_dom


def main() -> int:
    install()
    return h.main()


if __name__ == "__main__":
    raise SystemExit(main())