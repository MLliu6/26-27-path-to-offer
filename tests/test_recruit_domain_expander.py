import os
import unittest
from unittest.mock import patch

from scripts import recruit_domain_expander as e
from scripts import recruit_domain_sweep as s


class RecruitDomainExpanderTest(unittest.TestCase):
    def test_recruit_surface_family(self):
        yes = [
            "https://zhaopin.jd.com/home",
            "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs",
            "https://job.xiaohongshu.com/campus",
            "https://talent.baidu.com/jobs/list",
            "https://career.hihonor.com/",
            "https://zhipu-ai.jobs.feishu.cn/campus",
            "https://metax.zhiye.com/campus",
        ]
        for url in yes:
            self.assertTrue(e.is_recruit_surface(e.normalize_url(url)), url)

    def test_reject_aggregator_static_and_auth_shell(self):
        for url in [
            "https://www.zhipin.com/job_detail/abc.html",
            "https://weworkremotely.com/remote-jobs/example",
            "https://remotive.com/remote-jobs/software-dev/example",
            "https://www.indeed.com/jobs?q=ai",
            "https://www.linkedin.com/jobs/view/1",
        ]:
            self.assertEqual(e.normalize_url(url), "", url)
        self.assertEqual(e.normalize_url("https://career.example.com/assets/main.js"), "")
        self.assertFalse(e.is_recruit_surface(e.normalize_url("https://example.com/login")))

    def test_real_registry_expands_major_china_employers(self):
        entries, meta = e.build()
        companies = {x.get("company") for x in entries}
        for company in ["快手", "百度", "阿里巴巴", "字节跳动", "小红书", "地平线", "寒武纪", "摩尔线程", "沐曦"]:
            self.assertIn(company, companies)
        self.assertGreaterEqual(meta["source_count"], 50)
        self.assertGreaterEqual(meta["sweepable_count"], 20)
        self.assertTrue(meta.get("employer_direct_only"))
        hosts = {x.get("host") for x in entries}
        self.assertNotIn("weworkremotely.com", hosts)
        self.assertNotIn("remotive.com", hosts)

        ks = [x for x in entries if x.get("company") == "快手" and x.get("sweep_enabled")]
        self.assertGreaterEqual(len(ks), 4)
        urls = [x.get("start_url", "") for x in ks]
        self.assertEqual(sum("recruitSubProjectCodes=20271779425607" in u for u in urls), 1)
        self.assertEqual(sum("recruitSubProjectCodes=20271772783534" in u for u in urls), 1)
        self.assertTrue(any("/official/social/" in u for u in urls))
        self.assertTrue(any("/official/trainee/" in u for u in urls))
        self.assertFalse(any("/official/intern/" in u for u in urls))

        reviewed = s.override_configs()
        fulltime = reviewed["recruit-kuaishou-campus-2027"]
        intern = reviewed["recruit-kuaishou-intern-2027"]
        social = reviewed["recruit-kuaishou-social"]
        trainee = reviewed["recruit-kuaishou-trainee"]
        self.assertEqual(fulltime["adapter"], "kuaishou-campus-api")
        self.assertEqual(fulltime["api_project_code"], "20271779425607")
        self.assertEqual(fulltime["batch"], "2027校园招聘")
        self.assertEqual(intern["adapter"], "kuaishou-campus-api")
        self.assertEqual(intern["api_project_code"], "20271772783534")
        self.assertEqual(intern["batch"], "2027留用实习招聘")
        self.assertEqual(social["adapter"], "kuaishou-experienced-browser")
        self.assertEqual(social["position_nature_code"], "C001")
        self.assertEqual(social["route_fragment"], "official/social")
        self.assertEqual(social["batch"], "社会招聘")
        self.assertEqual(trainee["adapter"], "kuaishou-experienced-browser")
        self.assertEqual(trainee["position_nature_code"], "C002")
        self.assertEqual(trainee["route_fragment"], "official/trainee")
        self.assertEqual(trainee["batch"], "日常实习")

    def test_dedup_and_override(self):
        item = {"company": "X", "url": "https://career.example.com/jobs", "priority": 50}
        entry = e.candidate_from(item, "test", force_sweep=True)
        self.assertEqual(entry["company"], "X")
        self.assertTrue(entry["sweep_enabled"])
        self.assertEqual(e.dedupe_key(entry), e.dedupe_key(dict(entry)))

    def test_shard_union_covers_all(self):
        entries = [
            {"id": f"x{i}", "company": f"C{i}", "start_url": f"https://career{i}.example.com/jobs", "sweep_enabled": True}
            for i in range(37)
        ]
        with patch.dict(os.environ, {"PTO_RECRUIT_SWEEP_MAX_TARGETS": "7", "PTO_RECRUIT_SWEEP_FORCE_COMPANIES": ""}, clear=False):
            _, meta = s.select(entries)
            covered = set()
            for idx in range(meta["shard_count"]):
                with patch.dict(os.environ, {"PTO_RECRUIT_SWEEP_SHARD_INDEX": str(idx)}, clear=False):
                    chosen, _ = s.select(entries)
                    covered.update(x["id"] for x in chosen)
            self.assertEqual(covered, {x["id"] for x in entries})

    def test_force_company_is_always_selected(self):
        entries = [
            {"id": "ks1", "company": "快手", "start_url": "https://campus.kuaishou.cn/#/campus/jobs", "sweep_enabled": True},
            {"id": "jd1", "company": "京东", "start_url": "https://zhaopin.jd.com/home", "sweep_enabled": True},
        ]
        with patch.dict(os.environ, {
            "PTO_RECRUIT_SWEEP_MAX_TARGETS": "1",
            "PTO_RECRUIT_SWEEP_SHARD_INDEX": "0",
            "PTO_RECRUIT_SWEEP_FORCE_COMPANIES": "快手",
        }, clear=False):
            chosen, meta = s.select(entries)
        self.assertTrue(any(x["company"] == "快手" for x in chosen))
        self.assertEqual(meta["forced_targets"], 1)


if __name__ == "__main__":
    unittest.main()
