#!/usr/bin/env python3
"""Independent, bounded employer feed. Never touches account or main feed files."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'sources/workspace_sources_v15.json'
FEED = ROOT / 'data/jobs_supplemental.json'
STATUS = ROOT / 'data/supplemental_source_status.json'
TITLE = re.compile(r'工程师|研究员|开发|架构师|设计师|算法|Engineer|Developer|Scientist', re.I)
REJECT = re.compile(r'招聘启动|招聘正式启动|加入我们|隐私|登录|关于我们|招聘流程|岗位职责|任职要求|技能要求|工作职责|了解更多|招聘简章')

def load(path):
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Invalid JSON object: {path}')
    return value

def stamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def select(entries, now=None, full=False):
    ordered = sorted(entries, key=lambda e: e['id'])
    if full:
        return ordered
    size = 6
    shards = max(1, (len(ordered) + size - 1) // size)
    idx = int((time.time() if now is None else now) // 7200) % shards
    return ordered[idx * size:(idx + 1) * size]

def valid_job(job):
    title = str(job.get('role') or '').strip()
    jd = str(job.get('jd') or '').strip()
    return bool(2 <= len(title) <= 100 and TITLE.search(title) and not REJECT.search(title)
                and len(jd) > len(title) + 20 and job.get('apply_url', '').startswith(('https://', 'http://')))

def merge_source(previous, fresh, source_id, ok):
    old = [j for j in previous if j.get('s') == source_id]
    other = [j for j in previous if j.get('s') != source_id]
    # Bounded samples cannot establish a vacancy deletion. Keep observation dates.
    if not ok:
        return previous, len(old)
    merged = {j['i']: j for j in old}
    merged.update({j['i']: j for j in fresh})
    return other + list(merged.values()), len(merged)

def install_extra(h, base):
    base.install()
    original = h.response_handler
    def response(entry, page, capture, res):
        host = (urlparse(res.url).hostname or '').lower()
        if entry.get('family') == 'feishu' and host in entry.get('api_hosts', []) and base.FEISHU_JOB_POSTS_PATH_RE.search(urlparse(res.url).path):
            try:
                payload = res.json()
                for row in base.feishu_job_rows(payload):
                    capture.add(base.normalize_feishu_job(entry, row, res.url, page.url))
                capture.json_responses += 1
                base.mark_feishu_job_posts(capture)
                return
            except Exception as exc:
                capture.errors.append(type(exc).__name__)
                return
        original(entry, page, capture, res)
    h.response_handler = response
    original_dom = h.collect_dom
    def dom(entry, page, capture):
        if entry.get('family') != 'static':
            return original_dom(entry, page, capture)
        blocks = page.eval_on_selector_all('tr,h2,h3,h4,h5', '''els => els.map(el => {
          const cell=el.matches('tr')?el.querySelector('td'):el;
          const title=(cell?.innerText||'').trim();
          let n=el, block=el.innerText||'';
          if(!el.matches('tr'))for(let i=0;i<4&&n.parentElement;i++){
            n=n.parentElement;const t=n.innerText||'';
            if(t.length>title.length+80&&t.length<7500){block=t;break;}
          }
          return {title,block};
        }).filter(x=>x.title.length>1&&x.title.length<101)''')
        for item in blocks:
            title = h.clean(item['title'])
            if not TITLE.search(title) or REJECT.search(title):
                continue
            job = h.normalize_dom_job(entry, page.url, title, item['block'])
            if job and valid_job(job):
                job['role'] = title
                job['observed_via'] = 'employer-public-role-block'
                capture.add(job)
        return len(capture.jobs)
    h.collect_dom = dom

def encode(job, entry, checked):
    role = job['role']
    pid = str(job.get('position_id') or '')
    sid = 'direct-official:v15:' + entry['id']
    url = job['apply_url']
    key = hashlib.sha256(f"{entry['id']}|{pid or role}|{job.get('location','')}|{url}".encode()).hexdigest()[:20]
    return dict(i=key, c=entry['company'], r=role, l=job.get('location',''), d=job.get('jd','')[:5000],
                u=url, n=job.get('notice_url') or url, s=sid, x=entry['company']+'招聘官网 · 扩展采集',
                q=7, z=pid, b=job.get('batch') or '公开招聘·届别待确认', g=job.get('graduation') or '',
                t=job.get('updated_at') or '', observed_at=checked,
                observed_via=job.get('observed_via') or 'browser-public-ui', verification='employer-observed')

def main():
    from playwright.sync_api import sync_playwright
    from scripts import priority_browser_harvester as h, priority_browser_runner as base
    entries = [e for e in load(REGISTRY).get('sources',[]) if e.get('enabled',True)]
    chosen = select(entries, full=os.getenv('PTO_V15_FULL') == '1')
    jobs = load(FEED).get('jobs',[])
    statuses = {s['id']: s for s in load(STATUS).get('sources',[])}
    for entry in entries:
        statuses.setdefault(entry['id'],dict(id=entry['id'],company=entry['company'],official_url=entry['official_url'],ok=False,count=0,checked_at=None,status='pending'))
    install_extra(h, base)
    h.NAV_TIMEOUT = 12000
    started = time.monotonic()
    fresh_count = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=h.browser_path(), args=['--no-sandbox','--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width':1440,'height':1000}, locale='zh-CN')
        for entry in chosen:
            if time.monotonic()-started > 720:
                break
            checked = stamp()
            old = statuses.get(entry['id'],{})
            sid = 'direct-official:v15:' + entry['id']
            try:
                rows, diag = h.collect_one(context, entry)
                accepted = [encode(j, entry, checked) for j in rows if valid_job(j)]
                ok = bool(accepted)
                jobs, count = merge_source(jobs, accepted, sid, ok)
                fresh_count += len(accepted)
                status = dict(id=entry['id'],company=entry['company'],official_url=entry['official_url'],
                              ok=ok,count=count,fresh_count=len(accepted),checked_at=checked,
                              last_success_at=checked if ok else old.get('last_success_at'),
                              preserved_previous=not ok and count>0, complete=False,
                              coverage='bounded-public-sample',pages_advanced=diag.get('pages_advanced',0),
                              error='' if ok else 'No valid concrete job observed; last known rows retained')
            except Exception as exc:
                _, count = merge_source(jobs, [], sid, False)
                status = dict(id=entry['id'],company=entry['company'],official_url=entry['official_url'],
                              ok=False,count=count,fresh_count=0,checked_at=checked,
                              last_success_at=old.get('last_success_at'),preserved_previous=count>0,
                              complete=False,error=f'{type(exc).__name__}: {str(exc)[:150]}')
            statuses[entry['id']] = status
            print(json.dumps(status,ensure_ascii=False),flush=True)
        browser.close()
    now = stamp()
    FEED.write_text(json.dumps(dict(schema_version=4,generated_at=now,jobs=jobs),ensure_ascii=False,separators=(',',':'))+'\n')
    STATUS.write_text(json.dumps(dict(version=1,generated_at=now,registered_sources=len(entries),selected_sources=len(chosen),
                                      fresh_count=fresh_count,catalog_count=len(jobs),sources=list(statuses.values())),ensure_ascii=False,indent=2)+'\n')
    print(f'Official supplemental rows: {len(jobs)}; fresh observations: {fresh_count}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
