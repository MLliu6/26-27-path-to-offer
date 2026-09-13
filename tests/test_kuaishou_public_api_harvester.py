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
    def campus_config(self):
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

    def social_config(self):
        return {
            "id": "recruit-kuaishou-social",
            "company": "快手",
            "adapter": "kuaishou-experienced-browser",
            "position_nature_code": "C001",
            "route_fragment": "official/social",
            "batch": "社会招聘",
            "official_url": "https://zhaopin.kuaishou.cn/",
            "start_url": "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/?pageNum=1",
            "detail_url_template": "https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/{id}",
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
        job = k.normalize_job(self.campus_config(), row)
        self.assertIsNotNone(job)
        self.assertEqual(job["location"], "北京/深圳")
        self.assertEqual(job["batch"], "2027校园招聘")
        self.assertEqual(job["position_id"], "13049")
        self.assertTrue(job["apply_url"].endswith("/13049"))
        self.assertEqual(job["observed_via"], "official-public-api")

    def test_normalizes_experienced_browser_row(self):
        row = {
            "id": 8476,
            "name": "机器学习架构工程师-【国际化】",
            "description": "负责机器学习系统架构",
            "positionDemand": "熟悉分布式系统",
            "workLocationCode": "Beijing",
        }
        job = k.normalize_job(self.social_config(), row, transport="official-browser-ui-xhr")
        self.assertEqual(job["location"], "北京")
        self.assertEqual(job["batch"], "社会招聘")
        self.assertEqual(job["observed_via"], "official-browser-ui-xhr")
        self.assertIn("真实浏览器公开XHR", job["tags"])
        self.assertTrue(job["apply_url"].endswith("/8476"))
        self.assertEqual(job["source"], "direct-official:browser:recruit-kuaishou-social")

    def test_experienced_hash_never_adds_private_state(self):
        self.assertEqual(k.experienced_hash("official/social", 50), "/official/social/?pageNum=50")
        self.assertEqual(k.experienced_hash("/official/trainee/", 111), "/official/trainee/?pageNum=111")
        value = k.experienced_hash("official/trainee", 2)
        self.assertNotIn("cookie", value.lower())
        self.assertNotIn("token", value.lower())
        self.assertNotIn("workLocationCode", value)

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
        config = self.campus_config()
        config["api_page_size"] = 10
        jobs, diag = k.harvest(config, session=session)
        self.assertEqual(len(jobs), 3)
        self.assertEqual(diag["reported_total"], 3)
        self.assertEqual(diag["pages_read"], 2)
        self.assertTrue(diag["complete"])
        self.assertEqual(diag["coverage_ratio"], 1.0)
        self.assertEqual([call[1]["pageNum"] for call in session.calls], [1, 2])


if __name__ == "__main__":
    unittest.main()
