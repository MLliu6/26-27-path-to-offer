#!/usr/bin/env python3
"""2027 recruiting discovery from public university employment sites.

University career centres are valuable breadth sensors: they receive current
campus announcements from large firms, SOEs, banks and startups, including
companies whose own career site is JavaScript-heavy or not search-indexed.

Rows from this layer are clearly marked as discovery/evidence. If a detail page
publishes an external employer recruiting URL, that URL becomes the apply URL;
otherwise the university announcement remains the notice URL. The layer never
claims a university page is the employer's canonical recruiting system.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"sources"/"campus_discovery_sources.json"
UA="PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT=16
CAMPAIGN=re.compile(r"2027|27届",re.I)
RECRUIT=re.compile(r"招聘|校招|校园|提前批|秋招|实习|探索者|人才计划",re.I)
SKIP=re.compile(r"讲座|课堂|求职|就业指导|教师|博士后|事业单位公开招聘",re.I)
LOCATIONS=["北京","上海","深圳","广州","杭州","南京","苏州","成都","武汉","西安","天津","重庆","长沙","合肥","无锡","厦门","青岛","济南","宁波","东莞","珠海","佛山","大连","沈阳","郑州","福州"]
APPLY_HOST_HINT=re.compile(r"career|careers|job|jobs|zhaopin|recruit|campus|zhiye|feishu|moka|liepin|51job",re.I)


def session():
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.6"});return s


def fetch(s,url):
    r=s.get(url,timeout=TIMEOUT,allow_redirects=True);r.raise_for_status();r.encoding=r.apparent_encoding or r.encoding;return r


def title_company(title:str,body:str)->str:
    for pat in [r"(?:单位名称|公司名称|单位名片\s*单位名称)\s*[:：]?\s*([^\n|｜]{2,70})",r"^([^|｜]{2,60}?)(?=2027|27届)"]:
        m=re.search(pat,body if "单位" in pat else title,re.I)
        if m:
            x=clean(m.group(1)).strip(" -—：:")
            if 2<=len(x)<=70:return x
    # Remove common campaign suffixes from the visible heading.
    x=re.split(r"2027|27届",title,1)[0].strip(" -—：:｜|")
    x=re.sub(r"^(?:校招|招聘信息|招聘公告)\s*[:：-]?\s*","",x)
    return x[:70] if 2<=len(x)<=70 else ""


def location_from(text:str)->str:
    hits=[]
    for c in LOCATIONS:
        if c in text and c not in hits:hits.append(c)
    return "/".join(hits[:8])


def external_apply(soup:BeautifulSoup,base_url:str,university_host:str)->str:
    candidates=[]
    for a in soup.find_all("a",href=True):
        href=urljoin(base_url,a.get("href",""));u=urlparse(href);host=(u.hostname or "").lower();label=clean(a.get_text(" ",strip=True))
        if u.scheme not in {"http","https"} or not host:continue
        if host==university_host or host.endswith('.'+university_host):continue
        if host.endswith("weixin.qq.com") or host.endswith("mp.weixin.qq.com"):
            candidates.append((2,href));continue
        score=0
        if APPLY_HOST_HINT.search(host+" "+href):score+=5
        if re.search(r"投递|网申|申请|官网|招聘",label,re.I):score+=3
        if score:candidates.append((score,href))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else ""


def normalize(company,title,detail_url,apply_url,body,source_name):
    location=location_from(body)
    batch="2027实习/提前批" if re.search(r"实习|提前批",title+body,re.I) else ("2027秋招" if "秋招" in title+body else "2027校园招聘")
    job={"source":"campus-discovery:university","source_label":f"高校就业网·{source_name}","source_url":detail_url,"updated_at":"","company":company,"department":"","role":title[:180],"location":location,"salary":"","batch":batch,"company_type":"","industry":"","graduation":"2027届","education":"","notice_url":detail_url,"apply_url":apply_url or detail_url,"jd":body[:5000],"tags":["2027","高校就业网发现",batch],"observed_via":"public-university-employment-site"}
    job["id"]=stable_id(company,title,location,job["apply_url"]);return job


def candidate_links(soup,base_url):
    out=[];seen=set()
    for a in soup.find_all("a",href=True):
        text=clean(a.get_text(" ",strip=True))
        if not text or not CAMPAIGN.search(text) or not RECRUIT.search(text) or SKIP.search(text):continue
        href=urljoin(base_url,a.get("href",""));u=urlparse(href)
        if u.scheme not in {"http","https"} or href in seen:continue
        seen.add(href);out.append((text[:180],href))
    return out


def crawl_source(entry):
    name,url=entry.get("name",""),entry.get("url","");max_details=max(10,min(120,int(entry.get("max_details") or 50)));s=session();diag={"name":name,"url":url,"ok":False,"index_candidates":0,"details_ok":0,"rows":0,"external_apply":0,"error":""};jobs=[]
    try:
        r=fetch(s,url);soup=BeautifulSoup(r.text,"html.parser");links=candidate_links(soup,r.url)[:max_details];diag["index_candidates"]=len(links);host=(urlparse(r.url).hostname or "").lower()
        for visible,href in links:
            try:
                rr=fetch(s,href);ss=BeautifulSoup(rr.text,"html.parser");body=clean(ss.get_text(" ",strip=True));title=visible
                h=ss.find(["h1","h2"])
                if h and CAMPAIGN.search(clean(h.get_text(" ",strip=True))):title=clean(h.get_text(" ",strip=True))[:180]
                if not CAMPAIGN.search(title+" "+body[:1500]):continue
                company=title_company(title,body)
                if not company:continue
                apply=external_apply(ss,rr.url,host)
                jobs.append(normalize(company,title,rr.url,apply,body,name));diag["details_ok"]+=1;diag["external_apply"]+=bool(apply)
            except Exception:continue
            time.sleep(.05)
        # Some career-home pages themselves list campaign titles and do not use
        # traditional detail links. Keep the visible campaign as a discovery row.
        if not jobs:
            for visible,href in links[:20]:
                company=title_company(visible,visible)
                if company:jobs.append(normalize(company,visible,href,"",visible,name))
        dedup={j["company"].lower()+"|"+j["role"].lower()+"|"+j["apply_url"]:j for j in jobs};jobs=list(dedup.values());diag.update(ok=True,rows=len(jobs))
    except Exception as exc:diag["error"]=f"{type(exc).__name__}: {clean(exc)[:180]}"
    return diag,jobs


def identity(j):return (clean(j.get("company")).lower(),clean(j.get("role")).lower(),clean(j.get("location")).lower(),clean(j.get("apply_url") or j.get("notice_url")).lower())


def main():
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"));fresh=[];diags=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs=[pool.submit(crawl_source,e) for e in cfg.get("sources",[]) if isinstance(e,dict)]
        for f in as_completed(futs):d,rows=f.result();diags.append(d);fresh.extend(rows)
    payload=json.loads(JOBS_PATH.read_text(encoding="utf-8"));existing=payload.get("jobs",[])
    if existing and isinstance(existing[0],dict) and "c" in existing[0]:raise RuntimeError("university_2027_discovery.py must run before compact_feed.py")
    merged={identity(j):j for j in existing if isinstance(j,dict) and clean(j.get("company")) and clean(j.get("role"))}
    for j in fresh:
        key=identity(j)
        if key not in merged:merged[key]=j
    payload["schema_version"]=3;payload["generated_at"]=utc_now();payload["jobs"]=list(merged.values());JOBS_PATH.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group={"name":"university-2027-discovery","label":"高校就业网·2027招聘发现网络","url":"","ok":any(x.get('ok') for x in diags),"count":len(fresh),"error":"","diagnostics":{"sources":diags,"sources_ok":sum(1 for x in diags if x.get('ok')),"external_apply":sum(x.get('external_apply',0) for x in diags)}}
    sources=[s for s in status.get("sources",[]) if not isinstance(s,dict) or s.get("name")!=group["name"]];sources.insert(0,group);status["sources"]=sources;status["catalog_count"]=len(payload["jobs"]);status["generated_at"]=utc_now();STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("university discovery:",[(x.get('name'),x.get('index_candidates'),x.get('rows'),x.get('external_apply'),x.get('ok')) for x in diags],"total",len(fresh))
    return 0

if __name__=="__main__":raise SystemExit(main())
