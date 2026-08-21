#!/usr/bin/env python3
"""Production entrypoint for reviewed browser ATS adapters.

The base runner installs reviewed schema adapters. This final runtime layer:

1. keeps the strict IGuopin tenant provenance rule;
2. overlays a separately reviewed source cluster for emerging China compute /
   GPU / AI-infrastructure employers without making the already-large base
   registry harder to audit;
3. recognizes Feishu Hire job-list responses reached through an employer custom
   recruiting domain; and
4. adds an opt-in rendered-role-block fallback for smaller employers that put
   several real jobs directly on one careers page instead of giving every role
   a separate link/API row.

No login, CAPTCHA handling, private-cookie replay, proxy rotation or access-
control bypass is introduced here.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from scripts import priority_browser_harvester as h
from scripts import priority_browser_runner as base

_PATCHED = False
_BASE_REGISTRY = h.REGISTRY
_EXTRA_REGISTRY = Path(__file__).resolve().parents[1] / "sources" / "emerging_compute_browser_sources.json"


def _install_registry_overlay() -> None:
    """Merge reviewed source registries into the one Path consumed by h.main()."""
    payloads = []
    for path in (_BASE_REGISTRY, _EXTRA_REGISTRY):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payloads.append(payload)

    merged: dict[str, dict] = {}
    policies = []
    version = 1
    for payload in payloads:
        version = max(version, int(payload.get("version") or 1))
        policy = h.clean(payload.get("policy"))
        if policy and policy not in policies:
            policies.append(policy)
        for entry in payload.get("sources", []):
            if not isinstance(entry, dict) or entry.get("enabled", True) is False:
                continue
            key = h.clean(entry.get("id")) or h.clean(entry.get("company")).lower()
            if key:
                merged[key] = dict(entry)

    runtime_payload = {
        "version": version,
        "policy": " ".join(policies),
        "sources": list(merged.values()),
    }
    runtime_path = Path(tempfile.gettempdir()) / "pto-priority-browser-sources-runtime.json"
    runtime_path.write_text(json.dumps(runtime_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    h.REGISTRY = runtime_path


def _custom_feishu_response(entry: dict, page, capture, response) -> bool:
    """Handle a reviewed Feishu tenant after it redirects to a custom domain."""
    if h.clean(entry.get("family")).lower() != "feishu":
        return False
    try:
        parsed = urlparse(response.url)
        host = (parsed.hostname or "").lower()
        allowed = {
            (urlparse(h.clean(entry.get("start_url"))).hostname or "").lower(),
            *[h.clean(value).lower() for value in (entry.get("api_hosts") or [])],
        }
        if host not in allowed or not base.FEISHU_JOB_POSTS_PATH_RE.search(parsed.path or ""):
            return False
        payload = response.json()
        rows = base.feishu_job_rows(payload)
        capture.json_responses += 1
        base.mark_feishu_job_posts(capture)
        if len(capture.response_urls) < 30 and response.url not in capture.response_urls:
            capture.response_urls.append(response.url)
        capture.jobs = {
            key: value for key, value in capture.jobs.items()
            if value.get("observed_via") not in {
                "browser-rendered-dom", "browser-current-job-page", "browser-rendered-role-block"
            }
        }
        for row in rows:
            capture.json_candidates += 1
            capture.add(base.normalize_feishu_job(entry, row, response.url, page.url))
        return True
    except Exception as exc:
        if len(capture.errors) < 20:
            capture.errors.append(f"custom feishu response {type(exc).__name__}: {h.clean(exc)[:160]}")
        return True


def _rendered_role_blocks(page) -> list[dict[str, str]]:
    """Read heading/card text from public static careers pages.

    This is deliberately opt-in per source. Broad arbitrary DIV scraping would
    create false jobs, so only heading-like or explicitly job/position/recruit
    classed elements are considered and the Python role predicate stays strict.
    """
    try:
        return page.eval_on_selector_all(
            "h1,h2,h3,h4,h5,h6,[class*='job' i],[class*='position' i],[class*='recruit' i]",
            """els => els.slice(0, 2200).map(el => {
              const text=(el.innerText||el.textContent||'').trim();
              let node=el, block=text, href='';
              for(let i=0;i<5 && node;i++,node=node.parentElement){
                const t=(node.innerText||node.textContent||'').trim();
                if(t.length>=Math.max(8,text.length) && t.length<=2200) block=t;
                const a=(node.matches&&node.matches('a[href]'))?node:(node.querySelector?node.querySelector('a[href]'):null);
                if(!href && a && /^https?:/i.test(a.href||'')) href=a.href;
                if(t.length>=80 && t.length<=1400) break;
              }
              return {text,block,href:href||location.href};
            }).filter(x => x.text.length>=2 && x.text.length<=180 && x.block.length>=x.text.length)""",
        )
    except Exception:
        return []


def _collect_rendered_role_blocks(entry: dict, page, capture) -> int:
    if "browser-rendered-role-blocks" not in (entry.get("modes") or []):
        return 0
    before = len(capture.jobs)
    for item in _rendered_role_blocks(page):
        text = h.clean(item.get("text"))
        block = str(item.get("block") or "").strip()
        role = h.dom_role(text, block)
        if not role or not h.looks_like_role(role, strict=True):
            continue
        href = h.clean(item.get("href"))
        if not href.startswith(("http://", "https://")):
            href = page.url
        job = h.normalize_dom_job(entry, href, role, block)
        if not job:
            continue
        job["source_label"] = f"{h.clean(entry.get('company'))}招聘官网 · 页面公开岗位"
        job["observed_via"] = "browser-rendered-role-block"
        tags = list(job.get("tags") or [])
        job["tags"] = list(dict.fromkeys([*tags, "企业官网", "页面公开岗位"]))
        capture.add(job)
    return len(capture.jobs) - before


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    base.install()
    _install_registry_overlay()

    original_response_handler = h.response_handler

    def response_handler(entry, page, capture, response):
        if _custom_feishu_response(entry, page, capture, response):
            return
        return original_response_handler(entry, page, capture, response)

    h.response_handler = response_handler

    original_collect_dom = h.collect_dom

    def collect_dom(entry, page, capture):
        before = len(capture.jobs)
        original_collect_dom(entry, page, capture)
        _collect_rendered_role_blocks(entry, page, capture)
        return len(capture.jobs) - before

    h.collect_dom = collect_dom

    original_collect_one = h.collect_one

    def collect_one(context, entry):
        jobs, diagnostics = original_collect_one(context, entry)
        if h.clean(entry.get("family")).lower() != "iguopin":
            return jobs, diagnostics

        tenant_jobs = [
            job for job in jobs
            if isinstance(job, dict)
            and job.get("observed_via") == "browser-public-iguopin-tenant-list"
            and h.clean(job.get("tenant_id"))
            and h.clean(job.get("position_id"))
        ]
        rejected = len(jobs) - len(tenant_jobs)
        diagnostics = dict(diagnostics or {})
        diagnostics["iguopin_tenant_only"] = True
        diagnostics["rejected_non_tenant_rows"] = max(0, rejected)
        diagnostics["unique_jobs"] = len(tenant_jobs)
        return tenant_jobs, diagnostics

    h.collect_one = collect_one
    _PATCHED = True


def main() -> int:
    install()
    return h.main()


if __name__ == "__main__":
    raise SystemExit(main())
