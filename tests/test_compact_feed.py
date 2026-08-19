from __future__ import annotations

import unittest

from scripts.compact_feed import encode_job, encode_jobs, compact_text, clean_status, is_domestic, domestic_priority


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

    def test_browser_direct_job_survives_china_first_compaction(self):
        job={
            'id':'mthreads:abc-123',
            'company':'摩尔线程',
            'role':'GPU软件研发工程师',
            'location':'北京',
            'apply_url':'https://mthreads.zhiye.com/campus/detail?jobAdId=abc-123',
            'notice_url':'https://mthreads.zhiye.com/campus/detail?jobAdId=abc-123',
            'jd':'GPU 软件栈 CUDA 编译器 runtime 性能优化',
            'updated_at':'2026-08-19',
            'source':'direct-official:browser:mthreads',
            'source_label':'摩尔线程招聘官网 · 浏览器自主直连',
            'company_type':'民营/GPU/AI芯片',
            'batch':'校园招聘',
        }
        self.assertTrue(is_domestic(job))
        self.assertLess(domestic_priority(job)[0], -140)
        row=encode_job(job)
        self.assertEqual(row['c'],'摩尔线程')
        self.assertEqual(row['q'],7)
        self.assertEqual(row['u'],'https://mthreads.zhiye.com/campus/detail?jobAdId=abc-123')
        self.assertIn('招聘官网',row['x'])

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
