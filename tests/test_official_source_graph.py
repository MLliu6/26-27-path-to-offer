from __future__ import annotations

import unittest

from scripts.official_source_graph import add, canonical_url, observed_source_url, source_key


class OfficialSourceGraphTests(unittest.TestCase):
    def test_reviewed_url_canonicalization_keeps_specific_page(self):
        url = "https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application?utm_source=x"
        self.assertEqual(
            canonical_url(url),
            "https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application",
        )

    def test_ashby_job_details_collapse_to_tenant_board(self):
        a = "https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application"
        b = "https://jobs.ashbyhq.com/applied/22222222-2222-2222-2222-222222222222/application"
        self.assertEqual(observed_source_url(a), "https://jobs.ashbyhq.com/applied")
        self.assertEqual(observed_source_url(b), "https://jobs.ashbyhq.com/applied")
        self.assertEqual(source_key("Applied Intuition", observed_source_url(a)), source_key("Applied Intuition", observed_source_url(b)))

    def test_lever_smartrecruiters_greenhouse_and_recruitee_collapse(self):
        cases = [
            ("https://jobs.lever.co/company/abc-123", "https://jobs.lever.co/company"),
            ("https://jobs.smartrecruiters.com/Company/123456-job-title", "https://jobs.smartrecruiters.com/Company"),
            ("https://job-boards.greenhouse.io/company/jobs/123456", "https://job-boards.greenhouse.io/company"),
            ("https://company.recruitee.com/o/senior-ai-infra-engineer", "https://company.recruitee.com/"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(observed_source_url(raw), expected)

    def test_two_observed_ashby_jobs_create_one_graph_source(self):
        rows = {}
        add(
            rows,
            company="Applied Intuition",
            url="https://jobs.ashbyhq.com/applied/11111111-1111-1111-1111-111111111111/application",
            category="自动驾驶/AI",
            priority=42,
            origin="observed-job",
        )
        add(
            rows,
            company="Applied Intuition",
            url="https://jobs.ashbyhq.com/applied/22222222-2222-2222-2222-222222222222/application",
            category="自动驾驶/AI",
            priority=42,
            origin="observed-job",
        )
        self.assertEqual(len(rows), 1)
        row = next(iter(rows.values()))
        self.assertEqual(row["url"], "https://jobs.ashbyhq.com/applied")
        self.assertEqual(row["origin"], "observed-job")

    def test_non_ats_employer_career_url_is_not_overcollapsed(self):
        url = "https://careers.example.com/jobs/ai-infra-engineer"
        self.assertEqual(observed_source_url(url), url)

    def test_feishu_source_key_uses_portal_not_position_id(self):
        one = "https://company.jobs.feishu.cn/campus/position/111/detail"
        two = "https://company.jobs.feishu.cn/campus/position/222/detail"
        self.assertEqual(source_key("测试公司", one), source_key("测试公司", two))


if __name__ == "__main__":
    unittest.main()
