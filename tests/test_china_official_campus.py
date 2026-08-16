from __future__ import annotations

import unittest

from scripts.china_official_campus import (
    company_name,
    geo_kind,
    normalize_position,
    old_v07_job,
    parse_json_stdout,
    rank,
    source_key,
    source_url,
)


class ChinaOfficialCampusTests(unittest.TestCase):
    def setUp(self):
        self.jd={"key":"jd","family":"Bespoke","source":"campus.jd.com","label":"JD / 京东"}

    def test_directory_identity_and_portal_are_company_official(self):
        self.assertEqual(company_name(self.jd),"京东")
        self.assertEqual(source_url(self.jd),"https://campus.jd.com")
        zhipu={"key":"zhipu","family":"Feishu","source":"zhipu-ai.jobs.feishu.cn","label":"Zhipu / 智谱AI"}
        self.assertEqual(company_name(zhipu),"智谱AI")
        self.assertEqual(source_url(zhipu),"https://zhipu-ai.jobs.feishu.cn")

    def test_scope_campus_provenance_is_explicit_in_normalized_row(self):
        row=normalize_position(self.jd,{
            "post_id":"123","title":"大模型推理系统工程师","project":"2027校园招聘","recruit_label":"技术",
            "bgs":"基础架构","work_cities":"北京","apply_url":"https://campus.jd.com/job/123"
        })
        self.assertIsNotNone(row)
        self.assertEqual(row["company"],"京东")
        self.assertTrue(row["source"].startswith("china-campus:jobpro:jd"))
        self.assertIn("校园招聘",row["batch"])
        self.assertIn("企业官网",row["tags"])
        self.assertEqual(row["apply_url"],"https://campus.jd.com/job/123")
        self.assertEqual(source_key(row),"jd")
        self.assertTrue(old_v07_job(row))

    def test_foreign_only_and_senior_rows_are_rejected(self):
        foreign=normalize_position(self.jd,{"post_id":"1","title":"LLM Engineer","work_cities":"Singapore","apply_url":"https://campus.jd.com/1"})
        senior=normalize_position(self.jd,{"post_id":"2","title":"资深大模型推理架构师","work_cities":"北京","apply_url":"https://campus.jd.com/2"})
        self.assertIsNone(foreign)
        self.assertIsNone(senior)
        self.assertEqual(geo_kind("北京 / 上海"),"china")
        self.assertEqual(geo_kind("Singapore"),"foreign")

    def test_beijing_priority(self):
        bj=normalize_position(self.jd,{"post_id":"1","title":"CUDA算子工程师","work_cities":"北京","apply_url":"https://campus.jd.com/1"})
        sh=normalize_position(self.jd,{"post_id":"2","title":"CUDA算子工程师","work_cities":"上海","apply_url":"https://campus.jd.com/2"})
        self.assertGreater(rank(bj),rank(sh))

    def test_cli_json_parser_tolerates_package_manager_noise(self):
        payload=parse_json_stdout("npm notice cache\n{\"ok\":true,\"positions\":[]}\n")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["positions"],[])


if __name__=="__main__":
    unittest.main()
