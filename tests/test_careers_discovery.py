import unittest
from unittest.mock import patch
from hives.careers.matching import match
from hives.careers.api import Search, search_catalog
from hives.careers.branding import company_brand
from hives.careers.taxonomy import opportunity_types


def job(id, title, description='', location='Boston', source='greenhouse'):
    return {'id': id, 'title': title, 'description': description, 'location': location, 'company': 'Example', 'source': source, 'role_type': 'internship' if 'Intern' in title else 'other'}


class DiscoveryTests(unittest.TestCase):
    def test_field_count_equals_results_under_all_other_filters(self):
        jobs = [job('1', 'Marketing Intern', 'SEO'), job('2', 'Marketing Manager', 'SEO'), job('3', 'Marketing Intern', 'SEO', 'London'), job('4', 'Software Intern', 'Python')]
        data = {'jobs': jobs, 'boards': []}
        request = Search(role_type='internship', query='SEO', location='Boston', career_field='marketing')
        result = search_catalog(data, request)
        marketing = next(f for f in result['facets']['fields'] if f['value']=='marketing')
        self.assertEqual(marketing['count'], result['total'])
        self.assertEqual(result['total'], 1)
        zero = search_catalog(data, Search(role_type='internship', query='Python', career_field='marketing'))
        self.assertEqual(next(f['count'] for f in zero['facets']['fields'] if f['value']=='marketing'), 0)
        self.assertEqual(zero['total'], 0)
        self.assertEqual(next(f['count'] for f in zero['facets']['fields'] if f['value']=='software'), 1)

    def test_comparable_and_type_filters_affect_counts(self):
        data = {'jobs': [job('1', 'Marketing Intern', 'Requirements\nSEO'), job('2', 'Marketing Intern'), job('3', 'Research Intern', 'Requirements\nPython'), job('4', 'Research Scientist', 'Requirements\nPython')], 'boards': []}
        result = search_catalog(data, Search(role_type='all', comparable_only=True, opportunity_type='research'))
        self.assertEqual(result['total'], 2)
        self.assertEqual(sum(f['count'] for f in result['facets']['fields']), 2)
        intern = search_catalog(data, Search(role_type='all', opportunity_type='internship'))
        self.assertEqual(intern['total'], 3)
        for field in intern['facets']['fields']:
            selected=search_catalog(data, Search(role_type='all', opportunity_type='internship',career_field=field['value']))
            self.assertEqual(selected['total'],field['count'])
        self.assertEqual(opportunity_types('Research Internship', 'internship'), ['internship','research'])
        self.assertIn('research', opportunity_types('Anthropic Fellows Program','other'))

    def test_interest_lists_are_not_counted_as_current_openings(self):
        result=search_catalog({'jobs':[job('1','Interested in an internship?'),job('2','Marketing Intern')],'boards':[]},Search())
        self.assertEqual(result['total'],1)
        self.assertEqual(result['catalog_total'],1)

    def test_empty_profile_only_computes_visible_matches(self):
        data = {'jobs': [job(str(i),'Marketing Intern','Requirements\nSEO') for i in range(30)], 'boards': []}
        with patch('hives.careers.api.match', wraps=match) as compare:
            result=search_catalog(data, Search(limit=3))
            self.assertEqual(compare.call_count,3)
            self.assertEqual(result['effective_sort'],'newest')
            self.assertEqual(result['total'],30)

    def test_common_community_companies_have_branding(self):
        for name in ['TikTok','Waymo','American Express','Procter & Gamble','Ai2 (Allen Institute for AI)']:
            self.assertIsNotNone(company_brand(name)['company_logo_url'],name)
