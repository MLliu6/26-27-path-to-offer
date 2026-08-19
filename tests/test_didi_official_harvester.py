from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import didi_official_harvester as didi


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def get(self, url, timeout=None):
        if didi.LIST_ENDPOINT in url:
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(url).query)
            code = query.get("recruitType", [""])[0]
            page = int(query.get("page", ["1"])[0])
            if code == "1" and page == 1:
                return FakeResponse({"meta": {"code": 0}, "data": {"total": 0, "items": [
                    {"jdId": 101, "jobName": "大模型基础设施工程师", "workArea": "北京市", "deptName": "AI平台", "refreshTime": "2026-08-18 12:00:00"},
                    {"jdId": 102, "jobName": "产品经理", "workArea": "杭州市", "deptName": "出行业务", "refreshTime": "2026-08-18 11:00:00"},
                ]}})
            if code == "1" and page == 2:
                return FakeResponse({"meta": {"code": 0}, "data": {"total": 0, "items": [
                    {"jdId": 103, "jobName": "商业分析", "workArea": "上海市", "deptName": "战略", "refreshTime": "2026-08-18 10:00:00"},
                ]}})
            if code == "2" and page == 1:
                return FakeResponse({"meta": {"code": 0}, "data": {"total": 1, "items": [
                    {"jdId": 201, "jobName": "2027届算法工程师", "workArea": "北京市", "deptName": "自动驾驶", "refreshTime": "2026-08-17 09:00:00"},
                ]}})
            return FakeResponse({"meta": {"code": 0}, "data": {"total": 0, "items": []}})
        raise AssertionError(url)


def fake_detail(jd_id):
    data = {
        "101": {"jdId": 101, "jobName": "大模型基础设施工程师", "deptName": "AI平台", "workArea": "北京市", "recruitType": "1", "jobDesc": "负责推理平台和算力调度", "qualification": "本科及以上，熟悉 vLLM 与 CUDA", "refreshTime": "2026-08-18 12:00:00"},
        "102": {"jdId": 102, "jobName": "产品经理", "deptName": "出行业务", "workArea": "杭州市", "recruitType": "1", "jobDesc": "负责产品规划", "qualification": "本科及以上"},
        "103": {"jdId": 103, "jobName": "商业分析", "deptName": "战略", "workArea": "上海市", "recruitType": "1", "jobDesc": "负责商业分析", "qualification": "本科及以上"},
        "201": {"jdId": 201, "jobName": "2027届算法工程师", "deptName": "自动驾驶", "workArea": "北京市", "recruitType": "2", "jobDesc": "机器学习与自动驾驶算法", "qualification": "面向2027届硕士毕业生"},
    }
    return data[str(jd_id)]


class DidiOfficialHarvesterTest(unittest.TestCase):
    def test_unreliable_total_does_not_stop_pagination(self):
        with patch.object(didi, "fetch_detail", side_effect=fake_detail):
            jobs, diagnostics = didi.collect_didi(FakeSession())
        self.assertEqual(len(jobs), 4)
        roles = {job["role"] for job in jobs}
        self.assertIn("商业分析", roles)
        social = next(row for row in diagnostics["scopes"] if row["code"] == "1")
        self.assertGreaterEqual(social["pages"], 3)
        self.assertEqual(social["unique"], 3)

    def test_normalized_rows_keep_scope_and_direct_url(self):
        with patch.object(didi, "fetch_detail", side_effect=fake_detail):
            jobs, _ = didi.collect_didi(FakeSession())
        by_role = {job["role"]: job for job in jobs}
        infra = by_role["大模型基础设施工程师"]
        self.assertEqual(infra["source"], "direct-official:didi")
        self.assertEqual(infra["batch"], "社会招聘")
        self.assertIn("vLLM", infra["jd"])
        self.assertEqual(infra["apply_url"], "https://talent.didiglobal.com/social/p/101")
        campus = by_role["2027届算法工程师"]
        self.assertEqual(campus["batch"], "校园招聘")
        self.assertEqual(campus["graduation"], "2027届")
        self.assertEqual(campus["education"], "硕士")
        self.assertEqual(campus["apply_url"], "https://talent.didiglobal.com/campus/p/201")

    def test_merge_replaces_previous_didi_direct_only(self):
        with patch.object(didi, "fetch_detail", side_effect=fake_detail):
            fresh, _ = didi.collect_didi(FakeSession())
        existing = [
            {"source": "direct-official:didi", "company": "滴滴", "role": "旧岗位", "location": "北京", "position_id": "old"},
            {"source": "direct-official:pdd", "company": "拼多多", "role": "保留岗位", "location": "上海", "position_id": "pdd"},
        ]
        merged = didi.merge_catalog(existing, fresh)
        roles = {job["role"] for job in merged}
        self.assertNotIn("旧岗位", roles)
        self.assertIn("保留岗位", roles)
        self.assertIn("大模型基础设施工程师", roles)


if __name__ == "__main__":
    unittest.main()
