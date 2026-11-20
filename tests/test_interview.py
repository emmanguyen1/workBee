import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch


class TestInterview(unittest.TestCase):
    def setUp(self):
        from hives.careers.app import app
        self.client = TestClient(app)

    def _start(self, **kwargs):
        body = {
            'job_id': 'test-job-1',
            'job_title': 'Software Engineering Intern',
            'company': 'Acme Corp',
            'job_description': 'Build scalable APIs using Python and FastAPI.',
            'requirements': ['Python', 'FastAPI', 'REST APIs'],
            'career_field': 'engineering',
            **kwargs
        }
        with patch('hives.careers.bee.enabled', return_value=False):
            return self.client.post('/api/bee/interview/start', json=body)

    def test_interview_start_no_api_key(self):
        resp = self._start()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('session_id', data)
        self.assertIn('question', data)
        self.assertIn('total_questions', data)
        q = data['question']
        self.assertIn('index', q)
        self.assertIn('type', q)
        self.assertIn('text', q)
        self.assertIn('context', q)

    def test_interview_answer_missing_session(self):
        body = {
            'session_id': 'bad-id',
            'question_index': 0,
            'answer_text': 'Some answer text here.',
        }
        with patch('hives.careers.bee.enabled', return_value=False):
            resp = self.client.post('/api/bee/interview/answer', json=body)
        self.assertEqual(resp.status_code, 404)

    def test_interview_full_flow(self):
        # Start a session
        start_resp = self._start()
        self.assertEqual(start_resp.status_code, 200)
        start_data = start_resp.json()
        session_id = start_data['session_id']
        total = start_data['total_questions']

        answer_body_base = {
            'session_id': session_id,
            'answer_text': 'In my previous project, I identified the problem, assigned tasks, executed the plan, and achieved a 20% improvement in performance.',
        }

        completed = False
        for idx in range(total):
            body = {**answer_body_base, 'question_index': idx}
            with patch('hives.careers.bee.enabled', return_value=False):
                resp = self.client.post('/api/bee/interview/answer', json=body)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            # Check feedback keys on each answer
            feedback = data.get('feedback', {})
            self.assertIn('strengths', feedback)
            self.assertIn('improvements', feedback)
            self.assertIn('star_example', feedback)
            self.assertIn('score', feedback)

            if data.get('completed'):
                completed = True
                self.assertIsNone(data.get('next_question'))
                break

        self.assertTrue(completed, 'Interview should be completed after answering all questions')

    def test_practice_page_route(self):
        resp = self.client.get('/practice')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers.get('content-type', ''))
        self.assertIn('Practice with Bee', resp.text)
        self.assertIn('practice-customizer-form', resp.text)
        self.assertIn('industry-pills', resp.text)

    def test_distinct_pages_routes(self):
        # Sandbox route
        resp_sand = self.client.get('/sandbox')
        self.assertEqual(resp_sand.status_code, 200)
        self.assertIn('page-sandbox-editor', resp_sand.text)
        self.assertIn('page-sandbox-run', resp_sand.text)

        # Prep route
        resp_prep = self.client.get('/prep')
        self.assertEqual(resp_prep.status_code, 200)
        self.assertIn('prep-builder-form', resp_prep.text)
        self.assertIn('prep-generate-btn', resp_prep.text)

        # Behavioral route
        resp_behav = self.client.get('/behavioral')
        self.assertEqual(resp_behav.status_code, 200)
        self.assertIn('behavioral-competency-pills', resp_behav.text)
        self.assertIn('behavioral-questions-grid', resp_behav.text)

    def test_interview_industry_customization(self):
        from hives.careers.bee import local_interview_questions
        
        # Test Data & AI customization
        q_data = local_interview_questions('Machine Learning Intern', 'Databricks', 'data', ['PyTorch', 'SQL'])
        self.assertEqual(len(q_data), 3)
        self.assertIn('data science or machine learning workflow', q_data[1]['text'])

        # Test Healthcare customization
        q_health = local_interview_questions('Clinical Research Associate', 'Pfizer', 'healthcare', ['GCP', 'Protocols'])
        self.assertEqual(len(q_health), 3)
        self.assertIn('patient care, clinical data, or protocol compliance', q_health[1]['text'])

        # Test Product & UX customization
        q_prod = local_interview_questions('Product Designer', 'Figma', 'product', ['Figma', 'UX'])
        self.assertEqual(len(q_prod), 3)
        self.assertIn('user experience and make design trade-offs', q_prod[1]['text'])

        # Test Hardware & Aerospace customization
        q_aero = local_interview_questions('Robotics Engineer', 'SpaceX', 'hardware', ['ROS', 'C++'])
        self.assertEqual(len(q_aero), 3)
        self.assertIn('hardware or robotics project', q_aero[1]['text'])

        # Test Finance customization
        q_fin = local_interview_questions('Quant Analyst', 'Citadel', 'finance', ['Python', 'Stochastic'])
        self.assertEqual(len(q_fin), 3)
        self.assertIn('quantitative analysis, financial model, or ledger system', q_fin[1]['text'])

    def test_interview_start_with_initial_question_and_competency(self):
        scenario_prompt = 'Tell me about a time you had a fundamental disagreement with a colleague or manager.'
        resp = self._start(
            initial_question=scenario_prompt,
            competency='conflict',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('question', data)
        q = data['question']
        self.assertEqual(q['index'], 0)
        self.assertEqual(q['type'], 'behavioral')
        self.assertEqual(q['text'], scenario_prompt)
        self.assertIn('STAR Competency: Conflict', q['context'])

    def test_practice_page_has_scenario_banner(self):
        resp = self.client.get('/practice')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="practice-scenario-banner"', resp.text)
        self.assertIn('id="scenario-banner-text"', resp.text)
        self.assertIn('id="scenario-clear-btn"', resp.text)

    def test_behavioral_page_has_deep_link_scenarios(self):
        resp = self.client.get('/behavioral')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('href="/practice?competency=conflict&prompt=', resp.text)
        self.assertIn('data-competency="tradeoffs"', resp.text)
        self.assertIn('data-competency="impact"', resp.text)


if __name__ == '__main__':
    unittest.main()
