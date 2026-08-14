#!/usr/bin/env python3
"""Browser-context replay for OfferJack's public paginated job response.

The APIRequestContext transport can behave differently from the page's own fetch stack on
some sites. This adapter keeps the request inside the already-loaded public page: it first
observes the job response that OfferJack itself requests, then calls `window.fetch` on the
same origin while changing only the observed page/page-size parameters. No authentication,
CAPTCHA bypass, anti-bot evasion, hidden credential, or private endpoint discovery is used.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Response, sync_playwright

from scripts.aggregate_jobs import JOBS_PATH, clean, dedupe, utc_now
from scripts.offerjack_public_api import (
    MAX_PAGES,
    MAX_RECORDS,
    TARGET_PAGE_SIZE,
    URL,
    Template,
    chrome_path,
    is_offer_payload,
    load_json,
    map_record,
    mutate_paging,
    page_metadata,
    write_status,
)


def fetch_in_page(page, *, url: str, method: str, body: str | None, content_type: str | None) -> dict[str, Any]:
    return page.evaluate(
        """async ({url, method, body, contentType}) => {
          const headers = {Accept: 'application/json, text/plain, */*'};
          if (contentType && body != null) headers['Content-Type'] = contentType;
          const response = await fetch(url, {
            method,
            headers,
            body: body == null ? undefined : body,
            credentials: 'same-origin',
            cache: 'no-store'
          });
          const text = await response.text();
          let payload = null;
          try { payload = JSON.parse(text); } catch (_) {}
          return {status: response.status, payload, preview: text.slice(0, 240)};
        }""",
        {"url": url, "method": method, "body": body, "contentType": content_type},
    )


def content_type_for(template: Template) -> str | None:
    value = template.headers.get("content-type") or template.headers.get("Content-Type")
    if value:
        return value
    if template.post_data:
        try:
            json.loads(template.post_data)
            return "application/json"
        except Exception:
            return "application/x-www-form-urlencoded"
    return None


def sanitize_links(job: dict[str, Any]) -> dict[str, Any]:
    for key in ("notice_url", "apply_url"):
        value = clean(job.get(key))
        try:
            host = (urlparse(value).hostname or "").lower()
        except Exception:
            host = ""
        if not value.startswith(("http://", "https://")) or host in {"invalid.uri", "example.com", "localhost"}:
            job[key] = ""
    return job


def main() -> int:
    executable = chrome_path()
    if not executable:
        print("OfferJack browser replay skipped: Chrome not found")
        return 0

    template: Template | None = None
    diagnostics: dict[str, Any] = {"adapter": "same-origin-browser-replay", "renderer": Path(executable).name}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        def on_response(response: Response) -> None:
            nonlocal template
            if template is not None:
                return
            if response.request.resource_type not in {"xhr", "fetch"} or "json" not in response.headers.get("content-type", "").lower():
                return
            try:
                payload = response.json()
            except Exception:
                return
            if not is_offer_payload(payload):
                return
            req = response.request
            template = Template(
                method=req.method.upper(),
                url=req.url,
                post_data=req.post_data,
                headers={"content-type": req.headers.get("content-type", "")},
                first_payload=payload,
            )

        page.on("response", on_response)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(8_000)
            if template is None:
                write_status(ok=False, count=0, error="same-origin replay could not observe the public job response", diagnostics=diagnostics)
                browser.close(); return 0

            meta = page_metadata(template.first_payload)
            diagnostics.update({
                "observed_path": urlparse(template.url).path,
                "method": template.method,
                "initial_total": meta["total"],
                "initial_size": meta["size"],
                "initial_pages": meta["pages"],
            })
            content_type = content_type_for(template)
            all_jobs = [sanitize_links(j) for rec in (template.first_payload.get("data", {}).get("records") or []) if isinstance(rec, dict) for j in [map_record(rec)] if j]

            effective_size = meta["size"] or 20
            if TARGET_PAGE_SIZE > effective_size:
                try:
                    probe_url, probe_body, _ = mutate_paging(template, 1, TARGET_PAGE_SIZE)
                    probe = fetch_in_page(page, url=probe_url, method=template.method, body=probe_body, content_type=content_type)
                    diagnostics["page_size_probe_status"] = probe["status"]
                    if probe["status"] == 200 and is_offer_payload(probe.get("payload")):
                        candidate_meta = page_metadata(probe["payload"])
                        if candidate_meta["size"] >= effective_size:
                            meta = candidate_meta
                            effective_size = candidate_meta["size"] or effective_size
                            all_jobs = [sanitize_links(j) for rec in (probe["payload"].get("data", {}).get("records") or []) if isinstance(rec, dict) for j in [map_record(rec)] if j]
                    else:
                        diagnostics["page_size_probe_preview"] = clean(probe.get("preview"))[:180]
                except Exception as exc:
                    diagnostics["page_size_probe_error"] = f"{type(exc).__name__}: {clean(exc)[:180]}"

            diagnostics["effective_size"] = effective_size
            diagnostics["effective_pages"] = meta["pages"]
            pages_to_fetch = min(meta["pages"] or 1, MAX_PAGES)
            diagnostics["page_cap"] = MAX_PAGES

            last_page = 1
            for page_no in range(2, pages_to_fetch + 1):
                if len(all_jobs) >= MAX_RECORDS:
                    diagnostics["record_cap_reached"] = True
                    break
                try:
                    replay_url, replay_body, _ = mutate_paging(template, page_no, effective_size)
                    replay = fetch_in_page(page, url=replay_url, method=template.method, body=replay_body, content_type=content_type)
                    if replay["status"] in {401, 403, 429}:
                        diagnostics["stopped_status"] = replay["status"]
                        break
                    payload = replay.get("payload")
                    if replay["status"] != 200 or not is_offer_payload(payload):
                        diagnostics["stopped_page"] = page_no
                        diagnostics["stopped_status"] = replay["status"]
                        diagnostics["stopped_preview"] = clean(replay.get("preview"))[:220]
                        if isinstance(payload, dict):
                            diagnostics["stopped_payload_keys"] = list(payload.keys())[:20]
                            diagnostics["stopped_msg"] = clean(payload.get("msg"))[:180]
                        break
                    records = payload.get("data", {}).get("records") or []
                    if not records:
                        break
                    all_jobs.extend(sanitize_links(j) for rec in records if isinstance(rec, dict) for j in [map_record(rec)] if j)
                    last_page = page_no
                    # Serial and deliberately modest; no concurrent hammering.
                    time.sleep(0.05)
                    if page_no % 30 == 0:
                        time.sleep(0.35)
                except Exception as exc:
                    diagnostics["stopped_page"] = page_no
                    diagnostics["stopped_error"] = f"{type(exc).__name__}: {clean(exc)[:180]}"
                    break

            diagnostics["last_page"] = last_page
            browser.close()
        except Exception as exc:
            try: browser.close()
            except Exception: pass
            write_status(ok=False, count=0, error=f"same-origin browser replay failed: {type(exc).__name__}", diagnostics={**diagnostics, "detail": clean(exc)[:220]})
            return 0

    all_jobs = dedupe(all_jobs)[:MAX_RECORDS]
    diagnostics["records_collected"] = len(all_jobs)
    diagnostics["coverage_ratio"] = round(len(all_jobs) / meta["total"], 4) if meta["total"] else None

    feed = load_json(JOBS_PATH, {"schema_version": 1, "generated_at": None, "jobs": []})
    non_offerjack = [j for j in feed.get("jobs", []) if j.get("source") != "offerjack"]
    if all_jobs:
        JOBS_PATH.write_text(json.dumps({"schema_version": 1, "generated_at": utc_now(), "jobs": dedupe(non_offerjack + all_jobs)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_status(ok=True, count=len(all_jobs), diagnostics=diagnostics)
        print(f"OfferJack same-origin replay: {len(all_jobs)}/{meta['total'] or '?'} records")
    else:
        write_status(ok=False, count=0, error="same-origin replay returned no normalized jobs", diagnostics=diagnostics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
