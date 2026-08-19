from __future__ import annotations

import unittest

from scripts import priority_browser_harvester as h
from scripts.priority_browser_runner import install


class PriorityBrowserRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install()

    def test_beisen_jobad_object_is_a_job(self):
        row = {
            "jobAdId": "e4f28a5f-c434-46de-a73a-5db32762bee4",
            "jobAdName": "AI Infra研发工程师",
            "detailAddress": "北京市海淀区",
            "jobCategory": "软件类",
            "postDate": "2026-08-19T09:00:00Z",
        }
        self.assertTrue(h.json_candidate(row, "root.data.items[0]"))
        self.assertEqual(h.title_from_json(row, "root.data.items[0]"), "AI Infra研发工程师")

    def test_reviewed_detail_template_preserves_specific_job_url(self):
        entry = {
            "id": "mthreads",
            "company": "摩尔线程",
            "company_type": "民营/GPU/AI芯片",
            "start_url": "https://mthreads.zhiye.com/campus",
            "official_url": "https://www.mthreads.com/jobs",
            "batch": "校园招聘",
            "detail_url_template": "https://mthreads.zhiye.com/campus/detail?jobAdId={position_id}",
        }
        row = {
            "jobAdId": "abc-123",
            "jobAdName": "GPU软件研发工程师",
            "detailAddress": "北京",
            "jobDescription": "负责GPU软件栈研发与性能优化",
            "salary": "面议",
        }
        job = h.normalize_json_job(entry, row, "root.data.items[0]", "https://mthreads.zhiye.com/api/Jobad/GetJobAdPageList", entry["start_url"])
        self.assertIsNotNone(job)
        self.assertEqual(job["position_id"], "abc-123")
        self.assertEqual(job["apply_url"], "https://mthreads.zhiye.com/campus/detail?jobAdId=abc-123")
        self.assertEqual(job["salary"], "面议")


if __name__ == "__main__":
    unittest.main()
