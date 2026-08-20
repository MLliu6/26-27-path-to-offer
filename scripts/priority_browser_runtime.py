#!/usr/bin/env python3
"""Production entrypoint for reviewed browser ATS adapters.

The base runner installs reviewed schema adapters. This final runtime layer
adds one provenance rule that is intentionally stricter than the generic
browser collector: IGuopin employer portals may contribute concrete jobs only
from the tenant-scoped public `/api/jobs/v1/list` response normalized by the
IGuopin adapter. Generic site configuration JSON and rendered portal metadata
are never accepted as job rows for an IGuopin source.
"""
from __future__ import annotations

from scripts import priority_browser_harvester as h
from scripts import priority_browser_runner as base

_PATCHED = False


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    base.install()
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
