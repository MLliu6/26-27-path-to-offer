import unittest

from scripts.priority_browser_runner import normalize_feishu_job


class FeishuBatchPreservationTests(unittest.TestCase):
    def test_reviewed_2027_batch_survives_generic_recruit_type(self):
        entry = {
            "id": "minimax",
            "company": "MiniMax",
            "company_type": "民营/大模型/AI",
            "category": "大模型/AI",
            "start_url": "https://vrfi1sk8a0.jobs.feishu.cn/379481/?project=7495675705720965415",
            "official_url": "https://www.minimaxi.com/careers",
            "batch": "2027校园招聘",
        }
        row = {
            "id": "post-2027",
            "title": "大模型推理系统工程师",
            "city_list": [{"name": "北京"}],
            "job_function": {"name": "研发"},
            "recruit_type": {"name": "校园招聘"},
            "description": "负责大模型推理系统研发与性能优化",
            "requirement": "熟悉CUDA、推理引擎和系统优化",
        }
        job = normalize_feishu_job(
            entry,
            row,
            "https://vrfi1sk8a0.jobs.feishu.cn/api/v1/search/job/posts",
            entry["start_url"],
        )
        self.assertIsNotNone(job)
        self.assertEqual(job["batch"], "2027校园招聘")
        self.assertEqual(job["graduation"], "2027届")
        self.assertEqual(
            job["apply_url"],
            "https://vrfi1sk8a0.jobs.feishu.cn/379481/position/post-2027/detail",
        )


if __name__ == "__main__":
    unittest.main()
