import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from hives.careers.app import app
from hives.careers.programs import program_catalog, student_years, program_jobs
from hives.careers.api import Search, search_catalog


class ProgramTests(unittest.TestCase):
    def test_researched_windows_expiry_and_stale_sources(self):
        now=datetime(2026,11,5,tzinfo=timezone.utc)
        rows={p['id']:p for p in program_catalog(now)}
        self.assertEqual(rows['program:nvidia-ignite']['status'],'closed')
        self.assertEqual(rows['program:nreip']['status'],'application_window')
        self.assertEqual(rows['program:doe-suli']['status'],'application_window')
        self.assertEqual(rows['program:jane-street-fttp']['status'],'notify_only')
        self.assertEqual(rows['program:microsoft-explore']['status'],'check_postings')
        self.assertEqual(rows['program:microsoft-discovery']['years'],[0])
        future={p['id']:p for p in program_catalog(datetime(2026,12,15,tzinfo=timezone.utc))}
        self.assertEqual(future['program:nreip']['status'],'closed')
        self.assertEqual(future['program:doe-suli']['status'],'needs_review')
        end={p['id']:p for p in program_catalog(datetime(2027,1,6,22,1,tzinfo=timezone.utc))}
        self.assertEqual(end['program:doe-suli']['status'],'closed')

    def test_programs_have_official_links_and_separate_ids(self):
        with TestClient(app) as client:
            r=client.get('/api/careers/programs');self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers['cache-control'],'no-store')
            rows=r.json()['programs'];self.assertEqual(len(rows),7)
            self.assertEqual(len({p['id'] for p in rows}),len(rows))
            for p in rows:
                self.assertTrue(p['source_url'].startswith('https://'))
                self.assertTrue(p['id'].startswith('program:'))
                self.assertTrue(p['eligibility'])
                self.assertIsNotNone(p['company_logo_url'])
            self.assertEqual(client.get('/careers/assets/workbee-logo.png').headers['content-type'],'image/png')
            self.assertEqual(client.get('/careers/logos/unknown.example.png').status_code,404)
            logo=client.get('/careers/logos/figma.com.png')
            self.assertEqual(logo.status_code,200)
            self.assertTrue(logo.content.startswith(b'\x89PNG'))

    def test_class_year_mentions_are_conservative_and_counted(self):
        def job(id,text):return {'id':id,'title':'Software Intern','role_type':'internship','company':'Example','location':'','description':text}
        first=job('first','Qualifications\nFirst or second-year undergraduate students may apply.')
        other=job('other','First-year masters students may apply.')
        excluded=job('excluded','This internship is not open to freshmen.')
        self.assertEqual(student_years(first)['years'],[1,2])
        self.assertEqual(student_years(other)['years'],[])
        self.assertEqual(student_years(excluded)['years'],[])
        self.assertEqual(student_years(job('mentor','You will mentor freshman students.'))['years'],[])
        data={'jobs':[first,other,excluded],'boards':[]}
        result=search_catalog(data,Search(student_year='first'))
        self.assertEqual(result['total'],1)
        self.assertEqual(sum(f['count'] for f in result['facets']['fields']),1)
        self.assertTrue(result['jobs'][0]['student_audience']['evidence'])

    def test_programs_share_search_filters_and_have_separate_counts(self):
        listing={'id':'feed:1','title':'Software Intern','role_type':'internship','company':'Example','location':'Boston, MA','description':'First-year undergraduate students may apply.'}
        with patch('hives.careers.api.program_jobs',return_value=program_jobs(datetime(2026,11,5,tzinfo=timezone.utc))):
            result=search_catalog({'jobs':[listing],'boards':[]},Search(include_programs=True,role_type='all',limit=100))
            self.assertEqual(result['total'],8)
            self.assertEqual(result['listing_total'],1)
            self.assertEqual(result['program_total'],7)
            self.assertEqual(sum(f['count'] for f in result['facets']['fields']),8)
            self.assertTrue(all(j['match']['score'] is None for j in result['jobs'] if j.get('is_program')))
            first=search_catalog({'jobs':[listing],'boards':[]},Search(include_programs=True,student_year='first',role_type='all'))
            self.assertEqual(first['listing_total'],1)
            self.assertEqual(first['program_total'],6)
            opened=search_catalog({'jobs':[listing],'boards':[]},Search(opportunity_type='program',program_status='application_window',role_type='all'))
            self.assertEqual(opened['program_total'],2)
            self.assertEqual(opened['listing_total'],0)
            self.assertEqual(opened['total'],next(f['count'] for f in opened['facets']['fields'] if f['value']=='science'))
            query=search_catalog({'jobs':[],'boards':[]},Search(include_programs=True,query='NVIDIA Ignite',role_type='all'))
            self.assertEqual(query['total'],1)
            self.assertEqual(query['jobs'][0]['status'],'closed')
            self.assertEqual(search_catalog({'jobs':[],'boards':[]},Search(include_programs=True,country='GB'))['total'],0)

    def test_main_page_integrates_programs_without_separate_launchpad(self):
        with TestClient(app) as client:
            page=client.get('/').text
            self.assertIn('value="program"',page)
            self.assertIn('id="student-year"',page)
            self.assertNotIn('id="launchpad"',page)
            self.assertIn('workbee-logo.png',page)
