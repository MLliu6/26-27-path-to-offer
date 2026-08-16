from __future__ import annotations

import unittest

from scripts.china_official_campus import (
    adapter_family,
    career_kind,
    company_hint,
    eligible,
    geo_kind,
    portal_for,
    sort_key,
    source_is_company_official,
)


class ChinaOfficialCampusTests(unittest.TestCase):
    def test_adapter_families_and_public_company_portals(self):
        feishu={"args":["parsers/feishu.py","zhipu-ai.jobs.feishu.cn","智谱AI","{keyword}"]}
        moka={"args":["parsers/moka.py","cambricon","44201","寒武纪","{keyword}"]}
        beisen={"args":["parsers/beisen.py","boe","京东方","{keyword}"]}
        self.assertEqual(adapter_family(feishu),"feishu")
        self.assertEqual(company_hint("zhipu",feishu),"智谱AI")
        self.assertEqual(portal_for("zhipu",feishu),"https://zhipu-ai.jobs.feishu.cn")
        self.assertEqual(adapter_family(moka),"moka")
        self.assertEqual(company_hint("cambricon",moka),"寒武纪")
        self.assertEqual(portal_for("cambricon",moka),"https://app.mokahr.com/social-recruitment/cambricon/44201")
        self.assertEqual(adapter_family(beisen),"beisen")
        self.assertEqual(portal_for("boe",beisen),"https://boe.zhiye.com")

    def test_domestic_campus_survives_foreign_and_senior_do_not(self):
        campus={"company":"京东","role":"大模型推理系统工程师","location":"北京","batch":"2027校园招聘","jd":"vLLM CUDA"}
        foreign={**campus,"company":"Foreign","location":"Singapore"}
        senior={**campus,"role":"资深大模型推理架构师","batch":"社会招聘"}
        self.assertEqual(geo_kind(campus["location"]),"china")
        self.assertEqual(career_kind(campus),"early")
        self.assertTrue(eligible(campus,official=True)[0])
        self.assertFalse(eligible(foreign,official=True)[0])
        self.assertFalse(eligible(senior,official=True)[0])

    def test_unknown_company_official_role_can_survive(self):
        # Chinese company portals often omit a per-row “校招” literal even when
        # the surrounding portal is a campus/early-career surface.
        job={"company":"智谱AI","role":"系统研发工程师","location":"北京","batch":"","jd":"CUDA 推理"}
        self.assertTrue(eligible(job,official=True)[0])

    def test_beijing_official_priority_and_source_detection(self):
        bj={"company":"智谱AI","role":"AI Infra工程师","location":"北京","batch":"校招","source":"china-company:feishu:zhipu","source_label":"公司官网 · 智谱AI","apply_url":"https://zhipu-ai.jobs.feishu.cn/x","updated_at":"2026-08-17"}
        sh={**bj,"location":"上海"}
        self.assertTrue(source_is_company_official(bj))
        self.assertGreater(sort_key(bj),sort_key(sh))


if __name__=="__main__":
    unittest.main()
