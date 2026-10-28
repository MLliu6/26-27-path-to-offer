#!/usr/bin/env python3
"""Audit the delivered catalogue; optionally inspect a bounded official directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'sources/sector_sources_v16.json'
REPORT = ROOT / 'data/source_integrity_audit.json'
VERIFIED = ROOT / 'data/jobs_verified_v16.json'
FEEDS = ('jobs_cn.json', 'jobs_priority.json', 'jobs_supplemental.json', 'jobs_verified_v16.json')
CLOSED = re.compile(r'职位已关闭|职位已下线|该职位已结束|该岗位已关闭|招聘已结束|job (?:is )?no longer available|position (?:is |has been )?closed|no longer accepting applications', re.I)
CHALLENGE = re.compile(r'access denied|verify you are human|checking your browser|人机验证|访问验证|访问过于频繁|验证码', re.I)
GENERIC = re.compile(r'^(?:首页|招聘官网|加入我们|校园招聘|社会招聘|职位列表|人才招聘|careers|search jobs|job search)$', re.I)
ANNOUNCEMENT = re.compile(r'邀请函|双选会|宣讲会|招聘会|招聘简章|招聘公告|招聘(?:正式)?启动|校园招聘(?:正式)?启动', re.I)
PORTAL = re.compile(r'招聘(?:门户|官网|首页)|(?:门户|官网|首页).{0,8}招聘|^(?:20\d{2}[届年]?\s*)?(?:校园招聘|社会招聘|招聘职位|职位列表|岗位列表|加入我们)$', re.I)


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def stamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def safe_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in ('https', 'http') and bool(parsed.hostname) and not parsed.username and not parsed.password
    except (TypeError, ValueError):
        return False


def date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return None


def expired(value, now=None):
    parsed = date(value)
    if parsed and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)):
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return bool(parsed and parsed < (now or datetime.now(timezone.utc)))


def cohort(row):
    # A year in a publication timestamp is not a graduation requirement.
    text = ' '.join(str(row.get(k) or '') for k in ('g', 'graduation', 'b', 'batch', 'r', 'role'))
    if re.search(r'2027|27届', text):
        return '2027'
    if re.search(r'20(?:2[0-689]|[3-9]\d)\s*届|(?:202[0-689]|20[3-9]\d).*?(?:campus|graduate)', text, re.I):
        return 'other'
    return 'unknown'


def record_issues(row):
    title = clean(row.get('r') or row.get('role'))
    url = row.get('u') or row.get('apply_url') or row.get('n') or ''
    try:
        parsed = urlparse(url)
    except ValueError:
        parsed = urlparse('')
    host = (parsed.hostname or '').lower()
    share = (host == 'service.weibo.com' and '/share' in parsed.path or
             host in ('sns.qzone.qq.com', 'connect.qq.com') and re.search(r'share|qzshare', parsed.path, re.I))
    kind = row.get('record_kind', '')
    return dict(portal=kind == 'portal' or bool(GENERIC.fullmatch(title) or PORTAL.search(title)),
                announcement=kind in ('announcement', 'campaign') or bool(ANNOUNCEMENT.search(title)),
                unsafe_share_url=bool(share))


def flatten_jsonld(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten_jsonld(item)
    elif isinstance(value, dict):
        kind = value.get('@type', [])
        if kind == 'JobPosting' or isinstance(kind, list) and 'JobPosting' in kind:
            yield value
        for key in ('@graph', 'mainEntity', 'itemListElement', 'item'):
            if key in value:
                yield from flatten_jsonld(value[key])


def make_job(entry, title, description, url, checked, **extra):
    title = clean(title)
    if not 3 <= len(title) <= 200 or GENERIC.fullmatch(title) or not safe_url(url):
        return None
    cohort = entry.get('cohort', '') if entry.get('entry_kind') != 'portal' or entry.get('role_sections') else ''
    return dict(i=hashlib.sha256(f"{entry['id']}|{title}|{url}".encode()).hexdigest()[:20],
                c=entry['company'], r=title, l=entry.get('location', ''),
                d=clean(description)[:220], jd_full=clean(description)[:8000], u=url, n=entry['url'],
                s='direct-official:v16:' + entry['id'], x=entry['company'] + ' · 官网核验', q=7,
                y=entry['company_type'], h=entry['industry'], e=entry.get('education', ''),
                b='2027校园招聘' if cohort == '2027届' else ('2027招聘项目' if '2027' in cohort else '公开招聘·届别待确认'),
                g=cohort if cohort.endswith('届') else '',
                observed_at=checked, observed_via='official-public-page', source_url=entry['url'],
                record_kind='position', verification='detail-observed', status='observed',
                deadline=entry.get('deadline', ''), **extra)


def extract_jobs(entry, html, final_url, checked):
    soup = BeautifulSoup(html, 'html.parser')
    body = clean(soup.get_text(' ', strip=True))
    if CLOSED.search(body):
        return [], 'closed'
    if expired(entry.get('deadline')):
        return [], 'closed'
    rows = []
    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            values = list(flatten_jsonld(json.loads(tag.string or tag.get_text())))
        except (ValueError, TypeError):
            continue
        for job in values:
            if expired(job.get('validThrough')):
                continue
            description = clean(BeautifulSoup(str(job.get('description', '')), 'html.parser').get_text(' ', strip=True))
            url = job.get('url') or final_url
            if not safe_url(url) or urlparse(url).hostname != urlparse(final_url).hostname:
                continue
            row = make_job(entry, job.get('title'), description, url, checked)
            if row and description:
                row['deadline'] = job.get('validThrough') or row['deadline']
                row['t'] = job.get('datePosted', '')
                if re.search(r'2027|27届', row['r']):
                    row['b'] = '2027招聘项目'
                if re.search(r'2027\s*届|27届|graduat(?:e|ing)\s+in\s+2027', row['r'] + ' ' + description, re.I):
                    row['g'] = '2027届'
                rows.append(row)
    # Reviewed public announcements sometimes describe several real job families.
    # A registered portal never becomes a vacancy without a title and requirements.
    sections = entry.get('role_sections', [])
    application = entry.get('application_url', '')
    if sections and safe_url(application) and urlparse(application).hostname in body:
        for title in sections:
            marker = re.search(r'[\[【]\s*' + re.escape(title) + r'\s*[\]】]', body)
            if not marker:
                continue
            tail = body[marker.end():]
            tail = re.split(r'[\[【][^\]】]{2,30}[\]】]|招聘流程', tail, maxsplit=1)[0]
            if len(tail) > 60 and re.search(r'职责|要求|专业', tail):
                row = make_job(entry, title, tail, application, checked)
                if row:
                    rows.append(row)
    if not rows and entry.get('entry_kind') == 'position':
        expected = entry.get('expected_title', '')
        headings = [clean(h.get_text(' ', strip=True)) for h in soup.select('h1')]
        title = next((h for h in headings if expected and expected.lower() in h.lower()), '')
        if title and len(body) > 400 and re.search(r'qualification|responsibilit|graduate programme|任职|职责', body, re.I):
            row = make_job(entry, title, body, final_url, checked, z=entry.get('position_id', ''))
            if row:
                rows.append(row)
    unique = {r['i']: r for r in rows}
    return list(unique.values()), 'positions_observed' if unique else 'portal_only'


def check_entry(entry):
    checked = stamp()
    result = {**entry, 'checked_at': checked, 'reachable': False, 'status': 'unavailable', 'http_status': None, 'observed_positions': 0}
    try:
        response = requests.get(entry['url'], timeout=(6, 14), headers={'User-Agent': 'PathToOfferBot/1.6 (+https://github.com/MLliu6/26-27-path-to-offer)'})
        result.update(http_status=response.status_code, final_url=response.url)
        if response.status_code in (401, 403, 412, 429):
            result['status'] = 'access_restricted'
            return result, []
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text[:3_000_000]
        soup = BeautifulSoup(html, 'html.parser')
        visible = clean(soup.get_text(' ', strip=True))
        result['title'] = clean(soup.title.get_text())[:180] if soup.title else ''
        if re.search(r'/(?:404|error)(?:[/?.]|$)', response.url, re.I) or re.search(r'404|page not found|页面不存在|页面未找到', result['title'], re.I):
            result['status'] = 'not_found'
            return result, []
        if len(visible) < 1500 and CHALLENGE.search(visible):
            result['status'] = 'access_restricted'
            return result, []
        allowed = {urlparse(entry['url']).hostname, urlparse(entry['evidence_url']).hostname, *entry.get('allowed_hosts', [])}
        if urlparse(response.url).hostname not in allowed:
            result['status'] = 'redirect_review'
            return result, []
        result['reachable'] = True
        rows, status = extract_jobs(entry, html, response.url, checked)
        if entry.get('moka'):
            from scripts.moka_public_harvester import call_page, normalize_job, public_session, PAGE_SIZE
            spec = dict(entry['moka'], company=entry['company'], official_url=entry['url'])
            session = public_session()
            page_limit = min(12, max(1, int(entry.get('max_pages', 2))))
            for page in range(page_limit):
                public_rows = call_page(session, spec, page * PAGE_SIZE)
                for public_row in public_rows:
                    job = normalize_job(spec, public_row)
                    if not job:
                        continue
                    row = make_job(entry, job['role'], job.get('jd', ''), job['apply_url'], checked, z=job.get('position_id', ''))
                    if row:
                        row.update(l=job.get('location', ''), g=job.get('graduation', ''),
                                   b=job.get('batch', '') or row['b'], t=job.get('updated_at', ''),
                                   observed_via='moka-public-website-api')
                        rows.append(row)
                if len(public_rows) < PAGE_SIZE:
                    break
            if rows:
                status = 'positions_observed'
            result['coverage'] = f'up-to-{page_limit}-public-pages'
            result['pages_checked'] = page + 1
        result.update(status=status, observed_positions=len(rows), cohort_signal_2027=bool(re.search(r'2027|27届', visible)))
        if not rows and len(visible) < 120:
            result['status'] = 'browser_required'
        return result, rows
    except (requests.RequestException, RuntimeError, ValueError, ImportError) as exc:
        result['status'] = 'collector_unavailable' if isinstance(exc, ImportError) else 'unavailable'
        result['error'] = type(exc).__name__
        return result, []


def audit(feeds, portals, generated=None):
    rows = []
    seen = set()
    duplicates = 0
    for feed in feeds:
        for row in feed.get('jobs', []):
            company = row.get('c') or row.get('company') or ''
            role = row.get('r') or row.get('role') or ''
            url = row.get('u') or row.get('apply_url') or row.get('n') or ''
            key = (company.casefold(), role.casefold(), str(row.get('l') or row.get('location') or '').casefold(), url)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(row)
    now = date(generated) or datetime.now(timezone.utc)
    years = Counter(cohort(r) for r in rows)
    observations = [date(r.get('observed_at')) for r in rows]
    closed = [r for r in rows if r.get('status') == 'closed' or expired(r.get('deadline'), now)]
    unsupported = [r for r in rows if not safe_url(r.get('u') or r.get('apply_url') or r.get('n') or '')]
    quality = {key: [r for r in rows if record_issues(r)[key]] for key in ('portal', 'announcement', 'unsafe_share_url')}
    summary = dict(catalogue_rows=len(rows), duplicated_rows=duplicates, explicit_2027=years['2027'], other_cohort=years['other'], cohort_unknown=years['unknown'],
                   observation_unknown=sum(x is None for x in observations), observed_within_30_days=sum(x is not None and 0 <= (now-x).days <= 30 for x in observations),
                   observed_over_30_days=sum(x is not None and (now-x).days > 30 for x in observations), closed_or_expired=len(closed), invalid_application_urls=len(unsupported),
                   registered_portals=len(portals), reachable_portals=sum(p.get('reachable') is True for p in portals),
                   portals_with_positions=sum(p.get('observed_positions', 0) > 0 for p in portals),
                   portal_records=len(quality['portal']), announcement_records=len(quality['announcement']), unsafe_share_urls=len(quality['unsafe_share_url']),
                   rows_with_extended_jd=sum(len(r.get('jd_full', '')) > len(r.get('d', '')) for r in rows))
    by_company = Counter(str(r.get('c') or r.get('company') or '').casefold() for r in rows)
    groups = {}
    for field in ('industry', 'company_type'):
        groups['by_' + field] = [dict(name=name, registered_portals=len(items), reachable_portals=sum(x.get('reachable') is True for x in items),
                                    catalogue_rows=sum(by_company[name] for name in {x['company'].casefold() for x in items}))
                                for name in sorted({p[field] for p in portals})
                                for items in [[p for p in portals if p[field] == name]]]
    return dict(version=1, generated_at=generated or stamp(), cohort_year=2027, summary=summary,
                feed_snapshots=[dict(file=f.get('_file'), generated_at=f.get('generated_at'), rows=len(f.get('jobs', []))) for f in feeds],
                portal_checks=portals, **groups,
                issues=[dict(code='cohort_unknown', count=years['unknown']), dict(code='observation_unknown', count=summary['observation_unknown']),
                        dict(code='closed_or_expired', count=len(closed)), dict(code='invalid_application_url', count=len(unsupported)),
                        *[dict(code=key, count=len(items), samples=[dict(company=r.get('c') or r.get('company'), role=r.get('r') or r.get('role'), url=r.get('u') or r.get('apply_url') or r.get('n')) for r in items[:5]]) for key, items in quality.items()]])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-links', action='store_true')
    args = parser.parse_args()
    entries = load(REGISTRY)['sources']
    previous = {p['id']: p for p in load(REPORT).get('portal_checks', [])}
    portals = [{**previous.get(entry['id'], {}), **entry} for entry in entries]
    if args.check_links:
        with ThreadPoolExecutor(max_workers=6) as pool:
            checked = list(pool.map(check_entry, entries))
        portals = [result for result, _ in checked]
        current = {row['i']: row for _, rows in checked for row in rows}
        states = {p['id']: p['status'] for p in portals}
        # Failure keeps the prior evidence date. Explicit closure removes a job
        # from this public discovery feed; personal applications live elsewhere.
        for row in load(VERIFIED).get('jobs', []):
            source = row.get('s', '').removeprefix('direct-official:v16:')
            if row['i'] not in current and states.get(source) != 'closed' and not expired(row.get('deadline')):
                current[row['i']] = {**row, 'verification': 'previous-observation', 'status': 'needs-review'}
        VERIFIED.write_text(json.dumps(dict(schema_version=4, generated_at=stamp(), jobs=list(current.values())), ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    feeds = [{**load(ROOT / 'data' / name), '_file': name} for name in FEEDS]
    report = audit(feeds, portals)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
