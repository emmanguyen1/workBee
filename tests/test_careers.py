import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from hives.careers.app import app
from hives.careers.collector import JobCollector
from hives.careers.feeds import fetch_board, normalize, plain, role_type
from hives.careers.matching import Profile, SkillEvidence, match, requirements
from hives.careers.api import Search, search_catalog
from hives.careers.taxonomy import career_field, location_matches


class MatchingTests(unittest.TestCase):
    def test_alternatives_preferred_and_evidence(self):
        job = {"description": "Requirements\nExperience with Python or Java\nNice to haves\nDocker", "location": "Boston"}
        result = match(job, Profile(skills=[SkillEvidence(skill="java", evidence="Built a compiler")], location="Boston"))
        self.assertEqual(result["score"], 67)
        self.assertEqual(result["checks"][0]["skills"], ["Python", "Java"])
        self.assertEqual(result["checks"][0]["evidence"][0]["text"], "Built a compiler")
        self.assertEqual(result["checks"][1]["kind"], "preferred")
        self.assertEqual(result["location_fit"], "matches")

    def test_word_boundaries_and_negated_requirement(self):
        checks = requirements("JavaScript experience required\nNo Docker experience required\nMust know C++ and C#")
        self.assertNotIn("Java", [s for c in checks for s in c["skills"]])
        self.assertEqual(next(c for c in checks if c["skills"] == ["Docker"])["kind"], "mentioned")
        self.assertEqual(len([c for c in checks if c["skills"] in [["C++"], ["C#"]]]), 2)

    def test_eligibility_unknowns_and_conflicts(self):
        job = {"description": "Must be enrolled in a degree program.\nGraduating between 2027 and 2029.\nWe cannot sponsor visas.", "location": ""}
        unknown = match(job, Profile())
        self.assertTrue(all(c["status"] == "unknown" for c in unknown["eligibility"]))
        result = match(job, Profile(enrolled=False, graduation_year=2030, needs_sponsorship=True))
        self.assertEqual([c["status"] for c in result["eligibility"]], ["conflict"] * 3)
        self.assertTrue(result["has_conflict"])
        self.assertIsNone(result["score"])

    def test_mentions_do_not_claim_required_skills(self):
        result = match({"description": "Our platform uses Python.", "location": ""}, Profile())
        self.assertIsNone(result["score"])
        self.assertEqual(result["checks"][0]["kind"], "mentioned")

    def test_nontechnical_aliases_and_gpa(self):
        job = {"description": "Requirements\nExperience with financial modelling and PowerBI\nMinimum GPA of 3.2", "location": ""}
        result = match(job, Profile(skills=[SkillEvidence(skill="financial modeling"), SkillEvidence(skill="Power BI")], gpa=3.1))
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["has_conflict"])
        self.assertEqual(result["eligibility"][0]["criterion"], "Minimum GPA (4.0 scale)")
        unknown = match(job, Profile())
        self.assertEqual(unknown["eligibility"][0]["status"], "unknown")

    def test_secondary_office_matches_profile(self):
        job = {"description": "", "location": "London", "locations": ["London", "Dublin"]}
        self.assertEqual(match(job, Profile(location="Dublin"))["location_fit"], "matches")


class FeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_feed_formats_and_lever_pagination(self):
        calls = []
        def handler(request):
            calls.append(request)
            if request.url.host == "boards-api.greenhouse.io":
                return httpx.Response(200, json={"jobs": [{"id": 1, "title": "Engineering Intern", "content": "<p>Python</p>", "location": {"name": "NYC"}, "absolute_url": "https://example.com/job"}]})
            if request.url.host == "api.ashbyhq.com":
                return httpx.Response(200, json={"jobs": [{"id": "2", "title": "Engineer", "employmentType": "Intern", "descriptionPlain": "SQL", "workplaceType": "Hybrid"}, {"id": "hidden", "title": "Intern", "isListed": False}]})
            if request.url.params["skip"] == "0":
                return httpx.Response(200, json=[{"id": str(i), "text": "New Grad Engineer", "lists": [{"text": "Requirements", "content": "<li>Python</li>"}]} for i in range(100)])
            return httpx.Response(200, json=[])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for source in ["greenhouse", "ashby", "lever"]:
                rows = await fetch_board(client, {"source": source, "board": "example", "name": "Example"})
                self.assertEqual(len(rows), 100 if source == "lever" else 1)
                self.assertIn("Python" if source != "ashby" else "SQL", rows[0]["description"])
                self.assertEqual(rows[0]["role_type"], "new_grad" if source == "lever" else "internship")
        self.assertEqual(len(calls), 4)

    async def test_rate_limit_does_not_overwrite_snapshot(self):
        bot = JobCollector()
        employer = {"source": "greenhouse", "board": "example", "name": "Example"}
        error = httpx.HTTPStatusError("limited", request=httpx.Request("GET", "https://example.com"), response=httpx.Response(429))
        with patch("hives.careers.collector.employers", return_value=[employer]), patch("hives.careers.collector.fetch_board", new=AsyncMock(side_effect=error)), patch("hives.careers.collector.store.initialize", new=AsyncMock()), patch("hives.careers.collector.store.record_error", new=AsyncMock()) as record, patch("hives.careers.collector.store.save_snapshot", new=AsyncMock()) as save, patch.object(bot, "publish", new=AsyncMock()):
            await bot.run_once()
            save.assert_not_awaited()
            record.assert_awaited_once()

    def test_html_urls_and_role_boundaries(self):
        self.assertEqual(plain("<script>secret</script><p>Hello</p><li>World</li>"), "Hello\nWorld")
        job = normalize({"source": "greenhouse", "board": "x", "name": "X"}, {"id": 1, "title": "Internal tools engineer", "absolute_url": "javascript:alert(1)"})
        self.assertEqual(job["apply_url"], "")
        self.assertEqual(job["role_type"], "other")
        self.assertEqual(role_type("Software Co-op"), "internship")

    def test_early_career_and_field_classification(self):
        for title, expected in [("Junior Accountant", "entry_level"), ("Graduate Analyst", "new_grad"), ("Marketing Apprentice", "apprenticeship"), ("Senior Software Engineer", "other"), ("Internal Audit Manager", "other")]:
            self.assertEqual(role_type(title), expected)
        for title, expected in [("Marketing Intern", "marketing"), ("Mechanical Design Engineer Intern", "engineering"), ("Recruiting Coordinator", "people"), ("Financial Analyst", "finance"), ("Software Engineer", "software"), ("Clinical Research Intern", "healthcare"), ("Data Scientist Intern", "data")]:
            self.assertEqual(career_field(title), expected)

    def test_secondary_locations_and_workplace_are_preserved(self):
        job = normalize({"name": "Example", "source": "ashby", "board": "example"}, {"id": "a", "title": "Design Intern", "location": "London", "secondaryLocations": [{"location": "Dublin"}], "workplaceType": "Hybrid"})
        self.assertEqual(job["locations"], ["London", "Dublin"])
        self.assertEqual(job["workplace"], "hybrid")

    def test_location_aliases_boundaries_and_no_cross_office_mix(self):
        self.assertTrue(location_matches("UK", ["London, United Kingdom"]))
        self.assertTrue(location_matches("NYC", ["New York, NY"]))
        self.assertTrue(location_matches("USA", ["Remote, United States"]))
        self.assertFalse(location_matches("US", ["Australia"]))
        self.assertFalse(location_matches("CA", ["Canada"]))
        self.assertFalse(location_matches("London Canada", ["London, UK", "Toronto, Canada"]))


