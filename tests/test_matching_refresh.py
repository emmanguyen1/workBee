import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from hives.careers.app import app
from hives.careers.api import Search, search_catalog
from hives.careers.branding import company_brand
from hives.careers.matching import Profile, match


class MatchingRefreshTests(unittest.TestCase):
    def test_comma_list_matches_like_individual_skills(self):
        job = {"description": "Requirements\nPython and SQL required", "location": ""}
        combined = Profile(skills=[{"skill": " Python, SQL; python ", "evidence": "Built an API, with a database"}])
        separate = Profile(skills=[{"skill": "Python"}, {"skill": "SQL"}])
        self.assertEqual([s.skill for s in combined.skills], ["Python", "SQL"])
        self.assertEqual(combined.skills[0].evidence, "Built an API, with a database")
        self.assertEqual(match(job, combined)["score"], match(job, separate)["score"])
        self.assertEqual(match(job, combined)["score"], 100)

    def test_skill_normalization_preserves_best_evidence_and_limits(self):
        profile = Profile(skills="js, Python\nJavaScript | Student website, with charts")
        self.assertEqual(len(profile.skills), 2)
        self.assertEqual(profile.skills[0].evidence, "Student website, with charts")
        with self.assertRaises(ValidationError):
            Profile(skills=','.join('Skill'+str(i) for i in range(61)))

    def test_unscored_states_are_not_zero_percent_matches(self):
        self.assertIsNone(match({"description": "Requirements\nPython", "location": ""}, Profile())["score"])
        self.assertEqual(match({"description": "Requirements\nPython", "location": ""}, Profile())["assessment"], "needs_profile")
        no_description = match({"description": "", "location": ""}, Profile(skills="Python"))
        self.assertEqual(no_description["assessment"], "requirements_unavailable")
        self.assertFalse(no_description["comparable"])
        self.assertEqual(match({"description": "Join our team", "location": ""}, Profile(skills="Python"))["assessment"], "unrecognized_requirements")

    def test_outdated_stored_extraction_is_recomputed_for_new_tools(self):
        job = {"description": "Requirements\nPandas and NumPy", "location": "", "requirements": [], "requirements_version": 2}
        result = match(job, Profile(skills="pandas, numpy"))
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["assessment"], "assessed")

    def test_comparable_filter_and_explicit_score_ranking(self):
        base = {"company": "Figma", "location": "Boston", "title": "Intern", "role_type": "internship"}
        jobs = [{**base, "id": "missing", "description": ""}, {**base, "id": "zero", "description": "Requirements\nJava"}, {**base, "id": "good", "description": "Requirements\nPython"}]
        result = search_catalog({"jobs": jobs, "boards": []}, Search(profile=Profile(skills="Python")))
        self.assertEqual([j["id"] for j in result["jobs"]], ["good", "zero", "missing"])
        filtered = search_catalog({"jobs": jobs, "boards": []}, Search(profile=Profile(skills="Python"), comparable_only=True, sort="newest"))
        self.assertEqual(filtered["total"], 2)
        self.assertTrue(all(j["match"]["comparable"] for j in filtered["jobs"]))
        self.assertEqual(filtered["profile_skills"], ["Python"])

    def test_manual_requirements_compare_without_persisting(self):
        with patch('hives.careers.api.store.catalog', new=AsyncMock(side_effect=AssertionError('Must not persist or fetch jobs'))), TestClient(app) as client:
            response = client.post('/api/careers/match', json={"profile": {"skills": "Python, SQL"}, "description": "Requirements\nPython and SQL required"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["score"], 100)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(client.post('/api/careers/match',json={"profile": {}, "description": "short"}).status_code, 422)

    def test_assets_and_company_logo_fallback(self):
        known = company_brand('Figma')
        self.assertEqual(known['company_domain'], 'figma.com')
        self.assertTrue(known['company_logo_url'].startswith(('/careers/logos/figma.com.png','https://www.google.com/s2/favicons?')))
        unknown = company_brand('Unknown Example')
        self.assertIsNone(unknown['company_logo_url'])
        self.assertEqual(unknown['company_initials'], 'UE')
        with TestClient(app) as client:
            for name in ['styles.css', 'app.mjs', 'logic.mjs']:
                self.assertEqual(client.get('/careers/assets/'+name).status_code, 200)
            self.assertEqual(client.get('/careers/assets/accounts.py').status_code, 404)
