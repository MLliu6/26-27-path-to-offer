import unittest

from scripts.merge_public_tables import parse_table_source


class PublicTableParsingTests(unittest.TestCase):
    def test_offer_style_chinese_table_maps_to_canonical_job(self):
        html = '''
        <table>
          <thead><tr>
            <th>公司名称</th><th>企业性质</th><th>行业</th><th>招聘批次</th>
            <th>毕业年份</th><th>工作地点</th><th>岗位</th><th>更新时间</th><th>投递链接</th><th>公告链接</th>
          </tr></thead>
          <tbody><tr>
            <td>京东JD</td><td>民营企业</td><td>互联网/人工智能</td><td>秋招</td>
            <td>2027届</td><td>北京</td><td>AI Infra / 大模型推理工程师</td><td>2026-07-28</td>
            <td><a href="https://zhaopin.jd.com/">投递</a></td><td><a href="https://example.org/jd">公告</a></td>
          </tr></tbody>
        </table>'''
        jobs = parse_table_source(html, name='fixture', label='fixture', url='https://example.org/jobs')
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job['company'], '京东JD')
        self.assertEqual(job['role'], 'AI Infra / 大模型推理工程师')
        self.assertEqual(job['location'], '北京')
        self.assertEqual(job['graduation'], '2027届')
        self.assertEqual(job['apply_url'], 'https://zhaopin.jd.com/')
        self.assertEqual(job['notice_url'], 'https://example.org/jd')


if __name__ == '__main__':
    unittest.main()
