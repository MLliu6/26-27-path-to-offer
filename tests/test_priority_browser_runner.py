from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import priority_browser_harvester as h
from scripts.official_source_graph import add as graph_add
from scripts.official_source_graph import canonical_url as graph_canonical_url
from scripts.official_source_graph import observed_source_url, source_key
from scripts.priority_browser_runner import (
    feishu_job_rows,
    feishu_portal_path,
    install,
    normalize_feishu_job,
    normalize_heading,
    page_job_from_text,
    trusted_response_host,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "priority_browser_sources.json"


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

    def test_feishu_filter_title_metadata_is_not_a_job(self):
        row = {"id": "101", "title": "算法研发", "value": "101"}
        self.assertFalse(h.json_candidate(row, "root.data[0]"))
        self.assertFalse(h.json_candidate(row, "root.data.filters[0]"))

    def test_feishu_direct_job_post_list_excludes_nested_metadata(self):
        payload = {
            "code": 0,
            "data": {
                "count": 1,
                "job_post_list": [{
                    "id": "post-101",
                    "title": "大模型推理系统工程师",
                    "city_list": [{"code": "BJ", "name": "北京"}],
                    "job_function": {"id": "fn-1", "name": "算法研发"},
                    "recruit_type": {"id": "rt-1", "name": "校园招聘"},
                    "description": "负责大模型推理系统研发与性能优化",
                    "requirement": "熟悉CUDA、推理引擎和系统优化",
                    "publish_time": 1787100000000,
                }],
            },
        }
        rows = feishu_job_rows(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "post-101")
        self.assertNotIn(rows[0]["job_function"], rows)
        self.assertNotIn(rows[0]["city_list"][0], rows)

    def test_feishu_direct_row_normalizes_specific_detail_url(self):
        entry = {
            "id": "rhino",
            "company": "辉羲智能",
            "company_type": "民营/AI芯片初创",
            "category": "AI芯片/具身智能",
            "start_url": "https://r712him1th.jobs.feishu.cn/huixi/position/list",
            "official_url": "https://www.rhino.auto/ShouYe",
            "batch": "公开招聘",
        }
        row = {
            "id": "post-101",
            "title": "大模型推理系统工程师",
            "city_list": [{"code": "BJ", "name": "北京"}],
            "job_function": {"id": "fn-1", "name": "算法研发"},
            "recruit_type": {"id": "rt-1", "name": "校园招聘"},
            "description": "负责大模型推理系统研发与性能优化",
            "requirement": "熟悉CUDA、推理引擎和系统优化",
            "publish_time": 1787100000000,
        }
        job = normalize_feishu_job(entry, row, "https://r712him1th.jobs.feishu.cn/api/v1/search/job/posts", entry["start_url"])
        self.assertIsNotNone(job)
        self.assertEqual(job["position_id"], "post-101")
        self.assertEqual(job["location"], "北京")
        self.assertEqual(job["department"], "算法研发")
        self.assertEqual(job["apply_url"], "https://r712him1th.jobs.feishu.cn/huixi/position/post-101/detail")
        self.assertEqual(job["observed_via"], "browser-public-feishu-job-list")

    def test_feishu_reviewed_2027_batch_survives_generic_recruit_type(self):
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
        job = normalize_feishu_job(entry, row, "https://vrfi1sk8a0.jobs.feishu.cn/api/v1/search/job/posts", entry["start_url"])
        self.assertIsNotNone(job)
        self.assertEqual(job["batch"], "2027校园招聘")
        self.assertEqual(job["graduation"], "2027届")
        self.assertEqual(job["apply_url"], "https://vrfi1sk8a0.jobs.feishu.cn/379481/position/post-2027/detail")

    def test_feishu_portal_path_handles_root_style_project_portal(self):
        self.assertEqual(feishu_portal_path({"start_url": "https://vrfi1sk8a0.jobs.feishu.cn/379481/?project=123"}), "379481")
        self.assertEqual(feishu_portal_path({"start_url": "https://agirobot.jobs.feishu.cn/campusrecruitment"}), "campusrecruitment")

    def test_browser_json_isolated_to_registered_ats_host(self):
        feishu = {"start_url": "https://r712him1th.jobs.feishu.cn/huixi/position/list"}
        self.assertTrue(trusted_response_host(feishu, "https://r712him1th.jobs.feishu.cn/api/v1/search/job/posts?offset=0"))
        self.assertFalse(trusted_response_host(feishu, "https://starling.zijieapi.com/check_and_get_text/abc"))
        self.assertFalse(trusted_response_host(feishu, "https://mon.zijieapi.com/monitor_web/settings/browser-settings"))

        moka = {"start_url": "https://app.mokahr.com/campus-recruitment/moonshot/148507#/jobs"}
        self.assertTrue(trusted_response_host(moka, "https://app.mokahr.com/api/outer/ats-apply/website/jobs/v2"))
        self.assertFalse(trusted_response_host(moka, "https://sentry-fe.mokahr.com/api/98/envelope/"))

        reviewed_cross_host = {"start_url": "https://jobs.example.com/", "api_hosts": ["api.example.com"]}
        self.assertTrue(trusted_response_host(reviewed_cross_host, "https://api.example.com/jobs"))

    def test_reviewed_detail_template_preserves_specific_job_url(self):
        entry = {
            "id": "mthreads",
            "company": "摩尔线程",
            "company_type": "民营/GPU/AI芯片",
            "start_url": "https://mthreads.zhiye.com/campus/jobs",
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
            "id": "company-job-page",
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

    def test_priority_browser_registry_keeps_distinct_priority_companies(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        sources = [row for row in payload.get("sources", []) if isinstance(row, dict)]
        companies = {row.get("company") for row in sources}
        required = {
            "辉羲智能", "银河通用", "智元机器人", "地平线", "寒武纪", "摩尔线程", "沐曦", "壁仞科技", "智谱AI",
            "月之暗面", "MiniMax", "阶跃星辰", "燧原科技", "宇树科技", "昆仑芯",
        }
        self.assertEqual(len(sources), len(companies), "priority browser registry should use one authoritative live entry per company")
        self.assertGreaterEqual(len(companies), 15)
        self.assertTrue(required.issubset(companies), required - companies)
        by_id = {row.get("id"): row for row in sources}
        self.assertEqual(by_id["moonshot"]["start_url"], "https://app.mokahr.com/campus-recruitment/moonshot/148507#/jobs")
        self.assertIn("project=7495675705720965415", by_id["minimax"]["start_url"])
        self.assertIn("campus-recruitment/step/141903", by_id["stepfun"]["start_url"])
        self.assertIn("campus-recruitment/enflame/168420", by_id["enflame"]["start_url"])
        self.assertEqual(by_id["unitree"]["start_url"], "https://www.unitree.com/cn/position/")
        self.assertEqual(by_id["mthreads"]["start_url"], "https://mthreads.zhiye.com/campus/jobs")
        self.assertIn("jobAdId={position_id}", by_id["mthreads"]["detail_url_template"])
        self.assertEqual(by_id["cambricon"]["start_url"], "https://app.mokahr.com/campus-recruitment/cambricon/44201")
        self.assertEqual(by_id["zhipu"]["start_url"], "https://zhipu-ai.jobs.feishu.cn/zhipucampus/position/list")
        self.assertEqual(by_id["rhino"]["start_url"], "https://r712him1th.jobs.feishu.cn/huixi/position/list")
        self.assertEqual(by_id["kunlunxin"]["start_url"], "https://kunlunxin.zhiye.com/xiangqing?jobId=151190919")


class OfficialSourceGraphTests(unittest.TestCase):
    def test_reviewed_url_canonicalization_keeps_specific_page(self):
        url = "https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application?utm_source=x"
        self.assertEqual(
            graph_canonical_url(url),
            "https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application",
        )

    def test_shared_ats_position_urls_collapse_to_company_boards(self):
        cases = [
            ("https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application", "https://jobs.ashbyhq.com/applied"),
            ("https://jobs.lever.co/company/abc-123", "https://jobs.lever.co/company"),
            ("https://jobs.smartrecruiters.com/Company/123456-job-title", "https://jobs.smartrecruiters.com/Company"),
            ("https://job-boards.greenhouse.io/company/jobs/123456", "https://job-boards.greenhouse.io/company"),
            ("https://boards.greenhouse.io/embed/job_app?for=company&token=123456", "https://boards.greenhouse.io/company"),
            ("https://company.recruitee.com/o/senior-ai-infra-engineer", "https://company.recruitee.com/"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(observed_source_url(raw), expected)

    def test_two_ashby_positions_create_one_graph_node(self):
        rows = {}
        for job_id in ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]:
            graph_add(
                rows,
                company="Applied Intuition",
                url=f"https://jobs.ashbyhq.com/applied/{job_id}/application",
                category="自动驾驶/AI",
                priority=42,
                origin="observed-job",
            )
        self.assertEqual(len(rows), 1)
        row = next(iter(rows.values()))
        self.assertEqual(row["url"], "https://jobs.ashbyhq.com/applied")

    def test_feishu_source_key_does_not_include_position_id(self):
        one = "https://company.jobs.feishu.cn/campus/position/111/detail"
        two = "https://company.jobs.feishu.cn/campus/position/222/detail"
        self.assertEqual(source_key("测试公司", one), source_key("测试公司", two))

    def test_non_ats_career_url_is_not_overcollapsed(self):
        url = "https://careers.example.com/jobs/ai-infra-engineer"
        self.assertEqual(observed_source_url(url), url)


if __name__ == "__main__":
    unittest.main()