#!/usr/bin/env python3
"""Discover live 2027 recruiting campaigns from monitored employer portals.

Each run visits the official portal registry and extracts *links visibly published
by that portal* whose text identifies a 2027/new-grad/intern recruiting campaign.
It does not invent job rows from a reachable homepage. A row is emitted only when
an official portal exposes a concrete recruiting link/title.

This is deliberately generic: when a bank, SOE or startup publishes a new 2027
campaign on a monitored site, Path to Offer can discover it on the next scheduled
refresh without waiting for a hand-written adapter.
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

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_official_sources.json"
UA = "PathToOfferBot/0.9 (+https://github.com/MLliu6/26-27-path-to-offer)"
TIMEOUT = 14
CAMPAIGN = re.compile(r"(?:2027|27届).{0,45}(?:校园招聘|校招|秋招|招聘|毕业生|实习)|(?:校园招聘|校招|秋招|招聘|毕业生|实习).{0,45}(?:2027|27届)", re.I)
TECH = re.compile(r"人工智能|AI|大模型|算法|软件|计算机|信息科技|金融科技|芯片|编译|CUDA|GPU|NPU|机器人|自动驾驶|研发|开发|数据|网络安全", re.I)


def session() -> requests.Session:
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.6"});return s


def canonical_text(a) -> str:
    text=clean(a.get_text(" ",strip=True))
    if text and len(text)>=4:return text[:180]
    title=clean(a.get("title"));return title[:180]


def fetch_entry(entry: dict[str,Any]) -> tuple[dict[str,Any],list[dict[str,Any]]]:
    company=clean(entry.get("company"));url=clean(entry.get("url"));category=clean(entry.get("category"))
    diag={"company":company,"url":url,"ok":False,"links":0,"error":""};out=[]
    if not company or not url:return diag,out
    try:
        r=session().get(url,timeout=TIMEOUT,allow_redirects=True);r.raise_for_status();r.encoding=r.apparent_encoding or r.encoding
        soup=BeautifulSoup(r.text,"html.parser");seen=set()
        for a in soup.find_all("a",href=True):
            title=canonical_text(a)
            if not title or not CAMPAIGN.search(title):continue
            href=urljoin(r.url,a.get("href","")).split("#",1)[0]
            u=urlparse(href)
            if u.scheme not in {"http","https"} or not u.hostname or href in seen:continue
            seen.add(href)
            batch="2027实习/人才储备" if "实习" in title else ("2027秋招" if "秋招" in title else "2027校园招聘")
            job={
                "source":"priority-official:campaign-discovery",
                "source_label":f"{company}官方招聘·自动发现",
                "source_url":url,"updated_at":"","company":company,"department":"","role":title,
                "location":"","salary":"","batch":batch,"company_type":category,"industry":"",
                "graduation":"2027届","education":"","notice_url":href,"apply_url":href,
                "jd":title,"tags":["官方招聘","2027",batch]+(["技术相关"] if TECH.search(title) else []),
                "observed_via":"employer-visible-campaign-link"
            }
            job["id"]=stable_id(company,title,"",href);out.append(job)
        diag.update(ok=True,links=len(out),final_url=r.url,status=r.status_code)
    except Exception as exc:
        diag["error"]=f"{type(exc).__name__}: {clean(exc)[:180]}"
    return diag,out


def identity(job:dict[str,Any])->tuple[str,str,str,str]:
    return (clean(job.get("company")).lower(),clean(job.get("role")).lower(),clean(job.get("location")).lower(),clean(job.get("apply_url") or job.get("notice_url")).lower())


def main()->int:
    cfg=json.loads(REGISTRY.read_text(encoding="utf-8"));payload=json.loads(JOBS_PATH.read_text(encoding="utf-8"));existing=payload.get("jobs",[])
    if existing and isinstance(existing[0],dict) and "c" in existing[0]:raise RuntimeError("official_campaign_discovery.py must run before compact_feed.py")
    diagnostics=[];fresh=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs=[pool.submit(fetch_entry,e) for e in cfg.get("watch",[]) if isinstance(e,dict)]
        for fut in as_completed(futs):
            d,rows=fut.result();diagnostics.append(d);fresh.extend(rows)
    merged={}
    for j in existing:
        if isinstance(j,dict) and clean(j.get("company")) and clean(j.get("role")):merged[identity(j)]=j
    for j in fresh:merged[identity(j)]=j
    out=dict(payload);out["schema_version"]=3;out["generated_at"]=utc_now();out["jobs"]=list(merged.values())
    JOBS_PATH.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    status=json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    group={"name":"official-campaign-discovery","label":"企业官网 2027 招聘活动自动发现","url":"","ok":any(x.get("ok") for x in diagnostics),"count":len(fresh),"error":"",
           "diagnostics":{"portals":len(diagnostics),"portals_ok":sum(1 for x in diagnostics if x.get("ok")),"portals_with_2027_links":sum(1 for x in diagnostics if x.get("links",0)>0),"top":sorted(diagnostics,key=lambda x:x.get("links",0),reverse=True)[:30]}}
    sources=[s for s in status.get("sources",[]) if not isinstance(s,dict) or s.get("name")!=group["name"]];sources.insert(0,group);status["sources"]=sources;status["catalog_count"]=len(out["jobs"]);status["generated_at"]=utc_now()
    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"official campaign discovery: portals={len(diagnostics)} ok={group['diagnostics']['portals_ok']} with_2027={group['diagnostics']['portals_with_2027_links']} rows={len(fresh)}")
    for x in group["diagnostics"]["top"][:12]:
        if x.get("links"):print(" campaign",x.get("company"),x.get("links"),x.get("url"))
    return 0


if __name__=="__main__":raise SystemExit(main())
