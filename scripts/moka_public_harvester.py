#!/usr/bin/env python3
"""Read-only public Moka employer-career harvester.

Moka career sites load their current public job catalogue from the anonymous
website endpoint below. The response envelope contains both an encrypted payload
and the ephemeral decryption key needed by the public website. This collector
implements that public browser contract only: it never calls applicant, login,
resume-upload or authenticated APIs and never reuses user cookies.

The deep federation can discover Moka tenants from the pinned Hiring-Radar seed
file, while the ten-minute priority feed uses a small local registry for sources
we want to regress explicitly (currently Shopee).
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
RADAR_DIR = Path(os.getenv("PTO_HIRING_RADAR_DIR", "/tmp/hiring-radar"))
SEED_PATH = RADAR_DIR / "parsers" / "companies.seed"
PRIORITY_PATH = ROOT / "sources" / "moka_priority_sources.json"
API = "https://app.mokahr.com/api/outer/ats-apply/website/jobs/v2"
IV = b"de7c21ed8d6f50fe"
UA = "PathToOfferBot/1.3 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = max(8, min(45, int(os.getenv("PTO_MOKA_TIMEOUT", "25"))))
MAX_PAGES = max(1, min(60, int(os.getenv("PTO_MOKA_MAX_PAGES", "20"))))
PAGE_SIZE = max(20, min(100, int(os.getenv("PTO_MOKA_PAGE_SIZE", "50"))))
WORKERS = max(2, min(20, int(os.getenv("PTO_MOKA_WORKERS", "10"))))
MAX_JD = max(400, min(10000, int(os.getenv("PTO_MOKA_JD_CHARS", "5000"))))

COMPANY_OVERRIDES = {
    "shopee": "Shopee（深圳虾皮信息科技有限公司）",
}


def strip_html(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|li|div|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return text if len(text) <= MAX_JD else text[:MAX_JD].rstrip() + "…"


def parse_date(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return ""
    try:
        n = float(raw)
        if n > 10_000_000_000:
            n /= 1000.0
        return datetime.fromtimestamp(n, tz=timezone.utc).date().isoformat()
    except Exception:
        pass
    m = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", raw)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return raw[:10] if re.match(r"20\d{2}-\d{2}-\d{2}", raw) else ""


def infer_graduation(text: str) -> str:
    m = re.search(r"(20(?:2[4-9]|3\d))\s*届", text)
    if m:
        return f"{m.group(1)}届"
    m = re.search(r"\b(20(?:2[4-9]|3\d))\b", text)
    if m and re.search(r"校招|校园|应届|毕业|秋招|春招|campus|graduate", text, re.I):
        return f"{m.group(1)}届"
    return ""


def infer_education(text: str) -> str:
    lower = text.lower()
    if "博士" in text or "phd" in lower:
        return "博士"
    if "硕士" in text or "研究生" in text or "master" in lower:
        return "硕士"
    if "本科" in text or "学士" in text or "bachelor" in lower:
        return "本科"
    if "大专" in text or "专科" in text:
        return "大专"
    return ""


def parse_moka_seed_file(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    """Parse only Moka tenant declarations from a public discovery seed file."""
    text = path.read_text(encoding="utf-8")
    out: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 5 or parts[1].lower() != "moka":
            continue
        key, _, company, org, site = parts[:5]
        category = parts[5] if len(parts) > 5 else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", org or "") or not str(site).isdigit():
            continue
        out.append({
            "key": key,
            "org": org,
            "site": int(site),
            "company": COMPANY_OVERRIDES.get(key, company),
            "category": category,
            "portal_kind": "social-recruitment",
            "official_url": f"https://app.mokahr.com/social-recruitment/{org}/{site}#/jobs",
        })
    return out


def load_priority_specs(path: Path = PRIORITY_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for row in payload.get("sources", []):
        if not isinstance(row, dict):
            continue
        org, site = clean(row.get("org")), row.get("site")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", org or "") or not str(site).isdigit():
            continue
        item = dict(row)
        item["site"] = int(site)
        item["company"] = COMPANY_OVERRIDES.get(clean(item.get("key")), clean(item.get("company")))
        out.append(item)
    return out


def decrypt_public_envelope(payload: Any) -> Any:
    if not isinstance(payload, dict):
        raise RuntimeError("Moka returned a non-object response")
    if "data" not in payload or "necromancer" not in payload:
        return payload
    key = str(payload.get("necromancer") or "").encode("utf-8")
    if len(key) not in (16, 24, 32):
        raise RuntimeError(f"Moka public envelope key length changed: {len(key)}")
    encrypted = base64.b64decode(str(payload.get("data") or ""))
    clear = unpad(AES.new(key, AES.MODE_CBC, IV).decrypt(encrypted), 16)
    return json.loads(clear.decode("utf-8"))


def public_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Content-Type": "application/json",
        "Origin": "https://app.mokahr.com",
        "Referer": "https://app.mokahr.com/",
    })
    return session


def response_jobs(payload: Any) -> list[dict[str, Any]]:
    value = payload
    for _ in range(4):
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if not isinstance(value, dict):
            return []
        for key in ("jobs", "list", "results", "items"):
            if isinstance(value.get(key), list):
                return [row for row in value[key] if isinstance(row, dict)]
        nxt = value.get("data")
        if nxt is value:
            break
        value = nxt
    return []


def call_page(session: requests.Session, spec: dict[str, Any], offset: int) -> list[dict[str, Any]]:
    body = {
        "orgId": spec["org"],
        "siteId": int(spec["site"]),
        "locale": "zh-CN",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    response = session.post(API, json=body, timeout=TIMEOUT)
    response.raise_for_status()
    return response_jobs(decrypt_public_envelope(response.json()))


def location_text(row: dict[str, Any]) -> str:
    values=[]
    for item in row.get("locations") or []:
        if not isinstance(item, dict):
            continue
        for key in ("cityName", "name", "locationName"):
            value=clean(item.get(key))
            if value:
                values.append(value);break
    fallback=clean(row.get("location") or row.get("workLocation") or row.get("city"))
    if fallback:
        values.append(fallback)
    return "、".join(dict.fromkeys(values))


def department_text(row: dict[str, Any]) -> str:
    dep=row.get("department")
    if isinstance(dep, dict):
        return clean(dep.get("name") or dep.get("title"))
    return clean(dep or row.get("dept") or row.get("team"))


def portal_url(spec: dict[str, Any]) -> str:
    explicit=clean(spec.get("official_url"))
    if explicit:
        return explicit
    kind=clean(spec.get("portal_kind")) or "social-recruitment"
    return f"https://app.mokahr.com/{kind}/{spec['org']}/{spec['site']}#/jobs"


def job_url(spec: dict[str, Any], job_id: str) -> str:
    kind=clean(spec.get("portal_kind")) or "social-recruitment"
    return f"https://app.mokahr.com/{kind}/{spec['org']}/{spec['site']}#/job/{job_id}"


def normalize_job(spec: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    title=clean(row.get("title") or row.get("jobName") or row.get("name"))
    job_id=clean(row.get("id") or row.get("jobId") or row.get("positionId"))
    if not title or not job_id:
        return None
    company=clean(spec.get("company")) or clean(row.get("company")) or clean(spec.get("key"))
    location=location_text(row)
    department=department_text(row)
    description=strip_html(row.get("jobDescription") or row.get("description") or row.get("jd"))
    requirement=strip_html(row.get("jobRequirement") or row.get("requirements") or row.get("qualification"))
    commitment=clean(row.get("commitment") or row.get("jobType") or row.get("type"))
    category=clean(spec.get("category"))
    blob=" ".join([title,description,requirement,commitment,department,category])
    graduation=infer_graduation(blob)
    campus=bool(re.search(r"2027|27届|2028|28届|校招|校园招聘|应届|秋招|春招|campus|graduate", blob, re.I)) or clean(spec.get("portal_kind"))=="campus-recruitment"
    batch="校园招聘" if campus else commitment
    if graduation:
        batch=f"{graduation}校园招聘" + (f" · {commitment}" if commitment else "")
    jd="；".join(part for part in [department and f"部门：{department}", commitment and f"性质：{commitment}", description and f"岗位描述：{description}", requirement and f"任职要求：{requirement}"] if part) or title
    url=job_url(spec,job_id)
    salary=""
    min_salary=clean(row.get("minSalary"));max_salary=clean(row.get("maxSalary"))
    if min_salary or max_salary:
        salary=f"{min_salary}-{max_salary}".strip("-")
    source_id=f"direct-official:moka:{clean(spec.get('key')) or spec['org']}"
    if clean(spec.get("key"))=="shopee":
        source_id="direct-official:shopee"
    job={
        "source":source_id,
        "source_label":f"{company}招聘官网 · Moka公开直连",
        "source_url":portal_url(spec),
        "updated_at":parse_date(row.get("publishedAt") or row.get("createdAt") or row.get("openedAt") or row.get("updatedAt")),
        "company":company,
        "department":department,
        "role":title,
        "location":location,
        "salary":salary,
        "batch":batch,
        "company_type":"外企/互联网" if clean(spec.get("key"))=="shopee" else "",
        "industry":category,
        "graduation":graduation,
        "education":infer_education(blob),
        "notice_url":url,
        "apply_url":url,
        "jd":jd[:MAX_JD],
        "tags":[x for x in ["企业官网","Moka",commitment,category,graduation] if x],
        "observed_via":"moka-public-website-api",
        "position_id":job_id,
        "portal_kind":clean(spec.get("portal_kind")),
    }
    job["id"]=stable_id(company,title,location,job_id)
    return job


def fetch_company(spec: dict[str, Any], session: requests.Session | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    active=session or public_session()
    jobs: dict[str, dict[str, Any]]={}
    raw_count=0
    page_sizes=[]
    for page in range(MAX_PAGES):
        rows=call_page(active,spec,page*PAGE_SIZE)
        page_sizes.append(len(rows));raw_count+=len(rows)
        if not rows:
            break
        for row in rows:
            job=normalize_job(spec,row)
            if job:
                jobs[clean(job.get("position_id"))]=job
        if len(rows)<PAGE_SIZE:
            break
    values=list(jobs.values())
    return values,{
        "key":clean(spec.get("key")),"company":clean(spec.get("company")),"org":spec.get("org"),"site":spec.get("site"),
        "official_url":portal_url(spec),"pages":len(page_sizes),"page_sizes":page_sizes,"raw_rows":raw_count,"unique_jobs":len(values),
        "campus_rows":sum(1 for job in values if re.search(r"校招|校园|应届|秋招|春招|2027|27届", " ".join([job.get("role", ""),job.get("batch", ""),job.get("graduation", "")]), re.I)),
        "year_2027_rows":sum(1 for job in values if "2027" in " ".join([job.get("role", ""),job.get("batch", ""),job.get("graduation", ""),job.get("jd", "")])),
        "beijing_rows":sum(1 for job in values if "北京" in clean(job.get("location"))),
    }


def collect_specs(specs: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spec_list=list(specs);jobs=[];statuses=[]
    with ThreadPoolExecutor(max_workers=min(WORKERS,max(1,len(spec_list)))) as pool:
        futures={pool.submit(fetch_company,spec):spec for spec in spec_list}
        for future in as_completed(futures):
            spec=futures[future]
            try:
                rows,diag=future.result();jobs.extend(rows)
                statuses.append({"key":clean(spec.get("key")),"company":clean(spec.get("company")),"source":f"direct-official:moka:{clean(spec.get('key'))}","ok":True,"count":len(rows),"error":"","diagnostics":diag})
            except Exception as exc:
                statuses.append({"key":clean(spec.get("key")),"company":clean(spec.get("company")),"source":f"direct-official:moka:{clean(spec.get('key'))}","ok":False,"count":0,"error":f"{type(exc).__name__}: {clean(exc)[:260]}","diagnostics":{}})
    statuses.sort(key=lambda x:x.get("company") or x.get("key"))
    return jobs,statuses


def collect_priority_moka() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs=load_priority_specs();jobs,statuses=collect_specs(specs)
    return jobs,{"sources":statuses,"companies":len(specs),"jobs":len(jobs)}


def collect_all_moka() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs=parse_moka_seed_file();jobs,statuses=collect_specs(specs)
    ok=sum(1 for row in statuses if row.get("ok"));
    return jobs,{"sources":statuses,"companies":len(specs),"companies_ok":ok,"jobs":len(jobs),"seed_path":str(SEED_PATH)}


def source_key(job: dict[str, Any]) -> str:
    source=clean(job.get("source"))
    return source if source.startswith("direct-official:moka:") or source=="direct-official:shopee" else ""


def merge_with_previous(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    successful=set()
    for row in diagnostics.get("sources",[]):
        if not row.get("ok"):
            continue
        key=clean(row.get("key"));successful.add("direct-official:shopee" if key=="shopee" else f"direct-official:moka:{key}")
    out=[]
    for job in existing:
        if not isinstance(job,dict):
            continue
        key=source_key(job)
        if key and key in successful:
            continue
        out.append(job)
    seen={(clean(j.get("company")).lower(),clean(j.get("role")).lower(),clean(j.get("location")).lower(),clean(j.get("position_id") or j.get("apply_url")).lower()) for j in out}
    for job in fresh:
        ident=(clean(job.get("company")).lower(),clean(job.get("role")).lower(),clean(job.get("location")).lower(),clean(job.get("position_id") or job.get("apply_url")).lower())
        if ident not in seen:
            seen.add(ident);out.append(job)
    return out


def main() -> int:
    jobs,diag=collect_all_moka()
    if not diag.get("companies_ok"):
        raise RuntimeError("all public Moka sources failed; previous catalogue preserved")
    payload=json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"schema_version":3,"jobs":[]}
    existing=payload.get("jobs",[]) if isinstance(payload,dict) else []
    if existing and isinstance(existing[0],dict) and "c" in existing[0]:
        raise RuntimeError("moka_public_harvester.py must run before compact_feed.py")
    merged=merge_with_previous(existing if isinstance(existing,list) else [],jobs,diag)
    payload=dict(payload) if isinstance(payload,dict) else {}
    payload.update({"schema_version":3,"generated_at":utc_now(),"jobs":merged})
    JOBS_PATH.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")

    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group={"name":"moka-public-federation","label":"企业招聘官网 · Moka公开职位联邦","url":"https://app.mokahr.com/","ok":True,"count":len(jobs),"error":"","diagnostics":diag}
    sources=[row for row in status.get("sources",[]) if not isinstance(row,dict) or row.get("name")!=group["name"]]
    sources.insert(0,group);status.update({"sources":sources,"catalog_count":len(merged),"generated_at":utc_now()})
    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    shopee=[job for job in jobs if "Shopee" in clean(job.get("company"))]
    print(json.dumps({"moka_jobs":len(jobs),"companies":diag.get("companies"),"companies_ok":diag.get("companies_ok"),"shopee":len(shopee)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
