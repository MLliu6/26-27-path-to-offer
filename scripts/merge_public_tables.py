#!/usr/bin/env python3
"""Merge additional public recruiting tables into Path to Offer's job feed.

This adapter is intentionally conservative:
- only URLs explicitly listed in sources/public_pages.json;
- only public unauthenticated HTML returned by a normal GET;
- robots.txt is checked by aggregate_jobs.fetch_public;
- no login, CAPTCHA, anti-bot, hidden endpoint, or pagination bypass;
- failure of one source never erases previously collected jobs.

It exists to broaden discovery beyond a single aggregator while keeping the source
boundary auditable and replaceable.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scripts.aggregate_jobs import (
    DATA,
    JOBS_PATH,
    STATUS_PATH,
    SourceResult,
    clean,
    dedupe,
    fetch_public,
    map_headers,
    stable_id,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "sources" / "public_pages.json"


def link_from(cell, base: str) -> str:
    if cell is None:
        return ""
    link = cell.find("a", href=True)
    if not link:
        return ""
    href = clean(link.get("href"))
    if not href or href.startswith(("#", "javascript:")):
        return ""
    return urljoin(base, href)


def parse_table_source(html: str, *, name: str, label: str, url: str) -> list[dict[str, Any]]:
    """Parse tables using the same canonical field aliases as the main crawler."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = table.find_all("th")
        if not header_cells:
            header_cells = rows[0].find_all(["th", "td"])
        headers = [clean(c.get_text(" ", strip=True)) for c in header_cells]
        mapping = map_headers(headers)
        if "company" not in mapping or "role" not in mapping:
            continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            def value(key: str) -> str:
                idx = mapping.get(key)
                return clean(cells[idx].get_text(" ", strip=True)) if idx is not None and idx < len(cells) else ""

            company, role = value("company"), value("role")
            if not company or not role:
                continue
            notice_idx, apply_idx = mapping.get("notice_url"), mapping.get("apply_url")
            notice_url = link_from(cells[notice_idx] if notice_idx is not None and notice_idx < len(cells) else None, url)
            apply_url = link_from(cells[apply_idx] if apply_idx is not None and apply_idx < len(cells) else None, url)
            job = {
                "source": name,
                "source_label": label,
                "source_url": url,
                "updated_at": value("updated_at"),
                "company": company,
                "department": "",
                "role": role,
                "location": value("location"),
                "salary": "",
                "batch": value("batch"),
                "company_type": value("company_type"),
                "industry": value("industry"),
                "graduation": value("graduation"),
                "education": value("education"),
                "notice_url": notice_url,
                "apply_url": apply_url,
                "jd": role,
                "tags": [],
                "observed_via": "public-html-table",
            }
            job["id"] = stable_id(name, company, role, job["location"], apply_url or notice_url)
            jobs.append(job)
    return jobs


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def main() -> int:
    if not CONFIG.exists():
        print("no public page source config")
        return 0
    config = load_json(CONFIG, {})
    feed = load_json(JOBS_PATH, {"schema_version": 1, "generated_at": None, "jobs": []})
    status = load_json(STATUS_PATH, {"generated_at": None, "sources": []})
    existing = feed.get("jobs", []) if isinstance(feed, dict) else []
    all_jobs = list(existing) if isinstance(existing, list) else []
    session = requests.Session()
    new_statuses: list[SourceResult] = []

    for item in config.get("html_tables", []):
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        name = clean(item.get("name"))
        label = clean(item.get("label")) or name
        url = clean(item.get("url"))
        sr = SourceResult(name=name, label=label, url=url, ok=False)
        try:
            response = fetch_public(session, url)
            jobs = parse_table_source(response.text, name=name, label=label, url=url)
            if not jobs:
                raise RuntimeError("public page returned no compatible recruiting table")
            sr.ok = True
            sr.count = len(jobs)
            all_jobs.extend(jobs)
        except Exception as exc:
            sr.error = clean(exc)[:260]
        new_statuses.append(sr)

    merged = dedupe(all_jobs)
    merged.sort(key=lambda j: (clean(j.get("updated_at")), clean(j.get("company")), clean(j.get("role"))), reverse=True)
    now = utc_now()
    DATA.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps({"schema_version": 1, "generated_at": now, "jobs": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    old_sources = [s for s in status.get("sources", []) if isinstance(s, dict)]
    replace_names = {s.name for s in new_statuses}
    old_sources = [s for s in old_sources if s.get("name") not in replace_names]
    STATUS_PATH.write_text(json.dumps({"generated_at": now, "sources": old_sources + [asdict(s) for s in new_statuses]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("public table merge:", ", ".join(f"{s.name}:{'ok' if s.ok else 'fail'}:{s.count}" for s in new_statuses), f"total={len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
