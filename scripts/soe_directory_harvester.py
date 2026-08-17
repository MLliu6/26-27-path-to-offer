#!/usr/bin/env python3
"""Central-SOE official-domain discovery from the government enterprise directory.

The source of company/domain identities is the State Council/SASAC-provided
central-enterprise directory. We then inspect those company-owned public pages
for visible recruiting links and 2027 campaign links. This converts coverage
from a hand-maintained list into an expandable official-domain graph.

No login, CAPTCHA, search-engine scraping, stealth or access-control bypass is
used. A company can be discovered without producing a job row; only visible
2027 recruiting links become catalogue entries.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

DIRECTORY="https://gjzwfw.www.gov.cn/col/col1560/"
ROOT=Path(__file__).resolve().parents[1]
UA="PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT=14
COMPANY_RE=re.compile(r"(?:集团|有限责任|股份有限|有限公司|总公司|研究院|研究总院)")
RECRUIT_RE=re.compile(r"招聘|人才|加入我们|career|careers|job|jobs|recruit",re.I)
CAMPAIGN_RE=re.compile(r"(?:2027|27届).{0,50}(?:招聘|校招|校园|秋招|毕业生|实习)|(?:招聘|校招|校园|秋招|毕业生|实习).{0,50}(?:2027|27届)",re.I)
GOV_HOSTS=("gov.cn","sasac.gov.cn")


def sess():
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.6"});return s


def company_from_context(a) -> str:
    candidates=[clean(a.get_text(" ",strip=True)),clean(a.get("title"))]
    node=a
    for _ in range(4):
        node=getattr(node,"parent",None)
        if node is None:break
        text=clean(node.get_text(" ",strip=True))
        if 2<=len(text)<=300:candidates.append(text)
    for text in candidates:
        if not text:continue
        parts=re.split(r"https?://|官网地址|官网|\s{2,}|[|｜]",text)
        for p in parts:
            p=clean(re.sub(r"^\d+[.、\s]*","",p))
            if COMPANY_RE.search(p) and 4<=len(p)<=80:return p[:80]
    return ""


def discover_directory() -> tuple[list[dict[str,str]],dict[str,Any]]:
    s=sess();queue=[DIRECTORY];seen=set();companies={};fail=[]
    while queue and len(seen)<8:
        url=queue.pop(0)
        if url in seen:continue
        seen.add(url)
        try:
            r=s.get(url,timeout=TIMEOUT,allow_redirects=True);r.raise_for_status();r.encoding=r.apparent_encoding or r.encoding;soup=BeautifulSoup(r.text,"html.parser")
        except Exception as exc:
            fail.append(f"{url}: {type(exc).__name__}: {clean(exc)[:120]}");continue
        for a in soup.find_all("a",href=True):
            href=urljoin(r.url,a.get("href",""));u=urlparse(href);host=(u.hostname or "").lower()
            if not host:continue
            if any(host.endswith(x) for x in GOV_HOSTS):
                if "col1560" in href and href not in seen and href not in queue:queue.append(href)
                continue
            if u.scheme not in {"http","https"}:continue
            company=company_from_context(a)
            if not company:continue
            companies.setdefault(company,{"company":company,"url":href,"host":host})
    return list(companies.values()),{"directory_pages":len(seen),"companies":len(companies),"failures":fail[:20]}


def inspect_company(entry:dict[str,str])->tuple[dict[str,Any],list[dict[str,Any]]]:
    company,url=entry["company"],entry["url"];diag={"company":company,"url":url,"ok":False,"recruit_links":0,"campaigns":0,"error":""};rows=[]
    try:
        s=sess();r=s.get(url,timeout=TIMEOUT,allow_redirects=True);r.raise_for_status();r.encoding=r.apparent_encoding or r.encoding;soup=BeautifulSoup(r.text,"html.parser")
        recruit=[]
        for a in soup.find_all("a",href=True):
            label=clean(a.get_text(" ",strip=True));href=urljoin(r.url,a.get("href",""));
            if RECRUIT_RE.search(label+" "+href):recruit.append((label,href))
            if CAMPAIGN_RE.search(label):
                job={"source":"priority-official:soe-directory","source_label":f"{company}官网·央企目录发现","source_url":url,"updated_at":"","company":company,"department":"","role":label[:180],"location":"","salary":"","batch":"2027校园招聘","company_type":"央企","industry":"","graduation":"2027届","education":"","notice_url":href,"apply_url":href,"jd":label[:1000],"tags":["央企","官方招聘","2027"],"observed_via":"state-directory-to-employer-domain"}
                job["id"]=stable_id(company,job["role"],"",href);rows.append(job)
        # inspect a small number of visible recruiting landing pages on the same
        # employer domain. This is enough to catch home->recruit->2027 without a
        # broad/costly site crawl.
        basehost=(urlparse(r.url).hostname or "").lower();visited=set()
        for _,href in recruit[:4]:
            h=(urlparse(href).hostname or "").lower()
            if not h or (h!=basehost and not h.endswith('.'+basehost) and not basehost.endswith('.'+h)):continue
            if href in visited:continue
            visited.add(href)
            try:
                rr=s.get(href,timeout=TIMEOUT,allow_redirects=True);rr.raise_for_status();rr.encoding=rr.apparent_encoding or rr.encoding;ss=BeautifulSoup(rr.text,"html.parser")
                for a in ss.find_all("a",href=True):
                    label=clean(a.get_text(" ",strip=True))
                    if not CAMPAIGN_RE.search(label):continue
                    link=urljoin(rr.url,a.get("href",""));job={"source":"priority-official:soe-directory","source_label":f"{company}官网·央企目录发现","source_url":url,"updated_at":"","company":company,"department":"","role":label[:180],"location":"","salary":"","batch":"2027校园招聘","company_type":"央企","industry":"","graduation":"2027届","education":"","notice_url":link,"apply_url":link,"jd":label[:1000],"tags":["央企","官方招聘","2027"],"observed_via":"state-directory-to-employer-domain"};job["id"]=stable_id(company,job["role"],"",link);rows.append(job)
            except Exception:pass
        dedup={j["apply_url"]+"|"+j["role"]:j for j in rows};rows=list(dedup.values());diag.update(ok=True,recruit_links=len(recruit),campaigns=len(rows),final_url=r.url)
    except Exception as exc:diag["error"]=f"{type(exc).__name__}: {clean(exc)[:160]}"
    return diag,rows


def identity(j):return (clean(j.get("company")).lower(),clean(j.get("role")).lower(),clean(j.get("location")).lower(),clean(j.get("apply_url") or j.get("notice_url")).lower())


def main():
    companies,ddiag=discover_directory();fresh=[];checks=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs={pool.submit(inspect_company,e):e for e in companies[:140]}
        for f in as_completed(futs):
            d,rows=f.result();checks.append(d);fresh.extend(rows)
    payload=json.loads(JOBS_PATH.read_text(encoding="utf-8"));existing=payload.get("jobs",[])
    if existing and isinstance(existing[0],dict) and "c" in existing[0]:raise RuntimeError("soe_directory_harvester.py must run before compact_feed.py")
    merged={identity(j):j for j in existing if isinstance(j,dict) and clean(j.get("company")) and clean(j.get("role"))}
    for j in fresh:merged[identity(j)]=j
    payload["schema_version"]=3;payload["generated_at"]=utc_now();payload["jobs"]=list(merged.values());JOBS_PATH.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group={"name":"central-soe-official-directory","label":"国务院/SASAC央企名录→企业官网招聘雷达","url":DIRECTORY,"ok":bool(companies),"count":len(fresh),"error":"","diagnostics":{**ddiag,"sites_checked":len(checks),"sites_ok":sum(1 for x in checks if x.get('ok')),"sites_with_recruit_links":sum(1 for x in checks if x.get('recruit_links',0)>0),"sites_with_2027_campaigns":sum(1 for x in checks if x.get('campaigns',0)>0),"top":sorted(checks,key=lambda x:(x.get('campaigns',0),x.get('recruit_links',0)),reverse=True)[:30]}}
    sources=[s for s in status.get("sources",[]) if not isinstance(s,dict) or s.get("name")!=group["name"]];sources.insert(0,group);status["sources"]=sources;status["catalog_count"]=len(payload["jobs"]);status["generated_at"]=utc_now();STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"SOE directory: companies={len(companies)} checked={len(checks)} recruit_sites={group['diagnostics']['sites_with_recruit_links']} campaigns={len(fresh)}")
    return 0

if __name__=="__main__":raise SystemExit(main())
