import unittest

from scripts import kuaishou_public_api_harvester as k


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json, timeout))
        page = int((json or {}).get("pageNum") or 1)
        return FakeResponse({"code": 0, "message": "ok", "result": self.pages[page]})


class KuaishouPublicApiHarvesterTest(unittest.TestCase):
    def config(self):
        return {
            "id": "recruit-kuaishou-campus-2027",
            "company": "快手",
            "adapter": "kuaishou-campus-api",
            "api_project_code": "20271779425607",
            "api_page_size": 2,
            "batch": "2027校园招聘",
            "official_url": "https://campus.kuaishou.cn/",
            "start_url": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs",
            "detail_url_template": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/{id}",
        }

    def test_normalizes_locations_batch_and_detail_link(self):
        row = {
            "id": 13049,
            "name": "AIGC视觉生成算法工程师",
            "description": "负责视觉生成模型研发",
            "positionDemand": "熟悉深度学习",
            "workLocationDicts": [{"name": "北京", "code": "beijing"}, {"name": "深圳", "code": "Shenzhen"}],
            "releaseTime": 1787000000000,
        }
        job = k.normalize_job(self.config(), row)
        self.assertIsNotNone(job)
        self.assertEqual(job["location"], "北京/深圳")
        self.assertEqual(job["batch"], "2027校园招聘")
        self.assertEqual(job["position_id"], "13049")
        self.assertTrue(job["apply_url"].endswith("/13049"))
        self.assertEqual(job["observed_via"], "official-public-api")

    def test_paginates_until_reported_total(self):
        pages = {
            1: {"total": 3, "pages": 2, "pageNum": 1, "pageSize": 2, "list": [
                {"id": 1, "name": "算法工程师", "workLocationDicts": [{"name": "北京"}]},
                {"id": 2, "name": "研发工程师", "workLocationDicts": [{"name": "杭州"}]},
            ]},
            2: {"total": 3, "pages": 2, "pageNum": 2, "pageSize": 2, "list": [
                {"id": 3, "name": "系统工程师", "workLocationDicts": [{"name": "深圳"}]},
            ]},
        }
        session = FakeSession(pages)
        config = self.config()
        config["api_page_size"] = 10
        jobs, diag = k.harvest(config, session=session)
        self.assertEqual(len(jobs), 3)
        self.assertEqual(diag["reported_total"], 3)
        self.assertEqual(diag["pages_read"], 2)
        self.assertTrue(diag["complete"])
        self.assertEqual([call[1]["pageNum"] for call in session.calls], [1, 2])


if __name__ == "__main__":
    unittest.main()
