from __future__ import annotations

import unittest

from scripts.compact_feed import encode_job, compact_text


class CompactFeedTests(unittest.TestCase):
    def test_verbose_job_encodes_to_short_transport_keys(self):
        job={
            'id':'abc','company':'京东','role':'大模型推理系统工程师','location':'北京',
            'apply_url':'https://zhaopin.jd.com/job/1','jd':'vLLM CUDA KV Cache '*100,
            'updated_at':'2026-08-16','source':'china-official:jd','source_label':'官方招聘 · 京东',
            'department':'基础架构','batch':'校招'
        }
        row=encode_job(job)
        self.assertEqual(row['c'],'京东')
        self.assertEqual(row['r'],'大模型推理系统工程师')
        self.assertEqual(row['x'],'中国企业官方招聘')
        self.assertIn('u',row)
        self.assertNotIn('company',row)
        self.assertLessEqual(len(row['d']),221)

    def test_compact_encoding_is_idempotent(self):
        row={'i':'1','c':'腾讯','r':'后台开发','d':'Python '*200,'x':'中国企业官方招聘'}
        encoded=encode_job(row)
        self.assertEqual(encoded['c'],'腾讯')
        self.assertLessEqual(len(encoded['d']),221)

    def test_preview_collapses_whitespace(self):
        self.assertEqual(compact_text('  CUDA\n\n GEMM   Tensor Core ',100),'CUDA GEMM Tensor Core')


if __name__=='__main__':
    unittest.main()
