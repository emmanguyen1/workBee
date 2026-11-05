import unittest
from datetime import datetime,timezone
from hives.careers.sectors import technical_role,sector_tags
from hives.careers.api import Search,search_catalog
from hives.careers.accounts import Preferences

class TechSectorTests(unittest.TestCase):
    def test_sector_does_not_make_a_non_tech_role_technical(self):
        for title in ['Registered Nurse','Technical Recruiter','Account Executive','Care Coordinator','Marketing Manager','Finance Manager','Business Operations Manager']:
            self.assertFalse(technical_role({'title':title,'company':'Commure','description':''})[0],title)
        for title in ['Clinical Informatics Analyst','Software Engineer','Business Systems Analyst','Avionics Engineer','Security Engineer','Machine Learning Scientist','IT Support Specialist']:
            self.assertTrue(technical_role({'title':title,'company':'Example','description':''})[0],title)
        self.assertTrue(technical_role({'title':'Business Analyst','description':'Requirements\nSQL required'})[0])
        self.assertFalse(technical_role({'title':'Business Analyst','description':'You will collaborate with software engineers.'})[0])

    def test_multiple_technical_sectors_with_current_postings(self):
        def job(id,title,company):return {'id':id,'title':title,'company':company,'source':'greenhouse','board':'test','location':'Boston, MA','description':'','role_type':'other','last_seen':datetime.now(timezone.utc).isoformat()}
        jobs=[job('health','Software Engineer','Commure'),job('clinical','Registered Nurse','Commure'),job('space','Avionics Engineer','SpaceX'),job('finance','Software Engineer','Stripe'),job('business','Business Systems Analyst','Gusto')]
        result=search_catalog({'jobs':jobs,'boards':[]},Search(current_only=True,technical_only=True,role_type='all',sectors=['health_it','aerospace']))
        self.assertEqual({j['id'] for j in result['jobs']},{'health','space'})
        self.assertTrue(all('technical_evidence' in j for j in result['jobs']))
        counts={s['value']:s['count'] for s in result['facets']['sectors']}
        self.assertEqual(counts['health_it'],1)
        self.assertEqual(counts['aerospace'],1)
        self.assertEqual(counts['fintech'],1)
        self.assertEqual(Preferences(sectors=['health_it','aerospace']).sectors,['health_it','aerospace'])
        self.assertIn('health_it',sector_tags(jobs[0]))
        self.assertIn('business_systems',sector_tags(jobs[-1]))
