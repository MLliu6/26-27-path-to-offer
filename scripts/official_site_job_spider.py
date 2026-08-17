#!/usr/bin/env python3
"""Bounded same-origin job-page spider for employer-owned career websites.

Some startups expose real job pages on their own CMS but do not provide a JSON
API and do not use predictable `/careers/...` paths. This crawler follows a
small bounded set of same-origin HTML links and recognizes pages by job-content
markers (岗位职责 / 任职要求 / 职位描述). It is therefore useful for companies
such as 辉羲智能 without depending on a third-party job list.

It does not cross login walls, solve CAPTCHAs, execute stealth automation, or
crawl unlimited pages. The registry controls per-site page/depth budgets.
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import JOBS_PATH, STATUS_PATH, clean, stable_id, utc_now

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources"/"priority_official_sources.json"
UA="PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT=15
JOB_RE=re.compile(r"岗位职责|工作职责|职位描述|任职资格|任职要求|岗位要求",re.I)
CAREER_RE=re.compile(r"招聘|职位|岗位|人才|加入|career|careers|job|jobs|join|recruit",re.I)
SKIP_EXT=re.compile(r"\.(?:jpg|jpeg|png|gif|svg|webp|pdf|zip|rar|7z|mp4|mp3|css|js|ico)(?:\?|$)",re.I)
LOC_RE=re.compile(r"【(?:全职|实习)[-—–]?([^】]{2,16})】|(?:工作地点|办公地点|职位地点)\s*[:：]\s*([^,，。；;]{2,30})")


def sess():
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.5"});return s


def role_title(soup:BeautifulSoup,text:str,company:str)->str:
    for selector in ["h1","h2","h3","title"]:
        el=soup.find(selector)
        if not el:continue
        title=clean(el.get_text(" ",strip=True))
        title=re.sub(rf"^{re.escape(company)}\s*[-|｜:]?\s*","",title).strip()
        title=re.sub(r"^招聘\s*[-|｜:]?\s*","",title).strip()
        if 2<=len(title)<=120 and not re.fullmatch(r"招聘|加入我们|人才招聘|联系我们",title):return title
    m=re.search(r"(?:岗位|职位)(?:名称)?\s*[:：]\s*([^,，。；;]{2,80})",text)
    return clean(m.group(1)) if m else ""


def crawl(entry:dict[str,Any])->tuple[list[dict[str,Any]],dict[str,Any]]:
    company=clean(entry.get("company"));start=clean(entry.get("start_url"));ctype=clean(entry.get("company_type"));max_pages=max(5,min(100,int(entry.get("max_pages") or 45)));max_depth=max(1,min(3,int(entry.get("max_depth") or 2)))
    host=(urlparse(start).hostname or "").lower();s=sess();q=deque([(start,0,100)]);seen=set();queued={start};jobs={};errors=[]
    while q and len(seen)<max_pages:
        # Prefer links whose visible text/path looks career-related, but still
        # permit other same-origin pages so CMS job slugs such as `/SoCdesign`
        # are discoverable.
        items=sorted(list(q),key=lambda x:-x[2]);q=deque();url,depth,_=items.pop(0);q.extend(items)
        if url in seen:continue
        seen.add(url)
        try:
            r=s.get(url,timeout=TIMEOUT,allow_redirects=True);r.raise_for_status();ctype_h=(r.headers.get("content-type") or "").lower()
            if "html" not in ctype_h and ctype_h:continue
            r.encoding=r.apparent_encoding or r.encoding;soup=BeautifulSoup(r.text,"html.parser");text=clean(soup.get_text(" ",strip=True))
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {clean(exc)[:100]}");continue
        if JOB_RE.search(text) and len(text)>=180:
            role=role_title(soup,text,company)
            if role:
                loc="";m=LOC_RE.search(text)
                if m:loc=clean(m.group(1) or m.group(2))
                batch="2027校园招聘" if "2027" in text or "27届" in text else ("实习" if "实习" in text[:1200] else "公开招聘")
                final=r.url
                job={"source":f"direct-official:site:{host}","source_label":f"{company}招聘官网","source_url":start,"updated_at":"","company":company,"department":"","role":role,"location":loc,"salary":"","batch":batch,"company_type":ctype,"industry":"","graduation":"2027届" if "2027" in text or "27届" in text else "","education":"","notice_url":final,"apply_url":final,"jd":text[:6000],"tags":["企业官网","自主抓取",batch],"observed_via":"bounded-employer-site-spider"}
                job["id"]=stable_id(company,role,loc,final);jobs[final]=job
        if depth>=max_depth:continue
        links=[]
        for a in soup.find_all("a",href=True):
            href,_=urldefrag(urljoin(r.url,a.get("href","")));u=urlparse(href);h=(u.hostname or "").lower()
            if u.scheme not in {"http","https"} or not h or h!=host or href in seen or href in queued or SKIP_EXT.search(href):continue
            label=clean(a.get_text(" ",strip=True));priority=20 if CAREER_RE.search(label+" "+href) else 1
            links.append((href,depth+1,priority));queued.add(href)
        links.sort(key=lambda x:-x[2]);q.extend(links[:max(0,max_pages-len(seen))]);time.sleep(.04)
    return list(jobs.values()),{"start_url":start,"pages_seen":len(seen),"unique_jobs":len(jobs),"errors":errors[:15]}


def identity(j):return (clean(j.get("company")).lower(),clean(j.get("role")).lower(),clean(j.get("location")).lower(),clean(j.get("apply_url") or j.get("notice_url")).lower())


def main():
    cfg=json.loads(REGISTRY.read_text(encoding="utf-8"));fresh=[];results=[]
    for entry in cfg.get("career_spiders",[]):
        try:
            rows,diag=crawl(entry);fresh.extend(rows);results.append({"company":entry.get("company"),"ok":True,"count":len(rows),"diagnostics":diag});print("official-site",entry.get("company"),len(rows),diag)
        except Exception as exc:
            results.append({"company":entry.get("company"),"ok":False,"count":0,"error":f"{type(exc).__name__}: {clean(exc)[:160]}"})
    payload=json.loads(JOBS_PATH.read_text(encoding="utf-8"));existing=payload.get("jobs",[])
    if existing and isinstance(existing[0],dict) and "c" in existing[0]:raise RuntimeError("official_site_job_spider.py must run before compact_feed.py")
    merged={identity(j):j for j in existing if isinstance(j,dict) and clean(j.get("company")) and clean(j.get("role"))}
    for j in fresh:merged[identity(j)]=j
    payload["schema_version"]=3;payload["generated_at"]=utc_now();payload["jobs"]=list(merged.values());JOBS_PATH.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {};group={"name":"employer-site-job-spider","label":"企业官网岗位页 · 有界自主抓取","url":"","ok":any(x.get('ok') for x in results),"count":len(fresh),"error":"","diagnostics":{"sites":results}}
    sources=[x for x in status.get("sources",[]) if not isinstance(x,dict) or x.get("name")!=group["name"]];sources.insert(0,group);status["sources"]=sources;status["catalog_count"]=len(payload["jobs"]);status["generated_at"]=utc_now();STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("official site spider total",len(fresh));return 0

if __name__=="__main__":raise SystemExit(main())
