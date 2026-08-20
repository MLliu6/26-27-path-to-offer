from __future__ import annotations

import unittest

from scripts.didi_ui_priority_seed import is_didi_social_row, merge_priority_rows


class DidiPrioritySeedTests(unittest.TestCase):
    def test_social_rows_are_replaced_but_other_scopes_survive(self):
        previous = [
            {
                "i": "old-social",
                "c": "滴滴",
                "r": "旧社会岗位",
                "l": "北京",
                "s": "direct-official:didi",
                "b": "社会招聘",
                "u": "https://talent.didiglobal.com/social/p/old",
            },
            {
                "i": "campus-201",
                "c": "滴滴",
                "r": "2027届算法工程师",
                "l": "北京",
                "s": "direct-official:didi",
                "b": "校园招聘",
                "u": "https://talent.didiglobal.com/campus/p/201",
            },
            {
                "i": "pdd-1",
                "c": "拼多多",
                "r": "AI Infra研发工程师",
                "l": "北京",
                "s": "direct-official:pdd",
                "u": "https://careers.pddglobalhr.com/campus/grad/detail?positionId=1",
            },
        ]
        fresh = [
            {
                "i": "new-social",
                "c": "滴滴",
                "r": "大模型基础设施工程师",
                "l": "北京",
                "s": "direct-official:didi",
                "b": "社会招聘",
                "u": "https://talent.didiglobal.com/social/p/101",
            }
        ]

        merged = list(merge_priority_rows(previous, fresh).values())
        roles = {row["r"] for row in merged}
        self.assertNotIn("旧社会岗位", roles)
        self.assertIn("大模型基础设施工程师", roles)
        self.assertIn("2027届算法工程师", roles)
        self.assertIn("AI Infra研发工程师", roles)

    def test_social_detection_uses_batch_or_social_route_only_for_didi(self):
        self.assertTrue(is_didi_social_row({"s": "direct-official:didi", "b": "社会招聘"}))
        self.assertTrue(is_didi_social_row({"s": "direct-official:didi", "u": "https://talent.didiglobal.com/social/p/1"}))
        self.assertFalse(is_didi_social_row({"s": "direct-official:didi", "b": "校园招聘", "u": "https://talent.didiglobal.com/campus/p/2"}))
        self.assertFalse(is_didi_social_row({"s": "direct-official:pdd", "b": "社会招聘", "u": "https://example.com/social/p/3"}))


if __name__ == "__main__":
    unittest.main()
