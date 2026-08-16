from __future__ import annotations

import unittest

from scripts.compact_feed import encode_job, encode_jobs, compact_text, clean_status


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

    def test_retired_scraper_health_is_removed(self):
        status={'sources':[
            {'name':'offerjack','ok':False},
            {'name':'gank-public-search','ok':False},
            {'name':'china-official-federation','ok':True},
            {'name':'gankinterview-state','ok':True},
        ]}
        cleaned=clean_status(status)
        names=[s['name'] for s in cleaned['sources']]
        self.assertEqual(names,['china-official-federation','gankinterview-state'])
        self.assertEqual(cleaned['retired_sources'],['gank-public-search','offerjack'])

    def test_final_transport_enforces_row_cap(self):
        jobs=[{'id':str(i),'company':f'企业{i}','role':'工程师'} for i in range(5)]
        rows=encode_jobs(jobs,max_rows=3)
        self.assertEqual(len(rows),3)
        self.assertEqual([x['c'] for x in rows],['企业0','企业1','企业2'])


if __name__=='__main__':
    unittest.main()