class ApiTests(unittest.TestCase):
    def test_combined_field_geography_workplace_and_stage_filters(self):
        jobs = [{"id": "1", "title": "Marketing Intern", "company": "Example", "location": "London", "locations": ["London", "Dublin"], "description": "Requirements\nSEO", "role_type": "internship", "workplace": "remote"}, {"id": "2", "title": "Junior Accountant", "company": "Other", "location": "New York", "description": "Accounting", "role_type": "other"}, {"id": "3", "title": "Senior Engineer", "company": "Other", "location": "London", "description": "Python", "role_type": "other"}]
        data = {"jobs": jobs, "boards": []}
        result = search_catalog(data, Search(career_field="marketing", location="Dublin", workplace="remote", company="Example", query="SEO Intern"))
        self.assertEqual([j["id"] for j in result["jobs"]], ["1"])
        self.assertEqual(result["catalog_total"], 3)
        self.assertEqual(result["early_career_total"], 2)
        self.assertEqual(search_catalog(data, Search(role_type="all"))["total"], 3)
        self.assertEqual(search_catalog(data, Search(role_type="entry_level"))["jobs"][0]["id"], "2")
        self.assertEqual(search_catalog(data, Search(location="Canada", workplace="remote"))["total"], 0)

    def test_newest_sort_uses_publication_when_available(self):
        jobs = [{"id": "1", "title": "Intern", "company": "Example", "location": "", "description": "", "role_type": "internship", "first_seen": "2026-10-21", "published_at": "2026-10-23"}, {"id": "2", "title": "Intern", "company": "Example", "location": "", "description": "", "role_type": "internship", "first_seen": "2026-10-22", "published_at": "2026-10-20"}]
        result = search_catalog({"jobs": jobs, "boards": []}, Search(sort="newest", limit=1))
        self.assertEqual(result["jobs"][0]["id"], "1")
        self.assertIn("match", result["jobs"][0])

    def test_recent_days_filter_isolates_golden_window_and_recent_drops(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        fresh_time = (now - timedelta(hours=6)).isoformat()
        medium_time = (now - timedelta(days=2)).isoformat()
        old_time = (now - timedelta(days=10)).isoformat()
        jobs = [
            {"id": "fresh", "title": "Intern", "company": "CoA", "location": "", "description": "", "role_type": "internship", "first_seen": fresh_time},
            {"id": "medium", "title": "Intern", "company": "CoB", "location": "", "description": "", "role_type": "internship", "first_seen": medium_time},
            {"id": "old", "title": "Intern", "company": "CoC", "location": "", "description": "", "role_type": "internship", "first_seen": old_time},
        ]
        res_1 = search_catalog({"jobs": jobs, "boards": []}, Search(recent_days=1))
        self.assertEqual([j["id"] for j in res_1["jobs"]], ["fresh"])

        res_3 = search_catalog({"jobs": jobs, "boards": []}, Search(recent_days=3))
        self.assertEqual([j["id"] for j in res_3["jobs"]], ["fresh", "medium"])

        res_all = search_catalog({"jobs": jobs, "boards": []}, Search(recent_days=0))
        self.assertEqual(len(res_all["jobs"]), 3)

    def test_filter_match_and_private_response(self):
        jobs = [{"id": "one", "title": "Intern", "company": "Example", "location": "Boston", "description": "Requirements\nPython", "role_type": "internship"}, {"id": "two", "title": "Senior", "company": "Example", "location": "Boston", "description": "Java", "role_type": "other"}]
        with patch("hives.careers.api.store.catalog", new=AsyncMock(return_value={"jobs": jobs, "boards": []})), TestClient(app) as client:
            response = client.post("/api/careers/search", json={"profile": {"skills": [{"skill": "Python", "evidence": "My project"}]}})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            data = response.json()
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["jobs"][0]["match"]["score"], 100)
            self.assertEqual(client.post("/api/careers/search", json={"limit": 1000}).status_code, 422)
            self.assertIn('id="keyword-search"', client.get("/careers").text)
            self.assertIn("workBee", client.get("/hivepath").text)
            self.assertNotIn("Kalshi", client.get("/").text)
            self.assertEqual(client.get("/kalshi").status_code,404)

    def test_database_unavailable_is_actionable(self):
        with patch("hives.careers.api.store.catalog", new=AsyncMock(side_effect=OSError("private connection string"))), TestClient(app) as client:
            response = client.post("/api/careers/search", json={})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private connection", response.text)


if __name__ == "__main__":
    unittest.main()
