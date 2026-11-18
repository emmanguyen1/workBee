import unittest
from fastapi.testclient import TestClient


class TestInstantApply(unittest.TestCase):
    def setUp(self):
        from hives.careers.app import app
        self.client = TestClient(app)

    def test_instant_apply_validation(self):
        # Missing required email
        resp = self.client.post('/api/careers/apply/instant', json={
            'job_id': 'job-123',
            'applicant_name': 'Taylor Swift',
            'applicant_email': 'invalid-email',
        })
        self.assertEqual(resp.status_code, 400)

        # Missing name (Pydantic min_length validation returns 422)
        resp = self.client.post('/api/careers/apply/instant', json={
            'job_id': 'job-123',
            'applicant_name': '',
            'applicant_email': 'taylor@example.com',
        })
        self.assertIn(resp.status_code, (400, 422))

    def test_instant_apply_success(self):
        resp = self.client.post('/api/careers/apply/instant', json={
            'job_id': 'figma-swe-intern',
            'applicant_name': 'Emma Nguyen',
            'applicant_email': 'emma@usf.edu',
            'applicant_phone': '(555) 987-6543',
            'school': 'University of South Florida',
            'major': 'Computer Science',
            'graduation_year': '2027',
            'work_authorization': 'cpt_opt',
            'portfolio_url': 'https://github.com/ngduonn',
            'start_date': '2027-05-15',
            'note': 'Excited about Figma design systems and developer tooling.',
            'has_resume': True,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'applied')
        self.assertEqual(data.get('job_id'), 'figma-swe-intern')
        self.assertIn('applied_at', data)
        self.assertIn('message', data)


if __name__ == '__main__':
    unittest.main()
