import unittest

from scripts.aggregate_jobs import dedupe, parse_offerjack_tables, stable_id


HTML = '''
<html><body><table>
<tr><th>更新时间</th><th>企业名称</th><th>招聘批次</th><th>企业性质</th><th>行业</th><th>工作地点</th><th>职位</th><th>毕业年份</th><th>学历</th><th>公告链接</th><th>投递地址</th></tr>
<tr><td>2026-08-14</td><td>真实企业A</td><td>秋招</td><td>民企</td><td>人工智能</td><td>北京</td><td>AI Infra 工程师</td><td>2027</td><td>硕士</td><td><a href="/notice/1">公告</a></td><td><a href="https://careers.example.com/a">投递</a></td></tr>
</table></body></html>
'''


class AggregateJobsTest(unittest.TestCase):
    def test_public_table_normalization(self):
        jobs = parse_offerjack_tables(HTML, 'https://www.offerjack.cn/')
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job['company'], '真实企业A')
        self.assertEqual(job['role'], 'AI Infra 工程师')
        self.assertEqual(job['location'], '北京')
        self.assertEqual(job['education'], '硕士')
        self.assertEqual(job['notice_url'], 'https://www.offerjack.cn/notice/1')
        self.assertEqual(job['apply_url'], 'https://careers.example.com/a')
        self.assertTrue(job['id'])

    def test_dedupe_prefers_richer_jd(self):
        key = stable_id('x', 'a', 'b', 'c')
        thin = {'id': key, 'jd': 'short'}
        rich = {'id': key, 'jd': 'much richer job description'}
        self.assertEqual(dedupe([thin, rich])[0]['jd'], rich['jd'])


if __name__ == '__main__':
    unittest.main()
