from __future__ import annotations

import unittest

from scripts.compact_feed import encode_job
from scripts.expand_feed import expand_job, expand_payload


class ExpandFeedTests(unittest.TestCase):
    def test_compact_round_trip_preserves_retrieval_fields(self):
        original={
            'id':'jd-1','company':'京东','role':'大模型推理系统工程师','location':'北京',
            'apply_url':'https://zhaopin.jd.com/job/1','notice_url':'https://zhaopin.jd.com/',
            'jd':'vLLM CUDA KV Cache','updated_at':'2026-08-16','batch':'校招',
            'graduation':'2027届','education':'硕士','salary':'','company_type':'民营企业',
            'industry':'互联网','department':'基础架构','source':'china-official:jd','source_label':'官方招聘 · 京东'
        }
        compact=encode_job(original)
        restored=expand_job(compact)
        self.assertEqual(restored['id'],'jd-1')
        self.assertEqual(restored['company'],'京东')
        self.assertEqual(restored['role'],'大模型推理系统工程师')
        self.assertEqual(restored['apply_url'],'https://zhaopin.jd.com/job/1')
        self.assertEqual(restored['jd'],'vLLM CUDA KV Cache')
        self.assertEqual(restored['source_label'],'中国企业官方招聘')

    def test_verbose_rows_are_already_readable(self):
        row={'company':'腾讯','role':'后台开发','id':'1'}
        self.assertEqual(expand_job(row),row)

    def test_payload_returns_crawler_schema(self):
        payload={'schema_version':4,'generated_at':'x','jobs':[{'i':'1','c':'字节跳动','r':'算法工程师','u':'https://jobs.bytedance.com/1','x':'中国企业官方招聘'}]}
        restored=expand_payload(payload)
        self.assertEqual(restored['schema_version'],3)
        self.assertEqual(restored['jobs'][0]['company'],'字节跳动')
        self.assertEqual(restored['jobs'][0]['apply_url'],'https://jobs.bytedance.com/1')


if __name__=='__main__':
    unittest.main()
