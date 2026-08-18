from __future__ import annotations

import unittest

from scripts import pdd_official_harvester as pdd


EXACT_ID = "5e4eb6f3-294f-491b-9d39-42895eed98c3"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def post(self, url, json=None, timeout=None):
        body = json or {}
        if url == pdd.LIST_GRAD:
            return FakeResponse({
                "success": True,
                "result": {
                    "total": "3",
                    "list": [
                        {
                            "id": EXACT_ID,
                            "name": "AI Infra研发工程师",
                            "workLocationName": "上海",
                            "job": "technology",
                            "jobName": "技术",
                            "releaseTime": 1778210700000,
                            "jobDuty": "负责大模型训练与推理基础设施研发，建设高并发低延迟在线推理平台。",
                            "recruitTypeName": "技术专场",
                            "graduationYear": "2027",
                            "labelList": ["紧缺"],
                        },
                        {
                            "id": "pdd-product-1",
                            "name": "产品经理管培生",
                            "workLocationName": "上海",
                            "jobName": "产品",
                            "releaseTime": 1778210700000,
                            "jobDuty": "负责用户研究和产品规划。",
                            "recruitTypeName": "管培生",
                            "graduationYear": "2027",
                        },
                        {
                            "id": "pdd-legal-1",
                            "name": "法务助理（上海）",
                            "workLocationName": "上海",
                            "jobName": "职能",
                            "releaseTime": 1778210700000,
                            "jobDuty": "协助全球合规与合同审阅。",
                            "recruitTypeName": "管培生",
                            "graduationYear": "2027",
                        },
                    ],
                },
            })
        if url == pdd.LIST_INTERN:
            return FakeResponse({
                "success": True,
                "result": {
                    "total": "1",
                    "list": [{
                        "id": "pdd-intern-1",
                        "name": "HR实习生",
                        "workLocationName": "上海市",
                        "jobName": "职能",
                        "releaseTime": 1786869350000,
                        "jobDuty": "协助校园招聘流程。",
                        "recruitTypeName": "管培生",
                        "graduationYear": "2027",
                    }],
                },
            })
        if url == pdd.DETAIL_GRAD:
            pid = body.get("id")
            if pid == EXACT_ID:
                return FakeResponse({
                    "success": True,
                    "result": {
                        "id": EXACT_ID,
                        "name": "AI Infra研发工程师",
                        "workLocationName": "上海",
                        "jobName": "技术",
                        "releaseTime": 1778210700000,
                        "jobDuty": "负责大模型训练与推理基础设施研发，建设高并发低延迟在线推理平台。",
                        "serveRequirement": "熟悉 vLLM、PyTorch、GPU、RDMA、NVLink、分布式系统与 C/C++、Python。",
                        "recruitTypeName": "技术专场",
                        "graduationYear": "2027",
                    },
                })
            return FakeResponse({"success": True, "result": {"id": pid}})
        if url in pdd.DETAIL_INTERN_CANDIDATES:
            return FakeResponse({"success": True, "result": {}})
        raise AssertionError(f"unexpected endpoint: {url}")


class PddOfficialHarvesterTest(unittest.TestCase):
    def test_exact_position_and_all_categories_survive(self):
        rows, diagnostics = pdd.collect_pdd(FakeSession())
        by_id = {row["position_id"]: row for row in rows}
        self.assertIn(EXACT_ID, by_id)
        exact = by_id[EXACT_ID]
        self.assertEqual(exact["role"], "AI Infra研发工程师")
        self.assertEqual(exact["graduation"], "2027届")
        self.assertIn(f"positionId={EXACT_ID}", exact["apply_url"])
        self.assertIn("vLLM", exact["jd"])
        self.assertIn("分布式系统", exact["jd"])
        self.assertEqual(exact["source"], "direct-official:pdd")
        self.assertTrue(diagnostics["seed_gate_ok"])
        self.assertEqual(len(rows), 4)
        departments = {row["department"] for row in rows}
        self.assertTrue({"技术", "产品", "职能"}.issubset(departments))

    def test_merge_replaces_old_direct_pdd_but_keeps_other_sources(self):
        fresh, _ = pdd.collect_pdd(FakeSession())
        existing = [
            {"source": "direct-official:pdd", "company": "拼多多", "role": "旧职位", "location": "上海", "apply_url": "old"},
            {"source": "direct-official:meituan", "company": "美团", "role": "保留职位", "location": "北京", "apply_url": "keep"},
        ]
        merged = pdd.merge_catalog(existing, fresh)
        roles = {row["role"] for row in merged}
        self.assertNotIn("旧职位", roles)
        self.assertIn("保留职位", roles)
        self.assertIn("AI Infra研发工程师", roles)


if __name__ == "__main__":
    unittest.main()
