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


if __name__ == '__main__':
    unittest.main()
