import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, Mock

from scripts import source_integrity_audit as audit
from scripts.compact_feed import encode_job
from scripts.expand_feed import expand_job
from scripts import workspace_source_refresh as supplemental


class SourceIntegrityTests(unittest.TestCase):
    def test_evidence_survives_round_trip(self):
        job = dict(id='one', company='企业', role='财务管培生', location='上海', source='direct-official:one',
                   source_url='https://employer.example/jobs', apply_url='https://employer.example/jobs/1',
                   jd='负责财务与预算分析。' * 80, position_id='JD001', graduation='2027届',
                   observed_at='2026-10-28T00:00:00Z', observed_via='official-public-api', q=7,
                   verification='detail-observed', deadline='2026-11-10', record_kind='position')
        encoded = encode_job(job)
        self.assertLessEqual(len(encoded['d']), 221)
        self.assertGreater(len(encoded['jd_full']), 220)
        restored = expand_job(encoded)
        for field in ('source', 'source_url', 'position_id', 'observed_at', 'observed_via', 'q', 'verification', 'deadline', 'record_kind'):
            self.assertEqual(restored[field], job[field], field)
        self.assertEqual(restored['jd'], job['jd'])

    def test_non_technical_roles_are_kept(self):
        for role in ('财务管培生', '法务专员', '供应链分析师', '临床研究助理', '人力资源实习生', 'Marketing Graduate'):
            self.assertTrue(supplemental.valid_job(dict(role=role, jd='负责部门专业项目推进、业务分析、跨团队沟通，要求掌握本专业基础知识，能够协作完成任务。', apply_url='https://employer.example/jobs/1')), role)
        self.assertFalse(supplemental.valid_job(dict(role='财务招聘正式启动', jd='本次招聘正式启动，欢迎报名。' * 5, apply_url='https://employer.example/')))

    def test_year_must_describe_cohort_not_fetch_date(self):
        self.assertEqual(audit.cohort(dict(r='财务专员', observed_at='2027-10-01', t='2027-01-01')), 'unknown')
        self.assertEqual(audit.cohort(dict(r='2027 Graduate Programme')), '2027')
        self.assertEqual(audit.cohort(dict(g='2026届')), 'other')

    def test_portal_is_not_promoted_to_a_position(self):
        entry = self.entry()
        rows, status = audit.extract_jobs(entry, '<h1>校园招聘</h1><p>欢迎加入我们。</p>', entry['url'], '2026-10-28T00:00:00Z')
        self.assertEqual(rows, [])
        self.assertEqual(status, 'portal_only')

    def test_portal_year_does_not_label_every_position(self):
        entry = {**self.entry(), 'entry_kind': 'portal', 'cohort': '2027届'}
        row = audit.make_job(entry, '机械研发实习生', '负责机械设计，熟悉 CAD。', entry['url'] + '/1', '2026-10-28')
        self.assertEqual(row['g'], '')
        self.assertNotIn('2027', row['b'])

    def test_extended_requirements_survive_after_old_1800_limit(self):
        text = '实验方法验证与数据分析。' * 250 + '熟悉GMP及HPLC方法开发。'
        original = dict(id='lab', company='药企', role='分析研发实习生', location='上海', source='direct-official:lab', batch='校园招聘', jd=text)
        self.assertEqual(expand_job(encode_job(original))['jd'], text)
        row = audit.make_job(self.entry(), '分析研发实习生', text, 'https://employer.example/job/1', '2026-10-28')
        self.assertEqual(row['jd_full'], text)

    def test_announcement_portal_and_social_share_audit(self):
        rows = [dict(c='企业', r='招聘门户首页', u='https://employer.example/'),
                dict(c='大学', r='2027毕业生双选会邀请函', u='https://university.example/news/1'),
                dict(c='企业', r='分析师', u='https://service.weibo.com/share/share.php?url=https://employer.example'),
                dict(c='药企', r='QC分析师', u='https://employer.example/jobs/share?id=5'),
                dict(c='药企', r='坏链接', u='https://[invalid')]
        report = audit.audit([dict(jobs=rows)], [])
        self.assertEqual(report['summary']['portal_records'], 1)
        self.assertEqual(report['summary']['announcement_records'], 1)
        self.assertEqual(report['summary']['unsafe_share_urls'], 1)
        self.assertEqual(report['summary']['invalid_application_urls'], 1)

    def test_bosch_feed_has_no_unobserved_2027_cohort(self):
        rows = audit.load(audit.VERIFIED).get('jobs', [])
        for row in rows:
            if row.get('s') == 'direct-official:v16:sector-bosch' and row.get('g') == '2027届':
                self.assertRegex(row.get('r', '') + row.get('jd_full', '') + row.get('d', ''), r'2027|27届')

    def test_jsonld_closed_and_off_domain_jobs_are_rejected(self):
        entry = self.entry()
        jobs = [dict(**{'@type': 'JobPosting'}, title='2027 Finance Graduate', description='Financial analysis and accounting.', url=entry['url']+'/1', validThrough='2099-12-01'),
                dict(**{'@type': 'JobPosting'}, title='Expired Finance Graduate', description='Financial analysis.', validThrough='2000-01-01'),
                dict(**{'@type': 'JobPosting'}, title='Wrong employer', description='Financial analysis.', url='https://unrelated.example/jobs/1')]
        html = '<script type="application/ld+json">'+json.dumps(jobs)+'</script>'
        rows, _ = audit.extract_jobs(entry, html, entry['url'], '2026-10-28T00:00:00Z')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['g'], '')
        self.assertEqual(rows[0]['b'], '2027招聘项目')
        self.assertEqual(audit.extract_jobs(entry, '<h1>职位已关闭</h1>'+html, entry['url'], '2026-10-28T00:00:00Z'), ([], 'closed'))

    def test_campaign_requires_observed_role_and_application_host(self):
        entry = {**self.entry(), 'role_sections': ['信息技术类', '综合管理类'], 'application_url': 'https://apply.example/jobs', 'cohort': '2027届'}
        html = '<h1>2027校园招聘</h1><p>[信息技术类] 工作职责：'+('系统开发与维护，计算机相关专业。'*8)+'</p><p>申请入口 apply.example</p>'
        rows, _ = audit.extract_jobs(entry, html, entry['url'], '2026-10-28T00:00:00Z')
        self.assertEqual([r['r'] for r in rows], ['信息技术类'])
        self.assertEqual(audit.extract_jobs(entry, html.replace('apply.example', 'different.example'), entry['url'], '2026-10-28T00:00:00Z')[0], [])

    def test_audit_does_not_treat_generation_date_as_observation(self):
        feeds = [dict(generated_at='2026-10-28', jobs=[dict(c='企业', r='财务管培生', g='2027届', u='https://example.com/1'),
                 dict(c='企业', r='旧职位', u='javascript:alert(1)', observed_at='2026-01-01', deadline='2026-02-01')])]
        report = audit.audit(feeds, [], '2026-10-28T00:00:00Z')['summary']
        self.assertEqual(report['observation_unknown'], 1)
        self.assertEqual(report['observed_within_30_days'], 0)
        self.assertEqual(report['closed_or_expired'], 1)
        self.assertEqual(report['invalid_application_urls'], 1)

    def test_soft_404_is_not_a_healthy_portal(self):
        response = Mock(status_code=200, url='https://employer.example/404?errorpath=campus', text='<title>404</title>', apparent_encoding='utf-8')
        with patch.object(audit.requests, 'get', return_value=response):
            result, rows = audit.check_entry({**self.entry(), 'evidence_url': 'https://employer.example/'})
        self.assertEqual(result['status'], 'not_found')
        self.assertFalse(result['reachable'])
        self.assertEqual(rows, [])

    def test_date_only_deadline_includes_that_day(self):
        self.assertFalse(audit.expired('2026-10-28', datetime(2026, 10, 28, 16, tzinfo=timezone.utc)))
        self.assertTrue(audit.expired('2026-10-28', datetime(2026, 10, 29, tzinfo=timezone.utc)))

    def test_directory_covers_multiple_sectors_and_company_types(self):
        entries = audit.load(audit.REGISTRY)['sources']
        self.assertEqual(len(entries), len({e['id'] for e in entries}))
        self.assertGreaterEqual(len({e['industry'] for e in entries}), 15)
        self.assertTrue({'中央企业', '国有企业', '外资企业', '民营企业', '初创企业'}.issubset({e['company_type'] for e in entries}))
        self.assertTrue(all(audit.safe_url(e['url']) and audit.safe_url(e['evidence_url']) for e in entries))

    def test_failed_refresh_keeps_cache_but_not_healthy_status(self):
        from scripts.priority_direct_feed import record_special_source
        old = [dict(i='old', s='direct-official:test', observed_at='2026-01-01')]
        fresh, runs = {}, []
        def fail():
            raise RuntimeError('upstream unavailable')
        record_special_source(source_id='direct-official:test', name='test', label='Test', url='https://employer.example',
                              collector=fail, old_by_source={'direct-official:test': old}, fresh_by_source=fresh, source_runs=runs)
        self.assertEqual(fresh['direct-official:test'], old)
        self.assertFalse(runs[0]['ok'])
        self.assertTrue(runs[0]['preserved_previous'])
        self.assertEqual(runs[0]['fresh_count'], 0)

    @staticmethod
    def entry():
        return dict(id='test', company='企业', company_type='民营企业', industry='金融', url='https://employer.example/jobs', entry_kind='portal', cohort='待官网确认')


if __name__ == '__main__':
    unittest.main()
