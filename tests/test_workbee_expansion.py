import unittest
from datetime import datetime,timedelta,timezone
from hives.careers.api import Search,search_catalog
from hives.careers.opportunity_facts import facts
from hives.careers.matching import Profile,match


def job(id,title,text,company='Example'):
    return {'id':id,'title':title,'description':text,'company':company,'role_type':'internship','location':'','source':'greenhouse'}

class ExpandedDiscoveryTests(unittest.TestCase):
    def test_nontech_discovery_and_independent_fields_and_industries(self):
        rows=[job('1','Marketing Intern','Requirements\nCopywriting required','Oscar Health'),job('2','Teacher','Requirements\nClassroom management required','Achievement First'),job('3','Software Intern','Python')]
        data={'jobs':rows,'boards':[]}
        broad=search_catalog(data,Search(role_type='all'))
        self.assertEqual(broad['total'],3)
        self.assertEqual(search_catalog(data,Search(technical_only=True,role_type='all'))['total'],1)
        chosen=search_catalog(data,Search(role_type='all',career_fields=['marketing'],sectors=['health_it']))
        self.assertEqual([j['id'] for j in chosen['jobs']],['1'])
        self.assertEqual(next(f['count'] for f in chosen['facets']['fields'] if f['value']=='marketing'),1)
    def test_pay_does_not_infer_from_benefits_or_budgets(self):
        self.assertEqual(facts('Intern','Paid time off and a $5,000 research budget')['pay_status'],'unknown')
        self.assertEqual(facts('Intern','Internships are unpaid.')['pay_status'],'unpaid')
        self.assertEqual(facts('Intern','This is a paid internship.')['pay_status'],'paid')
        self.assertTrue(facts('Intern','Hourly compensation: $22 per hour.')['pay_disclosed'])
        self.assertEqual(facts('Intern','This unpaid internship has a salary of $20 per hour.')['pay_status'],'unknown')
    def test_practical_filters_and_facets_agree(self):
        now=datetime.now(timezone.utc)
        rows=[job('paid','Policy Intern','Part-time paid internship.\nRequirements\nPolicy analysis required'),job('unpaid','Policy Intern','Full-time unpaid internship.'),job('unknown','Policy Intern','Paid time off.')]
        rows[0]['first_seen']=now.isoformat()
        rows[0]['deadline_info']={'date':(now+timedelta(days=3)).date().isoformat(),'at':None,'source':'employer_field'}
        rows[1]['first_seen']=(now-timedelta(days=20)).isoformat()
        result=search_catalog({'jobs':rows,'boards':[]},Search(pay='paid',commitments=['part_time'],recent_days=7,closing_within_days=7))
        self.assertEqual([j['id'] for j in result['jobs']],['paid'])
        self.assertEqual(sum(f['count'] for f in result['facets']['fields']),1)
    def test_nontechnical_skills_have_explained_coverage(self):
        result=match(job('1','Policy Intern','Requirements\nPolicy analysis and qualitative research required'),Profile(skills='Policy analysis | Analyzed a policy project'))
        self.assertEqual(result['score'],50)
        self.assertIn('Qualitative research',result['breakdown']['missing_required'])


class CachedAvailabilityTests(unittest.TestCase):
    def test_paused_collection_keeps_last_known_open_without_claiming_current(self):
        now=datetime.now(timezone.utc)
        cached={**job('cached','Marketing Intern',''), 'board':'example','last_seen':(now-timedelta(hours=2)).isoformat()}
        ancient={**cached,'id':'ancient','last_seen':(now-timedelta(days=8)).isoformat()}
        expired={**cached,'id':'expired','deadline_info':{'date':(now-timedelta(days=1)).date().isoformat(),'at':None}}
        data={'jobs':[cached,ancient,expired],'boards':[{'key':'greenhouse:example','error':None}]}
        self.assertEqual(search_catalog(data,Search(current_only=True))['total'],0)
        result=search_catalog(data,Search(current_only=True,include_stale=True))
        self.assertEqual([j['id'] for j in result['jobs']],['cached'])
        self.assertTrue(result['jobs'][0]['needs_recheck'])
        self.assertEqual(result['jobs'][0]['availability']['state'],'stale')
        self.assertEqual(result['needs_recheck_total'],1)
    def test_old_removal_stays_excluded_until_a_new_source_snapshot(self):
        now=datetime.now(timezone.utc)
        removed={**job('removed','Policy Intern',''), 'board':'example','last_seen':(now-timedelta(hours=3)).isoformat(),'verification':{'state':'removed','checked_at':(now-timedelta(hours=2)).isoformat()}}
        data={'jobs':[removed],'boards':[{'key':'greenhouse:example','error':None}]}
        self.assertEqual(search_catalog(data,Search(current_only=True,include_stale=True))['total'],0)
        data['jobs']=[{**removed,'last_seen':(now-timedelta(hours=1)).isoformat()}]
        self.assertEqual(search_catalog(data,Search(current_only=True,include_stale=True))['total'],1)
