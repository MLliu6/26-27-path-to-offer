from __future__ import annotations

import unittest

from scripts.ncss_public_harvester import normalize


class NCSSPublicHarvesterTests(unittest.TestCase):
    def test_explicit_2027_row_is_campus_job(self):
        row = {
            "jobName": "中芯国际2027届校园招聘",
            "jobId": "abc123",
            "recName": "中芯国际集成电路制造（上海）有限公司",
            "areaCodeName": "上海",
            "degreeName": "本科及以上",
            "major": "电子信息、计算机信息技术、自动化等相关专业",
            "recProperty": "外商独资/外企代表处",
            "lowMonthPay": 15,
            "highMonthPay": 20,
            "headCount": 1000,
            "publishDate": 1786537054618,
        }
        job = normalize(row, explicit_query=True)
        self.assertIsNotNone(job)
        self.assertEqual(job["graduation"], "2027届")
        self.assertEqual(job["batch"], "2027校园招聘")
        self.assertEqual(job["salary"], "15-20K/月")
        self.assertEqual(job["notice_url"], "https://job.ncss.cn/student/jobs/abc123/detail.html")
        self.assertEqual(job["apply_url"], "")

    def test_recent_priority_intern_does_not_invent_year(self):
        row = {
            "jobName": "大模型算法实习生",
            "jobId": "mt-ai",
            "recName": "某科技公司",
            "areaCodeName": "北京",
            "degreeName": "硕士及以上",
            "major": "计算机、人工智能",
        }
        job = normalize(row, explicit_query=False)
        self.assertIsNotNone(job)
        self.assertEqual(job["graduation"], "")
        self.assertIn("年份待确认", job["batch"])

    def test_ncss_is_discovery_not_fake_employer_direct_apply(self):
        row = {"jobName":"2027届AI研发","jobId":"j1","recName":"公司A","areaCodeName":"北京"}
        job = normalize(row, explicit_query=True)
        self.assertEqual(job["source"], "ncss-public:2027")
        self.assertEqual(job["apply_url"], "")
        self.assertIn("国家大学生就业服务平台", job["source_label"])


if __name__ == "__main__":
    unittest.main()
