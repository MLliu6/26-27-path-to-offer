from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from scripts import moka_public_harvester as moka


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def envelope(value):
    key = b"0123456789abcdef"
    clear = json.dumps(value, ensure_ascii=False).encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, moka.IV).encrypt(pad(clear, 16))
    return {"data": base64.b64encode(cipher).decode(), "necromancer": key.decode()}


ROWS = {
    "data": {
        "jobs": [
            {
                "id": "shopee-ai-infra-2027-bj",
                "title": "（27届秋招）AI 基础设施研发工程师-北京",
                "locations": [{"cityName": "北京市"}],
                "department": {"name": "Shopee CNDC"},
                "commitment": "全职",
                "publishedAt": "2026-07-28T08:00:00Z",
                "jobDescription": "负责 AI 平台、分布式训练与推理基础设施，建设 GPU 训练推理集群和模型服务。",
                "requirements": "2027届，本科及以上，熟悉分布式系统、C++、Python。",
            },
            {
                "id": "shopee-product-2027-sz",
                "title": "（27届秋招）产品经理-深圳",
                "locations": [{"cityName": "深圳市"}],
                "department": {"name": "Product"},
                "commitment": "全职",
                "publishedAt": "2026-07-28T08:00:00Z",
                "jobDescription": "负责跨境电商产品规划、用户研究和需求分析。",
            },
        ]
    }
}


class FakeSession:
    def post(self, url, json=None, timeout=None):
        self.last_url = url
        self.last_body = json
        return FakeResponse(envelope(ROWS))


class MokaPublicHarvesterTest(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "key": "shopee",
            "org": "shopee",
            "site": 2962,
            "company": "Shopee（深圳虾皮信息科技有限公司）",
            "category": "外企/互联网/跨境电商",
            "portal_kind": "campus-recruitment",
            "official_url": "https://app.mokahr.com/campus-recruitment/shopee/2962#/jobs",
        }

    def test_public_envelope_roundtrip(self):
        self.assertEqual(moka.decrypt_public_envelope(envelope(ROWS)), ROWS)

    def test_shopee_exact_family_normalization(self):
        session = FakeSession()
        jobs, diag = moka.fetch_company(self.spec, session=session)
        self.assertEqual(len(jobs), 2)
        by_title = {job["role"]: job for job in jobs}
        exact = by_title["（27届秋招）AI 基础设施研发工程师-北京"]
        self.assertEqual(exact["company"], "Shopee（深圳虾皮信息科技有限公司）")
        self.assertEqual(exact["source"], "direct-official:shopee")
        self.assertEqual(exact["updated_at"], "2026-07-28")
        self.assertEqual(exact["graduation"], "2027届")
        self.assertIn("北京", exact["location"])
        self.assertIn("AI 平台", exact["jd"])
        self.assertTrue(exact["apply_url"].startswith("https://app.mokahr.com/campus-recruitment/shopee/2962#/job/"))
        self.assertEqual(diag["year_2027_rows"], 2)
        self.assertEqual(diag["beijing_rows"], 1)
        self.assertEqual(session.last_body["orgId"], "shopee")
        self.assertEqual(session.last_body["siteId"], 2962)

    def test_parse_only_moka_seed_rows(self):
        text = """
# comment
shopee | moka | Shopee | shopee | 2962 | 外企电商
li | feishu | 理想汽车 | li.jobs.feishu.cn | | 车厂
biren | moka | 壁仞科技 | biren | 44726 | 半导体
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "companies.seed"
            path.write_text(text, encoding="utf-8")
            rows = moka.parse_moka_seed_file(path)
        self.assertEqual({row["key"] for row in rows}, {"shopee", "biren"})
        shopee = next(row for row in rows if row["key"] == "shopee")
        self.assertEqual(shopee["company"], "Shopee（深圳虾皮信息科技有限公司）")


if __name__ == "__main__":
    unittest.main()
