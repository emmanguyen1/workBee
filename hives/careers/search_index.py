"""Public compact search records. Full descriptions and source excerpts stay in data."""
from copy import deepcopy
from hives.careers.matching import requirements,REQUIREMENTS_VERSION
from hives.careers.qualifications import qualification_snapshot,QUALIFICATION_VERSION
from hives.careers.opportunity_facts import opportunity_facts
from hives.careers.sectors import technical_role
from hives.careers.simplify import application_key

VERSION=1


def build(job,employer=None):
    from hives.careers.catalog import prepare
    employer=employer or {}
    base={'company':employer.get('name',''),'source':employer.get('source',''),'board':employer.get('board',''),'location':'','role_type':'other',**job}
    description=base.get('description','')
    if base.get('requirements_version')!=REQUIREMENTS_VERSION:
        base={**base,'requirements':requirements(description),'requirements_version':REQUIREMENTS_VERSION}
    if base.get('qualification_version')!=QUALIFICATION_VERSION:
        base={**base,'qualification_snapshot':qualification_snapshot(description),'qualification_version':QUALIFICATION_VERSION}
    prepared=prepare({'jobs':[base]})['jobs']
    public=deepcopy(prepared[0] if prepared else base)
    public['facts']=opportunity_facts(base)
    public['is_technical'],public['technical_evidence']=technical_role(base)
    public['application_key']=application_key(base)
    # Preserve quote equality/deduplication for scoring without sending duplicate prose.
    quote_ids={}
    def quote(value):
        if value not in quote_ids:quote_ids[value]='q:'+str(len(quote_ids))
        return quote_ids[value]
    for rule in public['requirements']:rule['quote']=quote(rule['quote'])
    for group in ('rules','other'):
        for rule in public['qualification_snapshot'][group]:rule['quote']=quote(rule['quote'])
    public.update(description='',has_description=bool(description.strip()),description_deferred=True,summary_version=VERSION)
    document=' '.join([base['title'],base['company'],*(base.get('locations') or [base.get('location','')]),description,base.get('search_text','')]).casefold()
    public.pop('search_text',None)
    return public,document
