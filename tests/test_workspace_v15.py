import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import workspace_source_refresh as s, recruit_domain_sweep as sweep, user_target_overlay as overlay
ROOT=Path(__file__).resolve().parents[1]
class WorkspaceTests(unittest.TestCase):
    def test_registry(self):
        sources=s.load(s.REGISTRY)['sources']
        self.assertGreaterEqual(len(sources),22)
        self.assertEqual(len(sources),len({x['id'] for x in sources}))
        self.assertTrue({'曦望Sunrise','无问芯穹','思朗科技','墨芯','华为'}.issubset({x['company'] for x in sources}))
        self.assertTrue(all(x['start_url'].startswith('https://') for x in sources))
    def test_supplemental_rotation(self):
        sources=s.load(s.REGISTRY)['sources']
        seen={e['id'] for i in range(4) for e in s.select(sources,i*7200)}
        self.assertEqual(seen,{e['id'] for e in sources})
    def test_existing_sweep_even_shards(self):
        entries=[dict(id=str(i),company=str(i),start_url=f'https://{i}.test/jobs') for i in range(16)]
        seen=set()
        with patch.dict(os.environ,{'PTO_RECRUIT_SWEEP_MAX_TARGETS':'2','PTO_RECRUIT_SWEEP_FORCE_COMPANIES':'','PTO_RECRUIT_SWEEP_SHARD_INDEX':''}):
            for hour in range(1,17,2):
                with patch('scripts.recruit_domain_sweep.time.time',return_value=hour*3600):
                    selected,_=sweep.select(entries);seen.update(x['id'] for x in selected)
        self.assertEqual(len(seen),16)
    def test_failed_refresh_keeps_previous(self):
        old=[dict(i='old',s='one'),dict(i='two',s='two')]
        out,count=s.merge_source(old,[],'one',False)
        self.assertEqual(out,old);self.assertEqual(count,1)
    def test_bounded_success_is_not_a_deletion_signal(self):
        old=[dict(i='old',s='one')]
        out,count=s.merge_source(old,[dict(i='new',s='one')],'one',True)
        self.assertEqual(count,2);self.assertEqual(len(out),2)
    def test_never_promote_announcement(self):
        self.assertFalse(s.valid_job(dict(role='2027工程师招聘正式启动',jd='工程师招聘正式启动 '+ '申请报名 '*30,apply_url='https://x.test')))
        self.assertFalse(s.valid_job(dict(role='AI算子工程师',jd='AI算子工程师',apply_url='https://x.test')))
        self.assertTrue(s.valid_job(dict(role='AI算子工程师',jd='负责算子研发与优化，熟悉CUDA、C++、GPU和高性能计算，有相关实习经验优先。',apply_url='https://x.test')))
    def test_exact_id_no_title_substitution(self):
        job=dict(c='NVIDIA',r='AI Engineer',z='JR20241070')
        self.assertIsNone(overlay.live_match('NVIDIA','北京',dict(title='AI Engineer',position_id='JR2024107'),[job]))
        job['z']='JR2024107'
        self.assertIsNotNone(overlay.live_match('NVIDIA','北京',dict(title='AI Engineer',position_id='JR2024107'),[job]))
        job['s']=overlay.SOURCE
        self.assertIsNone(overlay.live_match('NVIDIA','北京',dict(title='AI Engineer',position_id='JR2024107'),[job]))
    def test_no_public_applied_tiers(self):
        manifest=json.loads((ROOT/'sources/user_target_positions_20260903.json').read_text())
        self.assertFalse(any(r.get('tier')=='applied' for t in manifest['targets'] for r in t['roles']))
    def test_frontend_core(self):
        subprocess.run(['node',str(ROOT/'tests/workspace_v15.mjs')],check=True)
    def test_storage_boundary(self):
        text=(ROOT/'workspace-v15.js').read_text()
        self.assertNotIn('localStorage.clear(',text)
        self.assertNotIn('deleteGithubVault(',text)
        self.assertNotIn('putGithubVault(',text)
        self.assertIn('pto.secure.device-account.v1',text)
        self.assertIn('pto.secure.local.v2.',text)
if __name__=='__main__':unittest.main()
