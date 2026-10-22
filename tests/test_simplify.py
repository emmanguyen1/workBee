import unittest

from hives.careers.simplify import normalize_list, deduplicate, SOURCE_URL
from hives.careers.matching import Profile, match


def listing(**values):
    return {"id": "one", "active": True, "is_visible": True, "terms": ["Summer 2027"], "title": "Engineering Intern", "company_name": "Example", "url": "https://jobs.lever.co/example/one", "locations": ["London", "New York"], "category": "Software", **values}


class SimplifyTests(unittest.TestCase):
    def test_active_visible_correct_season_only_and_no_invented_requirements(self):
        jobs = normalize_list([listing(), listing(id="closed", active=False), listing(id="hidden", is_visible=False), listing(id="old", terms=["Summer 2026"])])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source_url"], SOURCE_URL)
        self.assertEqual(jobs[0]["locations"], ["London", "New York"])
        self.assertEqual(jobs[0]["listing_status"], "community_listed")
        self.assertIsNone(match(jobs[0], Profile())["score"])
        self.assertFalse(jobs[0]["requirements_available"])

    def test_malformed_snapshot_fails_instead_of_closing_jobs(self):
        for rows in [[], {}, [{"id": "bad"}]]:
            with self.assertRaises(ValueError):
                normalize_list(rows)

    def test_duplicate_prefers_employer_description_and_preserves_attribution(self):
        community = normalize_list([listing(url="https://job-boards.greenhouse.io/example/jobs/123?gh_src=repo")])[0]
        direct = {**community, "id": "greenhouse:example:123", "source": "greenhouse", "apply_url": "https://boards.greenhouse.io/example/jobs/123", "description": "Requirements\nPython", "requirements_available": True}
        direct.pop("source_url")
        jobs = deduplicate([community, direct])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], direct["id"])
        self.assertIn("Python", jobs[0]["description"])
        self.assertEqual(jobs[0]["source_references"][0]["url"], SOURCE_URL)

    def test_lever_apply_link_dedup_and_distinct_postings(self):
        a = normalize_list([listing()])[0]
        b = {**a, "id": "lever:example:one", "source": "lever", "apply_url": a["apply_url"] + "/apply"}
        c = {**a, "id": "different", "apply_url": "https://jobs.lever.co/example/two"}
        self.assertEqual(len(deduplicate([a, b, c])), 2)
