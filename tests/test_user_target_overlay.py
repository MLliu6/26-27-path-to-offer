import json
import unittest
from pathlib import Path

from scripts import user_target_overlay as o

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sources" / "user_target_positions_20260903.json"


class UserTargetOverlayTest(unittest.TestCase):
    def test_manifest_has_expected_scale_and_ids(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        targets = payload.get("targets") or []
        companies = {x.get("company") for x in targets if isinstance(x, dict)}
        roles = [r for x in targets if isinstance(x, dict) for r in (x.get("roles") or []) if isinstance(r, dict)]
        ids = {str(r.get("position_id") or "") for r in roles}
        self.assertGreaterEqual(len(companies), 45)
        self.assertGreaterEqual(len(roles), 85)
        for pid in [
            "5e4eb6f3-294f-491b-9d39-42895eed98c3",
            "JR2024107", "JR2024109",
            "7667126080873433397", "7669645528939153717",
            "199907640056", "199907720115",
            "4531829293", "4534241363",
            "7659673414492145946",
            "7646709410002323731",
            "2088167899066974208",
            "7672029899397744902",
            "10493864",
            "0b8de09c-3508-4144-99b2-3ddcfd88a29b",
        ]:
            self.assertIn(pid, ids)

    def test_role_company_and_city_matching(self):
        self.assertTrue(o.role_match("AI Infra 研发工程师", "AI Infra研发工程师"))
        self.assertTrue(o.role_match("高性能计算/系统开发", "高性能计算系统开发工程师"))
        self.assertEqual(o.company_norm("Shopee（深圳虾皮信息科技有限公司）"), o.company_norm("Shopee"))
        self.assertEqual(o.company_norm("小鹏汽车"), o.company_norm("小鹏集团"))
        self.assertTrue(o.location_compatible("北京/合肥", "北京市"))
        self.assertFalse(o.location_compatible("北京", "湖南·长沙市"))
        live = [
            {"c": "沐曦", "r": "GPU验证和Agentic AI工程师", "l": "湖南·长沙市", "s": "live"},
            {"c": "沐曦", "r": "AI 工程师", "l": "北京", "s": "live"},
        ]
        hit = o.live_match("沐曦", "北京", {"title": "AI 工程师"}, live)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["l"], "北京")

    def test_curated_seed_is_explicitly_not_live(self):
        target = {"company": "Example", "location": "北京", "portal_url": "https://careers.example.com/jobs"}
        role = {"title": "AI Infra工程师", "tier": "S+"}
        row = o.seed_row(target, role, "2026-09-03")
        self.assertIsNotNone(row)
        self.assertEqual(row["s"], o.SOURCE)
        self.assertEqual(row["q"], 6)
        self.assertIn("待官网实时复核", row["b"])
        self.assertIn("不代表岗位仍开放", row["d"])


if __name__ == "__main__":
    unittest.main()
