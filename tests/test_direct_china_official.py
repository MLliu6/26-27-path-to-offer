from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import direct_china_official as direct


class DirectChinaOfficialTests(unittest.TestCase):
    def test_meituan_official_page_normalizes_campus_job(self):
        payload={'data':{'page':{'totalCount':1},'list':[{
            'name':'大模型推理引擎研发工程师','jobUnionId':123456,'cityList':[{'name':'北京市'}],
            'department':[{'name':'LongCat大模型'}],'jobFamily':'技术','jobDuty':'负责大模型推理服务、KV Cache和调度优化',
            'jobRequirement':'熟悉CUDA、vLLM、C++','refreshTime':1786809600000,
        }]}}
        cfg={'company':'美团','job_type_codes':['1'],'max_pages':1,'page_size':100,'official_url':'https://zhaopin.meituan.com/web/campus'}
        with patch.object(direct,'session',return_value=object()), patch.object(direct,'request_json',return_value=payload): rows,diag=direct.meituan(cfg)
        self.assertEqual(len(rows),1); job=rows[0]
        self.assertEqual(job['company'],'美团'); self.assertEqual(job['batch'],'校园招聘'); self.assertIn('北京',job['location']); self.assertIn('vLLM',job['jd'])
        self.assertTrue(job['source'].startswith('direct-official:meituan')); self.assertIn('zhaopin.meituan.com/web/position/detail',job['apply_url']); self.assertEqual(diag['unique_jobs'],1)

    def test_meituan_code2_is_intern_campus_special(self):
        payload={'data':{'page':{'totalCount':1},'list':[{'name':'大模型算法实习生','jobUnionId':'intern-1','cityList':[{'name':'北京'}],'department':[{'name':'基础模型'}],'jobDuty':'多模态训练','jobRequirement':'PyTorch CUDA'}]}}
        cfg={'company':'美团','job_type_codes':['2'],'max_pages':1,'page_size':100}
        with patch.object(direct,'session',return_value=object()), patch.object(direct,'request_json',return_value=payload): rows,_=direct.meituan(cfg)
        self.assertEqual(rows[0]['batch'],'实习/校园专项')

    def test_bytedance_campus_and_intern_use_distinct_recruitment_ids(self):
        calls=[]
        def fake(_s,_method,_url,**kwargs):
            rid=kwargs['json']['recruitment_id_list'][0]; calls.append(rid)
            return {'data':{'count':1,'job_post_list':[{
                'id':f'bd-{rid}','title':'大模型系统工程师' if rid=='201' else '大模型系统实习生',
                'city_info':{'name':'北京'},'job_category':{'name':'研发/R&D'},
                'description':'负责推理系统与分布式服务','requirement':'CUDA C++ vLLM',
                'recruit_type':{'name':'正式' if rid=='201' else '实习'},'publish_time':1786809600000,
            }]}}
        cfg={'company':'字节跳动','scopes':['campus','intern'],'max_pages':1,'page_size':100,'official_url':'https://jobs.bytedance.com/campus/position'}
        with patch.object(direct,'session',return_value=object()), patch.object(direct,'request_json',side_effect=fake): rows,diag=direct.bytedance(cfg)
        self.assertEqual(calls,['201','202']); self.assertEqual(len(rows),2)
        self.assertEqual({x['batch'] for x in rows},{'校园招聘','实习招聘'})
        self.assertTrue(all(x['source']=='direct-official:bytedance' for x in rows)); self.assertTrue(all('jobs.bytedance.com/campus/position/' in x['apply_url'] for x in rows))
        self.assertEqual(diag['scope_counts']['campus']['recruitment_id'],'201'); self.assertEqual(diag['scope_counts']['intern']['recruitment_id'],'202')

    def test_tencent_public_api_normalizes_direct_link(self):
        payload={'Data':{'Count':1,'Posts':[{
            'RecruitPostName':'大模型后台开发工程师','PostId':'tx-1','CountryName':'中国','LocationName':'北京','BGName':'TEG',
            'CategoryName':'技术','Responsibility':'大模型推理平台和服务','Requirement':'C++ CUDA 分布式系统','LastUpdateTime':'2026年08月17日'
        }]}}
        cfg={'company':'腾讯','max_pages':1,'page_size':100,'official_url':'https://careers.tencent.com/search.html'}
        with patch.object(direct,'session',return_value=object()), patch.object(direct,'request_json',return_value=payload): rows,diag=direct.tencent(cfg)
        self.assertEqual(len(rows),1); job=rows[0]
        self.assertEqual(job['company'],'腾讯'); self.assertIn('北京',job['location']); self.assertIn('CUDA',job['jd']); self.assertIn('careers.tencent.com/jobdesc.html',job['apply_url']); self.assertEqual(diag['unique_jobs'],1)

    def test_direct_rows_survive_merge_and_replace_same_identity(self):
        base={'company':'美团','role':'大模型推理','location':'北京','apply_url':'https://x/1','source':'third-party','jd':'short'}
        direct_job={**base,'source':'direct-official:meituan','source_label':'美团校园招聘官网','jd':'official rich jd'}
        rows=direct.merge_catalog([base],[direct_job])
        self.assertEqual(len(rows),1); self.assertEqual(rows[0]['source'],'direct-official:meituan'); self.assertEqual(rows[0]['jd'],'official rich jd')


if __name__=='__main__': unittest.main()
