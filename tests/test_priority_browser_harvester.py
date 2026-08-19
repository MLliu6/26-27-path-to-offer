from __future__ import annotations

import unittest

from scripts.priority_browser_harvester import (
    dom_role,
    job_identity,
    json_candidate,
    merge,
    normalize_dom_job,
    normalize_json_job,
    walk_json,
)


ENTRY = {
    "id": "example",
    "company": "示范芯片",
    "company_type": "民营/AI芯片",
    "start_url": "https://jobs.example.com/campus",
    "official_url": "https://example.com/join",
    "batch": "校园招聘",
}


class PriorityBrowserHarvesterTests(unittest.TestCase):
    def test_nested_public_api_jobs_are_discovered(self):
        payload = {
            "data": {
                "jobList": [
                    {
                        "jobId": "101",
                        "jobName": "大模型推理系统工程师",
                        "city": {"name": "北京"},
                        "jobDescription": "负责推理引擎与 KV Cache 优化",
                        "detailUrl": "/campus/job/101",
                    },
                    {
                        "positionId": "102",
                        "positionName": "CUDA 算子工程师",
                        "locations": [{"name": "上海"}],
                        "requirements": "熟悉 CUDA / C++",
                        "url": "https://jobs.example.com/campus/job/102",
                    },
                ],
                "filters": {
                    "cities": [{"id": 1, "name": "北京"}],
                    "categories": [{"code": "01", "name": "研发"}],
                },
            }
        }
        # response_handler intentionally starts structural traversal from root;
        # the request URL itself must never leak `/job/list` into object paths.
        rows = list(walk_json(payload, "root"))
        titles = {r.get("jobName") or r.get("positionName") for r, _ in rows}
        self.assertIn("大模型推理系统工程师", titles)
        self.assertIn("CUDA 算子工程师", titles)
        self.assertFalse(any(r.get("name") == "北京" and r.get("id") == 1 for r, _ in rows))
        self.assertFalse(any(r.get("name") == "研发" and r.get("code") == "01" for r, _ in rows))

    def test_generic_metadata_name_is_not_a_job(self):
        self.assertFalse(json_candidate({"id": 1, "name": "北京"}, "root.data.cityList[0]"))
        self.assertFalse(json_candidate({"code": "01", "name": "研发"}, "root.filters.categories[0]"))

    def test_normalize_json_job_preserves_official_detail(self):
        raw = {
            "postId": "abc",
            "title": "编译器研发工程师",
            "locationName": "北京",
            "departmentName": "AI 编译器",
            "description": "负责编译器优化",
            "requirement": "熟悉 MLIR",
            "applyUrl": "/position/abc",
        }
        job = normalize_json_job(ENTRY, raw, "root.jobs[0]", "https://jobs.example.com/api/jobs", "https://jobs.example.com/campus")
        self.assertIsNotNone(job)
        self.assertEqual(job["company"], "示范芯片")
        self.assertEqual(job["role"], "编译器研发工程师")
        self.assertEqual(job["location"], "北京")
        self.assertEqual(job["apply_url"], "https://jobs.example.com/position/abc")
        self.assertEqual(job["source"], "direct-official:browser:example")
        self.assertIn("MLIR", job["jd"])

    def test_dom_detail_button_recovers_role_from_card(self):
        block = "CUDA 算子优化工程师\n北京\n岗位职责：负责 GPU kernel 性能优化\n查看详情"
        self.assertEqual(dom_role("查看详情", block), "CUDA 算子优化工程师")
        job = normalize_dom_job(ENTRY, "https://jobs.example.com/job/7", "查看详情", block)
        self.assertIsNotNone(job)
        self.assertEqual(job["role"], "CUDA 算子优化工程师")
        self.assertEqual(job["location"], "北京")

    def test_merge_replaces_managed_source_but_keeps_other_sources(self):
        old_managed = normalize_dom_job(ENTRY, "https://jobs.example.com/job/old", "软件研发工程师", "软件研发工程师 北京")
        other = dict(old_managed)
        other.update({"source": "direct-official:other", "id": "other", "role": "其他岗位", "apply_url": "https://other.example/job/1"})
        fresh = normalize_dom_job(ENTRY, "https://jobs.example.com/job/new", "AI 芯片软件工程师", "AI 芯片软件工程师 北京")
        merged = merge([old_managed, other], {"direct-official:browser:example": [fresh]})
        roles = {row["role"] for row in merged}
        self.assertNotIn("软件研发工程师", roles)
        self.assertIn("AI 芯片软件工程师", roles)
        self.assertIn("其他岗位", roles)
        self.assertEqual(len({job_identity(row) for row in merged}), len(merged))


if __name__ == "__main__":
    unittest.main()
