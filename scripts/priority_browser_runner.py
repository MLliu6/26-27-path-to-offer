#!/usr/bin/env python3
"""Install public-ATS schema adapters, then run the generic browser harvester.

The generic collector intentionally keeps a conservative field vocabulary so
filter metadata cannot be mistaken for jobs.  This runner adds reviewed schema
aliases for ATS families that we have actually observed in employer public UI
traffic.  It does not add another transport or bypass any access control.
"""
from __future__ import annotations

from urllib.parse import quote

from scripts import priority_browser_harvester as h


EXTRA_TITLE_KEYS = (
    "jobadname", "job_ad_name", "jobadtitle", "job_ad_title",
)
EXTRA_ID_KEYS = (
    "jobadid", "job_ad_id", "jobadcode", "job_ad_code",
)
EXTRA_LOCATION_KEYS = (
    "detailaddress", "detail_address", "joblocation", "job_location",
    "joblocations", "job_locations", "worklocations", "work_locations",
)
EXTRA_DEPARTMENT_KEYS = (
    "kind", "jobkind", "job_kind", "jobfamily", "job_family",
)
EXTRA_JD_KEYS = (
    "jobaddescription", "job_ad_description", "jobadrequirement", "job_ad_requirement",
    "jobadresponsibility", "job_ad_responsibility", "workcontent", "work_content",
)
EXTRA_UPDATED_KEYS = (
    "postdate", "post_date", "modifiedtime", "modified_time", "createdtime", "created_time",
)


def extend(existing, extra):
    return tuple(dict.fromkeys([*existing, *extra]))


def install() -> None:
    h.TITLE_KEYS = extend(h.TITLE_KEYS, EXTRA_TITLE_KEYS)
    h.ID_KEYS = extend(h.ID_KEYS, EXTRA_ID_KEYS)
    h.LOCATION_KEYS = extend(h.LOCATION_KEYS, EXTRA_LOCATION_KEYS)
    h.DEPARTMENT_KEYS = extend(h.DEPARTMENT_KEYS, EXTRA_DEPARTMENT_KEYS)
    h.JD_KEYS = extend(h.JD_KEYS, EXTRA_JD_KEYS)
    h.UPDATED_KEYS = extend(h.UPDATED_KEYS, EXTRA_UPDATED_KEYS)

    base_normalize = h.normalize_json_job

    def normalize_json_job(entry, row, path, response_url, page_url):
        job = base_normalize(entry, row, path, response_url, page_url)
        if not job:
            return None
        position_id = h.clean(job.get("position_id"))
        template = h.clean(entry.get("detail_url_template"))
        if position_id and template:
            detail = template.replace("{position_id}", quote(position_id, safe=""))
            if detail.startswith(("http://", "https://")):
                job["apply_url"] = detail
                job["notice_url"] = detail
                job["id"] = h.stable_id(job.get("company"), job.get("role"), job.get("location"), position_id)
        salary = h.flat_text(h.first_value(row, ("salary", "salaryrange", "salary_range")), 160)
        if salary:
            job["salary"] = salary
        return job

    h.normalize_json_job = normalize_json_job


def main() -> int:
    install()
    return h.main()


if __name__ == "__main__":
    raise SystemExit(main())
