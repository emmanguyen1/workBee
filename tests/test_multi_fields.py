import unittest
from unittest.mock import patch
from pydantic import ValidationError
from hives.careers.api import Search,search_catalog
from hives.careers.accounts import Preferences
from hives.careers.matching import Profile,match
from hives.careers.qualifications import qualification_snapshot,QUALIFICATION_VERSION
from hives.careers.taxonomy import career_field

class MultiFieldTests(unittest.TestCase):
    def test_more_fields_classify_the_role_not_just_the_employer(self):
        for title,expected in [('Registered Nurse','healthcare'),('Business Operations Analyst','business'),('Clinical Coordinator','healthcare'),('School Teacher','education'),('Environmental Scientist','environment'),('Property Manager','real_estate'),('Hotel Guest Services','hospitality'),('Community Outreach Specialist','public_service'),('Data Scientist','data')]:
            self.assertEqual(career_field(title),expected,title)
        self.assertEqual(career_field('Software Engineer','Healthcare'),'software')

    def test_multiple_options_are_or_within_group_and_and_across_groups(self):
        def job(id,title,loc,company,workplace):return {'id':id,'title':title,'location':loc,'company':company,'workplace':workplace,'description':'Requirements\nExcel required','role_type':'other'}
        jobs=[job('1','Registered Nurse','Boston, MA','A','onsite'),job('2','Business Operations Analyst','Toronto, ON, Canada','B','remote'),job('3','Software Engineer','Boston, MA','A','remote'),job('4','Business Operations Analyst','London, UK','A','hybrid')]
        data={'jobs':jobs,'boards':[]}
        request=Search(role_type='all',career_fields=['healthcare','business'],countries=['US','CA'],companies=['A','B'],workplaces=['remote','onsite'])
        result=search_catalog(data,request)
        self.assertEqual({j['id'] for j in result['jobs']},{'1','2'})
        counts={f['value']:f['count'] for f in result['facets']['fields']}
        self.assertEqual(counts['healthcare']+counts['business'],result['total'])
        self.assertEqual(counts['software'],1) # Field facet excludes only its own selections.
        region=search_catalog(data,Search(role_type='all',regions=['US-MA','CA-ON'],career_fields=['healthcare','business']))
        self.assertEqual(region['total'],2)
        self.assertEqual(Preferences(career_fields=['healthcare','business'],companies=['A','B']).career_fields,['healthcare','business'])
        with self.assertRaises(ValidationError):Search(career_fields=['fake-field'])

    def test_precomputed_public_qualifications_match_on_demand_results(self):
        description='Requirements\nPython required\nMust be currently enrolled\nMinimum GPA of 3.0\nStrong communication ability and willingness to learn.'
        profile=Profile(skills='Python | Built a class project',gpa=3.5,enrolled=True)
        expected=match({'description':description},profile)
        snapshot=qualification_snapshot(description)
        with patch('hives.careers.qualifications.qualification_snapshot',side_effect=AssertionError('Must use stored public analysis')):
            actual=match({'description':description,'qualification_snapshot':snapshot,'qualification_version':QUALIFICATION_VERSION},profile)
        self.assertEqual(actual,expected)
