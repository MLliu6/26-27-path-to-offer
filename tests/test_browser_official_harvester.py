from __future__ import annotations

import unittest

from scripts import browser_official_harvester as harvester


SOURCE={
    "id":"didi",
    "company":"滴滴",
    "company_type":"民营/互联网/出行",
    "start_urls":["https://talent.didiglobal.com/"],
    "allowed_hosts":["talent.didiglobal.com"],
}


class BrowserOfficialHarvesterTest(unittest.TestCase):
    def test_walk_json_recognizes_diverse_job_rows(self):
        payload={
            "data":{
                "records":[
                    {
                        "positionId":"didi-ai-1",
                        "positionName":"大模型推理基础设施工程师",
                        "cityName":"北京",
                        "departmentName":"自动驾驶与AI",
                        "description":"负责分布式训练、在线推理平台和GPU集群调度。",
                        "requirement":"熟悉vLLM、CUDA、RDMA、C++与Python。",
                        "detailUrl":"/jobs/didi-ai-1",
                        "recruitTypeName":"2027校园招聘",
                        "graduationYear":"2027",
                    },
                    {
                        "jobId":"didi-product-1",
                        "jobTitle":"产品经理",
                        "location":"北京",
                        "jobDescription":"负责用户研究、产品规划与跨团队协作。",
                        "qualifications":"逻辑清晰，具备数据分析能力。",
                        "jobUrl":"https://talent.didiglobal.com/jobs/didi-product-1",
                        "batch":"公开招聘",
                    },
                    {"job":"technology","jobName":"技术"},
                ]
            }
        }
        jobs={}
        harvester.walk_json(payload,SOURCE,"https://talent.didiglobal.com/jobs","https://talent.didiglobal.com/api/jobs",jobs)
        self.assertEqual(len(jobs),2)
        roles={row["role"] for row in jobs.values()}
        self.assertIn("大模型推理基础设施工程师",roles)
        self.assertIn("产品经理",roles)
        ai=next(row for row in jobs.values() if row["role"].startswith("大模型"))
        self.assertEqual(ai["company"],"滴滴")
        self.assertEqual(ai["location"],"北京")
        self.assertEqual(ai["graduation"],"2027届")
        self.assertIn("vLLM",ai["jd"])
        self.assertTrue(ai["apply_url"].endswith("/jobs/didi-ai-1"))
        self.assertEqual(ai["source"],"direct-official:browser:didi")

    def test_merge_replaces_only_successful_source(self):
        old_didi={"source":"direct-official:browser:didi","company":"滴滴","role":"旧岗位","location":"北京","apply_url":"https://old"}
        old_galbot={"source":"direct-official:browser:galbot","company":"银河通用","role":"保留岗位","location":"北京","apply_url":"https://keep"}
        fresh={
            "direct-official:browser:didi":[{
                "source":"direct-official:browser:didi","company":"滴滴","role":"新岗位","location":"北京","apply_url":"https://new"
            }],
            "direct-official:browser:galbot":[],
        }
        merged=harvester.merge_catalog([old_didi,old_galbot],fresh,{"direct-official:browser:didi"})
        roles={row["role"] for row in merged}
        self.assertNotIn("旧岗位",roles)
        self.assertIn("新岗位",roles)
        self.assertIn("保留岗位",roles)

    def test_priority_sources_are_always_selected(self):
        config={"sources_per_run":4,"sources":[
            {"id":"didi","company":"滴滴","always":True,"start_urls":["https://a"]},
            {"id":"galbot","company":"银河通用","always":True,"start_urls":["https://b"]},
            {"id":"one","company":"一","start_urls":["https://c"]},
            {"id":"two","company":"二","start_urls":["https://d"]},
            {"id":"three","company":"三","start_urls":["https://e"]},
        ]}
        selected=harvester.selected_sources(config)
        ids={row["id"] for row in selected}
        self.assertIn("didi",ids)
        self.assertIn("galbot",ids)
        self.assertEqual(len(selected),4)


if __name__=="__main__":
    unittest.main()
