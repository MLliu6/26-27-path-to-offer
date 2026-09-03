#!/usr/bin/env python3
"""Production entrypoint for reviewed browser ATS adapters.

The base runner installs reviewed schema adapters. This final runtime layer keeps
strict provenance rules for shared ATS families and overlays a few reviewed
employer-specific browser sources whose public job schema needs small adapters.

Huawei is collected from its anonymous official campus portal. The page itself
calls ``HW.Portal.Reccamp.Job.findJobList`` and renders concrete rows containing
``jobId``, ``jobname``, ``jobArea``/``jobAddress`` and ``dataSource``. We observe
that normal browser traffic and reconstruct the same public official detail URL;
we do not log in, upload resumes, solve CAPTCHA, replay private cookies or bypass
access controls.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote

from scripts import priority_browser_harvester as h
from scripts import priority_browser_runner as base

_PATCHED = False
_BASE_REGISTRY = h.REGISTRY
_EXTRA_REGISTRIES = [
    Path(__file__).resolve().parents[1] / "sources" / "huawei_browser_source.json",
    Path(__file__).resolve().parents[1] / "sources" / "reviewed_target_jobs_v15.json",
    Path(__file__).resolve().parents[1] / "sources" / "reviewed_target_portals_v15.json",
]


def _install_registry_overlay() -> None:
    payloads = []
    for path in [_BASE_REGISTRY, *_EXTRA_REGISTRIES]:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payloads.append(payload)

    merged: dict[str, dict] = {}
    policies: list[str] = []
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

    runtime_path = Path(tempfile.gettempdir()) / "pto-priority-browser-sources-runtime.json"
    runtime_path.write_text(json.dumps({
        "version": version,
        "policy": " ".join(policies),
        "sources": list(merged.values()),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    h.REGISTRY = runtime_path


def _huawei_text(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return h.flat_text(value, 800)
    return ""


def _patch_huawei_job(entry: dict, row: dict, job: dict | None) -> dict | None:
    if h.clean(entry.get("family")).lower() != "huawei" or not job:
        return job

    role = _huawei_text(row, "jobname", "jobName", "externalJobName", "externaljobname") or h.clean(job.get("role"))
    job_id = _huawei_text(row, "jobId", "jobid", "id") or h.clean(job.get("position_id"))
    if not role or not job_id:
        return None

    location = _huawei_text(row, "jobArea", "jobarea", "jobAddress", "jobaddress", "workplace", "workPlace")
    department = _huawei_text(row, "deptName", "deptname", "jobFamilyName", "jobfamilyname")
    data_source = _huawei_text(row, "dataSource", "datasource")
    detail = (
        "https://career.huawei.com/reccampportal/portal5/campus-recruitment-detail.html"
        f"?jobId={quote(job_id, safe='')}"
    )
    if data_source:
        detail += f"&dataSource={quote(data_source, safe='')}"

    job.update({
        "role": role[:140],
        "location": location or h.clean(job.get("location")),
        "department": department or h.clean(job.get("department")),
        "batch": "2027校园招聘",
        "graduation": "2027届",
        "industry": "ICT/AI/芯片/云计算",
        "notice_url": detail,
        "apply_url": detail,
        "source_label": "华为校园招聘官网 · 公开职位",
        "observed_via": "browser-public-huawei-campus-list",
        "position_id": job_id,
    })
    job["tags"] = list(dict.fromkeys([*(job.get("tags") or []), "华为官网", "2027校园招聘", "公开职位列表"]))
    job["id"] = h.stable_id("华为", role, job.get("location"), job_id)
    return job


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    base.install()
    _install_registry_overlay()

    # Huawei list rows use these names on the public campus page.
    h.LOCATION_KEYS = base.extend(h.LOCATION_KEYS, ("jobarea", "jobaddress"))
    h.DEPARTMENT_KEYS = base.extend(h.DEPARTMENT_KEYS, ("deptname", "jobfamilyname"))

    original_normalize_json_job = h.normalize_json_job

    def normalize_json_job(entry, row, path, response_url, page_url):
        job = original_normalize_json_job(entry, row, path, response_url, page_url)
        return _patch_huawei_job(entry, row, job)

    h.normalize_json_job = normalize_json_job

    original_collect_one = h.collect_one

    def collect_one(context, entry):
        jobs, diagnostics = original_collect_one(context, entry)
        family = h.clean(entry.get("family")).lower()
        if family == "huawei":
            diagnostics = dict(diagnostics or {})
            diagnostics["huawei_official_list"] = True
            diagnostics["official_detail_links"] = sum(
                1 for job in jobs
                if h.clean(job.get("apply_url")).startswith(
                    "https://career.huawei.com/reccampportal/portal5/campus-recruitment-detail.html?jobId="
                )
            )
            return jobs, diagnostics
        if family != "iguopin":
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
