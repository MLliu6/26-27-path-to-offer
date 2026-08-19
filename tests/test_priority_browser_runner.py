from __future__ import annotations

import unittest

from scripts import priority_browser_harvester as h
from scripts.priority_browser_runner import install, normalize_heading, page_job_from_text


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

    def test_current_employer_page_with_duty_and_qualification_is_a_job(self):
        entry = {
            "id": "rhino-site-soc",
            "company": "辉羲智能",
            "company_type": "民营/AI芯片初创",
            "category": "AI芯片/具身智能",
            "official_url": "https://www.rhino.auto/",
            "batch": "公开招聘",
        }
        body = (
            "Recruitment\n资深SoC设计工程师\n职位描述\n"
            "按照系统芯片功能和性能要求，编写SoC架构文档并完成RTL设计。\n"
            "任职资格\n电子、微电子、计算机等相关专业，硕士以上学历；熟悉SoC设计流程、Verilog和EDA工具。\n"
            "简历投递：talent@rhino.auto"
        )
        job = page_job_from_text(entry, "https://www.rhino.auto/SoCdesign", ["Recruitment", "资深SoC设计工程师"], body)
        self.assertIsNotNone(job)
        self.assertEqual(job["company"], "辉羲智能")
        self.assertEqual(job["role"], "资深SoC设计工程师")
        self.assertEqual(job["apply_url"], "https://www.rhino.auto/SoCdesign")
        self.assertEqual(job["observed_via"], "browser-current-job-page")

    def test_bracketed_location_metadata_is_removed_from_role(self):
        self.assertEqual(normalize_heading("【全职-上海】芯片功能安全工程师"), "芯片功能安全工程师")
        self.assertEqual(normalize_heading("〖实习-北京〗CUDA算子工程师"), "CUDA算子工程师")

    def test_generic_company_page_is_not_invented_as_job(self):
        entry = {"id": "x", "company": "测试公司", "official_url": "https://example.com"}
        body = "加入我们 公司介绍 工作地点 北京 上海 联系方式 招聘邮箱 hr@example.com"
        self.assertIsNone(page_job_from_text(entry, "https://example.com/join", ["加入我们"], body))


if __name__ == "__main__":
    unittest.main()
