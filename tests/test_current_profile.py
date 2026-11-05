import unittest
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from hives.careers.app import app
from hives.careers.api import Search,search_catalog
from hives.careers.resume import build_draft
from hives.careers.matching import Profile,match

class CurrentProfileTests(unittest.TestCase):
    def test_current_search_excludes_archives_failed_stale_and_community(self):
        now=datetime.now(timezone.utc)
        base={'title':'Software Intern','role_type':'internship','company':'Example','location':'Boston, MA','description':'First-year undergraduate students may apply.','source':'greenhouse','board':'example','last_seen':now.isoformat()}
        jobs=[{**base,'id':'fresh'},{**base,'id':'stale','last_seen':(now-timedelta(hours=2)).isoformat()},{**base,'id':'community','source':'simplify'},{**base,'id':'removed','open':False},{**base,'id':'failed','board':'failed'}]
        data={'jobs':jobs,'boards':[{'key':'greenhouse:failed','error':'Timeout'}]}
        result=search_catalog(data,Search(current_only=True,include_programs=True,role_type='all'))
        self.assertEqual([j['id'] for j in result['jobs']],['fresh'])
        self.assertEqual(result['program_total'],0)
        self.assertEqual(sum(f['count'] for f in result['facets']['fields']),1)
        targeted=search_catalog(data,Search(current_only=True,opportunity_type='program',role_type='all'))
        self.assertEqual(targeted['total'],1)
        # The cached classification list must not mark unrelated roles as first-year.
        plain={**base,'id':'plain','description':'Software development experience.'}
        self.assertEqual(search_catalog({'jobs':[plain],'boards':[]},Search(current_only=True,opportunity_type='program'))['total'],0)

    def test_resume_prefers_project_evidence_and_skips_unsupported_learning(self):
        text='Education\nBachelor of Science in Computer Science, class of 2029\nSkills: Python, SQL, Canva\nBuilt a Python and SQL project serving 200 users.\nCurrently learning TensorFlow\nNo experience with Kubernetes\nDesigned Canva posters for a student event.'
        result=build_draft(text);skills={s['skill']:s['evidence'] for s in result['draft']['skills']}
        self.assertIn('Built a Python',skills['Python'])
        self.assertIn('Canva',skills)
        self.assertNotIn('TensorFlow',skills)
        self.assertNotIn('Kubernetes',skills)
        self.assertEqual(result['draft']['graduation_year'],2029)
        self.assertGreaterEqual(result['summary']['with_examples'],3)
        self.assertTrue(any('Skipped' in w for w in result['warnings']))
        self.assertIsNone(result['draft']['needs_sponsorship'])

    def test_equal_skill_coverage_prefers_supporting_examples(self):
        result=search_catalog({'jobs':[{'id':'python','title':'Software Intern','role_type':'internship','company':'Example','location':'','description':'Requirements\nPython required'},{'id':'react','title':'Frontend Intern','role_type':'internship','company':'Example','location':'','description':'Requirements\nReact required'}],'boards':[]},Search(profile=Profile(skills='Python | Skills list\nReact | Built a student website')))
        self.assertEqual([j['id'] for j in result['jobs']],['react','python'])
        self.assertEqual(result['jobs'][0]['match']['score'],100)
        self.assertEqual(result['jobs'][1]['match']['breakdown']['self_reported'],1)

    def test_simple_search_and_visible_profile_controls(self):
        with TestClient(app) as c:
            page=c.get('/').text
            for id in ['account-toggle','display-name','profile-school','profile-tagline','resume-apply-mode']:
                self.assertIn('id="'+id+'"',page)
            self.assertEqual(page.count('class="selection-note"'),1)
            self.assertEqual(page.count('class="multi-filter"'),7)
            self.assertNotIn('Class-year wording',page)
            self.assertNotIn('Program guide status',page)
