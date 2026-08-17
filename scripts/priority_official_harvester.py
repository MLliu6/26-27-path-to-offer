#!/usr/bin/env python3
"""Priority China campus-source harvester for Path to Offer v0.9.

This is the product-facing source layer for high-value Chinese employers. It is
separate from broad fallback federation and does four things:

1. maintains a health ledger for employer-owned recruiting portals;
2. crawls server-rendered employer campus pages (currently CASIC/Beisen style);
3. spiders company-owned career pages for real job detail pages (e.g. Rhino);
4. watches authoritative recruitment indexes (e.g. SASAC) for new 2027 campaigns.

No login/CAPTCHA bypass, credential replay, proxy rotation, stealth automation or
anti-bot evasion is used. Sources that cannot be read anonymously are recorded as
unavailable rather than silently replaced by scraped third-party rows.
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_official_sources.json"
UA = "PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = 14
MAX_TEXT = 6000
CAMPUS_RE = re.compile(r"2027|27届|校园招聘|校招|应届|毕业生|实习", re.I)
TECH_RE = re.compile(r"大模型|人工智能|AI|算法|软件|计算机|芯片|编译|CUDA|GPU|NPU|机器人|自动驾驶|数据|研发|开发|测试|嵌入式", re.I)
CAREER_LINK_RE = re.compile(r"招聘|职位|岗位|人才|加入|career|careers|job|jobs|join|recruit", re.I)
JOB_PAGE_RE = re.compile(r"职位描述|岗位职责|工作职责|任职资格|任职要求|岗位要求", re.I)


def sess() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5"})
    return s


def fetch_text(s: requests.Session, url: str, timeout: int = TIMEOUT) -> tuple[str, str, int]:
    r = s.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        return json.dumps(r.json(), ensure_ascii=False), r.url, r.status_code
    r.encoding = r.apparent_encoding or r.encoding
    return r.text, r.url, r.status_code


def plain(html: str) -> str:
    return clean(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))


def normalize_job(*, company: str, role: str, location: str, batch: str, company_type: str,
                  source: str, source_label: str, source_url: str, apply_url: str,
                  jd: str = "", updated_at: str = "", graduation: str = "", department: str = "",
                  notice_url: str = "") -> dict[str, Any] | None:
    company, role = clean(company), clean(role)
    if not company or not role:
        return None
    out = {
        "source": source, "source_label": source_label, "source_url": source_url,
        "updated_at": clean(updated_at)[:10], "company": company, "department": clean(department),
        "role": role, "location": clean(location), "salary": "", "batch": clean(batch),
        "company_type": clean(company_type), "industry": "", "graduation": clean(graduation),
        "education": "", "notice_url": clean(notice_url or apply_url), "apply_url": clean(apply_url),
        "jd": clean(jd)[:MAX_TEXT] or role, "tags": ["官方招聘", batch] if batch else ["官方招聘"],
        "observed_via": "priority-official-harvester",
    }
    out["id"] = stable_id(company, role, out["location"], out["apply_url"])
    return out


def watch_one(entry: dict[str, Any]) -> dict[str, Any]:
    company, url = clean(entry.get("company")), clean(entry.get("url"))
    result = {"company": company, "category": entry.get("category", ""), "url": url, "ok": False,
              "campus_signal": False, "year_2027": False, "status": 0, "error": ""}
    if not url:
        result["error"] = "missing URL"; return result
    try:
        html, final, status = fetch_text(sess(), url)
        text = plain(html)[:20000]
        result.update(ok=True, status=status, final_url=final, campus_signal=bool(CAMPUS_RE.search(text)), year_2027="2027" in text)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {clean(exc)[:180]}"
    return result


def ancestor_text(a) -> str:
    node = a
    best = clean(a.get_text(" ", strip=True))
    for _ in range(5):
        node = getattr(node, "parent", None)
        if node is None: break
        text = clean(node.get_text(" ", strip=True))
        if 20 <= len(text) <= 3000:
            best = text
            if "工作" in text or "发布时间" in text or "招聘" in text: break
    return best


def role_from_block(anchor_text: str, block: str) -> str:
    a = clean(anchor_text)
    if a and not re.fullmatch(r"立即申请|查看详情|申请|详情", a): return a[:140]
    patterns = [
        r"((?:2026/)?2027届[^|｜]{2,90}?)(?=\s*(?:招聘类别|职位类别|招聘单位|工作城市|工作地点|发布时间|薪资区间))",
        r"职位名称\s*[:：]?\s*([^|｜]{2,90}?)(?=\s*(?:专业类型|工作地点|发布时间))",
    ]
    for p in patterns:
        m = re.search(p, block, re.I)
        if m: return clean(m.group(1))[:140]
    return ""


def parse_location(block: str) -> str:
    for p in [r"工作城市\s*[:：]\s*([^|｜]{2,80}?)(?=\s*(?:发布时间|薪资|学历|工作职责|任职))",
              r"工作地点\s*[:：]\s*([^|｜]{2,80}?)(?=\s*(?:发布时间|薪资|学历|工作职责|任职))"]:
        m = re.search(p, block, re.I)
        if m: return clean(m.group(1))
    return ""


def crawl_zhiye(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    company = clean(entry.get("company")); tpl = clean(entry.get("list_url")); official = clean(entry.get("official_url"))
    max_pages = max(1, min(80, int(entry.get("max_pages") or 20))); required = clean(entry.get("require_year"))
    s = sess(); jobs: dict[str, dict[str, Any]] = {}; pages_ok = 0
    for page in range(1, max_pages + 1):
        url = tpl.format(page=page)
        try: html, _, _ = fetch_text(s, url)
        except Exception: break
        soup = BeautifulSoup(html, "html.parser")
        anchors = [a for a in soup.find_all("a", href=True) if "xiangqing?jobId=" in a.get("href", "")]
        if not anchors:
            if page == 1:
                # Some zhiye variants render the list at /campus?p=N.
                alt = official.rstrip('/') + f"?p={page}"
                try:
                    html, _, _ = fetch_text(s, alt); soup = BeautifulSoup(html, "html.parser")
                    anchors = [a for a in soup.find_all("a", href=True) if "xiangqing?jobId=" in a.get("href", "")]
                except Exception: pass
        if not anchors: break
        pages_ok += 1; added = 0
        for a in anchors:
            href = urljoin(official or url, a.get("href", "")); block = ancestor_text(a); role = role_from_block(a.get_text(" ", strip=True), block)
            if not role: continue
            if required and required not in (role + " " + block): continue
            location = parse_location(block)
            mdate = re.search(r"发布时间\s*[:：]\s*(20\d{2}-\d{1,2}-\d{1,2})", block)
            dept = ""
            md = re.search(r"招聘单位\s*[:：]\s*([^|｜]{2,100}?)(?=\s*(?:工作城市|工作地点|发布时间|薪资))", block)
            if md: dept = clean(md.group(1))
            job = normalize_job(company=company, role=role, location=location, batch="2027校园招聘" if "2027" in role+block else "校园招聘",
                company_type=entry.get("company_type", "央企/国企"), source=f"priority-official:zhiye:{urlparse(official).hostname}",
                source_label=f"{company}校园招聘官网", source_url=official, apply_url=href, jd=block,
                updated_at=mdate.group(1) if mdate else "", graduation="2027届" if "2027" in role+block else "", department=dept)
            if job: jobs[href] = job; added += 1
        if added == 0 and required: break
        time.sleep(0.12)
    return list(jobs.values()), {"pages_ok": pages_ok, "unique_jobs": len(jobs), "official_url": official}


def spider_career(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    company, start = clean(entry.get("company")), clean(entry.get("start_url")); max_pages = max(3, min(80, int(entry.get("max_pages") or 30))); max_depth = max(1, min(3, int(entry.get("max_depth") or 2)))
    host = (urlparse(start).hostname or "").lower(); s = sess(); q = deque([(start, 0)]); seen: set[str] = set(); jobs: dict[str, dict[str, Any]] = {}; failures = 0
    while q and len(seen) < max_pages:
        url, depth = q.popleft()
        if url in seen: continue
        seen.add(url)
        try: html, final, _ = fetch_text(s, url)
        except Exception: failures += 1; continue
        soup = BeautifulSoup(html, "html.parser"); text = clean(soup.get_text(" ", strip=True))
        if JOB_PAGE_RE.search(text) and len(text) >= 180:
            heading = ""
            for tag in ("h1","h2","h3","title"):
                el = soup.find(tag)
                if el and clean(el.get_text(" ", strip=True)):
                    heading = clean(el.get_text(" ", strip=True)); break
            heading = re.sub(r"^.*?招聘\s*", "", heading).strip(" -|｜") or "招聘岗位"
            if len(heading) <= 120:
                loc = ""
                m = re.search(r"【(?:全职|实习)[-—–]?([^】]{2,12})】", text)
                if m: loc = clean(m.group(1))
                if not loc:
                    m = re.search(r"(?:工作地点|办公地点)\s*[:：]\s*([^,，。；;]{2,30})", text)
                    if m: loc = clean(m.group(1))
                job = normalize_job(company=company, role=heading, location=loc, batch="校园招聘" if CAMPUS_RE.search(text) else "公开招聘",
                    company_type=entry.get("company_type", "民营/科技"), source=f"priority-official:spider:{host}", source_label=f"{company}招聘官网",
                    source_url=start, apply_url=final, jd=text, graduation="2027届" if "2027" in text else "")
                if job: jobs[final] = job
        if depth < max_depth:
            for a in soup.find_all("a", href=True):
                href = urljoin(final, a.get("href", "")); u = urlparse(href)
                if (u.hostname or "").lower() != host: continue
                label = clean(a.get_text(" ", strip=True)) + " " + href
                if CAREER_LINK_RE.search(label) and href not in seen: q.append((href, depth + 1))
    return list(jobs.values()), {"pages_seen": len(seen), "failures": failures, "unique_jobs": len(jobs), "start_url": start}


def campaign_rows(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence = clean(entry.get("evidence_url")); official = clean(entry.get("official_url")); company = clean(entry.get("company")); roles = entry.get("roles") or []
    ok = False; error = ""; text = ""
    try:
        html, _, _ = fetch_text(sess(), evidence); text = plain(html); ok = company[:2] in text and ("2027" in text or "27届" in text)
    except Exception as exc: error = f"{type(exc).__name__}: {clean(exc)[:160]}"
    # Evidence URLs can transiently fail. Keep the campaign only when its
    # publication date and role list are explicitly curated in the registry;
    # diagnostics remain honest about live verification.
    rows: list[dict[str, Any]] = []
    for role in roles if isinstance(roles, list) else []:
        job = normalize_job(company=company, role=clean(role), location=entry.get("locations", ""), batch=entry.get("batch", "2027校园招聘"),
            company_type=entry.get("company_type", ""), source="priority-campaign:verified-announcement", source_label=f"{company} 2027校园招聘",
            source_url=official, apply_url=official, notice_url=evidence, jd=(text[:MAX_TEXT] if ok else clean(role)), updated_at=entry.get("published", ""), graduation=entry.get("graduation", "2027届"))
        if job: rows.append(job)
    return rows, {"evidence_url": evidence, "live_verified": ok, "error": error, "rows": len(rows)}


def infer_company_from_title(title: str) -> str:
    t = clean(title)
    for suffix in ["2027届", "2027", "校招", "校园招聘", "招聘"]:
        if suffix in t:
            head = t.split(suffix, 1)[0].strip(" |｜-—：:")
            if 2 <= len(head) <= 40: return head
    return t[:40]


def sasac_discovery(entry: dict[str, Any], watch_map: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = clean(entry.get("url")); rows: list[dict[str, Any]] = []; seen: set[str] = set()
    try: html, final, _ = fetch_text(sess(), url)
    except Exception as exc: return [], {"ok":False,"error":f"{type(exc).__name__}: {clean(exc)[:180]}"}
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))
        if not title or "2027" not in title or "招聘" not in title: continue
        href = urljoin(final, a.get("href", ""))
        if href in seen: continue
        seen.add(href); company = infer_company_from_title(title)
        official = next((v for k,v in watch_map.items() if k in company or company in k), href)
        job = normalize_job(company=company, role=title, location="全国", batch="2027校园招聘", company_type="央企/国企",
            source="priority-discovery:sasac", source_label="国务院国资委·2027招聘动态", source_url=url, apply_url=official,
            notice_url=href, jd=title, graduation="2027届")
        if job: rows.append(job)
    return rows, {"ok":True,"rows":len(rows),"index":url}


def identity(job: dict[str, Any]) -> tuple[str,str,str,str]:
    return (clean(job.get("company")).lower(), clean(job.get("role")).lower(), clean(job.get("location")).lower(), clean(job.get("apply_url") or job.get("notice_url")).lower())


def merge(existing: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[tuple[str,str,str,str], dict[str,Any]] = {}
    for job in existing:
        if isinstance(job, dict) and clean(job.get("company")) and clean(job.get("role")): out[identity(job)] = job
    for job in fresh:
        key = identity(job); old = out.get(key)
        if old is None: out[key] = job; continue
        if str(job.get("source","")).startswith("priority-official"):
            merged = dict(old); merged.update({k:v for k,v in job.items() if v not in (None,"",[],{})}); out[key] = merged
    return list(out.values())


def main() -> int:
    cfg = json.loads(REGISTRY.read_text(encoding="utf-8")); payload = json.loads(JOBS_PATH.read_text(encoding="utf-8")); existing = payload.get("jobs", [])
    if existing and isinstance(existing[0], dict) and "c" in existing[0]: raise RuntimeError("priority_official_harvester.py must run before compact_feed.py")

    watch_results=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs=[pool.submit(watch_one,e) for e in cfg.get("watch",[]) if isinstance(e,dict)]
        for f in as_completed(futs): watch_results.append(f.result())
    watch_results.sort(key=lambda x:(x.get("category",""),x.get("company","")))
    watch_map={clean(x.get("company")):clean(x.get("url")) for x in cfg.get("watch",[]) if isinstance(x,dict)}

    fresh=[]; adapter_results=[]
    for entry in cfg.get("zhiye_campus",[]):
        try: jobs,diag=crawl_zhiye(entry); fresh.extend(jobs); adapter_results.append({"company":entry.get("company"),"type":"zhiye-campus","ok":bool(jobs),"count":len(jobs),"diagnostics":diag})
        except Exception as exc: adapter_results.append({"company":entry.get("company"),"type":"zhiye-campus","ok":False,"count":0,"error":f"{type(exc).__name__}: {clean(exc)[:180]}"})
    for entry in cfg.get("career_spiders",[]):
        try: jobs,diag=spider_career(entry); fresh.extend(jobs); adapter_results.append({"company":entry.get("company"),"type":"career-spider","ok":bool(jobs),"count":len(jobs),"diagnostics":diag})
        except Exception as exc: adapter_results.append({"company":entry.get("company"),"type":"career-spider","ok":False,"count":0,"error":f"{type(exc).__name__}: {clean(exc)[:180]}"})
    for entry in cfg.get("campaigns",[]):
        jobs,diag=campaign_rows(entry); fresh.extend(jobs); adapter_results.append({"company":entry.get("company"),"type":"campaign","ok":diag.get("live_verified",False),"count":len(jobs),"diagnostics":diag})
    for entry in cfg.get("discovery_indexes",[]):
        if entry.get("type")=="sasac":
            jobs,diag=sasac_discovery(entry,watch_map); fresh.extend(jobs); adapter_results.append({"company":"国务院国资委招聘索引","type":"discovery-index","ok":diag.get("ok",False),"count":len(jobs),"diagnostics":diag})

    merged=merge(existing if isinstance(existing,list) else [],fresh); out=dict(payload); out["schema_version"]=3; out["generated_at"]=utc_now(); out["jobs"]=merged
    JOBS_PATH.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")

    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group={"name":"priority-official-sources","label":"重点国内企业官网 / 央国企校招雷达","url":"","ok":bool(fresh),"count":len(fresh),"error":"",
           "diagnostics":{"registry":"sources/priority_official_sources.json","watch_total":len(watch_results),"watch_ok":sum(1 for x in watch_results if x.get("ok")),"watch_2027":sum(1 for x in watch_results if x.get("year_2027")),"watch":watch_results,"adapters":adapter_results}}
    sources=[s for s in status.get("sources",[]) if not isinstance(s,dict) or s.get("name")!=group["name"]]; sources.insert(0,group); status["sources"]=sources; status["catalog_count"]=len(merged); status["generated_at"]=utc_now()
    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"priority official: fresh={len(fresh)} merged={len(merged)} watch={len(watch_results)} ok={group['diagnostics']['watch_ok']} 2027={group['diagnostics']['watch_2027']}")
    for r in adapter_results: print(" priority",r.get("company"),r.get("type"),"count=",r.get("count"),"ok=",r.get("ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
