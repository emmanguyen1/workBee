import unittest
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from hives.careers.deadlines import extract_deadline,deadline_info,recency
from hives.careers.api import Search,search_catalog

class DeadlineTests(unittest.TestCase):
    def test_only_explicit_unambiguous_deadlines(self):
        self.assertIsNone(extract_deadline('Internship starts January 10, 2027')['date'])
        self.assertEqual(extract_deadline('Apply by January 10, 2027')['date'],'2027-01-10')
        self.assertIsNone(extract_deadline('Apply by January 10, 2027\nApplication deadline February 10, 2027')['date'])
        self.assertIsNone(extract_deadline('Apply by January 10')['date'])
        self.assertIsNone(extract_deadline('Apply by January 10, 2027 for first round reviews')['date'])
        self.assertFalse(deadline_info({'description':'Apply by January 10, 2027 for first round reviews','deadline_info':{'date':'2027-01-10','source':'posting_text','quote':'Apply by January 10, 2027 for first round reviews'}},datetime(2027,1,11,tzinfo=timezone.utc))['expired'])
        self.assertTrue(deadline_info({'description':'Apply by January 10, 2027'},datetime(2027,1,11,tzinfo=timezone.utc))['expired'])
    def test_deadline_order_missing_last_and_sectors_alphabetical(self):
        jobs=[{'id':str(i),'title':'Software intern','company':'Example','location':'','description':text,'role_type':'internship'} for i,text in enumerate(['','Apply by January 20, 2030','Apply by January 10, 2030'])]
        result=search_catalog({'jobs':jobs,'boards':[]},Search(sort='deadline'))
        self.assertEqual([j['id'] for j in result['jobs']],['2','1','0'])
        labels=[s['label'] for s in result['facets']['sectors']]
        self.assertEqual(labels,sorted(labels,key=str.casefold))
    def test_recency_preserves_offset(self):
        self.assertEqual(recency({'published_at':'2027-01-01T12:00:00-05:00'}),recency({'published_at':'2027-01-01T17:00:00Z'}))

class PageTests(unittest.TestCase):
    def test_pages_have_unique_controls_and_search_precedes_sidebar(self):
        class IDs(HTMLParser):
            def __init__(self):super().__init__();self.ids=[]
            def handle_starttag(self,tag,attrs):
                for key,value in attrs:
                    if key=='id':self.ids.append(value)
        for page in ['page.html','account.html','practice.html','sandbox.html','prep.html','behavioral.html']:
            markup=(Path('hives/careers')/page).read_text();parser=IDs();parser.feed(markup)
            self.assertEqual(len(parser.ids),len(set(parser.ids)),page)
        search=Path('hives/careers/page.html').read_text()
        self.assertLess(search.index('id="keyword-search"'),search.index('class="filter-sidebar"'))
        self.assertIn('id="account-storage"',search)
        self.assertIn('id="account-private" class="hidden"',Path('hives/careers/account.html').read_text())


class SimplifiedFilterTests(unittest.TestCase):
    def test_sort_is_outside_sidebar_and_removed_filters_are_not_hidden_controls(self):
        class Controls(HTMLParser):
            def __init__(self):super().__init__();self.in_form=0;self.sort_in_form=None;self.ids=set();self.sort_attrs={}
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='form':self.in_form+=1
                if 'id' in attrs:self.ids.add(attrs['id'])
                if attrs.get('id')=='sort':self.sort_in_form=self.in_form;self.sort_attrs=attrs
            def handle_endtag(self,tag):
                if tag=='form':self.in_form-=1
        p=Controls();p.feed(Path('hives/careers/page.html').read_text())
        self.assertEqual(p.sort_in_form,0);self.assertEqual(p.sort_attrs.get('form'),'filters')
        self.assertFalse({'pay-filter','closing-window','recent-window'}&p.ids)
        account=Controls();account.feed(Path('hives/careers/account.html').read_text())
        self.assertFalse({'pay-filter','closing-window','recent-window'}&account.ids)
