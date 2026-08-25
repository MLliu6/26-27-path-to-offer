from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import recruit_domain_sweep as sweep


class RecruitDomainDetailLinksTest(unittest.TestCase):
    def test_enriches_only_selected_reviewed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs.json"
            overrides = root / "overrides.json"
            jobs.write_text(json.dumps({
                "schema_version": 3,
                "jobs": [
                    {
                        "source": "direct-official:browser:recruit-kuaishou-campus",
                        "company": "快手",
                        "role": "多模态推理平台工程师",
                        "position_id": "12763",
                        "apply_url": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs",
                        "notice_url": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs",
                        "tags": ["企业官网/官方ATS"],
                    },
                    {
                        "source": "direct-official:browser:other-source",
                        "company": "其他公司",
                        "role": "研发工程师",
                        "position_id": "99",
                        "apply_url": "https://example.com/jobs",
                        "notice_url": "https://example.com/jobs",
                    },
                ],
            }, ensure_ascii=False), encoding="utf-8")
            overrides.write_text(json.dumps({
                "sources": [{
                    "id": "recruit-kuaishou-campus",
                    "detail_url_template": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/{id}",
                }],
            }, ensure_ascii=False), encoding="utf-8")

            old_jobs, old_overrides = sweep.JOBS, sweep.OVERRIDES
            try:
                sweep.JOBS = jobs
                sweep.OVERRIDES = overrides
                changed = sweep.enrich_detail_links([{"id": "recruit-kuaishou-campus"}])
            finally:
                sweep.JOBS, sweep.OVERRIDES = old_jobs, old_overrides

            self.assertEqual(changed, 1)
            rows = json.loads(jobs.read_text(encoding="utf-8"))["jobs"]
            self.assertEqual(rows[0]["apply_url"], "https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/12763")
            self.assertEqual(rows[0]["notice_url"], rows[0]["apply_url"])
            self.assertIn("官方职位详情", rows[0]["tags"])
            self.assertEqual(rows[1]["apply_url"], "https://example.com/jobs")

    def test_ignores_unreviewed_or_missing_position_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs.json"
            overrides = root / "overrides.json"
            jobs.write_text(json.dumps({
                "jobs": [{
                    "source": "direct-official:browser:recruit-kuaishou-campus",
                    "company": "快手",
                    "role": "研发工程师",
                    "apply_url": "https://campus.kuaishou.cn/",
                    "notice_url": "https://campus.kuaishou.cn/",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            overrides.write_text(json.dumps({
                "sources": [{
                    "id": "recruit-kuaishou-campus",
                    "detail_url_template": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/{id}",
                }],
            }, ensure_ascii=False), encoding="utf-8")

            old_jobs, old_overrides = sweep.JOBS, sweep.OVERRIDES
            try:
                sweep.JOBS = jobs
                sweep.OVERRIDES = overrides
                self.assertEqual(sweep.enrich_detail_links([{"id": "recruit-kuaishou-campus"}]), 0)
            finally:
                sweep.JOBS, sweep.OVERRIDES = old_jobs, old_overrides


if __name__ == "__main__":
    unittest.main()
