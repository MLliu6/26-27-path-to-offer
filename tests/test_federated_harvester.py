from __future__ import annotations

import unittest

from scripts import federated_harvester as fed


class FederatedHarvesterTests(unittest.TestCase):
    def test_normalize_official_row(self):
        fed.RADAR = type("R", (), {"_fmt_date": staticmethod(lambda x: "2026-08-16")})()
        row = {
            "title": "大模型推理系统工程师",
            "company": "京东",
            "location": "北京",
            "dept": "基础架构",
            "jd": "vLLM KV Cache CUDA " * 200,
            "url": "https://example.com/job/1",
            "date": "2026-08-16T12:00:00Z",
        }
        job = fed.normalize_row(row, source="official:jd", label="京东官方")
        self.assertIsNotNone(job)
        self.assertEqual(job["company"], "京东")
        self.assertEqual(job["role"], "大模型推理系统工程师")
        self.assertEqual(job["updated_at"], "2026-08-16")
        self.assertLessEqual(len(job["jd"]), fed.MAX_JD_CHARS + 1)

    def test_cross_source_dedupe_keeps_one_identity(self):
        rows = [
            {"source":"a","source_label":"A","source_url":"https://a","company":"某科技有限公司","role":"CUDA工程师","location":"北京","jd":"CUDA","id":"a"},
            {"source":"b","source_label":"B","source_url":"https://b","company":"某科技","role":"CUDA工程师","location":"北京","jd":"CUDA Tensor Core GEMM","id":"b"},
        ]
        merged = fed.compact_catalog(rows)
        self.assertEqual(len(merged), 1)
        self.assertIn("Tensor Core", merged[0]["jd"])
        self.assertEqual(set(merged[0]["source_labels"]), {"A", "B"})

    def test_moka_is_excluded_from_local_federation(self):
        radar = type("R", (), {"LOCAL_PARSERS": {
            "safe": {"args":["parsers/feishu.py","x.jobs.feishu.cn","X","{keyword}"]},
            "skip": {"args":["parsers/moka.py","org","1","Y","{keyword}"]},
        }})()
        keys = [k for k,_ in fed.safe_local_specs(radar)]
        self.assertEqual(keys, ["safe"])

    def test_company_hint_for_generic_china_ats(self):
        self.assertEqual(fed.infer_company_hint({"args":["parsers/feishu.py","jd.jobs.feishu.cn","京东","{keyword}"]}, "x"), "京东")
        self.assertEqual(fed.infer_company_hint({"args":["parsers/beisen.py","boe","京东方","{keyword}"]}, "x"), "京东方")


if __name__ == "__main__":
    unittest.main()
