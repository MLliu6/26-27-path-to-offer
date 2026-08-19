from __future__ import annotations

import unittest

from scripts import priority_browser_harvester as h
from scripts.priority_browser_runner import has_feishu_job_posts, mark_feishu_job_posts


class FeishuFallbackMarkerTests(unittest.TestCase):
    def test_generic_json_does_not_disable_feishu_fallback(self):
        capture = h.Capture()
        capture.json_responses = 3
        self.assertFalse(has_feishu_job_posts(capture))
        mark_feishu_job_posts(capture)
        self.assertTrue(has_feishu_job_posts(capture))
        self.assertEqual(capture.json_responses, 3)

    def test_marker_counts_only_explicit_job_list_responses(self):
        capture = h.Capture()
        mark_feishu_job_posts(capture)
        mark_feishu_job_posts(capture)
        self.assertTrue(has_feishu_job_posts(capture))
        self.assertEqual(getattr(capture, "_feishu_job_post_responses", 0), 2)


if __name__ == "__main__":
    unittest.main()
